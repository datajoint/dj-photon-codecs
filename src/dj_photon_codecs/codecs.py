"""Codec for photon-limited movies with Anscombe transformation."""

from __future__ import annotations

from typing import Any

import numpy as np
import zarr
from anscombe_transform import AnscombeTransformV3
from datajoint import DataJointError
from datajoint.builtin_codecs import SchemaCodec
from zarr.codecs import BloscCodec, BytesCodec

# Raw photon counts: one count per photon, and zero counts without light.
CONVERSION_GAIN = 1.0
ZERO_LEVEL = 0
# The Anscombe lookup table covers inputs up to this value; larger ones would be clipped.
MAX_COUNT = 0x7FFF
# The transform maps counts up to MAX_COUNT to fewer than 1024 levels.
ENCODED_DTYPE = "uint16"


def _require_context(context: dict[str, Any] | None, *names: str) -> dict[str, Any]:
    """
    Return ``context``, checked to carry ``names``.

    DataJoint 2.3.4 and later pass ``context`` to every codec that declares it:
    ``schema``, ``table``, ``field``, and ``config`` on insert, ``config`` on
    fetch. The codec reads them there only, never from underscore keys in ``key``.
    """
    missing = [n for n in names if context is None or context.get(n) is None]
    if context is None or missing:
        raise DataJointError(
            "<photon> needs the context that DataJoint 2.3.4 and later pass to codecs "
            f"(missing: {', '.join(missing)}); install datajoint>=2.3.4"
        )
    return context


def _primary_key(key: dict[str, Any] | None) -> dict[str, Any]:
    """The primary key values in ``key``, without the underscore keys DataJoint 2.3 adds."""
    return {k: v for k, v in (key or {}).items() if not k.startswith("_")}


class PhotonCodec(SchemaCodec):
    """
    Store photon-limited movies with Anscombe variance stabilization.

    The ``<photon@>`` codec stores movies of raw photon counts as Zarr arrays
    in object storage. Each chunk passes through the Anscombe transform from
    the ``anscombe-transform`` package before Blosc/Zstd compression. The
    transform equalizes the Poisson noise across intensity levels and
    re-quantizes the counts to fewer levels, which compress much better. The
    quantization step is below the photon shot noise.

    Reading the array applies the inverse transform, so a fetch returns photon
    counts in the original dtype (16-bit for 8-bit input), within the
    quantization step.

    Example::

        import datajoint as dj
        import numpy as np

        schema = dj.Schema('calcium_imaging')

        @schema
        class Recording(dj.Manual):
            definition = '''
            recording_id : int32
            ---
            movie : <photon@>  # photon-limited movie
            '''

        # Insert raw photon counts
        movie = np.random.poisson(lam=10, size=(1000, 512, 512)).astype('uint16')
        Recording.insert1({'recording_id': 1, 'movie': movie})

        # Fetch returns a read-only Zarr array
        zarr_array = (Recording & {'recording_id': 1}).fetch1('movie')
        frame_100 = zarr_array[100]      # one frame
        snippet = zarr_array[100:200]    # a frame range

    Storage Structure::

        {store_root}/{schema}/{table}/{pk}/{field}_{token}.zarr/

    Notes
    -----
    - Input must be non-negative integer photon counts, at most 32767.
    - 8-bit movies are stored and fetched as 16-bit.
    - Chunks hold up to 100 frames with full spatial dimensions, for
      frame-by-frame access.

    See Also
    --------
    anscombe-transform : Anscombe transform codec for Zarr.
    dj-zarr-codecs : Zarr array storage codec.
    """

    name = "photon"
    CODEC_VERSION = "1.0"  # Data format version for backward compatibility

    def validate(self, value: Any) -> None:
        """
        Validate that value is a movie of photon counts.

        Parameters
        ----------
        value : Any
            Value to validate.

        Raises
        ------
        DataJointError
            If value is not a numpy array of 3 or more dimensions with an
            integer dtype and values from 0 to 32767.
        """
        if not isinstance(value, np.ndarray):
            raise DataJointError(f"<photon> requires numpy.ndarray, got {type(value).__name__}")
        if value.dtype.kind not in "iu":
            raise DataJointError(
                f"<photon> requires an integer array of photon counts, got dtype {value.dtype}"
            )
        if value.ndim < 3:
            raise DataJointError(
                f"<photon> requires 3D+ arrays (time, height, width, ...), got {value.ndim}D"
            )
        if value.size and value.min() < 0:
            raise DataJointError(
                "<photon> requires non-negative values (photon counts cannot be negative)"
            )
        if value.size and value.max() > MAX_COUNT:
            raise DataJointError(f"<photon> supports photon counts up to {MAX_COUNT}")

    def encode(
        self,
        value: np.ndarray,
        *,
        key: dict | None = None,
        context: dict | None = None,
        store_name: str | None = None,
    ) -> dict:
        """
        Encode a photon-limited movie as an Anscombe-filtered Zarr array.

        Parameters
        ----------
        value : np.ndarray
            Movie of raw photon counts (3D+: time, height, width, ...).
        key : dict, optional
            Primary key values for path construction.
        context : dict, optional
            ``schema``, ``table``, ``field``, and ``config`` of the insert, as
            DataJoint passes them.
        store_name : str, optional
            Name of the object store to use.

        Returns
        -------
        dict
            Metadata stored in database: path, store, codec_version, shape, dtype, transform.

        Raises
        ------
        DataJointError
            If ``context`` lacks the ``schema``, ``table``, ``field``, or
            ``config`` that DataJoint 2.3.4 and later pass, or if encoding fails.
        """
        context = _require_context(context, "schema", "table", "field", "config")
        config = context["config"]
        self.validate(value)
        if value.dtype.itemsize < 2:
            # The inverse lookup table spans counts up to MAX_COUNT, beyond 8 bits.
            value = value.astype(np.uint16 if value.dtype.kind == "u" else np.int16)
        try:
            path, _token = self._build_path(
                context["schema"],
                context["table"],
                context["field"],
                _primary_key(key),
                ext=".zarr",
                store_name=store_name,
                config=config,
            )
            store_map = self._get_backend(store_name, config=config).get_fsmap(path)

            # Chunk along time so frames can be read in sequence.
            chunks = (min(100, value.shape[0]), *value.shape[1:])
            zarr.create_array(
                store=store_map,
                data=value,
                chunks=chunks,
                filters=[
                    AnscombeTransformV3(
                        zero_level=ZERO_LEVEL,
                        conversion_gain=CONVERSION_GAIN,
                        encoded_dtype=ENCODED_DTYPE,
                        decoded_dtype=str(value.dtype),
                    )
                ],
                # The filter's output is uint16 whatever the input dtype, so the
                # serializer names its byte order.
                serializer=BytesCodec(endian="little"),
                compressors=BloscCodec(cname="zstd", clevel=5, shuffle="bitshuffle"),
                attributes={"codec_name": self.name, "codec_version": self.CODEC_VERSION},
            )
        except Exception as e:
            raise DataJointError(f"Failed to encode photon movie: {e}") from e

        return {
            "path": path,
            "store": store_name,
            "codec_version": self.CODEC_VERSION,
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "transform": "anscombe",
        }

    def decode(
        self,
        stored: dict,
        *,
        key: dict | None = None,
        context: dict | None = None,
    ) -> zarr.Array:
        """
        Open a stored photon-limited movie.

        Parameters
        ----------
        stored : dict
            Metadata from database containing path and store.
        key : dict, optional
            Primary key values (unused).
        context : dict, optional
            ``config`` of the fetching connection, as DataJoint passes it.

        Returns
        -------
        zarr.Array
            Read-only Zarr array. Reading it applies the inverse Anscombe
            transform and returns photon counts in the original dtype.

        Raises
        ------
        DataJointError
            If ``context`` lacks the ``config`` that DataJoint 2.3.4 and later
            pass, or if decoding fails.
        """
        del key  # the stored metadata locates the array
        config = _require_context(context, "config")["config"]
        try:
            backend = self._get_backend(stored.get("store"), config=config)
            z = zarr.open_array(backend.get_fsmap(stored["path"]), mode="r")
        except Exception as e:
            raise DataJointError(f"Failed to decode photon movie: {e}") from e

        # Check codec version for backward compatibility.
        # Priority: Zarr attrs > DB metadata > default "1.0"
        version = str(z.attrs.get("codec_version", stored.get("codec_version", "1.0")))
        if not version.startswith("1."):
            raise DataJointError(
                f"Unsupported photon codec version: {version}. "
                "Upgrade dj-photon-codecs or migrate data."
            )
        return z

"""Codec for photon-limited movies with Anscombe transformation."""

from __future__ import annotations

from typing import Any

import numpy as np
import zarr

try:
    from anscombe import generalized_anscombe
except ImportError as e:
    raise ImportError(
        "anscombe-transform is required. Install with: pip install anscombe-transform"
    ) from e

try:
    import datajoint as dj
    from datajoint import DataJointError
    from datajoint.builtin_codecs import SchemaCodec
except ImportError as e:
    raise ImportError(
        "datajoint>=2.0.0a22 is required. Install with: pip install 'datajoint>=2.0.0a22'"
    ) from e


class PhotonCodec(SchemaCodec):
    """
    Store photon-limited movies with Anscombe variance stabilization.

    The ``<photon@>`` codec applies Anscombe transformation to photon-limited
    imaging data (Poisson noise) to stabilize variance, then stores in Zarr
    format for efficient access.

    **Why Anscombe Transformation:**
    - Converts Poisson-distributed photon counts to approximately Gaussian noise
    - Stabilizes variance across intensity levels
    - Enables better compression and denoising
    - Standard preprocessing for low-light microscopy

    **Storage:**
    - Transformed data stored in Zarr with movie-optimized chunking
    - Metadata includes transform parameters for inverse operation
    - Schema-addressed paths: ``{schema}/{table}/{pk}/{field}.zarr``

    Example::

        import datajoint as dj
        import numpy as np

        schema = dj.Schema('calcium_imaging')

        @schema
        class Recording(dj.Manual):
            definition = '''
            recording_id : int
            ---
            movie : <photon@>  # Photon-limited movie with Anscombe transform
            '''

        # Insert photon-limited movie (raw photon counts)
        movie = np.random.poisson(lam=10, size=(1000, 512, 512))
        Recording.insert1({
            'recording_id': 1,
            'movie': movie,
        })

        # Fetch returns Zarr array (transformed data)
        zarr_array = (Recording & {'recording_id': 1}).fetch1('movie')

        # Access movie frames efficiently
        frame_100 = zarr_array[100]  # Single frame
        snippet = zarr_array[100:200]  # Frame range

        # Apply inverse transform if needed
        from anscombe import generalized_inverse_anscombe
        original = generalized_inverse_anscombe(zarr_array[:])

    Storage Structure::

        {store_root}/{schema}/{table}/{pk}/{field}.zarr/
            .zarray           # Zarr metadata
            .zattrs           # Transform parameters
            0.0.0, 0.1.0, ... # Chunks (time, y, x)

    Notes
    -----
    - Input data should be raw photon counts (non-negative integers or floats)
    - Transformed data is float64 with stabilized variance
    - Chunking optimized for temporal access (process frames sequentially)
    - For inverse transformation, use anscombe.generalized_inverse_anscombe()

    See Also
    --------
    anscombe-transform : Anscombe variance stabilization library
    dj-zarr-codecs : Zarr array storage codec
    """

    name = "photon"
    CODEC_VERSION = "1.0"  # Data format version for backward compatibility

    def validate(self, value: Any) -> None:
        """
        Validate that value is a numpy array suitable for photon-limited data.

        Parameters
        ----------
        value : Any
            Value to validate.

        Raises
        ------
        DataJointError
            If value is not a numpy array, has object dtype, or contains
            negative values (invalid for photon counts).
        """
        if not isinstance(value, np.ndarray):
            raise DataJointError(
                f"<photon> requires numpy.ndarray, got {type(value).__name__}"
            )
        if value.dtype == object:
            raise DataJointError("<photon> does not support object dtype arrays")
        if value.ndim < 3:
            raise DataJointError(
                f"<photon> requires 3D+ arrays (time, height, width, ...), got {value.ndim}D"
            )
        if np.any(value < 0):
            raise DataJointError(
                "<photon> requires non-negative values (photon counts cannot be negative)"
            )

    def encode(
        self,
        value: np.ndarray,
        *,
        key: dict | None = None,
        store_name: str | None = None,
    ) -> dict:
        """
        Encode photon-limited movie with Anscombe transformation to Zarr.

        Parameters
        ----------
        value : np.ndarray
            Photon-limited movie data (3D+: time, height, width, ...).
            Should be raw photon counts (non-negative).
        key : dict, optional
            Primary key values for path construction.
        store_name : str, optional
            Name of the object store to use.

        Returns
        -------
        dict
            Metadata stored in database: path, store, codec_version, shape, dtype, transform.

        Raises
        ------
        DataJointError
            If encoding fails.
        """
        try:
            # Validate input
            self.validate(value)

            # Extract context from key
            schema, table, field, primary_key = self._extract_context(key)

            # Build schema-addressed path
            path, _token = self._build_path(
                schema, table, field, primary_key, ext=".zarr", store_name=store_name
            )

            # Get storage backend
            backend = self._get_backend(store_name)

            # Get fsspec mapper for Zarr write
            store_map = backend.get_fsmap(path)

            # Apply Anscombe transformation
            # Default parameters: gain=1, offset=0, variance=0 (Poisson noise)
            transformed = generalized_anscombe(value, gain=1.0, offset=0.0, variance=0.0)

            # Optimize chunking for temporal access (movies)
            # Chunk along time axis to enable efficient frame-by-frame processing
            chunk_time = min(100, value.shape[0])  # Max 100 frames per chunk
            chunks = (chunk_time,) + value.shape[1:]  # Full spatial dimensions

            # Write array to Zarr with chunking and compression
            zarr.save_array(
                store_map,
                transformed,
                chunks=chunks,
                compressor=zarr.Blosc(cname="zstd", clevel=5, shuffle=zarr.Blosc.BITSHUFFLE),
            )

            # Store transform parameters in Zarr attributes
            z = zarr.open(store_map, mode="r+")
            z.attrs["codec_version"] = self.CODEC_VERSION
            z.attrs["codec_name"] = self.name
            z.attrs["anscombe_gain"] = 1.0
            z.attrs["anscombe_offset"] = 0.0
            z.attrs["anscombe_variance"] = 0.0
            z.attrs["original_dtype"] = str(value.dtype)

            # Return metadata for database storage
            return {
                "path": path,
                "store": store_name,
                "codec_version": self.CODEC_VERSION,
                "shape": list(value.shape),
                "dtype": str(transformed.dtype),
                "transform": "anscombe",
            }

        except Exception as e:
            raise DataJointError(f"Failed to encode photon movie: {e}") from e

    def decode(self, stored: dict, *, key: dict | None = None) -> zarr.Array:
        """
        Decode photon-limited movie from Zarr storage.

        Parameters
        ----------
        stored : dict
            Metadata from database containing path and store.
        key : dict, optional
            Primary key values (unused).

        Returns
        -------
        zarr.Array
            Read-only Zarr array containing Anscombe-transformed data.
            Use ``anscombe.generalized_inverse_anscombe()`` to recover
            original photon counts if needed.

        Notes
        -----
        The returned array contains transformed data. To get original scale:

            >>> from anscombe import generalized_inverse_anscombe
            >>> zarr_array = (MyTable & key).fetch1('movie')
            >>> original = generalized_inverse_anscombe(zarr_array[:])

        Transform parameters are stored in ``zarr_array.attrs``.

        Raises
        ------
        DataJointError
            If decoding fails.
        """
        try:
            # Get storage backend
            backend = self._get_backend(stored.get("store"))

            # Get fsspec mapper for Zarr path
            store_map = backend.get_fsmap(stored["path"])

            # Open Zarr array (read-only)
            z = zarr.open(store_map, mode="r")

            # Check codec version for backward compatibility
            # Priority: Zarr attrs > DB metadata > default "1.0"
            version = z.attrs.get(
                "codec_version", stored.get("codec_version", "1.0")
            )

            # All v1.x versions are compatible
            if version.startswith("1."):
                return z
            else:
                raise DataJointError(
                    f"Unsupported photon codec version: {version}. "
                    f"Upgrade dj-photon-codecs or migrate data."
                )

        except Exception as e:
            raise DataJointError(f"Failed to decode photon movie: {e}") from e

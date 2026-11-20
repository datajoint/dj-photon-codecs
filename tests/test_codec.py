import datajoint as dj
import numpy as np
import pytest
import zarr

from dj_photon_codecs import PhotonCodec

# anscombe-transform 1.0.0 builds its inverse lookup table by the rank of each
# encoded level, not by the level itself. With a conversion gain of 1 (raw
# photon counts) the forward table skips levels 1 and 3, so decoded counts come
# back about 2 levels too high. Remove this mark once anscombe-transform ships
# the fix; strict=True makes the test fail as soon as it passes.
ANSCOMBE_INVERSE_BUG = pytest.mark.xfail(
    strict=True,
    reason="anscombe-transform 1.0.0 inverts its lookup table by rank (levels 1 and 3 are skipped)",
)


def _movie(dtype="uint16", shape=(5, 8, 8), lam=20.0):
    rng = np.random.default_rng(42)
    return rng.poisson(lam=lam, size=shape).astype(dtype)


def _assert_close(decoded, movie):
    """Within the quantization step of the transform: half the shot noise, plus rounding."""
    error = np.abs(decoded.astype(float) - movie.astype(float))
    assert np.all(error <= np.sqrt(movie) / 2 + 1)


def _context(**overrides):
    context = {"schema": "s", "table": "t", "field": "movie", "config": dj.config}
    context.update(overrides)
    return context


@pytest.mark.parametrize(
    ("dtype", "stored_dtype"),
    [("uint8", "uint16"), ("int8", "int16"), ("uint16", "uint16"), ("int32", "int32")],
)
def test_roundtrip(file_store, dtype, stored_dtype):
    codec = PhotonCodec()
    movie = _movie(dtype)
    stored = codec.encode(movie, key={"id": 1}, context=_context(), store_name=file_store)

    assert "/s/t/id=1/movie" in f"/{stored['path']}"
    assert stored["store"] == file_store
    assert stored["shape"] == list(movie.shape)
    assert stored["dtype"] == stored_dtype

    z = codec.decode(stored, context={"config": dj.config})
    assert isinstance(z, zarr.Array)
    assert z.shape == movie.shape
    assert z.dtype == stored_dtype
    assert z.attrs["codec_name"] == "photon"
    assert [f.to_dict()["name"] for f in z.filters] == ["anscombe-v1"]
    assert z[:].shape == movie.shape


@ANSCOMBE_INVERSE_BUG
def test_roundtrip_values(file_store):
    codec = PhotonCodec()
    movie = _movie()
    stored = codec.encode(movie, key={"id": 1}, context=_context(), store_name=file_store)
    _assert_close(codec.decode(stored, context={"config": dj.config})[:], movie)


def test_ignores_underscore_keys(file_store):
    """The path comes from `context`, not from the underscore keys DataJoint 2.3 adds to `key`."""
    key = {"id": 1, "_schema": "wrong", "_table": "wrong", "_field": "wrong"}
    stored = PhotonCodec().encode(_movie(), key=key, context=_context(), store_name=file_store)
    assert "wrong" not in stored["path"]
    assert "/s/t/id=1/movie" in f"/{stored['path']}"


@pytest.mark.parametrize(
    "context",
    [None, {"schema": "s", "table": "t", "field": "f"}],
    ids=["no context", "no config"],
)
def test_encode_needs_context(context):
    legacy_key = {"id": 1, "_schema": "s", "_table": "t", "_field": "f", "_config": dj.config}
    with pytest.raises(dj.DataJointError, match=r"DataJoint 2\.3\.4"):
        PhotonCodec().encode(_movie(), key=legacy_key, context=context, store_name="store")


def test_decode_needs_context():
    stored = {"path": "x.zarr", "store": None}
    with pytest.raises(dj.DataJointError, match=r"missing: config"):
        PhotonCodec().decode(stored, key={"_config": dj.config}, context=None)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([[[1]]], "numpy.ndarray"),
        (np.ones((2, 2, 2)), "integer"),
        (np.ones((2, 2), dtype="uint16"), "3D"),
        (-np.ones((2, 2, 2), dtype="int16"), "non-negative"),
        (np.full((2, 2, 2), 40000, dtype="uint16"), "up to 32767"),
    ],
    ids=["list", "float", "2D", "negative", "too large"],
)
def test_validate(value, message):
    with pytest.raises(dj.DataJointError, match=message):
        PhotonCodec().validate(value)


def test_insert_and_fetch(schema, file_store):
    """DataJoint passes the context on insert and fetch."""

    @schema
    class Recording(dj.Manual):
        definition = f"""
        recording_id : int32
        ---
        movie : <photon@{file_store}>
        """

    movie = _movie(shape=(120, 4, 4))
    Recording.insert1({"recording_id": 1, "movie": movie})
    fetched = (Recording & {"recording_id": 1}).fetch1("movie")
    assert isinstance(fetched, zarr.Array)
    assert fetched.shape == movie.shape
    assert fetched.dtype == movie.dtype
    assert fetched.chunks == (100, 4, 4)

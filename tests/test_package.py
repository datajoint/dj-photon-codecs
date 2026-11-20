from importlib.metadata import entry_points, version

import datajoint as dj

import dj_photon_codecs
from dj_photon_codecs import PhotonCodec


def test_version():
    assert version("dj-photon-codecs") == dj_photon_codecs.__version__


def test_entry_point():
    (ep,) = entry_points(group="datajoint.codecs", name="photon")
    assert ep.load() is PhotonCodec


def test_registered_with_datajoint():
    assert "photon" in dj.list_codecs()
    assert isinstance(dj.get_codec("photon"), PhotonCodec)

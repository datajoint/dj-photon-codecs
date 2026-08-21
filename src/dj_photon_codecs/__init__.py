"""DataJoint codec for photon-limited movies with Anscombe transformation."""

from .codecs import PhotonCodec

from ._version import version as __version__
__all__ = ["PhotonCodec", "__version__"]

"""DataJoint codec for photon-limited movies with Anscombe transformation."""

from ._version import version as __version__
from .codecs import PhotonCodec

__all__ = ["PhotonCodec", "__version__"]

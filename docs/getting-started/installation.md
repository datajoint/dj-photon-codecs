# Installation

## Requirements

- Python 3.10+
- DataJoint 2.0.0a22 or later
- NumPy
- Zarr
- anscombe-transform

## Install from PyPI

```bash
pip install dj-photon-codecs
```

This will automatically install all dependencies:

- `datajoint>=2.0.0a22`
- `numpy`
- `zarr`
- `anscombe-transform`

## Development Installation

For development or contributing, clone the repository and install in editable mode:

```bash
git clone https://github.com/datajoint/dj-photon-codecs.git
cd dj-photon-codecs
pip install -e ".[dev]"
```

The `[dev]` extra includes:

- `pytest` - Testing framework
- `ruff` - Linter and formatter
- `mkdocs-material` - Documentation builder

## Verify Installation

Check that the codec is registered:

```python
import datajoint as dj

# List registered codecs
print(dj.codecs)
# Should include 'photon' codec
```

## Next Steps

- [Quick Start](quick-start.md) - Get started with a simple example
- [Configuration](configuration.md) - Configure object storage

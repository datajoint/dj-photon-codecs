# dj-photon-codecs

DataJoint codec for photon-limited movies with Anscombe variance stabilization and compressed Zarr storage.

[![PyPI version](https://badge.fury.io/py/dj-photon-codecs.svg)](https://pypi.org/project/dj-photon-codecs/)
[![Documentation](https://readthedocs.org/projects/dj-photon-codecs/badge/?version=latest)](https://dj-photon-codecs.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

This codec enables efficient storage of photon-limited imaging data (calcium imaging, fluorescence microscopy) by:

1. **Variance stabilization** - Anscombe transformation converts Poisson noise to constant variance
2. **High compression** - Blosc/Zstd achieves 3-5x compression on stabilized data
3. **Efficient access** - Zarr format with temporal chunking for frame-by-frame processing

## Quick Start

### Installation

```bash
pip install dj-photon-codecs
```

### Basic Usage

```python
import datajoint as dj
import numpy as np

# Configure object storage
dj.config['stores'] = {
    'imaging': {
        'protocol': 's3',
        'bucket': 'my-data',
    }
}

# Define table
schema = dj.Schema('calcium_imaging')

@schema
class Recording(dj.Manual):
    definition = """
    recording_id : uint16
    ---
    movie : <photon@imaging>  # Photon-limited movie
    """

# Insert raw photon counts
movie = np.random.poisson(lam=10, size=(1000, 512, 512))
Recording.insert1({'recording_id': 1, 'movie': movie})

# Fetch returns Zarr array (Anscombe-transformed)
zarr_array = (Recording & {'recording_id': 1}).fetch1('movie')
frame = zarr_array[100]  # Efficient frame access
```

### Apply Inverse Transform

```python
from anscombe import generalized_inverse_anscombe

# Recover original photon counts
original = generalized_inverse_anscombe(zarr_array[:])
```

## Features

- **Automatic variance stabilization** using Anscombe transformation
- **3-5x compression** with Blosc/Zstd on variance-stabilized data
- **Temporal chunking** optimized for sequential frame access
- **Schema-addressed paths** mirroring database structure
- **Lazy loading** - access frames without loading entire movie
- **Invertible transformation** - mathematically lossless

## When to Use

✅ **Use for:**
- Photon-limited imaging (calcium imaging, fluorescence microscopy)
- Data where Poisson shot noise dominates
- Large movies requiring efficient storage
- Sequential frame processing workflows

❌ **Don't use for:**
- Preprocessed/normalized data (ΔF/F, z-scored)
- Data with negative values
- Non-Poisson noise dominates

## Documentation

📚 **[Full Documentation](https://dj-photon-codecs.readthedocs.io/)**

- [Installation Guide](https://dj-photon-codecs.readthedocs.io/en/latest/getting-started/installation/)
- [Quick Start Tutorial](https://dj-photon-codecs.readthedocs.io/en/latest/getting-started/quick-start/)
- [User Guide](https://dj-photon-codecs.readthedocs.io/en/latest/user-guide/overview/)
- [API Reference](https://dj-photon-codecs.readthedocs.io/en/latest/api/reference/)
- [Examples](https://dj-photon-codecs.readthedocs.io/en/latest/examples/calcium-imaging/)

## Contributing

Contributions are welcome! See our [Contributing Guide](https://dj-photon-codecs.readthedocs.io/en/latest/contributing/).

```bash
# Development setup
git clone https://github.com/datajoint/dj-photon-codecs.git
cd dj-photon-codecs
pip install -e ".[dev]"

# Run tests
pytest

# Build docs
mkdocs serve
```

## Support

- 📖 [Documentation](https://dj-photon-codecs.readthedocs.io/)
- 💬 [GitHub Discussions](https://github.com/datajoint/dj-photon-codecs/discussions) - Questions and community
- 🐛 [GitHub Issues](https://github.com/datajoint/dj-photon-codecs/issues) - Bug reports and feature requests

## Related Projects

- [DataJoint](https://datajoint.com) - Scientific data pipeline framework
- [anscombe-transform](https://github.com/datajoint/anscombe-transform) - Variance stabilization library
- [dj-zarr-codecs](https://github.com/datajoint/dj-zarr-codecs) - General Zarr array codec
- [Zarr](https://zarr.dev/) - Chunked, compressed array storage

## License

MIT License. Copyright (c) 2026 DataJoint Inc.

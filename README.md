# dj-photon-codecs

DataJoint codec for photon-limited movies with Anscombe variance stabilization and compressed Zarr storage.

[![PyPI version](https://badge.fury.io/py/dj-photon-codecs.svg)](https://pypi.org/project/dj-photon-codecs/)
[![Documentation](https://readthedocs.org/projects/dj-photon-codecs/badge/?version=latest)](https://dj-photon-codecs.readthedocs.io/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

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
    recording_id : int32
    ---
    movie : <photon@imaging>  # Photon-limited movie
    """

# Insert raw photon counts (non-negative integers up to 32767)
movie = np.random.poisson(lam=10, size=(1000, 512, 512)).astype(np.uint16)
Recording.insert1({'recording_id': 1, 'movie': movie})

# Fetch returns a read-only Zarr array; reading it applies the inverse transform
zarr_array = (Recording & {'recording_id': 1}).fetch1('movie')
frame = zarr_array[100]  # photon counts of one frame
```

The movie is stored as a Zarr array whose chunks pass through the
[anscombe-transform](https://github.com/datajoint/anscombe-transform) filter
before Blosc/Zstd compression. The filter re-quantizes the counts with a step
below the photon shot noise, so the fetched counts match the inserted ones
within that step.

Requires `datajoint>=2.3.4` and Python 3.11 or later.

## Features

- **Automatic variance stabilization** using Anscombe transformation
- **3-5x compression** with Blosc/Zstd on variance-stabilized data
- **Temporal chunking** optimized for sequential frame access
- **Schema-addressed paths** mirroring database structure
- **Lazy loading** - access frames without loading entire movie
- **Transparent inverse** - fetched arrays read back as photon counts

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
uv sync

# Run tests (the database test needs Docker and skips without it)
uv run pytest

# Build docs
uv run --group docs mkdocs serve
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

Apache License 2.0. Copyright (c) 2026 DataJoint Inc.

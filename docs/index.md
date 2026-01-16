# dj-photon-codecs

DataJoint codec for photon-limited movies with Anscombe variance stabilization and compressed Zarr storage.

## Overview

This package provides a DataJoint codec for storing photon-limited imaging data (calcium imaging, low-light microscopy) with automatic variance stabilization and compression.

**Why this codec:**

- **Photon-limited data** has Poisson noise (variance = mean)
- **Anscombe transform** converts to approximately Gaussian noise with constant variance
- **Variance stabilization enables better compression** - constant variance is more compressible
- **Zarr + Blosc compression** achieves high compression ratios on stabilized data
- **Movie-optimized chunking** for efficient temporal access

## Features

- **Variance stabilization**: Anscombe transformation for Poisson noise
- **High compression**: Blosc/Zstd compression on variance-stabilized data
- **Efficient storage**: Zarr format with temporal chunking
- **Schema-addressed paths**: Organized storage mirroring database structure
- **Lazy loading**: Access frames without loading entire movie
- **Automatic registration**: Codec available immediately after installation
- **Invertible**: Transform parameters stored for recovery of original data

## Quick Example

```python
import datajoint as dj
import numpy as np

schema = dj.Schema('calcium_imaging')

@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    movie : <photon@>  # Photon-limited movie
    """

# Insert raw photon counts
movie = np.random.poisson(lam=10, size=(1000, 512, 512))
Recording.insert1({'recording_id': 1, 'movie': movie})

# Fetch returns Zarr array (transformed data)
zarr_array = (Recording & {'recording_id': 1}).fetch1('movie')
frame = zarr_array[100]  # Efficient frame access
```

## Getting Started

- [Installation](getting-started/installation.md) - Install the package
- [Quick Start](getting-started/quick-start.md) - Step-by-step tutorial
- [Configuration](getting-started/configuration.md) - Configure object storage

## Learn More

- [User Guide](user-guide/overview.md) - Comprehensive guide to features
- [Examples](examples/calcium-imaging.md) - Real-world use cases
- [API Reference](api/reference.md) - Detailed API documentation

## Related Projects

- [DataJoint](https://datajoint.com) - Framework for scientific data pipelines
- [anscombe-transform](https://github.com/datajoint/anscombe-transform) - Anscombe variance stabilization
- [dj-zarr-codecs](https://github.com/datajoint/dj-zarr-codecs) - Zarr array storage codec
- [Zarr](https://zarr.dev/) - Chunked, compressed arrays

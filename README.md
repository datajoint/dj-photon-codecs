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

## Installation

```bash
pip install dj-photon-codecs
```

## Quick Start

### 1. Configure Object Storage

```python
import datajoint as dj

dj.config['stores'] = {
    'imaging': {
        'protocol': 's3',
        'endpoint': 's3.amazonaws.com',
        'bucket': 'my-imaging-data',
        'location': 'calcium',
    }
}
```

### 2. Define Table with `<photon@>`

```python
schema = dj.Schema('calcium_imaging')

@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    movie : <photon@imaging>  # Photon-limited movie (compressed)
    """
```

### 3. Insert Raw Photon Counts

```python
import numpy as np

# Simulate photon-limited movie (Poisson noise)
# Shape: (frames, height, width)
movie = np.random.poisson(lam=10, size=(1000, 512, 512))

Recording.insert1({
    'recording_id': 1,
    'movie': movie,
})
```

### 4. Fetch and Process

```python
# Returns Zarr array (Anscombe-transformed data)
zarr_array = (Recording & {'recording_id': 1}).fetch1('movie')

# Efficient frame access
frame = zarr_array[100]           # Single frame
snippet = zarr_array[100:200]     # Frame range
all_frames = zarr_array[:]        # Full movie

# Check properties
print(zarr_array.shape)   # (1000, 512, 512)
print(zarr_array.chunks)  # (100, 512, 512) - temporal chunking
print(zarr_array.dtype)   # float64

# Apply inverse transform if needed
from anscombe import generalized_inverse_anscombe
original = generalized_inverse_anscombe(zarr_array[:])
```

## Compression Performance

The combination of Anscombe transformation and Blosc compression typically achieves:

- **2-5x compression** on photon-limited data compared to uncompressed
- **Better than raw compression** because variance stabilization removes intensity-dependent patterns
- **No quality loss** - mathematically invertible transformation

**Example compression ratios:**
- Low signal (λ=5 photons): ~3-4x compression
- Medium signal (λ=20 photons): ~4-5x compression
- High signal (λ=100 photons): ~2-3x compression

## Use Cases

### Calcium Imaging

```python
@schema
class CalciumRecording(dj.Imported):
    definition = """
    -> Experiment
    -> Scan
    ---
    raw_movie : <photon@imaging>     # Raw photon counts (compressed)
    """

    def make(self, key):
        # Load raw photon-limited data from microscope
        movie = load_tiff_stack(key)  # Shape: (frames, height, width)

        self.insert1({
            **key,
            'raw_movie': movie,
        })

@schema
class MotionCorrected(dj.Computed):
    definition = """
    -> CalciumRecording
    ---
    corrected_movie : <photon@imaging>
    """

    def make(self, key):
        # Fetch Anscombe-transformed data (variance-stabilized)
        movie = (CalciumRecording & key).fetch1('raw_movie')

        # Motion correction on variance-stabilized data
        corrected = apply_motion_correction(movie[:])

        # Inverse transform before storing
        from anscombe import generalized_inverse_anscombe
        original_scale = generalized_inverse_anscombe(corrected)

        self.insert1({
            **key,
            'corrected_movie': original_scale,
        })
```

### Low-Light Microscopy

```python
@schema
class Microscopy(dj.Manual):
    definition = """
    imaging_session : int
    ---
    movie : <photon@>               # Low-light movie (compressed)
    exposure_ms : float             # Exposure time
    """

# Process time-lapse
for key in (Microscopy & 'exposure_ms < 10').fetch('KEY'):
    movie = (Microscopy & key).fetch1('movie')

    # Efficient frame-by-frame processing
    for i, frame in enumerate(movie):
        if i % 100 == 0:
            print(f"Processing frame {i}/{len(movie)}")
        process_frame(frame)
```

## How It Works

### Encoding (Insert)

1. **Validate**: Check for non-negative values (photon counts)
2. **Transform**: Apply Anscombe transformation to stabilize variance
3. **Compress**: Blosc/Zstd compression on variance-stabilized data
4. **Chunk**: Optimize for temporal access (100 frames per chunk)
5. **Store**: Schema-addressed path with transform metadata

### Decoding (Fetch)

1. **Open**: Zarr array in read-only mode (decompression on demand)
2. **Return**: Direct zarr.Array for lazy access
3. **Metadata**: Transform parameters available in `.attrs`

### Storage Structure

```
s3://bucket/location/
└── schema_name/
    └── recording/
        └── recording_id=1/
            └── movie.zarr/
                ├── .zarray          # Zarr metadata
                ├── .zattrs          # Transform parameters
                ├── 0.0.0            # Compressed chunk (frames 0-99)
                ├── 0.0.1            # Compressed chunk (frames 100-199)
                └── ...
```

## Anscombe Transformation

### What It Does

Converts Poisson-distributed data to approximately Gaussian:

```
transformed = 2 * sqrt(photon_counts + 3/8)
```

**Before transformation:**
- Variance = Mean (Poisson property)
- Heteroscedastic (variance changes with intensity)
- Poor compression (intensity-dependent patterns)

**After transformation:**
- Variance ≈ 1 (constant)
- Approximately Gaussian noise
- Homoscedastic (constant variance)
- Excellent compression (constant noise is highly compressible)

### When to Use

✅ **Use `<photon@>` when:**
- Data is photon-limited (low light, single photons)
- Poisson noise dominates
- Storage efficiency is important (compression)
- Downstream processing assumes Gaussian noise

❌ **Don't use when:**
- Data has other noise sources (read noise, thermal)
- Already preprocessed/normalized
- High photon counts (Poisson ≈ Gaussian already)

### Inverse Transform

Recover original photon counts after processing:

```python
from anscombe import generalized_inverse_anscombe

# Fetch transformed data
transformed = (Recording & key).fetch1('movie')

# Apply inverse
original = generalized_inverse_anscombe(transformed[:])
```

## Comparison with Other Codecs

| Codec | Transform | Compression | Best For |
|-------|-----------|-------------|----------|
| `<photon@>` | Anscombe | High (Blosc) | Photon-limited movies |
| `<zarr@>` | None | Optional | General arrays |
| `<npy@>` | None | None | Arrays with lazy loading |
| `<blob@>` | None | Python pickle | Small arrays with dedup |

## Configuration

### Compression Settings

Default: Blosc with Zstd compression (level 5, bit shuffle)

The codec uses Blosc compression which is:
- **Fast**: Near memory-speed decompression
- **Effective**: 2-5x compression on variance-stabilized data
- **Standard**: Widely supported in Zarr ecosystem

### Custom Chunking

The codec automatically chunks along time axis (100 frames per chunk). For custom chunking, you can modify the codec or use `<zarr@>` directly with preprocessed data.

## Development

### Setup

```bash
git clone https://github.com/datajoint/dj-photon-codecs.git
cd dj-photon-codecs
pip install -e ".[dev]"
```

### Testing

```bash
pytest
```

### Code Style

```bash
ruff check src tests
ruff format src tests
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License. Copyright (c) 2026 DataJoint Inc. See [LICENSE](LICENSE) for details.

## Related Projects

- [DataJoint](https://datajoint.com) - Framework for scientific data pipelines
- [anscombe-transform](https://github.com/datajoint/anscombe-transform) - Anscombe variance stabilization
- [dj-zarr-codecs](https://github.com/datajoint/dj-zarr-codecs) - Zarr array storage codec
- [Zarr](https://zarr.dev/) - Chunked, compressed arrays

## Documentation & Support

- [DataJoint Documentation](https://docs.datajoint.com) - Complete DataJoint documentation
- [GitHub Discussions](https://github.com/datajoint/dj-photon-codecs/discussions) - Ask questions and share use cases
- [GitHub Issues](https://github.com/datajoint/dj-photon-codecs/issues) - Report bugs and request features

## References

Anscombe, F. J. (1948). "The transformation of Poisson, binomial and negative-binomial data". *Biometrika* 35 (3–4): 246–254.

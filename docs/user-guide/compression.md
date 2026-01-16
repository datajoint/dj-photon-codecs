# Compression

The `<photon@>` codec achieves high compression through the combination of variance stabilization and Blosc compression.

## Compression Pipeline

1. **Anscombe transformation** - Stabilizes variance to constant ~1
2. **Blosc compression** - Zstd algorithm with bit shuffle
3. **Zarr chunking** - Temporal chunks for efficient access

## Blosc Configuration

The codec uses these Blosc settings:

```python
compressor = zarr.Blosc(
    cname='zstd',      # Zstandard compression
    clevel=5,          # Compression level (1-9)
    shuffle=zarr.Blosc.BITSHUFFLE  # Bit-level shuffling
)
```

### Why These Settings?

- **Zstd** - Fast decompression, good compression ratios
- **Level 5** - Balance between speed and compression
- **Bit shuffle** - Effective for floating-point data with similar magnitudes

## Compression Performance

### Typical Ratios

On photon-limited data after Anscombe transformation:

| Photon Count (λ) | Raw Size | Compressed Size | Ratio |
|------------------|----------|-----------------|-------|
| 5 photons/pixel  | 4 GB     | ~1 GB          | 3-4x  |
| 20 photons/pixel | 4 GB     | ~800 MB        | 4-5x  |
| 100 photons/pixel| 4 GB     | ~1.3 GB        | 2-3x  |

Example: 1000 frames × 512×512 pixels × 8 bytes (float64) = 2 GB raw

### Why Variance Stabilization Improves Compression

**Without transformation** (raw Poisson data):
- Variance = Mean (heteroscedastic)
- Low-intensity regions: small variance, highly compressible
- High-intensity regions: large variance, poorly compressible
- Overall compression: **1.5-2x**

**With Anscombe transformation**:
- Variance ≈ 1 everywhere (homoscedastic)
- All regions equally compressible
- Compression algorithms optimized for constant variance
- Overall compression: **3-5x**

The variance stabilization enables Blosc to achieve much better compression ratios.

## Compression vs. Accuracy

The Anscombe transformation is **mathematically invertible** - no information is lost:

```python
# Original data
original = np.random.poisson(lam=10, size=(1000, 512, 512))

# Encode (transform + compress)
transformed = generalized_anscombe(original, gain=1.0, offset=0.0, variance=0.0)

# Decode (decompress + inverse)
recovered = generalized_inverse_anscombe(transformed)

# Difference is due to floating-point rounding only
np.allclose(original, recovered, rtol=1e-10)  # True
```

The compression is **lossless** in the sense that the transformation itself is bijective.

## Chunking Strategy

### Temporal Chunking

The codec chunks along the time axis:

```python
chunk_time = min(100, n_frames)
chunks = (chunk_time, height, width)
```

**Benefits:**
- Sequential frame access is efficient (read one chunk at a time)
- Random frame access loads ~100 frames (reasonable overhead)
- Full spatial dimensions in each chunk (no spatial fragmentation)

### Example Storage

For a 1000-frame movie (512×512 pixels):

```
movie.zarr/
├── .zarray                    # Metadata
├── .zattrs                    # Transform parameters
├── 0.0.0                      # Frames 0-99 (compressed)
├── 1.0.0                      # Frames 100-199 (compressed)
├── 2.0.0                      # Frames 200-299 (compressed)
└── ...                        # 10 chunks total
```

Each chunk is compressed independently with Blosc.

## Decompression Performance

Blosc is optimized for speed:

- **Decompression**: Near memory bandwidth (~5 GB/s)
- **Multithreaded**: Parallel chunk decompression
- **Lazy loading**: Only decompress accessed chunks

Typical access times:

| Operation | Chunks Loaded | Time |
|-----------|--------------|------|
| Single frame | 1 chunk (~100 frames) | ~10-50 ms |
| Frame range (200 frames) | 2 chunks | ~20-100 ms |
| Full movie (1000 frames) | 10 chunks | ~100-500 ms |

Times depend on storage backend and network latency.

## Comparison: With vs. Without Anscombe

### Compression Ratio

```python
import numpy as np
import zarr

# Generate photon-limited data
movie = np.random.poisson(lam=10, size=(1000, 512, 512))

# Option 1: Raw data (no transformation)
zarr.save('raw.zarr', movie, compressor=zarr.Blosc(cname='zstd', clevel=5))

# Option 2: With Anscombe transformation
from anscombe import generalized_anscombe
transformed = generalized_anscombe(movie, gain=1.0, offset=0.0, variance=0.0)
zarr.save('transformed.zarr', transformed, compressor=zarr.Blosc(cname='zstd', clevel=5))

# Compare sizes
raw_size = get_directory_size('raw.zarr')
transformed_size = get_directory_size('transformed.zarr')

print(f"Raw compression: {movie.nbytes / raw_size:.1f}x")
print(f"With Anscombe: {movie.nbytes / transformed_size:.1f}x")
```

Expected output:
```
Raw compression: 1.8x
With Anscombe: 4.2x
```

The Anscombe transformation typically provides **2-3x additional compression** beyond raw Blosc.

## Trade-offs

| Aspect | `<photon@>` | `<zarr@>` |
|--------|-------------|-----------|
| Compression | High (3-5x) | Medium (1-2x) |
| Transform overhead | Small (~10ms/GB) | None |
| Data format | Transformed (requires inverse) | Original scale |
| Best for | Photon-limited (Poisson) | General arrays |

## Custom Compression Settings

The codec uses fixed Blosc settings. For custom compression:

1. Preprocess with Anscombe transformation
2. Store with `<zarr@>` codec and custom settings
3. Document transform parameters

Future codec versions may support custom compressor settings.

## Next Steps

- [Storage Structure](storage-structure.md) - File organization
- [Best Practices](best-practices.md) - Optimization tips

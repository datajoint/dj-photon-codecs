# Overview

The `<photon@>` codec is designed for photon-limited imaging data where Poisson noise dominates. It combines variance stabilization (Anscombe transformation) with efficient compression (Zarr + Blosc) to achieve optimal storage and processing.

## What is Photon-Limited Data?

Photon-limited data occurs when:

- Few photons are detected per pixel (low light)
- Signal-to-noise ratio is limited by photon counting statistics
- Noise follows Poisson distribution (variance = mean)

Common examples:

- **Calcium imaging** - Fluorescence signals from neural activity
- **Low-light microscopy** - Single-molecule imaging, TIRF, etc.
- **Astronomy** - Deep-sky imaging with long exposures
- **Single-photon imaging** - SPAD arrays, photon counting

## Why Anscombe Transformation?

Poisson noise creates heteroscedasticity - variance depends on signal intensity:

```
Variance = Mean  (Poisson property)
```

This causes problems:

- Compression algorithms assume constant variance
- Many image processing algorithms assume Gaussian noise
- Statistical tests require homoscedastic data

The Anscombe transformation converts Poisson data to approximately Gaussian with constant variance:

```
transformed = 2 * sqrt(photon_counts + 3/8)
```

After transformation:

```
Variance ≈ 1  (constant)
```

This enables:

- **Better compression** - Constant variance is highly compressible
- **Standard image processing** - Algorithms designed for Gaussian noise work better
- **Valid statistics** - Homoscedastic assumptions hold

## Codec Pipeline

### Encoding (Insert)

1. **Validate** - Check data is non-negative (photon counts)
2. **Transform** - Apply Anscombe transformation
3. **Chunk** - Organize into 100-frame temporal chunks
4. **Compress** - Blosc/Zstd compression (level 5, bit shuffle)
5. **Store** - Write Zarr format to object storage
6. **Metadata** - Save transform parameters and version info

### Decoding (Fetch)

1. **Open** - Connect to Zarr array (read-only)
2. **Validate** - Check codec version compatibility
3. **Return** - Zarr array for lazy access (no full load)

Data remains Anscombe-transformed - apply inverse if original scale is needed.

## Compression Performance

Typical compression ratios on photon-limited data:

| Photon Count (λ) | Variance | Compression Ratio |
|------------------|----------|-------------------|
| 5 photons/pixel  | High     | 3-4x              |
| 20 photons/pixel | Medium   | 4-5x              |
| 100 photons/pixel| Low      | 2-3x              |

The transformation works best at low-to-medium photon counts where Poisson noise dominates.

## When to Use

✅ **Use `<photon@>` when:**

- Data is photon-limited (few photons per detection)
- Poisson noise is the dominant noise source
- Storage efficiency matters (large movies)
- Processing assumes Gaussian noise
- Data will be accessed frame-by-frame

❌ **Don't use when:**

- Other noise sources dominate (read noise, thermal)
- Data is already preprocessed/normalized
- Very high photon counts (Poisson ≈ Gaussian already)
- Need frequent random access to small regions

## Comparison with Other Codecs

| Codec | Transform | Compression | Access Pattern | Best For |
|-------|-----------|-------------|----------------|----------|
| `<photon@>` | Anscombe | High (Blosc) | Sequential frames | Photon-limited movies |
| `<zarr@>` | None | Optional | Flexible chunks | General arrays |
| `<npy@>` | None | None | Full array | Medium arrays, lazy load |
| `<blob@>` | None | Pickle + dedup | Full load | Small arrays with dedup |

## Next Steps

- [Anscombe Transform](anscombe-transform.md) - Mathematical details
- [Compression](compression.md) - Compression settings and performance
- [Storage Structure](storage-structure.md) - File organization
- [Best Practices](best-practices.md) - Usage recommendations

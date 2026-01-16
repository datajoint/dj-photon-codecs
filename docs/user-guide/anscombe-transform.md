# Anscombe Transformation

The Anscombe transformation is a variance-stabilizing transformation for Poisson-distributed data.

## Mathematical Definition

### Generalized Anscombe Transform

$$
f(x) = 2\sqrt{x + \frac{3}{8}}
$$

Where $x$ is the observed photon count.

### Parameters

The codec uses the **generalized** Anscombe transformation with fixed parameters:

- **gain** = 1.0 (no gain correction)
- **offset** = 0.0 (no offset correction)
- **variance** = 0.0 (pure Poisson noise)

This assumes raw photon counts without camera-specific corrections.

## Why It Works

### Poisson Distribution Properties

For photon counts following Poisson distribution:

$$
\text{Variance} = \text{Mean} = \lambda
$$

This heteroscedasticity (variance depends on mean) causes problems for:

- Compression algorithms (assume constant variance)
- Image processing (Gaussian noise assumptions)
- Statistical inference (homoscedasticity requirements)

### Variance Stabilization

After Anscombe transformation:

$$
\text{Variance} \approx 1 \quad \text{(constant)}
$$

The transformed data is approximately:

$$
f(x) \sim \mathcal{N}(2\sqrt{\lambda + \frac{3}{8}}, 1)
$$

Normal distribution with constant unit variance, independent of $\lambda$.

## Inverse Transformation

### Exact Inverse

The exact algebraic inverse is:

$$
x = \left(\frac{f(x)}{2}\right)^2 - \frac{3}{8}
$$

### Generalized Inverse Anscombe

For better accuracy, use the generalized inverse from the `anscombe-transform` library:

```python
from anscombe import generalized_inverse_anscombe

original = generalized_inverse_anscombe(transformed_data)
```

This accounts for:

- Bias correction at low photon counts
- Improved accuracy for $\lambda < 10$
- Asymptotic unbiasedness

## When Anscombe Works Best

### Optimal Range

The transformation is most beneficial for:

- **λ ∈ [5, 100]** photons per pixel - where variance stabilization has strongest compression benefit
- Pure Poisson noise (photon-limited regime)
- Data where Poisson noise is dominant noise source

### Performance by Photon Count

| λ (photons) | Variance After Transform | Approximation Quality |
|-------------|-------------------------|----------------------|
| 1           | ~0.9                    | Fair                 |
| 5           | ~0.95                   | Good                 |
| 20          | ~0.98                   | Excellent            |
| 100         | ~0.99                   | Excellent            |
| 1000        | ~1.00                   | Perfect              |

### Limitations

❌ **Anscombe is not appropriate when:**

- **Read noise dominates** - Use generalized Anscombe with variance parameter
- **Very low counts** (λ < 1) - Transformation bias becomes significant
- **Already normalized data** - Transformation assumes raw counts
- **Non-Poisson noise** - Thermal, quantization, or other noise sources dominate

## Example: Variance Stabilization

```python
import numpy as np
import matplotlib.pyplot as plt
from anscombe import generalized_anscombe, generalized_inverse_anscombe

# Generate photon-limited data with varying intensity
intensities = [5, 10, 20, 50, 100]
n_pixels = 10000

fig, axes = plt.subplots(2, len(intensities), figsize=(15, 6))

for i, lam in enumerate(intensities):
    # Generate Poisson data
    data = np.random.poisson(lam, n_pixels)

    # Apply transformation
    transformed = generalized_anscombe(data, gain=1.0, offset=0.0, variance=0.0)

    # Plot original
    axes[0, i].hist(data, bins=50, alpha=0.7)
    axes[0, i].set_title(f'λ={lam}\nVar={np.var(data):.1f}')

    # Plot transformed
    axes[1, i].hist(transformed, bins=50, alpha=0.7, color='orange')
    axes[1, i].set_title(f'Transformed\nVar={np.var(transformed):.2f}')

axes[0, 0].set_ylabel('Raw Counts')
axes[1, 0].set_ylabel('Transformed')
plt.tight_layout()
plt.show()
```

All transformed distributions have variance ≈ 1, regardless of original intensity.

## Implementation Details

### Codec Parameters

The PhotonCodec uses fixed parameters:

```python
transformed = generalized_anscombe(value, gain=1.0, offset=0.0, variance=0.0)
```

These are stored in Zarr attributes:

```python
zarr_array.attrs['anscombe_gain']      # 1.0
zarr_array.attrs['anscombe_offset']    # 0.0
zarr_array.attrs['anscombe_variance']  # 0.0
```

### Future Extensions

For cameras with gain and read noise, future versions could support:

```python
# Camera with gain=0.5 electrons/ADU, read noise σ²=4
movie : <photon@store:gain=0.5,variance=4>
```

This would require codec API extensions.

## References

Anscombe, F. J. (1948). "The transformation of Poisson, binomial and negative-binomial data". *Biometrika* 35 (3–4): 246–254.

## Next Steps

- [Compression](compression.md) - How compression benefits from variance stabilization
- [Best Practices](best-practices.md) - When to use Anscombe transformation

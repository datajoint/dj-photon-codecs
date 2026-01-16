# API Reference

Complete reference for the `dj-photon-codecs` package.

## PhotonCodec

::: dj_photon_codecs.PhotonCodec
    options:
      show_root_heading: true
      show_source: true
      members:
        - name
        - CODEC_VERSION
        - validate
        - encode
        - decode

## Usage Syntax

### Table Definition

```python
@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    movie : <photon@store>  # Photon-limited movie
    """
```

### Syntax Components

- **`<photon@store>`** - Full syntax with named store
- **`<photon@>`** - Use default store
- **`<photon>`** - ERROR: Missing `@` (codec requires object storage)

The `@` symbol is **required** because the photon codec always stores data in object storage, never in the database directly.

## Codec Registration

The codec is automatically registered via entry points when the package is installed:

```toml
[project.entry-points."datajoint.codecs"]
photon = "dj_photon_codecs:PhotonCodec"
```

### Manual Registration (Advanced)

```python
import datajoint as dj
from dj_photon_codecs import PhotonCodec

# Register manually (usually not needed)
dj.codecs.register(PhotonCodec())

# Verify registration
assert 'photon' in dj.codecs
```

## Metadata Format

### Database Storage

When data is inserted, the following metadata is stored in the database:

```python
{
    "path": "schema/table/pk/field.zarr",
    "store": "store_name",
    "codec_version": "1.0",
    "shape": [1000, 512, 512],
    "dtype": "float64",
    "transform": "anscombe"
}
```

### Zarr Attributes

Additional metadata is stored in Zarr `.zattrs`:

```python
zarr_array.attrs = {
    "codec_version": "1.0",
    "codec_name": "photon",
    "anscombe_gain": 1.0,
    "anscombe_offset": 0.0,
    "anscombe_variance": 0.0,
    "original_dtype": "uint16"
}
```

## Validation

### Input Validation

The codec validates input data during insertion:

```python
def validate(self, value):
    """
    Validate photon-limited data.

    Checks:
    - Must be numpy.ndarray
    - No object dtype
    - At least 3 dimensions (time, height, width)
    - All values non-negative

    Raises
    ------
    DataJointError
        If validation fails
    """
```

### Error Messages

```python
# Not a numpy array
>>> Recording.insert1({'recording_id': 1, 'movie': [1, 2, 3]})
DataJointError: <photon> requires numpy.ndarray, got list

# Contains negative values
>>> Recording.insert1({'recording_id': 1, 'movie': np.array([-1, 0, 1])})
DataJointError: <photon> requires non-negative values (photon counts cannot be negative)

# Wrong dimensions
>>> Recording.insert1({'recording_id': 1, 'movie': np.array([[1, 2], [3, 4]])})
DataJointError: <photon> requires 3D+ arrays (time, height, width, ...), got 2D
```

## Type Annotations

```python
from typing import Any
import numpy as np
import zarr

class PhotonCodec:
    def validate(self, value: Any) -> None: ...

    def encode(
        self,
        value: np.ndarray,
        *,
        key: dict | None = None,
        store_name: str | None = None,
    ) -> dict: ...

    def decode(
        self,
        stored: dict,
        *,
        key: dict | None = None,
    ) -> zarr.Array: ...
```

## Return Types

### encode()

Returns metadata dictionary for database storage:

```python
{
    "path": str,              # Relative path in object store
    "store": str | None,      # Store name
    "codec_version": str,     # Format version
    "shape": list[int],       # Array shape
    "dtype": str,             # Data type
    "transform": str,         # "anscombe"
}
```

### decode()

Returns `zarr.Array` (read-only):

```python
>>> movie = (Recording & key).fetch1('movie')
>>> type(movie)
<class 'zarr.core.Array'>

>>> movie.shape
(1000, 512, 512)

>>> movie.dtype
dtype('float64')

>>> movie.chunks
(100, 512, 512)

>>> movie.attrs
{'codec_version': '1.0', 'anscombe_gain': 1.0, ...}
```

## Version Compatibility

### Codec Version

The codec includes a version field for backward compatibility:

```python
CODEC_VERSION = "1.0"
```

### Version Checking

During decode, the codec checks version compatibility:

```python
version = zarr_array.attrs.get('codec_version', stored.get('codec_version', '1.0'))

if version.startswith('1.'):
    return zarr_array  # All v1.x compatible
else:
    raise DataJointError(f"Unsupported photon codec version: {version}")
```

### Future Versions

If the codec format changes in the future (e.g., different transform parameters), the version will be incremented to `2.0`, and the decode method will handle both formats.

## Storage Paths

### Schema-Addressed Paths

The codec constructs paths based on database structure:

```python
path = f"{schema_name}/{table_name}/{primary_key}/{field_name}.zarr"
```

### Example Paths

```python
# Simple primary key
recording_id=42
→ calcium_imaging/recording/recording_id=42/movie.zarr

# Compound primary key
subject_id=10, session_date='2024-01-15'
→ calcium_imaging/session/subject_id=10/session_date=2024-01-15/movie.zarr

# With location prefix
store: {'location': 'movies'}
→ movies/calcium_imaging/recording/recording_id=42/movie.zarr
```

## Compression Configuration

### Blosc Compressor

```python
compressor = zarr.Blosc(
    cname='zstd',
    clevel=5,
    shuffle=zarr.Blosc.BITSHUFFLE
)
```

### Chunking Strategy

```python
chunk_time = min(100, n_frames)
chunks = (chunk_time, height, width)
```

## Error Handling

All codec errors are raised as `DataJointError`:

```python
from datajoint import DataJointError

try:
    Recording.insert1({'recording_id': 1, 'movie': invalid_data})
except DataJointError as e:
    print(f"Codec error: {e}")
```

## Related Functions

### Anscombe Transform

From the `anscombe-transform` package:

```python
from anscombe import (
    generalized_anscombe,
    generalized_inverse_anscombe
)

# Forward transform
transformed = generalized_anscombe(
    data,
    gain=1.0,
    offset=0.0,
    variance=0.0
)

# Inverse transform
original = generalized_inverse_anscombe(transformed)
```

## See Also

- [DataJoint Documentation](https://docs.datajoint.com) - DataJoint framework
- [Zarr Documentation](https://zarr.readthedocs.io/) - Zarr array format
- [anscombe-transform](https://github.com/datajoint/anscombe-transform) - Transform library

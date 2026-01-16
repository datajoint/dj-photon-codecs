# Quick Start

This tutorial will get you started with storing photon-limited movies using the `<photon@>` codec.

## Step 1: Configure Object Storage

First, configure an object store for your data:

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

For local filesystem storage (testing):

```python
dj.config['stores'] = {
    'local': {
        'protocol': 'file',
        'location': '/tmp/dj-storage',
    }
}
```

## Step 2: Define Table with `<photon@>`

Create a DataJoint table with a photon-limited movie field:

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

The `<photon@imaging>` syntax means:

- `photon` - Use Anscombe transformation + Zarr storage
- `@` - Store externally (not in database)
- `imaging` - Use the 'imaging' object store

## Step 3: Insert Raw Photon Counts

Insert raw photon count data (non-negative integers or floats):

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

!!! info "What happens during insert"
    1. Codec validates data is non-negative (photon counts)
    2. Applies Anscombe transformation to stabilize variance
    3. Compresses with Blosc/Zstd
    4. Stores in Zarr format with temporal chunking
    5. Saves transform parameters for inverse operation

## Step 4: Fetch and Process

Fetch returns a Zarr array containing the Anscombe-transformed data:

```python
# Returns Zarr array (Anscombe-transformed data)
zarr_array = (Recording & {'recording_id': 1}).fetch1('movie')

# Efficient frame access (lazy loading)
frame = zarr_array[100]           # Single frame
snippet = zarr_array[100:200]     # Frame range
all_frames = zarr_array[:]        # Full movie

# Check properties
print(zarr_array.shape)   # (1000, 512, 512)
print(zarr_array.chunks)  # (100, 512, 512) - temporal chunking
print(zarr_array.dtype)   # float64
```

## Step 5: Apply Inverse Transform (Optional)

To recover original photon counts after processing:

```python
from anscombe import generalized_inverse_anscombe

# Apply inverse transform
original = generalized_inverse_anscombe(zarr_array[:])
```

!!! tip "When to use inverse transform"
    - After processing transformed data
    - When you need original photon count scale
    - Before visualization (if original units matter)

## Complete Example

```python
import datajoint as dj
import numpy as np
from anscombe import generalized_inverse_anscombe

# Configure storage
dj.config['stores'] = {
    'local': {'protocol': 'file', 'location': '/tmp/dj-storage'}
}

# Define schema
schema = dj.Schema('calcium_imaging')

@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    movie : <photon@local>
    """

# Insert photon-limited movie
movie = np.random.poisson(lam=10, size=(1000, 512, 512))
Recording.insert1({'recording_id': 1, 'movie': movie})

# Fetch and process
zarr_array = (Recording & {'recording_id': 1}).fetch1('movie')

# Process frames efficiently
for i in range(0, len(zarr_array), 100):
    batch = zarr_array[i:i+100]
    # Process batch...

# Recover original if needed
original = generalized_inverse_anscombe(zarr_array[:])
```

## Next Steps

- [Configuration](configuration.md) - Configure storage backends
- [User Guide](../user-guide/overview.md) - Learn about features and best practices
- [Examples](../examples/calcium-imaging.md) - See real-world use cases

# Best Practices

Guidelines for optimal use of the `<photon@>` codec.

## When to Use This Codec

### ✅ Ideal Use Cases

**Photon-limited imaging data:**
- Calcium imaging (GCaMP, jRGECO, etc.)
- Two-photon microscopy
- Confocal microscopy
- Widefield fluorescence microscopy
- Most well-controlled microscopy modalities

**Data characteristics:**
- Poisson noise dominates other noise sources
- Raw photon counts or proportional values
- Large movies requiring efficient storage
- Sequential frame access patterns

### ❌ When Not to Use

**Other noise dominates:**
- High read noise relative to signal
- Thermal noise significant
- Quantization artifacts dominant

**Already preprocessed:**
- Normalized data (z-scored, ΔF/F)
- Background-subtracted with negative values
- Denoised or filtered data

**Data format issues:**
- Contains negative values (not photon counts)
- Non-numeric data types
- Less than 3 dimensions (need time × height × width)

## Data Preparation

### Raw Photon Counts

Best results with raw photon count data:

```python
# Good: Raw photon counts from detector
movie = load_raw_photon_counts()  # Non-negative integers

Recording.insert1({
    'recording_id': 1,
    'movie': movie,
})
```

### Camera Data

For camera data with gain and offset:

```python
# Remove camera offset first
movie_counts = (camera_data - offset) / gain

# Clip negative values (due to read noise)
movie_counts = np.maximum(movie_counts, 0)

Recording.insert1({
    'recording_id': 1,
    'movie': movie_counts,
})
```

### Do Not Use For

```python
# Bad: Normalized data (has negative values)
df_f = (fluorescence - baseline) / baseline
movie : <photon@>  # ❌ Will fail validation

# Bad: z-scored data
z_scored = (data - mean) / std
movie : <photon@>  # ❌ Will fail validation

# Use <zarr@> instead for preprocessed data
preprocessed_movie : <zarr@>  # ✅ Correct
```

## Processing Workflows

### Workflow 1: Store Raw, Process On-Demand

```python
@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    raw_movie : <photon@>  # Raw photon counts
    """

@schema
class MotionCorrected(dj.Computed):
    definition = """
    -> Recording
    ---
    corrected_movie : <photon@>
    """

    def make(self, key):
        # Fetch Anscombe-transformed data
        movie = (Recording & key).fetch1('raw_movie')

        # Process on variance-stabilized data
        corrected = motion_correction(movie[:])

        # Inverse transform before storing
        from anscombe import generalized_inverse_anscombe
        original_scale = generalized_inverse_anscombe(corrected)

        self.insert1({
            **key,
            'corrected_movie': original_scale,
        })
```

### Workflow 2: Store Multiple Representations

```python
@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    raw_movie : <photon@>           # Raw photon counts
    """

@schema
class Processed(dj.Computed):
    definition = """
    -> Recording
    ---
    motion_corrected : <photon@>    # Still photon counts
    df_over_f : <zarr@>             # Normalized (use zarr)
    """
```

## Performance Optimization

### Frame-by-Frame Processing

Leverage temporal chunking for efficient processing:

```python
# Good: Process chunks sequentially
movie = (Recording & key).fetch1('movie')

results = []
for i in range(0, len(movie), 100):
    chunk = movie[i:i+100]  # Reads one Zarr chunk
    results.append(process_chunk(chunk))
```

### Avoid Random Access

```python
# Bad: Random frame access (loads many chunks)
for i in [5, 157, 283, 691, 842]:
    frame = movie[i]  # Each may load different chunk

# Good: Sequential access
frames = movie[5:850]  # Load contiguous chunks once
for i in [5, 157, 283, 691, 842]:
    frame = frames[i - 5]
```

### Memory Management

```python
# Good: Process in batches
movie = (Recording & key).fetch1('movie')
n_frames = len(movie)

for batch_start in range(0, n_frames, 500):
    batch = movie[batch_start:batch_start+500]
    # Process batch
    del batch  # Free memory

# Bad: Load entire movie
all_frames = movie[:]  # May be GBs of data
```

## Data Validation

### Check Data Before Insert

```python
def validate_photon_data(movie):
    """Validate data is suitable for photon codec."""
    assert movie.ndim >= 3, "Need 3D+ array (time, height, width)"
    assert movie.dtype in [np.uint8, np.uint16, np.uint32, np.float32, np.float64], \
        "Must be numeric type"
    assert np.all(movie >= 0), "Photon counts must be non-negative"
    assert np.any(movie > 0), "Movie is all zeros"

# Use before insert
movie = load_data()
validate_photon_data(movie)
Recording.insert1({'recording_id': 1, 'movie': movie})
```

### Handle Edge Cases

```python
# Camera data may have small negative values due to read noise
camera_data = load_camera_data()

# Remove offset and clip negatives
photon_counts = np.maximum(camera_data - camera_offset, 0)

# Verify result
assert np.all(photon_counts >= 0)
```

## Storage Strategy

### Multiple Stores by Access Pattern

```python
dj.config['stores'] = {
    'active': {  # Frequently accessed
        'protocol': 's3',
        'bucket': 'imaging-active',
        'storage_class': 'STANDARD',
    },
    'archive': {  # Rarely accessed
        'protocol': 's3',
        'bucket': 'imaging-archive',
        'storage_class': 'GLACIER',
    },
}

@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    movie : <photon@active>  # Recent experiments
    """

@schema
class ArchivedRecording(dj.Manual):
    definition = """
    recording_id : int
    ---
    movie : <photon@archive>  # Old experiments
    """
```

### Lifecycle Management

```python
# Archive old recordings after 1 year
def archive_old_recordings():
    one_year_ago = datetime.now() - timedelta(days=365)

    for key in (Recording & f'recording_date < "{one_year_ago}"').fetch('KEY'):
        # Fetch and re-insert to archive store
        movie = (Recording & key).fetch1('movie')
        ArchivedRecording.insert1({**key, 'movie': movie[:]})

        # Delete from active storage
        (Recording & key).delete()
```

## Debugging

### Inspect Transform Parameters

```python
# Check Anscombe parameters used
movie = (Recording & key).fetch1('movie')

print(f"Codec: {movie.attrs['codec_name']}")
print(f"Version: {movie.attrs['codec_version']}")
print(f"Gain: {movie.attrs['anscombe_gain']}")
print(f"Offset: {movie.attrs['anscombe_offset']}")
print(f"Variance: {movie.attrs['anscombe_variance']}")
```

### Verify Compression

```python
import fsspec

# Get storage path from metadata
stored = (Recording & key).fetch1('movie', as_dict=True)
path = stored['path']
store_name = stored['store']

# Calculate compressed size
backend = dj.stores[store_name]
fs = backend.get_filesystem()
zarr_files = fs.glob(f"{path}/**")
total_size = sum(fs.size(f) for f in zarr_files)

print(f"Compressed size: {total_size / 1e9:.2f} GB")
print(f"Original size: {movie.nbytes / 1e9:.2f} GB")
print(f"Compression ratio: {movie.nbytes / total_size:.1f}x")
```

## Common Pitfalls

### Pitfall 1: Inserting Normalized Data

```python
# ❌ Wrong: Normalized data has negative values
df_f = (raw - baseline) / baseline
Recording.insert1({'recording_id': 1, 'movie': df_f})
# → DataJointError: photon requires non-negative values

# ✅ Correct: Use zarr for normalized data
@schema
class Normalized(dj.Computed):
    definition = """
    -> Recording
    ---
    df_over_f : <zarr@>  # Use zarr, not photon
    """
```

### Pitfall 2: Assuming Original Scale on Fetch

```python
# Data is Anscombe-transformed!
movie = (Recording & key).fetch1('movie')

# ❌ Wrong: Treating as original photon counts
mean_photons = np.mean(movie)  # This is in transformed space

# ✅ Correct: Apply inverse first
from anscombe import generalized_inverse_anscombe
original = generalized_inverse_anscombe(movie[:])
mean_photons = np.mean(original)
```

### Pitfall 3: Loading Entire Movie Unnecessarily

```python
# ❌ Wrong: Load all frames to compute one metric
movie = (Recording & key).fetch1('movie')
mean_per_frame = np.mean(movie[:], axis=(1, 2))  # Loads all

# ✅ Correct: Process chunk by chunk
movie = (Recording & key).fetch1('movie')
means = []
for i in range(0, len(movie), 100):
    chunk = movie[i:i+100]
    means.extend(np.mean(chunk, axis=(1, 2)))
```

## Next Steps

- [Examples](../examples/calcium-imaging.md) - See complete workflows
- [API Reference](../api/reference.md) - Detailed codec documentation

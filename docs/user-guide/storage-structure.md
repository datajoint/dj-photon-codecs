# Storage Structure

The `<photon@>` codec uses schema-addressed paths that mirror your database structure.

## Path Organization

### Schema-Addressed Paths

```
{store_root}/{location}/
└── {schema_name}/
    └── {table_name}/
        └── {primary_key}/
            └── {field_name}.zarr/
                ├── .zarray          # Zarr metadata
                ├── .zattrs          # Transform parameters
                ├── 0.0.0            # Compressed chunk
                ├── 1.0.0            # Compressed chunk
                └── ...
```

### Example

For this table definition:

```python
schema = dj.Schema('calcium_imaging')

@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    movie : <photon@imaging>
    """

Recording.insert1({'recording_id': 42, 'movie': movie_data})
```

Storage path:

```
s3://my-bucket/calcium/
└── calcium_imaging/
    └── recording/
        └── recording_id=42/
            └── movie.zarr/
                ├── .zarray
                ├── .zattrs
                └── 0.0.0, 1.0.0, ...
```

## Primary Key Encoding

### Simple Keys

Single primary key becomes directory name:

```python
recording_id=42  →  recording_id=42/
```

### Compound Keys

Multiple primary keys joined with `/`:

```python
subject_id=10, session_date='2024-01-15'
→  subject_id=10/session_date=2024-01-15/
```

### URL Encoding

Special characters are URL-encoded:

```python
filename='data/raw.tif'  →  filename=data%2Fraw.tif/
```

## Zarr Directory Structure

### `.zarray` - Array Metadata

JSON file describing array properties:

```json
{
    "chunks": [100, 512, 512],
    "compressor": {
        "id": "blosc",
        "cname": "zstd",
        "clevel": 5,
        "shuffle": 2
    },
    "dtype": "<f8",
    "fill_value": null,
    "filters": null,
    "order": "C",
    "shape": [1000, 512, 512],
    "zarr_format": 2
}
```

### `.zattrs` - Transform Parameters

JSON file with codec-specific metadata:

```json
{
    "codec_version": "1.0",
    "codec_name": "photon",
    "anscombe_gain": 1.0,
    "anscombe_offset": 0.0,
    "anscombe_variance": 0.0,
    "original_dtype": "uint16"
}
```

### Chunk Files

Compressed binary chunks named by index:

```
0.0.0  →  chunk[0, 0, 0]  (frames 0-99)
1.0.0  →  chunk[1, 0, 0]  (frames 100-199)
...
```

For 3D array with shape `(1000, 512, 512)` and chunks `(100, 512, 512)`:
- 10 chunks total (along time dimension only)
- Each chunk: ~20-40 MB compressed

## Storage Backends

### S3

```python
dj.config['stores'] = {
    'imaging': {
        'protocol': 's3',
        'endpoint': 's3.amazonaws.com',
        'bucket': 'my-imaging-data',
        'location': 'calcium',
    }
}
```

Path: `s3://my-imaging-data/calcium/calcium_imaging/recording/...`

### MinIO

```python
dj.config['stores'] = {
    'imaging': {
        'protocol': 's3',
        'endpoint': 'minio.example.com:9000',
        'bucket': 'imaging',
        'location': 'movies',
    }
}
```

Path: `s3://imaging/movies/calcium_imaging/recording/...`

### Google Cloud Storage

```python
dj.config['stores'] = {
    'imaging': {
        'protocol': 'gs',
        'bucket': 'my-imaging-bucket',
        'location': 'calcium',
    }
}
```

Path: `gs://my-imaging-bucket/calcium/calcium_imaging/recording/...`

### Local Filesystem

```python
dj.config['stores'] = {
    'local': {
        'protocol': 'file',
        'location': '/data/dj-storage',
    }
}
```

Path: `/data/dj-storage/calcium_imaging/recording/...`

## Garbage Collection

When you delete rows from DataJoint tables, the Zarr directories remain in storage (orphaned).

### Manual Cleanup

```python
import datajoint as dj

# Find and remove orphaned data
dj.gc.collect(schema_name='calcium_imaging')
```

This scans the database and removes storage paths that no longer have corresponding table entries.

### Automated Cleanup

Set up periodic garbage collection:

```python
# In your maintenance script
import schedule
import datajoint as dj

def cleanup():
    for schema_name in ['calcium_imaging', 'behavior', 'analysis']:
        dj.gc.collect(schema_name=schema_name)

schedule.every().week.do(cleanup)
```

## Storage Costs

### Cost Estimation

Example: 1000 movies × 1000 frames × 512×512 pixels

| Component | Size per Movie | Total (1000 movies) |
|-----------|----------------|---------------------|
| Raw data (uint16) | 500 MB | 500 GB |
| Anscombe + Blosc | 125 MB | 125 GB |
| **Storage savings** | **75%** | **375 GB saved** |

At $0.023/GB/month (S3 Standard):
- Raw: $11.50/month
- Compressed: $2.88/month
- **Savings: $8.62/month per 1000 movies**

### Storage Classes

Use S3 storage classes for different access patterns:

```python
dj.config['stores'] = {
    'hot': {  # Frequent access
        'protocol': 's3',
        'bucket': 'imaging',
        'location': 'active',
        'storage_class': 'STANDARD',  # $0.023/GB/month
    },
    'warm': {  # Occasional access
        'protocol': 's3',
        'bucket': 'imaging',
        'location': 'archive',
        'storage_class': 'STANDARD_IA',  # $0.0125/GB/month
    },
    'cold': {  # Rare access
        'protocol': 's3',
        'bucket': 'imaging',
        'location': 'deep-archive',
        'storage_class': 'GLACIER',  # $0.004/GB/month
    },
}
```

## Direct Access

You can access Zarr arrays directly without DataJoint:

```python
import zarr
import fsspec

# Connect to storage
fs = fsspec.filesystem(
    's3',
    endpoint_url='https://s3.amazonaws.com',
    key='YOUR_ACCESS_KEY',
    secret='YOUR_SECRET_KEY'
)

# Open Zarr array
store = fs.get_mapper('s3://bucket/location/schema/table/pk/field.zarr')
z = zarr.open(store, mode='r')

# Access data
frame = z[100]  # Frame 100
print(z.attrs)  # Transform parameters
```

This is useful for external tools or non-Python environments.

## Next Steps

- [Best Practices](best-practices.md) - Optimization and usage tips
- [Configuration](../getting-started/configuration.md) - Storage backend setup

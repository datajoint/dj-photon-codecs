# Configuration

## Object Store Configuration

The `<photon@>` codec requires an external object store. Configure stores in your DataJoint config:

### S3 (Amazon Web Services)

```python
import datajoint as dj

dj.config['stores'] = {
    'imaging': {
        'protocol': 's3',
        'endpoint': 's3.amazonaws.com',
        'bucket': 'my-imaging-data',
        'location': 'calcium',  # Prefix within bucket
        'access_key': 'YOUR_ACCESS_KEY',  # Or use AWS credentials
        'secret_key': 'YOUR_SECRET_KEY',
    }
}
```

### MinIO (S3-compatible)

```python
dj.config['stores'] = {
    'imaging': {
        'protocol': 's3',
        'endpoint': 'minio.example.com:9000',
        'bucket': 'imaging-data',
        'location': 'photon-movies',
        'access_key': 'minio_access_key',
        'secret_key': 'minio_secret_key',
        'secure': True,  # Use HTTPS
    }
}
```

### Google Cloud Storage

```python
dj.config['stores'] = {
    'imaging': {
        'protocol': 'gs',
        'bucket': 'my-imaging-bucket',
        'location': 'calcium',
        'project': 'my-gcp-project',
    }
}
```

### Local Filesystem (Development/Testing)

```python
dj.config['stores'] = {
    'local': {
        'protocol': 'file',
        'location': '/data/dj-storage',
    }
}
```

!!! warning "Local filesystem for development only"
    Local filesystem storage is useful for testing but not recommended for production. Use cloud storage for scalability and durability.

## Multiple Stores

You can configure multiple stores for different purposes:

```python
dj.config['stores'] = {
    'raw': {  # Raw data
        'protocol': 's3',
        'bucket': 'imaging-raw',
        'location': 'movies',
    },
    'processed': {  # Processed data
        'protocol': 's3',
        'bucket': 'imaging-processed',
        'location': 'movies',
    },
    'archive': {  # Long-term archive
        'protocol': 's3',
        'bucket': 'imaging-archive',
        'location': 'movies',
        'storage_class': 'GLACIER',  # S3 storage class
    },
}
```

Then use in table definitions:

```python
@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    raw_movie : <photon@raw>          # Raw photon counts
    corrected : <photon@processed>    # Motion corrected
    backup : <photon@archive>         # Long-term backup
    """
```

## Default Store

If no store is specified (`<photon@>` without store name), DataJoint uses the default store:

```python
dj.config['stores'] = {
    'default': {  # Special name 'default'
        'protocol': 's3',
        'bucket': 'my-bucket',
    }
}

# This uses 'default' store
@schema
class Recording(dj.Manual):
    definition = """
    recording_id : int
    ---
    movie : <photon@>  # Uses 'default' store
    """
```

## Persistent Configuration

Save configuration to a file for reuse:

```python
# Save to dj_local_conf.json
dj.config.save('/path/to/dj_local_conf.json')

# Load in future sessions
dj.config.load('/path/to/dj_local_conf.json')
```

Or use environment variable:

```bash
export DJ_STORES='{
  "imaging": {
    "protocol": "s3",
    "bucket": "my-bucket"
  }
}'
```

## Storage Structure

The codec uses schema-addressed paths within the store:

```
{store_root}/{location}/
└── {schema_name}/
    └── {table_name}/
        └── {primary_key}/
            └── {field_name}.zarr/
                ├── .zarray          # Zarr metadata
                ├── .zattrs          # Transform parameters
                └── chunks/          # Compressed chunks
```

Example path:

```
s3://my-imaging-data/calcium/
└── calcium_imaging/
    └── recording/
        └── recording_id=1/
            └── movie.zarr/
```

## Next Steps

- [Quick Start](quick-start.md) - Get started with a simple example
- [Storage Structure](../user-guide/storage-structure.md) - Learn about storage organization

# Calcium Imaging Pipeline

Complete example of a calcium imaging data pipeline using `<photon@>`.

## Overview

This example demonstrates:

- Storing raw calcium imaging movies
- Motion correction on variance-stabilized data
- ROI extraction and trace analysis
- Multiple storage tiers (active/archive)

## Schema Definition

```python
import datajoint as dj
import numpy as np
from anscombe import generalized_anscombe, generalized_inverse_anscombe

# Configure storage
dj.config['stores'] = {
    'imaging': {
        'protocol': 's3',
        'bucket': 'calcium-imaging',
        'location': 'movies',
    }
}

schema = dj.Schema('calcium_imaging')

@schema
class Mouse(dj.Manual):
    definition = """
    mouse_id : int
    ---
    strain : varchar(32)
    sex : enum('M', 'F')
    """

@schema
class Session(dj.Manual):
    definition = """
    -> Mouse
    session_date : date
    ---
    experimenter : varchar(64)
    notes : varchar(1000)
    """

@schema
class Recording(dj.Imported):
    definition = """
    -> Session
    recording_num : int
    ---
    raw_movie : <photon@imaging>    # Raw photon counts
    frame_rate : float              # Hz
    width : int                     # pixels
    height : int                    # pixels
    n_frames : int
    """

    def make(self, key):
        # Load raw TIFF stack from microscope
        tiff_path = get_recording_path(key)
        raw_movie = load_tiff_stack(tiff_path)

        # Validate data
        assert raw_movie.ndim == 3, "Expected (time, height, width)"
        assert np.all(raw_movie >= 0), "Raw data must be non-negative"

        self.insert1({
            **key,
            'raw_movie': raw_movie,
            'frame_rate': 30.0,
            'width': raw_movie.shape[2],
            'height': raw_movie.shape[1],
            'n_frames': raw_movie.shape[0],
        })
```

## Motion Correction

Process on variance-stabilized data:

```python
@schema
class MotionCorrected(dj.Computed):
    definition = """
    -> Recording
    ---
    corrected_movie : <photon@imaging>
    shift_x : longblob              # X shifts per frame
    shift_y : longblob              # Y shifts per frame
    """

    def make(self, key):
        # Fetch Anscombe-transformed movie
        movie = (Recording & key).fetch1('raw_movie')

        # Motion correction on variance-stabilized data
        # (Many algorithms assume Gaussian noise)
        corrected, shifts = self.motion_correct(movie[:])

        # Apply inverse Anscombe before storing
        corrected_counts = generalized_inverse_anscombe(corrected)

        self.insert1({
            **key,
            'corrected_movie': corrected_counts,
            'shift_x': shifts[:, 0],
            'shift_y': shifts[:, 1],
        })

    @staticmethod
    def motion_correct(movie):
        """Simple motion correction using phase correlation."""
        from scipy.ndimage import shift as apply_shift
        from skimage.registration import phase_cross_correlation

        reference = np.mean(movie[:100], axis=0)
        corrected = np.zeros_like(movie)
        shifts = np.zeros((len(movie), 2))

        for i, frame in enumerate(movie):
            # Compute shift relative to reference
            shift_yx, _, _ = phase_cross_correlation(reference, frame)
            shifts[i] = shift_yx

            # Apply correction
            corrected[i] = apply_shift(frame, shift_yx)

        return corrected, shifts
```

## ROI Detection and Traces

Extract regions of interest and fluorescence traces:

```python
@schema
class ROI(dj.Computed):
    definition = """
    -> MotionCorrected
    ---
    n_rois : int
    roi_masks : <blob>              # Binary masks (n_rois, height, width)
    """

    def make(self, key):
        # Fetch corrected movie (Anscombe-transformed)
        movie = (MotionCorrected & key).fetch1('corrected_movie')

        # Detect ROIs on mean projection
        mean_image = np.mean(movie[:], axis=0)
        roi_masks = self.detect_rois(mean_image)

        self.insert1({
            **key,
            'n_rois': len(roi_masks),
            'roi_masks': roi_masks,
        })

    @staticmethod
    def detect_rois(mean_image):
        """Simple ROI detection by thresholding."""
        from skimage.measure import label, regionprops

        # Threshold and label connected components
        threshold = np.percentile(mean_image, 95)
        binary = mean_image > threshold
        labeled = label(binary)

        # Extract ROI masks
        roi_masks = []
        for region in regionprops(labeled):
            if 50 < region.area < 500:  # Size filter
                mask = labeled == region.label
                roi_masks.append(mask)

        return np.array(roi_masks)

@schema
class Trace(dj.Computed):
    definition = """
    -> ROI
    roi_id : int
    ---
    fluorescence : longblob         # Raw fluorescence trace
    """

    def make(self, key):
        # Fetch data
        movie = (MotionCorrected & key).fetch1('corrected_movie')
        roi_masks = (ROI & key).fetch1('roi_masks')

        # Extract traces for each ROI
        for roi_id, mask in enumerate(roi_masks):
            # Process movie in chunks to save memory
            trace = []
            for i in range(0, len(movie), 100):
                chunk = movie[i:i+100]

                # Apply inverse Anscombe for quantitative analysis
                chunk_counts = generalized_inverse_anscombe(chunk)

                # Mean fluorescence in ROI
                chunk_trace = np.mean(chunk_counts[:, mask], axis=1)
                trace.extend(chunk_trace)

            self.insert1({
                **key,
                'roi_id': roi_id,
                'fluorescence': np.array(trace),
            })
```

## Usage Example

```python
# Insert subject
Mouse.insert1({
    'mouse_id': 1,
    'strain': 'C57BL/6J',
    'sex': 'M',
})

# Insert session
Session.insert1({
    'mouse_id': 1,
    'session_date': '2024-01-15',
    'experimenter': 'Jane Doe',
    'notes': 'Baseline recording',
})

# Import recording (automatically processes TIFF)
Recording.populate({'mouse_id': 1, 'session_date': '2024-01-15'})

# Compute motion correction
MotionCorrected.populate()

# Detect ROIs and extract traces
ROI.populate()
Trace.populate()

# Analyze traces
traces = (Trace & {'mouse_id': 1, 'session_date': '2024-01-15'}).fetch('fluorescence')

import matplotlib.pyplot as plt
plt.figure(figsize=(12, 6))
for i, trace in enumerate(traces[:10]):  # First 10 ROIs
    plt.plot(trace + i * 500, label=f'ROI {i}')
plt.xlabel('Frame')
plt.ylabel('Fluorescence (AU)')
plt.legend()
plt.title('Calcium Traces')
plt.show()
```

## Storage Analysis

```python
# Compare storage efficiency
for key in Recording.fetch('KEY'):
    # Get original size
    movie = (Recording & key).fetch1('raw_movie')
    original_size = movie.nbytes

    # Get compressed size (from storage)
    stored = (Recording & key).fetch1('raw_movie', as_dict=True)
    # Calculate actual storage size...

    print(f"Recording {key}:")
    print(f"  Original: {original_size / 1e9:.2f} GB")
    print(f"  Compressed: {compressed_size / 1e9:.2f} GB")
    print(f"  Ratio: {original_size / compressed_size:.1f}x")
```

## Advanced: Multi-Plane Imaging

For volumetric calcium imaging:

```python
@schema
class VolumeRecording(dj.Imported):
    definition = """
    -> Session
    recording_num : int
    ---
    volume_movie : <photon@imaging>  # 4D: (time, z, height, width)
    n_planes : int
    plane_spacing : float            # μm
    """

    def make(self, key):
        # Load multi-plane data
        planes = [load_plane(key, z) for z in range(n_planes)]
        volume = np.stack(planes, axis=1)  # (time, z, height, width)

        self.insert1({
            **key,
            'volume_movie': volume,
            'n_planes': n_planes,
            'plane_spacing': 2.5,
        })
```

The codec handles 4D data with the same temporal chunking strategy.

## Next Steps

- [Low-Light Microscopy](low-light.md) - Single-molecule imaging example
- [Best Practices](../user-guide/best-practices.md) - Optimization tips

# Low-Light Microscopy

Example pipeline for single-molecule imaging and other low-light applications.

## Overview

This example demonstrates:

- Storing photon-limited single-molecule movies
- Particle localization on variance-stabilized data
- Tracking molecules across frames
- Temporal analysis of molecular dynamics

## Schema Definition

```python
import datajoint as dj
import numpy as np
from anscombe import generalized_anscombe, generalized_inverse_anscombe

dj.config['stores'] = {
    'microscopy': {
        'protocol': 's3',
        'bucket': 'single-molecule',
        'location': 'tirf',
    }
}

schema = dj.Schema('single_molecule')

@schema
class Sample(dj.Manual):
    definition = """
    sample_id : int
    ---
    construct : varchar(128)        # Labeled molecule
    concentration : float           # nM
    buffer : varchar(128)
    """

@schema
class Acquisition(dj.Manual):
    definition = """
    -> Sample
    acquisition_id : int
    ---
    movie : <photon@microscopy>     # Photon-limited TIRF movie
    exposure_ms : float             # Exposure time
    laser_power : float             # mW
    frame_rate : float              # Hz
    n_frames : int
    """

@schema
class LocalizedMolecules(dj.Computed):
    definition = """
    -> Acquisition
    ---
    n_molecules : int
    localizations : <blob>          # (n_molecules, 5): frame, x, y, intensity, sigma
    """

    def make(self, key):
        # Fetch variance-stabilized movie
        movie = (Acquisition & key).fetch1('movie')

        # Localize molecules on Anscombe-transformed data
        localizations = self.localize_molecules(movie[:])

        self.insert1({
            **key,
            'n_molecules': len(localizations),
            'localizations': localizations,
        })

    @staticmethod
    def localize_molecules(movie):
        """
        Localize single molecules using 2D Gaussian fitting.

        Operates on Anscombe-transformed data where variance is stabilized.
        """
        from scipy.optimize import curve_fit

        def gaussian_2d(xy, amplitude, x0, y0, sigma):
            """2D Gaussian function."""
            x, y = xy
            return amplitude * np.exp(-((x - x0)**2 + (y - y0)**2) / (2 * sigma**2))

        localizations = []

        for frame_idx, frame in enumerate(movie):
            # Detect peaks (local maxima)
            from scipy.ndimage import maximum_filter

            # Threshold for detection
            threshold = np.mean(frame) + 3 * np.std(frame)
            maxima = (frame == maximum_filter(frame, size=5)) & (frame > threshold)

            # Localize each peak
            peaks = np.argwhere(maxima)
            for y, x in peaks:
                # Extract local region (11x11 pixels)
                size = 5
                if (y < size or y >= frame.shape[0] - size or
                    x < size or x >= frame.shape[1] - size):
                    continue

                region = frame[y-size:y+size+1, x-size:x+size+1]
                yy, xx = np.mgrid[-size:size+1, -size:size+1]

                # Fit 2D Gaussian
                try:
                    popt, _ = curve_fit(
                        gaussian_2d,
                        (xx.ravel(), yy.ravel()),
                        region.ravel(),
                        p0=[region.max(), 0, 0, 1.5]
                    )
                    amplitude, dx, dy, sigma = popt

                    # Store localization
                    localizations.append([
                        frame_idx,          # Frame number
                        x + dx,             # X position (pixels)
                        y + dy,             # Y position (pixels)
                        amplitude,          # Amplitude
                        sigma,              # PSF width (pixels)
                    ])

                except RuntimeError:
                    continue  # Fit failed

        return np.array(localizations)
```

## Molecule Tracking

Track molecules across frames:

```python
@schema
class Track(dj.Computed):
    definition = """
    -> LocalizedMolecules
    track_id : int
    ---
    n_frames : int                  # Track length
    trajectory : <blob>             # (n_frames, 3): frame, x, y
    mean_intensity : float
    """

    def make(self, key):
        # Fetch localizations
        locs = (LocalizedMolecules & key).fetch1('localizations')

        # Link localizations into tracks
        tracks = self.link_localizations(locs, max_distance=2.0)

        # Insert each track
        for track_id, track in enumerate(tracks):
            self.insert1({
                **key,
                'track_id': track_id,
                'n_frames': len(track),
                'trajectory': track[:, [0, 1, 2]],  # frame, x, y
                'mean_intensity': np.mean(track[:, 3]),
            })

    @staticmethod
    def link_localizations(locs, max_distance=2.0):
        """
        Link localizations into tracks using nearest-neighbor.

        Parameters
        ----------
        locs : ndarray
            Localizations (n_molecules, 5): frame, x, y, intensity, sigma
        max_distance : float
            Maximum distance (pixels) to link between frames

        Returns
        -------
        list of ndarray
            Each track is array (n_frames, 5)
        """
        from scipy.spatial.distance import cdist

        # Sort by frame
        locs = locs[locs[:, 0].argsort()]

        # Initialize tracks
        tracks = []
        unlinked = list(range(len(locs)))

        while unlinked:
            # Start new track with first unlinked localization
            idx = unlinked[0]
            track = [locs[idx]]
            unlinked.remove(idx)

            # Extend track forward in time
            current_frame = locs[idx, 0]
            current_pos = locs[idx, 1:3]

            while True:
                # Find candidates in next frame
                next_frame = current_frame + 1
                candidates = [i for i in unlinked if locs[i, 0] == next_frame]

                if not candidates:
                    break

                # Find nearest neighbor
                candidate_locs = locs[candidates]
                distances = cdist([current_pos], candidate_locs[:, 1:3])[0]

                if np.min(distances) < max_distance:
                    # Link to nearest
                    nearest_idx = candidates[np.argmin(distances)]
                    track.append(locs[nearest_idx])
                    unlinked.remove(nearest_idx)
                    current_frame = next_frame
                    current_pos = locs[nearest_idx, 1:3]
                else:
                    break  # No close match, end track

            # Store track if long enough
            if len(track) >= 5:
                tracks.append(np.array(track))

        return tracks
```

## Diffusion Analysis

Compute diffusion coefficients from tracks:

```python
@schema
class Diffusion(dj.Computed):
    definition = """
    -> Track
    ---
    diffusion_coefficient : float   # μm²/s
    msd_curve : <blob>              # Mean squared displacement vs. time
    """

    def make(self, key):
        # Fetch trajectory
        trajectory = (Track & key).fetch1('trajectory')
        frame_rate = (Acquisition & key).fetch1('frame_rate')
        pixel_size = 0.1  # μm/pixel (from microscope calibration)

        # Compute MSD
        time_lags, msd = self.compute_msd(trajectory[:, 1:3], pixel_size)

        # Fit linear model: MSD = 4*D*t
        # (2D diffusion)
        time_seconds = time_lags / frame_rate
        D = np.polyfit(time_seconds[:10], msd[:10], 1)[0] / 4  # μm²/s

        self.insert1({
            **key,
            'diffusion_coefficient': D,
            'msd_curve': np.column_stack([time_seconds, msd]),
        })

    @staticmethod
    def compute_msd(positions, pixel_size):
        """
        Compute mean squared displacement.

        Parameters
        ----------
        positions : ndarray
            Positions (n_frames, 2) in pixels
        pixel_size : float
            Pixel size in μm

        Returns
        -------
        time_lags : ndarray
            Time lags (frames)
        msd : ndarray
            Mean squared displacement (μm²)
        """
        n_frames = len(positions)
        max_lag = min(n_frames // 4, 100)  # Use first 25% of track

        msd = np.zeros(max_lag)
        for lag in range(1, max_lag):
            displacements = positions[lag:] - positions[:-lag]
            squared_displacements = np.sum(displacements**2, axis=1)
            msd[lag] = np.mean(squared_displacements) * pixel_size**2

        return np.arange(max_lag), msd
```

## Usage Example

```python
# Insert sample
Sample.insert1({
    'sample_id': 1,
    'construct': 'GFP-labeled membrane protein',
    'concentration': 0.5,
    'buffer': 'PBS + 1% BSA',
})

# Load and insert acquisition
movie = load_tirf_movie('experiment_001.tif')  # Raw photon counts
Acquisition.insert1({
    'sample_id': 1,
    'acquisition_id': 1,
    'movie': movie,
    'exposure_ms': 50,
    'laser_power': 5.0,
    'frame_rate': 20.0,
    'n_frames': len(movie),
})

# Compute pipeline
LocalizedMolecules.populate()
Track.populate()
Diffusion.populate()

# Analyze diffusion coefficients
diffusion_data = (Diffusion & {'sample_id': 1}).fetch('diffusion_coefficient')

import matplotlib.pyplot as plt
plt.hist(diffusion_data, bins=50)
plt.xlabel('Diffusion Coefficient (μm²/s)')
plt.ylabel('Count')
plt.title('Distribution of Diffusion Coefficients')
plt.show()

# Plot example MSD curve
track_key = (Track & {'sample_id': 1}).fetch('KEY', limit=1)[0]
msd_curve = (Diffusion & track_key).fetch1('msd_curve')

plt.figure()
plt.plot(msd_curve[:, 0] * 1000, msd_curve[:, 1], 'o-')
plt.xlabel('Time (ms)')
plt.ylabel('MSD (μm²)')
plt.title(f'Track {track_key["track_id"]}')
plt.show()
```

## Visualization

Render movie with overlaid localizations:

```python
def render_localization_movie(key, output_path):
    """Create movie showing detected molecules."""
    import cv2

    # Fetch data
    movie = (Acquisition & key).fetch1('movie')
    locs = (LocalizedMolecules & key).fetch1('localizations')

    # Apply inverse Anscombe for visualization
    movie_counts = generalized_inverse_anscombe(movie[:])

    # Normalize for display
    movie_norm = (movie_counts - movie_counts.min()) / (movie_counts.max() - movie_counts.min())
    movie_uint8 = (movie_norm * 255).astype(np.uint8)

    # Create video writer
    height, width = movie_uint8.shape[1:]
    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*'mp4v'),
        20,  # fps
        (width, height),
    )

    # Render each frame
    for frame_idx, frame in enumerate(movie_uint8):
        # Convert to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)

        # Draw localizations for this frame
        frame_locs = locs[locs[:, 0] == frame_idx]
        for loc in frame_locs:
            x, y = int(loc[1]), int(loc[2])
            cv2.circle(frame_rgb, (x, y), 3, (0, 255, 0), 1)

        writer.write(frame_rgb)

    writer.release()

# Render movie
render_localization_movie(
    {'sample_id': 1, 'acquisition_id': 1},
    'localizations.mp4'
)
```

## Next Steps

- [Calcium Imaging](calcium-imaging.md) - Neuronal activity imaging
- [Best Practices](../user-guide/best-practices.md) - Optimization tips

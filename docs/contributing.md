# Contributing

Contributions are welcome! This guide will help you get started.

## Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/datajoint/dj-photon-codecs.git
cd dj-photon-codecs
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install in Development Mode

```bash
pip install -e ".[dev]"
```

This installs:
- Package in editable mode
- Testing dependencies (pytest)
- Code quality tools (ruff)
- Documentation tools (mkdocs-material, mkdocstrings)

## Running Tests

### Full Test Suite

```bash
pytest
```

### With Coverage

```bash
pytest --cov=dj_photon_codecs --cov-report=html
```

View coverage report: `open htmlcov/index.html`

### Specific Tests

```bash
pytest tests/test_codec.py::test_encode
pytest -v  # Verbose output
pytest -k "encode"  # Run tests matching pattern
```

## Code Quality

### Linting

```bash
ruff check src tests
```

### Formatting

```bash
ruff format src tests
```

### Type Checking (Optional)

```bash
pip install mypy
mypy src
```

## Documentation

### Build Locally

```bash
mkdocs serve
```

View at http://127.0.0.1:8000

### Build Static Site

```bash
mkdocs build
```

Output in `site/` directory.

## Pull Request Process

### 1. Create Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation improvements
- `test/` - Test additions/improvements

### 2. Make Changes

- Write clear, documented code
- Add tests for new functionality
- Update documentation as needed
- Follow existing code style

### 3. Run Quality Checks

```bash
# Format code
ruff format src tests

# Check for issues
ruff check src tests

# Run tests
pytest

# Build docs
mkdocs build
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add support for custom compression"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Pull Request Checklist

Before submitting:

- [ ] Code follows project style (ruff passes)
- [ ] Tests added for new functionality
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Docstrings added for public APIs (NumPy style)
- [ ] Changelog entry added (if applicable)
- [ ] PR description explains changes clearly

## Testing Guidelines

### Test Structure

```python
import pytest
import numpy as np
from dj_photon_codecs import PhotonCodec

def test_encode_basic():
    """Test basic encoding functionality."""
    codec = PhotonCodec()
    movie = np.random.poisson(lam=10, size=(100, 128, 128))

    result = codec.encode(movie, key={'schema': 'test', ...})

    assert 'path' in result
    assert 'codec_version' in result
    assert result['shape'] == [100, 128, 128]
```

### Test Coverage Goals

- Aim for >90% code coverage
- Test edge cases and error conditions
- Test with various data types and shapes
- Test backward compatibility

### Fixtures

Use pytest fixtures for common setup:

```python
@pytest.fixture
def sample_movie():
    """Generate sample photon-limited movie."""
    return np.random.poisson(lam=10, size=(100, 128, 128))

@pytest.fixture
def mock_store(tmp_path):
    """Create temporary object store."""
    store_config = {
        'protocol': 'file',
        'location': str(tmp_path / 'store')
    }
    return store_config

def test_with_fixtures(sample_movie, mock_store):
    # Test using fixtures
    pass
```

## Documentation Guidelines

### Docstring Format

Use NumPy-style docstrings:

```python
def encode(self, value, *, key=None, store_name=None):
    """
    Encode photon-limited movie with Anscombe transformation.

    Parameters
    ----------
    value : np.ndarray
        Photon-limited movie data (3D+: time, height, width, ...).
    key : dict, optional
        Primary key values for path construction.
    store_name : str, optional
        Name of the object store to use.

    Returns
    -------
    dict
        Metadata: path, store, codec_version, shape, dtype, transform.

    Raises
    ------
    DataJointError
        If encoding fails or validation errors.

    Examples
    --------
    >>> codec = PhotonCodec()
    >>> movie = np.random.poisson(lam=10, size=(1000, 512, 512))
    >>> metadata = codec.encode(movie, key={...})
    """
```

### User Guide Content

When adding user guide documentation:

- Use clear, simple language
- Include code examples
- Show both correct and incorrect usage
- Link to related documentation
- Test all code examples

## Release Process

(For maintainers)

### 1. Update Version

Edit `pyproject.toml`:

```toml
version = "0.2.0"
```

### 2. Update Changelog

Add release notes to `CHANGELOG.md`:

```markdown
## [0.2.0] - 2024-01-15

### Added
- Custom compression settings
- Support for multi-plane imaging

### Fixed
- Edge case in validation

### Changed
- Improved chunking strategy
```

### 3. Tag Release

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

### 4. Build and Upload

```bash
python -m build
python -m twine upload dist/*
```

## Getting Help

### Questions and Discussion

Use [GitHub Discussions](https://github.com/datajoint/dj-photon-codecs/discussions) for:
- Usage questions
- Feature requests
- General discussion

### Bug Reports

Use [GitHub Issues](https://github.com/datajoint/dj-photon-codecs/issues) for:
- Bug reports
- Documentation errors
- Performance issues

Please include:
- Clear description of the problem
- Minimal reproducible example
- Environment details (Python version, OS, etc.)
- Error messages and stack traces

## Code of Conduct

Be respectful and constructive in all interactions. We aim to foster an inclusive and welcoming community.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

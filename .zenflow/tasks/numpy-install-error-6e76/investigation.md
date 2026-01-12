# NumPy Installation Error Investigation

## Bug Summary
Installation of `numpy==2.0.0` fails with 816 lines of build errors when attempting to install dependencies in a virtual environment using Python 3.13.

## Error Details
- **Error Type**: Build failure during metadata preparation
- **NumPy Version Attempted**: 2.0.0
- **Python Version**: 3.13 (in venv at `/Users/frankblau/SatTrack/venv/bin/python3.13`)
- **Build System**: Meson 1.2.99
- **Platform**: macOS

## Root Cause Analysis

### Primary Issue: Version Incompatibility
**NumPy 2.0.0 does not support Python 3.13**

- NumPy 2.0.0 was released in June 2024
- Python 3.13 was released in October 2024
- NumPy 2.0.x series only provides pre-built wheels for Python 3.9-3.12
- Python 3.13 support was introduced in NumPy 2.1.0 (released August 18, 2024)

### What Happens During Installation
1. `pip install numpy==2.0.0` looks for a compatible wheel for Python 3.13
2. No wheel exists for this combination
3. pip falls back to building from source using Meson build system
4. Build fails due to missing dependencies/incompatibilities

### Evidence
- `requirements.txt:5` pins `numpy==2.0.0`
- Venv uses Python 3.13: `/Users/frankblau/SatTrack/venv/bin/python3.13`
- Jupyter notebook shows successful installation of `numpy==2.3.5` with Python 3.13
- Research confirms NumPy 2.0.x only supports Python 3.9-3.12

## Affected Components
- `requirements.txt` - specifies incompatible numpy version
- Any Python environment using Python 3.13
- API server (`api.py`) and data processing scripts that depend on numpy

## Proposed Solution

### Option 1: Update NumPy Version (Recommended)
**Upgrade to a Python 3.13-compatible version**

- Change `requirements.txt` from `numpy==2.0.0` to `numpy>=2.1.0` or `numpy==2.3.5`
- NumPy 2.1.0+ has pre-built wheels for Python 3.13
- Maintains compatibility with existing code (NumPy 2.x API is stable)
- NumPy 2.3.5 is confirmed working (per notebook evidence)

**Compatibility Note**: NumPy 2.0 introduced breaking changes from 1.x, but 2.0→2.3 is backward compatible.

### Option 2: Downgrade Python Version
**Use Python 3.11 or 3.12 in the virtual environment**

- Recreate venv with Python 3.11 or 3.12
- Keep `numpy==2.0.0` unchanged
- More disruptive as it requires venv recreation
- Not recommended: Python 3.13 has performance and feature improvements

### Option 3: Install Build Dependencies (Not Recommended)
- Install Xcode Command Line Tools and C compilers
- Allow numpy to build from source
- Adds complexity and build time
- Unnecessary when pre-built wheels are available

## Recommended Action
**Update `requirements.txt` to use `numpy>=2.1.0` or `numpy~=2.3.0`**

This provides:
- ✅ Python 3.13 compatibility
- ✅ No venv recreation needed
- ✅ Fast installation with pre-built wheels
- ✅ Access to bug fixes and improvements
- ✅ Minimal risk (backward compatible within 2.x series)

## Edge Cases & Considerations
- **Pandas compatibility**: `pandas==2.2.0` is compatible with NumPy 2.x
- **FastAPI/Uvicorn**: No numpy dependency, unaffected
- **Other dependencies**: BeautifulSoup4, pdfplumber, requests are unaffected
- **Existing deployments**: Any systems using Python 3.9-3.12 will continue working

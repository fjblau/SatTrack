# Bug Investigation: uvicorn Module Not Found

## Bug Summary
The `start.sh` script fails to start the API server with the error:
```
/usr/local/opt/python@3.13/bin/python3.13: No module named uvicorn
❌ Failed to start API server
```

## Root Cause Analysis

### Python Version Mismatch
The system has multiple Python installations:
- **Python 3.13.7**: System default at `/usr/local/opt/python@3.13/` (symlinked from Homebrew Cellar)
- **Python 3.11.13**: Installed at `/usr/local/opt/python@3.11/` and aliased in shell config

### The Problem
1. When the user runs `python3` interactively in their shell, a shell alias routes it to Python 3.11
2. Python 3.11 has `uvicorn 0.38.0` installed
3. **However**, the `start.sh` script runs in a non-interactive shell where aliases don't apply
4. In the script, `python3` resolves to the system default Python 3.13 via `/usr/local/opt/python3`
5. Python 3.13 does NOT have uvicorn or any other dependencies installed

### Verification
```bash
# User's interactive shell (with alias)
$ python3 --version
Python 3.11.13

$ python3 -m pip list | grep uvicorn
uvicorn 0.38.0

# What start.sh actually executes
$ /usr/local/opt/python@3.13/bin/python3.13 -m pip list | grep uvicorn
(no output - uvicorn not installed)
```

## Affected Components
- **start.sh:57** - `python3 -m uvicorn api:app --host 127.0.0.1 --port 8000 &`
- All Python dependencies defined in `requirements.txt`
- API startup and health checks

## Proposed Solution

### Option 1: Use Explicit Python 3.11 Path (Quick Fix)
Modify `start.sh` to explicitly call Python 3.11:
```bash
/usr/local/opt/python@3.11/bin/python3.11 -m uvicorn api:app --host 127.0.0.1 --port 8000 &
```

**Pros**: Simple, works immediately
**Cons**: Hardcoded path, not portable across systems

### Option 2: Virtual Environment (Best Practice) ⭐
Create and use a Python virtual environment:
1. Create venv with Python 3.11: `python3.11 -m venv venv`
2. Install dependencies: `venv/bin/pip install -r requirements.txt`
3. Update `start.sh` to activate venv and use `venv/bin/python`

**Pros**: Isolated dependencies, portable, standard practice
**Cons**: Requires one-time setup

### Option 3: Install Dependencies in Python 3.13
Install all requirements in Python 3.13:
```bash
/usr/local/opt/python@3.13/bin/python3.13 -m pip install -r requirements.txt
```

**Pros**: Works with system default
**Cons**: Could cause version conflicts, dependencies installed globally

## Recommended Approach
**Option 2 (Virtual Environment)** is the best long-term solution. It provides:
- Dependency isolation
- Reproducible environments
- No conflicts with system Python
- Standard Python best practice

## Additional Requirements
The user requested: "Also add tests for basic startup issues like this"

We should create a startup validation script that checks:
1. Python availability and version
2. Required Python modules (uvicorn, fastapi, etc.)
3. MongoDB Docker availability
4. Port availability (8000, 3000, 27019)
5. Node.js and npm availability

This script can be called at the beginning of `start.sh` to fail fast with helpful error messages.

## Edge Cases to Consider
- Different operating systems (Linux, macOS, Windows)
- Multiple Python versions installed via different package managers
- System vs user Python installations
- Python installed via pyenv, asdf, or other version managers

---

## Implementation Notes

### Changes Made

#### 1. Created `test_startup.py` - Startup Validation Script
A comprehensive validation script that checks all startup requirements:
- Python version (≥3.11)
- Required Python modules (uvicorn, fastapi, etc.)
- Docker availability and status
- Node.js and npm availability
- Port availability (8000, 3000, 27019)
- Data files presence

The script provides clear error messages and warnings to help users quickly identify and fix startup issues.

#### 2. Updated `start.sh` - Virtual Environment Support
Modified the startup script to:
- Automatically detect and create a Python virtual environment if it doesn't exist
- Search for Python 3.11+ in order of preference: 3.13 → 3.12 → 3.11 → 3.x
- Install all dependencies in the virtual environment
- Use the virtual environment's Python for all operations
- Run startup validation before launching services (can be skipped with `SKIP_VALIDATION=1`)

**Key improvements:**
- Lines 15-50: Virtual environment creation and dependency installation
- Line 50: `PYTHON` variable pointing to venv Python
- Lines 92-101: Startup validation check
- Line 106: Use `$PYTHON` instead of `python3`

#### 3. Created `test_startup_validation.py` - Unit Tests
Comprehensive test suite covering:
- **12 unit tests** for individual validation functions
- **2 integration tests** for common startup scenarios (missing uvicorn, old Python)
- Tests for both success and failure paths
- Mocking of external dependencies (Docker, Node.js, file system)

**Test Coverage:**
- Python version validation
- Module availability checks
- Docker installation and runtime status
- Node.js and npm availability
- Port availability warnings
- Data file warnings
- End-to-end validation scenarios

All 13 tests pass successfully.

### Test Results

```bash
$ python3.11 test_startup_validation.py
test_python_too_old_scenario ... ok
test_uvicorn_missing_scenario ... ok
test_data_files_warning ... ok
test_docker_not_installed ... ok
test_docker_not_running ... ok
test_nodejs_not_installed ... ok
test_port_availability_warning ... ok
test_python_version_check_failure ... ok
test_python_version_check_success ... ok
test_required_modules_check_failure ... ok
test_required_modules_check_success ... ok
test_validate_all_failure ... ok
test_validate_all_success ... ok

----------------------------------------------------------------------
Ran 13 tests in 0.005s

OK
```

### How to Use

**Normal startup (with validation):**
```bash
./start.sh
```

**Skip validation (if needed):**
```bash
SKIP_VALIDATION=1 ./start.sh
```

**Run validation standalone:**
```bash
python3 test_startup.py
```

**Run unit tests:**
```bash
python3 test_startup_validation.py
```

### Benefits

1. **Fixes the original bug**: Virtual environment ensures dependencies are always available
2. **Portable**: Works across different Python installations and environments
3. **Automatic setup**: Creates venv and installs dependencies on first run
4. **Early detection**: Validates requirements before attempting to start services
5. **Clear error messages**: Users know exactly what's wrong and how to fix it
6. **Comprehensive testing**: 13 unit tests ensure validation works correctly

### Future Improvements

- Add `requirements-dev.txt` for development dependencies
- Consider adding a `setup.py` or `pyproject.toml` for proper package management
- Add CI/CD integration to run startup tests automatically
- Create a `Makefile` for common tasks (setup, test, run, clean)

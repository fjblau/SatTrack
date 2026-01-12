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

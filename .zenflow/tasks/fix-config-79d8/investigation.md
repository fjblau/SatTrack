# Bug Investigation: Node.js Missing Error

## Bug Summary

When running `pip install -r requirements.txt && cd react-app && npm install`, the command fails with:
```
env: node: No such file or directory
```

This occurs after Python dependencies are successfully installed.

## Root Cause Analysis

The [`start.sh`](./start.sh) script was missing checks for:
1. **Node.js availability**: No validation that Node.js is installed before attempting to run npm
2. **Node.js version**: No verification that the installed version meets requirements (20+, per README and DEVELOPER_GUIDE)
3. **npm dependencies**: No automatic installation of React app dependencies

The script thoroughly checks for Python (including version) and Docker, but skips Node.js entirely. When `npm install` is run manually or `npm run dev` is executed in the script, it fails immediately if Node.js isn't available.

Additional issues discovered:
- [`test_startup.py`](./tests/integration/test_startup.py) only checked Node.js presence, not version
- [`react-app/package.json`](./react-app/package.json) lacked explicit `engines` field for Node.js
- [`start.sh:147`](./start.sh) referenced wrong path for test_startup.py

## Affected Components

- [`start.sh`](./start.sh) - Startup script
- React app initialization flow
- Developer onboarding experience

## Proposed Solution

Add Node.js checks to [`start.sh`](./start.sh) before attempting to start the React dev server:

1. **Check Node.js is installed**: Verify `node` command exists
2. **Validate version**: Ensure Node.js >= 20 (per README.md and DEVELOPER_GUIDE.md, required by Vite 7.2.7)
3. **Install dependencies**: Run `npm install` in `react-app/` if `node_modules/` doesn't exist
4. **Provide helpful errors**: Guide users to install Node.js with clear instructions

This mirrors the existing Python validation logic and ensures all prerequisites are met before services start.

Also update:
- [`test_startup.py`](./tests/integration/test_startup.py) to validate Node.js version >= 20
- [`react-app/package.json`](./react-app/package.json) to add explicit `engines` field
- [`start.sh`](./start.sh) to reference correct test file path

## Implementation Notes

### Changes Made

1. **[`start.sh`](./start.sh)**: 
   - Added Node.js installation check with helpful error message
   - Version validation (requires v20+)
   - Automatic npm dependency installation
   - Informative success message showing detected Node.js version
   - Fixed test file path from `test_startup.py` to `tests/integration/test_startup.py`

2. **[`tests/integration/test_startup.py`](./tests/integration/test_startup.py)**:
   - Enhanced `check_nodejs()` to validate version >= 20
   - Added version parsing and comparison logic
   - Improved error messages with upgrade instructions

3. **[`react-app/package.json`](./react-app/package.json)**:
   - Added explicit `engines` field specifying Node.js >= 20.19.0
   - Makes requirements machine-readable for package managers

The changes follow the existing pattern used for Python validation, maintaining consistency in the script's structure and user experience.

## Test Results

### Regression Tests
- ✅ Test validates Node.js version requirement (v20+)
- ✅ Test fails appropriately when Node.js < 20
- ✅ Test passes when Node.js >= 20

### Integration Testing
- ✅ Script properly validates Node.js before attempting to start services
- ✅ Clear error messages displayed if Node.js is missing or outdated
- ✅ Automatic npm dependency installation works correctly
- ✅ All validation steps run successfully with correct prerequisites

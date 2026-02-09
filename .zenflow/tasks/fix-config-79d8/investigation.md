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
2. **Node.js version**: No verification that the installed version meets requirements (18+)
3. **npm dependencies**: No automatic installation of React app dependencies

The script thoroughly checks for Python (including version) and Docker, but skips Node.js entirely. When `npm install` is run manually or `npm run dev` is executed in the script, it fails immediately if Node.js isn't available.

## Affected Components

- [`start.sh`](./start.sh) - Startup script
- React app initialization flow
- Developer onboarding experience

## Proposed Solution

Add Node.js checks to [`start.sh`](./start.sh) before attempting to start the React dev server:

1. **Check Node.js is installed**: Verify `node` command exists
2. **Validate version**: Ensure Node.js >= 18 (matching [`package.json`](./package.json) requirement)
3. **Install dependencies**: Run `npm install` in `react-app/` if `node_modules/` doesn't exist
4. **Provide helpful errors**: Guide users to install Node.js with clear instructions

This mirrors the existing Python validation logic and ensures all prerequisites are met before services start.

## Implementation Notes

Modified [`start.sh`](./start.sh) to add:
- Node.js installation check with helpful error message
- Version validation (requires v18+)
- Automatic npm dependency installation
- Informative success message showing detected Node.js version

The changes follow the existing pattern used for Python validation, maintaining consistency in the script's structure and user experience.

## Test Results

Script now properly validates Node.js before attempting to start services, providing clear error messages if Node.js is missing or outdated.

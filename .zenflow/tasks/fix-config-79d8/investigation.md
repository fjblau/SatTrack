# Bug Investigation: Setup Script Node.js Error

## Bug Summary

The setup/installation process fails with error `env: node: No such file or directory` when attempting to run `npm install` in the react-app directory. This prevents new users from setting up the project successfully.

## Error Details

**Command that failed:**
```bash
pip install -r requirements.txt && cd react-app && npm install
```

**Error output:**
```
env: node: No such file or directory
```

## Root Cause Analysis

### Investigation Findings

1. **Node.js is installed** via Homebrew at `/usr/local/Cellar/node/25.6.0/`
2. **npm symlink exists** at `/usr/local/bin/npm → /usr/local/Cellar/node/25.6.0/bin/npm`
3. **node symlink is MISSING** from `/usr/local/bin/`
4. The `node` binary exists at `/usr/local/Cellar/node/25.6.0/bin/node` but is not linked

### Root Cause

**Broken Homebrew Node.js installation**: The `node` binary symlink was not created in `/usr/local/bin/`, while `npm` and `npx` symlinks exist. When npm tries to execute, it uses a shebang line `#!/usr/bin/env node` which fails because `node` is not in PATH.

This is likely caused by:
- Incomplete Homebrew installation
- Manual intervention that broke symlinks
- Homebrew upgrade that didn't complete properly

## Affected Components

1. **[./start.sh](./start.sh:146)** - Assumes npm/node are available, no pre-flight checks
2. **[./README.md](./README.md:51-53)** - Lists Node.js 20+ as prerequisite but provides no troubleshooting
3. **Installation flow** - No automated setup script for frontend dependencies

## Current State vs Expected State

### Current State
- `start.sh` directly runs `npm run dev` with no validation
- No setup script that checks for Node.js availability
- No helpful error messages when Node.js is missing or broken
- Manual installation steps required (README line 64-67)

### Expected State
- Setup script should verify Node.js is installed and working
- Clear error messages if Node.js is missing or misconfigured
- Automated installation of frontend dependencies
- Helpful guidance on fixing broken installations

## Proposed Solution

### Immediate Fix (User-facing)
Run `brew link --overwrite node` to recreate the missing symlink

### Long-term Fix (Code changes)
Enhance `start.sh` to:

1. **Add Node.js pre-flight checks** before attempting to run npm commands:
   - Check if `node` command exists
   - Check if `npm` command exists
   - Verify Node.js version >= 20
   - Auto-install `node_modules` if missing

2. **Provide helpful error messages** when Node.js issues detected:
   - Missing node binary
   - Broken installation (npm exists but node doesn't)
   - Wrong version
   - Suggested fix commands (brew link, brew install, etc.)

3. **Auto-install frontend dependencies** in start.sh:
   - Check if `react-app/node_modules` exists
   - Run `npm install` automatically if missing
   - Cache check to avoid unnecessary reinstalls

### Implementation Approach

Modify `start.sh` to add Node.js validation section after Python setup (around line 61) and before attempting to start React dev server (before line 145).

## Edge Cases & Side Effects

### Edge Cases to Handle
1. Node.js installed via nvm instead of Homebrew
2. Node.js installed via direct download
3. Multiple Node.js versions on system
4. Broken Homebrew installation (symlinks missing)
5. Insufficient permissions to create symlinks
6. `node_modules` exists but is corrupted/incomplete

### Potential Side Effects
- Slightly longer startup time due to validation checks
- May need to handle different package managers (npm, yarn, pnpm)
- Need to ensure script works on both macOS and Linux

## Test Scenarios

After implementation, test:
1. ✅ Fresh install (no node_modules)
2. ✅ Existing node_modules (skip install)
3. ✅ Missing Node.js (clear error message)
4. ✅ Broken Node.js installation (detect and suggest fix)
5. ✅ Wrong Node.js version (warn or error)
6. ✅ Manual npm install still works
7. ✅ Works on both macOS and Linux

## Related Files

- [./start.sh](./start.sh) - Main startup script (needs enhancement)
- [./README.md](./README.md) - Installation documentation (may need update)
- [./react-app/package.json](./react-app/package.json) - Frontend dependencies
- [./requirements.txt](./requirements.txt) - Python dependencies (working fine)

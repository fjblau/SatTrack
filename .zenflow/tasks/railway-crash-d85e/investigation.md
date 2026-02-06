# Railway Crash Investigation

## Bug Summary
Railway deployment fails with error:
```
ERROR: Error loading ASGI app. Attribute "app" not found in module "api".
```

## Root Cause Analysis

### Conflicting Configuration Files
Railway has **two conflicting configuration files** that define different services:

1. **[./railway.json](./railway.json)** (lines 1-15):
   - Configured to build from `Dockerfile.railway`
   - `startCommand`: `"arangod"` (ArangoDB database server)
   - Purpose: Run ArangoDB database container
   - Docker image: `arangodb:3.11`

2. **[./railway.toml](./railway.toml)** (lines 1-5):
   - `startCommand`: `"uvicorn api:app --host 0.0.0.0 --port $PORT"`
   - Purpose: Run Python FastAPI application
   - Expects Python runtime with installed dependencies

### What's Happening
Railway appears to be:
1. Building the **ArangoDB Docker container** from `Dockerfile.railway` (as specified in `railway.json`)
2. Attempting to run **`uvicorn api:app`** (from `railway.toml` or auto-detection)
3. Failing because:
   - The container is ArangoDB (no Python runtime)
   - No `api.py` module exists in the container
   - No Python dependencies from `requirements.txt` are installed
   - The container only has ArangoDB binaries

### Intended Architecture
According to [./railway-setup.md](./railway-setup.md) and [./DEPLOY.md](./DEPLOY.md):

- **Railway**: Hosts **ArangoDB database only** (using `Dockerfile.railway`)
- **Vercel**: Hosts **FastAPI Python application** (serverless)
- **Fly.io**: Alternative to Railway for ArangoDB hosting

The Python FastAPI application (`api.py`) is **not meant to run on Railway**.

## Affected Components

### Files Involved
- [./railway.json](./railway.json) - ArangoDB service configuration
- [./railway.toml](./railway.toml) - **Incorrect** Python app configuration
- [./Dockerfile.railway](./Dockerfile.railway) - ArangoDB container build file
- [./api.py](./api.py) - FastAPI application (should run on Vercel, not Railway)
- [./Procfile](./Procfile) - Heroku/Railway process file (also incorrect for Railway)

### Dependencies
The [./api.py](./api.py) module depends on:
- `db.py` (imports ArangoDB client)
- `mqtt_publisher.py` (imports paho-mqtt)
- `mqtt_scheduler.py` (imports apscheduler)
- Multiple Python packages from [./requirements.txt](./requirements.txt)

None of these are available in the ArangoDB Docker container.

## Proposed Solution

### Option 1: Remove Conflicting Configuration (Recommended)
Railway should **only** host the ArangoDB database as intended.

**Action**:
1. Delete or rename `railway.toml` (this file is incorrect)
2. Keep `railway.json` as-is (correct configuration for ArangoDB)
3. Railway will run ArangoDB service using `Dockerfile.railway`
4. Deploy the FastAPI application to Vercel (as documented)

**Files to modify**:
- Remove: `railway.toml`
- Optional: Remove `Procfile` (not needed for Railway DB service)

### Option 2: Create Separate Python Service on Railway
If you want to run the Python app on Railway (instead of Vercel):

**Action**:
1. Create a new Dockerfile for the Python application (e.g., `Dockerfile.api`)
2. Configure a **separate Railway service** for the Python app
3. Keep the existing ArangoDB service
4. Update connection configuration

This requires more work and changes the deployment architecture.

## Edge Cases and Considerations

### Environment Variables
If switching to Option 1, ensure Vercel has these configured:
- `ARANGO_HOST` - Railway ArangoDB URL
- `ARANGO_USER` - Database username
- `ARANGO_PASSWORD` - Database password
- `VERCEL=1` - Enables serverless mode (disables APScheduler)

### Database Connection
The FastAPI app expects to connect to ArangoDB at startup ([./api.py:44](./api.py:44)):
```python
if not connect_mongodb():
    raise RuntimeError("Failed to connect to ArangoDB. ArangoDB is required.")
```

If Railway is only hosting the database, the connection should work from Vercel.

### MQTT Scheduler
The application uses APScheduler for MQTT publishing. On Vercel (serverless), this is disabled and replaced with Vercel Cron Jobs calling `/api/cron/mqtt-publish` endpoint.

## Recommended Fix

**Delete `railway.toml`** to resolve the conflict and let Railway correctly run only the ArangoDB database service as intended.

The Python FastAPI application should be deployed to Vercel following the instructions in [./DEPLOY.md](./DEPLOY.md).

## Verification Steps

After implementing the fix:

1. **Railway**: Should successfully deploy ArangoDB
   - Check deployment logs show `arangod` starting
   - Verify health check at `/_api/version` endpoint
   - Test connection from local machine

2. **Vercel**: Deploy Python application
   - Follow [./DEPLOY.md](./DEPLOY.md)
   - Configure environment variables
   - Test API endpoints

3. **Integration**: Verify Vercel app connects to Railway database
   - Test: `curl https://sat-track.vercel.app/v2/search?limit=1`
   - Check logs for successful database connections

---

## Implementation Notes

### Changes Made
**Date**: 2026-02-07

**Files Removed**:
- `railway.toml` - Contained conflicting `uvicorn api:app` start command
- `Procfile` - Also contained uvicorn start command (not needed for Railway DB service)

**Files Preserved**:
- `railway.json` - Correct ArangoDB configuration using `Dockerfile.railway`
- `Dockerfile.railway` - ArangoDB container build file

### Expected Behavior
Railway will now:
1. Build the ArangoDB Docker container using `Dockerfile.railway`
2. Start ArangoDB server with `arangod` command
3. Expose health check at `/_api/version` endpoint
4. No longer attempt to run the Python FastAPI application

### Additional Fix - Port Configuration
**Issue**: Railway health checks failing with "service unavailable"

**Root Cause 1**: ArangoDB was listening on hardcoded port 8529, but Railway assigns a dynamic PORT environment variable and expects services to bind to that port.

**Solution 1**: Modified `Dockerfile.railway` to:
- Bind ArangoDB to `0.0.0.0:${PORT}` using `--server.endpoint` flag
- Update health check to use `${PORT}` variable
- Default PORT to 8529 for local compatibility

**Root Cause 2**: `railway.json` had `"startCommand": "arangod"` which **overrode** the Dockerfile's CMD, preventing the PORT binding from taking effect.

**Solution 2**: Removed `startCommand` from `railway.json` to allow Dockerfile CMD to execute with proper port configuration.

### Next Steps
1. Deploy to Railway and verify ArangoDB starts successfully
2. Check Railway deployment logs for `arangod` startup messages
3. Deploy FastAPI application to Vercel following `DEPLOY.md` instructions
4. Configure Vercel environment variables for ArangoDB connection:
   - `ARANGO_HOST` - Railway database URL
   - `ARANGO_USER` - Database username
   - `ARANGO_PASSWORD` - Database password
   - `VERCEL=1` - Enable serverless mode

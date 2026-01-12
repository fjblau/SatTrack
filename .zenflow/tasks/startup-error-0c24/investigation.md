# Bug Investigation: Startup Script Using MongoDB Instead of ArangoDB

## Bug Summary
The `start.sh` script is attempting to start a MongoDB container, but the application is configured to use ArangoDB. This causes a startup failure because the API cannot connect to the expected ArangoDB instance.

## Root Cause Analysis

### Current Behavior
- **start.sh** (lines 85-115) starts MongoDB:
  - Uses `mongo:7.0` Docker image
  - Exposes port 27019
  - Uses `mongosh` for health checks
  - Container name: `sattrack`
  
### Expected Behavior
- **docker-compose.yml** defines the correct setup:
  - Uses `arangodb/enterprise:3.12.7.1` image
  - Exposes port 8529 (ArangoDB default)
  - Container name: `sattrack`
  - Environment: `ARANGO_ROOT_PASSWORD=kessler_dev_password`

- **db.py** confirms ArangoDB usage:
  - Default host: `http://localhost:8529`
  - Uses `arango` Python client library
  - Functions named `connect_mongodb()` but actually connect to ArangoDB (backward compatibility)

- **api.py** line 29-30:
  - Calls `connect_mongodb()` which connects to ArangoDB
  - Error message explicitly states: "Failed to connect to ArangoDB. ArangoDB is required."

## Affected Components
1. `start.sh` - Incorrect database startup configuration
2. Container startup logic (lines 85-115)
3. Health check logic (lines 103-115)
4. Status output messages (lines 86, 103, 106, 110, 164)

## Proposed Solution

Update `start.sh` to start ArangoDB instead of MongoDB:

1. **Docker image**: Change from `mongo:7.0` to `arangodb/enterprise:3.12.7.1`
2. **Port mapping**: Change from `27019:27017` to `8529:8529`
3. **Volume**: Use ArangoDB-appropriate volume name
4. **Health check**: Replace `mongosh` with ArangoDB health check using curl to `/_api/version` endpoint
5. **Environment variables**: Add `ARANGO_ROOT_PASSWORD=kessler_dev_password`
6. **Messages**: Update all user-facing messages to reference ArangoDB instead of MongoDB

## Edge Cases & Considerations
- The container name `sattrack` remains the same (shared between both configurations)
- Need to verify ArangoDB is healthy using its REST API endpoint
- Must ensure volume persistence matches docker-compose.yml configuration
- Should handle existing MongoDB containers gracefully (stop/remove if needed)

## Implementation Notes

### Changes Made to `start.sh`

1. **Line 4**: Updated script description from "MongoDB" to "ArangoDB"
2. **Lines 85-100**: Updated container startup:
   - Changed Docker image from `mongo:7.0` to `arangodb/enterprise:3.12.7.1`
   - Changed port mapping from `27019:27017` to `8529:8529`
   - Added environment variable: `ARANGO_ROOT_PASSWORD=kessler_dev_password`
   - Changed volume from `import-data-from-other-instance-5b0d_mongodb_data:/data/db` to `sattrack_arangodb_data:/var/lib/arangodb3`
   - Updated status messages from "MongoDB" to "ArangoDB"
3. **Lines 103-115**: Updated health check:
   - Replaced `docker exec sattrack mongosh --eval "db.adminCommand('ping')"` with `curl -s -u root:kessler_dev_password http://localhost:8529/_api/version`
   - Health check now uses curl from host machine (ArangoDB container doesn't have curl installed)
   - Authenticates with root credentials to access version endpoint
4. **Line 165**: Updated status output from "MongoDB: localhost:27019" to "ArangoDB: http://localhost:8529"

### Testing Results

- ✅ ArangoDB container starts successfully with `arangodb/enterprise:3.12.7.1` image
- ✅ Port 8529 is properly exposed and accessible
- ✅ Health check successfully verifies ArangoDB is ready using `/_api/version` endpoint
- ✅ Authentication works with configured password `kessler_dev_password`
- ✅ Volume `sattrack_arangodb_data` is created and mounted correctly

### Verification Command

```bash
curl -s -u root:kessler_dev_password http://localhost:8529/_api/version
# Returns: {"server":"arango","license":"enterprise","version":"3.12.7-1"}
```

All changes align with the existing `docker-compose.yml` configuration and the application's ArangoDB requirements in `db.py` and `api.py`.

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

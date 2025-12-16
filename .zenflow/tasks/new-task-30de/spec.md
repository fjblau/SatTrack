# Technical Specification: Docker-based MongoDB Integration

## Task Difficulty: **Medium**

This task involves replacing the locally installed MongoDB instance with a Docker-based setup for improved portability and development environment consistency. The change requires coordinating Docker Compose configuration, connection settings, startup scripts, and documentation updates.

---

## Current State

### MongoDB Integration
- **Connection**: Currently uses locally installed MongoDB at `localhost:27017`
- **Configuration**: Connection URI controlled via environment variable `MONGO_URI` in `db.py:7`
  - Default: `mongodb://localhost:27017`
  - Can be overridden via environment variable
- **Database**: `kessler`
- **Collection**: `satellites`
- **Driver**: pymongo 4.0.0+ (`requirements-mongodb.txt`)

### Project Structure
- **API**: FastAPI backend in `api.py` with MongoDB lifespan management
- **Database Layer**: `db.py` provides MongoDB connection, queries, and document management
- **Startup**: `start.sh` launches API and React dev server (no MongoDB management)
- **Dependencies**: Python 3.11, FastAPI, pymongo
- **Environment**: macOS development environment

### Current Limitations
- Requires local MongoDB installation
- Not portable across development environments
- No standardized MongoDB version control
- Manual MongoDB service management required
- No data persistence guarantees across restarts

---

## Implementation Approach

### 1. Docker Compose Configuration

**Create `docker-compose.yml`** in project root with:
- MongoDB 7.0 service (latest stable)
- Port mapping: `27018:27017` (host:container)
  - **Rationale**: Avoids conflict with local MongoDB on default port 27017
  - Docker MongoDB accessible at `localhost:27018`
- Named volume for data persistence: `mongodb_data`
- Health check to ensure service readiness
- Container name: `kessler-mongodb`
- Restart policy: `unless-stopped` for resilience

**Benefits**:
- Single command to start MongoDB (`docker compose up -d`)
- Version-controlled MongoDB version
- Isolated environment - no port conflicts with local MongoDB
- Automatic data persistence
- Easy cleanup and reset
- Can run both local and Docker MongoDB simultaneously during migration

### 2. Environment Configuration

**Create `.env.example`** template with:
- `MONGO_URI=mongodb://localhost:27018` (default for Docker setup on port 27018)
- Comments explaining purpose and customization options
- Note about port selection to avoid conflicts with local MongoDB

**Update `.gitignore`** to ensure:
- `.env` already ignored (confirmed)
- Add Docker-specific ignores:
  - `docker-compose.override.yml` (for local customization)
  - `mongodb_backup/` (for exported data)

**Connection Strategy**:
- Keep existing `db.py` logic unchanged (already uses `MONGO_URI` env var)
- Docker MongoDB accessible at `localhost:27018` (avoids conflict with local port 27017)
- Create `.env` file with `MONGO_URI=mongodb://localhost:27018` to connect to Docker instance
- No code changes required for connection logic

### 3. Startup Script Enhancement

**Update `start.sh`** to:
1. Check if Docker is installed and running
2. Start MongoDB via Docker Compose before starting API
3. Wait for MongoDB health check (readiness probe)
4. Continue with existing API and React startup flow
5. Handle graceful shutdown (stop Docker containers on Ctrl+C)

**Fallback behavior**:
- If Docker not available, print helpful error message
- Document how to use local MongoDB as alternative

### 4. Data Migration from Local MongoDB

**Export from local installation** (running on port 27017):
```bash
mongodump --uri="mongodb://localhost:27017" --db=kessler --out=./mongodb_backup
```

**Import to Docker MongoDB** (running on port 27018):
```bash
docker compose up -d mongodb
mongorestore --uri="mongodb://localhost:27018" --db=kessler ./mongodb_backup/kessler
```

**Port Strategy**:
- Local MongoDB: `localhost:27017` (unchanged)
- Docker MongoDB: `localhost:27018` (new, no conflicts)
- During migration, both can run simultaneously
- After migration is verified, local MongoDB can be stopped/uninstalled

**Add to `.gitignore`**:
- `mongodb_backup/` (contains exported data snapshots)

### 5. Helper Scripts (Optional but Recommended)

**Create `scripts/mongodb.sh`** for common operations:
- Start MongoDB: `./scripts/mongodb.sh start`
- Stop MongoDB: `./scripts/mongodb.sh stop`
- Reset data: `./scripts/mongodb.sh reset`
- View logs: `./scripts/mongodb.sh logs`
- Shell access: `./scripts/mongodb.sh shell` (connects to port 27018)

**Create `scripts/migrate_data.sh`** (optional):
- Automates export from local MongoDB (port 27017)
- Imports to Docker MongoDB (port 27018)
- Validates successful migration
- Provides rollback instructions

---

## Files to Create/Modify

### New Files
1. **`docker-compose.yml`** - MongoDB service definition
2. **`.env.example`** - Environment variable template
3. **`scripts/mongodb.sh`** (optional) - MongoDB management utilities
4. **`scripts/migrate_data.sh`** (optional) - Data migration automation

### Modified Files
1. **`.gitignore`** - Add Docker-specific entries (`docker-compose.override.yml`, `mongodb_backup/`)
2. **`start.sh`** - Integrate Docker Compose MongoDB startup
3. **`docs/MONGODB_SETUP.md`** - Update installation instructions for Docker and data migration

### Unchanged Files
- `db.py` - Already uses `MONGO_URI` env var, no changes needed
- `api.py` - Connection logic unchanged
- `requirements-mongodb.txt` - Dependencies unchanged

---

## Data Model / API Changes

**No changes required** - This is purely an infrastructure change:
- Database schema remains identical
- API endpoints unchanged
- Connection interface (`db.py`) unchanged
- Only deployment mechanism changes (Docker vs local install)

---

## Verification Approach

### 1. Docker Setup Verification
```bash
# Verify Docker Compose configuration is valid
docker compose config

# Start MongoDB service
docker compose up -d mongodb

# Check MongoDB is running and healthy
docker compose ps
docker compose logs mongodb
```

### 2. Connection Testing
```bash
# Test Docker MongoDB connection from Python
MONGO_URI=mongodb://localhost:27018 python3 -c "from pymongo import MongoClient; import os; MongoClient(os.getenv('MONGO_URI')).admin.command('ping'); print('✓ Connected')"

# Import test data
MONGO_URI=mongodb://localhost:27018 python3 import_to_mongodb.py --clear
```

### 3. API Integration Testing
```bash
# Ensure .env file exists with correct URI
echo "MONGO_URI=mongodb://localhost:27018" > .env

# Start all services (MongoDB + API + React)
./start.sh

# Test health endpoint
curl http://localhost:8000/v2/health

# Test search endpoint
curl http://localhost:8000/v2/search?q=ISS

# Verify API connects to MongoDB successfully
# Check logs show "Connected to MongoDB: kessler.satellites"
```

### 4. Data Migration Testing
```bash
# Export from local MongoDB (port 27017)
mongodump --uri="mongodb://localhost:27017" --db=kessler --out=./mongodb_backup

# Start Docker MongoDB (port 27018)
docker compose up -d mongodb

# Import to Docker MongoDB
mongorestore --uri="mongodb://localhost:27018" --db=kessler ./mongodb_backup/kessler

# Verify data was imported successfully
docker compose exec mongodb mongosh kessler --eval "db.satellites.countDocuments({})"

# Test API with migrated data (ensure .env has MONGO_URI=mongodb://localhost:27018)
echo "MONGO_URI=mongodb://localhost:27018" > .env
curl http://localhost:8000/v2/stats
```

### 5. Data Persistence Testing
```bash
# Import data (or use migrated data from step 4)
MONGO_URI=mongodb://localhost:27018 python3 import_to_mongodb.py --clear

# Stop MongoDB
docker compose down

# Restart MongoDB
docker compose up -d mongodb

# Verify data still exists
curl http://localhost:8000/v2/stats
```

### 6. Cleanup and Reset Testing
```bash
# Full cleanup (including volumes)
docker compose down -v

# Verify data is removed and fresh start works
docker compose up -d mongodb
python3 import_to_mongodb.py --clear
```

---

## Implementation Risks and Considerations

### Low Risk
- Docker Compose is stable and widely used
- MongoDB connection logic already abstracted via env var
- No code changes to database layer required

### Medium Risk
- **Docker availability**: Users must have Docker installed
  - **Mitigation**: Document Docker installation, provide fallback instructions for local MongoDB
  
- **Port conflicts**: Port 27018 might be in use (unlikely but possible)
  - **Mitigation**: Use port 27018 instead of 27017 to avoid conflict with local MongoDB. Document how to customize port via `docker-compose.override.yml`

- **Startup script complexity**: Adding Docker orchestration to shell script
  - **Mitigation**: Keep changes minimal, add clear error messages, test on multiple shells (bash/zsh)
  
- **Environment variable confusion**: Users must remember to create `.env` file
  - **Mitigation**: Provide clear `.env.example` template, document in setup guide, add error message in API if connection fails

### Considerations
- **Performance**: Docker adds minimal overhead for database operations
- **Development workflow**: Developers need Docker Desktop/Engine installed
- **CI/CD**: Future deployment may need Docker Compose or Kubernetes
- **Data migration**: Existing local MongoDB data won't automatically transfer
  - **Solution**: Document export/import process if needed

---

## Success Criteria

1. ✅ MongoDB runs in Docker container via `docker compose up -d`
2. ✅ `start.sh` successfully orchestrates MongoDB, API, and React
3. ✅ Data persists across container restarts
4. ✅ Existing local MongoDB data can be exported and imported to Docker MongoDB
5. ✅ All existing API endpoints work identically
6. ✅ Documentation updated with Docker-based setup and migration instructions
7. ✅ Clean teardown via `docker compose down`
8. ✅ `.env.example` provides clear configuration template
9. ✅ `.gitignore` includes Docker and backup artifacts

---

## Post-Implementation Benefits

- **Portability**: Works on any system with Docker (macOS, Linux, Windows)
- **Consistency**: All developers use same MongoDB version (7.0)
- **Isolation**: MongoDB isolated from host system
- **No port conflicts**: Uses port 27018, allowing local MongoDB to coexist during migration
- **Easy reset**: Quick database reset via `docker compose down -v`
- **Production parity**: Similar to containerized production deployments
- **Onboarding**: New developers need fewer manual installation steps
- **Clean migration path**: Can verify Docker setup before removing local MongoDB installation

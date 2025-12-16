# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: f76a3c27-5dfc-4961-b707-4bcdc5a94e39 -->

✅ **Completed**: Created comprehensive technical specification at `.zenflow/tasks/new-task-30de/spec.md`
- **Difficulty**: Medium
- **Approach**: Docker Compose for MongoDB with minimal code changes
- **Files to create**: `docker-compose.yml`, `.env.example`, optional `scripts/mongodb.sh`
- **Files to modify**: `start.sh`, `.gitignore`, `docs/MONGODB_SETUP.md`
- **Key insight**: No database layer code changes needed (already uses `MONGO_URI` env var)

---

### [ ] Step: Create Docker Compose Configuration

Create `docker-compose.yml` with MongoDB 7.0 service:
- Port mapping: `27017:27017`
- Named volume `mongodb_data` for persistence
- Health check for service readiness
- Container name: `kessler-mongodb`

**Verification**:
```bash
docker compose config
docker compose up -d mongodb
docker compose ps
```

---

### [ ] Step: Create Environment Configuration Template

Create `.env.example` with:
- `MONGO_URI=mongodb://localhost:27017` (default)
- Documentation comments

Update `.gitignore` with Docker-specific entries:
- `docker-compose.override.yml`
- `mongodb_backup/` (for exported data)

**Verification**:
```bash
# Verify .gitignore includes new entries
cat .gitignore | grep docker-compose.override.yml
cat .gitignore | grep mongodb_backup
```

---

### [ ] Step: Update Startup Script

Modify `start.sh` to:
1. Check Docker availability
2. Start MongoDB via Docker Compose
3. Wait for MongoDB health check
4. Continue with existing API/React startup
5. Handle graceful shutdown (stop containers on exit)

**Verification**:
```bash
./start.sh
# Should start MongoDB, API, and React successfully
curl http://localhost:8000/v2/health
```

---

### [ ] Step: Create MongoDB Management Helper Script (Optional)

Create `scripts/mongodb.sh` with commands:
- `start`, `stop`, `reset`, `logs`, `shell`

Make executable: `chmod +x scripts/mongodb.sh`

**Verification**:
```bash
./scripts/mongodb.sh start
./scripts/mongodb.sh logs
./scripts/mongodb.sh shell
```

---

### [ ] Step: Update Documentation

Update `docs/MONGODB_SETUP.md`:
- Replace local MongoDB installation instructions with Docker setup
- Add Docker prerequisites
- Add troubleshooting section for Docker-specific issues
- Document data persistence and volume management
- Add data migration instructions for existing local MongoDB users

**Verification**:
- Review updated documentation for accuracy
- Follow installation steps in a fresh environment if possible

---

### [ ] Step: Import Data from Exported Local MongoDB

Create migration path for existing local MongoDB data:

1. **Document export process** (if not already exported):
   ```bash
   # Export from local MongoDB
   mongodump --uri="mongodb://localhost:27017" --db=kessler --out=./mongodb_backup
   ```

2. **Import to Docker MongoDB**:
   ```bash
   # Ensure Docker MongoDB is running
   docker compose up -d mongodb
   
   # Import the exported data
   mongorestore --uri="mongodb://localhost:27017" --db=kessler ./mongodb_backup/kessler
   ```

3. **Create helper script** `scripts/migrate_data.sh` (optional):
   - Automates export from local and import to Docker
   - Validates data migration
   - Provides rollback instructions

**Verification**:
```bash
# After import, verify data exists
docker compose exec mongodb mongosh kessler --eval "db.satellites.countDocuments({})"

# Test API can access migrated data
curl http://localhost:8000/v2/stats
```

---

### [ ] Step: Integration Testing

Comprehensive testing of the Docker-based setup:
1. Start from clean state: `docker compose down -v`
2. Start all services: `./start.sh`
3. Import test data: `python3 import_to_mongodb.py --clear`
4. Test API endpoints: `/v2/health`, `/v2/search?q=ISS`, `/v2/stats`
5. Verify data persistence: stop and restart MongoDB, check data still exists
6. Test cleanup: `docker compose down -v`

**Verification**:
- All API endpoints return expected results
- Data persists across container restarts
- Clean startup and shutdown work correctly

---

### [ ] Step: Final Report

Write completion report to `.zenflow/tasks/new-task-30de/report.md` with:
- Summary of implementation
- Testing results
- Any issues encountered and solutions
- Usage instructions for developers

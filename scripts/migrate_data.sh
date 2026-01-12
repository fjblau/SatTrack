#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

BACKUP_DIR="./mongodb_backup"
LOCAL_URI="mongodb://localhost:27017"
DOCKER_URI="mongodb://localhost:27019"

echo "=========================================="
echo "MongoDB Data Migration Script"
echo "=========================================="
echo ""
echo "This script migrates data from local MongoDB to Docker MongoDB"
echo "  Source: Local MongoDB ($LOCAL_URI)"
echo "  Target: Docker MongoDB ($DOCKER_URI)"
echo ""

if ! command -v mongodump &> /dev/null || ! command -v mongorestore &> /dev/null; then
    echo "❌ Error: mongodump and mongorestore are required"
    echo "Install MongoDB Database Tools: https://www.mongodb.com/try/download/database-tools"
    exit 1
fi

echo "Step 1: Export data from local MongoDB..."
if mongodump --uri="$LOCAL_URI" --db=kessler --out="$BACKUP_DIR" 2>&1 | grep -q "done dumping"; then
    echo "✅ Export successful"
else
    echo "❌ Export failed. Is local MongoDB running on port 27017?"
    exit 1
fi

echo ""
echo "Step 2: Start Docker MongoDB..."
docker compose up -d mongodb

echo "Waiting for MongoDB to be ready..."
for i in {1..30}; do
    if docker compose exec -T mongodb mongosh --eval "db.adminCommand('ping')" --quiet &> /dev/null; then
        echo "✅ Docker MongoDB is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Docker MongoDB failed to start"
        exit 1
    fi
    sleep 1
done

echo ""
echo "Step 3: Import data to Docker MongoDB..."
if mongorestore --uri="$DOCKER_URI" --db=kessler "$BACKUP_DIR/kessler" 2>&1 | grep -q "done"; then
    echo "✅ Import successful"
else
    echo "❌ Import failed"
    exit 1
fi

echo ""
echo "Step 4: Verify data migration..."
LOCAL_COUNT=$(docker compose exec -T mongodb mongosh kessler --quiet --eval "db.satellites.countDocuments({})" 2>/dev/null | tail -1)
echo "Documents in Docker MongoDB: $LOCAL_COUNT"

if [ "$LOCAL_COUNT" -gt 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Migration completed successfully!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Create .env file: echo 'MONGO_URI=$DOCKER_URI' > .env"
    echo "2. Test the API: curl http://localhost:8000/v2/health"
    echo "3. After verifying, you can stop local MongoDB"
    echo ""
    echo "Backup location: $BACKUP_DIR"
    echo "(You can delete this after verifying the migration)"
else
    echo ""
    echo "⚠️  Warning: No documents found after migration"
    echo "Please check the import logs above"
fi

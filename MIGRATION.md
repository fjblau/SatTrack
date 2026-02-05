# ArangoDB Cloud Migration Guide

**Status**: ✅ Data exported (185,257 documents, 106 MB)

---

## Step 1: Create ArangoDB Oasis Account (Free Tier)

1. Go to https://cloud.arangodb.com
2. Click **"Get Started Free"**
3. Sign up with email or GitHub
4. Verify your email

---

## Step 2: Create Deployment

1. Click **"Create Deployment"**
2. Select **"ArangoGraph Free (Developer)"**
   - 💾 Storage: 4 GB (enough for our ~106 MB)
   - 🌍 Region: Choose closest to Vercel deployment (e.g., US East for iad1)
3. Click **"Create"**
4. Wait 2-3 minutes for deployment to provision
5. **SAVE CREDENTIALS** (shown once):
   - 🔗 Endpoint: `https://xxxxxxxx.arangodb.cloud:8529`
   - 👤 Username: `root`
   - 🔑 Password: `<generated-password>`

---

## Step 3: Create Database

1. Open your deployment → **"Dashboard"**
2. Click **"DATABASES"** tab
3. Click **"+ New Database"**
4. Name: `kessler`
5. Click **"Create"**

---

## Step 4: Import Data

### Option A: Web UI (Slower, but simpler)

For each `.jsonl` file in `arango_export/`:

1. Go to deployment → **"Collections"** tab
2. Create collection with same name (e.g., `satellites`)
   - For edge collections: Check **"Edge Collection"** box:
     - `constellation_membership`
     - `registration_links`
     - `orbital_proximity`
3. Click collection → **"Import"** button
4. Upload corresponding `.jsonl` file
5. Click **"Import"**

**Note**: This might time out for large files like `orbital_proximity.jsonl` (145K docs)

---

### Option B: CLI (Faster, recommended for large files)

Install ArangoDB tools:
```bash
pip install python-arango-backup
```

Or download arangoimport binary:
- https://www.arangodb.com/download/

**Import all collections:**

```bash
cd /Users/frankblau/.zenflow/worktrees/create-mqtt-feed-c9b8

# Set your credentials
export ARANGO_ENDPOINT="https://xxxxxxxx.arangodb.cloud:8529"
export ARANGO_PASSWORD="your-password-here"

# Import each collection
for file in arango_export/*.jsonl; do
  collection=$(basename "$file" .jsonl)
  
  # Determine if edge collection
  if [[ "$collection" =~ (constellation_membership|registration_links|orbital_proximity) ]]; then
    edge_flag="--create-collection-type edge"
  else
    edge_flag="--create-collection-type document"
  fi
  
  echo "Importing $collection..."
  
  arangoimport \
    --server.endpoint "$ARANGO_ENDPOINT" \
    --server.username root \
    --server.password "$ARANGO_PASSWORD" \
    --server.database kessler \
    --collection "$collection" \
    $edge_flag \
    --create-collection true \
    --type jsonl \
    --file "$file" \
    --overwrite true
done
```

**Expected time**: 5-10 minutes for all 185K documents

---

## Step 5: Verify Import

Check document counts in ArangoDB Oasis dashboard:

| Collection | Expected Count |
|------------|----------------|
| satellites | 18,870 |
| constellation_membership | 14,884 |
| registration_links | 5,054 |
| registration_documents | 745 |
| mqtt_configurations | 2 |
| orbital_proximity | 145,702 |
| **TOTAL** | **185,257** |

---

## Step 6: Create Indexes

After import, recreate indexes for performance:

Go to ArangoDB web UI → **"Queries"** → Run these AQL queries:

```aql
// Satellites collection
FOR coll IN ["satellites"]
  LET c = COLLECTION(coll)
  RETURN {
    collection: coll,
    indexes: [
      c.ensureIndex({type: "persistent", fields: ["canonical.international_designator"], unique: false}),
      c.ensureIndex({type: "persistent", fields: ["canonical.registration_number"], unique: false}),
      c.ensureIndex({type: "persistent", fields: ["identifier"], unique: true})
    ]
  }

// MQTT configurations
FOR coll IN ["mqtt_configurations"]
  LET c = COLLECTION(coll)
  RETURN {
    collection: coll,
    indexes: [
      c.ensureIndex({type: "persistent", fields: ["satellite_id"], unique: true}),
      c.ensureIndex({type: "persistent", fields: ["enabled"], unique: false}),
      c.ensureIndex({type: "persistent", fields: ["next_publish"], unique: false})
    ]
  }
```

---

## Step 7: Configure Vercel Environment Variables

Add these to your Vercel project:

### Via Vercel CLI:
```bash
vercel env add ARANGO_HOST production
# Paste: https://xxxxxxxx.arangodb.cloud:8529

vercel env add ARANGO_USER production
# Paste: root

vercel env add ARANGO_PASSWORD production
# Paste: <your-generated-password>

vercel env add VERCEL production
# Paste: 1
```

### Via Vercel Dashboard:
1. Go to https://vercel.com/your-username/sat-track/settings/environment-variables
2. Add each variable for **Production, Preview, Development**:

| Variable | Value | Example |
|----------|-------|---------|
| `ARANGO_HOST` | Your Oasis endpoint | `https://abc123.arangodb.cloud:8529` |
| `ARANGO_USER` | `root` | `root` |
| `ARANGO_PASSWORD` | Your password | `<generated-password>` |
| `VERCEL` | `1` | `1` |

---

## Step 8: Redeploy to Vercel

```bash
cd /Users/frankblau/.zenflow/worktrees/create-mqtt-feed-c9b8
vercel --prod
```

Wait for deployment to complete (~2 minutes)

---

## Step 9: Verify Data on Vercel

Test API endpoints:

```bash
# Check satellite count
curl https://sat-track.vercel.app/v2/search?limit=1

# Should return satellite data (not empty)

# Check specific satellite
curl https://sat-track.vercel.app/v2/search?query=ISS

# Check MQTT configs
curl https://sat-track.vercel.app/v2/mqtt/config/test-satellite-id
```

---

## Troubleshooting

### Import fails with "collection not found"
- Create collection manually first (with correct type: document or edge)

### Vercel shows empty data
- Verify environment variables in Vercel dashboard
- Check Vercel logs: `vercel logs --prod`
- Verify ArangoDB connection allows external access (should be enabled by default in Oasis)

### "Connection refused" errors
- Ensure ARANGO_HOST uses `https://` (not `http://`)
- Verify endpoint includes `:8529` port

---

## Summary

✅ Exported: 185,257 documents  
✅ Collections: 6 (3 document, 3 edge)  
✅ Total size: ~106 MB  
🎯 Target: ArangoDB Oasis Free Tier (4 GB storage)  
⏱️ Migration time: ~15 minutes total

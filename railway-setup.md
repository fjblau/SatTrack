# Deploy ArangoDB to Railway - Step by Step

## Method 1: Railway Dashboard (Easiest - 5 minutes)

### Step 1: Create Project
1. Go to https://railway.app/new
2. Click **"Empty Project"**
3. Name it: `kessler-arangodb`

### Step 2: Add ArangoDB Service
1. Click **"+ New"** → **"Docker Image"**
2. Enter image: `arangodb:3.11`
3. Click **"Deploy"**

### Step 3: Configure Environment Variables
1. Click on the ArangoDB service
2. Go to **"Variables"** tab
3. Add:
   - `ARANGO_ROOT_PASSWORD` = `your-secure-password-here`
   - `ARANGO_NO_AUTH` = `0`

### Step 4: Configure Port
1. Go to **"Settings"** tab
2. Scroll to **"Networking"**
3. Click **"Generate Domain"** (creates public URL)
4. Note the domain: `kessler-arangodb-production.up.railway.app`

### Step 5: Wait for Deployment
- Wait 2-3 minutes for container to start
- Check **"Deployments"** tab for status
- Should show "Active" when ready

### Step 6: Get Connection URL

Your connection string:
```
https://kessler-arangodb-production.up.railway.app:443
```

**Note**: Railway automatically handles HTTPS, so use port 443, not 8529.

---

## Method 2: Railway CLI (Alternative)

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
```

### Step 2: Login
```bash
railway login
```

### Step 3: Create New Project
```bash
railway init
# Enter project name: kessler-arangodb
```

### Step 4: Create Service from Docker Image
```bash
# This won't work directly - Railway CLI doesn't support docker images well
# Use dashboard method instead OR use Dockerfile approach below
```

---

## Method 3: Using Dockerfile (Most Control)

### Step 1: Push Code to GitHub
```bash
cd /Users/frankblau/.zenflow/worktrees/create-mqtt-feed-c9b8

# Add Railway files to git
git add Dockerfile.railway railway.json
git commit -m "Add Railway deployment config"
git push origin create-mqtt-feed-c9b8
```

### Step 2: Connect Railway to GitHub
1. Go to https://railway.app/new
2. Click **"Deploy from GitHub repo"**
3. Select your repository: `fjblau/SatTrack`
4. Select branch: `create-mqtt-feed-c9b8`
5. Railway detects `Dockerfile.railway`

### Step 3: Configure Build
1. In Railway dashboard, go to **"Settings"**
2. Set **"Root Directory"**: `/` (leave blank)
3. Set **"Dockerfile Path"**: `Dockerfile.railway`

### Step 4: Set Environment Variables
```
ARANGO_ROOT_PASSWORD=your-secure-password
```

### Step 5: Deploy
Railway auto-deploys on git push.

---

## After Deployment: Import Data

### Step 1: Create Database
1. Open Railway deployment URL in browser
2. Login with username `root` and your password
3. Create database: `kessler`

### Step 2: Import Data from Local Machine

```bash
cd /Users/frankblau/.zenflow/worktrees/create-mqtt-feed-c9b8

# Get your Railway URL from dashboard
export RAILWAY_ARANGO="https://kessler-arangodb-production.up.railway.app:443"
export RAILWAY_PASSWORD="your-password"

# Import all collections
for file in arango_export/*.jsonl; do
  collection=$(basename "$file" .jsonl)
  
  # Determine collection type
  if [[ "$collection" =~ (constellation_membership|registration_links|orbital_proximity) ]]; then
    edge_flag="--create-collection-type edge"
  else
    edge_flag="--create-collection-type document"
  fi
  
  echo "Importing $collection..."
  
  arangoimport \
    --server.endpoint "$RAILWAY_ARANGO" \
    --server.username root \
    --server.password "$RAILWAY_PASSWORD" \
    --server.database kessler \
    --collection "$collection" \
    $edge_flag \
    --create-collection true \
    --type jsonl \
    --file "$file" \
    --overwrite true
done
```

---

## Configure Vercel to Use Railway Database

```bash
# Set Vercel environment variable
vercel env add ARANGO_HOST production
# Enter: https://kessler-arangodb-production.up.railway.app:443

vercel env add ARANGO_PASSWORD production
# Enter: your-railway-password

# Redeploy
vercel --prod
```

---

## Troubleshooting

### Container fails to start
**Error**: "This image does not have a latest tag"
- **Solution**: Use specific version `arangodb:3.11` (not `arangodb:latest`)

### Can't connect from Vercel
**Error**: Connection refused
- **Solution**: Ensure Railway domain is generated (Settings → Networking → Generate Domain)
- **Solution**: Use port 443 (HTTPS), not 8529

### Import fails
**Error**: Database not found
- **Solution**: Create `kessler` database manually first via ArangoDB web UI

### High memory usage
**Error**: Container crashes due to OOM
- **Solution**: Upgrade Railway plan to get more RAM (free tier may not be enough)
- **Solution**: Check **"Metrics"** tab to see memory usage

---

## Costs

Railway charges based on usage:

**Free Tier**: $5 credit/month
**ArangoDB usage estimate**:
- Memory (512MB): ~$2.50/month
- CPU (light usage): ~$0.50/month
- **Total**: ~$3/month

Your $5 credit covers it, but barely. May need to add payment method if you go over.

---

## Alternative: Use Fly.io Instead (True Free Tier)

If Railway doesn't work or you hit credit limits, see `fly-arangodb-setup.md` for Fly.io deployment (permanent free tier, no credit card).

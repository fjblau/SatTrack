# Deploy ArangoDB to Fly.io (Free Tier)

## Prerequisites
- Fly.io account (free, no credit card needed): https://fly.io/app/sign-up
- flyctl CLI installed

## Step 1: Install flyctl

```bash
# macOS
brew install flyctl

# Or via curl
curl -L https://fly.io/install.sh | sh
```

## Step 2: Login

```bash
flyctl auth login
```

## Step 3: Create Dockerfile

Create `Dockerfile.arangodb` in your project:

```dockerfile
FROM arangodb:3.11

# Set root password via environment variable
ENV ARANGO_ROOT_PASSWORD=kessler_prod_password

# Expose ArangoDB port
EXPOSE 8529
```

## Step 4: Create fly.toml

```toml
app = "kessler-arangodb"

[build]
  dockerfile = "Dockerfile.arangodb"

[env]
  ARANGO_NO_AUTH = "0"

[[services]]
  internal_port = 8529
  protocol = "tcp"

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.tcp_checks]]
    interval = "15s"
    timeout = "2s"
    grace_period = "10s"

[mounts]
  source = "arangodb_data"
  destination = "/var/lib/arangodb3"
```

## Step 5: Create Volume

```bash
flyctl volumes create arangodb_data --size 3 --region iad
# Choose region closest to Vercel deployment
```

## Step 6: Deploy

```bash
flyctl launch --no-deploy
# Answer prompts:
# - Choose app name: kessler-arangodb
# - Choose region: iad (or closest to you)
# - Don't deploy yet

# Set secrets
flyctl secrets set ARANGO_ROOT_PASSWORD=your-secure-password

# Deploy
flyctl deploy
```

## Step 7: Get Connection URL

```bash
flyctl info
# Look for Hostname: kessler-arangodb.fly.dev

# Connection string:
# https://kessler-arangodb.fly.dev:8529
```

## Step 8: Import Data

```bash
# From your local machine, import to Fly.io ArangoDB
cd /Users/frankblau/.zenflow/worktrees/create-mqtt-feed-c9b8

export FLY_ARANGO_HOST="https://kessler-arangodb.fly.dev:8529"
export FLY_ARANGO_PASSWORD="your-secure-password"

for file in arango_export/*.jsonl; do
  collection=$(basename "$file" .jsonl)
  
  if [[ "$collection" =~ (constellation_membership|registration_links|orbital_proximity) ]]; then
    edge_flag="--create-collection-type edge"
  else
    edge_flag="--create-collection-type document"
  fi
  
  echo "Importing $collection..."
  
  arangoimport \
    --server.endpoint "$FLY_ARANGO_HOST" \
    --server.username root \
    --server.password "$FLY_ARANGO_PASSWORD" \
    --server.database kessler \
    --collection "$collection" \
    $edge_flag \
    --create-collection true \
    --type jsonl \
    --file "$file" \
    --overwrite true
done
```

## Step 9: Update Vercel Environment Variables

```bash
vercel env add ARANGO_HOST production
# Enter: https://kessler-arangodb.fly.dev:8529

vercel env add ARANGO_PASSWORD production
# Enter: your-secure-password
```

## Step 10: Redeploy Vercel

```bash
vercel --prod
```

---

## Monitoring

```bash
# View logs
flyctl logs

# Check status
flyctl status

# SSH into container
flyctl ssh console

# Monitor metrics
flyctl dashboard
```

---

## Costs

**Free tier includes**:
- ✅ Up to 3GB volume (our data: 106MB)
- ✅ 256MB RAM (may need to upgrade to 512MB for $2-3/month)
- ✅ Outbound data transfer: 160GB/month

**Estimated cost**: $0-3/month depending on RAM needs

---

## Troubleshooting

### Container keeps restarting
- Check memory limits: `flyctl scale memory 512`
- View logs: `flyctl logs`

### Can't connect from Vercel
- Verify ARANGO_HOST includes `https://` and `:8529`
- Check firewall: Fly.io should allow all outbound by default

### Import fails
- Ensure database `kessler` exists (create via Web UI first)
- Check credentials are correct

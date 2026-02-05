# Quick Deploy to Vercel

## Prerequisites Checklist

- [x] Vercel project "sat-track" created
- [ ] Vercel CLI installed
- [ ] ArangoDB cloud instance (get free at https://cloud.arangodb.com)

## Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

## Step 2: Login to Vercel

```bash
vercel login
```

## Step 3: Deploy

From this directory:

```bash
cd /Users/frankblau/.zenflow/worktrees/create-mqtt-feed-c9b8
vercel
```

When prompted:
- **Set up and deploy?** Yes
- **Which scope?** Select your account
- **Link to existing project?** Yes
- **Project name:** sat-track
- **Overwrite settings?** No

This creates a preview deployment.

## Step 4: Add Environment Variables

Go to https://vercel.com/your-username/sat-track/settings/environment-variables

Add these variables for **Production, Preview, and Development**:

| Variable | Value | Notes |
|----------|-------|-------|
| `ARANGO_HOST` | `https://xxx.arangodb.cloud:8529` | From ArangoDB Oasis |
| `ARANGO_USER` | `root` | Default user |
| `ARANGO_PASSWORD` | Your password | From ArangoDB setup |
| `CORS_ORIGINS` | `https://sat-track.vercel.app` | Your Vercel domain |
| `VERCEL` | `1` | Enables serverless mode |

**Or via CLI:**

```bash
# Add each variable
vercel env add ARANGO_HOST production
# Paste your ArangoDB URL when prompted

vercel env add ARANGO_USER production
# Enter: root

vercel env add ARANGO_PASSWORD production
# Enter your password

vercel env add CORS_ORIGINS production
# Enter: https://sat-track.vercel.app

vercel env add VERCEL production
# Enter: 1

# Pull environment variables locally (optional, for testing)
vercel env pull
```

## Step 5: Deploy to Production

```bash
vercel --prod
```

## Step 6: Verify Deployment

### Check the app is live:

```bash
curl https://sat-track.vercel.app/v2/search?limit=1
```

### Test MQTT configuration endpoint:

```bash
curl https://sat-track.vercel.app/v2/mqtt/config/test
```

Should return 404 (expected if no config exists)

### Test cron endpoint manually:

```bash
curl https://sat-track.vercel.app/api/cron/mqtt-publish
```

## Important Notes

### ArangoDB Setup

1. Sign up at https://cloud.arangodb.com
2. Create a new deployment (Free tier available)
3. Select region closest to your Vercel region
4. Create database named `kessler`
5. Note the connection URL (format: `https://xxx.arangodb.cloud:8529`)
6. **Important:** Set IP whitelist to `0.0.0.0/0` (allow all) since Vercel IPs change

### CORS Configuration

After deployment, update CORS to include all Vercel domains:

```bash
vercel env add CORS_ORIGINS production
# Enter: https://sat-track.vercel.app,https://sat-track-*.vercel.app
```

Redeploy:
```bash
vercel --prod
```

### Cron Jobs

- Cron jobs **only work in production** (not preview deployments)
- Check cron logs: Vercel Dashboard → sat-track → Functions → `/api/cron/mqtt-publish`
- Schedule: Every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)

## Troubleshooting

### Build Fails

**Error:** `npm: command not found` in frontend build

**Fix:** Wait for Vercel to install Node.js environment automatically, or check build logs.

### Database Connection Fails

**Error:** `Failed to connect to ArangoDB`

**Check:**
1. Environment variables are set correctly
2. ArangoDB instance is running
3. IP whitelist includes `0.0.0.0/0`
4. Using HTTPS URL (not HTTP)

### CORS Errors

**Error:** `Access-Control-Allow-Origin` error in browser

**Fix:** Update `CORS_ORIGINS` to include your Vercel domain:

```bash
vercel env rm CORS_ORIGINS production
vercel env add CORS_ORIGINS production
# Enter: https://sat-track.vercel.app,https://sat-track-git-main-yourname.vercel.app
vercel --prod
```

### Function Timeout

**Error:** `Task timed out after 10.00 seconds`

If you have many MQTT configurations, the cron job might timeout.

**Solutions:**
1. Upgrade to Vercel Pro ($20/mo) for 60s timeout
2. Or batch process: split configs into chunks, process 10 at a time

## Monitoring

### View Logs

```bash
vercel logs --follow
```

Or in dashboard:
- https://vercel.com/your-username/sat-track/logs

### Check Cron Job Execution

Dashboard → Deployments → Functions → `/api/cron/mqtt-publish`

Shows execution history and logs.

## Updating After Changes

```bash
# Make code changes locally
# Commit to git (optional)

# Deploy to production
vercel --prod
```

## Rollback

```bash
# List deployments
vercel ls

# Promote a previous deployment
vercel promote [deployment-url]
```

## Cost

**Vercel Hobby (Free):**
- ✅ Unlimited deployments
- ✅ 100 GB-hours serverless functions
- ✅ Unlimited cron jobs (with limits on frequency)
- ✅ Automatic HTTPS

**ArangoDB Oasis Free:**
- ✅ 1 database
- ✅ 4 GB storage
- ✅ Shared instance

**Total: $0/month** 🎉

## Next Steps

1. ✅ Deploy to Vercel
2. ✅ Set up ArangoDB cloud
3. ✅ Configure environment variables
4. ✅ Test frontend at https://sat-track.vercel.app
5. ✅ Verify cron job executes (check after 4 hours)
6. ✅ Configure first MQTT feed via UI
7. ✅ Monitor cron logs for successful publishes

## Support

- Vercel Docs: https://vercel.com/docs
- ArangoDB Docs: https://www.arangodb.com/docs/
- Issues: Check deployment logs in Vercel dashboard

# Vercel Deployment Guide

## ⚠️ Database Migration Required First

**Before deploying to Vercel**, migrate your local ArangoDB data to the cloud.

👉 **See [MIGRATION.md](./MIGRATION.md) for complete migration guide**

**Quick overview**: 
- ✅ Data already exported (185,257 docs, 106 MB in `arango_export/`)
- 📋 Next: Create ArangoDB Oasis account → Import data → Configure Vercel env vars

---

## Prerequisites Checklist

- [x] Vercel project "sat-track" created
- [x] **Data exported** (see `arango_export/`)
- [ ] Vercel CLI installed
- [ ] **ArangoDB Oasis configured** (see [MIGRATION.md](./MIGRATION.md))
- [ ] **Vercel env vars set** (ARANGO_HOST, ARANGO_USER, ARANGO_PASSWORD)

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

⚠️ **CRITICAL**: Configure these before production deployment!

Go to https://vercel.com/your-username/sat-track/settings/environment-variables

Add these variables for **Production, Preview, and Development**:

| Variable | Value | Notes |
|----------|-------|-------|
| `ARANGO_HOST` | `https://xxx.arangodb.cloud:8529` | From ArangoDB Oasis (see [MIGRATION.md](./MIGRATION.md)) |
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

Should return status and results.

---

## Architecture Notes

### Serverless Adaptation

The application automatically detects Vercel serverless environment (`VERCEL=1`) and:

1. **Disables APScheduler** - Background schedulers don't work in serverless
2. **Uses Vercel Cron Jobs** - Configured in `vercel.json` to call `/api/cron/mqtt-publish` every 4 hours
3. **Maintains state in ArangoDB** - All configuration and timestamps stored in cloud database

### MQTT Publishing Schedule

- **Frequency**: Every 4 hours (0, 4, 8, 12, 16, 20 UTC)
- **Mechanism**: Vercel Cron Job → `/api/cron/mqtt-publish` endpoint
- **Configuration**: Individual satellites can still choose 8hr or 24hr frequencies
  - 8hr configs: Publish every time (6 times/day)
  - 24hr configs: Publish only if `next_publish` timestamp is due

### File Structure

```
/
├── api/
│   └── index.py          # Serverless function entry point
├── react-app/
│   └── dist/             # Frontend build output
├── api.py                # FastAPI application
├── vercel.json           # Vercel configuration
└── requirements.txt      # Python dependencies
```

---

## Troubleshooting

### Build Failures

**Issue**: "No Output Directory named 'dist' found"
- **Solution**: Check `vercel.json` has correct `buildCommand` and `outputDirectory`

**Issue**: "Function Runtimes must have a valid version"
- **Solution**: Remove `runtime` specification, let Vercel auto-detect

### Runtime Errors

**Issue**: API returns 500 errors
- **Check Vercel logs**: `vercel logs --prod`
- **Verify env vars**: https://vercel.com/your-username/sat-track/settings/environment-variables
- **Test database connection**: Ensure ArangoDB Oasis allows external connections

**Issue**: No data returned from API
- **Database not migrated**: See [MIGRATION.md](./MIGRATION.md)
- **Wrong ARANGO_HOST**: Verify it matches your Oasis deployment endpoint

### MQTT Issues

**Issue**: Cron job not executing
- **Check cron logs**: Vercel Dashboard → Deployments → Functions
- **Verify cron schedule**: Should see `/api/cron/mqtt-publish` in Functions tab
- **Manual test**: `curl https://sat-track.vercel.app/api/cron/mqtt-publish`

**Issue**: MQTT publish fails
- **Check broker connectivity**: Test from local machine first
- **Verify credentials**: Ensure username/password are correct
- **Check topic permissions**: Some brokers restrict topic patterns

---

## Local Development

To test serverless behavior locally:

```bash
# Set serverless mode
export VERCEL=1

# Start API server (scheduler will be disabled)
python -m uvicorn api:app --host 127.0.0.1 --port 8000

# In another terminal, test cron endpoint
curl http://127.0.0.1:8000/api/cron/mqtt-publish
```

To test with scheduler (normal mode):

```bash
# Unset serverless mode
unset VERCEL

# Start API server (scheduler will run)
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

---

## Performance Considerations

### Cold Starts
- **First request**: 2-5 seconds (function initialization)
- **Subsequent requests**: <1 second (warm function)

### Database Queries
- **Optimize indexes**: Ensure proper indexes exist (see [MIGRATION.md](./MIGRATION.md))
- **Limit result sizes**: Use pagination for large datasets

### Frontend
- **Static assets**: Served via Vercel Edge Network (CDN)
- **API calls**: Proxied through `/api` and `/v2` routes

---

## Monitoring

### Vercel Dashboard
- **Analytics**: Request counts, error rates, response times
- **Logs**: Real-time function logs
- **Cron Jobs**: Execution history and status

### Recommended Monitoring
1. **Set up Vercel notifications** for failed deployments
2. **Monitor MQTT broker** for message delivery
3. **Track ArangoDB Oasis usage** (free tier has limits)

---

## Costs

### Free Tier Limits

**Vercel** (Hobby):
- ✅ Unlimited deployments
- ✅ 100 GB bandwidth/month
- ✅ 100 GB-hours serverless function execution/month
- ✅ Cron jobs included

**ArangoDB Oasis** (Free tier):
- ✅ 4 GB storage (our data: ~106 MB ✅)
- ✅ Single server
- ⚠️ No backups (manual export recommended)

### Estimated Usage
- **API requests**: <1,000/day → Free tier ✅
- **Cron jobs**: 6/day (4-hour interval) → Free tier ✅
- **Storage**: 106 MB → Free tier ✅

---

## Next Steps After Deployment

1. ✅ Verify satellite data loads
2. ✅ Test MQTT configuration flow
3. ✅ Configure at least one satellite for MQTT publishing
4. ✅ Monitor first cron job execution (check logs after 4 hours)
5. ✅ Subscribe to MQTT topic to verify messages
6. 📋 Set up regular database backups (export script)
7. 📋 Configure custom domain (optional)
8. 📋 Set up error alerting (Sentry, etc.)

---

**Deployment Status**: ✅ Configured, ⏳ Pending database migration

See [MIGRATION.md](./MIGRATION.md) to complete the setup.

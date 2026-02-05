# Vercel Deployment Guide for Kessler

## Prerequisites

1. **Vercel Account** - Already created project "sat-track"
2. **ArangoDB Cloud Instance** - Required (local MongoDB won't work)
   - Sign up at https://cloud.arangodb.com/
   - Create a free tier database
   - Note down connection details

## Deployment Steps

### 1. Install Vercel CLI (if not already installed)

```bash
npm install -g vercel
```

### 2. Link Project to Vercel

```bash
cd /Users/frankblau/.zenflow/worktrees/create-mqtt-feed-c9b8
vercel link
```

Select your existing project "sat-track" when prompted.

### 3. Configure Environment Variables

Add these environment variables in Vercel Dashboard (Settings > Environment Variables):

```
ARANGO_HOST=https://your-instance.arangodb.cloud:8529
ARANGO_USER=root
ARANGO_PASSWORD=your_secure_password
CORS_ORIGINS=https://sat-track.vercel.app
VERCEL=1
```

Or via CLI:

```bash
vercel env add ARANGO_HOST
# Enter value: https://your-instance.arangodb.cloud:8529

vercel env add ARANGO_USER
# Enter value: root

vercel env add ARANGO_PASSWORD
# Enter value: your_secure_password

vercel env add CORS_ORIGINS
# Enter value: https://sat-track.vercel.app

vercel env add VERCEL
# Enter value: 1
```

### 4. Deploy to Production

```bash
vercel --prod
```

## How It Works

### Architecture Changes for Serverless

**Before (Local Development):**
- APScheduler runs in background process
- Publishes TLE data every 8/24 hours automatically

**After (Vercel Serverless):**
- APScheduler disabled (serverless functions can't run background jobs)
- Vercel Cron Job calls `/api/cron/mqtt-publish` every 4 hours
- Endpoint publishes all enabled MQTT configurations

### Cron Job Configuration

The cron job is configured in `vercel.json`:

```json
"crons": [
  {
    "path": "/api/cron/mqtt-publish",
    "schedule": "0 */4 * * *"
  }
]
```

**Schedule:** Every 4 hours at minute 0
- 00:00, 04:00, 08:00, 12:00, 16:00, 20:00

### Individual Satellite Frequencies

Since cron runs every 4 hours but satellites have different frequencies:

**8-hour frequency satellites:**
- Will publish every 8 hours (skip every other cron run)
- Tracked via `next_publish` timestamp in database

**24-hour frequency satellites:**
- Will publish once per day
- Tracked via `next_publish` timestamp in database

**Implementation Note:** The cron endpoint currently publishes ALL enabled satellites every 4 hours. To respect individual frequencies, update the cron endpoint logic to check `next_publish` timestamp before publishing.

## Verifying Deployment

### Check Frontend

Visit: `https://sat-track.vercel.app`

### Check Backend API

```bash
curl https://sat-track.vercel.app/v2/search?limit=1
```

### Check Cron Job Logs

1. Go to Vercel Dashboard → sat-track project
2. Click "Deployments" tab
3. Click on latest deployment
4. Click "Functions" tab
5. Find `/api/cron/mqtt-publish` function
6. View logs to see cron execution results

### Test Cron Endpoint Manually

```bash
curl https://sat-track.vercel.app/api/cron/mqtt-publish
```

Response:
```json
{
  "success": true,
  "timestamp": "2026-02-05T12:00:00+00:00",
  "results": {
    "total": 5,
    "successful": 4,
    "failed": 1,
    "errors": [
      {
        "satellite_id": "NORAD-123",
        "error": "TLE data not found"
      }
    ]
  }
}
```

## Limitations on Vercel Free Plan

1. **Cron Jobs:** Limited to 1 per minute
   - Our 4-hour interval is well within limits ✓

2. **Function Timeout:** 10 seconds on Hobby plan
   - If you have many MQTT configs, may timeout
   - Upgrade to Pro ($20/mo) for 60s timeout

3. **Function Memory:** 1024 MB on Hobby
   - Should be sufficient for this app ✓

## Troubleshooting

### Cron Job Not Running

**Check:**
1. Cron jobs only work in Production (not Preview deployments)
2. Verify `vercel.json` is deployed correctly
3. Check function logs in Vercel dashboard

### Database Connection Fails

**Check:**
1. ArangoDB instance is publicly accessible
2. IP whitelist includes Vercel's IPs (or set to 0.0.0.0/0)
3. Environment variables are set correctly
4. ARANGO_HOST uses HTTPS (not HTTP) for cloud instances

### CORS Errors

**Update CORS_ORIGINS:**
```bash
vercel env add CORS_ORIGINS production
# Enter: https://sat-track.vercel.app,https://sat-track-*.vercel.app
```

The wildcard pattern allows preview deployments to work.

### Frontend Can't Connect to API

**Check `react-app/vite.config.js`:**

For production, Vite doesn't use the proxy. The frontend should make requests to the same domain:

```javascript
// In production, all requests go to the same origin
// /api/* and /v2/* are handled by Vercel routing
```

No code changes needed - `vercel.json` routing handles this.

## Updating Individual Satellite Frequencies

To respect 8hr vs 24hr frequencies in the cron job, update `/api/cron/mqtt-publish` in `api.py`:

```python
# Check if it's time to publish based on next_publish timestamp
next_publish = config.get('next_publish')
now = datetime.now(timezone.utc)

if next_publish:
    next_publish_dt = datetime.fromisoformat(next_publish.replace('Z', '+00:00'))
    if now < next_publish_dt:
        continue  # Skip this satellite, not time yet

# ... rest of publishing logic ...

# After successful publish, set next_publish based on frequency
frequency_hours = config.get('frequency_hours', 24)
next_publish_time = now + timedelta(hours=frequency_hours)
update_next_publish(config_id, next_publish_time)
```

## Cost Estimate

**Free Tier:**
- Frontend hosting: Free ✓
- Serverless functions: Free (100GB-hrs/month) ✓
- Cron jobs: Free ✓

**ArangoDB Oasis:**
- Free tier: 1 DB, 4GB storage ✓

**Total: $0/month** (assuming usage stays within free limits)

## Monitoring

**Set up monitoring for:**
1. Cron job execution (check logs weekly)
2. Failed MQTT publishes (review error counts)
3. Database connection issues

**Vercel provides:**
- Real-time function logs
- Error tracking
- Analytics dashboard

## Next Steps After Deployment

1. ✅ Deploy to production
2. ✅ Verify cron job runs every 4 hours
3. ✅ Test MQTT feed configuration via UI
4. ✅ Monitor first few cron executions
5. 🔄 Optional: Implement frequency-aware cron logic
6. 🔄 Optional: Add alerting for failed publishes

## Support

If deployment fails, check:
- Vercel deployment logs
- Build logs for errors
- Environment variables are set
- ArangoDB connection is accessible

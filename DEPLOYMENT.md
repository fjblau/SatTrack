# Kessler Deployment Architecture

## Overview

Kessler uses a **split deployment architecture**:
- **Frontend (React)**: Deployed to **Vercel**
- **Backend (Python/FastAPI)**: Deployed to **Railway**

This architecture solves the serverless function size limit issue on Vercel (250 MB max).

---

## Architecture Diagram

```
User Browser
     |
     v
Vercel (Frontend)
     |
     ├─── Static Files (React app)
     |
     └─── API Proxy (/api/*, /v2/*)
              |
              v
         Railway (Backend)
              |
              ├─── FastAPI Application
              ├─── ArangoDB Connection
              ├─── TLE Data Fetching
              └─── MQTT Publishing
```

---

## Deployment Configuration

### Vercel (Frontend Only)

**What gets deployed:**
- `react-app/` directory (React/Vite application)
- Built static files from `react-app/dist/`

**What is EXCLUDED** (via `.vercelignore`):
- `api/` - Python API modules
- `database/` - Database modules
- `scripts/` - Utility scripts
- `tests/` - Test files
- `*.py` - All Python files
- `requirements.txt` - Python dependencies

**Configuration** (`vercel.json`):
```json
{
  "buildCommand": "cd react-app && npm install && npm run build",
  "outputDirectory": "react-app/dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://web-production-e283.up.railway.app/api/:path*"
    },
    {
      "source": "/v2/:path*",
      "destination": "https://web-production-e283.up.railway.app/v2/:path*"
    }
  ]
}
```

**Key Points:**
- Only builds React frontend
- Proxies all `/api/*` and `/v2/*` requests to Railway
- No Python dependencies installed on Vercel
- No serverless functions created

---

### Railway (Backend)

**What gets deployed:**
- `api/` - FastAPI routers and services
- `database/` - Database connection and operations
- `config.py` - Configuration management
- `mqtt_publisher.py` - MQTT publishing service
- `mqtt_scheduler.py` - MQTT scheduling
- `requirements.txt` - Python dependencies

**Required Environment Variables:**
```bash
# Database
ARANGO_HOST=<arangodb-host>
ARANGO_USER=<username>
ARANGO_PASSWORD=<password>
ARANGO_DB=kessler

# API
CORS_ORIGINS=https://your-vercel-app.vercel.app,http://localhost:3000
API_HOST=0.0.0.0
API_PORT=8000

# Cache
TLE_CACHE_TTL=3600
DOCUMENT_CACHE_TTL=3600
MAX_CACHE_SIZE=1000

# Optional: MQTT
MQTT_BROKER=<broker-url>
MQTT_PORT=1883
```

**Start Command:**
```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

---

## Why This Architecture?

### Problem: Vercel Serverless Function Size Limit
- Vercel serverless functions have a **250 MB unzipped limit**
- Python dependencies exceed this:
  - `pandas`: ~50 MB
  - `numpy`: ~30 MB
  - `python-arango`: ~10 MB
  - Other dependencies: ~20 MB
  - **Total: >110 MB** (plus FastAPI, uvicorn, etc.)

### Solution: Split Deployment
1. **Vercel hosts only the frontend** (static React files)
2. **Railway hosts the full Python backend** (no size limits)
3. **Vercel proxies API requests** to Railway transparently

### Benefits
- ✅ No size limit issues
- ✅ Frontend gets Vercel's global CDN
- ✅ Backend runs on dedicated infrastructure
- ✅ Easy to scale independently
- ✅ No code changes needed (proxy is transparent)

---

## Deployment Steps

### 1. Deploy Backend to Railway

```bash
# From project root
railway up

# Or link to existing project
railway link <project-id>
railway up
```

**Verify:**
- Visit `https://your-railway-app.railway.app/docs`
- Test API endpoint: `https://your-railway-app.railway.app/v2/stats`

### 2. Update Vercel Configuration

Update `vercel.json` with your Railway URL:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-RAILWAY-APP.railway.app/api/:path*"
    },
    {
      "source": "/v2/:path*",
      "destination": "https://YOUR-RAILWAY-APP.railway.app/v2/:path*"
    }
  ]
}
```

### 3. Deploy Frontend to Vercel

```bash
# Option 1: Using Vercel CLI
vercel --prod

# Option 2: Push to GitHub (auto-deploy)
git push origin main
```

**Verify:**
- Visit `https://your-app.vercel.app`
- Open browser DevTools → Network
- Verify API calls go to Railway backend

---

## Local Development

### Backend
```bash
# Start FastAPI server
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend
```bash
# Start Vite dev server
cd react-app
npm run dev
```

**Note:** In development, Vite proxies API requests to `localhost:8000` (configured in `vite.config.js`).

---

## Troubleshooting

### Issue: "Serverless Function exceeded 250 MB"

**Cause:** Vercel is trying to deploy Python backend as serverless function.

**Solution:**
1. Verify `.vercelignore` excludes all Python files:
   ```
   api/
   database/
   scripts/
   tests/
   *.py
   requirements.txt
   ```

2. Verify `vercel.json` has `buildCommand` pointing to React only:
   ```json
   "buildCommand": "cd react-app && npm install && npm run build"
   ```

3. Clear Vercel cache and redeploy:
   ```bash
   vercel --prod --force
   ```

### Issue: API requests fail from frontend

**Cause:** CORS not configured properly.

**Solution:**
1. Update Railway environment variable:
   ```
   CORS_ORIGINS=https://your-app.vercel.app
   ```

2. Restart Railway deployment

### Issue: 404 on API endpoints

**Cause:** Proxy rewrite not working.

**Solution:**
1. Verify `vercel.json` rewrites use correct Railway URL
2. Check Railway app is running: `https://your-app.railway.app/v2/health`
3. Check Vercel deployment logs for proxy errors

---

## Monitoring

### Backend Health Check
```bash
curl https://your-railway-app.railway.app/v2/health
```

Expected response:
```json
{"status": "ok"}
```

### Frontend Check
```bash
curl https://your-app.vercel.app
```

Should return React HTML.

### End-to-End Check
Open frontend in browser:
- Search for satellites
- View satellite details
- Check graph visualizations
- Open DevTools → Network → Verify API calls succeed

---

## Performance

**Expected Response Times:**
- Static assets (Vercel CDN): <50ms
- API endpoints (proxied to Railway): 50-300ms
  - Cached TLE data: ~15ms
  - Database queries: ~30-50ms
  - Graph queries: ~100-250ms

**Scaling:**
- Frontend: Auto-scaled by Vercel CDN
- Backend: Configure Railway replicas as needed

---

## Cost Considerations

### Vercel (Frontend)
- **Pro Plan**: $20/month
  - 100GB bandwidth
  - Unlimited requests
  - Custom domains

### Railway (Backend)
- **Developer Plan**: $5/month + usage
  - 500 hours/month included
  - $0.000463/GB-hour for additional usage
  
**Estimated Monthly Cost:** $25-30 for small to medium traffic

---

## Security

### CORS Configuration
- Railway backend only accepts requests from Vercel domain
- Configured via `CORS_ORIGINS` environment variable

### API Keys
- Store sensitive keys in Railway environment variables
- Never commit to repository
- Use `.env.example` for documentation

### Database Access
- ArangoDB credentials stored in Railway environment
- Not exposed to frontend
- Backend validates all queries

---

## Future Improvements

1. **Add Health Checks**
   - Implement `/v2/health` endpoint
   - Monitor Railway uptime
   - Alert on failures

2. **Caching Layer**
   - Add Redis for distributed caching
   - Cache TLE data across instances
   - Reduce database load

3. **Rate Limiting**
   - Implement rate limiting on Railway
   - Prevent API abuse
   - Configure per-endpoint limits

4. **Monitoring**
   - Add Sentry for error tracking
   - Use Railway metrics dashboard
   - Set up Vercel Analytics

---

## Related Documentation

- [Vercel Configuration Reference](https://vercel.com/docs/configuration)
- [Railway Deployment Guide](https://docs.railway.app/)
- [FastAPI Deployment Best Practices](https://fastapi.tiangolo.com/deployment/)

---

**Last Updated:** February 6, 2026  
**Deployment Architecture Version:** 1.0

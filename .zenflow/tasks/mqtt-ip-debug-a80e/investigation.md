# MQTT IP Address Investigation

## Bug Summary
MQTT connection test was failing in the UI, but the actual issue was a **frontend bug**, not firewall restrictions.

**Root Cause**: Frontend was sending wrong field names to the API:
- Frontend sent: `broker_host`, `broker_port`
- API expected: `host`, `port`

**Deployment Architecture**:
- **Frontend**: React app on Vercel (sat-track-zeta.vercel.app)
- **Backend**: Python FastAPI on Vercel Serverless Functions (same domain)
- **MQTT Connection**: Happens from backend → MQTT broker (172.104.235.199:1883 on Linode)

## Current IP Addresses (Dynamic)
DNS lookup for sat-track-zeta.vercel.app currently returns:
- `64.29.17.131`
- `216.198.79.131`

**⚠️ WARNING**: These IP addresses are **dynamic** and will change. Do not rely on them for long-term firewall configuration.

## Root Cause Analysis
The connection test was failing because the frontend component `MqttConfigModal.jsx` was sending incorrect field names in the API request body.

**Bug location**: `react-app/src/components/MqttConfigModal.jsx:194-199`

The test-connection endpoint expects:
```json
{"host": "...", "port": 1883}
```

But frontend was sending:
```json
{"broker_host": "...", "broker_port": 1883}
```

This caused API validation errors (422 Unprocessable Entity).

**Verification**: Direct API test with correct field names succeeded:
```bash
curl -X POST https://sat-track-zeta.vercel.app/v2/mqtt/test-connection \
  -H "Content-Type: application/json" \
  -d '{"host":"172.104.235.199","port":1883}'
# Response: {"success":true,"message":"Connection successful"}
```

## Affected Components
- `MqttConfigModal.jsx` - Test connection button functionality
- User experience when testing MQTT broker connectivity

## Implemented Solution

**Fixed frontend field names** in `MqttConfigModal.jsx:195-196`:
- Changed `broker_host` → `host`
- Changed `broker_port` → `port`

This aligns with the API's expected request schema.

## Additional Context (IP Allowlisting)

During investigation, we discovered that IP allowlisting was NOT the issue. However, for reference, here are solutions if you need static IPs in the future:

### Option 1: Use Vercel Static IPs (if on Pro/Enterprise)
**Requirements**: Vercel Pro or Enterprise plan

**Steps**:
1. Navigate to Team/Project settings → Connectivity tab
2. Enable Static IPs for the region where your backend is located
3. Vercel will provide a pair of static IP addresses
4. Add those static IPs to your MQTT broker's firewall allowlist

**Pros**:
- Stable, consistent IP addresses
- Applies to Serverless Functions and builds
- Easy to configure

**Cons**:
- Requires Pro or Enterprise plan ($20/month minimum)
- Shared infrastructure (small group of customers)

### Option 2: Use Vercel Secure Compute (Enterprise Only)
**Requirements**: Vercel Enterprise plan

**Benefits**:
- Dedicated VPC with unique IP pair
- Complete network isolation
- VPC Peering support

**Best for**: Organizations with stringent security/compliance requirements

### Option 3: Alternative Architecture (For Free/Hobby Plans)
If upgrading Vercel plan is not an option:

**A. Move MQTT connection to a different host with static IP**:
- Deploy a small proxy service on a VPS (DigitalOcean, AWS EC2, etc.) with a static IP
- Vercel app → Proxy with static IP → MQTT broker
- Allowlist only the proxy's static IP

**B. Use authentication instead of IP allowlisting**:
- Configure MQTT broker to use username/password or certificate-based auth
- Remove IP allowlisting requirement
- More secure and flexible than IP-based restrictions

**C. Move to a different hosting provider**:
- Deploy to a platform with static IP support (AWS, GCP, DigitalOcean)
- Configure static IP for the application
- Update DNS to point to new host

### Option 4: Temporary Solution (Not Recommended)
Add the current dynamic IPs to the allowlist:
- `64.29.17.131`
- `216.198.79.131`

**⚠️ This will break when Vercel rotates IPs**. Only use for immediate testing.

## Recommended Action Plan

### Step 1: Check Vercel Plan
Visit https://vercel.com/account/billing or run:
```bash
vercel whoami
```

### Step 2: Choose Solution Based on Plan

**If Pro/Enterprise Plan ($20+/month)**:
1. Go to Vercel Dashboard → sat-track project → Settings → Connectivity
2. Enable Static IPs for your backend region
3. Copy the static IP addresses provided by Vercel
4. Add those IPs to your MQTT broker's firewall allowlist
5. Test the MQTT connection again from the UI

**If Hobby/Free Plan**:

Choose one of these approaches:

**A. Upgrade to Pro** ($20/month)
- Pros: Clean solution, officially supported
- Cons: Monthly cost

**B. Deploy proxy service with static IP**
1. Deploy a small MQTT proxy on DigitalOcean/AWS/GCP ($5-10/month for VPS)
2. The proxy forwards connections: Vercel → Proxy (static IP) → MQTT broker
3. Allowlist only the proxy's IP on your MQTT broker
4. Update backend to connect to proxy instead of broker directly

**C. Remove IP allowlisting, use authentication**
1. Configure MQTT broker to use username/password or certificate auth
2. Remove IP allowlisting requirement from broker firewall
3. This is more secure and flexible than IP-based restrictions
4. No additional costs

**D. Move to different hosting**
1. Deploy backend to Railway.app, Fly.io, or traditional VPS
2. These platforms offer static IPs without enterprise pricing
3. Keep frontend on Vercel, point API calls to new backend
4. Update CORS and DNS configuration

### Step 3: Test Connection
After implementing your chosen solution:
1. Open MQTT Config modal in the UI
2. Enter broker host and port
3. Click "Test Connection"
4. Verify success message appears

## Edge Cases and Considerations
- **Middleware**: Static IPs do NOT apply to Vercel Edge Middleware (runs on Edge Network)
- **Multiple regions**: If functions run in multiple regions, need static IPs for each region
- **Build traffic**: Ensure Static IPs covers build-time connections if needed
- **Security best practice**: Always combine IP allowlisting with authentication (username/password or certificates)

## Additional Resources
- [Vercel Static IPs Documentation](https://vercel.com/guides/how-to-allowlist-deployment-ip-address)
- [Vercel Pricing](https://vercel.com/pricing)

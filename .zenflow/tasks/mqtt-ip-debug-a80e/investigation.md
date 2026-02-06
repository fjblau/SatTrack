# MQTT IP Address Investigation

## Bug Summary
MQTT message sending is failing due to firewall restrictions on the Broker. The application is hosted on Vercel (sat-track-zeta.vercel.app) and needs to connect to an MQTT broker that requires IP allowlisting.

## Current IP Addresses (Dynamic)
DNS lookup for sat-track-zeta.vercel.app currently returns:
- `64.29.17.131`
- `216.198.79.131`

**⚠️ WARNING**: These IP addresses are **dynamic** and will change. Do not rely on them for long-term firewall configuration.

## Root Cause Analysis
Vercel's default infrastructure uses a **dynamic range of IP addresses** for outbound requests from:
- Builds
- Serverless Functions
- Edge Functions

This makes IP allowlisting unreliable without using Vercel's static IP features.

## Affected Components
- MQTT broker connection from sat-track-zeta.vercel.app
- Any outbound connections from Vercel Serverless Functions
- Firewall configuration on MQTT broker

## Proposed Solutions

### Option 1: Use Vercel Static IPs (Recommended if on Pro/Enterprise)
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

1. **Immediate**: Check your Vercel plan tier (Dashboard → Settings → Billing)
2. **If Pro/Enterprise**: Enable Static IPs (see Option 1)
3. **If Hobby/Free**: 
   - Evaluate cost of upgrading vs. proxy service
   - Consider switching to authentication-based security (Option 3B)
4. **Update firewall**: Add appropriate IP addresses once static IPs are obtained
5. **Test**: Verify MQTT connection works after firewall update

## Edge Cases and Considerations
- **Middleware**: Static IPs do NOT apply to Vercel Edge Middleware (runs on Edge Network)
- **Multiple regions**: If functions run in multiple regions, need static IPs for each region
- **Build traffic**: Ensure Static IPs covers build-time connections if needed
- **Security best practice**: Always combine IP allowlisting with authentication (username/password or certificates)

## Additional Resources
- [Vercel Static IPs Documentation](https://vercel.com/guides/how-to-allowlist-deployment-ip-address)
- [Vercel Pricing](https://vercel.com/pricing)

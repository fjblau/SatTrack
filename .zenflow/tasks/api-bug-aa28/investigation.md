# Bug Investigation: TLE API Connection Errors

## Bug Summary
API endpoint `/v2/tle/{norad_id}` experiences intermittent connection errors when fetching TLE (Two-Line Element) data from external API `tle.ivanstanojevic.me`.

**Error Message:**
```
Error fetching from TLE API: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
```

## Root Cause Analysis

### Location
- **File**: `api.py`
- **Function**: `fetch_tle_by_norad_id` (lines 579-601)
- **Endpoint**: `/v2/tle/{norad_id}` (lines 604-620)

### Problem
The external TLE API (`https://tle.ivanstanojevic.me/api/tle/{norad_id}`) is unreliable and intermittently closes connections without responding. This causes `requests.exceptions.ConnectionError` with the specific error: `RemoteDisconnected('Remote end closed connection without response')`.

### Current Implementation Issues
1. **No retry mechanism**: Single request attempt without retries for transient failures
2. **No connection pooling**: Each request creates a new connection instead of reusing sessions
3. **Generic error handling**: All exceptions caught and logged, but no distinction between transient (retryable) and permanent errors
4. **Silent failure**: Errors are only printed to stdout/logs, endpoint returns 200 OK even on failure

### Affected Components
- **Primary**: `/v2/tle/{norad_id}` endpoint in `api.py:604-620`
- **Secondary**: `import_tle_api.py:22-39` (same external API, same pattern)

## Proposed Solution

### 1. Add Retry Logic with Exponential Backoff
Implement retry mechanism for transient network errors:
- Use `requests` with retry adapter or manual retry loop
- 3 retry attempts with exponential backoff (0.5s, 1s, 2s)
- Only retry on connection errors and 5xx server errors
- Do not retry on 404 (not found) or 400 (bad request)

### 2. Implement Session Reuse
Use a shared `requests.Session` object:
- Connection pooling reduces overhead
- Better handling of keep-alive connections
- Can configure default timeout and retry behavior

### 3. Improve Error Handling
- Distinguish between:
  - **404**: Satellite TLE not available (expected, return None)
  - **Connection errors**: Transient, retry
  - **Timeout errors**: Transient, retry
  - **Other errors**: Log and return None

### 4. Optional: Add Circuit Breaker (Future Enhancement)
If TLE API continues to fail frequently, implement circuit breaker pattern to avoid overwhelming the failing service.

## Implementation Plan

### Changes to `api.py`
1. Create a shared `requests.Session` with retry adapter
2. Update `fetch_tle_by_norad_id` to use session with retry logic
3. Improve error logging to distinguish error types

### Changes to `import_tle_api.py` (Optional)
Apply same fix to maintain consistency, though this is a background import script with less critical timing.

## Edge Cases & Side Effects

### Edge Cases
- TLE API permanently down: Will retry 3 times then return None (current behavior)
- Rate limiting by TLE API: Backoff will help, but may need to add rate limiting detection
- Invalid NORAD IDs: 404 response, no retries needed

### Side Effects
- Increased latency: Retries add ~3.5 seconds worst case (0.5 + 1 + 2 seconds)
- More resilient: Transient failures will be automatically recovered
- Better logging: Clearer error messages for debugging

## Test Strategy
1. **Unit test**: Mock `requests.get` to simulate connection errors and verify retry behavior
2. **Integration test**: Test against actual TLE API (may be flaky)
3. **Manual test**: Verify endpoint still works for valid NORAD IDs after fix

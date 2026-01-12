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
**The TLE API server blocks requests with Python's default User-Agent header.** The external TLE API (`https://tle.ivanstanojevic.me/api/tle/{norad_id}`) closes connections when requests are made without a browser User-Agent, causing `requests.exceptions.ConnectionError` with `RemoteDisconnected('Remote end closed connection without response')`.

**Verification:**
- ✓ curl works (uses curl/X.X User-Agent)
- ✗ `requests.get()` without headers fails
- ✓ `requests.get()` with browser User-Agent works

### Current Implementation Issues
1. **Missing User-Agent header**: Requests use default Python-requests User-Agent which the server blocks
2. **No retry mechanism**: Single request attempt without retries for transient failures
3. **Generic error handling**: All exceptions caught and logged, but no distinction between transient (retryable) and permanent errors

### Affected Components
- **Primary**: `/v2/tle/{norad_id}` endpoint in `api.py:604-620`
- **Secondary**: `import_tle_api.py:22-39` (same external API, same pattern)

## Proposed Solution

### 1. Add User-Agent Header (PRIMARY FIX)
Set a browser User-Agent header in all requests to TLE API:
```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
```

### 2. Add Retry Logic (SECONDARY - DEFENSE IN DEPTH)
Implement retry mechanism for remaining transient failures:
- 2-3 retry attempts with exponential backoff
- Only retry on connection errors and 5xx server errors
- Do not retry on 404 (not found) or 400 (bad request)

### 3. Improve Error Handling
- Distinguish between:
  - **404**: Satellite TLE not available (expected, return None)
  - **Connection errors**: Retry with headers
  - **Other errors**: Log and return None

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

## Implementation Notes

### Changes Made
1. **api.py:579-618**: Updated `fetch_tle_by_norad_id` 
   - Added User-Agent header with browser signature
   - Implemented retry logic with exponential backoff (3 attempts: 0.5s, 1s, 2s)
   - Improved error handling to distinguish connection errors from other errors

2. **import_tle_api.py:22-40**: Updated `fetch_tle_from_api`
   - Added User-Agent header for consistency

### Test Results
✓ Test with NORAD ID 58023 (PRETTY): Success  
✓ Test with NORAD ID 25544 (ISS): Success  
✓ Test with invalid NORAD ID 99999999: Correctly returns None  
✓ No more "Remote end closed connection" errors

# Sentry Integration Troubleshooting

## Quick Test

Run the test script to verify Sentry is working:

```bash
python3 test-sentry.py
```

You should see 4 events in your Sentry dashboard within a few seconds.

## Common Issues

### 1. No Events Appearing

**Check if dependencies are installed:**
```bash
pip3 list | grep sentry
# Should show: sentry-sdk  2.48.0 (or similar)
```

**If not installed:**
```bash
pip3 install -e .
```

### 2. Import Errors

If you see `ModuleNotFoundError: No module named 'sentry_sdk'`:

```bash
# Install in the correct Python environment
cd /Users/visionik/Projects/uptop
pip3 install -e .
```

### 3. Events Sent But Not Visible in Portal

**Enable debug mode to see what's happening:**
```python
from uptop.sentry import init_sentry
init_sentry(debug=True)
```

**Check Sentry dashboard:**
- Go to: https://sentry.io/organizations/YOUR_ORG/projects/
- Select your uptop project
- Check Issues tab
- Verify no filters are applied
- Check the environment dropdown

### 4. AsyncIO Warnings

The warning "There is no running asyncio loop" is expected if Sentry is initialized outside an async context. This won't prevent error capture, but may affect async-specific instrumentation.

**To fix for async code:**
```python
import asyncio
from uptop.sentry import init_sentry

async def main():
    init_sentry()  # Initialize inside async context
    # Your async code here

asyncio.run(main())
```

### 5. Testing Error Capture

**Manually trigger a test error:**
```python
import sentry_sdk
from uptop.sentry import init_sentry

init_sentry()

# This will send an error to Sentry
try:
    1 / 0
except Exception as e:
    sentry_sdk.capture_exception(e)

# Wait for it to be sent
sentry_sdk.flush(timeout=5)
```

## Verification Checklist

- [ ] `sentry-sdk` is installed (`pip3 list | grep sentry`)
- [ ] `uptop --version` runs without errors
- [ ] Test script (`test-sentry.py`) completes successfully
- [ ] Sentry dashboard shows test events
- [ ] DSN in `src/uptop/sentry.py` matches your project
- [ ] No environment filters are hiding events

## Sentry Configuration

Current configuration in `src/uptop/sentry.py`:

```python
SENTRY_DSN = "https://7ecf22e898e00f2a64f4815c09d01e8e@o4510618809270272.ingest.us.sentry.io/4510661135237120"

init_sentry(
    dsn=SENTRY_DSN,
    traces_sample_rate=1.0,          # Capture 100% of transactions
    profile_session_sample_rate=1.0,  # Capture 100% of profiles
    debug=False,                      # Set to True for debugging
)
```

### Log Level Configuration

Sentry automatically adjusts log levels based on environment:

**Development mode** (captures more):
- Breadcrumbs: INFO and above
- Events: **WARNING and above** (includes warnings as separate events)
- Triggers when:
  - `UPTOP_ENV=dev` or `UPTOP_ENV=development`
  - `debug=True` is passed to `init_sentry()`
  - Version is 0.1.x (early development)

**Production mode** (reduces noise):
- Breadcrumbs: INFO and above
- Events: **ERROR and above only** (warnings only appear as breadcrumbs)
- Default when none of the development conditions are met

## Useful Commands

**Check uptop version:**
```bash
uptop --version
```

**Check Python environment:**
```bash
which python3
python3 --version
```

**View Sentry debug output:**
```bash
python3 -c "from uptop.sentry import init_sentry; import sentry_sdk; init_sentry(debug=True); sentry_sdk.capture_message('Test'); sentry_sdk.flush()"
```

**Run in development mode (captures WARNING+ events):**
```bash
UPTOP_ENV=dev uptop
```

**Run in production mode (captures ERROR+ events only):**
```bash
UPTOP_ENV=production uptop
# or just
uptop
```

## Support

If issues persist:
1. Check Sentry dashboard filters and environment settings
2. Verify your DSN is correct
3. Check Sentry project quotas
4. Review Sentry rate limits
5. Check network connectivity to sentry.io

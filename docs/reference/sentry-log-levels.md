# Sentry Log Level Configuration

## Overview

Sentry now automatically adjusts which log messages become events based on your environment.

## Behavior

### Development Mode (v0.1.x or UPTOP_ENV=dev)

**Captures more events for easier debugging:**

| Log Level | Behavior |
|-----------|----------|
| DEBUG | Breadcrumb only |
| INFO | Breadcrumb only |
| **WARNING** | ✅ **Creates Sentry event** |
| **ERROR** | ✅ **Creates Sentry event** |
| **CRITICAL** | ✅ **Creates Sentry event** |

**Triggers when:**
- Version is 0.1.x (early development)
- `UPTOP_ENV=dev` or `UPTOP_ENV=development`
- `debug=True` passed to `init_sentry()`

### Production Mode (v1.0+ or UPTOP_ENV=production)

**Reduces noise, only errors matter:**

| Log Level | Behavior |
|-----------|----------|
| DEBUG | Breadcrumb only |
| INFO | Breadcrumb only |
| WARNING | Breadcrumb only (attached to errors) |
| **ERROR** | ✅ **Creates Sentry event** |
| **CRITICAL** | ✅ **Creates Sentry event** |

**Default when:**
- None of the development conditions are met
- Explicitly set with `UPTOP_ENV=production`

## Usage Examples

### Run in development mode
```bash
# Explicit environment variable
UPTOP_ENV=dev uptop

# Or rely on version detection (0.1.x = dev)
uptop
```

### Run in production mode
```bash
# Explicit
UPTOP_ENV=production uptop

# Or change version to 1.0.0+
```

### Override in code
```python
from uptop.sentry import init_sentry
import logging

# Force WARNING level even in production
init_sentry(event_level=logging.WARNING)

# Force ERROR level even in development
init_sentry(event_level=logging.ERROR)

# Force INFO level (not recommended - very noisy)
init_sentry(event_level=logging.INFO)
```

## What This Means

### During Development (Now)
- You'll see **WARNING** messages as separate events in Sentry
- Easier to catch potential issues during development
- More visibility into what's happening

### In Production (Later)
- Only **ERROR** and **CRITICAL** create events
- Reduces Sentry quota usage
- Focuses on actual problems
- Warnings still visible as breadcrumbs on errors

## Recommendations

### Keep current behavior for now
Since uptop is at v0.1.0, the automatic WARNING level is appropriate. It helps you:
- Catch potential issues early
- See what's happening during development
- Build intuition for what's normal vs. problematic

### When to adjust

**Lower to INFO** (capture everything):
```python
init_sentry(event_level=logging.INFO)
```
- Only during active debugging
- Very noisy, not for regular use

**Raise to ERROR** (production-style):
```python
init_sentry(event_level=logging.ERROR)
```
- When you want to test production behavior
- When WARNING events are too noisy
- When approaching release

## Manual Control

You can always manually send any level as an event:
```python
import sentry_sdk

# Always creates an event, regardless of configured level
sentry_sdk.capture_message("Important info", level="info")
sentry_sdk.capture_message("Important warning", level="warning")
```

## Current Status

✅ **Configured automatically**
- v0.1.0 detected → WARNING level enabled
- Environment-aware switching implemented
- Breadcrumbs always captured (INFO+)
- All automatic, no action needed

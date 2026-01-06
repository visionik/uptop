#!/usr/bin/env python3
"""Test script to verify Sentry integration is working."""

from uptop.sentry import init_sentry, capture_collector_error, add_breadcrumb
import sentry_sdk

def test_basic_message():
    """Test sending a basic message."""
    print("1. Testing basic message capture...")
    event_id = sentry_sdk.capture_message("Test message from uptop", level="info")
    print(f"   ✓ Message sent (event_id: {event_id})")

def test_exception_capture():
    """Test capturing an exception."""
    print("\n2. Testing exception capture...")
    try:
        _ = 1 / 0
    except Exception as e:
        event_id = sentry_sdk.capture_exception(e)
        print(f"   ✓ Exception captured (event_id: {event_id})")

def test_breadcrumbs():
    """Test breadcrumbs functionality."""
    print("\n3. Testing breadcrumbs...")
    add_breadcrumb("User started uptop", category="lifecycle", level="info")
    add_breadcrumb("Loading configuration", category="config", level="debug")
    add_breadcrumb("Initializing plugins", category="plugin", level="debug")
    print("   ✓ Breadcrumbs added")

def test_collector_error():
    """Test collector-specific error capture."""
    print("\n4. Testing collector error capture...")
    try:
        raise ValueError("Test collector error")
    except Exception as e:
        capture_collector_error(
            "test_collector",
            e,
            extra={"test_mode": True, "collector_version": "1.0"}
        )
        print("   ✓ Collector error captured with context")

if __name__ == "__main__":
    print("Initializing Sentry...")
    init_sentry(debug=False)
    print("✓ Sentry initialized\n")
    
    test_basic_message()
    test_exception_capture()
    test_breadcrumbs()
    test_collector_error()
    
    print("\n5. Flushing events to Sentry...")
    sentry_sdk.flush(timeout=10)
    print("   ✓ All events flushed\n")
    
    print("✅ All tests completed!")
    print("\nCheck your Sentry dashboard at:")
    print("https://o4510618809270272.ingest.us.sentry.io/")
    print("\nYou should see 4 events (2 messages, 2 errors)")

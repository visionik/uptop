#!/usr/bin/env python3
"""Test importing and using the Mojo module from Python."""

import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

print("Testing Mojo module import...")
print(f"Python path includes: {repo_root}")

try:
    # Try to import mojo.importer
    print("\n1. Importing mojo.importer...")
    import mojo.importer
    print("   ✓ mojo.importer imported successfully")
    
    # Try to import our Mojo module
    print("\n2. Importing uptop_mojo_module...")
    import uptop_mojo_module
    print("   ✓ uptop_mojo_module imported successfully")
    
    # Test the test_connection function
    print("\n3. Testing connection...")
    result = uptop_mojo_module.test_connection(None)
    print(f"   ✓ test_connection() returned: {result}")
    
    # Test collect_summary
    print("\n4. Testing collect_summary...")
    summary = uptop_mojo_module.collect_summary(None)
    print(f"   ✓ Total processes: {summary['total_count']}")
    print(f"   ✓ Running processes: {summary['running_count']}")
    
    # Test collect_processes (top 10)
    print("\n5. Testing collect_processes(10)...")
    data = uptop_mojo_module.collect_processes(10)
    print(f"   ✓ Collected: {data['total_count']} processes")
    print(f"   ✓ Running: {data['running_count']}")
    print(f"   ✓ Top process: {data['processes'][0]['name']} (PID {data['processes'][0]['pid']})")
    
    print("\n✅ All tests passed!")
    print("Mojo module is working correctly!")
    
except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    print("\nMake sure to compile the Mojo module first:")
    print("  mojo build uptop_mojo_module.mojo")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

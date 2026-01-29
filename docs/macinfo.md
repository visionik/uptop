# Mac System Information Collection

This document describes how mactop collects macOS-specific system information from Apple Silicon Macs, with sufficient detail to reproduce in Python.

## Overview

mactop uses a combination of:
- **IOReport API** - Power metrics, GPU/CPU statistics (no sudo required)
- **IOKit** - Hardware enumeration and device properties
- **Apple SMC** (System Management Controller) - Temperature and power readings
- **IOHIDEventSystemClient** - Fallback temperature sensor access
- **sysctl** - System configuration and CPU information
- **Mach Kernel API** - Per-core CPU usage via `host_processor_info`

## 1. CPU Information

### CPU Brand, Core Counts, and Topology

**Method 1: sysctl**
```python
# Basic CPU info via sysctl command or ctypes
import subprocess

def get_cpu_info():
    result = subprocess.run(['sysctl', 'machdep.cpu'], 
                          capture_output=True, text=True)
    info = {}
    for line in result.stdout.split('\n'):
        if 'machdep.cpu.brand_string' in line:
            info['brand'] = line.split(':')[1].strip()
        if 'machdep.cpu.core_count' in line:
            info['core_count'] = int(line.split(':')[1].strip())
    
    # Get E-core and P-core counts
    result = subprocess.run(['sysctl', 'hw.perflevel0.logicalcpu', 
                           'hw.perflevel1.logicalcpu'],
                          capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'hw.perflevel0.logicalcpu' in line:  # P-cores
            info['p_cores'] = int(line.split(':')[1].strip())
        if 'hw.perflevel1.logicalcpu' in line:  # E-cores
            info['e_cores'] = int(line.split(':')[1].strip())
    
    return info
```

**Method 2: IOKit Core Topology (Authoritative)**

Uses IORegistry to get the actual core type (E vs P) from IOPlatformDevice entries:

```python
# Requires PyObjC or ctypes bindings to IOKit
from Foundation import *
from IOKit import *

def get_core_topology():
    """
    Query IORegistry for CPU cores to determine E-core vs P-core.
    Each core is an IOPlatformDevice with name like "cpu0", "cpu1", etc.
    The 'cluster-type' property is a CFData containing 'E' or 'P'.
    """
    # Match IOPlatformDevice services
    # Iterate through entries with name starting with "cpu"
    # Read "cluster-type" property (CFData with bytes 'E' or 'P')
    # Returns: [(cpu_id, 'E' or 'P'), ...]
    pass
```

### Per-Core CPU Usage

Uses Mach kernel API `host_processor_info`:

```python
import ctypes
from ctypes import *

# Define Mach types
mach_port_t = c_uint
natural_t = c_uint
integer_t = c_int

class processor_cpu_load_info(Structure):
    _fields_ = [
        ("cpu_ticks", c_uint * 4)  # CPU_STATE_USER, SYSTEM, IDLE, NICE
    ]

# Load libc
libc = CDLL("/usr/lib/libc.dylib")

def get_cpu_usage():
    """
    Get per-core CPU usage via host_processor_info.
    Returns array of usage percentages for each logical core.
    """
    host = libc.mach_host_self()
    processor_count = c_uint()
    processor_info = POINTER(integer_t)()
    processor_info_count = c_uint()
    
    # Call host_processor_info with PROCESSOR_CPU_LOAD_INFO flavor (2)
    ret = libc.host_processor_info(
        host, 
        2,  # PROCESSOR_CPU_LOAD_INFO
        byref(processor_count),
        byref(processor_info),
        byref(processor_info_count)
    )
    
    if ret != 0:
        return []
    
    # Parse results - need to track deltas between calls
    # Each core has 4 ticks: USER, SYSTEM, IDLE, NICE
    cores = []
    for i in range(processor_count.value):
        offset = i * 4
        user = processor_info[offset]
        system = processor_info[offset + 1]
        idle = processor_info[offset + 2]
        nice = processor_info[offset + 3]
        cores.append({
            'user': user,
            'system': system,
            'idle': idle,
            'nice': nice
        })
    
    # Must track previous values and compute deltas
    return cores
```

### CPU Frequencies

CPU frequency tables are extracted from IORegistry `pmgr` device properties:
- E-cores: `voltage-states1-sram` property
- P-cores: `voltage-states5-sram` property

These are CFData arrays where each 8-byte entry contains frequency in Hz (first 4 bytes).

## 2. GPU Information

### GPU Core Count

```python
def get_gpu_core_count():
    """
    Query IORegistry AGXAccelerator service for 'gpu-core-count' property.
    Uses IORegistryEntrySearchCFProperty with kIOServicePlane.
    """
    # Match service: "AGXAccelerator"
    # Search recursively for "gpu-core-count" CFNumber property
    pass
```

### GPU Usage and Frequency

Via **IOReport API** - see Power Metrics section below.

## 3. Power Metrics

mactop uses the **IOReport API** which provides power metrics without sudo.

### IOReport C API (Available via IOKit framework + IOReport library)

Key functions (not public API, but linkable with `-lIOReport`):
```c
extern CFDictionaryRef IOReportCopyChannelsInGroup(
    CFStringRef group, CFStringRef subgroup,
    uint64_t a, uint64_t b, uint64_t c);

extern IOReportSubscriptionRef IOReportCreateSubscription(
    void *a, CFMutableDictionaryRef channels,
    CFMutableDictionaryRef *out, uint64_t d, CFTypeRef e);

extern CFDictionaryRef IOReportCreateSamples(
    IOReportSubscriptionRef sub,
    CFMutableDictionaryRef channels,
    CFTypeRef unused);

extern CFDictionaryRef IOReportCreateSamplesDelta(
    CFDictionaryRef a, CFDictionaryRef b, CFTypeRef unused);

extern int64_t IOReportSimpleGetIntegerValue(
    CFDictionaryRef item, int32_t idx);
```

### Python Implementation Approach

```python
# Requires ctypes or PyObjC bindings to IOReport library
from ctypes import *
import objc

# Load IOReport library
ioReport = CDLL('/System/Library/Frameworks/IOKit.framework/Versions/A/Frameworks/IOReport.framework/IOReport')

def sample_power_metrics(duration_ms=500):
    """
    Sample power metrics over duration_ms milliseconds.
    
    Groups to query:
    - "Energy Model": CPU, GPU, ANE, DRAM, GPU SRAM power
    - "GPU Stats": GPU frequency and active time
    - "CPU Stats": E-cluster and P-cluster frequencies and active time
    
    Returns dict with:
    - cpu_power (W)
    - gpu_power (W)
    - ane_power (W) - Neural Engine
    - dram_power (W)
    - gpu_sram_power (W)
    - system_power (W) - from SMC PSTR key
    - gpu_freq_mhz (int)
    - gpu_active_percent (float)
    - e_cluster_active (float)
    - p_cluster_active (float)
    - e_cluster_freq_mhz (int)
    - p_cluster_freq_mhz (int)
    """
    
    # 1. Get channels from groups
    energy_channels = ioReport.IOReportCopyChannelsInGroup(
        "Energy Model", None, 0, 0, 0)
    gpu_channels = ioReport.IOReportCopyChannelsInGroup(
        "GPU Stats", None, 0, 0, 0)
    cpu_channels = ioReport.IOReportCopyChannelsInGroup(
        "CPU Stats", None, 0, 0, 0)
    
    # 2. Merge channels
    # IOReportMergeChannels(energy_channels, gpu_channels, None)
    
    # 3. Create subscription
    subscription = ioReport.IOReportCreateSubscription(
        None, energy_channels, None, 0, None)
    
    # 4. Take two samples with sleep in between
    sample1 = ioReport.IOReportCreateSamples(subscription, energy_channels, None)
    time.sleep(duration_ms / 1000.0)
    sample2 = ioReport.IOReportCreateSamples(subscription, energy_channels, None)
    
    # 5. Compute delta
    delta = ioReport.IOReportCreateSamplesDelta(sample1, sample2, None)
    
    # 6. Parse channels from delta['IOReportChannels'] array
    # For each channel dict:
    #   - IOReportChannelGetGroup(item) -> "Energy Model", "GPU Stats", etc.
    #   - IOReportChannelGetChannelName(item) -> "CPU Energy", "GPU Energy", etc.
    #   - IOReportSimpleGetIntegerValue(item, 0) -> energy value
    #   - IOReportChannelGetUnitLabel(item) -> "mJ", "uJ", "nJ"
    
    # Energy values are in millijoules/microjoules/nanojoules
    # Convert to Watts: (energy / duration_seconds) / scale_factor
    
    # For GPU/CPU Stats groups, use:
    #   - IOReportStateGetCount(item) -> number of frequency states
    #   - IOReportStateGetNameForIndex(item, idx) -> state name (e.g., "V0", "OFF")
    #   - IOReportStateGetResidency(item, idx) -> time in state
    
    return metrics
```

### Practical Consideration for Python

Since IOReport is not officially documented, the most practical approach is:
1. **Use subprocess to call powermetrics** (Apple's official tool):
   ```python
   result = subprocess.run(
       ['powermetrics', '-n', '1', '-i', '1000', '--samplers', 'cpu_power,gpu_power'],
       capture_output=True, text=True)
   # Parse output
   ```

2. **Or use py-applescript to call IOReport indirectly**

3. **Or create a small C/Objective-C extension** that wraps IOReport and exposes to Python

## 4. Temperature Sensors

### Method 1: Apple SMC

SMC provides direct temperature readings via IOKit service "AppleSMC":

```python
def read_smc_temperature():
    """
    Read temperature keys from SMC.
    CPU keys: Tp* (P-core), Te* (E-core)
    GPU keys: Tg*
    
    Keys are 4-character codes, values are float32 type (dataType=1718383648).
    Common keys:
    - "Tp0H": P-core die temperature
    - "Tg0H": GPU die temperature
    """
    # Open IOService "AppleSMC"
    # Use IOConnectCallStructMethod to read keys
    # Key structure: 4-byte key code, 1-byte command, payload
    pass
```

### Method 2: IOHIDEventSystemClient (Fallback)

```python
def read_hid_temperature():
    """
    Fallback temperature source using HID events.
    Match devices with:
    - PrimaryUsagePage: kHIDPage_AppleVendor (0xff00)
    - PrimaryUsage: kHIDUsage_AppleVendor_TemperatureSensor (0x0005)
    
    Events contain temperature readings for:
    - "PMU tdie", "pACC", "eACC" -> CPU temps
    - "GPU" -> GPU temp
    """
    pass
```

### Method 3: Thermal State

System thermal throttling state via NSProcessInfo:
```python
import Foundation
thermal_state = Foundation.NSProcessInfo.processInfo().thermalState()
# 0=Nominal, 1=Fair, 2=Serious, 3=Critical
```

Or via sysctl:
```python
# sysctl machdep.xcpm.cpu_thermal_level
# Returns 0-3
```

## 5. Memory Metrics

### Via Mach VM Statistics

```python
import ctypes

def get_memory_info():
    """
    Use host_statistics64 with HOST_VM_INFO64 flavor.
    Returns vm_statistics64_data_t structure containing:
    - free_count, active_count, inactive_count, wire_count
    - compressor_page_count
    
    Get page size via sysctl hw.pagesize
    Get total memory via sysctl hw.memsize
    """
    libc = ctypes.CDLL("/usr/lib/libc.dylib")
    
    # Call host_statistics64
    # Calculate:
    # - Used = Total - (Free + Inactive)
    # - Available = Free + Inactive
    
    # For swap, use sysctl vm.swapusage
    return {
        'total': total_bytes,
        'used': used_bytes,
        'available': available_bytes,
        'swap_total': swap_total,
        'swap_used': swap_used
    }
```

## 6. Disk I/O

Query IORegistry `AppleAPFSVolume` or `IOBlockStorageDriver` services:

```python
def get_disk_io():
    """
    Match services: "AppleAPFSVolume" (preferred for Apple Silicon)
    Read 'Statistics' dictionary property with keys:
    - "Bytes read from block device"
    - "Bytes written to block device"
    - "Read requests sent to block device"
    - "Write requests sent to block device"
    
    Track values over time and compute deltas for rates.
    """
    pass
```

## 7. Network I/O

Use BSD sockets API `getifaddrs`:

```python
import ctypes
from ctypes import *

class ifaddrs(Structure):
    pass

ifaddrs._fields_ = [
    ("ifa_next", POINTER(ifaddrs)),
    ("ifa_name", c_char_p),
    ("ifa_flags", c_uint),
    ("ifa_addr", c_void_p),
    ("ifa_netmask", c_void_p),
    ("ifa_dstaddr", c_void_p),
    ("ifa_data", c_void_p)
]

def get_network_stats():
    """
    Call getifaddrs and iterate through interfaces.
    For AF_LINK family interfaces, ifa_data points to if_data struct:
    - ifi_ibytes: input bytes
    - ifi_obytes: output bytes
    - ifi_ipackets: input packets
    - ifi_opackets: output packets
    
    Track values and compute deltas for rates.
    """
    libc = CDLL("/usr/lib/libc.dylib")
    ifap = POINTER(ifaddrs)()
    
    if libc.getifaddrs(byref(ifap)) == 0:
        # Iterate through linked list
        # Filter for AF_LINK (18) family
        # Cast ifa_data to if_data structure
        pass
    
    libc.freeifaddrs(ifap)
```

## 8. Thunderbolt Information

Query IORegistry `IOThunderboltSwitch` services:

```python
def get_thunderbolt_info():
    """
    Match service: "IOThunderboltSwitch"
    
    For each switch, read properties:
    - "UID" (uint64): Unique switch identifier
    - "Depth" (int): 0 = host controller, >0 = connected device
    - "Router ID" (int)
    - "Vendor ID" (int)
    - "Device ID" (int)
    - "Vendor Name" (string)
    - "Device Model Name" (string)
    - "Thunderbolt Version" (int): 16=TB3, 32=TB4, 64=TB5
    - "Max Port Number" (int)
    
    Build hierarchy:
    - Depth 0 switches are host ports (buses)
    - Depth >0 switches are connected devices
    - Match devices to ports by finding parent UID
    
    For USB devices connected via TB/USB-C:
    - Query IORegistry "IOUSBHostDevice" services
    - Look for "UsbCPortNumber" property to map to receptacle
    """
    pass
```

### Thunderbolt Network Stats

For Thunderbolt network bridges:
```python
def get_thunderbolt_network():
    """
    Thunderbolt interfaces appear as network interfaces (e.g., en2-en7).
    Use standard network stats collection via getifaddrs.
    Map interface to TB bus using IORegistry hierarchy.
    """
    pass
```

## 9. Per-Process GPU Usage

Query IORegistry `AGXDeviceUserClient` child objects of `AGXAccelerator`:

```python
def get_gpu_process_stats():
    """
    Find service: "AGXAccelerator"
    Get child iterator in kIOServicePlane
    For each child of class "AGXDeviceUserClient":
    
    Properties:
    - "IOUserClientCreator" (string): "pid 123, ProcessName"
    - "AppUsage" (array of dicts): Each dict has "accumulatedGPUTime" (int64, nanoseconds)
    
    Sum all accumulatedGPUTime values for a PID.
    Track deltas over time to compute GPU usage percentage.
    """
    pass
```

## 10. RDMA (Remote Direct Memory Access) Support

For Thunderbolt 5 RDMA:
```python
def check_rdma_support():
    """
    Check if RDMA over Thunderbolt 5 is available.
    Look for IORegistry entries or run 'rdma_ctl status' command.
    """
    result = subprocess.run(['rdma_ctl', 'status'], 
                          capture_output=True, text=True)
    # Parse output
```

## Python Library Recommendations

To access these APIs in Python:

1. **PyObjC** - Provides Objective-C bridge, access to Foundation/IOKit
   ```python
   pip install pyobjc-framework-IOKit
   ```

2. **psutil** - Cross-platform process utilities (CPU, memory, disk, network)
   - Limited Apple Silicon-specific features
   - Good for basic metrics

3. **py-cpuinfo** - CPU information
   - May not detect E/P cores correctly

4. **subprocess + CLI tools**:
   - `powermetrics` - Official Apple power/performance tool
   - `system_profiler` - Hardware info (JSON output with -json flag)
   - `ioreg` - IORegistry browser
   - `sysctl` - Kernel state

## Example: Complete Power Metrics Flow

```python
import subprocess
import json
import time

def get_power_metrics_via_cli():
    """
    Use powermetrics as the most reliable method.
    Requires sudo for full access, but some metrics work without it.
    """
    cmd = [
        'powermetrics',
        '--samplers', 'cpu_power,gpu_power,thermal',
        '-i', '1000',  # 1 second interval
        '-n', '1',     # 1 sample
        '--format', 'plist'
    ]
    
    result = subprocess.run(cmd, capture_output=True)
    # Parse plist output
    # Contains: processor.cpu_power, processor.gpu_power, etc.
    pass

def get_hardware_info_via_profiler():
    """
    Use system_profiler for hardware enumeration.
    """
    cmd = [
        'system_profiler',
        'SPThunderboltDataType',
        'SPStorageDataType',
        'SPDisplaysDataType',
        '-json'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return data
```

## Architecture Notes

### Apple Silicon Specifics

1. **Unified Memory**: GPU and CPU share memory, tracked as single pool
2. **Cluster Architecture**: E-cores and P-cores run at different frequencies
3. **Neural Engine (ANE)**: Separate power domain for ML tasks
4. **Package Power**: Includes CPU + GPU + ANE + DRAM + system overhead
5. **IOReport Groups**:
   - Energy Model: Power consumption data
   - GPU Stats: GPU performance states (GPUPH)
   - CPU Stats: CPU performance states (ECPU/PCPU or CPU0/CPU1)

### Compatibility

- **Minimum macOS**: 12.3+ (Monterey) for full IOReport support
- **Architecture**: ARM64 (Apple Silicon) only
- **Chips tested**: M1, M1 Pro/Max/Ultra, M2, M2 Pro/Max/Ultra, M3, M3 Pro/Max, M4, M4 Pro/Max

## Security Considerations

1. **No sudo required** for IOReport, IOKit, sysctl access
2. **SMC access** works without sudo for read-only operations
3. **Process information** available to all users for their own processes
4. **powermetrics** requires sudo for full feature set

## Implementation Differences: mactop vs uptop

### mactop's Approach (Go + CGO + C/Objective-C)

mactop is implemented as a **monolithic Go application** with extensive CGO bindings to low-level macOS APIs:

#### Architecture
- **Language**: Go with CGO for C/Objective-C interop
- **Direct API Access**: Links directly to private frameworks:
  - `-lIOReport` for power metrics
  - IOKit framework for hardware enumeration
  - CoreFoundation for data structures
  - Custom C/Objective-C code in `.c` and `.m` files
- **No Dependencies**: Self-contained binary with all functionality built-in
- **Single Process**: All metrics collection happens in one process

#### Key Implementation Details

1. **IOReport Integration** (`ioreport.m`):
   - Directly calls undocumented IOReport C functions
   - Manual CFDictionary/CFArray manipulation
   - Two-sample delta approach for power measurements
   - Embedded frequency tables from IORegistry

2. **SMC Access** (`smc.c`):
   - Custom SMC protocol implementation
   - Direct `IOConnectCallStructMethod` calls
   - Manual key enumeration and type parsing
   - Float32 temperature value extraction

3. **Native Statistics** (`native_stats.go` + C inline):
   - Inline C code via CGO comments
   - Direct IORegistry queries with IOKit C API
   - Manual memory management with CF objects
   - Thunderbolt switch tree building from IORegistry

4. **Build Complexity**:
   - Requires CGO (C compiler at build time)
   - Platform-specific compilation flags
   - Frameworks linked at compile time
   - No cross-compilation support

### Recommended uptop Approach (Pure Python)

For uptop, a **pure Python plugin architecture** is recommended:

#### Architecture
- **Language**: Python 3.10+ with optional C extensions
- **Plugin System**: Modular collectors as separate Python modules
- **Hybrid Access**: Combine multiple approaches based on reliability
- **Cross-Platform**: Abstract platform-specific code behind interfaces

#### Implementation Strategy

**Layer 1: PyObjC for Hardware Enumeration (80% of features)**
```python
# Advantages:
# - Direct IOKit access without C compilation
# - Fast and efficient for hardware queries
# - Proper Python objects and memory management
# - Works for most hardware enumeration needs

try:
    from Foundation import NSProcessInfo
    from IOKit import (
        IOServiceMatching, 
        IOServiceGetMatchingService,
        IOServiceGetMatchingServices,
        IORegistryEntryCreateCFProperties,
        IORegistryEntrySearchCFProperty,
        kIOServicePlane
    )
    HAS_PYOBJC = True
except ImportError:
    HAS_PYOBJC = False

class IOKitHardwareCollector:
    """Collect hardware info via PyObjC + IOKit."""
    
    def get_gpu_cores(self) -> int:
        """Get GPU core count from AGXAccelerator."""
        if not HAS_PYOBJC:
            return self._fallback_gpu_cores()
        
        matching = IOServiceMatching("AGXAccelerator")
        service = IOServiceGetMatchingService(0, matching)
        if service:
            cores = IORegistryEntrySearchCFProperty(
                service, kIOServicePlane, "gpu-core-count", None, 3
            )
            return int(cores) if cores else 0
        return 0
    
    def get_thunderbolt_info(self) -> list:
        """Query IOThunderboltSwitch devices."""
        matching = IOServiceMatching("IOThunderboltSwitch")
        iterator = IOServiceGetMatchingServices(0, matching)
        # Iterate and read properties: UID, Depth, Vendor ID, etc.
        return []
    
    def get_thermal_state(self) -> int:
        """Get system thermal state (0-3)."""
        return NSProcessInfo.processInfo().thermalState()
```

**Layer 2: ctypes/psutil for Standard APIs (10% of features)**
```python
# Advantages:
# - Access to Mach kernel APIs without C compilation
# - psutil is cross-platform and well-maintained
# - Efficient for CPU, memory, network, disk stats

import ctypes
from ctypes import c_uint, c_uint64, Structure, byref
import psutil  # Recommended for cross-platform code

class MachAPICollector:
    """Collect system metrics via Mach APIs."""
    
    def __init__(self):
        self.libc = ctypes.CDLL("/usr/lib/libc.dylib")
    
    def get_memory_stats(self) -> dict:
        """Get VM statistics via host_statistics64."""
        # Use psutil for simplicity (recommended)
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'used': mem.used,
            'available': mem.available
        }
    
    def get_per_core_cpu(self) -> list[float]:
        """Get per-core CPU usage."""
        # Use psutil (recommended)
        return psutil.cpu_percent(percpu=True, interval=0.1)
    
    def get_network_io(self) -> dict:
        """Get network I/O stats."""
        return psutil.net_io_counters(pernic=True)
```

**Layer 3: CLI Tools for Private APIs (10% of features)**
```python
# Advantages:
# - Apple-supported, stable APIs
# - JSON/plist output for easy parsing
# - Only option for IOReport power metrics
# - No sudo required for most features

import subprocess
import json
import plistlib

class PowerMetricsCLICollector:
    """Collect power metrics via powermetrics CLI."""
    
    def collect(self) -> dict:
        """Sample power metrics using Apple's powermetrics."""
        result = subprocess.run(
            ['powermetrics', '-n', '1', '-i', '500',
             '--samplers', 'cpu_power,gpu_power,thermal',
             '--format', 'plist'],
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            return plistlib.loads(result.stdout)
        return {}
    
    def get_temperatures(self) -> dict:
        """Get SMC temperatures via powermetrics."""
        result = subprocess.run(
            ['powermetrics', '-n', '1', '-i', '100',
             '--samplers', 'smc', '--format', 'plist'],
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            data = plistlib.loads(result.stdout)
            # Parse SMC data
            return data
        return {}

class SystemProfilerCollector:
    """Collect hardware info via system_profiler."""
    
    def collect(self, *datatypes) -> dict:
        """Query system_profiler with JSON output."""
        result = subprocess.run(
            ['system_profiler'] + list(datatypes) + ['-json'],
            capture_output=True, 
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {}
```

**Layer 4: C Extension (Optional, for Performance)**
```python
# Only implement if profiling shows CLI overhead is problematic
# Build as optional wheel with graceful fallback

try:
    import _macmetrics  # C extension module
    HAS_C_EXTENSION = True
except ImportError:
    HAS_C_EXTENSION = False

class NativeIOReportCollector:
    """Direct IOReport access via C extension."""
    
    def collect(self) -> dict:
        if HAS_C_EXTENSION:
            # C extension links to -lIOReport
            return _macmetrics.sample_power(500)  # ms
        else:
            # Fallback to CLI
            return PowerMetricsCLICollector().collect()
```

#### Plugin Architecture for uptop

```python
# uptop/plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class MetricsCollector(ABC):
    """Base class for all metrics collectors."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique collector name."""
        pass
    
    @property
    def platforms(self) -> list[str]:
        """Supported platforms: ['darwin', 'linux', 'win32']."""
        return ['darwin']  # Default to macOS only
    
    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """Collect metrics, return dict."""
        pass
    
    def is_available(self) -> bool:
        """Check if collector can run on this system."""
        import sys
        return sys.platform in self.platforms

# uptop/plugins/mac/power.py
class MacPowerCollector(MetricsCollector):
    """Power metrics collector with layered fallback."""
    name = "mac.power"
    platforms = ['darwin']
    
    def __init__(self):
        # Check availability in order of preference
        self._has_c_ext = self._check_c_extension()
        self._has_cli = self._check_powermetrics_available()
    
    def collect(self) -> Dict[str, Any]:
        """Collect power metrics using best available method."""
        # Power metrics REQUIRE IOReport - only available via:
        # 1. C extension (optimal)
        # 2. CLI powermetrics (recommended)
        
        if self._has_c_ext:
            return self._collect_via_c_extension()
        elif self._has_cli:
            return self._collect_via_cli()  # Primary recommended method
        else:
            raise RuntimeError(
                "No power collection method available. "
                "IOReport requires powermetrics CLI or C extension."
            )

# uptop/plugins/mac/hardware.py  
class MacHardwareCollector(MetricsCollector):
    """Hardware enumeration via PyObjC."""
    name = "mac.hardware"
    platforms = ['darwin']
    
    def __init__(self):
        try:
            from IOKit import IOServiceMatching
            self._has_pyobjc = True
        except ImportError:
            self._has_pyobjc = False
    
    def collect(self) -> Dict[str, Any]:
        """Collect hardware info using PyObjC + IOKit."""
        if self._has_pyobjc:
            return self._collect_via_iokit()
        else:
            # Fallback to system_profiler CLI
            return self._collect_via_cli()
    
    def _collect_via_iokit(self) -> Dict[str, Any]:
        """Direct IOKit queries via PyObjC."""
        return {
            'gpu_cores': self._get_gpu_cores(),
            'thunderbolt': self._get_thunderbolt_info(),
            'thermal_state': self._get_thermal_state(),
        }

# uptop/plugins/mac/system.py
class MacSystemCollector(MetricsCollector):
    """System metrics via psutil/ctypes."""
    name = "mac.system"
    platforms = ['darwin']
    
    def collect(self) -> Dict[str, Any]:
        """Collect CPU, memory, disk, network stats."""
        import psutil  # Cross-platform, well-maintained
        
        return {
            'cpu': {
                'percent': psutil.cpu_percent(interval=0.1),
                'per_core': psutil.cpu_percent(percpu=True, interval=0.1),
            },
            'memory': self._get_memory(),
            'disk_io': psutil.disk_io_counters(perdisk=True),
            'network_io': psutil.net_io_counters(pernic=True),
        }
```

### Key Differences Summary

| Aspect | mactop (Go) | uptop (Python) |
|--------|-------------|----------------|
| **API Access** | Direct C/ObjC via CGO | PyObjC + subprocess |
| **Build** | Requires C compiler | Pure Python (optional C ext) |
| **Portability** | macOS only | Cross-platform design |
| **Extensibility** | Monolithic | Plugin architecture |
| **Dependencies** | None (statically linked) | Runtime Python packages |
| **Memory Management** | Manual CF retain/release | Automatic (GC + PyObjC) |
| **Error Handling** | C-style error codes | Python exceptions |
| **Testing** | Harder (CGO complexity) | Easier (mocking, fixtures) |
| **Distribution** | Single binary | Python package + wheels |
| **Development** | Requires macOS + Xcode | Any platform (with mocks) |
| **Performance** | Optimal (native code) | Good (Python + native tools) |
| **Maintenance** | Coupled to macOS internals | Abstracted, graceful degradation |

### Recommended Implementation Plan for uptop

Based on the PyObjC feasibility analysis above, implement in this order:

#### Phase 1: PyObjC + psutil Foundation (Week 1-2)
**Goal**: Get 90% of functionality working with pure Python

1. **Hardware Collectors** (PyObjC + IOKit)
   - GPU core count from AGXAccelerator
   - Thunderbolt device enumeration
   - Core topology (E-core/P-core detection)
   - CPU frequency tables from pmgr device
   - Thermal state via NSProcessInfo
   - Per-process GPU usage from AGXDeviceUserClient

2. **System Collectors** (psutil + ctypes)
   - CPU usage (total and per-core) via psutil
   - Memory statistics via psutil
   - Disk I/O via psutil
   - Network I/O via psutil
   - Fallback: ctypes for Mach APIs if psutil insufficient

3. **Plugin Architecture**
   - Base MetricsCollector abstract class
   - Platform detection and graceful degradation
   - Collector registration and discovery
   - Output formatters (JSON, Markdown, table)

**Deliverable**: Core functionality working without any CLI dependencies or C extensions

#### Phase 2: CLI Integration for Power Metrics (Week 3)
**Goal**: Add the 10% of features that require private APIs

1. **Power Metrics Collector** (powermetrics CLI)
   - CPU power consumption
   - GPU power consumption  
   - ANE (Neural Engine) power
   - DRAM power
   - System power
   - GPU frequency and active percentage
   - E-cluster and P-cluster frequencies

2. **Temperature Collector** (powermetrics CLI with SMC sampler)
   - CPU temperatures (E-core and P-core)
   - GPU temperatures
   - Fallback to IOHIDEventSystemClient if needed

3. **System Info Collector** (system_profiler CLI)
   - Detailed hardware profiles
   - Thunderbolt device details
   - Storage configuration
   - Only for features not available via PyObjC

**Deliverable**: Full feature parity with mactop using CLI for power/temp only

#### Phase 3: Optimization and Polish (Week 4)
**Goal**: Improve performance and user experience

1. **Performance Tuning**
   - Profile CLI overhead for power metrics
   - Cache system_profiler data (hardware doesn't change often)
   - Optimize PyObjC queries (reuse services, avoid repeated lookups)
   - Implement intelligent refresh rates per collector

2. **Error Handling and Fallbacks**
   - Graceful degradation when PyObjC not installed → fall back to CLI
   - Handle missing powermetrics (older macOS) → limited functionality
   - Timeout handling for CLI commands
   - User-friendly error messages

3. **Testing**
   - Mock PyObjC IOKit calls for unit tests
   - Mock subprocess calls for CLI collectors
   - Integration tests on real macOS systems
   - Test on multiple macOS versions (12.3+)

**Deliverable**: Production-ready with comprehensive tests

#### Phase 4: Optional C Extension (Only if Needed)
**Goal**: Reduce CLI overhead if profiling shows it's a bottleneck

**Decision Point**: Only proceed if:
- Profiling shows CLI overhead >50ms consistently
- Users need <500ms update intervals
- Willing to maintain C code and build wheels

**Implementation**:
1. Create `_macmetrics` C extension module
2. Link to `-lIOReport` for power metrics
3. Implement SMC protocol for temperatures
4. Build wheels for macOS 12.3+ (ARM64 and x86_64)
5. Maintain CLI fallback for systems without extension

**Trade-offs**:
- ✅ ~10ms overhead instead of ~50ms for power metrics
- ❌ Requires C compiler during development
- ❌ Must distribute pre-built wheels
- ❌ More complex build and maintenance

**Verdict**: Likely unnecessary given 1-second default interval

### Why Python Approach is Better for uptop

1. **Plugin Architecture**: Python's dynamic imports and duck typing make plugins natural
2. **Cross-Platform**: Abstract Mac-specific code, add Linux/Windows collectors later
3. **Testing**: Mock subprocess calls, test on any platform
4. **Maintenance**: Apple's CLI tools are more stable than private IOReport APIs
5. **Development Speed**: No CGO complexity, faster iteration
6. **Distribution**: PyPI packages easier than distributing Go binaries
7. **User Extensions**: Users can write plugins without C/Go knowledge
8. **Graceful Degradation**: Multiple fallback paths if dependencies missing

### Performance Considerations

For a 1-second update interval (uptop's default):
- CLI overhead (10-50ms) is acceptable: 1-5% of interval
- PyObjC overhead (~1-5ms) is negligible
- C extension only needed if targeting <100ms intervals

For uptop's use case (monitoring tool, not profiler), **CLI + PyObjC approach provides best balance** of:
- Reliability (uses official Apple tools)
- Maintainability (less coupling to private APIs)
- Development speed (pure Python)
- Extensibility (plugin architecture)

## PyObjC Feasibility Analysis

### Can All mactop Collectors Be Implemented with PyObjC?

**Short Answer**: Almost all, but with important caveats.

### Detailed Breakdown by Feature

#### ✅ Fully Possible with PyObjC

1. **IOKit Hardware Enumeration**
   - **Status**: ✅ Yes, fully supported
   - **APIs**: `IOServiceMatching`, `IOServiceGetMatchingServices`, `IORegistryEntryCreateCFProperties`
   - **Use Cases**: 
     - GPU core count from AGXAccelerator
     - Thunderbolt switch enumeration
     - USB device listing
     - Storage device information
     - Core topology (E/P-core detection)
   - **Example**:
   ```python
   from IOKit import (
       IOServiceMatching, 
       IOServiceGetMatchingService,
       IORegistryEntrySearchCFProperty,
       kIOServicePlane
   )
   from Foundation import NSNumber
   
   def get_gpu_core_count():
       matching = IOServiceMatching("AGXAccelerator")
       service = IOServiceGetMatchingService(0, matching)
       if service:
           cores = IORegistryEntrySearchCFProperty(
               service, kIOServicePlane, 
               "gpu-core-count", None, 3
           )
           return int(cores) if cores else 0
       return 0
   ```

2. **System Information**
   - **Status**: ✅ Yes, via sysctl wrapper or ctypes
   - **APIs**: Can call sysctl via subprocess or ctypes
   - **Use Cases**:
     - CPU brand string
     - Core counts
     - Memory size
     - Kernel version

3. **Memory Statistics**
   - **Status**: ✅ Yes, via ctypes or PyObjC
   - **APIs**: Can use `ctypes` to call `host_statistics64`
   - **Alternative**: Use `psutil` library (cross-platform)
   - **Example**:
   ```python
   import ctypes
   from ctypes import c_uint, c_uint64, Structure, POINTER, byref
   
   libc = ctypes.CDLL("/usr/lib/libc.dylib")
   
   class vm_statistics64(Structure):
       _fields_ = [
           ("free_count", c_uint),
           ("active_count", c_uint),
           ("inactive_count", c_uint),
           ("wire_count", c_uint),
           ("compressor_page_count", c_uint64),
           # ... other fields
       ]
   
   def get_memory_stats():
       vm_stat = vm_statistics64()
       count = c_uint(16)  # HOST_VM_INFO64_COUNT
       ret = libc.host_statistics64(
           libc.mach_host_self(), 4, byref(vm_stat), byref(count)
       )
       return vm_stat if ret == 0 else None
   ```

4. **Network Statistics**
   - **Status**: ✅ Yes, via ctypes
   - **APIs**: BSD `getifaddrs` accessible via ctypes
   - **Alternative**: Use `psutil.net_io_counters(pernic=True)`

5. **Disk I/O Statistics**
   - **Status**: ✅ Yes, via IOKit PyObjC
   - **APIs**: Query IORegistry for AppleAPFSVolume/IOBlockStorageDriver
   - **Alternative**: Use `psutil.disk_io_counters(perdisk=True)`

6. **Per-Core CPU Usage**
   - **Status**: ✅ Yes, via ctypes
   - **APIs**: `host_processor_info` with `PROCESSOR_CPU_LOAD_INFO`
   - **Alternative**: Use `psutil.cpu_percent(percpu=True)`

7. **Thermal State**
   - **Status**: ✅ Yes, via PyObjC
   - **APIs**: `NSProcessInfo.processInfo().thermalState()`
   - **Example**:
   ```python
   from Foundation import NSProcessInfo
   
   thermal_state = NSProcessInfo.processInfo().thermalState()
   # 0=Nominal, 1=Fair, 2=Serious, 3=Critical
   ```

8. **Per-Process GPU Usage**
   - **Status**: ✅ Yes, with PyObjC + IOKit
   - **APIs**: Query AGXDeviceUserClient children of AGXAccelerator
   - **Complexity**: Medium - need to iterate IORegistry tree

#### ⚠️ Partially Possible (Workarounds Needed)

9. **SMC Temperature Sensors**
   - **Status**: ⚠️ Possible but complex
   - **Challenge**: SMC protocol requires `IOConnectCallStructMethod`
   - **PyObjC Support**: Can call via ctypes bridge, but cumbersome
   - **Better Approach**: 
     - Use CLI: `sudo powermetrics -n 1 --samplers smc` (requires sudo)
     - Or IOHIDEventSystemClient (see below)
   - **Example (ctypes bridge)**:
   ```python
   from IOKit import IOServiceMatching, IOServiceGetMatchingService, IOServiceOpen
   import ctypes
   
   # This is possible but messy - need to define SMC structures
   # and call IOConnectCallStructMethod via ctypes
   iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
   
   def read_smc_key(key: str):
       # Open AppleSMC service
       matching = IOServiceMatching("AppleSMC")
       service = IOServiceGetMatchingService(0, matching)
       
       # Would need to call IOServiceOpen, then IOConnectCallStructMethod
       # This is doable but complex - easier to use CLI or HID fallback
       pass
   ```

10. **IOHIDEventSystemClient (Temperature Fallback)**
    - **Status**: ⚠️ Possible but undocumented
    - **Challenge**: IOHIDEventSystemClient functions not in standard PyObjC
    - **Workaround**: Load symbols dynamically via `ctypes.CDLL`
    - **Example**:
    ```python
    import ctypes
    from Foundation import CFDictionaryCreate, NSNumber
    
    # Load IOKit with RTLD_GLOBAL to access HID functions
    iokit = ctypes.CDLL(
        "/System/Library/Frameworks/IOKit.framework/IOKit",
        ctypes.RTLD_GLOBAL
    )
    
    # Define function signatures
    IOHIDEventSystemClientCreate = iokit.IOHIDEventSystemClientCreate
    IOHIDEventSystemClientCreate.restype = ctypes.c_void_p
    IOHIDEventSystemClientCreate.argtypes = [ctypes.c_void_p]
    
    # Can call, but still requires manual CF object management
    ```

#### ❌ Not Possible with Pure PyObjC (C Extension or CLI Required)

11. **IOReport Power Metrics**
    - **Status**: ❌ Cannot be done with pure PyObjC
    - **Challenge**: IOReport is a **private framework** with no Objective-C interface
    - **Why Not**: 
      - IOReport functions are pure C functions (not ObjC)
      - Not exposed in any public framework headers
      - PyObjC wraps Objective-C, not arbitrary C libraries
      - Functions like `IOReportCopyChannelsInGroup` are not in standard IOKit
    - **Solutions**:
      1. **CLI Tool** (Best): `powermetrics --samplers cpu_power,gpu_power`
      2. **C Extension**: Build Python module that links `-lIOReport`
      3. **ctypes + dlopen**: Load IOReport.framework dynamically
    - **ctypes Workaround** (Advanced):
    ```python
    import ctypes
    from ctypes import c_void_p, c_uint64
    
    # Load IOReport framework dynamically
    try:
        ioreport = ctypes.CDLL(
            "/System/Library/Frameworks/IOKit.framework/"
            "Versions/A/Frameworks/IOReport.framework/IOReport"
        )
        
        # Define function signatures (requires reverse engineering)
        IOReportCopyChannelsInGroup = ioreport.IOReportCopyChannelsInGroup
        IOReportCopyChannelsInGroup.restype = c_void_p  # CFDictionaryRef
        IOReportCopyChannelsInGroup.argtypes = [
            c_void_p,  # CFStringRef group
            c_void_p,  # CFStringRef subgroup
            c_uint64, c_uint64, c_uint64
        ]
        
        # Still need to manage CoreFoundation objects manually
        # This is essentially writing a C extension in Python
        HAS_IOREPORT = True
    except (OSError, AttributeError):
        HAS_IOREPORT = False
    ```
    - **Verdict**: Technically possible via ctypes, but so complex that a C extension or CLI is better

12. **CPU/GPU Frequency Tables from pmgr**
    - **Status**: ✅ Possible with PyObjC (IORegistry access)
    - **APIs**: Read `voltage-states*-sram` properties from pmgr device
    - **Example**:
    ```python
    from IOKit import IOServiceMatching, IOServiceGetMatchingServices
    from Foundation import NSData
    
    def get_gpu_frequencies():
        matching = IOServiceMatching("AppleARMIODevice")
        iterator = IOServiceGetMatchingServices(0, matching)
        
        # Iterate to find "pmgr" device
        # Read "voltage-states9-sram" CFData property
        # Parse 8-byte entries (frequency in Hz in first 4 bytes)
        pass
    ```

### Summary Matrix

| Feature | Pure PyObjC | ctypes Helper | C Extension | CLI Tool | Best Choice |
|---------|-------------|---------------|-------------|----------|-------------|
| IOKit Enumeration | ✅ | - | - | ✅ | PyObjC |
| Memory Stats | ✅ | ✅ | - | ✅ | ctypes/psutil |
| CPU Usage | ✅ | ✅ | - | ✅ | ctypes/psutil |
| Network I/O | ⚠️ | ✅ | - | ✅ | ctypes/psutil |
| Disk I/O | ✅ | - | - | ✅ | PyObjC/psutil |
| Thermal State | ✅ | - | - | ✅ | PyObjC |
| GPU Cores | ✅ | - | - | ✅ | PyObjC |
| Thunderbolt | ✅ | - | - | ✅ | PyObjC |
| SMC Temps | ⚠️ | ⚠️ | ✅ | ✅ | **CLI** |
| IOReport Power | ❌ | ⚠️ | ✅ | ✅ | **CLI** |
| HID Temps | ⚠️ | ⚠️ | ✅ | ✅ | **CLI** |
| CPU/GPU Freq | ✅ | - | - | ❌ | PyObjC |

### Recommended Strategy for uptop

**Layer 1: Pure Python + PyObjC** (90% of features)
```python
# Use for:
# - Hardware enumeration (IOKit)
# - System info (sysctl, NSProcessInfo)
# - Thermal state
# - GPU/CPU topology
```

**Layer 2: ctypes for Standard APIs** (9% of features)
```python
# Use for:
# - Memory statistics (host_statistics64)
# - CPU usage (host_processor_info)
# - Network stats (getifaddrs)
# Or just use psutil library instead
```

**Layer 3: CLI Tools for Complex/Private APIs** (1% of features)
```python
# Use for:
# - Power metrics (powermetrics)
# - SMC temperatures (powermetrics --samplers smc)
# - System profiler data (system_profiler -json)
```

**Optional Layer 4: C Extension for Performance**
```python
# Only if profiling shows CLI overhead is a bottleneck
# Build optional wheel with IOReport bindings
```

### Why This Works Well

1. **PyObjC covers 80-90%** of hardware enumeration needs
2. **ctypes or psutil** handles remaining standard APIs efficiently  
3. **CLI tools** used only for the 2-3 features that truly require it
4. **No C compilation required** for core functionality
5. **Graceful degradation** if PyObjC not installed (fall back to CLI)

### Answer to Your Question

**Can ALL mactop collectors be implemented with PyObjC?**

- **Technically**: 95% yes, 5% no (IOReport power metrics)
- **Practically**: Use PyObjC for 80%, ctypes for 10%, CLI for 10%
- **Recommended**: Hybrid approach is more maintainable than pure PyObjC

The **IOReport power metrics** (CPU/GPU power consumption) is the only major feature that genuinely requires either:
1. CLI (`powermetrics`) - **recommended**
2. C extension with `-lIOReport` - only if CLI overhead is proven problematic
3. Complex ctypes + manual CF management - not worth the maintenance burden

## References

- mactop source: https://github.com/metaspartan/mactop
- Apple IOKit documentation (limited/private APIs)
- Reverse engineering via `ioreg`, `powermetrics` output analysis
- macOS kernel XNU source code (open source): https://github.com/apple-oss-distributions/xnu
- PyObjC documentation: https://pyobjc.readthedocs.io/

"""Uptop Mojo module - Python-importable performance optimizations.

This module exports high-performance functions that can be called directly
from Python using the Mojo import hook or as a compiled shared library.

Usage from Python:
    import mojo.importer
    import uptop_mojo_module
    
    data = uptop_mojo_module.collect_processes(100)
"""

from python import PythonObject
from python.bindings import PythonModuleBuilder
from os import abort


@export
fn PyInit_uptop_mojo_module() -> PythonObject:
    """Initialize the Python module."""
    try:
        var m = PythonModuleBuilder("uptop_mojo_module")
        
        m.def_function[py_collect_top_processes](
            "collect_processes",
            docstring="Collect top N processes by CPU/memory usage. Returns dict with 'processes', 'total_count', 'running_count'."
        )
        
        m.def_function[py_collect_process_summary](
            "collect_summary",
            docstring="Fast process count without details. Returns dict with 'total_count', 'running_count'."
        )
        
        m.def_function[py_test_connection](
            "test_connection",
            docstring="Test if Mojo module is working. Returns True."
        )
        
        return m.finalize()
    except e:
        return abort[PythonObject](String("Error creating uptop Mojo module: ", e))


fn py_test_connection(py_obj: PythonObject) raises -> PythonObject:
    """Test function to verify module is working.
    
    Returns:
        PythonObject: True
    """
    return True


fn py_collect_process_summary(py_obj: PythonObject) raises -> PythonObject:
    """Fast process summary (counts only).
    
    Args:
        py_obj: Ignored parameter (for API compatibility)
    
    Returns:
        PythonObject: Dict with total_count and running_count
    """
    from python import Python
    
    var psutil = Python.import_module("psutil")
    
    var total = 0
    var running = 0
    
    # Just count, don't collect details
    var attrs = Python.list()
    attrs.append("status")
    
    for proc in psutil.process_iter(attrs=attrs):
        try:
            total += 1
            var info = proc.info
            if info is not None:
                var status = info.get("status")
                if status is not None:
                    var status_str = String(status)
                    if status_str == "running":
                        running += 1
        except:
            continue
    
    var result = Python.dict()
    result["total_count"] = total
    result["running_count"] = running
    
    return result


fn py_collect_top_processes(py_max: PythonObject) raises -> PythonObject:
    """Collect top N processes by CPU and memory usage.
    
    Args:
        py_max: PythonObject convertible to Int (max_processes)
    
    Returns:
        PythonObject: Dict with processes, total_count, running_count
    """
    from python import Python
    
    # Convert Python argument to Int
    var max_processes = Int(py_max)
    
    var psutil = Python.import_module("psutil")
    
    # Result list
    var result = Python.list()
    var running_count = 0
    
    # Prime CPU percent collection (first call returns None)
    for proc in psutil.process_iter():
        try:
            _ = proc.cpu_percent(interval=0)
        except:
            pass
    
    # Attributes to collect
    var attrs = Python.list()
    attrs.append("pid")
    attrs.append("name")
    attrs.append("username")
    attrs.append("cpu_percent")
    attrs.append("memory_percent")
    attrs.append("memory_info")
    attrs.append("status")
    attrs.append("create_time")
    attrs.append("cmdline")
    attrs.append("num_threads")
    
    # Collect processes
    for proc in psutil.process_iter(attrs=attrs):
        try:
            var info = proc.info
            if info is None:
                continue
            
            # Quick filter
            var cpu = info.get("cpu_percent")
            if cpu is not None:
                var cpu_val = Float64(cpu)
                if cpu_val < 0.1 and len(result) >= max_processes:
                    continue
            
            # Extract memory info
            var memory_info = info.get("memory_info")
            var rss = 0
            var vms = 0
            if memory_info is not None:
                var rss_attr = memory_info.__getattr__("rss")
                var vms_attr = memory_info.__getattr__("vms")
                if rss_attr is not None:
                    rss = Int(rss_attr)
                if vms_attr is not None:
                    vms = Int(vms_attr)
            
            # Handle cmdline
            var cmdline_raw = info.get("cmdline")
            var cmdline: PythonObject = None
            if cmdline_raw is not None:
                try:
                    var cmdline_len = len(cmdline_raw)
                    if cmdline_len > 0:
                        cmdline = " ".join(cmdline_raw)
                    else:
                        cmdline = None
                except:
                    var builtins = Python.import_module("builtins")
                    cmdline = builtins.str(cmdline_raw)
            
            # Count running
            var status = info.get("status")
            if status is not None:
                var status_str = String(status)
                if status_str == "running":
                    running_count += 1
            
            # Build dict with None handling
            var proc_dict = Python.dict()
            proc_dict["pid"] = info.get("pid", 0)
            proc_dict["name"] = info.get("name", "")
            proc_dict["username"] = info.get("username", "")
            
            var cpu_val = info.get("cpu_percent", 0.0)
            proc_dict["cpu_percent"] = 0.0 if cpu_val is None else cpu_val
            
            var mem_val = info.get("memory_percent", 0.0)
            proc_dict["memory_percent"] = 0.0 if mem_val is None else mem_val
            
            proc_dict["memory_rss_bytes"] = rss
            proc_dict["memory_vms_bytes"] = vms
            proc_dict["status"] = info.get("status", "unknown")
            proc_dict["create_time"] = info.get("create_time", 0.0)
            proc_dict["cmdline"] = cmdline
            
            var threads = info.get("num_threads", 1)
            proc_dict["num_threads"] = 1 if threads is None else threads
            
            result.append(proc_dict)
            
            # Early exit
            if len(result) >= max_processes * 2:
                break
                
        except:
            continue
    
    # Sort by CPU/memory
    var operator = Python.import_module("operator")
    var builtins = Python.import_module("builtins")
    
    var sorted_result = builtins.sorted(
        result,
        key=operator.itemgetter("cpu_percent", "memory_percent"),
        reverse=True
    )
    
    # Take top N
    if len(sorted_result) > max_processes:
        sorted_result = sorted_result[:max_processes]
    
    # Return as dict
    var output = Python.dict()
    output["processes"] = sorted_result
    output["total_count"] = len(sorted_result)
    output["running_count"] = running_count
    
    return output

"""Host-measured hardware offers, never guessed AI/film production capabilities.

A single creative agent can discover real CPU/RAM/disk/GPU claims while the
physical BODY is running. This is a constrained *technical* measurement: the
presence of a display adapter/driver or installed Blender binary does NOT
prove model checkpoint availability, live-action actors, aesthetic quality,
a free cloud provider, or a trained autonomous cinematographer.
"""
from __future__ import annotations

import csv
import math
import os
import shutil
import subprocess
from pathlib import Path


def _linux_memory():
    path=Path("/proc/meminfo")
    if not path.is_file():
        return {"available_bytes":None,"total_bytes":None,
                "measurement":"not_supported_by_current_platform"}
    data={}
    try:
        for line in path.read_text(encoding="ascii").splitlines():
            name,rest=line.split(":",1)
            if name in ("MemAvailable","MemTotal"):
                value,unit=rest.strip().split()
                if unit!="kB":
                    raise ValueError("Unknown host memory unit")
                data[name]=int(value)*1024
    except (OSError,ValueError):
        return {"available_bytes":None,"total_bytes":None,
                "measurement":"memory_probe_failed"}
    return {"available_bytes":data.get("MemAvailable"),
            "total_bytes":data.get("MemTotal"),
            "measurement":"physical_linux_meminfo"}


def _cgroup_effective_limits(cpu,memory,cgroup_root):
    """Respect actual container CPU/memory quotas, not host-wide illusion."""
    root=Path(cgroup_root)
    limited=dict(memory)
    cores=cpu
    try:
        limit_text=(root/"memory.max").read_text(encoding="ascii").strip()
        usage=int((root/"memory.current").read_text(encoding="ascii").strip())
        if limit_text!="max":
            limit=int(limit_text)
            if 0<limit<2**60 and 0<=usage:
                free=max(0,limit-usage)
                current=limited.get("available_bytes")
                total=limited.get("total_bytes")
                limited["available_bytes"]=min(current,free) if type(current) is int else free
                limited["total_bytes"]=min(total,limit) if type(total) is int else limit
                limited["measurement"]=str(limited.get("measurement","unknown"))+"+cgroup_v2_limit"
    except (OSError,ValueError):
        pass
    try:
        quota,period=(root/"cpu.max").read_text(encoding="ascii").split()
        if quota!="max":
            allowed=float(quota)/float(period)
            if math.isfinite(allowed) and allowed>0:
                physical_cores=max(1,math.ceil(allowed))
                cores=min(cores,physical_cores) if type(cores) is int else physical_cores
    except (OSError,ValueError,ZeroDivisionError):
        pass
    return cores,limited


def inspect_host_resources(workspace, *, cpu_count=None,disk_usage=None,
                           memory=None,nvidia_binary=None,gpu_runner=None,
                           cgroup_root=None):
    """Only operator-owned installed runtime is probed; no network/paid API."""
    root=Path(workspace).resolve()
    if not root.is_dir():
        raise ValueError("Resource probe requires existing original working space")
    processor=os.cpu_count() if cpu_count is None else cpu_count
    if type(processor) is not int or processor<=0:
        processor=None
    disk=(disk_usage or shutil.disk_usage)(root)
    if any(type(i) is not int or i<0 for i in (disk.total,disk.used,disk.free)):
        raise ValueError("Host storage report contains invalid values")
    ram=(memory or _linux_memory)()
    if not isinstance(ram,dict):
        raise ValueError("Host memory reporter returned unknown evidence")
    processor,ram=_cgroup_effective_limits(
        processor,ram,cgroup_root or "/sys/fs/cgroup")
    actual_binary=(shutil.which("nvidia-smi") if nvidia_binary is None else nvidia_binary)
    gpu={"driver_query_status":"no_nvidia_driver_executable","devices":[]}
    if actual_binary:
        runner=gpu_runner or subprocess.run
        try:
            response=runner([actual_binary,
                "--query-gpu=index,name,memory.total,memory.free",
                "--format=csv,noheader,nounits"],
                capture_output=True,text=True,timeout=4,check=False)
            if response.returncode!=0:
                raise RuntimeError("No live device query")
            records=[]
            for row in csv.reader(response.stdout.splitlines()):
                if len(row)!=4:
                    raise ValueError("Malformed GPU driver response")
                index,name,total,free=[x.strip() for x in row]
                if not index.isdigit() or not name or len(name)>120:
                    raise ValueError("Untrusted GPU name or ordinal")
                mb_total=int(total);mb_free=int(free)
                if not (0<=mb_free<=mb_total<=1048576):
                    raise ValueError("Invalid measured GPU memory")
                records.append({"index":int(index),"reported_name":name,
                                "total_memory_bytes":mb_total*1024*1024,
                                "reported_free_memory_bytes":mb_free*1024*1024})
            gpu={"driver_query_status":"nvidia_driver_reported_devices",
                 "devices":records}
        except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired):
            gpu={"driver_query_status":"gpu_probe_failed_or_no_access","devices":[]}
    return {
        "measurement":"live_authorized_host_resources",
        "cpu_logical_processors":processor,
        "memory":ram,
        "workspace_disk":{"total_bytes":disk.total,
                          "used_bytes":disk.used,
                          "free_bytes":disk.free},
        "nvidia_gpu_driver":gpu,
        "gpu_device_does_not_prove_cinematic_model_ready":True,
        "paid_or_unlimited_external_compute_assumed":False,
        "resource_probe_never_certifies_artistic_quality":True
    }

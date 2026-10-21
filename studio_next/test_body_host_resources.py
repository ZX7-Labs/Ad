"""No fictitious free GPU or artistic model readiness from a host probe."""
import json
import subprocess
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path

from studio_next.body_host_resources import inspect_host_resources


Disk=namedtuple("Disk","total used free")


class ActualProductionCapacityContracts(unittest.TestCase):
    def test_measured_capacity_discloses_hardware_not_magic_generation(self):
        with tempfile.TemporaryDirectory() as root:
            def runner(argv,**kwargs):
                self.assertEqual(argv[0],"/usr/bin/nvidia-smi")
                self.assertEqual(kwargs["timeout"],4)
                return subprocess.CompletedProcess(argv,0,
                        stdout="0, NVIDIA RTX Test GPU, 16384, 12288\n",stderr="")
            evidence=inspect_host_resources(
                root,cpu_count=12,
                disk_usage=lambda _:Disk(5000000000,2000000000,3000000000),
                memory=lambda:{"available_bytes":3100000000,
                               "total_bytes":8100000000,
                               "measurement":"known-test-physical-memory"},
                nvidia_binary="/usr/bin/nvidia-smi",gpu_runner=runner)
            self.assertEqual(evidence["cpu_logical_processors"],12)
            self.assertEqual(evidence["workspace_disk"]["free_bytes"],3000000000)
            devices=evidence["nvidia_gpu_driver"]["devices"]
            self.assertEqual(devices[0]["reported_free_memory_bytes"],12288*1024*1024)
            self.assertTrue(evidence["gpu_device_does_not_prove_cinematic_model_ready"])
            self.assertFalse(evidence["paid_or_unlimited_external_compute_assumed"])
            self.assertNotIn(root,json.dumps(evidence))

    def test_missing_or_fake_gpu_never_advertises_live_model(self):
        with tempfile.TemporaryDirectory() as root:
            result=inspect_host_resources(root,cpu_count=4,
                disk_usage=lambda _:Disk(1000,100,900),
                memory=lambda:{"available_bytes":None,
                    "total_bytes":None,"measurement":"unknown"},
                nvidia_binary="",
                gpu_runner=lambda *a,**k:self.fail("No driver means no subprocess"))
            self.assertEqual(result["nvidia_gpu_driver"]["devices"],[])
            self.assertEqual(result["nvidia_gpu_driver"]["driver_query_status"],
                             "no_nvidia_driver_executable")
            malformed=inspect_host_resources(root,cpu_count=4,
                disk_usage=lambda _:Disk(1000,100,900),
                memory=lambda:{"available_bytes":None,
                               "total_bytes":None,"measurement":"unknown"},
                nvidia_binary="/usr/bin/nvidia-smi",
                gpu_runner=lambda args,**k:subprocess.CompletedProcess(args,0,
                     stdout="0, Forged GPU, -5000, -1\n",stderr=""))
            self.assertEqual(malformed["nvidia_gpu_driver"]["devices"],[])
            self.assertEqual(malformed["nvidia_gpu_driver"]["driver_query_status"],
                             "gpu_probe_failed_or_no_access")

    def test_container_memory_and_cpu_quota_are_real_render_limits(self):
        with tempfile.TemporaryDirectory() as root:
            r=Path(root)
            limits=r/"cgroup"
            limits.mkdir()
            (limits/"memory.max").write_text(str(2*1024*1024*1024))
            (limits/"memory.current").write_text(str(3*1024*1024*1024//2))
            (limits/"cpu.max").write_text("250000 100000")
            evidence=inspect_host_resources(root,cpu_count=24,
                disk_usage=lambda _:Disk(5000000000,1000000000,4000000000),
                memory=lambda:{"available_bytes":6*1024*1024*1024,
                               "total_bytes":12*1024*1024*1024,
                               "measurement":"test-meminfo"},
                nvidia_binary="",cgroup_root=limits)
            self.assertEqual(evidence["cpu_logical_processors"],3)
            self.assertEqual(evidence["memory"]["available_bytes"],512*1024*1024)
            self.assertEqual(evidence["memory"]["total_bytes"],2*1024*1024*1024)
            self.assertIn("cgroup_v2_limit",evidence["memory"]["measurement"])

    def test_unlimited_or_missing_cgroup_does_not_invent_an_execution_budget(self):
        with tempfile.TemporaryDirectory() as root:
            r=Path(root)
            limits=r/"cgroup"
            limits.mkdir()
            (limits/"memory.max").write_text("max")
            (limits/"memory.current").write_text("200")
            (limits/"cpu.max").write_text("max 100000")
            evidence=inspect_host_resources(root,cpu_count=8,
                disk_usage=lambda _:Disk(1000000000,200000000,800000000),
                memory=lambda:{"available_bytes":900000000,
                               "total_bytes":1000000000,"measurement":"simulated"},
                nvidia_binary="",cgroup_root=limits)
            self.assertEqual(evidence["cpu_logical_processors"],8)
            self.assertEqual(evidence["memory"]["available_bytes"],900000000)

    def test_invalid_storage_measurement_blocks_fake_capacity(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"storage"):
                inspect_host_resources(root,cpu_count=4,
                    disk_usage=lambda _:Disk(10,10,-1),nvidia_binary="")


if __name__=="__main__":unittest.main()

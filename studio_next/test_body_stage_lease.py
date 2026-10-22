"""Real SQLite long-render lease ownership: no duplicate physical render writes."""
from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_stage_lease import RunningStageHeartbeat
from studio_next.durable_graph import DurableFilmGraph, RecoveryBlocked, execute_durable_film_graph
from studio_next.contracts import ToolSpec
from studio_next.registry import ToolCatalog


class PhysicalLongRenderLeaseTests(unittest.TestCase):
    def setup_store(self,root,seconds=.16):
        store=DurableFilmGraph(Path(root)/"production.sqlite3")
        status,_,owner=store.start_or_reuse("film","shot_a","source-fingerprint",
            trusted_idempotent=True,existing_result_verifier=lambda output:True,
            lease_seconds=seconds)
        self.assertEqual(status,"execute")
        return store,owner

    def test_rerun_blocked_after_original_fixed_lease_duration(self):
        with tempfile.TemporaryDirectory() as root:
            store,owner=self.setup_store(root)
            heart=RunningStageHeartbeat(store,"film","shot_a","source-fingerprint",
                owner,lease_seconds=.16)
            heart.start()
            try:
                time.sleep(.4) # original 160ms lease would have expired twice
                with self.assertRaisesRegex(RecoveryBlocked,"active scene lease"):
                    store.start_or_reuse("film","shot_a","source-fingerprint",
                        trusted_idempotent=True,existing_result_verifier=lambda _:True,
                        lease_seconds=.16)
                heart.stop()
                store.complete("film","shot_a","source-fingerprint",owner,
                               {"asset":"genuinely-finished-physical-media"})
                self.assertEqual(store.inspect("film")[0]["status"],"completed")
                self.assertFalse(store.renew_running_lease(
                    "film","shot_a","source-fingerprint",owner,.16))
            finally:
                heart.abort()

    def test_crash_lost_heartbeat_allows_safe_idempotent_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            store,owner=self.setup_store(root,seconds=.13)
            heart=RunningStageHeartbeat(store,"film","shot_a","source-fingerprint",
                owner,lease_seconds=.13)
            heart.start()
            time.sleep(.2)
            heart.stop()
            time.sleep(.18)
            resumed,_,new_owner=store.start_or_reuse(
                "film","shot_a","source-fingerprint",
                trusted_idempotent=True,existing_result_verifier=lambda _:True,
                lease_seconds=.13)
            self.assertEqual(resumed,"execute")
            self.assertNotEqual(new_owner,owner)
            self.assertFalse(store.renew_running_lease("film","shot_a",
                             "source-fingerprint",owner,.13))
            with self.assertRaises(RecoveryBlocked):
                store.complete("film","shot_a","source-fingerprint",owner,
                               {"asset":"stale-unlicensed-old-output"})

    def test_heartbeat_rejects_owner_substitution_before_commit(self):
        with tempfile.TemporaryDirectory() as root:
            store,owner=self.setup_store(root,seconds=.14)
            heart=RunningStageHeartbeat(store,"film","shot_a","source-fingerprint",
                owner,lease_seconds=.14)
            heart.start()
            # Simulate administrative cancellation/replacement: original
            # thread must never take back ownership of a different attempt.
            with store._connect() as db:
                db.execute("UPDATE node_results SET owner='other-worker',lease_until=0")
            time.sleep(.09)
            with self.assertRaisesRegex(RecoveryBlocked,"lost its durable lease"):
                heart.stop()
            self.assertFalse(store.renew_running_lease(
                "film","shot_a","source-fingerprint",owner,.14))

    def test_integration_graph_long_tool_auto_renews_while_original_art_executes(self):
        with tempfile.TemporaryDirectory() as root:
            store=DurableFilmGraph(Path(root)/"production.sqlite3")
            catalog=ToolCatalog()
            started=threading.Event()
            release=threading.Event()
            calls=[]
            def genuinely_working_render(inputs):
                calls.append("original-artwork")
                started.set()
                if not release.wait(4):
                    raise RuntimeError("timed out on original test signal")
                return {"asset":"original-cinema",
                        "sha256":"a"*64,
                        "bytes":12345,
                        "path":"host-specific-physical-render-fixture"}
            catalog.register(ToolSpec("render.art","original picture and sound",
                "Physical externally controlled original picture renderer","write"),
                genuinely_working_render,idempotent=True,implementation_revision="real-v1")
            ir={"project":{"creative_intent":"Arbitrary original camera work"},
                "assets":[],"shots":[{"id":"scene","purpose":"Original cinematic shot",
                                      "duration_seconds":22}],
                "tool_graph":[{"id":"scene_render","tool_id":"render.art",
                    "purpose":"Render actual originally intended footage",
                    "inputs":{"artwork":"artist chooses"},"depends_on":[]}]}
            result=[]
            renewals=[]
            repeated_renewal=threading.Event()
            actual_renew=store.renew_running_lease
            def measure_real_renewal(*args,**kwargs):
                success=actual_renew(*args,**kwargs)
                if success:
                    renewals.append(time.monotonic())
                    if len(renewals)>=5:
                        repeated_renewal.set()
                return success
            thread=threading.Thread(target=lambda:result.append(
                execute_durable_film_graph(ir,catalog,fact_ids=set(),store=store,
                    trusted_idempotent_tools={"render.art"},
                    output_verifier=lambda _id,out:out.get("asset")=="original-cinema",
                    tool_revisions={"render.art":"real-v1"},
                    lease_seconds=.15)),daemon=True)
            with patch.object(store,"renew_running_lease",
                              side_effect=measure_real_renewal):
                thread.start()
                try:
                    self.assertTrue(started.wait(5))
                    self.assertTrue(repeated_renewal.wait(5),
                        "Original renderer never successfully renewed its real SQLite lease")
                    with store._connect() as db:
                        row=db.execute("""SELECT lease_until,owner,node_state
                            FROM node_results WHERE node_id='scene_render'""").fetchone()
                    self.assertEqual(row[2],"running")
                    self.assertTrue(row[1])
                    # Five real successful SQLite renewals during a blocked
                    # physical renderer prove continued custody beyond the
                    # original 150ms lease. A wall-clock 'lease_until > now'
                    # assertion after a scheduled sleep is not deterministic
                    # under preempted/free CI hosts.
                    self.assertEqual(calls,["original-artwork"])
                finally:
                    release.set()
                    thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result[0]["status"],"all_tool_results_verified")
            self.assertEqual(result[0]["completed"],["scene_render"])
            self.assertEqual(calls,["original-artwork"])

    def test_nonfinite_and_model_boolean_lease_budgets_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            store,_=self.setup_store(root)
            for v in (float("nan"),float("inf"),True,0,-1):
                with self.assertRaises(ValueError):
                    store.renew_running_lease("film","shot_a",
                        "source-fingerprint","owner",v)


if __name__=="__main__":
    unittest.main()

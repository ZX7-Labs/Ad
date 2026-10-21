import tempfile
import unittest
from pathlib import Path

from studio_next.durable_graph import DurableFilmGraph,execute_durable_film_graph,RecoveryBlocked
from studio_next.contracts import ToolSpec
from studio_next.registry import ToolCatalog


def film():
    return {"project":{"creative_intent":"One independently directed original movie"},
            "assets":[],"shots":[{"id":"sequence_original","purpose":"Human meaning",
                         "duration_seconds":91.2}],
            "tool_graph":[
                {"id":"create","tool_id":"render.art","purpose":"Artist-defined cinematography",
                 "inputs":{"visual":"The original film's true 3D object"},"depends_on":[]},
                {"id":"finish","tool_id":"edit.encode","purpose":"Actual final montage",
                 "inputs":{"visual":{"$node_output":"create"}},"depends_on":["create"]}]}


def catalog(calls,*,fail_finish=False):
    tools=ToolCatalog()
    def art(x):
        calls.append("art")
        return {"asset":"scene","physical_hash":"verified123"}
    def finish(x):
        calls.append("finish")
        if fail_finish:raise RuntimeError("simulated renderer crash")
        return {"asset":"film","physical_hash":"original-film-verified"}
    tools.register(ToolSpec("render.art","actual 3D film",
                            "Installed artist-designed scene renderer","write"),art)
    tools.register(ToolSpec("edit.encode","actual video edit",
                            "Installed FFmpeg assembler","write"),finish)
    return tools


class DurableFilmExecutionTests(unittest.TestCase):
    def args(self,tmp,catalog_):
        return dict(ir=film(),catalog=catalog_,fact_ids=set(),
            store=DurableFilmGraph(Path(tmp)/"production.sqlite3"),
            output_verifier=lambda tid,value:bool(value.get("physical_hash")),
            trusted_idempotent_tools={"render.art","edit.encode"},
            tool_revisions={"render.art":"sha-source-render-v1",
                            "edit.encode":"sha-source-timeline-v1"})

    def test_resume_original_art_from_actual_committed_stage(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            args=self.args(root,catalog(calls,fail_finish=True))
            a=execute_durable_film_graph(**args)
            self.assertEqual(a["status"],"failed_partial")
            self.assertEqual(a["completed"],["create"])
            self.assertEqual(calls,["art","finish"])
            b=execute_durable_film_graph(**self.args(root,catalog(calls)))
            self.assertEqual(b["status"],"all_tool_results_verified")
            self.assertEqual(b["reused"],["create"])
            self.assertEqual(calls,["art","finish","finish"])
            self.assertFalse(b["video_proven"])

    def test_changed_director_story_never_uses_old_results(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            args=self.args(root,catalog(calls))
            self.assertEqual(execute_durable_film_graph(**args)["status"],
                             "all_tool_results_verified")
            different=film()
            different["shots"][0]["duration_seconds"]=192.5
            changed=self.args(root,catalog(calls))
            changed["ir"]=different
            self.assertEqual(execute_durable_film_graph(**changed)["reused"],[])
            self.assertEqual(calls,["art","finish","art","finish"])

    def test_missing_rights_and_paid_access_block_before_side_effects(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            task=film()
            task["shots"][0]["fact_refs"]=["invented endorsement"]
            args=self.args(root,catalog(calls))
            args["ir"]=task
            self.assertEqual(execute_durable_film_graph(**args)["status"],"blocked")
            self.assertEqual(calls,[])
            args=self.args(root,catalog(calls))
            args["step_budget"]=1
            self.assertEqual(execute_durable_film_graph(**args)["status"],"blocked")
            self.assertEqual(calls,[])

    def test_non_idempotent_crashed_operation_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as root:
            store=DurableFilmGraph(Path(root)/"save.sqlite3",clock=lambda:100.0)
            action,out,token=store.start_or_reuse("run","asset","fingerprint",
                trusted_idempotent=False,existing_result_verifier=lambda x:True,
                lease_seconds=20)
            self.assertEqual(action,"execute")
            with self.assertRaisesRegex(RecoveryBlocked,"lease"):
                store.start_or_reuse("run","asset","fingerprint",
                    trusted_idempotent=False,existing_result_verifier=lambda x:True,
                    lease_seconds=20)
            store.clock=lambda:200.0
            with self.assertRaisesRegex(RecoveryBlocked,"reconciliation"):
                store.start_or_reuse("run","asset","fingerprint",
                    trusted_idempotent=False,existing_result_verifier=lambda x:True,
                    lease_seconds=20)
            action,out,_=store.start_or_reuse("run","asset","fingerprint",
                trusted_idempotent=True,existing_result_verifier=lambda x:True,
                lease_seconds=20)
            self.assertEqual(action,"execute")

    def test_verifier_denial_prevents_false_render_and_restart(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            args=self.args(root,catalog(calls))
            args["output_verifier"]=lambda tid,output:False
            self.assertEqual(execute_durable_film_graph(**args)["status"],"blocked")
            self.assertEqual(calls,["art"])
            run=execute_durable_film_graph(**self.args(root,catalog(calls)))
            self.assertEqual(run["status"],"all_tool_results_verified")
            self.assertEqual(calls,["art","art","finish"])


if __name__=="__main__":unittest.main()

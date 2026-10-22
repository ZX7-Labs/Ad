"""Physical source provenance and artist-scoped non-destructive DAG invalidation."""
from __future__ import annotations

import hashlib
import tempfile
import threading
import unittest
from pathlib import Path

from studio_next.contracts import ToolSpec
from studio_next.durable_graph import DurableFilmGraph, execute_durable_film_graph
from studio_next.film_ir import validate_film_ir
from studio_next.media_vault import sha256_file
from studio_next.registry import ToolCatalog


def asset(asset_id,source):
    return {"id":asset_id,"status":"verified","rights":"owner_supplied",
            "location":source.name,"sha256":sha256_file(source)}


class OriginalPhysicalDependentFilmTests(unittest.TestCase):
    def _film(self,sources):
        return {
            "project":{"creative_intent":"Two independent scenes with original images"},
            "assets":[asset("camera_a",sources["a"]),asset("camera_b",sources["b"])],
            "shots":[
                {"id":"portrait","purpose":"Actual artist-chosen original shot A",
                 "asset_refs":["camera_a"],"duration_seconds":2.0},
                {"id":"landscape","purpose":"Actual artist-chosen original shot B",
                 "asset_refs":["camera_b"],"duration_seconds":2.0}],
            "tool_graph":[
                {"id":"frame_a","purpose":"Transform original scene A",
                 "tool_id":"art.stage","inputs":{"source":"a.wav"},
                 "shot_refs":["portrait"],"depends_on":[]},
                {"id":"frame_b","purpose":"Transform original scene B",
                 "tool_id":"art.stage","inputs":{"source":"b.wav"},
                 "shot_refs":["landscape"],"depends_on":[]},
                {"id":"final","purpose":"Combine both authored original shots",
                 "tool_id":"art.final","depends_on":["frame_a","frame_b"],
                 "inputs":{"a":{"$node_output":"frame_a"},"b":{"$node_output":"frame_b"}}}
            ]
        }

    def _catalog(self,root,calls,mutate=None):
        tools=ToolCatalog()
        def shot(inputs):
            name=inputs["source"]
            calls.append("shot:"+name)
            source=root/name
            if mutate and mutate==name:
                source.write_bytes(source.read_bytes()+b"source changed during rendering")
            return {"source":name,"original_sha256":sha256_file(source)}
        def final(inputs):
            calls.append("final")
            return {"film_shots":[inputs["a"]["source"],inputs["b"]["source"]],
                    "proof_sha":hashlib.sha256(repr(inputs).encode()).hexdigest()}
        tools.register(ToolSpec("art.stage","Original scene encoding",
            "Trusted local physical artist shot transform","write"),shot)
        tools.register(ToolSpec("art.final","Original film mux",
            "Trusted real film assembly artifact","write"),final)
        return tools

    def _run(self,film,root,calls,*,mutate=None):
        sources={"a":root/"a.wav","b":root/"b.wav"}
        def material(tool,inputs):
            if tool=="art.stage":
                p=root/inputs["source"]
                return [{"source":inputs["source"],
                         "bytes":p.stat().st_size,"sha256":sha256_file(p)}]
            return []
        return execute_durable_film_graph(
            film,self._catalog(root,calls,mutate=mutate),fact_ids=set(),
            store=DurableFilmGraph(root/"runtime.sqlite3"),
            trusted_idempotent_tools={"art.stage","art.final"},
            output_verifier=lambda tid,output:bool(output.get(
                "original_sha256" if tid=="art.stage" else "proof_sha")),
            tool_revisions={"art.stage":"artist-v1-content-proof",
                            "art.final":"artist-v1-content-proof"},
            input_material_fingerprint=material,
            lease_seconds=.5)

    def test_unrelated_original_asset_revision_preserves_other_scene_and_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            sources={"a":root/"a.wav","b":root/"b.wav"}
            sources["a"].write_bytes(b"original-audio-portrait")
            sources["b"].write_bytes(b"original-audio-landscape")
            film=self._film(sources)
            calls=[]
            first=self._run(film,root,calls)
            self.assertEqual(first["status"],"all_tool_results_verified",first)
            self.assertEqual(calls,["shot:a.wav","shot:b.wav","final"])
            second=self._run(film,root,calls)
            self.assertEqual(second["reused"],["frame_a","frame_b","final"])
            self.assertEqual(len(calls),3)

            # An unrelated *verified* asset in scene B must not cause scene A
            # to rerender. Actual bytes and scene-specific metadata still hash.
            extra=root/"extra.wav";extra.write_bytes(b"new original scene B insert")
            revised=self._film(sources)
            revised["assets"].append(asset("another_b_asset",extra))
            revised["shots"][1]["asset_refs"].append("another_b_asset")
            edit=self._run(revised,root,calls)
            self.assertEqual(edit["reused"],["frame_a"],edit)
            self.assertEqual(edit["completed"],["frame_a","frame_b","final"])
            self.assertEqual(calls,["shot:a.wav","shot:b.wav","final",
                                    "shot:b.wav","final"])
            self.assertTrue(any(x["node"]=="frame_a" and x["state"]=="reused"
                                for x in edit["trace"]))

    def test_real_original_source_swapped_during_render_never_gets_committed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            sources={"a":root/"a.wav","b":root/"b.wav"}
            sources["a"].write_bytes(b"real-camera-footage-a")
            sources["b"].write_bytes(b"real-camera-footage-b")
            calls=[]
            first=self._run(self._film(sources),root,calls,mutate="a.wav")
            self.assertIn(first["status"],("blocked","failed_partial"))
            self.assertIn("Original source changed during physical render",
                          " ".join(first["errors"]))
            self.assertNotIn("frame_a",first["completed"])
            store=DurableFilmGraph(root/"runtime.sqlite3")
            self.assertTrue(any(i["status"]=="failed" for i in
                                store.inspect(first["project_key"])))
            # A subsequent deterministic stage can safely redo only if the
            # original source has been authorized and re-fingerprinted.
            outcome=self._run(self._film(sources),root,calls)
            self.assertEqual(outcome["status"],"all_tool_results_verified",outcome)

    def test_missing_asset_scope_id_and_invalid_list_fail_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            files={"a":root/"a.wav","b":root/"b.wav"}
            for src in files.values():src.write_bytes(b"original")
            ir=self._film(files)
            ir["tool_graph"][0]["asset_refs"]=["not-owned"]
            report=validate_film_ir(ir,installed_tool_ids={"art.stage","art.final"},
                                    fact_ids=set())
            self.assertFalse(report.render_ready)
            self.assertIn("invalid original media asset scope"," ".join(report.errors))
            ir["tool_graph"][0]["asset_refs"]=["camera_a","camera_a"]
            report=validate_film_ir(ir,installed_tool_ids={"art.stage","art.final"},
                                    fact_ids=set())
            self.assertFalse(report.render_ready)

    def test_unscoped_production_op_conservatively_depends_on_whole_film(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=root/"a.wav";b=root/"b.wav"
            a.write_bytes(b"a");b.write_bytes(b"b")
            from studio_next.body_dependency_scope import select_verified_node_assets
            items=[asset("camera_a",a),asset("camera_b",b)]
            self.assertEqual(select_verified_node_assets(items,
                {"id":"final"},[]),items)
            self.assertEqual(select_verified_node_assets(items,
                {"id":"stage","asset_refs":["camera_a"]},[]),items[:1])


if __name__=="__main__":
    unittest.main()

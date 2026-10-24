import json
import tempfile
import unittest
from pathlib import Path

from studio_next.stage_checkpoint import DurableStageStore,content_signature,fingerprint


class DurableArtStageTests(unittest.TestCase):
    def test_recovers_identical_model_result_without_rerunning_film(self):
        with tempfile.TemporaryDirectory() as root:
            state=DurableStageStore(root)
            source={"film":"same original scene","identity":"one director"}
            scene={"camera":"model-authored","length_seconds":1.675}
            state.save("scene_001",source,scene)
            self.assertEqual(state.find("scene_001",source),scene)
            self.assertIsNone(state.find("scene_001",{"film":"new idea","identity":"one director"}))

    def test_never_reuses_different_model_brief_or_contract(self):
        source=lambda model,fact:content_signature(film_bytes=b"Original art",
            brief={"facts":{"identity":fact}},model_id=model,
            scene={"id":"a"},previous_design={},
            validation_contract_hash="ver1")
        with tempfile.TemporaryDirectory() as root:
            state=DurableStageStore(root)
            state.save("a",source("9b","notebook"),{"result":"real model creative specification"})
            self.assertIsNone(state.find("a",source("another","notebook")))
            self.assertIsNone(state.find("a",source("9b","product invented")))
            updated=source("9b","notebook")
            updated["renderer_contract_sha256"]="new_schema"
            self.assertIsNone(state.find("a",updated))

    def test_parallel_creative_directors_preserve_distinct_original_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=DurableStageStore(folder)
            first={"shot":"opening","source_sha256":"a"*64}
            second={"shot":"closing","source_sha256":"b"*64}
            a=archive.save("comfy_prompt",first,{"prompt_id":"first-actual-run"})
            b=archive.save("comfy_prompt",second,{"prompt_id":"second-actual-run"})
            self.assertNotEqual(a,b)
            self.assertTrue(a.is_file())
            self.assertTrue(b.is_file())
            self.assertEqual(archive.find("comfy_prompt",first),
                             {"prompt_id":"first-actual-run"})
            self.assertEqual(archive.find("comfy_prompt",second),
                             {"prompt_id":"second-actual-run"})
            with self.assertRaisesRegex(ValueError,"already owns"):
                archive.save("comfy_prompt",first,{"prompt_id":"different-run"})
            self.assertEqual(archive.find("comfy_prompt",first),
                             {"prompt_id":"first-actual-run"})
            self.assertEqual(archive.save("comfy_prompt",first,
                             {"prompt_id":"first-actual-run"}),a)

    def test_saved_evidence_is_tamper_evident(self):
        with tempfile.TemporaryDirectory() as root:
            state=DurableStageStore(root)
            path=state.save("s1",{"scene":1},{"model":"original"})
            doc=json.loads(path.read_text())
            doc["model_output"]["model"]="switched"
            path.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"digest"):
                state.find("s1",{"scene":1})

    def test_foreign_model_checkpoint_symlink_is_never_loaded_or_modified(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            state=DurableStageStore(root/"owner-artifacts")
            input_data={"original":"one private creator"}
            exposed=state._path("scene_007",input_data)
            state.root.mkdir()
            other=root/"independent-editor.json"
            other.write_bytes(b"do-not-change-existing-editor-data")
            exposed.symlink_to(other)
            with self.assertRaisesRegex(ValueError,"symbolic link"):
                state.find("scene_007",input_data)
            with self.assertRaisesRegex(ValueError,"symbolic link"):
                state.save("scene_007",input_data,{"shot":"untrusted"})
            self.assertEqual(other.read_bytes(),
                             b"do-not-change-existing-editor-data")

    def test_cannot_escape_checkpoint_directory(self):
        with tempfile.TemporaryDirectory() as root:
            state=DurableStageStore(root)
            for bad in ("../hack","/root/write","a/b","", "é"):
                with self.assertRaises(ValueError):
                    state.save(bad,{},{})

if __name__=="__main__":
    unittest.main()

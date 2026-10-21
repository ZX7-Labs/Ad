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

    def test_saved_evidence_is_tamper_evident(self):
        with tempfile.TemporaryDirectory() as root:
            state=DurableStageStore(root)
            path=state.save("s1",{"scene":1},{"model":"original"})
            doc=json.loads(path.read_text())
            doc["model_output"]["model"]="switched"
            path.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"digest"):
                state.find("s1",{"scene":1})

    def test_cannot_escape_checkpoint_directory(self):
        with tempfile.TemporaryDirectory() as root:
            state=DurableStageStore(root)
            for bad in ("../hack","/root/write","a/b","", "é"):
                with self.assertRaises(ValueError):
                    state.save(bad,{},{})

if __name__=="__main__":
    unittest.main()

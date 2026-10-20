import json
import tempfile
import unittest
from pathlib import Path
from studio_next.checkpoints import CheckpointLedger

class StageRecoveryTests(unittest.TestCase):
    def setup_case(self,folder):
        ledger=CheckpointLedger(folder)
        fp=ledger.fingerprint(name="treatment",model_id="local-film-brain",
                 system="Write a real original scene",input_data={"owner":{"fact":"FOLD is paper"}},
                 sampling={"temperature":0.72,"max_tokens":2800})
        return ledger,fp
    def test_verified_stage_can_resume_without_model_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,fp=self.setup_case(tmp)
            c.write("treatment",fp,{"scenes":[{"id":"real_draft"}]})
            self.assertEqual(c.load("treatment",fp)["scenes"][0]["id"],"real_draft")
    def test_changed_prompt_invalidates_old_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,fp=self.setup_case(tmp);c.write("treatment",fp,{"scenes":[]})
            new=c.fingerprint(name="treatment",model_id="local-film-brain",
                  system="Write a distinctly DIFFERENT story",input_data={"owner":{"fact":"FOLD is paper"}},
                  sampling={"temperature":.72,"max_tokens":2800})
            self.assertIsNone(c.load("treatment",new))
    def test_changed_owner_fact_invalidates_old_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,fp=self.setup_case(tmp);c.write("treatment",fp,{"scenes":[]})
            changed=c.fingerprint(name="treatment",model_id="local-film-brain",
                  system="Write a real original scene",
                  input_data={"owner":{"fact":"FOLD is a mobile app"}},
                  sampling={"temperature":.72,"max_tokens":2800})
            self.assertIsNone(c.load("treatment",changed))
    def test_changed_model_invalidates_old_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,fp=self.setup_case(tmp);c.write("treatment",fp,{"scenes":[]})
            different=c.fingerprint(name="treatment",model_id="stronger-9b",
                  system="Write a real original scene",input_data={"owner":{"fact":"FOLD is paper"}},
                  sampling={"temperature":.72,"max_tokens":2800})
            self.assertIsNone(c.load("treatment",different))
    def test_tampered_output_must_not_be_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,fp=self.setup_case(tmp);c.write("treatment",fp,{"scenes":[]})
            (Path(tmp)/"treatment.json").write_text('{"scenes":[{"id":"hijacked"}]}')
            self.assertIsNone(c.load("treatment",fp))
    def test_truncated_output_must_not_be_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,fp=self.setup_case(tmp);c.write("treatment",fp,{"scenes":[]})
            (Path(tmp)/"treatment.json").write_text('{"scenes":[')
            self.assertIsNone(c.load("treatment",fp))
    def test_stage_dependencies_are_part_of_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,fp=c0=self.setup_case(tmp);c.write("treatment",fp,{"scenes":[]})
            f=c.fingerprint(name="treatment",model_id="local-film-brain",
                  system="Write a real original scene",
                  input_data={"owner":{"fact":"FOLD is paper"},"selected":{"id":"different_pitch"}},
                  sampling={"temperature":.72,"max_tokens":2800})
            self.assertIsNone(c.load("treatment",f))
    def test_sampling_change_cannot_reuse_a_wrong_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,fp=self.setup_case(tmp);c.write("treatment",fp,{"scenes":[]})
            changed=c.fingerprint(name="treatment",model_id="local-film-brain",
                  system="Write a real original scene",input_data={"owner":{"fact":"FOLD is paper"}},
                  sampling={"temperature":.1,"max_tokens":2800})
            self.assertIsNone(c.load("treatment",changed))

if __name__=="__main__":unittest.main()

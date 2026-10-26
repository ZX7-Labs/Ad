import json
import tempfile
import unittest
from pathlib import Path
from studio_next.model_audition import verify_artistic_sample,run_audition


def brief():
    return {"request":"An original cinematic explanation","facts":{"first":"Owner-approved original truth"}}

def sample(n):
    return {"title":"The necessary question","creative_intent":"Find unexpected human relevance",
            "viewer_experience":"Wonder grows through actual event",
            "central_mechanism":"A single physical change forces a revelation",
            "visual_and_sound_language":"Authentic material and rooted camera",
            "exhibition":"Director chooses visual format","voice_decision":"Designed quiet",
            "shots":[{"id":f"beat{i}","dramatic_purpose":"Progress actual story",
                    "duration_seconds":2.3+i,
                    "visual":"A precise film image with subject",
                    "camera_and_motion":"Movement has a spatial purpose",
                    "edit_and_continuity":"A causal audiovisual match",
                    "sound_and_performance":"Noise shifts with consequence",
                    "spoken_words":"","factual_basis":["first"],"assets_needed":[]} for i in range(n)],
            "unresolved_production_needs":[]}


class CreativeModelAuditionTests(unittest.TestCase):
    def test_no_fixed_story_shots_runtime_voice_or_format(self):
        for n in (1,6,100):
            s=sample(n)
            x=verify_artistic_sample(s,brief())
            self.assertTrue(x["parseable"])
            self.assertEqual(x["scene_count"],n)
            self.assertFalse(x["original_model_quality_tested"])

    def test_bad_data_never_becomes_creative_approval(self):
        s=sample(1);s["shots"][0]["factual_basis"]=["false"]
        with self.assertRaisesRegex(ValueError,"Unknown owner"):
            verify_artistic_sample(s,brief())
        s=sample(1);s["shots"][0]["duration_seconds"]=float("nan")
        with self.assertRaisesRegex(ValueError,"duration"):
            verify_artistic_sample(s,brief())

    def test_model_samples_saved_even_when_some_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p1=Path(d)/"one.json";p2=Path(d)/"two.json"
            for p in (p1,p2):p.write_text(json.dumps(brief()))
            class Brain:
                def __init__(self):self.count=0
                def decide(self,context):
                    self.count+=1
                    return sample(8) if self.count==1 else {"title":"incomplete"}
            m=run_audition([p1,p2],Brain(),Path(d)/"output")
            self.assertEqual(len(m["samples"]),2)
            self.assertEqual(m["samples"][0]["status"],"awaiting_independent_creative_assessment")
            self.assertEqual(m["samples"][1]["status"],"rejected_model_output")
            self.assertTrue((Path(d)/"output"/"brief-01"/"original-model-sample.json").exists())
            self.assertTrue((Path(d)/"output"/"brief-02"/"original-model-sample.json").exists())
            self.assertTrue(m["no_model_promoted"])


if __name__=="__main__":
    unittest.main()

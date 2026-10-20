import copy
import unittest
from director_research.benchmark import allocate_times, construct_filmdsl, audit

BRIEF={"product":"NOVA","category":"software","audience":"creative teams",
       "benefit":"a calmer place to organize ideas","cta":"Discover NOVA"}
CONCEPT={"concept":"Scattered idea fragments align into one clean workspace",
         "audience_insight":"Creative teams have many ideas to organize",
         "hook":"Your ideas deserve some room",
         "visual_motif":"a single floating translucent note card",
         "palette":["#123456","#AABBCC","#EEFFDD"],
         "typography":"clear sans serif",
         "camera_language":"calm close push",
         "lighting":"diffused soft light","use_3d":"none; no benefit",
         "music":"quiet soft pulse","sound_design":"one click on alignment",
         "voice":"M3","voice_direction":"natural calm confident"}
ROLES=["hook","problem","reveal","demonstration","payoff"]
LINES=["Where did that idea go?","Too many notes can hide a good thought.",
       "NOVA gives creative teams a calmer place for ideas.",
       "Imagine each thought finding its own space.",
       "Discover NOVA. Keep your next idea close."]

def scenes():
    return {"clips":[{"role":role,"seconds":sec,"narration":line,
       "emotion":"curious and calm","on_screen":"IDEAS IN FOCUS",
       "composition":"one large floating note card in center, generous negative space",
       "camera":"slow forward push","motion":"slide paper into neat columns",
       "light":"soft studio light","transition":"match cut from note edge to next note edge",
       "sfx":"single tap","music":"soft synthesizer pulse",
       "technique":"2d","factual_basis":"original symbolic metaphor",
       "asset":"draw one translucent rectangular note"}
       for role,sec,line in zip(ROLES,[4,5,5,5,5],LINES)]}

class ResearchTests(unittest.TestCase):
    def test_compiles_and_passes(self):
        plan=construct_filmdsl(BRIEF,CONCEPT,scenes())
        checks=audit(plan,BRIEF)
        self.assertTrue(checks["passed"],checks)
        self.assertEqual(checks["shot_count"],5)
        self.assertEqual(checks["duration_seconds"],24)
        self.assertEqual(len(plan["assets"]),6)
        self.assertEqual(plan["clips"][2]["staging"]["asset_refs"][0],"motif_main")
    def test_unsupported_claim_blocks(self):
        x=scenes();x["clips"][2]["narration"]="NOVA works 100% guaranteed!"
        qa=audit(construct_filmdsl(BRIEF,CONCEPT,x),BRIEF)
        self.assertFalse(qa["passed"]);self.assertIn("unsupported",str(qa["hard_errors"]))
    def test_wrong_voice_blocks(self):
        concept=copy.deepcopy(CONCEPT);concept["voice"]="Robert Downey Jr."
        qa=audit(construct_filmdsl(BRIEF,concept,scenes()),BRIEF)
        self.assertIn("M3/F2",str(qa["hard_errors"]))
    def test_nonexistent_asset_blocks(self):
        plan=construct_filmdsl(BRIEF,CONCEPT,scenes())
        plan["clips"][0]["staging"]["asset_refs"].append("unknown_asset")
        self.assertIn("undefined continuity asset",str(audit(plan,BRIEF)["hard_errors"]))
    def test_speed_blocks(self):
        x=scenes();x["clips"][0]["narration"]="very "*25
        qa=audit(construct_filmdsl(BRIEF,CONCEPT,x),BRIEF)
        self.assertIn("not feasible",str(qa["hard_errors"]))
    def test_wrong_length_blocks(self):
        plan=construct_filmdsl(BRIEF,CONCEPT,scenes())
        plan["clips"][0]["duration_seconds"]=9
        self.assertIn("duration",str(audit(plan,BRIEF)["hard_errors"]))
    def test_3d_not_asserted_rendered(self):
        x=scenes();x["clips"][1]["technique"]="3d"
        plan=construct_filmdsl(BRIEF,CONCEPT,x)
        qa=audit(plan,BRIEF)
        self.assertIn("execution not demonstrated",str(qa["warnings"]))
        self.assertEqual(plan["clips"][1]["render"]["execution"],"NOT_EXECUTED")
    def test_model_technique_casing_normalized(self):
        x=scenes()
        x["clips"][0]["technique"]="2.5D"
        x["clips"][1]["technique"]="2D"
        p=construct_filmdsl(BRIEF,CONCEPT,x)
        self.assertEqual(p["clips"][0]["render"]["technique"],"2.5d")
        self.assertEqual(p["clips"][1]["render"]["technique"],"2d")
        self.assertEqual(audit(p,BRIEF)["hard_errors"],[])
    def test_unverified_automatic_claim_blocked(self):
        x=scenes()
        x["clips"][2]["narration"]="Ideas organize themselves automatically."
        p=construct_filmdsl(BRIEF,CONCEPT,x)
        self.assertIn("unsupported promise",str(audit(p,BRIEF)["hard_errors"]))
    def test_timing_preserves_script(self):
        x=scenes()
        x["clips"][1]["seconds"]=7
        copy_before=[p["narration"] for p in x["clips"]]
        allocate_times(x["clips"])
        self.assertEqual([p["narration"] for p in x["clips"]],copy_before)
        self.assertAlmostEqual(sum(p["seconds"] for p in x["clips"]),24.0)

if __name__=="__main__":unittest.main()

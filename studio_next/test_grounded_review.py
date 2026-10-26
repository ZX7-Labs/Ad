import unittest
from studio_next.grounded_review import validate_evidence_review

SCRIPT={"title":"Notebook ad","scenes":[
 {"id":"the_reach","purpose":"Show a simple gesture",
  "narration":"","visual":"A commuter pulls a small paper notebook from his pocket.",
  "motion":"The hand moves calmly.","edit":"Cut to the notebook.","audio":"Train hum."},
 {"id":"the_mark","purpose":"Capture the thought",
  "narration":"","visual":"A pencil scratches an idea on an empty notebook page.",
  "motion":"Slow pencil strokes.","edit":"Fade to black.","audio":"Paper scratch."}
]}
def critique(scene,quote,reason="Something looks inaccurate",repair="Check actual assets"):
 return {"approved":False,"issues":[{"scene_id":scene,"source_excerpt":quote,
           "reason":reason,"repair":repair}]}

class GroundedReviewTests(unittest.TestCase):
 def test_real_scene_quote_accepted(self):
  v=validate_evidence_review(SCRIPT,critique("the_reach","paper notebook"))
  self.assertTrue(v.structurally_valid,v.public())
  self.assertEqual(len(v.accepted_issues),1)
  self.assertFalse(v.verified_fact_claims)
  self.assertFalse(v.human_creative_approval)
 def test_invented_medical_emergency_reviewer_issue_rejected(self):
  v=validate_evidence_review(SCRIPT,critique("the_reach","his father is rushed into an emergency room"))
  self.assertFalse(v.structurally_valid)
  self.assertIn("No exact screenplay evidence",str(v.rejected_issues))
 def test_invented_quote_never_auto_revise(self):
  v=validate_evidence_review(SCRIPT,critique("the_mark","Ink fully dries in 1 second"))
  self.assertEqual(v.accepted_issues,[])
  self.assertFalse(v.structurally_valid)
 def test_other_scene_quote_not_evidence(self):
  v=validate_evidence_review(SCRIPT,critique("the_reach","pencil scratches an idea"))
  self.assertFalse(v.structurally_valid)
 def test_critical_review_must_name_existing_scene(self):
  v=validate_evidence_review(SCRIPT,critique("never_happened","paper notebook"))
  self.assertFalse(v.structurally_valid)
 def test_approval_with_issues_rejected(self):
  v=critique("the_reach","paper notebook")
  v["approved"]=True
  self.assertFalse(validate_evidence_review(SCRIPT,v).structurally_valid)
 def test_empty_review_cannot_claim_human_approval(self):
  v=validate_evidence_review(SCRIPT,{"approved":True,"issues":[]})
  self.assertTrue(v.structurally_valid)
  self.assertFalse(v.human_creative_approval)
 def test_malformed_model_issues_fail_closed(self):
  for x in ({"approved":True},{"approved":"yes","issues":[]},
            {"approved":False,"issues":[{"reason":"bad"}]}):
   v=validate_evidence_review(SCRIPT,x)
   self.assertFalse(v.structurally_valid)
 def test_matching_quote_is_not_proof_that_claim_is_true(self):
  v=validate_evidence_review(SCRIPT,critique("the_mark","pencil scratches an idea",
               "Claimed graphite needs to dry", "Rewrite"))
  self.assertTrue(v.structurally_valid)
  self.assertFalse(v.verified_fact_claims)
if __name__=="__main__":unittest.main()

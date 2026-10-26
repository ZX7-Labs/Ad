import unittest
from studio_next.creative_challenge import audit

BRIEF={"request":"An original advertisement","facts":{"fact1":"Real paper notebook"}}
PITCHES={"candidates":[
 {"id":"a","idea":"A traveller almost loses a thought","opening":"An empty page hits the floor",
  "viewer_reason":"Memory is fragile","visual_principle":"Physical paper motions","originality_risk":"Could become melodrama"},
 {"id":"b","idea":"The pocket holds a quiet observatory","opening":"A person opens a notebook like a telescope",
  "viewer_reason":"Capturing details","visual_principle":"Ink becomes constellations","originality_risk":"Unnecessary VFX"}]}
SELECTION={"selected_id":"a","why_this_concept":"Specific human incident","weaknesses":[],"revision_note":""}
SCRIPT={"creative_intent":"Make fleeting ideas tactile","story":"A sentence is preserved",
"voice":{"choice":"F2"},"scenes":[
 {"id":"opening","purpose":"Start surprise","duration_seconds":7.8,
  "narration":"The best ideas don't always wait for you.",
  "visual":"One page flies by a traveller","motion":"An angled drift into frame",
  "edit":"Match cut to pocket edge","audio":"Paper flutter","fact_refs":["fact1"],
  "assets_needed":["owner-supplied or original animation"]}]}
REVIEW={"approved_for_human_audition":True,"blockers":[]}

class TestScriptCompetition(unittest.TestCase):
 def test_no_fixed_length_or_scene_count(self):
  qa=audit(BRIEF,PITCHES,SELECTION,SCRIPT,REVIEW)
  self.assertTrue(qa["structural_passed"],qa)
  self.assertEqual(qa["scene_count"],1)
  self.assertTrue(qa["human_audition_candidate"])
  self.assertFalse(qa["render_ready"])
 def test_unproven_claim_ref_does_not_pass(self):
  p={**SCRIPT,"scenes":[{**SCRIPT["scenes"][0],"fact_refs":["500_percent_revenue"]}]}
  self.assertFalse(audit(BRIEF,PITCHES,SELECTION,p,REVIEW)["structural_passed"])
 def test_wrong_selection_does_not_pass(self):
  self.assertIn("Selected idea",str(audit(BRIEF,PITCHES,{"selected_id":"invented"},SCRIPT,REVIEW)["issues"]))
 def test_empty_scenes_not_accepted(self):
  self.assertFalse(audit(BRIEF,PITCHES,SELECTION,{**SCRIPT,"scenes":[]},REVIEW)["structural_passed"])
 def test_human_review_is_not_video(self):
  q=audit(BRIEF,PITCHES,SELECTION,SCRIPT,REVIEW)
  self.assertFalse(q["has_video"])
 def test_reviewer_cannot_approve_with_blockers(self):
  bad={**REVIEW,"blockers":[{"location":"opening","problem":"Bad","repair":"Repair"}]}
  self.assertFalse(audit(BRIEF,PITCHES,SELECTION,SCRIPT,bad)["structural_passed"])
 def test_no_unavailable_voice(self):
  p={**SCRIPT,"voice":{"choice":"unlicensed actor clone"}}
  self.assertFalse(audit(BRIEF,PITCHES,SELECTION,p,REVIEW)["structural_passed"])
 def test_no_hardcoded_pacing(self):
  p={**SCRIPT,"scenes":[{**SCRIPT["scenes"][0],"duration_seconds":72.1}]}
  q=audit(BRIEF,PITCHES,SELECTION,p,REVIEW)
  self.assertTrue(q["structural_passed"])
  self.assertEqual(q["planned_seconds"],72.1)
 def test_fast_speech_flag_only(self):
  p={**SCRIPT,"scenes":[{**SCRIPT["scenes"][0],"duration_seconds":1.4,
     "narration":"One two three four five six seven eight nine ten eleven twelve thirteen fourteen"}]}
  qa=audit(BRIEF,PITCHES,SELECTION,p,REVIEW)
  self.assertTrue(qa["timing_warnings"])
  self.assertFalse(qa["render_ready"])

if __name__=="__main__":unittest.main()

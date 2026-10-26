import copy
import unittest
from studio_next.blind_comparison import comparison,essence
def film(story,model):
 return {"model":model,"brief":{"request":"Film a notebook","facts":{"kind":"paper"}},
         "treatment":{"title":model,"creative_intent":story,"story":story,
                      "scenes":[{"id":"open","duration_seconds":11.5,
                                 "purpose":"Introduce paper","narration":"Hold onto the idea.",
                                 "visual":"One original paper notebook close-up",
                                 "motion":"Camera pull","edit":"Hard cut"}]}}
class BlindTests(unittest.TestCase):
 def test_identity_not_revealed_to_human_reader(self):
  text,key=comparison(film("An idea arriving at a station","model-secret-alpha"),
                      film("Handwritten notes","model-secret-beta"))
  self.assertNotIn("model-secret-alpha",text)
  self.assertNotIn("model-secret-beta",text)
  self.assertIn("Candidate A",text)
  self.assertIn("Candidate B",text)
  self.assertEqual(set(key),{"A","B"})
 def test_same_facts_required(self):
  a=film("One", "alpha")
  b=film("Two", "beta");b["brief"]["facts"]["kind"]="digital"
  with self.assertRaises(ValueError):comparison(a,b)
 def test_missing_scenes_cannot_pass(self):
  a=film("One","alpha");a["treatment"]["scenes"]=[]
  with self.assertRaises(ValueError):essence(a)
 def test_order_deterministic_and_unbiased_by_model_names(self):
  a=film("One original narrative","small_4b")
  b=film("Other distinct original narrative","large_9b")
  c1,k1=comparison(a,b)
  c2,k2=comparison(a,b)
  self.assertEqual(c1,c2)
  self.assertEqual(k1,k2)
 def test_review_does_not_auto_generate_creative_rank(self):
  text,_=comparison(film("Something","a"),film("Something else","b"))
  self.assertIn("No automated 'overall creativity percentage'",text)
if __name__=="__main__":unittest.main()

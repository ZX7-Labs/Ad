import copy
import unittest
from studio_next.film_ir import validate_film_ir

def film():
    return {
      "project":{"title":"An Original Story",
                 "creative_intent":"A single overheard sentence turns into a winding city map.",
                 "format":{"aspect_ratio":"21:9","language":"Hindi-English","genre":"educational"}},
      "assets":[{"id":"owner_clip","status":"verified","rights":"owner_supplied",
                 "location":"asset://owner/clip-one"}],
      "shots":[
        {"id":"opening","purpose":"Create a memorable human curiosity gap",
         "duration_seconds":0.9,"asset_refs":["owner_clip"],"fact_refs":["title"],
         "camera":{"movement":"owner decides"},"audio":{"voice":"F2"}},
        {"id":"evidence","purpose":"Visualize a concept with actual supplied footage",
         "duration_seconds":75.8,"asset_refs":["owner_clip"],
         "fact_refs":["title"],"layers":[{"asset":"owner_clip"}]}
      ],
      "tool_graph":[
          {"id":"shot1","tool_id":"editor.assemble","purpose":"Compose first shot","inputs":{},
           "depends_on":[]},
          {"id":"shot2","tool_id":"editor.assemble","purpose":"Compose second shot","inputs":{},
           "depends_on":["shot1"]},
          {"id":"film","tool_id":"ffmpeg.mux","purpose":"Encode composition","inputs":{},
           "depends_on":["shot1","shot2"]}
      ]
    }

class FilmIRTests(unittest.TestCase):
    def verify(self,p,installed={"editor.assemble","ffmpeg.mux"}):
        return validate_film_ir(p,installed_tool_ids=installed,fact_ids={"title"})
    def test_not_forced_to_9_16_five_shots_or_short_duration(self):
        o=self.verify(film())
        self.assertTrue(o.render_ready,o.errors)
        self.assertEqual(o.order,["shot1","shot2","film"])
    def test_required_assets_never_assumed_to_exist(self):
        p=film();p["assets"][0]["status"]="planned"
        o=self.verify(p)
        self.assertFalse(o.render_ready)
        self.assertIn("not verified",str(o.warnings))
    def test_unlicensed_media_blocked(self):
        p=film();p["assets"][0]["rights"]="unknown"
        o=self.verify(p)
        self.assertFalse(o.render_ready)
        self.assertIn("rights",str(o.errors))
    def test_missing_media_reference_blocked(self):
        p=film();p["shots"][0]["asset_refs"].append("random_internet_video")
        self.assertIn("unknown media",str(self.verify(p).errors))
    def test_missing_grounded_product_fact_blocked(self):
        p=film();p["shots"][1]["fact_refs"].append("proven_700_percent_growth")
        self.assertIn("unprovided fact",str(self.verify(p).errors))
    def test_graph_is_truly_acyclic(self):
        p=film();p["tool_graph"][0]["depends_on"]=["film"]
        self.assertIn("cycle",str(self.verify(p).errors))
    def test_unavailable_tool_cannot_claim_render_ready(self):
        p=film();p["tool_graph"][2]["tool_id"]="heavy.uninstalled.3d"
        self.assertIn("uninstalled",str(self.verify(p).errors))
    def test_no_graph_does_not_mean_completed_video(self):
        p=film();p["tool_graph"]=[]
        o=self.verify(p)
        self.assertFalse(o.render_ready)
        self.assertIn("No execution graph",str(o.warnings))
    def test_bad_time_never_accepted(self):
        for value in (-1,0,True,float("nan"),float("inf")):
            p=film();p["shots"][0]["duration_seconds"]=value
            self.assertIn("invalid duration",str(self.verify(p).errors))
    def test_duplicate_shots(self):
        p=film();p["shots"][1]["id"]="opening"
        self.assertIn("duplicate",str(self.verify(p).errors))
    def test_just_artistic_story_is_not_a_render(self):
        p=film();p["assets"][0]["status"]="planned";p["tool_graph"]=[]
        self.assertFalse(self.verify(p).render_ready)
    def test_adversarial_malformed_ir_references_cannot_crash(self):
        cases=[
          lambda p:p["shots"][0].update(asset_refs=[{"bad":"object"}]),
          lambda p:p["shots"][0].update(fact_refs=[["nested"]]),
          lambda p:p["shots"][0].update(fact_refs="pretend all"),
          lambda p:p["tool_graph"][1].update(depends_on=[{"bad":"object"}]),
          lambda p:p["tool_graph"][1].update(depends_on="shot1")
        ]
        for transform in cases:
            p=film();transform(p)
            self.assertTrue(self.verify(p).errors)
    def test_graph_order_deterministic(self):
        p=film();p["tool_graph"][2]["depends_on"]=["shot2","shot1"]
        self.assertEqual(self.verify(p).order,["shot1","shot2","film"])
if __name__=="__main__":unittest.main()

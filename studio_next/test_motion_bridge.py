import copy
import unittest
from studio_next.motion_bridge import compile_motion_project, UnsupportedMotionPlan, TOOL_ID


def case():
    return {
      "project":{"title":"Two thoughts","creative_intent":"See a line become a decision",
          "width":640,"height":960,"background":"#10151b","voice":"no_voice"},
      "assets":[
          {"id":"headline","status":"verified","rights":"generated_original","location":"inline://headline",
           "artwork":{"size":[540,92],"items":[{"type":"text","text":"A SMALL IDEA",
                          "at":[270,10],"size":50,"font":"bold","fill":"#fefefe","align":"center"}]}},
          {"id":"mark","status":"verified","rights":"generated_original","location":"inline://mark",
           "artwork":{"size":[200,120],"items":[{"type":"line","points":[[10,100],[180,16]],"width":8,"fill":"#fcce6a"}]}}
      ],
      "shots":[
          {"id":"open","purpose":"Introduce uncertainty","duration_seconds":1.2,
           "narration":"","asset_refs":["headline"],"fact_refs":[],
           "layers":[{"asset":"headline","x":320,"y":440,
                      "animate":{"opacity":[[0,0],[.6,1,"out"]]}}]},
          {"id":"turn","purpose":"Move from doubt to action","duration_seconds":1.5,
           "narration":"","asset_refs":["headline","mark"],"fact_refs":[],
           "layers":[{"asset":"headline","x":320,"y":350},
                     {"asset":"mark","x":310,"y":550,
                       "animate":{"reveal":[[0,0],[1.2,1,"out"]]}}]}
      ],
      "tool_graph":[{"id":"composite","tool_id":TOOL_ID,
                     "purpose":"Render original art with timed layers and sound",
                     "inputs":{},"depends_on":[]}]
    }


class MotionBridgeTests(unittest.TestCase):
    def test_real_renderer_schema_compiled_without_fabrication(self):
        p=compile_motion_project(case())
        self.assertEqual([s["id"] for s in p["scenes"]],["open","turn"])
        self.assertEqual(p["assets"]["mark"]["items"][0]["type"],"line")
        self.assertEqual(p["scenes"][1]["layers"][1]["animate"]["reveal"][1][0],1.2)
        self.assertEqual(p["voice"],"no_voice")

    def test_same_compiler_handles_director_selected_scene_count(self):
        x=case();x["shots"]=[x["shots"][0]]
        self.assertEqual(len(compile_motion_project(x)["scenes"]),1)
        x=case();x["shots"] += [copy.deepcopy(x["shots"][1])]
        x["shots"][2]["id"]="final"
        self.assertEqual(len(compile_motion_project(x)["scenes"]),3)

    def test_reject_unspecified_visual_instead_of_making_cards(self):
        x=case();del x["assets"][0]["artwork"]
        with self.assertRaisesRegex(UnsupportedMotionPlan,"lacks drawable artwork"):
            compile_motion_project(x)

    def test_reject_missing_layer_and_unused_licensed_asset(self):
        x=case();x["shots"][0]["layers"]=[]
        with self.assertRaises(UnsupportedMotionPlan): compile_motion_project(x)
        x=case();x["shots"][0]["asset_refs"].append("mark")
        with self.assertRaisesRegex(UnsupportedMotionPlan,"declared assets"):
            compile_motion_project(x)

    def test_reject_claim_refs_not_in_owner_evidence(self):
        x=case();x["shots"][0]["fact_refs"]=["invented_discount"]
        with self.assertRaisesRegex(UnsupportedMotionPlan,"unprovided fact"):
            compile_motion_project(x)

    def test_cannot_fake_real_footage_using_inline_shapes(self):
        x=case();x["assets"][0]["rights"]="owner_supplied"
        with self.assertRaisesRegex(UnsupportedMotionPlan,"inline cleared drawings"):
            compile_motion_project(x)

    def test_no_model_authored_shell_or_unknown_backend(self):
        x=case();x["tool_graph"][0]["inputs"]={"cmd":"rm -rf /"}
        with self.assertRaises(UnsupportedMotionPlan): compile_motion_project(x)
        x=case();x["tool_graph"][0]["tool_id"]="shell.execute"
        with self.assertRaisesRegex(UnsupportedMotionPlan,"uninstalled"):
            compile_motion_project(x)

    def test_no_silent_voice_selection_for_spoken_scene(self):
        x=case();x["shots"][0]["narration"]="This must be spoken"
        with self.assertRaisesRegex(UnsupportedMotionPlan,"no_voice"):
            compile_motion_project(x)

    def test_reject_hallucinated_camera_and_unsupported_image(self):
        x=case();x["shots"][0]["layers"][0]["3d_camera"]="flying drone"
        with self.assertRaisesRegex(UnsupportedMotionPlan,"unsupported layer"):
            compile_motion_project(x)
        x=case();x["assets"][0]["artwork"]["items"][0]["type"]="image"
        with self.assertRaisesRegex(UnsupportedMotionPlan,"supported 2D"):
            compile_motion_project(x)

    def test_invalid_tracks_and_cues(self):
        x=case();x["shots"][0]["layers"][0]["animate"]["opacity"]=[[0,0],[0,1]]
        with self.assertRaisesRegex(UnsupportedMotionPlan,"increasing"):
            compile_motion_project(x)
        x=case();x["shots"][1]["cues"]=[{"type":"paper","at":1.4,"seconds":.3}]
        with self.assertRaisesRegex(UnsupportedMotionPlan,"exceeds shot"):
            compile_motion_project(x)

    def test_limits_of_renderer_are_not_studio_creative_policy(self):
        x=case();x["shots"][1]["duration_seconds"]=90
        with self.assertRaisesRegex(UnsupportedMotionPlan,"in range"):
            compile_motion_project(x)

    def test_original_unicode_art_compiles_without_english_only_templates(self):
        x=case()
        x["assets"][0]["artwork"]["items"][0]["text"]="नमस्ते"
        # Artistic plans may use Hindi. The actual native renderer separately
        # verifies installed Unicode font cmap and RAQM shaping, not tofu.
        project=compile_motion_project(x)
        artwork=next(iter(project["assets"].values()))
        self.assertEqual(artwork["items"][0]["text"],"नमस्ते")


if __name__=="__main__":
    unittest.main()

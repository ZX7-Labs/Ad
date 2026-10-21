import unittest
from studio_next.segmented_screenplay import (
    create_screenplay,validate_spine,validate_authored_shot,retryable_output,
    complete_missing_ending, normalize_spine_layout)

def story(n=2):
    return {"title":"A drawn line has consequence",
      "creative_intent":"Demonstrate honest value","story":"Problem changes by a causal real action",
      "audience_impact":"See a small action differently",
      "visual_language":{"camera":"Physically meaningful and directed","sound":"Narrative"},
      "voice":{"choice":"F2","why":"Subtle","delivery":"Reflective"},
      "scene_map":[{"id":f"scene_{i}","purpose":f"Causal beat {i}",
         "duration_seconds":7+i,"dramatic_action":"Thing changes physically",
         "visual_goal":"Concrete filming objective","continuity_in":"Visual relation",
         "continuity_out":"Motivated bridge","sound_goal":"Meaningful sound",
         "factual_intent":["identity"]} for i in range(n)],
      "last_image":"A consequence is visible","production_unknowns":[]}

def actual_scene(b):
    return {"id":b["id"],"purpose":b["purpose"],
      "duration_seconds":b["duration_seconds"],"narration":"One honest sentence",
      "visual":"A real perspective camera sees ink contact paper",
      "motion":"Fingertip approaches and ink trace develops",
      "edit":"Match movement across the following shot",
      "audio":"Paper texture against silence","fact_refs":["identity"],
      "assets_needed":["Actually licensed close-up or generated conceptual artwork"]}

class ScriptBreakdownTests(unittest.TestCase):
    def test_model_alone_chooses_arbitrary_shot_count(self):
        for n in (1,4,31):
            model=story(n)
            calls=[]
            def invoke(name,prompt,payload,tokens,temp):
                calls.append((name,payload))
                if name=="spine":return model
                idx=int(name.split("-")[1])-1
                return actual_scene(model["scene_map"][idx])
            x=create_screenplay({"facts":{"identity":"Real notebook"}},{},{"selected_id":"a"},invoke)
            self.assertEqual(len(x["scenes"]),n)
            self.assertEqual(len(calls),n+1)
            self.assertEqual(calls[-1][1]["film_spine"],model)
            self.assertEqual(x["voice"]["choice"],"F2")

    def test_story_cannot_forge_fact_or_change_purpose(self):
        b=story()["scene_map"][0]
        s=actual_scene(b)
        s["fact_refs"]=["magic_product_claim"]
        with self.assertRaisesRegex(ValueError,"Unverified"):
            validate_authored_shot(s,b,{"identity"})
        s=actual_scene(b);s["purpose"]="Generic marketing"
        with self.assertRaisesRegex(ValueError,"purpose"):
            validate_authored_shot(s,b,{"identity"})

    def test_incomplete_shot_not_silently_deemed_production(self):
        b=story()["scene_map"][0]
        s=actual_scene(b);del s["assets_needed"]
        with self.assertRaisesRegex(ValueError,"full independent"):
            validate_authored_shot(s,b,{"identity"})

    def test_spine_validates_actor_voice_facts_and_time(self):
        x=story();self.assertEqual(len(validate_spine(x,{"identity"})),2)
        x=story();x["scene_map"][0]["factual_intent"]=["invention"]
        with self.assertRaisesRegex(ValueError,"nonexistent"):
            validate_spine(x,{"identity"})
        x=story();x["scene_map"][0]["duration_seconds"]=float("inf")
        with self.assertRaisesRegex(ValueError,"duration"):validate_spine(x,{"identity"})

    def test_intentional_silence_cannot_discard_written_dialogue(self):
        x=story(1);x["voice"]["choice"]="no_voice"
        def run(name, *_):
            return x if name=="spine" else actual_scene(x["scene_map"][0])
        with self.assertRaisesRegex(ValueError,"no_voice"):
            create_screenplay({"facts":{"identity":"Notebook"}},{},{},run)


    def test_missing_end_frame_repaired_without_rewriting_story(self):
        x=story(5)
        x["last_image"]=""
        original_beats=x["scene_map"]
        calls=[]
        def run(name,system,context,tokens,temperature):
            calls.append(name)
            if name=="spine":
                return x
            if name=="spine-last-image":
                return {"last_image":"The original ink line closes the shape across the notebook."}
            return actual_scene(original_beats[int(name.split("-")[1])-1])
        result=create_screenplay({"facts":{"identity":"Pocket notebook"}},{},{},run)
        self.assertEqual(len(result["scenes"]),5)
        self.assertEqual([a["id"] for a in result["scenes"]],
                         [a["id"] for a in original_beats])
        self.assertEqual(result["last_image"],
                         "The original ink line closes the shape across the notebook.")
        self.assertEqual(calls.count("spine"),1)
        self.assertEqual(calls.count("spine-last-image"),1)
        self.assertEqual(x["last_image"],"")

    def test_unverified_empty_ending_repair_does_not_pass(self):
        x=story(1)
        x.pop("last_image")
        def run(name,*args):
            if name=="spine":return x
            if name=="spine-last-image":return {"last_image":""}
            return actual_scene(x["scene_map"][0])
        with self.assertRaisesRegex(ValueError,"closing image"):
            create_screenplay({"facts":{"identity":"Owner fact"}},{},{},run)

    def test_nested_spine_fields_recovered_without_changing_story(self):
        x=story(3)
        preserved=[dict(b) for b in x["scene_map"]]
        nested=dict(x)
        nested["visual_language"]=dict(x["visual_language"])
        for name in ("voice","scene_map","last_image","production_unknowns"):
            nested["visual_language"][name]=nested.pop(name)
        out=normalize_spine_layout(nested)
        self.assertEqual(out["scene_map"],preserved)
        self.assertEqual(out, x)
        self.assertEqual(nested["visual_language"]["voice"]["choice"], "F2")
        self.assertEqual(len(validate_spine(out,{"identity"})),3)

    def test_nested_conflicts_and_fake_fact_ids_remain_blocked(self):
        x=story(2)
        x["visual_language"]["scene_map"]=[{"id":"invented"}]
        with self.assertRaisesRegex(ValueError,"Conflicting"):
            normalize_spine_layout(x)
        x=story(1)
        x["scene_map"][0]["factual_intent"]=["k2"]
        nested=dict(x)
        nested["visual_language"]=dict(x["visual_language"])
        for name in ("voice","scene_map","last_image","production_unknowns"):
            nested["visual_language"][name]=nested.pop(name)
        with self.assertRaisesRegex(ValueError,"nonexistent owner facts"):
            validate_spine(normalize_spine_layout(nested),{"identity"})

    def test_only_truncation_triggers_expansion(self):
        self.assertTrue(retryable_output(ValueError("Answer was truncated")))
        self.assertFalse(retryable_output(ValueError("Made up a client fact")))

if __name__=="__main__":
    unittest.main()

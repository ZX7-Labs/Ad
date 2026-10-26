import unittest
from studio_next.segmented_screenplay import (
    create_screenplay,validate_spine,validate_authored_shot,retryable_output,
    complete_missing_ending, normalize_spine_layout, reground_invalid_beats,
    repair_authored_shot)

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

    def test_actual_nested_voice_holding_entire_story_map(self):
        x=story(5)
        original=[dict(scene) for scene in x["scene_map"]]
        out={k:v for k,v in x.items() if k not in
             ("voice","scene_map","last_image","production_unknowns")}
        out["visual_language"]=dict(x["visual_language"])
        out["visual_language"]["voice"]=dict(x["voice"],
              scene_map=x["scene_map"],last_image=x["last_image"],
              production_unknowns=x["production_unknowns"])
        repaired=normalize_spine_layout(out)
        self.assertEqual(repaired["scene_map"],original)
        self.assertEqual(repaired["voice"],x["voice"])
        self.assertEqual(repaired["visual_language"],x["visual_language"])
        self.assertEqual(repaired,x)
        self.assertEqual(len(validate_spine(repaired,{"identity"})),5)

    def test_nested_voice_cannot_launder_nonexistent_facts(self):
        x=story(2)
        x["scene_map"][0]["factual_intent"]=["k2"]
        x["visual_language"]["voice"]=dict(x["voice"],
            scene_map=x.pop("scene_map"),last_image=x.pop("last_image"),
            production_unknowns=x.pop("production_unknowns"))
        x.pop("voice")
        corrected=normalize_spine_layout(x)
        with self.assertRaisesRegex(ValueError,"nonexistent owner facts"):
            validate_spine(corrected,{"identity"})

    def test_deep_nested_conflicts_are_rejected(self):
        x=story(1)
        x["visual_language"]["voice"]=dict(x["voice"],scene_map=[{"id":"other"}])
        with self.assertRaisesRegex(ValueError,"Conflicting director-authored scene_map"):
            normalize_spine_layout(x)

    def test_invented_ids_only_repaired_by_model_grounded_in_exact_owner_quotes(self):
        x=story(3)
        x["scene_map"][0]["factual_intent"]=["k2"]
        x["scene_map"][2]["factual_intent"]=["k2"]
        before=[dict(b) for b in x["scene_map"]]
        seen=[]
        def invoke(stage,prompt,data,tokens,temp):
            seen.append(stage)
            self.assertEqual(data["invalid_ids"],["k2"])
            beat=data["current_beat"]
            return {"id":beat["id"],
                    "dramatic_action":"Fictional travelling artist writes down an idea",
                    "visual_goal":"Explicitly conceptual hand-lettering, no actual product photo",
                    "factual_intent":["identity"],
                    "fact_quotes":{"identity":"Real notebook"},
                    "reason":"Only the notebook identity is established"}
        revised=reground_invalid_beats(x,{"facts":{"identity":"Real notebook"}},invoke)
        self.assertEqual(seen,["fact-repair-001","fact-repair-003"])
        self.assertEqual(len(revised["scene_map"]),3)
        self.assertEqual(revised["scene_map"][0]["factual_intent"],["identity"])
        self.assertEqual(revised["scene_map"][1],before[1])
        self.assertEqual(x["scene_map"],before)
        self.assertEqual(len(validate_spine(revised,{"identity"})),3)

    def test_grounding_cannot_relabel_invented_evidence_or_silent_delete_beat(self):
        x=story(1)
        x["scene_map"][0]["factual_intent"]=["k2"]
        def attempt(stage, system, context, tokens, temp):
            return {"id":"scene_0","dramatic_action":"Scene",
                    "visual_goal":"Visible act","factual_intent":["identity"],
                    "fact_quotes":{"identity":"Invented description"},
                    "reason":"Claimed"}
        with self.assertRaisesRegex(ValueError,"prove every owner fact"):
            reground_invalid_beats(x,{"facts":{"identity":"Real notebook"}},attempt)
        def wrong_scene(stage, system, context, tokens, temp):
            v=attempt(stage,system,context,tokens,temp)
            v["id"]="other"
            return v
        with self.assertRaisesRegex(ValueError,"replaced authored"):
            reground_invalid_beats(x,{"facts":{"identity":"Real notebook"}},wrong_scene)

    def test_model_can_revise_existing_continuity_and_audio_without_extra_facts(self):
        x=story(1)
        x["scene_map"][0]["factual_intent"]=["k2"]
        def revise(stage,prompt,context,tokens,temp):
            return {"id":"scene_0","dramatic_action":"Conceptual writing",
                    "visual_goal":"A specific purposeful filmed action",
                    "factual_intent":[],
                    "fact_quotes":{},
                    "reason":"Avoid unsupported actual product texture",
                    "continuity_in":"A human hand enters",
                    "continuity_out":"The shot connects to a written line",
                    "sound_goal":"Quiet paper scratching"}
        repaired=reground_invalid_beats(x,{"facts":{"identity":"Pocket paper notebook"}},revise)
        self.assertEqual(repaired["scene_map"][0]["sound_goal"],"Quiet paper scratching")
        self.assertEqual(repaired["scene_map"][0]["factual_intent"],[])
        self.assertEqual(x["scene_map"][0]["factual_intent"],["k2"])

    def test_exact_quoted_owner_fact_can_restore_omitted_parallel_id(self):
        x=story(1)
        x["scene_map"][0]["factual_intent"]=["k2"]
        def result(stage,prompt,data,tokens,temp):
            return {"id":"scene_0",
                "dramatic_action":"Genuinely staged notebook writing",
                "visual_goal":"Purposeful conceptual close shot",
                "factual_intent":[],"fact_quotes":{"identity":"Real notebook"},
                "reason":"The only known fact is that this is a notebook"}
        fixed=reground_invalid_beats(x,{"facts":{"identity":"Real notebook"}},result)
        self.assertEqual(fixed["scene_map"][0]["factual_intent"],["identity"])
        self.assertEqual(x["scene_map"][0]["factual_intent"],["k2"])

    def test_quote_without_source_key_cannot_be_invented(self):
        x=story(1);x["scene_map"][0]["factual_intent"]=["k2"]
        def result(stage,prompt,data,tokens,temp):
            return {"id":"scene_0",
                "dramatic_action":"A stage movement","visual_goal":"A camera shot",
                "factual_intent":[],
                "fact_quotes":{"k2":"Real notebook"},
                "reason":"Looks plausible"}
        with self.assertRaisesRegex(ValueError,"prove every owner fact"):
            reground_invalid_beats(x,{"facts":{"identity":"Real notebook"}},result)

    def test_corrupted_duration_requires_new_scene_direction_not_silent_cast(self):
        x=story(3)
        approved_duration=x["scene_map"][0]["duration_seconds"]
        approved_purpose=x["scene_map"][0]["purpose"]
        calls=[]
        def run(stage, system, context, tokens, temp):
            calls.append(stage)
            if stage=="spine":
                return x
            index=int(stage.rsplit("-",1)[-1])-1
            shot=actual_scene(x["scene_map"][index])
            if stage=="scene-001":
                shot["duration_seconds"]=4.5
                shot["visual"]="An unsupported physical tablet-failure claim"
                return shot
            if stage=="scene-repair-001":
                self.assertEqual(context["contract_error"],
                                 "Director-approved duration silently changed")
                self.assertEqual(context["director_approved_beat"]["duration_seconds"],
                                 approved_duration)
                shot["visual"]="A fictional subjective feeling expressed with authentic camera action"
                shot["motion"]="The scripted action unfolds over the actual director-approved duration"
                return shot
            return shot
        filmed=create_screenplay({"facts":{"identity":"Real notebook"}},{},{},run)
        self.assertEqual(len(filmed["scenes"]),3)
        self.assertEqual(filmed["scenes"][0]["duration_seconds"],approved_duration)
        self.assertEqual(filmed["scenes"][0]["purpose"],approved_purpose)
        self.assertIn("scene-repair-001",calls)
        self.assertNotIn("scene-repair-002",calls)

    def test_bad_revision_remains_blocked_not_hidden_as_completed(self):
        x=story(1)
        bad=actual_scene(x["scene_map"][0])
        bad["duration_seconds"]=3
        def model(stage, system, context, tokens, temp):
            return x if stage=="spine" else dict(bad)
        with self.assertRaisesRegex(ValueError,"duration silently changed"):
            create_screenplay({"facts":{"identity":"Real notebook"}},{},{},model)

    def test_revision_cannot_change_story_or_invent_new_owner_claims(self):
        beat=story(1)["scene_map"][0]
        invalid=actual_scene(beat)
        invalid["duration_seconds"]=1.3
        def model(stage, system, context, tokens, temp):
            correction=actual_scene(beat)
            correction["fact_refs"]=["unverified_product_magic"]
            return correction
        with self.assertRaisesRegex(ValueError,"Unverified factual"):
            repair_authored_shot(invalid,beat,
                {"facts":{"identity":"Real notebook"}},story(1),None,None,
                ValueError("mismatched duration"),model,1)

    def test_only_truncation_triggers_expansion(self):
        self.assertTrue(retryable_output(ValueError("Answer was truncated")))
        self.assertFalse(retryable_output(ValueError("Made up a client fact")))

if __name__=="__main__":
    unittest.main()

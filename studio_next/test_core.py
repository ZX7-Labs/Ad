"""P1/P2 core regression tests. Uses only Python stdlib; no GPU, API, files, or voice needed."""
import unittest
from studio_next.contracts import OwnerBrief,ToolSpec,audit_proposal,normalize_verdict
from studio_next.registry import ToolCatalog
from studio_next.director import StudioDirector

def good_brief():
    return OwnerBrief(
      request="Make a thoughtful film about this new notebook, pick a visual concept freely",
      owner_facts={"name":"The product is FOLD","benefit":"Handwritten paper notebook"},
      asset_rights={"owner_photo":"original owner-supplied licensed photo"},
      preferences={"audience":"students","creative_style":"director chooses"},
      hard_limits={"money_usd":0,"rights":"no unlicensed images"})

def make_plan(scene_count=2,voice="M3",scene_seconds=(2.8,9.7)):
    return {"creative_intent":"A thought appears as handwriting on a moving paper window",
      "story":"An unfinished thought catches the viewer; actual notebook is revealed as a way to record ideas.",
      "voice_choices":[voice],
      "scenes":[{"id":f"scene_{i}","purpose":f"narrative beat {i}",
                 "duration_seconds":scene_seconds[i] if i<len(scene_seconds) else 3.7,
                 "fact_refs":["benefit"],"asset_refs":["owner_photo"]}
               for i in range(scene_count)],
      "tool_route":[{"tool_id":"safe.preview","reason":"Visualize and inspect the chosen film",
                     "inputs":{"project":"FOLD"}}]}

class QueueBrain:
    def __init__(self,actions):self.actions=list(actions);self.contexts=[]
    def decide(self,context):
        self.contexts.append(context)
        if not self.actions:raise AssertionError("Brain unexpectedly called after completed actions")
        return self.actions.pop(0)

class QueueReviewer:
    def __init__(self,decisions):self.decisions=list(decisions);self.calls=[]
    def review(self,request):
        self.calls.append(request)
        return self.decisions.pop(0)

def critic_ok():return {"approved":True,"issues":[]}
def critic_fail():return {"approved":False,"issues":[{"location":"/scenes/0","reason":"Opening is generic","repair":"Use the notebook in the hook"}]}

class TestContract(unittest.TestCase):
    def test_fact_and_asset_ledger(self):
        b=good_brief()
        self.assertEqual(b.owner_facts["benefit"],"Handwritten paper notebook")
        self.assertFalse(audit_proposal(make_plan(),b,{"safe.preview"}))
    def test_director_controls_scene_count_voice_and_length(self):
        b=good_brief()
        p=make_plan(scene_count=1,voice="F2",scene_seconds=(43.8,))
        self.assertEqual(audit_proposal(p,b,{"safe.preview"}),[])
        q=make_plan(scene_count=2,voice="original_voice_future",scene_seconds=(.8,65.4))
        self.assertEqual(audit_proposal(q,b,{"safe.preview"}),[])
    def test_missing_or_misused_fact(self):
        p=make_plan()
        p["scenes"][0]["fact_refs"]=["made_up_5x_growth"]
        self.assertIn("unknown caller fact",str(audit_proposal(p,good_brief(),{"safe.preview"})))
    def test_unlicensed_asset_fails(self):
        p=make_plan()
        p["scenes"][0]["asset_refs"]=["celebrity_video"]
        self.assertIn("no evidence of rights",str(audit_proposal(p,good_brief(),{"safe.preview"})))
    def test_unregistered_tool_fails(self):
        p=make_plan()
        p["tool_route"]=[{"tool_id":"blender.3d","reason":"Need beautiful real 3D","inputs":{}}]
        self.assertIn("unavailable",str(audit_proposal(p,good_brief(),{"safe.preview"})))
    def test_invalid_scene_duration_fails(self):
        p=make_plan()
        p["scenes"][0]["duration_seconds"]=-10
        self.assertIn("invalid duration",str(audit_proposal(p,good_brief(),{"safe.preview"})))
    def test_reviewer_rejects_empty_approval(self):
        with self.assertRaises(ValueError):
            normalize_verdict({"approved":"yes","issues":[]})
        with self.assertRaises(ValueError):
            normalize_verdict({"approved":True,"issues":[{"location":"/scenes/0","reason":"bad"}]})

class TestToolCatalog(unittest.TestCase):
    def test_discover_only_actual_runners_executable(self):
        c=ToolCatalog()
        c.register(ToolSpec("safe.preview","graphic preview","Draw a preview","read",
                            operation_schema={"required":["project"]}),
                   lambda p:{"preview":p["project"]})
        c.register(ToolSpec("blender.render","3D render","3D rendering","write",
                            status="needs_setup",resource="GPU recommended",license="GPL/verify"))
        self.assertEqual(c.executable_ids(),{"safe.preview"})
        self.assertEqual(len(c.discover()),2)
        self.assertEqual(c.invoke("safe.preview",{"project":"hi"}),{"preview":"hi"})
        with self.assertRaises(RuntimeError):
            c.invoke("blender.render",{},allowed_access={"write"})
    def test_privileged_tool_requires_permission(self):
        c=ToolCatalog()
        side_effect=[]
        c.register(ToolSpec("fs.write","File write","Write a file","write"),
                   lambda x:side_effect.append(x) or {"done":True})
        with self.assertRaises(PermissionError):
            c.invoke("fs.write",{"anything":"value"})
        self.assertEqual(side_effect,[])
    def test_missing_inputs_do_not_execute_tool(self):
        c=ToolCatalog(); side_effect=[]
        c.register(ToolSpec("safe.preview","preview","preview","read",
                            operation_schema={"required":["scene"]}),
                   lambda x:side_effect.append(x) or {"ok":True})
        with self.assertRaises(ValueError):
            c.invoke("safe.preview",{})
        self.assertEqual(side_effect,[])
    def test_no_string_code_runner(self):
        c=ToolCatalog()
        with self.assertRaises(TypeError):
            c.register(ToolSpec("shell.exec","shell","bad fake tool","read"),"rm -rf .")
    def test_invalid_tool_identifier(self):
        with self.assertRaises(ValueError):
            ToolSpec("../etc/passwd","file","unsafe","read")

class TestProducer(unittest.TestCase):
    def setUp(self):
        self.catalog=ToolCatalog()
        self.catalog.register(ToolSpec("safe.preview","preview","Safe graphics preview","read",
                      operation_schema={"required":["project"]}),lambda x:{"preview_id":"scene-1"})
    def test_ordinary_prompt_then_tool_then_complete_plan(self):
        brain=QueueBrain([{"kind":"tool","tool_id":"safe.preview","inputs":{"project":"FOLD"}},
                          {"kind":"proposal","plan":make_plan()}])
        reviewer=QueueReviewer([critic_ok()])
        result=StudioDirector(brain,reviewer,self.catalog).create(good_brief())
        self.assertEqual(result.state,"ready_for_human_review")
        self.assertEqual(len(result.trace),2)
        self.assertEqual(result.trace[0]["outcome"],"completed")
        self.assertEqual(len(reviewer.calls),1)
    def test_asks_one_important_question(self):
        q=StudioDirector(QueueBrain([{"kind":"question","question":"May I use your product photographs?"}]),
                         QueueReviewer([]),self.catalog).create(good_brief())
        self.assertEqual(q.state,"needs_input")
        self.assertIn("photographs",q.question)
    def test_creative_plan_revision_after_hard_failure(self):
        bad=make_plan()
        bad["scenes"][0]["asset_refs"]=["stolen_asset"]
        brain=QueueBrain([{"kind":"proposal","plan":bad},{"kind":"proposal","plan":make_plan()}])
        reviewer=QueueReviewer([critic_ok()])
        r=StudioDirector(brain,reviewer,self.catalog).create(good_brief())
        self.assertEqual(r.state,"ready_for_human_review")
        self.assertIn("no evidence of rights",str(brain.contexts[1]["last_validation_errors"]))
    def test_critic_revisions_continue_without_claiming_rendered(self):
        brain=QueueBrain([{"kind":"proposal","plan":make_plan()},
                          {"kind":"proposal","plan":make_plan()}])
        rev=QueueReviewer([critic_fail(),critic_ok()])
        result=StudioDirector(brain,rev,self.catalog).create(good_brief())
        self.assertEqual(result.state,"ready_for_human_review")
        self.assertIn("no rendered video",result.note)
        self.assertEqual(len(rev.calls),2)
    def test_never_invoke_paid_or_write_tool_by_default(self):
        self.catalog.register(ToolSpec("paid.video","Paid video service","Costs money","paid"),
                              lambda v:{"charge":300})
        b=QueueBrain([{"kind":"tool","tool_id":"paid.video","inputs":{}},
                      {"kind":"proposal","plan":make_plan()}])
        r=StudioDirector(b,QueueReviewer([critic_ok()]),self.catalog).create(good_brief())
        self.assertEqual(r.trace[0]["outcome"],"blocked")
        self.assertEqual(r.state,"ready_for_human_review")
    def test_exhausted_budget_blocks(self):
        b=QueueBrain([{"kind":"tool","tool_id":"not.installed","inputs":{}}]*3)
        r=StudioDirector(b,QueueReviewer([]),self.catalog,max_turns=3).create(good_brief())
        self.assertEqual(r.state,"blocked")
        self.assertEqual(len(r.trace),3)
    def test_reviewer_bad_format_not_approved(self):
        brain=QueueBrain([{"kind":"proposal","plan":make_plan()}])
        reviewer=QueueReviewer([{"approved":"great","issues":[]}])
        r=StudioDirector(brain,reviewer,self.catalog,max_turns=1).create(good_brief())
        self.assertEqual(r.state,"blocked")
        self.assertEqual(r.trace[0]["outcome"],"invalid_review")

if __name__=="__main__":
    unittest.main()

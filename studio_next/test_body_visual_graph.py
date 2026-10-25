"""Analytic pixels and native media; test callers never claim LLM inference."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
from studio_next.body_visual_graph import VisualBudget,VisualGraph,revision_impact,rgba8,sample_image


def field(name,r="0",g="0",b="0",a="1",*,uniforms=None,inputs=None):
    return {"id":name,"op":"expression","inputs":inputs or {},"params":{
        "channels":{"r":r,"g":g,"b":b,"a":a},"uniforms":uniforms or {}}}


def plan(nodes=None,*,width=32,height=24,frames=8):
    nodes=nodes or [field("art","u","v","frame/8",".75")]
    return {"version":"zx7-visual-graph/1","canvas":{"width":width,"height":height,
        "frame_rate":{"numerator":24,"denominator":1},"frames":frames,"working_space":"linear_srgb"},
        "nodes":nodes,"output":nodes[-1]["id"],"render":{"first_frame":0,"frame_count":1,
            "format":"png","rgb_range":"clip_to_sdr","audio":"separate_tracks"}}


def linear(a,b,end=7):
    return {"interpolation":"linear","keys":[{"frame":0,"value":a},{"frame":end,"value":b}]}


@unittest.skipUnless(importlib.util.find_spec("numpy"),"Native NumPy runtime required")
class NativePixelGraphTests(unittest.TestCase):
    def test_source_over_matches_independent_linear_alpha_equation(self):
        import numpy as np
        nodes=[field("red","1","0","0",".5"),field("blue","0","0","1",".25"),
            {"id":"result","op":"over","inputs":{"foreground":"red","background":"blue"},"params":{"opacity":1}}]
        pixels=VisualGraph(plan(nodes)).frame(0)
        np.testing.assert_allclose(pixels[0,0],[.5,0,.125,.625])
        decoded,_=rgba8(pixels)
        self.assertEqual(tuple(decoded[0,0]),(231,0,124,159))

    def test_bilinear_filter_uses_associated_alpha_without_dark_fringes(self):
        import numpy as np
        pixels=np.array([[[1,0,0,1],[0,0,0,0]]],dtype=np.float32)
        middle=sample_image(pixels,np.array([[1.]]),np.array([[.5]]),method="bilinear",border="transparent")
        np.testing.assert_allclose(middle[0,0],[.5,0,0,.5])
        out,_=rgba8(middle)
        self.assertEqual(tuple(out[0,0]),(255,0,0,128))

    def test_remap_and_partial_render_keep_original_clock(self):
        import numpy as np
        nodes=[field("dot","1","0","0","where((x-3.5)**2+(y-3.5)**2 < 1,1,0)"),
            {"id":"moved","op":"remap","inputs":{"image":"dot"},"params":{"x":"x-offset","y":"y",
                "uniforms":{"offset":linear(0,7)},"filter":"bilinear","border":"transparent"}}]
        graph=VisualGraph(plan(nodes));start,end=graph.frame(0),graph.frame(7)
        self.assertEqual(tuple(np.argwhere(start[...,3]>.9)[0]),(3,3))
        self.assertEqual(tuple(np.argwhere(end[...,3]>.9)[0]),(3,10))
        revised=copy.deepcopy(graph.plan);revised["render"]["first_frame"]=7
        np.testing.assert_array_equal(VisualGraph(revised).frame(7),end)

    def test_authored_kernel_changes_real_pixels(self):
        import numpy as np
        nodes=[field("dot","1","0","0","where((x-3.5)**2+(y-3.5)**2 < 1,1,0)"),
            {"id":"blur","op":"convolve","inputs":{"image":"dot"},"params":{
                "kernel_x":[1,2,1],"kernel_y":[1,2,1],"divisor":16,"border":"transparent"}}]
        result=VisualGraph(plan(nodes)).frame(0)
        self.assertAlmostEqual(float(result[...,3].sum()),1)
        self.assertAlmostEqual(float(result[3,3,3]),.25)
        self.assertAlmostEqual(float(result[2,2,3]),.0625)
        self.assertEqual(int(np.count_nonzero(result[...,3])),9)

    def test_new_formula_is_not_bound_to_named_effects(self):
        import numpy as np
        graph=VisualGraph(plan([field("pattern","clamp(.5+.5*sin(u*frequency+time),0,1)","u*v","sqrt(v)",
            uniforms={"frequency":linear(3,31)})]))
        self.assertGreater(float(np.mean(np.abs(graph.frame(0)-graph.frame(7)))),.08)

    def test_branch_revision_reports_only_changed_dependencies(self):
        nodes=[field("left","u"),field("right","v"),{"id":"combined","op":"over",
            "inputs":{"foreground":"left","background":"right"},"params":{"opacity":.5}}]
        before=plan(nodes);after=copy.deepcopy(before)
        after["nodes"][0]["params"]["channels"]["r"]="u*u"
        impact=revision_impact(before,after)
        self.assertEqual(impact["changed_or_dependent_nodes"],["combined","left"])
        self.assertEqual(impact["unchanged_project_nodes"],["right"])
        self.assertFalse(impact["physical_cache_reuse_verified"])
        after["nodes"].reverse()
        self.assertEqual(impact,revision_impact(before,after))

    def test_invalid_math_alpha_references_cycles_and_resources_fail(self):
        for expression,alpha in (("sqrt(-1)","1"),("1/0","1"),("1","2")):
            with self.assertRaises(ValueError):VisualGraph(plan([field("bad",expression,a=alpha)])).frame(0)
        for target in ("missing","a"):
            with self.assertRaises(ValueError):VisualGraph(plan([field("a","source_r",inputs={"source":target})]))
        with self.assertRaisesRegex(ValueError,"budget"):VisualGraph(plan(),budget=VisualBudget(max_pixels=5))
        with self.assertRaisesRegex(ValueError,"memory budget"):VisualGraph(plan(),budget=VisualBudget(max_live_bytes=8)).frame(0)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and importlib.util.find_spec("numpy")
                    and importlib.util.find_spec("PIL"),"Native image and media engines required")
class RealVisualGraphTests(unittest.TestCase):
    def render(self,root,document,name):
        from studio_next.body_visual_render import render_visual_graph
        source=root/(name+".json");source.write_text(json.dumps(document))
        suffix=".png" if document["render"]["format"]=="png" else ".mov"
        return render_visual_graph(source,root,root/"vault",root/(name+suffix))

    def source(self,root,file,mime):
        from studio_next.media_vault import MediaVault
        ref=MediaVault(root/"vault").ingest(file,mime=mime,rights="owner_supplied",source_type="owner_upload",
            source_id=file.name,evidence="Physically generated test source",owner_or_generator="test-owner")
        return {"source":file.name,"asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"]}

    def test_motion_exact_rgba_and_partial_original_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);doc=plan();doc["render"].update(format="rgba_mov",frame_count=8)
            full=self.render(root,doc,"full")
            doc["render"].update(first_frame=3,frame_count=3);excerpt=self.render(root,doc,"excerpt")
            self.assertTrue(full["decoded_rgba_exact"])
            self.assertEqual(full["rendered_frame_pixel_sha256"][3:6],excerpt["rendered_frame_pixel_sha256"])
            self.assertEqual(excerpt["original_first_frame"],3)

    def test_real_source_video_reverse_and_hold_preserve_exact_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=plan();original["render"].update(format="rgba_mov",frame_count=8)
            produced=self.render(root,original,"source")
            media=self.source(root,Path(produced["path"]),"video/quicktime")
            reverse=plan([{"id":"footage","op":"source","inputs":{},"params":{
                "media":media,"kind":"video","color_space":"srgb","frame":linear(7,0)}}])
            reverse["render"].update(format="rgba_mov",frame_count=8)
            result=self.render(root,reverse,"reverse")
            self.assertEqual(result["rendered_frame_pixel_sha256"],list(reversed(produced["rendered_frame_pixel_sha256"])))
            reverse["nodes"][0]["params"]["frame"]=4;hold=self.render(root,reverse,"hold")
            self.assertEqual(hold["rendered_frame_pixel_sha256"],[produced["rendered_frame_pixel_sha256"][4]]*8)

    def test_photo_channel_edit_and_source_integrity(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/"photo.png";Image.new("RGBA",(32,24),(0,255,0,128)).save(file)
            media=self.source(root,file,"image/png")
            nodes=[{"id":"photo","op":"source","inputs":{},"params":{"media":media,"kind":"image","color_space":"srgb","frame":0}},
                field("changed","photo_g","photo_r","photo_b","photo_a",inputs={"photo":"photo"})]
            result=self.render(root,plan(nodes),"recolored")
            with Image.open(result["path"]) as image:self.assertEqual(image.getpixel((12,10)),(255,0,0,128))
            with Image.open(file) as image:self.assertEqual(image.getpixel((12,10)),(0,255,0,128))
            file.write_bytes(b"replaced-source")
            with self.assertRaises(ValueError):self.render(root,plan(nodes),"rejected")

    def test_source_mutation_during_actual_render_never_publishes(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"owned.png";Image.new("RGBA",(32,24),(1,50,100,255)).save(source)
            media=self.source(root,source,"image/png")
            doc=plan([{"id":"image","op":"source","inputs":{},"params":{
                "media":media,"kind":"image","color_space":"srgb","frame":0}}])
            actual=VisualGraph.frame
            def changed(graph,*args,**kwargs):
                pixels=actual(graph,*args,**kwargs);source.write_bytes(b"modified-after-decoding");return pixels
            with patch.object(VisualGraph,"frame",changed),self.assertRaisesRegex(ValueError,"changed"):
                self.render(root,doc,"must-not-publish")
            self.assertFalse((root/"must-not-publish.png").exists())

    def test_revisions_keep_original_output_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);doc=plan();first=self.render(root,doc,"original");old=Path(first["path"]).read_bytes()
            changed=copy.deepcopy(doc);changed["nodes"][0]["params"]["channels"]["r"]="1-u"
            revised=self.render(root,changed,"revision")
            self.assertNotEqual(first["sha256"],revised["sha256"])
            self.assertEqual(Path(first["path"]).read_bytes(),old)
            with self.assertRaises(ValueError):self.render(root,doc,"original")

    def test_model_facing_author_submit_render_and_generated_custody(self):
        from studio_next.body_service import LocalBodyCoordinator
        from studio_next.body_signal import BodyAuthority,LiveBodySignal
        with tempfile.TemporaryDirectory() as home:
            c=LocalBodyCoordinator(home)
            try:
                root=c._workspace("visual-project");root.mkdir(parents=True,exist_ok=True)
                brain=LiveBodySignal(c,authority=BodyAuthority(workspace_ids=frozenset({"visual-project"}),
                    operations=frozenset({"author_plan","submit"}),tool_access=frozenset({"read","write"})))
                self.assertEqual(brain.describe("visual-project","body.visual_graph")["status"],"ready_to_preflight")
                authored=brain.command("author_plan",{"workspace_id":"visual-project","tool_id":"body.visual_graph","document":plan()})
                project={"project":{"creative_intent":"Editable native graph proof"},"shots":[{"id":"image","purpose":"Authored pixels"}],
                    "tool_graph":[{"id":"image","tool_id":"body.visual_graph","purpose":"Real render",
                    "inputs":{"plan":authored["path"],"out":"native.png"},"depends_on":[]},
                    {"id":"custody","tool_id":"body.asset_vault","purpose":"Retain genuine output",
                    "inputs":{"source_witness":{"$node_output":"image"}},"depends_on":["image"]}]}
                job=brain.command("submit",{"workspace_id":"visual-project","film_ir":project});deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    observed=brain.observe(job["job_id"])
                    if observed["job_state"] in ("completed","failed","blocked"):break
                    time.sleep(.04)
                self.assertEqual(observed["job_state"],"completed",observed)
                self.assertTrue((root/"native.png").is_file())
            finally:c.close()

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
from .body_visual_graph import VisualBudget,VisualGraph,revision_impact,rgba8,sample_image


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

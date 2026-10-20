import unittest
from studio_next.capability_routing import resolve_routes
from studio_next.contracts import ToolSpec
from studio_next.registry import ToolCatalog


def catalog(*toolrows):
    c=ToolCatalog()
    for name,capability,license,status in toolrows:
        c.register(ToolSpec(name,capability,"Trusted dummy test engine","read",
                            status=status,license=license,resource="test only"),
                   (lambda _: {"verified":True}) if status=="installed" else None)
    return c


def film(n=3):
    shots=[{"id":f"scene{i}","purpose":"Unrestricted director choice"} for i in range(n)]
    return {"shots":shots,"production_requirements":[
        {"id":"opening","shot_ids":["scene0"],
         "alternatives":[["visual.true_3d","camera.3d"]]},
        {"id":"finish","shot_ids":[shots[-1]["id"]],
         "alternatives":[["edit.timeline"]]}
    ]}


class CapabilityRoutingTests(unittest.TestCase):
    def setUp(self):
        self.c = catalog(("blender.scene","visual.true_3d","GPL-3.0-or-later","installed"),
                         ("blender.camera","camera.3d","GPL-3.0-or-later","installed"),
                         ("ffmpeg.edit","edit.timeline","GPL-3.0-or-later","installed"),
                         ("flat.vector","visual.2d","MIT","installed"))
        self.allowed=frozenset({"blender.scene","blender.camera","ffmpeg.edit","flat.vector"})

    def route(self, p, c=None, ids=None):
        return resolve_routes(p,c or self.c,trusted_free_tool_ids=ids or self.allowed)

    def test_renders_3d_as_3d_and_edits_in_same_film(self):
        r=self.route(film())
        self.assertTrue(r.executable)
        self.assertEqual(r.routes[0].capabilities,("visual.true_3d","camera.3d"))
        self.assertEqual(set(r.routes[0].tool_ids),{"blender.scene","blender.camera"})
        self.assertEqual(r.routes[1].tool_ids,("ffmpeg.edit",))

    def test_if_3d_unavailable_never_substitutes_flat_cards(self):
        c=catalog(("flat.vector","visual.2d","MIT","installed"))
        r=self.route(film(),c,{"flat.vector"})
        self.assertFalse(r.executable)
        self.assertEqual(r.unresolved[0]["unmet_options"][0]["missing_capabilities"],
                         ["visual.true_3d","camera.3d"])

    def test_only_director_proposed_alternatives_allowed(self):
        p=film()
        p["production_requirements"][0]["alternatives"].append(["visual.2d"])
        c=catalog(("flat.vector","visual.2d","MIT","installed"),
                  ("ffmpeg.edit","edit.timeline","GPL-3.0-or-later","installed"))
        r=self.route(p,c,{"flat.vector","ffmpeg.edit"})
        self.assertTrue(r.executable)
        self.assertEqual(r.routes[0].alternative_index,1)

    def test_unknown_cost_license_and_uninstalled_are_not_runnable(self):
        c=catalog(("wild.engine","visual.true_3d","not-reviewed","installed"),
                  ("missing.cam","camera.3d","MIT","needs_setup"))
        r=self.route(film(),c,{"wild.engine","missing.cam"})
        self.assertFalse(r.executable)

    def test_tool_requires_explicit_free_cost_evidence(self):
        r=self.route(film(),self.c,{"blender.scene","blender.camera"})
        self.assertFalse(r.executable)
        self.assertEqual(r.unresolved[1]["unmet_options"][0]["missing_capabilities"],
                         ["edit.timeline"])

    def test_nonstandard_freeform_capabilities_not_hardcoded(self):
        p={"shots":[{"id":"a","purpose":"Wonder"}],
           "production_requirements":[{"id":"r","shot_ids":["a"],
           "alternatives":[["volumetric.octree.ribbon"]]}]}
        c=catalog(("engine.new","volumetric.octree.ribbon","MIT","installed"))
        self.assertTrue(self.route(p,c,{"engine.new"}).executable)

    def test_not_a_fixed_short_or_shot_count(self):
        for count in (1,7,130):
            p=film(count)
            self.assertEqual(len(p["shots"]),count)
            self.assertTrue(self.route(p).executable)

    def test_malformed_targets_and_routes_fail_closed(self):
        p=film()
        p["production_requirements"][0]["shot_ids"]=["fake"]
        with self.assertRaises(ValueError):self.route(p)
        p=film()
        p["production_requirements"][0]["alternatives"]=[]
        with self.assertRaises(ValueError):self.route(p)
        p=film()
        p["production_requirements"][0]["alternatives"]=[["visual.true_3d","visual.true_3d"]]
        with self.assertRaises(ValueError):self.route(p)

    def test_zero_capability_is_not_proof_of_video(self):
        r=self.route(film())
        self.assertIn("not a video",r.claim)


if __name__=="__main__":
    unittest.main()

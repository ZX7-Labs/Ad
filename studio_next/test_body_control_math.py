import importlib.util
import unittest
from .body_animation import curve_value, validate_curve
from .body_pixel_math import BASE_VARIABLES, PixelExpression


class ArtistControlMathTests(unittest.TestCase):
    def test_independent_cubic_tangents_and_original_clock(self):
        curve={"interpolation":"cubic_hermite","keys":[
            {"frame":2,"value":4,"in_slope":0,"out_slope":2},
            {"frame":6,"value":8,"in_slope":-1,"out_slope":0}]}
        validate_curve(curve)
        self.assertEqual(curve_value(curve,-1),4)
        self.assertEqual(curve_value(curve,9),8)
        self.assertAlmostEqual(curve_value(curve,4),7.5)
        curve["keys"][1]["in_slope"]=3
        self.assertAlmostEqual(curve_value(curve,4),5.5)
        curve["keys"][1]["frame"]=2
        with self.assertRaises(ValueError):validate_curve(curve)

    def test_math_is_creative_data_not_executable_python(self):
        for text in ("__import__('os').system('true')","x.__class__","x[0]",
                     "[x for x in y]","open('secret')","lambda:0","True","1e999","sin(x,y)"):
            with self.subTest(text=text),self.assertRaises(ValueError):
                PixelExpression(text,BASE_VARIABLES)

    @unittest.skipUnless(importlib.util.find_spec("numpy"),"Native numeric runtime required")
    def test_authored_mathematical_field_and_invalid_values(self):
        import numpy as np
        expression=PixelExpression("where(x < .5, x*x, 1-x)",BASE_VARIABLES)
        np.testing.assert_allclose(expression.evaluate({"x":np.array([.25,.75],dtype=np.float32)}),[.0625,.25])
        for text in ("1/0","sqrt(-1)"):
            with self.assertRaises(ValueError):PixelExpression(text,BASE_VARIABLES).evaluate({})

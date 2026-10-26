import importlib.util
import unittest
from studio_next.body_render_compare import compare_native_rgb_arrays


@unittest.skipUnless(importlib.util.find_spec('numpy'),'Actual RGB numeric arrays required')
class NativePictureAgreement(unittest.TestCase):
    def test_identical_picture_has_zero_difference(self):
        import numpy as np
        a=np.full((64,64,3),100,dtype=np.uint8);r=compare_native_rgb_arrays(a,a)
        self.assertTrue(r['pixels_identical']);self.assertTrue(r['within_quantization_tolerance'])

    def test_one_sparse_code_value_is_reported_without_claiming_identical_pixels(self):
        import numpy as np
        a=np.full((128,128,3),100,dtype=np.uint8);b=a.copy();b[12,35,1]+=1
        r=compare_native_rgb_arrays(a,b)
        self.assertFalse(r['pixels_identical']);self.assertTrue(r['within_quantization_tolerance'])
        self.assertEqual(r['differing_pixels'],1);self.assertEqual(r['max_channel_difference'],1)

    def test_a_two_code_value_change_is_never_roundoff(self):
        import numpy as np
        a=np.full((128,128,3),100,dtype=np.uint8);b=a.copy();b[12,35,1]+=2
        self.assertFalse(compare_native_rgb_arrays(a,b)['within_quantization_tolerance'])

    def test_global_colour_change_and_moving_shape_are_rejected(self):
        import numpy as np
        a=np.full((64,64,3),100,dtype=np.uint8)
        self.assertFalse(compare_native_rgb_arrays(a,a+1)['within_quantization_tolerance'])
        a=np.zeros((64,64,3),dtype=np.uint8);a[20:40,20:40]=255;b=np.roll(a,1,axis=1)
        self.assertFalse(compare_native_rgb_arrays(a,b)['within_quantization_tolerance'])

    def test_wrong_dimensions_and_float_data_cannot_use_the_rgb_budget(self):
        import numpy as np
        a=np.zeros((64,64,3),dtype=np.uint8)
        with self.assertRaises(ValueError):compare_native_rgb_arrays(a,a[:20])
        with self.assertRaises(ValueError):compare_native_rgb_arrays(a.astype(float),a.astype(float))

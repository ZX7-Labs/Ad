import unittest
from studio_next.execute_film import validate_delivery,verify_rendered_shot_duration


class DeliveryIntentTests(unittest.TestCase):
    def test_real_render_must_keep_director_chosen_timing(self):
        shot={"id":"unbounded_creative_beat","duration_seconds":86.0}
        passed=verify_rendered_shot_duration(shot,86.04,24)
        self.assertEqual(passed["intended_seconds"],86.0)
        with self.assertRaisesRegex(RuntimeError,"repair this specific production shot"):
            verify_rendered_shot_duration(shot,92.7,24)

    def test_rendered_pacing_rejects_nan_and_invented_zero(self):
        with self.assertRaises(ValueError):
            verify_rendered_shot_duration({"id":"x","seconds":8.0},
                                           float("nan"),24)
        with self.assertRaises(ValueError):
            verify_rendered_shot_duration({"id":"x","seconds":0},1,24)

    def test_no_limit_to_one_frame_shape_or_voice(self):
        for width,height in [(3840,2160),(1080,1920),(2560,1080)]:
            x={"format":{"width":width,"height":height,"fps":24,
                "framing":"fit","background":"#05090A"},
                "voice":"M3","reason":"Chosen to serve a specific audience"}
            t={"voice":{"choice":"M3"},
               "scenes":[{"id":"a","purpose":"Story beat","narration":"Speak"}]}
            self.assertEqual(validate_delivery(x,t),x)

    def test_reject_fabricated_silent_voice(self):
        x={"format":{"width":720,"height":1280,"fps":24,
            "framing":"fit","background":"#151515"},
            "voice":"no_voice","reason":"Purposely quiet"}
        t={"scenes":[{"id":"a","purpose":"Only meaningful silence",
                     "narration":"This must be spoken"}]}
        with self.assertRaisesRegex(ValueError,"discard narrated"):
            validate_delivery(x,t)

    def test_voice_identity_preserved(self):
        x={"format":{"width":1280,"height":720,"fps":30,
            "framing":"fill","background":"#FAFAFA"},
            "voice":"F2","reason":"A thoughtful female performance"}
        t={"voice":{"choice":"M3"},
           "scenes":[{"id":"a","purpose":"Intent","narration":"Hi"}]}
        with self.assertRaisesRegex(ValueError,"change director-selected"):
            validate_delivery(x,t)


if __name__=="__main__":
    unittest.main()

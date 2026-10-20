import unittest
from studio_next.execute_film import validate_delivery


class DeliveryIntentTests(unittest.TestCase):
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

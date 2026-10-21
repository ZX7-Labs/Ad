import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.delivery_audit import _probe_details,audit_delivered_movie


def real_streams():
    return {"streams":[{"codec_type":"video","codec_name":"h264",
                    "width":2048,"height":858},
                       {"codec_type":"audio","codec_name":"aac"}],
            "format":{"duration":"8.208"}}


class EncodedDeliveryQualityEvidenceTests(unittest.TestCase):
    def test_real_probe_is_not_artist_praise(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"actual-film.mp4"
            p.write_bytes(b"actual original encoded bytes"*40)
            with patch("studio_next.delivery_audit.subprocess.check_output",
                       return_value=json.dumps(real_streams()).encode()):
                check=audit_delivered_movie(p,output=root,expected={
                    "width":2048,"height":858,"duration_seconds":8.2,
                    "audio_required":True})
                self.assertTrue(check["render_contract_verified"])
                self.assertFalse(check["visual_aesthetics_reviewed"])
                self.assertFalse(check["audio_mix_listened_to"])

    def test_creator_can_deliberately_make_silent_black_or_wide_film(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"film.mp4"
            p.write_bytes(b"independent creative film"*100)
            data=real_streams()
            data["streams"]=data["streams"][:1]
            with patch("studio_next.delivery_audit.subprocess.check_output",
                       return_value=json.dumps(data).encode()):
                record=audit_delivered_movie(p,expected={
                    "width":2048,"height":858,"audio_required":False})
                self.assertTrue(record["render_contract_verified"])
                self.assertFalse(record["observed"]["audio_stream_present"])

    def test_true_mismatches_not_silently_called_done(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"film.mp4";p.write_bytes(b"physical video"*100)
            with patch("studio_next.delivery_audit.subprocess.check_output",
                       return_value=json.dumps(real_streams()).encode()):
                result=audit_delivered_movie(p,expected={"width":1080,
                    "height":1920,"audio_required":True,
                    "duration_seconds":22.0})
                self.assertEqual(len(result["violations"]),3)
                self.assertFalse(result["render_contract_verified"])

    def test_no_fake_shortcut_for_unavailable_movie(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"physical"):
                audit_delivered_movie(Path(root)/"not-created.mp4")
            file=Path(root)/"not-a-movie.mp4"
            file.write_bytes(b"x"*2048)
            with patch("studio_next.delivery_audit.subprocess.check_output",
                       return_value=b'{"streams":[],"format":{"duration":"9"}}'):
                with self.assertRaisesRegex(ValueError,"video stream"):
                    audit_delivered_movie(file)

if __name__=="__main__":unittest.main()

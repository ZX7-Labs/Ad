"""Real NTSC media may never be silently interpreted as an integer-FPS clock."""
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from studio_next.media_vault import MediaVault,sha256_file
from studio_next.precision_retime import plan_retime,render_retime,_source_timebase


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"Actual rational source frames required")
class ExactRetimeSourceClockTests(unittest.TestCase):
    def test_real_fractional_clocks_reject_rounded_labels_and_accept_equivalent_rationals(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);vault=MediaVault(root/"vault")
            for integer in (24,30,60):
                source=root/(str(integer)+"-fractional.mp4")
                numerator=integer*1000
                subprocess.run(["ffmpeg","-v","error","-nostdin","-f","lavfi","-i",
                    f"testsrc2=size=64x48:rate={numerator}/1001","-frames:v","12",
                    "-c:v","libx264","-pix_fmt","yuv420p",str(source)],check=True,timeout=40)
                record=vault.ingest(source,mime="video/mp4",rights="owner_supplied",
                    source_type="owner_upload",source_id=str(integer)+"-rational-clock",
                    evidence="Actual CFR encoded rational-clock fixture",owner_or_generator="test")
                plan={"source":"zx7:sha256:"+record["asset_id"],"asset_id":record["asset_id"],
                    "attestation_id":record["attestation_id"],
                    "source_fps":{"numerator":integer,"denominator":1},
                    "segments":[{"first_frame":0,"end_frame":12,"speed":{"numerator":1,"denominator":1}}],
                    "audio":"intentional_silence"}
                original=sha256_file(source)
                with self.subTest(clock=integer),self.assertRaisesRegex(ValueError,"exact original frame timebase"):
                    plan_retime(plan,root,root/"vault")
                bad=root/(str(integer)+"-bad.json");bad.write_text(json.dumps(plan))
                dest=root/(str(integer)+"-unapproved.mp4")
                with self.assertRaisesRegex(ValueError,"exact original frame timebase"):
                    render_retime(bad,root,root/"vault",dest)
                self.assertFalse(dest.exists())
                plan["source_fps"]={"numerator":numerator*2,"denominator":2002}
                valid=plan_retime(plan,root,root/"vault")
                self.assertEqual(valid["fps"],Fraction(numerator,1001))
                self.assertEqual(valid["expected_seconds"],float(Fraction(12*1001,numerator)))
                self.assertEqual(sha256_file(source),original)
                if integer==30:
                    exact=root/"exact.json";exact.write_text(json.dumps(plan))
                    out=root/"accepted-original-clock.mp4"
                    render_retime(exact,root,root/"vault",out)
                    self.assertEqual(_source_timebase(out),(Fraction(30000,1001),12))


if __name__=="__main__":unittest.main()

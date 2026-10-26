import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from studio_next.media_recovery import render_resumable
from studio_next.media_body import RenderError


def generate(path, color):
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
        '-f','lavfi','-i',f'color=c={color}:s=64x64:d=1:r=12',
        '-an','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)


class RecoveryTests(unittest.TestCase):
    def test_recovery_checks_real_media_content_and_corrupted_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);asset=root/'scene.mp4';out=root/'video.mp4'
            generate(asset,'red')
            plan={'canvas':{'width':64,'height':64,'fps':12,'duration':1},
                  'clips':[{'kind':'video','path':'scene.mp4','timeline_start':0,
                            'duration':1}]}
            initial=render_resumable(plan,asset_root=root,output_path=out)
            self.assertFalse(initial['reused'])
            again=render_resumable(copy.deepcopy(plan),asset_root=root,output_path=out)
            self.assertTrue(again['reused'])
            self.assertEqual(initial['input_fingerprint'],again['input_fingerprint'])
            original=out.read_bytes()
            generate(asset,'blue')
            changed=render_resumable(plan,asset_root=root,output_path=out)
            self.assertFalse(changed['reused'])
            self.assertNotEqual(initial['input_fingerprint'],changed['input_fingerprint'])
            self.assertNotEqual(original,out.read_bytes())
            out.write_bytes(b'corrupted!')
            restored=render_resumable(plan,asset_root=root,output_path=out)
            self.assertFalse(restored['reused'])
            self.assertGreater(out.stat().st_size,200)

    def test_malformed_plan_never_hits_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);asset=root/'scene.mp4';generate(asset,'red')
            plan={'canvas':{'width':64,'height':64,'fps':12,'duration':1},
                  'clips':[{'kind':'video','path':'../scene.mp4','timeline_start':0,'duration':1}]}
            with self.assertRaises(RenderError):
                render_resumable(plan,asset_root=root,output_path=root/'v.mp4')

if __name__=='__main__':unittest.main()

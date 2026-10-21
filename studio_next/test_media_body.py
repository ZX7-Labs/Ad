import tempfile
from pathlib import Path
import subprocess
import unittest
from studio_next.media_body import RenderError, render_timeline


def make_file(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *map(str, args)], check=True)


class MediaBodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        make_file('-f', 'lavfi', '-i', 'color=c=red:s=64x64:d=2:r=12',
                  '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', cls.root/'source.mp4')
        make_file('-f', 'lavfi', '-i', 'color=c=blue:s=64x64:d=2:r=12',
                  '-frames:v', '1', cls.root/'graphic.png')
        make_file('-f', 'lavfi', '-i', 'sine=frequency=440:duration=2', cls.root/'voice.wav')

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def plan(self):
        return {'canvas': {'width':128,'height':128,'fps':12,'duration':2,
                           'background':'#000000'},'clips':[
            {'kind':'video','path':'source.mp4','timeline_start':0,'duration':2,
             'width':128,'height':128,'z':0},
            {'kind':'image','path':'graphic.png','timeline_start':1,'duration':1,
             'x':64,'y':64,'width':64,'height':64,'z':1},
            {'kind':'audio','path':'voice.wav','timeline_start':0.25,'duration':1.5,
             'volume':0.45,'fade_in':0.1,'fade_out':0.1}]}

    def test_real_video_visual_overlay_and_audio(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'result.mp4'
            result=render_timeline(self.plan(),asset_root=self.root,output_path=out)
            self.assertTrue(out.is_file())
            self.assertEqual(result['video_streams'],1)
            self.assertEqual(result['audio_streams'],1)
            self.assertEqual(result['input_clips'],3)
            self.assertAlmostEqual(result['seconds'],2,delta=0.12)
            frame=Path(d)/'sample.rgb'
            make_file('-ss',1.4,'-i',out,'-frames:v',1,'-f','rawvideo','-pix_fmt','rgb24',frame)
            pixels=frame.read_bytes()
            def rgb(x,y):return pixels[(y*128+x)*3:(y*128+x)*3+3]
            self.assertGreater(rgb(10,10)[0],rgb(10,10)[2])
            self.assertGreater(rgb(110,110)[2],rgb(110,110)[0])

    def test_video_only_export(self):
        p=self.plan();p['clips']=[p['clips'][0]]
        with tempfile.TemporaryDirectory() as d:
            result=render_timeline(p,asset_root=self.root,output_path=Path(d)/'v.mp4')
            self.assertEqual(result['audio_streams'],0)

    def test_invalid_and_external_assets_refused_before_render(self):
        for invalid in ('../source.mp4','/etc/passwd','https://site.example/a.mp4','bad.sh'):
            p=self.plan();p['clips'][0]['path']=invalid
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(RenderError):
                    render_timeline(p,asset_root=self.root,output_path=Path(d)/'v.mp4')

    def test_timeline_rejects_overflow_and_invalid_values(self):
        for field, value in [('duration',float('nan')),('timeline_start',-1),('duration',3)]:
            p=self.plan();p['clips'][0][field]=value
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(RenderError):
                    render_timeline(p,asset_root=self.root,output_path=Path(d)/'v.mp4')

    def test_missing_audio_track_blocks(self):
        p=self.plan();p['clips'][2]['path']='source.mp4'
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RenderError,'audio stream'):
                render_timeline(p,asset_root=self.root,output_path=Path(d)/'v.mp4')


if __name__ == '__main__': unittest.main()

class AdditionalSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        make_file('-f','lavfi','-i','color=c=red:s=64x64:d=2:r=12',
                  '-an','-c:v','libx264',cls.root/'source.mp4')

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_malformed_kind_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            plan={'canvas':{'width':64,'height':64,'fps':12,'duration':1},
                  'clips':[{'kind':[], 'path':'not-a-file.mp4',
                            'timeline_start':0,'duration':1}]}
            with self.assertRaises(RenderError):
                render_timeline(plan,asset_root=self.root,output_path=Path(d)/'v.mp4')

    def test_negative_canvas_positions_and_layer_order_are_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            plan={'canvas':{'width':64,'height':64,'fps':12,'duration':1},
                  'clips':[{'kind':'video','path':'source.mp4','timeline_start':0,
                            'duration':1, 'width':64,'height':64,'x':-12,'y':-8,'z':-2}]}
            result=render_timeline(plan,asset_root=self.root,output_path=Path(d)/'v.mp4')
            self.assertEqual(result['video_streams'],1)

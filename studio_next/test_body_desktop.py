"""Drive real Tk widgets against the real authenticated local production API."""
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_desktop import IndependentStudioDesktop
from studio_next.test_body_controls import local_service


@unittest.skipUnless(os.environ.get('DISPLAY') and shutil.which('inkscape') and
                     shutil.which('ffmpeg'), 'Actual display and render tools required')
class LiveNativeStudioDesktopTests(unittest.TestCase):
    def test_real_tool_selection_media_import_production_and_verified_download(self):
        import tkinter as tk
        errors = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with local_service(root / 'runtime') as (host, client):
                window = tk.Tk()
                app = IndependentStudioDesktop(window, client)

                def pump(predicate, timeout=15):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        window.update()
                        if predicate():
                            self.assertEqual(errors, [])
                            return
                        time.sleep(.01)
                    self.fail('Real desktop operation did not complete: ' +
                              app.status_text.get() + ' ' + str(errors))

                try:
                    with patch('tkinter.messagebox.showerror',
                               side_effect=lambda *a, **k: errors.append(str(a))):
                        pump(lambda: app.pending == 0)
                        actual = [i['tool_id'] for i in app._tools]
                        self.assertIn('body.vector_png', actual)
                        app.tools_list.selection_set(actual.index('body.vector_png'))
                        app.inspect_tool()
                        pump(lambda: app.pending == 0)
                        detail = json.loads(app.tool_detail.get('1.0', 'end'))
                        self.assertEqual(detail['tool_id'], 'body.vector_png')
                        self.assertIn('operation_schema', detail)

                        svg = root / 'original.svg'
                        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" '
                                       'width="96" height="64"><circle cx="41" '
                                       'cy="31" r="23" fill="#346da7"/></svg>')
                        app.asset_workspace.set('commission')
                        app.asset_path.set(str(svg))
                        app.asset_source_id.set('कलाकार-मूल-स्रोत')
                        app.rights.set('अपनी मूल रचना का परीक्षण')
                        app.upload()
                        pump(lambda: app.pending == 0)
                        self.assertEqual((host.projects / 'commission' /
                                          'original.svg').read_bytes(), svg.read_bytes())

                        plan = {'project': {'creative_intent': 'Original UI production'},
                                'shots': [{'id': 'one', 'purpose': 'Original artwork',
                                           'duration_seconds': 1.7}],
                                'tool_graph': [{'id': 'draw', 'tool_id': 'body.vector_png',
                                                'purpose': 'Render real original pixels',
                                                'depends_on': [],
                                                'inputs': {'source_svg': 'original.svg',
                                                           'out': 'original.png',
                                                           'width': 96, 'height': 64}}]}
                        filename = root / 'plan.json'
                        filename.write_text(json.dumps(plan))
                        app.workspace.set('commission')
                        app.film_plan.set(str(filename))
                        app.submit()
                        pump(lambda: app.pending == 0 and app.current_job is not None)
                        job = app.current_job
                        pump(lambda: client.status(job)['status'] == 'completed')
                        app.refresh_jobs()
                        pump(lambda: app.pending == 0)
                        index = next(i for i, v in enumerate(app._jobs)
                                     if v['job_id'] == job)
                        app.job_list.selection_set(index)
                        app.inspect_job()
                        pump(lambda: app.pending == 0)
                        self.assertEqual(json.loads(app.job_detail.get('1.0', 'end'))[
                            'status'], 'completed')
                        app.load_artifacts()
                        pump(lambda: app.pending == 0)
                        index = next(i for i, v in enumerate(app._artifacts)
                                     if v['path'] == 'original.png')
                        app.artifact_list.selection_set(index)
                        received = root / 'downloaded-original.png'
                        with patch('tkinter.filedialog.asksaveasfilename',
                                   return_value=str(received)):
                            app.download()
                        pump(lambda: app.pending == 0)
                        self.assertEqual(received.read_bytes(),
                                         (host.projects / 'commission' /
                                          'original.png').read_bytes())
                        self.assertEqual(errors, [])
                        window.update_idletasks()
                        self.assertTrue(app.download_button.winfo_viewable())
                        self.assertLessEqual(app.download_button.winfo_rooty() +
                                             app.download_button.winfo_height(),
                                             window.winfo_rooty() + window.winfo_height())
                        if os.environ.get('ZX7_DESKTOP_QA_PNG'):
                            from PIL import ImageGrab
                            window.update_idletasks()
                            x, y = window.winfo_rootx(), window.winfo_rooty()
                            ImageGrab.grab(bbox=(x, y, x + window.winfo_width(),
                                               y + window.winfo_height()),
                                           xdisplay=os.environ['DISPLAY']).save(
                                               os.environ['ZX7_DESKTOP_QA_PNG'])
                finally:
                    app.close()


if __name__ == '__main__':
    unittest.main()

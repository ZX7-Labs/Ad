"""Actual process-death tests of the renderer -> SQLite settlement boundary."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_service import LocalBodyCoordinator


_CHILD = r'''
import json, os, sys, time
from pathlib import Path
from unittest.mock import patch
from studio_next.body_service import LocalBodyCoordinator
root = Path(sys.argv[1])
original = json.loads((root / 'request.json').read_text())
host = LocalBodyCoordinator(root)
def die(*args, **kwargs):
    os._exit(71)
boundary = ('studio_next.durable_graph.DurableFilmGraph.complete'
            if sys.argv[2] == 'after_publish' else
            'studio_next.body_integration.os.link')
with patch(boundary, side_effect=die):
    host.submit(original, workspace_id='original', job_id='one-artwork')
    for _ in range(1000):
        time.sleep(.01)
host.close()
raise SystemExit('Expected real process-death boundary was not reached')
'''


@unittest.skipUnless(shutil.which('inkscape') and shutil.which('ffmpeg'),
                     'Real Inkscape and media decoder required for crash proof')
class PhysicalPublicationCrashTests(unittest.TestCase):
    def _prepare_and_die(self, root, boundary):
        project = root / 'projects' / 'original'
        project.mkdir(parents=True)
        (project / 'art.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="64">'
            '<rect width="96" height="64" fill="#17354d"/>'
            '<circle cx="43" cy="27" r="19" fill="#f0a218"/></svg>')
        original = {
            'project': {'creative_intent': 'Original कलाकार chooses every visual'},
            'shots': [{'id': 'one', 'purpose': 'Original commissioned artwork',
                       'duration_seconds': 1.2}],
            'tool_graph': [{'id': 'draw', 'tool_id': 'body.vector_png',
                            'purpose': 'Rasterize exact original artwork',
                            'inputs': {'source_svg': 'art.svg', 'out': 'art.png',
                                       'width': 96, 'height': 64},
                            'depends_on': []}]}
        (root / 'request.json').write_text(json.dumps(original, ensure_ascii=False))
        result = subprocess.run([sys.executable, '-c', _CHILD, str(root), boundary],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 71, result.stdout + result.stderr)
        return project, original

    def _resume_without_renderer(self, root):
        with patch('studio_next.body_integration.rasterize_original_svg',
                   side_effect=AssertionError('Recovery reran the original renderer')):
            host = LocalBodyCoordinator(root)
            try:
                self.assertEqual(host.pending_restart(), 1)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    state = host.inspect('one-artwork')
                    if state['status'] not in ('running', 'queued'):
                        break
                    time.sleep(.02)
                return state
            finally:
                host.close()

    def test_killed_after_real_png_publication_reconciles_without_rasterizing_again(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, original = self._prepare_and_die(root, 'after_publish')
            before = (project / 'art.png').read_bytes()
            state = self._resume_without_renderer(root)
            self.assertEqual(state['status'], 'completed', state)
            self.assertEqual(state['attempts'], 2)
            self.assertEqual((project / 'art.png').read_bytes(), before)
            with sqlite3.connect(root / 'body-jobs.sqlite3') as db:
                stored = db.execute('SELECT original_ir FROM jobs').fetchone()[0]
            self.assertEqual(json.loads(stored), original)
            self.assertFalse(list(project.glob('.zx7-uncommitted-*')))

    def test_killed_after_durable_receipt_before_link_publishes_the_same_staged_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, _ = self._prepare_and_die(root, 'before_publish')
            self.assertFalse((project / 'art.png').exists())
            stages = list(project.glob('.zx7-uncommitted-*'))
            self.assertEqual(len(stages), 1)
            original_pixels = stages[0].read_bytes()
            state = self._resume_without_renderer(root)
            self.assertEqual(state['status'], 'completed', state)
            self.assertEqual((project / 'art.png').read_bytes(), original_pixels)
            self.assertFalse(stages[0].exists())

    def test_changed_published_art_is_never_trusted_or_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, _ = self._prepare_and_die(root, 'after_publish')
            corrupt = b'corrupt media that must never replace original art' * 50
            (project / 'art.png').write_bytes(corrupt)
            state = self._resume_without_renderer(root)
            self.assertEqual(state['status'], 'blocked', state)
            self.assertEqual((project / 'art.png').read_bytes(), corrupt)
            self.assertIn('draw', ' '.join(state['result']['errors']))

    def test_changed_source_cannot_adopt_receipt_for_a_different_original_artwork(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, _ = self._prepare_and_die(root, 'after_publish')
            before = (project / 'art.png').read_bytes()
            source = project / 'art.svg'
            source.write_text(source.read_text().replace('#f0a218', '#b12346'))
            state = self._resume_without_renderer(root)
            self.assertEqual(state['status'], 'blocked', state)
            self.assertEqual((project / 'art.png').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

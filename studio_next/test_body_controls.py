"""Physical, authenticated pause/restart/resume proof with real artist pixels."""
import json
import shutil
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from studio_next.body_client import ZX7BodyClient
from studio_next.body_service import LocalBodyCoordinator, make_body_http_handler
from studio_next.creative_asset_ops import rasterize_original_svg


@contextmanager
def local_service(root):
    host = LocalBodyCoordinator(root)
    token = 'test-only-operator-token-' + 'x' * 48
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_body_http_handler(host, token))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        client = ZX7BodyClient(endpoint=f'http://127.0.0.1:{server.server_port}', token=token)
        yield host, client
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)
        host.close()


@unittest.skipUnless(shutil.which('inkscape') and shutil.which('ffmpeg'),
                     'Actual Inkscape/decoder required for production control proof')
class ActualProductionControlTests(unittest.TestCase):
    def _source(self, root):
        project = root / 'runtime' / 'projects' / 'commission'
        project.mkdir(parents=True)
        (project / 'original.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="64">'
            '<path fill="#7a2" d="M0 0H96V64H0Z"/>'
            '<circle cx="37" cy="24" r="15" fill="#a32"/></svg>')
        plan = {
            'project': {'creative_intent': 'A distinct original artist commission'},
            'shots': [{'id': 'one', 'purpose': 'Artist decides exact composition',
                       'duration_seconds': 9.13}],
            'tool_graph': [
                {'id': 'draw', 'tool_id': 'body.vector_png', 'depends_on': [],
                 'purpose': 'Encode the original commissioned vector artwork',
                 'inputs': {'source_svg': 'original.svg', 'out': 'original.png',
                            'width': 96, 'height': 64}},
                {'id': 'custody', 'tool_id': 'body.inspect', 'depends_on': ['draw'],
                 'purpose': 'Independently inspect actual rendered artist pixels',
                 'inputs': {'source': 'original.png'}}]}
        filename = root / 'film.json'
        filename.write_text(json.dumps(plan))
        return project, filename

    def _stop_during_real_tool(self, root, action):
        project, filename = self._source(root)
        encoded = threading.Event()
        release = threading.Event()

        def real_controlled_render(*args, **kwargs):
            result = rasterize_original_svg(*args, **kwargs)
            encoded.set()
            if not release.wait(10):
                raise RuntimeError('Test failed to release genuine encoder')
            return result

        with patch('studio_next.body_integration.rasterize_original_svg',
                   side_effect=real_controlled_render) as physical:
            with local_service(root / 'runtime') as (host, client):
                job = client.submit(filename, 'commission')['job_id']
                try:
                    self.assertTrue(encoded.wait(10), client.status(job))
                    receipt = getattr(client, action)(job)
                    self.assertEqual(receipt['requested_action'], action)
                    during = client.status(job)
                    self.assertEqual(during['status'], 'running')
                    self.assertEqual(during['requested_action'], action)
                    self.assertFalse((project / 'original.png').exists())
                    # No half-encoded source or private receipt can leak through
                    # the real artifact browser while the renderer is stopped.
                    self.assertFalse(any('.zx7-' in x['path']
                                         for x in client.artifacts(job)['assets']))
                    stage = next(project.glob('.zx7-uncommitted-*'))
                    with self.assertRaises(ValueError):
                        host.inspect_media(job, stage.name)
                finally:
                    release.set()
                stopped = client.wait(job, poll_seconds=.1, max_seconds=10)
                expected = 'paused' if action == 'pause' else 'cancelled'
                self.assertEqual(stopped['status'], expected, stopped)
                self.assertTrue(stopped['result']['stopped_at_verified_tool_boundary'])
                self.assertEqual(stopped['result']['completed'], ['draw'])
                self.assertEqual(stopped['result']['next_node'], 'custody')
                self.assertEqual(physical.call_count, 1)
                before = (project / 'original.png').read_bytes()
                backup = host.create_recovery_snapshot(root / 'paused-body.tar.gz')
                self.assertGreater(backup['files'], 3)
        return project, job, before

    def test_pause_persists_across_host_restart_then_resumes_only_unfinished_custody(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, job, original_pixels = self._stop_during_real_tool(root, 'pause')
            with patch('studio_next.body_integration.rasterize_original_svg',
                       side_effect=AssertionError('Completed art must not be regenerated')):
                with local_service(root / 'runtime') as (host, client):
                    self.assertEqual(host.pending_restart(), 0)
                    self.assertEqual(client.status(job)['status'], 'paused')
                    client.resume(job)
                    done = client.wait(job, poll_seconds=.1, max_seconds=10)
                    self.assertEqual(done['status'], 'completed', done)
                    self.assertEqual(done['result']['reused'], ['draw'])
                    self.assertEqual(done['result']['completed'], ['draw', 'custody'])
                    self.assertEqual((project / 'original.png').read_bytes(), original_pixels)
                    with self.assertRaises(RuntimeError):
                        client.pause(job)

    def test_cancel_is_persistent_and_requires_explicit_original_job_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, job, pixels = self._stop_during_real_tool(root, 'cancel')
            with local_service(root / 'runtime') as (host, client):
                self.assertEqual(host.pending_restart(), 0)
                self.assertEqual(client.status(job)['status'], 'cancelled')
                with self.assertRaises(RuntimeError):
                    client.resume(job)
                client.retry(job)
                done = client.wait(job, poll_seconds=.1, max_seconds=10)
                self.assertEqual(done['status'], 'completed', done)
                self.assertEqual(done['result']['reused'], ['draw'])
                self.assertEqual((project / 'original.png').read_bytes(), pixels)


if __name__ == '__main__':
    unittest.main()

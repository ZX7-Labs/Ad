"""Content-addressed, crash-resistant resume for real ZX7 BODY renders.

A video is reused only when the authored timeline, actual source bytes, installed
encoder build and BODY implementation match the last verified successful render.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .media_body import RenderError, _asset, _ALLOWED, render_timeline


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _encoder_id(ffmpeg: str) -> str:
    try:
        p = subprocess.run([ffmpeg, '-version'], capture_output=True,
                           text=True, check=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenderError(f'Cannot identify encoder: {exc}') from exc
    return p.stdout.splitlines()[0] if p.stdout else ''


def _fingerprint(plan: dict, asset_root: Path, ffmpeg: str) -> str:
    if not isinstance(plan, dict) or not isinstance(plan.get('clips'), list):
        raise RenderError('Invalid BODY timeline')
    fingerprints = []
    for n, clip in enumerate(plan['clips']):
        if not isinstance(clip, dict) or not isinstance(clip.get('kind'), str) or clip['kind'] not in _ALLOWED:
            raise RenderError(f'Invalid clip {n}')
        path = _asset(asset_root, clip.get('path'), clip['kind'])
        fingerprints.append({'clip': n, 'source_sha256': _sha256(path)})
    material = {'schema_version': 1, 'plan': plan, 'assets': fingerprints,
                'encoder': _encoder_id(ffmpeg),
                'body_code_sha256': _sha256(Path(__file__).with_name('media_body.py')),
                'recovery_code_sha256': _sha256(Path(__file__))}
    try:
        source = json.dumps(material, sort_keys=True, separators=(',', ':'),
                            ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RenderError(f'Invalid timeline fingerprint data: {exc}') from exc
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


@contextmanager
def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_json_atomic(path: Path, data: dict) -> None:
    with tempfile.NamedTemporaryFile(mode='w', prefix='.zx7-manifest-',
                                     suffix='.tmp', dir=path.parent,
                                     encoding='utf-8', delete=False) as temporary:
        name = Path(temporary.name)
        try:
            json.dump(data, temporary, sort_keys=True, indent=2, allow_nan=False)
            temporary.flush()
            os.fsync(temporary.fileno())
        except BaseException:
            name.unlink(missing_ok=True)
            raise
    try:
        os.replace(name, path)
    finally:
        name.unlink(missing_ok=True)


def render_resumable(plan: dict, *, asset_root: str | Path, output_path: str | Path,
                     ffmpeg: str = 'ffmpeg', ffprobe: str = 'ffprobe',
                     timeout_seconds: float = 900) -> dict:
    """Render or safely reuse a verified MP4; serializes concurrent same-path jobs.

    A failed render never updates the successful checkpoint. Modified, replaced,
    deleted or corrupted input/output bytes invalidate reuse, irrespective of mtime.
    """
    root = Path(asset_root).resolve(strict=True)
    target = Path(output_path).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = target.with_name(target.name + '.zx7-cache.json')
    lock = target.with_name(target.name + '.zx7-lock')
    with _lock(lock):
        digest = _fingerprint(plan, root, ffmpeg)
        if manifest.is_file() and target.is_file():
            try:
                prior = json.loads(manifest.read_text(encoding='utf-8'))
                if (prior.get('fingerprint') == digest and
                        prior.get('output_sha256') == _sha256(target) and
                        isinstance(prior.get('render'), dict)):
                    return {**prior['render'], 'reused': True,
                            'input_fingerprint': digest}
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        result = render_timeline(plan, asset_root=root, output_path=target,
                                 ffmpeg=ffmpeg, ffprobe=ffprobe,
                                 timeout_seconds=timeout_seconds)
        _write_json_atomic(manifest, {'schema_version': 1, 'fingerprint': digest,
                                     'output_sha256': _sha256(target),
                                     'render': result})
        return {**result, 'reused': False, 'input_fingerprint': digest}

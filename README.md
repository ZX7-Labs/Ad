# ZX7 BODY

An open-source creative execution system operated by AI. The goal is one
workspace for design, editing, animation, CGI, VFX and sound, with detailed
control over the creative project and its output.

The current implementation provides a tool catalog, editable project controls,
native Blender projects, media rendering, source custody and resumable jobs.
Available operations depend on the engines installed on the host. Development
is active; this is not a completed all-purpose creative suite.

## Run locally

Python 3.11+ is required. The service is tested on Linux. Install FFmpeg/FFprobe
for media operations, Blender 4.5+ for native motion projects, and Inkscape for
SVG rasterization. These applications are installed separately.

```sh
python -m pip install '.[production]'
zx7-tools --workspace ./workspace
export ZX7_BODY_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
zx7-body --workspace-root ./workspace
```

Keep the same token in a second terminal to inspect the running service:

```sh
zx7-client tools
zx7-client describe body.motion_project
```

The authenticated service listens on `127.0.0.1:8765`. Discover tools and their
document schemas before submitting a project. Native operations run on the host;
missing engines are reported as requiring setup. Optional EXR and tracking
dependencies are available through `.[vfx_exr,vfx_tracking]`.

## Project and checks

- [AGENTS.md](AGENTS.md): product intent and development direction.
- `studio_next/`: execution, project controls, service, clients and tests.
- `motion_studio/`: existing 2D compositor and sample projects.
- `creative_director/`, `director_research/`, `voice_lab/`: optional research tools.
- `.github/workflows/`: automated verification and optional manual experiments.

GitHub Actions runs native rendering, source checks, security, browser, custody
and interchange tests. Run focused tests with `python -m unittest`; native tests
require their corresponding host engines and Python dependencies.

## Licenses

Repository code is covered by [LICENSE](LICENSE). External applications, model
weights, fonts, voices and media have their own terms. Research scripts do not
grant commercial rights to their models; the F5/XTTS comparison uses models with
non-commercial restrictions. Review the selected engine and asset licenses for
your deployment.

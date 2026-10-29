# ZX7 BODY

An open-source creative execution system operated by AI. The goal is one
workspace for design, editing, animation, CGI, VFX and sound, with detailed
control over the creative project and its output.

The current implementation provides a tool catalog, editable project controls,
native Blender projects, media rendering, source custody and resumable jobs.
Available operations depend on the engines installed on the host. Development
is active; this is not a completed all-purpose creative suite.

The current [architecture](docs/architecture.md),
[reuse research](docs/reuse-research.md) and
[video research plan](docs/video-research-plan.md) record foundation decisions,
their evidence and remaining acceptance gates.

## Native video editor

The complete [Velorn editor](third_party/velorn) is pinned at
`b3c02adbd5c0779feb8abf34978299e9502cc0e7`. Its native project, UI,
compositor, mixer and exporter are reused. Run `git submodule update --init
--recursive` to obtain source; [setup and native export test](engines/velorn/README.md)
explain how to run it locally without a hosted AI API.

The [execution record](research/editor-integration-evidence.json) verifies a
scripted native edit, saved revisions, application restart/reopen and actual
audiovisual export; it is not an autonomous AI or artistic-quality evaluation.

Python `LocalEditorClient` preserves native MCP schemas and requires explicit
host grants. `body_catalog(workspace, editor_client=client)` attaches granted
operations to the existing BODY catalog. Professional field completion,
autonomous creative acceptance and distribution packaging remain open.

For an MCP-capable local AI client, the [standard MCP launcher](engines/velorn/README.md#connect-a-local-ai-client-through-standard-mcp)
starts the existing editor and the permissioned bridge in one process. Install
the optional `.[editor]` extra; host configuration controls grants and media
roots. Models remain separate and no hosted AI API is required.
The [SDK-client execution record](research/editor-mcp-evidence.json) preserves
the measured scope and exact tested source digests.

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

After a verified archive is restored with relocation enabled, use
`zx7-relink-mlt --workspace NEW --old-workspace OLD --source NEW/edit.mlt --out NEW/relinked.mlt`
to create a separately verified native project at the new media locations.
The old edit and prior execution history remain preserved; renders run again.

## Project and checks

- [AGENTS.md](AGENTS.md): product intent and development direction.
- [CAPABILITIES.md](CAPABILITIES.md): full original A–L capability scope, engineering invariants and release gates.
- [ENGINEERING_STANDARD.md](ENGINEERING_STANDARD.md): autonomous research/engineering method, proof requirements and final 1–2 minute video **only after** field completion.
- `studio_next/`: execution, project controls, service, clients and tests.
- `motion_studio/`: existing 2D compositor and sample projects.
- `creative_director/`, `director_research/`, `voice_lab/`: optional research tools.
- `.github/workflows/`: automated verification and optional manual experiments.

GitHub Actions runs native rendering, source checks, security, browser, custody
and interchange tests. Run focused tests with `python -m unittest`; native tests
require their corresponding host engines and Python dependencies.

## Licenses

Repository code is covered by [LICENSE](LICENSE), except files with their own
notices. Velorn and the integration launcher are GPL-3.0-only; root terms do
not relicense them. External applications, model
weights, fonts, voices and media have their own terms. Research scripts do not
grant commercial rights to their models; the F5/XTTS comparison uses models with
non-commercial restrictions. Review the selected engine and asset licenses for
your deployment.

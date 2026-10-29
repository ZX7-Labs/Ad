# Velorn whole-editor integration

This directory launches the complete pinned [Velorn source](../../third_party/velorn) and calls its native MCP interface. It does not implement a timeline, compositor, audio mixer or renderer. Upstream commit `b3c02adbd5c0779feb8abf34978299e9502cc0e7`, version 0.3.37; this integration is GPL-3.0-only. Preserve [LICENSE](LICENSE), [NOTICE](NOTICE) and full upstream source with distributions.

## Setup

Use Linux, Node.js/npm, normal Electron runtime libraries, and a desktop display or Xvfb. Run as a regular user with the Electron sandbox enabled.

```sh
git submodule update --init --recursive
cd third_party/velorn
npm ci
npm run build
cd ../..
node --test engines/velorn/client.test.mjs engines/velorn/launcher.test.mjs
python -m unittest studio_next.test_body_editor_client studio_next.test_body_editor_catalog -v
```

When dependencies were installed with `--ignore-scripts`, run the normal Electron, ffmpeg-static and @derhuerst/ffprobe-static install scripts before launching. No model weights, ComfyUI, RIFE or hosted AI API are needed for native editing/export. Upstream `electron:pack`/`electron:build` separately require staged RIFE release inputs; distribution packaging is unresolved.

## Connect a local AI client through standard MCP

Install the optional bridge with `python -m pip install '.[editor]'`. Protocol
negotiation and framing use the pinned [official Python SDK 2.3.0](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0).
Copy [editor.example.json](editor.example.json) to a host-owned configuration
file outside the writable project roots, and replace its three absolute paths.
The example explicitly grants 77 local editorial operations from the pinned
source. This is a permission profile, not evidence that all 77 operations passed
production acceptance. Reduce grants for restricted clients. Removing `write`
from `allowed_access` hides and denies mutating operations.

Configure an MCP-capable local AI client to launch this command:

```sh
node /absolute/path/to/zx7/engines/velorn/mcp.mjs \
  --source /absolute/path/to/zx7/third_party/velorn \
  --config /absolute/path/to/host/editor.json \
  --state /absolute/path/to/private-editor-state \
  --python /absolute/path/to/editor-python/bin/python
```

This single process owns the existing editor and the standard stdio MCP bridge.
The `state` directory gets a fresh private profile per connection; projects and
media remain in the configured roots. Add the same display/headless flags below
when needed. Stdout carries only MCP messages. Disconnecting or signalling the
launcher closes its owned processes. Save the native project before disconnect;
this does not promise recovery of an unsaved or interrupted render.

Clients discover unchanged native schemas and choose their own editing values.
Calls validate those schemas and scoped filesystem arguments. Queued cancelled
edits are not applied; an in-flight native call finishes under serialization,
and an uncertain write is never automatically retried. Network/generation,
host-management, nested action plans and batch exports are outside this profile.
Exports require an explicit new `outputPath`; existing project, source and
delivery files are refused as destinations. Opening a project also checks its
primary/legacy native document against the configured project root.
The existing Film IR/mobile creative-session runner remains a separate route;
this connection is for a replaceable MCP-capable brain.

With the example host profile, the additional BODY-owned read-only
`zx7_verify_native_export` tool independently fully decodes a completed
native exported movie (picture and audio), checks its physical hash/identity
against concurrent changes, validates optional target dimensions/duration/audio
and returns an explicitly non-artistic result. It is separately identified
from the 77 granted native controls. Host configuration
`"verify_native_exports": true` opts in; the default is disabled.
Only files in the dedicated authorized output root can be observed; original
project/staging media are intentionally not exposed through this new tool.
After a successful source-bound export proof in the same MCP session,
`zx7_observe_verified_export_frame` can return an actual decoder-produced
PNG image plus a factual source/timestamp receipt to a visual-capable AI client.
The client chooses the requested moment. This is bounded to 768 pixels per
dimension, refuses stale bytes and reports that one selected still does not
establish continuous motion, exact frame presentation PTS, sound quality,
scene-linear/HDR fidelity or artistic acceptance. Refresh the full-export
proof after modifying the file or reconnecting the editor.
The verifier cannot establish editing originality, artistic acceptance,
source rights or OS process isolation. The import and editing tools retain
their exact upstream schemas; this BODY-owned tool is deliberately namespaced.

To verify the actual standard-client editing route:

```sh
python engines/velorn/mcp-e2e.py \
  --source /absolute/path/to/zx7/third_party/velorn \
  --xvfb-binary /usr/bin/Xvfb --display 127.0.0.1:95
```

The fixture uses the official SDK client and the shipped permission profile. It
checks every advertised schema, rejects outside imports/invalid arguments, edits
and saves two native versions, exports real audiovisual media, disconnects, and
reopens the same revision in a new editor process. It is a scripted integration
fixture, not an autonomous model or artistic evaluation.

## Start a local session

Paths must be absolute. Each launch requires a fresh profile; project/staging/output roots can persist. This upstream hardcodes ports 5173 and 19790, so only one instance per network namespace is supported. Occupied ports fail before startup.

```sh
node engines/velorn/cli.mjs \
  --source /absolute/path/to/zx7/third_party/velorn \
  --profile /absolute/path/to/fresh-profile \
  --projects /absolute/path/to/projects \
  --staging /absolute/path/to/staging \
  --outputs /absolute/path/to/outputs
```

For headless Linux install Xvfb, x11-xkb-utils, xkb-data and Electron system libraries, then append `--xvfb-binary /usr/bin/Xvfb --display 127.0.0.1:95`. Choose a free display with no stale lock. The supplied Xvfb uses unauthenticated TCP (`-ac`) for local isolated tests; prefer your own authenticated display in ordinary use. This launcher is not for public hosting.

`--software-gpu` uses Chromium's software compositor. `--no-sandbox` is an explicit exception for disposable restricted root test hosts; it is not the default or an isolation measure.

The process prints a ready record, accepts JSON lines and writes upstream logs to the private profile:

```json
{"id":1,"method":"tools/list"}
{"id":2,"method":"tools/call","params":{"name":"get_project","arguments":{}}}
{"id":3,"method":"tools/call","params":{"name":"create_project","arguments":{"name":"My edit","width":1920,"height":1080,"fps":24,"previewOnly":false}}}
{"id":4,"method":"shutdown"}
```

EOF, shutdown, SIGINT and SIGTERM stop the owned processes; signals also clean up an interrupted startup. Node hosts can import `launchVelorn` from `launcher.mjs`; it accepts an optional AbortSignal and returns `{client,close,revision,rendererUrl,logPath,appProfile,...roots}`. Discovery returns unchanged native schemas plus integration policy annotations. Calls return native MCP content and parsed `.data` for JSON text. Snapshots debounce mutations by 350 ms: `waitForState(predicate)` observes actual upstream state before using fresh IDs.

## Native integration proof

```sh
node engines/velorn/e2e.mjs \
  --source /absolute/path/to/zx7/third_party/velorn \
  --xvfb-binary /usr/bin/Xvfb --display 127.0.0.1:95
```

The fixture creates temporary synthetic media, native video/audio/title tracks, text/keyframes, two preserved project versions, a reopen, a complete application stop/restart with saved-project reopen, and audiovisual export through the existing production Electron export worker. It checks native BODY read/write grants, full original schema preservation, frame/audio decode and SHA256 receipts. This scripted test does not establish autonomous model use, interrupted-render/crash recovery, professional creative quality or complete field coverage. A new receipt is proof only when the command actually succeeds.

## Authority and remaining limits

This is a trusted local transport, not an autonomous-model security boundary. Python BODY must grant individual tools and apply host argument/path policy. Explicit top-level file paths are scoped; network/generation/launcher tools, recent-project lookup, nested plans and batch exports are blocked. Batch targets can nest file paths, so `export_delivery_batch` stays blocked until that structure has a reviewed policy. These checks do not confine the upstream process, remove filesystem races or validate references inside native projects. Open trusted projects only.

The upstream MCP endpoint is unauthenticated loopback at a fixed port; all 130 native tools lack security annotations. Instance identity/token, OS filesystem/network/resource isolation and production completion/progress integration remain release requirements. The application can request Google Fonts and optional services; network-off operation needs egress control or an audited fork patch.

Native source limitations: audio envelope/EQ and spline-point animation remain partly UI-only; variable video speed does not cover all audio retiming; interchange can lose native styling and rejects editable compounds. MCP checkpoints are memory-only; durable named versions require preserving native files. `export_timeline` has no status tool, so the fixture observes the existing worker log and decodes the output. Use separate title tracks to avoid native overwrite semantics, explicit custom ranges to avoid the default 60-second extent, and `h264_project` for project/custom dimensions. Graphics-only MCP exports are rejected by an older readiness check.

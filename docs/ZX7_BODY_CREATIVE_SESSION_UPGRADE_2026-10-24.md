# ZX7 BODY: ordinary briefs, open audio choices and executable contracts

This change connects an ordinary owner brief to the existing authorized BODY
instead of requiring the owner to supply Film IR. It also removes the active
production path's M3/F2-only gate. This is an implementation increment, not
acceptance of a complete autonomous professional studio.

Base: `9d01010d2aec98dca81fa34aa3168c35e1ddc278`, branch
`zx7-body/mobile-operator-20261021`, existing draft PR #3. Main is unchanged.

## What changed

- **One model controls real tools.** The host can configure a loopback model
  with `--creative-model` and `--creative-api`. The authenticated mobile page
  accepts a plain brief and optional known facts. Its session can discover,
  describe, author JSON, preflight, submit, inspect jobs, read native evidence,
  request actual image pixels and submit revisions. All write tools still run
  through the existing durable execution graph and source custody checks.
- **Receipts survive interruption.** SQLite retains the original brief, owner
  facts, configured model identity, protocol fingerprint, decisions, pending
  intent and actual results. Submission replay uses a stable host key and
  checks the unchanged original Film IR before reusing a job. A different
  model/protocol cannot silently take over a saved session. Turn and time
  budgets bound work. The owner can stop further creative actions; existing
  render jobs retain their separate pause/cancel controls. Backups refuse active
  sessions and transfers.
- **The model can query its authoring grammar.** A selected tool descriptor has
  `document_contracts` with version, SHA256 and JSON Schema. Eighteen native
  instruments have primary JSON contracts, including motion artwork, generic
  procedural sounds, Blender geometry/animation, EXR, ACES preview/movie,
  composition, original cuts, retime, review, finishing and local video jobs.
  The timeline editor also exposes its separate operation document. These
  describe technical shape, not a supplied story or composition. Native
  execution remains responsible for source rights, ranges, cross-field
  constraints and runtime feasibility. Plugin and legacy non-JSON formats
  are not certified by these schemas.
- **Voice choice is a runtime decision.** `body.voice_inventory` reports actual
  local style files and whether the synthesis package exists. Safe voice IDs
  replace the two-name gate in active production validators. Global and scene
  choices can carry language, speed, synthesis steps, chunk length and pauses.
  The installed TTS engine must actually load each requested style; custom
  local styles use its documented style-file loader. No downloads, new model
  weights or speech inference are implied by listing a style. Existing samples
  retain their default synthesis settings; their project files were not edited.
- **Sound is no longer limited to three named cues.** The motion renderer also
  accepts explicitly authored oscillator partials, frequency sweeps, phases,
  seeded noise and piecewise-linear envelopes. It preserves the old named cues
  for compatibility. New Film IR controls mix gain, fades, peak ceiling and
  optional loudness normalization; it receives no automatic old demo fades or
  fixed loudness target. The existing attested compositor continues to accept
  real recorded/generated audio tracks. This is procedural synthesis and
  mixing, not evidence of semantic Foley/music generation.
- **Reproduced audit defects were corrected.** All three creative/vision HTTP
  adapters share a no-proxy, no-redirect local transport. Owner transfers reserve
  storage and stream/decode without holding global job admission; HTTP reads
  have a timeout and transfer progress has a finite deadline. Malformed sfnt
  parser errors become custody errors. Creative application execution status
  comes from the same native operation registry as the BODY interface.
  Native release receipts subtract skipped cases, and the simulated CPU test
  uses an isolated cgroup fixture.

## Running the connected path

Run an already installed, authorized local model server first, then:

```bash
python -m studio_next.body_service \
  --workspace-root /srv/zx7 \
  --creative-model YOUR_INSTALLED_MODEL_ID \
  --creative-api http://127.0.0.1:8085
```

The existing `ZX7_BODY_API_TOKEN` host secret is required. Open `/studio` on
that service, authenticate and use **Create from a brief**. Phone-keyboard
dictation can supply text; speech recognition is not bundled. The host still
binds to loopback. This change does not deploy remote HTTPS or an Android host.

Endpoints: authenticated `POST /v1/creative-sessions` with
`{workspace_id, brief, facts}`, `GET /v1/creative-sessions/{id}` and
`POST /v1/creative-sessions/{id}/stop`. Without a configured model, the brief
endpoint returns an explicit setup error and the ordinary-brief button is
disabled. The prior Film IR submission route remains available.

## Evidence and acceptance boundary

`test_body_creative_session` exercises the actual local HTTP model adapter,
plan authoring, native FFmpeg motion render, full picture/sound decode,
revised sound amplitude, preservation of the first movie and reuse of its
verified render stage. The source is a deliberately **scripted protocol
fixture**, not neural inference or an independently imagined film. The decoded
original/revised soundtrack RMS ratio is checked against the authored change.

Other regressions cover actual proxy/redirect servers, an actually stalled HTTP
upload and cleanup, unrelated job admission during a blocked upload, local
style discovery, per-scene synthesis settings passed to a **fixture TTS**,
actual PCM spectrum/envelope output, exact schema errors, owner stop during
inference, non-finite model output, persisted sessions and submission replay.
The existing browser acceptance case now includes the brief form using a
scripted model response. Local verification and matching remote CI results are
recorded in the companion checkpoint; unavailable checks are not passes.

No live creative LLM/VLM, actual TTS weights, GPU actor/video model or semantic
sound listener was run for this change. No new cinematic quality or global
completion percentage is claimed. Complex NLE/VFX/color/audio scope, reliable
long-form work, deployed generation compute, remote Android access and
independent expert creative evaluation remain open. All twelve final studio
acceptance gates remain unaccepted; keep PR #3 draft and unmerged.

Voice API reference consulted: the official Supertonic Python
[quick start at the inspected revision](https://github.com/supertone-oss-archive/supertonic-py/blob/df0f9686dac7fbbde391b759e2ee5286a3737622/docs/quickstart.md).
It documents `voice_style_names`, `get_voice_style`,
`get_voice_style_from_path`, and the synthesis controls used here. Runtime
support still depends on the actually installed package and model assets.

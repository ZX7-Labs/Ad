# Browser-motion eligibility probe

This is an optional research environment, not a required BODY runtime component
or a newly adopted animation backend. The creative model is not involved.

Run with Node 24, FFmpeg, Inkscape and a working Chrome headless shell:

```sh
npm ci --ignore-scripts --no-audit --no-fund
./node_modules/.bin/puppeteer browsers install chrome-headless-shell
node probe.mjs --out ../../output/foundation/browser-motion.json
```

The dependency lock pins `@hyperframes/engine` 0.8.214. Source snapshot inspected:
[`a5496b1`](https://github.com/heygen-com/hyperframes/tree/a5496b1887950777b78ed5ac2bff3505961cb5fe).
The snapshot and the published package are separately identified; matching
version text alone is not a reproducible source-to-package build proof.

The probe authors one trusted synthetic rectangle, uses the native engine API,
captures integer/NTSC timestamps out of order and compares decoded geometry to
SVG rendered by Inkscape. It records repeatability and pixel differences. It
does not establish typography, sound, WebGPU, movie export, artistic quality,
model autonomy or operating cost. No generated media is committed.

Upstream Chromium launch includes `--no-sandbox`. Request interception and a
fixed CSP in this fixture do not establish host isolation. Do not expose this
runner as an arbitrary model-code execution service. Full engine source,
licenses/notices, build recipes and dependency review are required before
product adoption; the package lock alone does not fulfill that gate.

# Branch consolidation — 26 October 2026

The owner authorized consolidating the existing repository into default branch
`main`, preserving work and history, verifying duplication/integration, and
leaving branch deletion to the owner. No creative feature is added here.

## Source audit and resolution

All seven branch tips were fetched and compared by tree, merge-base and commit
ancestry. Their exact starting SHAs are in
[the consolidation manifest](ZX7_BRANCH_CONSOLIDATION_2026-10-26.json).

| Starting branch | Resolution |
| --- | --- |
| `main` | Preserve the current root README and main ancestry. |
| `zx7-body/mobile-operator-20261021` | Use its latest verified implementation as the runtime baseline. |
| `director-grounded-planning` | Already an ancestor of the runtime baseline; preserve all history. |
| `studio-vnext-independent-proof` | Already an ancestor of the runtime baseline; preserve all history. |
| `zx7-specialist-free-stack-20261020` | Already an ancestor of the runtime baseline; preserve all history. |
| `zx7-body/live-signal-contract-20261021` | Preserve its separate commit ancestry. Keep the newer consolidated `body_signal.py`, not the obsolete interface. |
| `zx7-body/real-multitrack-renderer` | Preserve ancestry plus its four unique Python files and historical recovery document. |

The standalone multitrack renderer is retained under its original module names
for compatibility. Its nine original tests physically render media and verify
source-change/corrupt-output cache invalidation. It does not become a duplicate
entry in the current executable BODY catalog. The current catalog and its media
custody/publication policies are unchanged.

The merge retains all seven original tips as ancestors. Deleting those branch
references after verifying the merge therefore does not lose their commits or
older file versions. Branch tips that change after this snapshot must be checked
again before deletion. No branch is deleted by this operation.

## Navigation and workflow cleanup

- `README.md` defines the current product; `ZX7_START_HERE.md` points to the
  consolidated code. Old contradictory entry-point text remains in Git history.
- Historical scope/reference documents are marked as snapshots. Historical
  branch URLs are pinned to immutable retained commits.
- Six existing BODY verification workflows run on `main`. The existing active
  development branch remains an accepted trigger during consolidation.
- Redundant path entries are removed from the migrated workflow filters.
- Historical research/showcase workflows retain manual dispatch and their
  existing issue events, while obsolete push triggers are removed. Their code,
  settings and old results remain available. The director regression keeps its
  existing pull-request check and runs on main.

## Verification

The runtime baseline's exact source `18c32ca792ca1ee7509024eddd5afa6c3b413e3f`
already passed native run
[40275242494](https://github.com/oyzitjfzj/Ad/actions/runs/40275242494):
654 cases, 653 passes, one browser-only skip, with actual installed native proofs.
The nine recovered multitrack tests also passed locally with actual FFmpeg.

The consolidation candidate must additionally pass its own complete native,
mobile security, real Chromium, source inventory, custody and OTIO workflows.
Record the exact candidate/run SHAs when promoting main; older baseline checks
are not substituted for candidate acceptance. Consolidation preserves engineering
work and does not certify complete creative-studio product readiness.

## Completed verification and main promotion

Candidate `ae7999b1f6f9866601483042a1104dc35d93d68b` passed all seven workflows,
and main was fast-forwarded to that exact commit without force. Native run
[40277595162](https://github.com/oyzitjfzj/Ad/actions/runs/40277595162) ran 663 cases:
662 passed, one browser-only skip. Separate real Chromium acceptance passed.
Source inventory, mobile security, source custody, OTIO and director checks all
passed on the same candidate. All 390 tracked files passed format inventory.

All six non-default branch snapshots are now ancestors of main. They may be
deleted after checking that their heads have not moved beyond this consolidation.
No branch deletion was performed. PRs whose heads are now retained in main are
closed as consolidated. The manifest retains exact starting heads and run URLs.

Final housekeeping records these results and restores the old multitrack
workflow's existing FFmpeg installation/probe steps for manual execution. This
changes verification configuration/documentation, not the tested runtime modules.

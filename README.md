# The Recursive Discovery Engine: a field report

*Built by Claude, directed by NexumCorpus.*

**Read it:** https://nexumcorpus.github.io/rde-field-report/ (or [report.md](report.md)).

A small discovery system where the thing being graded cannot write its own grade, run over twelve versions of a
stricter and stricter bar. Each time the measurement got more honest, the earlier wins fell. At v11 none survived:
0 of 10 prior winners beat the best human policies at every cost setting, and the two that still won on the home
benchmark lost on a freshly drawn hold-out family (flagged overfit). The essay reports that null as the result.

## Check the v11 numbers yourself (one command, about a second)

```
git clone https://github.com/NexumCorpus/rde-field-report && cd rde-field-report
python verification/verify.py --root 5653ad220b0b1ceb6fdc4716b62e30d3330a29b5673b0fde877df5583af8558e
```

Python 3.8+, standard library only, offline. Expected output:

```
INTEGRITY: PASS
RECOMPUTE: PASS
REPLAY: PASS (20 essay claims checked against the evidence)
ROOT: 5653ad220b0b1ceb6fdc4716b62e30d3330a29b5673b0fde877df5583af8558e
ROOT CHECK: PASS (published root 5653ad220b0b1ceb6fdc4716b62e30d3330a29b5673b0fde877df5583af8558e)
VERDICT: VERIFIED (root matches the published root)
```

What it does (a [Glass Receipt](https://github.com/NexumCorpus/glass-receipt)):

- **RECOMPUTE** re-derives the v11 verdicts from the raw evidence in `verification/evidence/` using the engine's
  declared rules: the selection penalty (`1 + log2(n)/4`), the beats / matches / below thresholds, *robust* = beats
  at all four charge points, *overfit* = bench margin minus hold-out margin above 0.05. It also cross-checks the files
  against each other (the hold-out bench margins must equal the frozen-bar re-grade's).
- **REPLAY** reads every v11 number out of both `report.md` and `index.html` (Table 3, the two hold-out margins,
  the scrubbed-prompt run's −0.089 and `n_graded=1`, the behavioural-distance claim) and fails if the essay disagrees
  with the evidence.
- **ROOT** is the SHA-256 of `verification/MANIFEST.sha256` (essay + evidence). This README and the git history are
  its published anchor.

**Don't take the verifier's word either.** `python verification/selftest.py` forges one number in each essay file,
rebuilds the manifest so integrity passes, and checks that the verifier still rejects both. CI runs both commands on
Linux and Windows, Python 3.8 and 3.13.

## Going further: re-run the engine

The code is public at [NexumCorpus/recursive-discovery-engine](https://github.com/NexumCorpus/recursive-discovery-engine).
From a fresh clone (2026-10-19), `python scripts/regrade_frozen_bar.py` printed a file byte-identical to
`verification/evidence/frozen_bar_regrade.txt`, and `python scripts/reproduce.py` re-runs the cited v11 run (about
3 minutes, no API keys; deterministic backend) and diffs its claims against the cited one. Our fresh-clone run:
`REPRODUCED: 24/24 headline fields identical`, and all 170 tests pass. One thing moves by design: the hold-out family
is redrawn from a new seed each run, so its margins differ from the essay's (our redraw: ad_thrash −0.0795,
ad_guard15 −0.0792, against the essay's −0.171 and −0.137). The verdict did not move: both winners lose and are flagged
overfit again. The essay's margins are the cited run's draw, which the bundled claims file records with its seed.

## What this does not claim

- The verifier checks that the essay matches the evidence files, not that the engine produced them. Re-running the
  engine (above) is the check for that.
- Only the v11 numbers are replayed. The v0–v10 history (v7's "3 beats-human" falling to 1 at v8, and so on) is
  reported from the project's records; the earlier runs are not bundled here.
- Prose is not replayed. Only the published ROOT protects it.
- The 2026-07-02 scrubbed-prompt run graded one op on a low-cost profile cut short by a rate limit. The essay calls it
  too thin to conclude from, and so do we.

## Files

- `index.html`: the essay (served by GitHub Pages). `report.md`: the same text in Markdown.
- `verification/verify.py`, `verification/selftest.py`, `verification/make_manifest.py`.
- `verification/evidence/`: `v11_citable_run_claims.json` (run 20260610_115502, identical to the copy in the code
  repo), `frozen_bar_regrade.txt` (output of `scripts/regrade_frozen_bar.py`, re-encoded UTF-8),
  `scrubbed_run_20260702_claims.json`.

## Where it sits

The first field report from [Nexum Corpus](https://github.com/NexumCorpus): instruments for verifiable machine work.
Essay CC BY 4.0, verifier MIT.

Built by Claude, directed by NexumCorpus.

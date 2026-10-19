"""verify.py - check the RDE field report against its evidence without trusting its author.
Python 3.8+, standard library only, offline, under a second.

    python verification/verify.py               # exit 0 = VERIFIED, 1 = NOT VERIFIED
    python verification/verify.py --root <hex>  # also require ROOT to equal the published root

Three checks:
  1. INTEGRITY  every file in verification/MANIFEST.sha256 exists and matches its SHA-256; no unlisted evidence files.
  2. RECOMPUTE  the v11 numbers are recomputed from the raw evidence with the engine's declared rules (selection
                penalty, beats/matches/below thresholds, robust = beats at every charge point, overfit gap) and the
                evidence files are cross-checked against each other.
  3. REPLAY     every number the essay states about v11 (Table 3, the hold-out margins, the scrubbed-prompt run) is
                read out of BOTH report.md and index.html and compared with the recomputed value. An essay edited
                after the fact fails here even if the manifest was rebuilt.
ROOT is the SHA-256 of MANIFEST.sha256. A match with the published root means you hold exactly what was published.
What this does not do: re-run the engine. For that, see scripts/reproduce.py in the code repository.
"""
import hashlib
import html
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP = HERE.parent
EV = HERE / "evidence"
EPS = 0.01          # rde/config.py utility_eps
SEL_DIV = 4.0       # rde/engine.py _SELECTION_DIV
OVERFIT_GAP = 0.05  # rde/engine.py, declared bench-vs-holdout gap


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sel_factor(n):
    return 1.0 + math.log2(max(n, 2)) / SEL_DIV


def region(m, n):
    """the declared multi-seed flag rule, applied to the mean margin"""
    if m > EPS * sel_factor(n):
        return "beats"
    return "matches" if m >= -EPS else "below"


def integrity():
    problems, listed = [], set()
    man = HERE / "MANIFEST.sha256"
    if not man.exists():
        return ["MANIFEST.sha256 missing"], None
    for line in man.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        listed.add(rel)
        p = TOP / rel
        if not p.exists():
            problems.append(f"listed file missing: {rel}")
        elif sha(p) != digest:
            problems.append(f"hash mismatch: {rel}")
    for p in EV.rglob("*"):
        rel = p.relative_to(TOP).as_posix()
        if p.is_file() and rel not in listed:
            problems.append(f"unlisted evidence file: {rel}")
    return problems, sha(man)


def frozen_bar():
    """evidence/frozen_bar_regrade.txt: the re-grade of the 10 prior v9/v10 winners (Table 3, row 1)"""
    probs = []
    lines = (EV / "frozen_bar_regrade.txt").read_text(encoding="utf-8").splitlines()
    h = re.search(r"n_graded=(\d+), selection_factor=([\d.]+); eps_beats=([\d.]+)", lines[0])
    n = int(h.group(1))
    if f"{sel_factor(n):.3f}" != h.group(2) or f"{EPS * sel_factor(n):.4f}" != h.group(3):
        probs.append(f"frozen bar header: selection penalty for n={n} recomputes to {sel_factor(n):.3f}")
    fronts = {k: [float(q) for q, _ in re.findall(r"\(([\d.]+), (\d+)\)", l)]
              for k, l in (("static", lines[1]), ("adaptive", lines[2]))}
    rows, i = {}, 3
    while i < len(lines):
        m = re.match(r"(\w+)\s+\S+\s+c\d+\s+([\d.]+)\s+(\w+)\s+([+-][\d.]+)\s+(\w+)\s+([+-][\d.]+)\s+(True|False)\s+"
                     r"(True|False)", lines[i])
        if m:
            name, wcr, sflag, smar, aflag, amar, robust, fragile = m.groups()
            sweep = dict(re.findall(r"([\d.]+): '(\w+)'", lines[i + 1]))
            rows[name] = dict(adaptive=aflag, margin=float(amar), robust=robust == "True", fragile=fragile == "True")
            for tier, flag, mar in (("static", sflag, smar), ("adaptive", aflag, amar)):
                if region(float(mar), n) != flag:
                    probs.append(f"{name} {tier}: margin {mar} recomputes to {region(float(mar), n)}, file says {flag}")
                comp = float(wcr) - float(mar)
                if not any(abs(comp - q) <= 0.0006 for q in fronts[tier]):
                    probs.append(f"{name} {tier}: wCR - margin = {comp:.4f} is not a point of the printed front")
            if (all(v == "beats" for v in sweep.values()) and len(sweep) == 4) != rows[name]["robust"]:
                probs.append(f"{name}: robust column disagrees with its charge sweep {sweep}")
            i += 2
        else:
            i += 1
    if len(rows) != n:
        probs.append(f"frozen bar: header says n_graded={n}, found {len(rows)} rows")
    beats = sum(r["adaptive"] == "beats" for r in rows.values())
    robust = sum(r["robust"] for r in rows.values())
    frag = sorted(k for k, r in rows.items() if r["fragile"])
    s = re.search(r"SUMMARY: (\d+)/(\d+) beats_adaptive_human.*?; (\d+)/(\d+) robust_beats.*fragile: \[(.*)\]", lines[-1]
                  if lines[-1].strip() else lines[-2])
    if not s or (int(s.group(1)), int(s.group(2)), int(s.group(3))) != (beats, n, robust) or \
            sorted(re.findall(r"'(\w+)'", s.group(5))) != frag:
        probs.append("frozen bar SUMMARY line disagrees with its own rows")
    return probs, dict(beats=beats, robust=robust, n=n, rows=rows)


def v11_run(bar_rows):
    """evidence/v11_citable_run_claims.json: the citable v11 run (Table 3 row 2, the hold-out, behavioural distance)"""
    probs = []
    c = json.loads((EV / "v11_citable_run_claims.json").read_text(encoding="utf-8"))
    ops = c["op_utility_adaptive"]
    n = c["n_graded"]
    if len(ops) != n:
        probs.append(f"v11 run: n_graded={n} but {len(ops)} ops graded")
    if round(sel_factor(n), 4) != c["selection_factor"]:
        probs.append(f"v11 run: selection_factor {c['selection_factor']} != recomputed {round(sel_factor(n), 4)}")
    for k in ("beats_human", "matches_human", "below_human"):
        if sum(v == k for v in ops.values()) != c["utility_adaptive"][k]:
            probs.append(f"v11 run: utility_adaptive.{k} disagrees with the per-op flags")
    robust = sorted(nm for nm, sw in c["sensitivity"].items() if sw and all(v == "beats_human" for v in sw.values()))
    if robust != sorted(c["robust_beats"]):
        probs.append(f"v11 run: robust_beats {c['robust_beats']} != recomputed from the charge sweep {robust}")
    hold = {}
    for nm, h in c["holdout"]["margins"].items():
        if (h["bench_margin"] - h["holdout_margin"] > OVERFIT_GAP) != h["overfit"]:
            probs.append(f"v11 run: {nm} overfit flag does not follow from its margins")
        if nm in bar_rows and abs(bar_rows[nm]["margin"] - h["bench_margin"]) > 1e-9:
            probs.append(f"{nm}: bench margin {h['bench_margin']} differs from the frozen-bar re-grade "
                         f"{bar_rows[nm]['margin']}")
        hold[nm] = h
    top2 = sorted(c["behavioral_distance"], key=lambda k: -c["behavioral_distance"][k]["distance"])[:2]
    return probs, dict(n=n, beats=c["utility_adaptive"]["beats_human"], robust=len(robust), hold=hold, top2=top2)


def scrubbed_run():
    """evidence/scrubbed_run_20260702_claims.json: the first pass on rubric-scrubbed prompts (section 8)"""
    probs = []
    c = json.loads((EV / "scrubbed_run_20260702_claims.json").read_text(encoding="utf-8"))
    g = c["recommended_grade"]
    if region(g["adaptive_margin"], c["n_graded"]) + "_human" != g["adaptive"]:
        probs.append("scrubbed run: adaptive flag does not follow from its margin")
    if round(sel_factor(c["n_graded"]), 4) != c["selection_factor"]:
        probs.append("scrubbed run: selection_factor does not recompute")
    return probs, dict(n=c["n_graded"], margin=g["adaptive_margin"], flag=g["adaptive"], ops=list(c["op_utility_adaptive"]))


def essay_text(p):
    t = p.read_text(encoding="utf-8")
    if p.suffix == ".html":
        t = re.sub(r"<[^>]+>", " ", t)
        t = html.unescape(t)
    t = t.replace("−", "-").replace("‑", "-").replace("*", "")
    return re.sub(r"\s+", " ", t)


WORDS = {"zero": 0, "one": 1, "two": 2, "ten": 10, "fourteen": 14}


def replay(bar, run, scrub):
    probs, checked = [], 0
    want = {
        "Table 3, prior winners, beats at declared charge": (r"10 prior v9/v10 winners \| ?(\d+) of (\d+)|"
                                                             r"10 prior v9/v10 winners (\d+) of (\d+)",
                                                             (bar["beats"], bar["n"])),
        "Table 3, prior winners, robust": (r"10 prior v9/v10 winners \|? ?\d+ of \d+ \|? ?(\d+) of (\d+)",
                                           (bar["robust"], bar["n"])),
        "Table 3, citable run, beats at declared charge": (r"(\d+) ops in the citable v11 run \|? ?(\d+) of (\d+)",
                                                           (run["n"], run["beats"], run["n"])),
        "Table 3, citable run, robust": (r"ops in the citable v11 run \|? ?\d+ of \d+ \|? ?(\d+) of (\d+)",
                                         (run["robust"], run["n"])),
        "abstract, zero of ten survived": (r"(\w+) of (\w+) prior winners survived", (bar["robust"], bar["n"])),
        "scrubbed run, adaptive margin": (r"below the best human policy \((-[\d.]+) on the adaptive tier\)",
                                          (round(scrub["margin"], 3),)),
        "scrubbed run, ops graded": (r"n_graded=(\d+)", (scrub["n"],)),
    }
    for nm, h in run["hold"].items():
        want[f"hold-out, {nm}"] = (nm + r" bench ([+-][\d.]+) -?\S* hold-out ([+-][\d.]+)",
                                   (round(h["bench_margin"], 3), round(h["holdout_margin"], 3)))
    for f in ("report.md", "index.html"):
        text = essay_text(TOP / f)
        for label, (pat, expect) in want.items():
            m = re.search(pat, text)
            if not m:
                probs.append(f"{f}: could not find '{label}' in the essay")
                continue
            got = tuple(g for g in m.groups() if g is not None)
            got = tuple(WORDS[g.lower()] if g.lower() in WORDS else (float(g) if "." in g else int(g)) for g in got)
            checked += 1
            if got != tuple(expect):
                probs.append(f"{f}: {label}: essay says {got}, evidence says {tuple(expect)}")
        checked += 1
        if not all(op in text for op in run["top2"]) or "most behaviorally distant" not in text:
            probs.append(f"{f}: behavioural-distance claim does not name the evidence's top two {run['top2']}")
        if not all(run["hold"][nm]["overfit"] for nm in run["hold"]) or "overfit: true" not in text:
            probs.append(f"{f}: essay says both hold-out ops are overfit; evidence disagrees or the line is gone")
    return probs, checked


def arg(flag):
    return sys.argv[sys.argv.index(flag) + 1].strip().lower() if flag in sys.argv[:-1] else None


def main():
    global TOP, HERE, EV
    if "--tree" in sys.argv[:-1]:  # check another copy of the repo with THIS verifier (selftest.py uses it)
        TOP = Path(sys.argv[sys.argv.index("--tree") + 1]).resolve()
        HERE, EV = TOP / "verification", TOP / "verification" / "evidence"
    ip, root = integrity()
    try:
        bp, bar = frozen_bar()
        rp, run = v11_run(bar["rows"])
        sp, scrub = scrubbed_run()
        cp = bp + rp + sp
        ep, n = replay(bar, run, scrub)
    except Exception as e:  # a malformed evidence file is a failure, not a crash
        cp, ep, n = [f"evidence unreadable: {type(e).__name__}: {e}"], [], 0
    for name, probs, extra in (("INTEGRITY", ip, ""), ("RECOMPUTE", cp, ""),
                               ("REPLAY", ep, f" ({n} essay claims checked against the evidence)")):
        print(f"{name}: {'PASS' if not probs else 'FAIL'}{extra}")
        for p in probs:
            print(f"  - {p}")
    want = arg("--root")
    print(f"ROOT: {root}")
    if want:
        print(f"ROOT CHECK: {'PASS' if want == root else 'FAIL'} (published root {want})")
    ok = not (ip or cp or ep) and (want is None or want == root)
    note = "" if not ok else (" (root matches the published root)" if want else " (root not checked: pass --root <published hex>)")
    print("VERDICT:", ("VERIFIED" if ok else "NOT VERIFIED") + note)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

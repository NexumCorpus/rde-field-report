"""selftest.py - don't take the verifier's word either. Copies the repo twice, forges one essay number in each copy
WITH the manifest rebuilt (so integrity passes), and checks that verify.py rejects both. Stdlib only, offline."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
CASES = [
    ("clean", None, None, 0),
    ("Table 3 forged in report.md: robust 0 of 10 -> 1 of 10", "report.md",
     ("| 10 prior v9/v10 winners | 7 of 10 | 0 of 10 |", "| 10 prior v9/v10 winners | 7 of 10 | 1 of 10 |"), 1),
    ("hold-out forged in index.html: -0.171 -> -0.017", "index.html", ("&minus;0.171", "&minus;0.017"), 1),
]


def run(case):
    name, f, edit, want = case
    with tempfile.TemporaryDirectory() as d:
        copy = Path(d) / "repo"
        shutil.copytree(TOP, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        if f:
            p = copy / f
            t = p.read_text(encoding="utf-8")
            assert t.count(edit[0]) == 1, f"selftest edit target not found once in {f}"
            p.write_text(t.replace(edit[0], edit[1]), encoding="utf-8", newline="\n")
            subprocess.run([sys.executable, "-I", str(copy / "verification" / "make_manifest.py")],
                           check=True, capture_output=True)
        # always the ORIGINAL verifier, never the copy's
        r = subprocess.run([sys.executable, "-I", str(TOP / "verification" / "verify.py"), "--tree", str(copy)],
                           capture_output=True, text=True)
        ok = r.returncode == want
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {'VERIFIED' if r.returncode == 0 else 'NOT VERIFIED'}")
        for line in r.stdout.splitlines():
            if line.startswith("  - ") and "MANIFEST" not in line:
                print("       " + line.strip())
        return ok


if __name__ == "__main__":
    results = [run(c) for c in CASES]
    print("SELFTEST:", "PASS" if all(results) else "FAIL")
    sys.exit(0 if all(results) else 1)

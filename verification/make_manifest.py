"""Rebuild verification/MANIFEST.sha256 over the essay and the evidence. Run from anywhere."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP = HERE.parent
files = [TOP / "report.md", TOP / "index.html"] + sorted(p for p in (HERE / "evidence").rglob("*") if p.is_file())
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(TOP).as_posix()}" for p in files]
(HERE / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print(f"{len(lines)} files; root {hashlib.sha256((HERE / 'MANIFEST.sha256').read_bytes()).hexdigest()}")

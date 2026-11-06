"""One-off codemod (decision 5): every tracked script opening the KB by a relative path goes through open_kb. Run from the repo root.
Rewrites text only; nothing is executed. Historical apply_phase*/verify_phase* scripts take an explicit path and stay byte-identical."""
import os, re, subprocess
files = subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True, check=True).stdout.splitlines()
LIT = r"""(?P<q>['"])(?:\./)?(?:knowledge_base/)?carrec_kb\.db(?P=q)"""
changed = []; skipped = []
for rel in files:
    if rel in ("knowledge_base/db/migrate_v6.py", "knowledge_base/kb_db.py") or rel.startswith("knowledge_base/tests/") or rel.startswith("paper/"): continue
    if not os.path.exists(rel): continue
    src = open(rel, encoding="utf-8").read(); s = src
    names = set(m.group(1) for m in re.finditer(rf"^\s*([\w.]+)\s*=\s*(?:{LIT}|KB_PATH)\s*(?:#.*)?$", s, re.M))
    s = re.sub(rf"sqlite3\.connect\(\s*{LIT}", "open_kb(KB_PATH", s)
    s = re.sub(LIT, "KB_PATH", s)
    for n in names:
        s = re.sub(rf"sqlite3\.connect\(\s*{re.escape(n)}\b", f"open_kb({n}", s)
    if s == src: continue
    depth = rel.count("/")
    ups = "".join(', ".."' for _ in range(depth))
    boot = ('import os as _kb_os, sys as _kb_sys\n'
            f'_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)){ups})))  # repo root\n'
            'from knowledge_base.kb_db import KB_PATH, open_kb\n')
    if "from knowledge_base.kb_db import KB_PATH, open_kb" in s:
        boot = ""
    elif "from knowledge_base.kb_db import open_kb" in s:
        s = s.replace("from knowledge_base.kb_db import open_kb", "from knowledge_base.kb_db import KB_PATH, open_kb", 1); boot = ""
    # after a module docstring and any __future__ import
    m = re.match(r'\s*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')[ \t]*\n', s)
    at = m.end() if m else 0
    if s.startswith("#!") and at == 0: at = s.index("\n") + 1
    for fm in re.finditer(r"^from __future__ import .*\n", s, re.M): at = max(at, fm.end())
    s = s[:at] + boot + s[at:]
    open(rel, "w", encoding="utf-8").write(s); changed.append(rel)
print(len(changed), "files changed")
print("\n".join(changed))

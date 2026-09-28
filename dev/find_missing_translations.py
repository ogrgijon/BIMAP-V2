import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src" / "bimap"
pattern = re.compile(r"""t\(["'](.*?)["']\)""")
used = set()
for root, dirs, files in os.walk(SOURCE_ROOT):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            txt = open(os.path.join(root, f), encoding='utf-8').read()
            for m in pattern.finditer(txt):
                used.add(m.group(1))

ns = {}
src = (SOURCE_ROOT / 'i18n.py').read_text(encoding='utf-8')
src_before_def = src.split('def t(')[0]
exec(src_before_def, ns)
defined = set(ns.get('_ES', {}).keys())

missing = sorted(used - defined)
print(f'Used t() calls: {len(used)}')
print(f'Defined in _ES: {len(defined)}')
print(f'MISSING ({len(missing)}):')
for m in missing:
    print(f'  {repr(m)}')

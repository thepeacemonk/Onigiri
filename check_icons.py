import os, re, sys
root = os.path.dirname(__file__)
icons_dir = os.path.join(root, 'system_files', 'system_icons')
icons = {f for f in os.listdir(icons_dir) if f.lower().endswith('.svg')}
refs = set()
for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        if not fn.lower().endswith(('.py', '.js', '.css', '.html')):
            continue
        path = os.path.join(dirpath, fn)
        try:
            text = open(path, encoding='utf-8', errors='ignore').read()
        except Exception as e:
            continue
        for m in re.finditer(r"([A-Za-z0-9_\-]+\.svg)", text):
            refs.add(m.group(1))
missing = sorted([r for r in refs if r not in icons])
present = sorted([r for r in refs if r in icons])
print('--- ICONS IN system_files/system_icons ---')
for i in sorted(icons): print(i)
print('\n--- SVG REFERENCES FOUND IN CODE ---')
for r in sorted(refs): print(r)
print('\n--- MISSING ICON FILES (referenced but not present) ---')
for m in missing: print(m)
print('\n--- PRESENT ICON FILES (referenced and present) ---')
for p in present: print(p)
sys.exit(0)

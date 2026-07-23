"""Find unindented code lines inside game.py that should be indented (method-level code)."""
with open(r'd:\Documentsss\AI-Hand-Rehabilitation-System\physio\game.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

skip_prefixes = ('#', 'class ', 'def ', 'import ', 'from ', 'try', 'except', '"""', "'''", 'matplotlib', 'if __name__')
for i, l in enumerate(lines[50:], start=51):
    stripped = l.rstrip()
    if not stripped:
        continue
    if any(stripped.startswith(p) for p in skip_prefixes):
        continue
    if l[0] not in (' ', '\t', '\r', '\n'):
        print(f'Line {i}: {stripped[:80]}')

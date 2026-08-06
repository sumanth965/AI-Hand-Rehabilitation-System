import os, re

pages_dir = r'd:\Documentsss\AI-Hand-Rehabilitation-System\admin_dashboard\pages'

files_to_update = ['risks.py', 'reports.py', 'digital_twin.py', 'performance.py', 'research.py', 'notes.py', 'auth.py', 'audit.py', 'patients.py', 'home.py']

for fname in files_to_update:
    fpath = os.path.join(pages_dir, fname)
    if not os.path.exists(fpath): continue
    
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    orig_content = content
    
    # 1. Wrap tables
    # Find <table ...> ... </table>
    content = re.sub(r'(<table\b[^>]*>.*?</table>)', lambda m: f'<div class="table-container" style="margin-top:24px;">\n{m.group(1)}\n</div>', content, flags=re.DOTALL)
    
    # Fix double wrapping
    content = re.sub(r'<div class="table-container"[^>]*>\s*<div class="table-container"[^>]*>\n(<table\b[^>]*>.*?</table>)\n</div>\s*</div>', r'<div class="table-container" style="margin-top:24px;">\n\1\n</div>', content, flags=re.DOTALL)

    # 2. Update grids with stat_card
    content = re.sub(r'(class="grid )(two|three|four|five|six|seven|eight|nine|ten)("[^>]*>\s*\{self\.stat_card)', r'\1stats \2\3', content)
    
    if content != orig_content:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated {fname}')

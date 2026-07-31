import os

with open('therapist_dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

os.makedirs('admin_dashboard', exist_ok=True)

with open('admin_dashboard/__init__.py', 'w', encoding='utf-8') as f:
    f.write("")

imports = "".join(lines[0:37])
config_lines = "".join(lines[37:42])
auth_lines = "".join(lines[42:68])
level_names = "".join(lines[68:80])
utils_lines = "".join(lines[80:206])
database_row = "".join(lines[206:240])
page_class = "".join(lines[240:247])
database_repo = "".join(lines[247:1282])
renderer_lines = "".join(lines[1282:3670])
server_lines = "".join(lines[3670:])

# Remove if __name__ == "__main__" block from server_lines if it exists
if 'if __name__ == "__main__":' in server_lines:
    server_lines = server_lines.split('if __name__ == "__main__":')[0]
elif "if __name__ == '__main__':" in server_lines:
    server_lines = server_lines.split("if __name__ == '__main__':")[0]

# config.py
with open('admin_dashboard/config.py', 'w', encoding='utf-8') as f:
    f.write(imports + "\n" + config_lines + "\n" + level_names)

# auth.py
with open('admin_dashboard/auth.py', 'w', encoding='utf-8') as f:
    f.write(imports + "\nfrom admin_dashboard.config import *\n\n" + auth_lines)

# utils.py
with open('admin_dashboard/utils.py', 'w', encoding='utf-8') as f:
    f.write(imports + "\nfrom admin_dashboard.config import *\n\n" + page_class + "\n" + utils_lines)

# database.py
with open('admin_dashboard/database.py', 'w', encoding='utf-8') as f:
    f.write(imports + "\nfrom admin_dashboard.config import *\nfrom admin_dashboard.utils import *\n\n" + database_row + "\n" + database_repo)

# renderer.py
with open('admin_dashboard/renderer.py', 'w', encoding='utf-8') as f:
    f.write(imports + "\nfrom admin_dashboard.config import *\nfrom admin_dashboard.auth import *\nfrom admin_dashboard.utils import *\nfrom admin_dashboard.database import *\n\n" + renderer_lines)

# server.py
with open('admin_dashboard/server.py', 'w', encoding='utf-8') as f:
    f.write(imports + "\nfrom admin_dashboard.config import *\nfrom admin_dashboard.auth import *\nfrom admin_dashboard.utils import *\nfrom admin_dashboard.database import *\nfrom admin_dashboard.renderer import *\n\n" + server_lines)

# main.py
with open('admin_dashboard/main.py', 'w', encoding='utf-8') as f:
    f.write("from admin_dashboard.server import run_server\n\nif __name__ == '__main__':\n    run_server()\n")

# Update therapist_dashboard.py
with open('therapist_dashboard.py', 'w', encoding='utf-8') as f:
    f.write("from admin_dashboard.server import run_server\n\nif __name__ == '__main__':\n    run_server()\n")

print("Extraction complete!")

import os
import json

with open(r'admin_dashboard\renderer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Extract header (imports) before class DashboardRenderer (line 44)
header = "".join(lines[0:43])

# Define the groups
groups = {
    'home': {'mixin': 'HomePageMixin', 'methods': ['home']},
    'auth': {'mixin': 'AuthPagesMixin', 'methods': ['login_page', 'register_page', 'reset_password_page', 'security_overview']},
    'patients': {'mixin': 'PatientPagesMixin', 'methods': ['patients', 'patient_form', 'patient_profile', 'recovery_status', 'prediction_badge']},
    'sessions': {'mixin': 'SessionPagesMixin', 'methods': ['sessions_page', 'bucket_progress', 'bucket_metric', 'bucket_derived']},
    'analytics': {'mixin': 'AnalyticsPagesMixin', 'methods': ['analytics']},
    'adaptive_ai': {'mixin': 'AdaptiveAIPagesMixin', 'methods': ['adaptive_ai', 'explainable_why', 'override_form']},
    'digital_twin': {'mixin': 'DigitalTwinPagesMixin', 'methods': ['digital_twin_page']},
    'sensei': {'mixin': 'SenseiPagesMixin', 'methods': ['sensei_review', 'sensei_trigger']},
    'risks': {'mixin': 'RiskPagesMixin', 'methods': ['risks_page', 'patient_risks']},
    'reports': {'mixin': 'ReportPagesMixin', 'methods': ['reports', 'report_chart_image', 'report_pdf']},
    'performance': {'mixin': 'PerformancePagesMixin', 'methods': ['performance']},
    'research': {'mixin': 'ResearchPagesMixin', 'methods': ['research_dashboard']},
    'notes': {'mixin': 'NotesPagesMixin', 'methods': ['notes']},
    'notifications': {'mixin': 'NotificationPagesMixin', 'methods': ['notifications', 'alert_cards', 'alerts']},
    'audit': {'mixin': 'AuditPagesMixin', 'methods': ['audit_logs_page']},
    'components': {'mixin': 'ComponentsMixin', 'methods': ['css', 'js', 'chart', 'stat_card', 'option', 'short_text']},
}

ranges = {
  "__init__": (45, 46),
  "layout": (48, 133),
  "css": (136, 363),
  "js": (365, 388),
  "chart": (390, 411),
  "stat_card": (413, 420),
  "security_overview": (422, 483),
  "audit_logs_page": (485, 561),
  "login_page": (563, 704),
  "register_page": (706, 852),
  "reset_password_page": (854, 990),
  "home": (993, 1033),
  "patients": (1035, 1089),
  "patient_form": (1091, 1120),
  "patient_profile": (1122, 1298),
  "option": (1300, 1301),
  "recovery_status": (1303, 1310),
  "short_text": (1312, 1316),
  "sessions_page": (1318, 1388),
  "prediction_badge": (1390, 1394),
  "analytics": (1396, 1465),
  "adaptive_ai": (1467, 1604),
  "explainable_why": (1606, 1613),
  "override_form": (1615, 1655),
  "digital_twin_page": (1657, 1743),
  "bucket_progress": (1745, 1746),
  "bucket_metric": (1748, 1758),
  "bucket_derived": (1760, 1770),
  "sensei_review": (1772, 1805),
  "sensei_trigger": (1807, 1827),
  "risks_page": (1829, 1860),
  "patient_risks": (1862, 1894),
  "reports": (1896, 1933),
  "performance": (1935, 1992),
  "research_dashboard": (1994, 2118),
  "notes": (2120, 2177),
  "notifications": (2179, 2181),
  "alert_cards": (2183, 2190),
  "alerts": (2192, 2227),
  "report_chart_image": (2229, 2251),
  "report_pdf": (2253, 2429)
}

os.makedirs(r'admin_dashboard\pages', exist_ok=True)

with open(r'admin_dashboard\pages\__init__.py', 'w', encoding='utf-8') as f:
    f.write("")

mixin_imports = []
mixin_classes = []

for file_name, group in groups.items():
    mixin_name = group['mixin']
    methods = group['methods']
    mixin_imports.append(f"from .pages.{file_name} import {mixin_name}")
    mixin_classes.append(mixin_name)
    
    file_content = header + f"\n\nclass {mixin_name}:\n"
    for method in methods:
        start, end = ranges[method]
        method_lines = lines[start-1:end]
        file_content += "".join(method_lines) + "\n"
    
    with open(rf'admin_dashboard\pages\{file_name}.py', 'w', encoding='utf-8') as f:
        f.write(file_content)

# Now rewrite admin_dashboard\renderer.py
new_renderer = header + "\n" + "\n".join(mixin_imports) + "\n\n"
new_renderer += f"class DashboardRenderer({', '.join(mixin_classes)}):\n"

# Add __init__ and layout
start_init, end_init = ranges['__init__']
start_layout, end_layout = ranges['layout']

new_renderer += "".join(lines[start_init-1:end_init]) + "\n"
new_renderer += "".join(lines[start_layout-1:end_layout]) + "\n"

with open(r'admin_dashboard\renderer.py', 'w', encoding='utf-8') as f:
    f.write(new_renderer)

print("Split completed successfully!")

import re

with open('server.py', 'r') as f:
    content = f.read()

# Remove SUPER_ADMIN_PASSCODE
content = re.sub(r"SUPER_ADMIN_PASSCODE = os\.environ\.get\('SUPER_ADMIN_PASSCODE', 'superadmin123'\)\n*", "", content)

# Remove /api/superadmin/data logic
content = re.sub(r"        elif self\.path == '/api/superadmin/data':.*?(?=\n        elif self\.path == '/api/superadmin/action':)", "", content, flags=re.DOTALL)

# Remove /api/superadmin/action logic
content = re.sub(r"        elif self\.path == '/api/superadmin/action':.*?(?=\n        elif self\.path == '/api/admin/config':)", "", content, flags=re.DOTALL)

# Remove superadmin route from do_GET
content = re.sub(r"        if self\.path == '/superadmin':\n            self\.path = '/superadmin\.html'\n\s+", "", content)

with open('server.py', 'w') as f:
    f.write(content)

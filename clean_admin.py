with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'r') as f:
    content = f.read()

# Remove the superadmin route
route_to_remove = """
        if parsed_path.path == '/superadmin' or parsed_path.path == '/super-admin':
            self.path = '/super_admin.html'
            super().do_GET()
            return
"""

content = content.replace(route_to_remove, "")

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'w') as f:
    f.write(content)

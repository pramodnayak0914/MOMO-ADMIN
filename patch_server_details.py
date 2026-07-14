import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'r') as f:
    content = f.read()

details_code = """
        if self.path.startswith('/api/admin/support/tickets/') and self.path.endswith('/details'):
            ticket_id = self.path.split('/')[-2]
            try:
                from services.admin_support_service import get_ticket_details
                details = get_ticket_details(ticket_id)
                if not details:
                    return self._send_json(404, {"success": False, "error": "Ticket not found"})
                return self._send_json(200, {"success": True, "data": details})
            except Exception as e:
                print(f"Error fetching ticket details: {e}")
                return self._send_json(500, {"success": False, "error": str(e)})
"""

# Insert before "if parsed_path.path == '/api/admin/support/dashboard_stats':"
if "self.path.endswith('/details')" not in content:
    content = content.replace(
        "if parsed_path.path == '/api/admin/support/dashboard_stats':",
        details_code.strip('\n') + "\n\n        if parsed_path.path == '/api/admin/support/dashboard_stats':"
    )

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'w') as f:
    f.write(content)
print("Details endpoint added to server.py")

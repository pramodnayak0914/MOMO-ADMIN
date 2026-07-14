import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'r') as f:
    content = f.read()

patch_code = """
    def do_PATCH(self):
        from urllib.parse import urlparse
        parsed_path = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        
        if self.path.startswith('/api/admin/support/tickets/'):
            ticket_id = self.path.split('/')[-1]
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                admin_email = 'admin@system.local' # Fake auth for demo
                
                from services.admin_support_service import update_ticket_status, assign_ticket, add_ticket_note
                
                if 'status' in data:
                    update_ticket_status(ticket_id, data['status'], admin_email)
                
                if 'assigned_agent' in data:
                    assign_ticket(ticket_id, data['assigned_agent'], admin_email)
                    
                if 'note' in data:
                    add_ticket_note(ticket_id, data['note'], admin_email)
                    
                return self._send_json(200, {"success": True})
            except Exception as e:
                print(f"Error in PATCH ticket: {e}")
                return self._send_json(500, {"success": False, "error": str(e)})
                
        self.send_response(404)
        self.end_headers()
"""

# Insert do_PATCH before do_PUT
if 'def do_PATCH' not in content:
    content = content.replace(
        "    def do_PUT(self):",
        patch_code.strip('\n') + "\n\n    def do_PUT(self):"
    )

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'w') as f:
    f.write(content)
print("do_PATCH added to server.py")

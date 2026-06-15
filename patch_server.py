import re

with open('server.py', 'r') as f:
    content = f.read()

new_endpoints = """        elif self.path == '/api/admin/recharges/status':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            order_id = data.get('order_id')
            status = data.get('status')
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    cur.execute("UPDATE transactions SET status = %s WHERE order_id = %s", (status, order_id))
                    conn.commit()
                    conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return
        elif self.path == '/api/admin/recharges/retry':"""

content = content.replace("        elif self.path == '/api/admin/recharges/retry':", new_endpoints)

with open('server.py', 'w') as f:
    f.write(content)

with open('index.html', 'r') as f:
    html = f.read()
html = html.replace("'/api/admin/recharge/status'", "'/api/admin/recharges/status'")
html = html.replace("'/api/admin/recharge/retry'", "'/api/admin/recharges/retry'")
with open('index.html', 'w') as f:
    f.write(html)

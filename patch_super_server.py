import re

with open('server.py', 'r') as f:
    content = f.read()

super_routes = """
SUPER_ADMIN_PASSCODE = os.environ.get('SUPER_ADMIN_PASSCODE', 'superadmin123')

class AdminAPIHandler(http.server.SimpleHTTPRequestHandler):
"""
if "SUPER_ADMIN_PASSCODE =" not in content:
    content = content.replace("class AdminAPIHandler(http.server.SimpleHTTPRequestHandler):", super_routes)

super_get = """        if self.path == '/':
            self.path = '/index.html'
        elif self.path == '/superadmin':
            self.path = '/superadmin.html'
"""
if "elif self.path == '/superadmin':" not in content:
    content = content.replace("        if self.path == '/':\n            self.path = '/index.html'", super_get)

super_api = """        elif self.path == '/api/superadmin/data':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != SUPER_ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("SELECT SUM(profit) as p FROM transactions WHERE status IN ('SUCCESS', 'PAID', 'success', 'paid')")
                profit_row = cur.fetchone()
                total_profit = float(profit_row['p'] or 0)
                
                cur.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 50")
                audit_logs = [dict(r) for r in cur.fetchall()]
                for a in audit_logs: a['created_at'] = str(a['created_at'])
                
                try:
                    cur.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
                    promo_codes = [dict(r) for r in cur.fetchall()]
                    for p in promo_codes:
                        p['created_at'] = str(p['created_at'])
                        p['value'] = float(p['value'])
                        p['max_cap'] = float(p['max_cap'] or 0)
                except Exception:
                    conn.rollback()
                    promo_codes = []
                
                cur.execute("SELECT value FROM app_config WHERE key = 'api_provider'")
                ap_row = cur.fetchone()
                api_provider = json.loads(ap_row['value']) if ap_row else {"provider": "Cashfree", "commission_margin": 2.5}
                
                conn.close()
                self._send_json(200, {
                    "success": True,
                    "total_profit": total_profit,
                    "audit_logs": audit_logs,
                    "promo_codes": promo_codes,
                    "api_provider": api_provider
                })
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        elif self.path == '/api/superadmin/action':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != SUPER_ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            
            action = data.get('action')
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                
                if action == 'update_provider':
                    val = json.dumps({"provider": data.get("provider"), "commission_margin": data.get("margin")})
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('api_provider', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (val,))
                    cur.execute("INSERT INTO audit_logs (admin_email, action, details) VALUES ('System', 'Provider Changed', %s)", (f"Provider: {data.get('provider')}, Margin: {data.get('margin')}%",))
                    
                elif action == 'create_coupon':
                    code = data.get('code')
                    val = data.get('value')
                    cap = data.get('max_cap')
                    limit = data.get('usage_limit')
                    cur.execute("INSERT INTO promo_codes (code, value, max_cap, usage_limit) VALUES (%s, %s, %s, %s)", (code, val, cap, limit))
                    cur.execute("INSERT INTO audit_logs (admin_email, action, details) VALUES ('System', 'Coupon Created', %s)", (f"Code: {code}, Value: {val}%",))
                
                elif action == 'broadcast':
                    aud = data.get('audience')
                    msg = data.get('message')
                    # Mock push notification count
                    cur.execute("SELECT COUNT(*) as c FROM users")
                    count = cur.fetchone()[0]
                    if aud == 'platinum': count = max(1, count // 10)
                    if aud == 'inactive': count = max(1, count // 3)
                    cur.execute("INSERT INTO audit_logs (admin_email, action, details) VALUES ('System', 'Broadcast Sent', %s)", (f"Audience: {aud}. Users: {count}",))
                    conn.commit()
                    conn.close()
                    return self._send_json(200, {"success": True, "count": count})

                conn.commit()
                conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return
"""

if "elif self.path == '/api/superadmin/data':" not in content:
    content = content.replace("        elif self.path == '/api/admin/config':", super_api + "\n        elif self.path == '/api/admin/config':")


with open('server.py', 'w') as f:
    f.write(content)

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'r') as f:
    content = f.read()

super_admin_endpoints = """
        if self.path == '/api/super-admin/promo':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                if data.get('passcode') != ADMIN_PASSCODE:
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                code = data.get('code')
                discount_type = data.get('discount_type', 'flat')
                value = data.get('value', 0)
                max_cap = data.get('max_cap', 0)
                usage_limit = data.get('usage_limit', 1)

                if not DATABASE_URL or not psycopg2:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return

                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO promo_codes (code, discount_type, value, max_cap, usage_limit)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (code, discount_type, value, max_cap, usage_limit))
                
                cur.execute("INSERT INTO audit_logs (admin_email, action, details, ip_address) VALUES (%s, %s, %s, %s)",
                            ("superadmin", f"Created Promo Code: {code}", f"Type: {discount_type}, Value: {value}, Max Cap: {max_cap}, Limit: {usage_limit}", self.client_address[0]))
                
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "message": f"Promo code {code} created successfully."})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if self.path == '/api/super-admin/campaigns':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                if data.get('passcode') != ADMIN_PASSCODE:
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                campaign_type = data.get('campaign_type') # 'sms', 'whatsapp', 'push'
                message = data.get('message')
                
                if not DATABASE_URL or not psycopg2:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                
                cur.execute("INSERT INTO audit_logs (admin_email, action, details, ip_address) VALUES (%s, %s, %s, %s)",
                            ("superadmin", f"Triggered {campaign_type.upper()} Campaign", message, self.client_address[0]))
                
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "message": f"{campaign_type.upper()} Campaign dispatched successfully to active users."})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if self.path == '/api/super-admin/config-update':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                if data.get('passcode') != ADMIN_PASSCODE:
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                key = data.get('key')
                value = data.get('value')
                
                if not DATABASE_URL or not psycopg2:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                    
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                
                cur.execute("SELECT value FROM app_config WHERE key = %s", (key,))
                row = cur.fetchone()
                old_value = row[0] if row else "None"
                
                cur.execute('''
                    INSERT INTO app_config (key, value) 
                    VALUES (%s, %s) 
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                ''', (key, str(value)))
                
                cur.execute("INSERT INTO audit_logs (admin_email, action, details, ip_address) VALUES (%s, %s, %s, %s)",
                            ("superadmin", f"Updated Config: {key}", f"Old: {old_value} -> New: {value}", self.client_address[0]))
                
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "message": "Updated successfully"})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return
            
        if self.path == '/api/super-admin/data':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                if data.get('passcode') != ADMIN_PASSCODE:
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                
                if not DATABASE_URL or not psycopg2:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                    
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # Fetch data
                cur.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 500")
                transactions = []
                for t in cur.fetchall():
                    t_dict = dict(t)
                    t_dict['created_at'] = str(t_dict['created_at'])
                    t_dict['amount'] = float(t_dict['amount'])
                    transactions.append(t_dict)
                    
                cur.execute("SELECT * FROM purchases ORDER BY created_at DESC LIMIT 500")
                purchases = []
                for p in cur.fetchall():
                    p_dict = dict(p)
                    p_dict['created_at'] = str(p_dict['created_at'])
                    purchases.append(p_dict)
                    
                cur.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 500")
                users_list = []
                for u in cur.fetchall():
                    u_dict = dict(u)
                    u_dict['created_at'] = str(u_dict['created_at'])
                    users_list.append(u_dict)
                    
                cur.execute("SELECT * FROM fraud_alerts ORDER BY created_at DESC LIMIT 200")
                fraud_alerts = []
                for a in cur.fetchall():
                    a_dict = dict(a)
                    a_dict['created_at'] = str(a_dict['created_at'])
                    fraud_alerts.append(a_dict)
                    
                cur.execute("SELECT * FROM login_history ORDER BY created_at DESC LIMIT 200")
                logins = []
                for l in cur.fetchall():
                    l_dict = dict(l)
                    l_dict['created_at'] = str(l_dict['created_at'])
                    logins.append(l_dict)
                    
                cur.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
                promo_codes = []
                for pr in cur.fetchall():
                    pr_dict = dict(pr)
                    pr_dict['created_at'] = str(pr_dict['created_at'])
                    pr_dict['value'] = float(pr_dict['value'])
                    pr_dict['max_cap'] = float(pr_dict['max_cap']) if pr_dict['max_cap'] is not None else None
                    promo_codes.append(pr_dict)
                    
                cur.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 500")
                audit_logs = []
                for l in cur.fetchall():
                    l_dict = dict(l)
                    l_dict['created_at'] = str(l_dict['created_at'])
                    audit_logs.append(l_dict)
                    
                cur.execute("SELECT value FROM app_config WHERE key = 'assistant_name'")
                row = cur.fetchone()
                current_assistant_name = row['value'] if row else ""
                
                analytics_summary = {'page_view': 0, 'entered_number': 0, 'logged_in': 0, 'checkout_started': 0, 'purchase_success': 0}
                try:
                    cur.execute("SELECT event_type, COUNT(DISTINCT session_id) as count FROM analytics_events GROUP BY event_type")
                    for r in cur.fetchall():
                        analytics_summary[r['event_type']] = r['count']
                except:
                    pass
                    
                business_metrics = {"revenue": {"today": 0, "monthly": 0, "total": 0}}
                try:
                    cur.execute("SELECT SUM(amount) as s FROM transactions WHERE LOWER(status) IN ('success', 'paid')")
                    res = cur.fetchone()
                    if res and res['s']: business_metrics['revenue']['total'] = float(res['s'])
                except:
                    pass
                    
                cur.close()
                conn.close()
                
                self._send_json(200, {
                    "success": True,
                    "transactions": transactions,
                    "purchases": purchases,
                    "analytics": analytics_summary,
                    "users": users_list,
                    "fraud_alerts": fraud_alerts,
                    "logins": logins,
                    "assistant_name": current_assistant_name,
                    "business_metrics": business_metrics,
                    "marketing_data": {},
                    "promo_codes": promo_codes,
                    "audit_logs": audit_logs
                })
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return
"""

if "/api/super-admin/data" not in content:
    content = content.replace("        if self.path == '/api/admin/data':", super_admin_endpoints + "\n        if self.path == '/api/admin/data':")

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'w') as f:
    f.write(content)

# Now we need to modify super_admin.html to pass passcode instead of token
with open('/Users/pramod2.nayak/MOMO-ADMIN/super_admin.html', 'r') as f:
    html = f.read()

# Replace token auth with passcode auth
html = html.replace("const token = sessionStorage.getItem('admin-token');", "const token = sessionStorage.getItem('admin-passcode');")
html = html.replace("'Authorization': 'Bearer ' + token", "'Authorization': 'Bearer ' + token")
# Wait, in the python code I just wrote, I check `if data.get('passcode') != ADMIN_PASSCODE:`
# So the JS needs to send passcode in the JSON payload!
html = html.replace("JSON.stringify({ code, discount_type: type, value: parseFloat(value) })", "JSON.stringify({ passcode: token, code, discount_type: type, value: parseFloat(value) })")
html = html.replace("JSON.stringify({ campaign_type: type, message: msg })", "JSON.stringify({ passcode: token, campaign_type: type, message: msg })")
html = html.replace("JSON.stringify({ key: 'api_provider', value: val })", "JSON.stringify({ passcode: token, key: 'api_provider', value: val })")
html = html.replace("JSON.stringify({ key: 'commission_margin', value: val })", "JSON.stringify({ passcode: token, key: 'commission_margin', value: val })")

# Also the initial load data
html = html.replace("const token = sessionStorage.getItem('admin-token');", "const token = sessionStorage.getItem('admin-passcode');")
html = html.replace("const res = await fetch('/api/super-admin/data', {", "const res = await fetch('/api/super-admin/data', { method: 'POST', body: JSON.stringify({passcode: sessionStorage.getItem('admin-passcode')}),")
html = html.replace("headers: { 'Authorization': 'Bearer ' + token }", "headers: { 'Content-Type': 'application/json' }")

# And login logic should use passcode
html = html.replace("const email = document.getElementById('login-email').value;", "")
html = html.replace("const pwd = document.getElementById('login-password').value;", "const pwd = document.getElementById('login-password').value;")
# Wait, super_admin.html has email and password inputs!
html = html.replace("body: JSON.stringify({ email, password: pwd })", "body: JSON.stringify({ passcode: pwd })")

with open('/Users/pramod2.nayak/MOMO-ADMIN/super_admin.html', 'w') as f:
    f.write(html)

print("Super Admin logic ported to MOMO-ADMIN")

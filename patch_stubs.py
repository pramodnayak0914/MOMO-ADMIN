import re

with open('server.py', 'r') as f:
    content = f.read()

# 1. Update users/action
users_action_old = """
        elif self.path == '/api/admin/users/action':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            action = data.get('action')
            phone = data.get('phone_number')
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    status = 'SUSPENDED' if action == 'suspend' else 'ACTIVE'
                    conn.close()
                self._send_json(200, {"success": True})
"""

users_action_new = """
        elif self.path == '/api/admin/users/action':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            action = data.get('action')
            phone = data.get('phone_number')
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    status = 'SUSPENDED' if action == 'suspend' else 'ACTIVE'
                    cur.execute("UPDATE users SET status = %s WHERE phone_number = %s", (status, phone))
                    conn.commit()
                    cur.close()
                    conn.close()
                self._send_json(200, {"success": True})
"""
content = content.replace(users_action_old.strip(), users_action_new.strip())

# 2. Update recharges/status
recharges_status_old = """
        elif self.path == '/api/admin/recharges/status':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            order_id = data.get('order_id')
            status = data.get('status')
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    conn.close()
                self._send_json(200, {"success": True})
"""

recharges_status_new = """
        elif self.path == '/api/admin/recharges/status':
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
                    cur.close()
                    conn.close()
                self._send_json(200, {"success": True})
"""
content = content.replace(recharges_status_old.strip(), recharges_status_new.strip())


# 3. Update recharges/retry
recharges_retry_old = """
        elif self.path == '/api/admin/recharges/retry':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            order_id = data.get('order_id')
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    conn.close()
                self._send_json(200, {"success": True})
"""

recharges_retry_new = """
        elif self.path == '/api/admin/recharges/retry':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            order_id = data.get('order_id')
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    cur.execute("UPDATE transactions SET status = 'PENDING' WHERE order_id = %s", (order_id,))
                    conn.commit()
                    cur.close()
                    conn.close()
                self._send_json(200, {"success": True})
"""
content = content.replace(recharges_retry_old.strip(), recharges_retry_new.strip())


# 4. Update growth/save
growth_save_old = """
        elif self.path == '/api/admin/growth/save':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    ref_rules = json.dumps(data.get('referral_rules', {}))
                    cb_rules = json.dumps(data.get('cashback_rules', {}))
                    loy_rules = json.dumps(data.get('loyalty_rules', {}))
                    
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('referral_rules', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (ref_rules,))
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('cashback_rules', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (cb_rules,))
                    conn.close()
                self._send_json(200, {"success": True})
"""

growth_save_new = """
        elif self.path == '/api/admin/growth/save':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    ref_rules = json.dumps(data.get('referral_rules', {}))
                    cb_rules = json.dumps(data.get('cashback_rules', {}))
                    loy_rules = json.dumps(data.get('loyalty_rules', {}))
                    
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('referral_rules', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (ref_rules,))
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('cashback_rules', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (cb_rules,))
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('loyalty_rules', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (loy_rules,))
                    conn.commit()
                    cur.close()
                    conn.close()
                self._send_json(200, {"success": True})
"""
content = content.replace(growth_save_old.strip(), growth_save_new.strip())

with open('server.py', 'w') as f:
    f.write(content)

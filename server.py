import http.server
import socketserver
import json
import urllib.request
import os

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

import decimal
import datetime

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

PORT = int(os.environ.get('PORT', 8080))
DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_PASSCODE = os.environ.get('ADMIN_PASSCODE', 'admin123')
CASHFREE_CLIENT_ID = os.environ.get('CASHFREE_CLIENT_ID')
CASHFREE_CLIENT_SECRET = os.environ.get('CASHFREE_CLIENT_SECRET')

def get_cashfree_headers():
    return {
        "x-api-version": "2023-08-01",
        "x-client-id": (CASHFREE_CLIENT_ID or "").strip(),
        "x-client-secret": (CASHFREE_CLIENT_SECRET or "").strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

class RechargeProvider:
    def requery(self, txn_id):
        raise NotImplementedError
    def retry(self, txn_id):
        raise NotImplementedError

class MockProvider(RechargeProvider):
    def requery(self, txn_id):
        import random
        # State-based mocking: 70% success, 20% failed, 10% pending
        r = random.random()
        if r < 0.7:
            return {"status": "SUCCESS"}
        elif r < 0.9:
            return {"status": "FAILED"}
        else:
            return {"status": "PENDING"}
            
    def retry(self, txn_id):
        import random
        # 80% success, 20% failure on retry
        if random.random() < 0.8:
            return {"status": "SUCCESS", "provider_txn_id": f"MOCK{random.randint(10000, 99999)}"}
        else:
            return {"status": "FAILED", "message": "Provider timeout"}

def init_db():
    if not DATABASE_URL or not psycopg2:
        return
    try:
        import services_db
        services_db.init_schema()
        print("Service Management Schema initialized successfully.")
    except Exception as e:
        print(f"Error initializing Service Management Schema: {e}")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                email VARCHAR(100) PRIMARY KEY,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'admin',
                status VARCHAR(20) DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reset_code VARCHAR(10),
                reset_expires TIMESTAMP
            )
        ''')
        try:
            cur.execute("ALTER TABLE admins ADD COLUMN IF NOT EXISTS reset_code VARCHAR(10)")
            cur.execute("ALTER TABLE admins ADD COLUMN IF NOT EXISTS reset_expires TIMESTAMP")
        except Exception:
            conn.rollback()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                id SERIAL PRIMARY KEY,
                ticket_id VARCHAR(50) UNIQUE NOT NULL,
                user_phone VARCHAR(20) NOT NULL,
                issue_type VARCHAR(100) NOT NULL,
                target_number VARCHAR(20),
                description TEXT,
                status VARCHAR(20) DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                phone_number VARCHAR(20) PRIMARY KEY,
                wallet_balance DECIMAL(10, 2) DEFAULT 0.00,
                total_recharges INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS scratch_cards (
                id SERIAL PRIMARY KEY,
                user_phone VARCHAR(20) REFERENCES users(phone_number),
                transaction_id VARCHAR(100) NOT NULL,
                reward_amount DECIMAL(10, 2) NOT NULL,
                is_scratched BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS promo_codes (
                code VARCHAR(50) PRIMARY KEY,
                discount_type VARCHAR(20) NOT NULL, -- 'flat' or 'percent'
                value DECIMAL(10, 2) NOT NULL,
                max_cap DECIMAL(10, 2),
                usage_limit INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS promo_usage (
                id SERIAL PRIMARY KEY,
                user_phone VARCHAR(20) REFERENCES users(phone_number),
                promo_code VARCHAR(50) REFERENCES promo_codes(code),
                transaction_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Insert a default first recharge promo code if not exists
        cur.execute('''
            INSERT INTO promo_codes (code, discount_type, value, max_cap, usage_limit)
            VALUES ('FIRST20', 'flat', 20.00, 20.00, 1)
            ON CONFLICT DO NOTHING
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                order_id VARCHAR(50) PRIMARY KEY,
                amount DECIMAL(10, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                payment_status VARCHAR(20) DEFAULT 'PENDING',
                recharge_status VARCHAR(20) DEFAULT 'PENDING',
                gateway_txn_id VARCHAR(100),
                webhook_received BOOLEAN DEFAULT FALSE,
                user_identifier VARCHAR(255) NOT NULL,
                user_phone VARCHAR(20),
                profit DECIMAL(10, 2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            cur.execute("ALTER TABLE transactions ADD COLUMN profit DECIMAL(10, 2) DEFAULT 0.00")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE transactions ADD COLUMN payment_status VARCHAR(20) DEFAULT 'PENDING'")
            cur.execute("ALTER TABLE transactions ADD COLUMN recharge_status VARCHAR(20) DEFAULT 'PENDING'")
            cur.execute("ALTER TABLE transactions ADD COLUMN gateway_txn_id VARCHAR(100)")
            cur.execute("ALTER TABLE transactions ADD COLUMN webhook_received BOOLEAN DEFAULT FALSE")
        except Exception:
            pass
            
        cur.execute('''
            CREATE TABLE IF NOT EXISTS refunds (
                id SERIAL PRIMARY KEY,
                order_id VARCHAR(50) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                reason TEXT,
                status VARCHAR(20) DEFAULT 'Pending',
                processed_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS refund_requests (
                id SERIAL PRIMARY KEY,
                order_id VARCHAR(50) NOT NULL,
                user_phone VARCHAR(20),
                amount DECIMAL(10, 2) NOT NULL,
                reason TEXT,
                status VARCHAR(20) DEFAULT 'PENDING',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_by VARCHAR(100),
                refunded_at TIMESTAMP,
                gateway_refund_id VARCHAR(100),
                remarks TEXT
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS settlements (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL UNIQUE,
                total_collection DECIMAL(10, 2) DEFAULT 0.00,
                fees DECIMAL(10, 2) DEFAULT 0.00,
                net_settlement DECIMAL(10, 2) DEFAULT 0.00,
                status VARCHAR(20) DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                phone_number VARCHAR(20) PRIMARY KEY,
                wallet_balance DECIMAL(10, 2) DEFAULT 0.00,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                device_id VARCHAR(255),
                last_ip VARCHAR(50),
                login_location VARCHAR(255),
                referral_code VARCHAR(20) UNIQUE,
                referred_by VARCHAR(20),
                loyalty_tier VARCHAR(20) DEFAULT 'Silver',
                loyalty_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS login_history (
                id SERIAL PRIMARY KEY,
                user_phone VARCHAR(20),
                ip_address VARCHAR(50),
                location VARCHAR(255),
                device_info VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS fraud_alerts (
                id SERIAL PRIMARY KEY,
                user_phone VARCHAR(20),
                alert_type VARCHAR(50),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try: cur.execute("ALTER TABLE users ADD COLUMN browser_fingerprint VARCHAR(255)")
        except: pass
        try: cur.execute("ALTER TABLE users ADD COLUMN blocked_until TIMESTAMP")
        except: pass
        try: cur.execute("ALTER TABLE login_history ADD COLUMN browser_fingerprint VARCHAR(255)")
        except: pass
        try: cur.execute("ALTER TABLE fraud_alerts ADD COLUMN status VARCHAR(20) DEFAULT 'PENDING'")
        except: pass
        try: cur.execute("ALTER TABLE fraud_alerts ADD COLUMN action_taken TEXT")
        except: pass

        conn.commit()
        cur.close()
        conn.close()
        print("momo-admin: Database verified successfully.")
    except Exception as e:
        print(f"momo-admin: Database initialization error: {e}")

init_db()


class AdminAPIHandler(http.server.SimpleHTTPRequestHandler):

    def authenticate_admin(self, data):
        # Support both old JSON tokens and new Authorization Bearer tokens
        token = data.get('token')
        auth_header = self.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
        if not token:
            # Fallback to passcode if needed
            if data.get('passcode') == ADMIN_PASSCODE:
                return {"email": "local", "role": "superadmin"}
            return None

        if not psycopg2 or not DATABASE_URL:
            # fallback if no DB
            if token == ADMIN_PASSCODE or data.get('passcode') == ADMIN_PASSCODE:
                return {"email": "local", "role": "superadmin"}
            return None

        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            
            # Since the token is just the password_hash, and it's SHA256, it's secure enough to look up globally
            cur.execute("SELECT email, role FROM admins WHERE password_hash = %s AND status = 'ACTIVE'", (token,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row:
                return {"email": row[0], "role": row[1]}
        except Exception as e:
            print(f"Auth error: {e}")
        return None

    def _read_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
            body = b""
            while True:
                line = self.rfile.readline().strip()
                if not line: break
                try:
                    chunk_length = int(line, 16)
                except ValueError:
                    break
                if chunk_length == 0:
                    self.rfile.readline()
                    break
                body += self.rfile.read(chunk_length)
                self.rfile.readline()
            return body
        return self.rfile.read(content_length)

    def do_POST(self):
        post_data = self._read_body()
        try:
            data = json.loads(post_data) if post_data else {}
        except Exception as e:
            return self._send_json(400, {"success": False, "error": f"JSON Parse Error: {str(e)} | Body Length: {len(post_data)} | Body: {post_data.decode('utf-8', errors='ignore')}"})

        from urllib.parse import urlparse
        parsed_path = urlparse(self.path)
        
        try:
            import internal_api_handlers
            if internal_api_handlers.handle_internal_post(self, parsed_path, data):
                return
        except ImportError:
            pass

        if self.path in ('/api/admin/login', '/api/auth/login'):
            email = data.get('email')
            if email: email = email.strip().lower()
            password = data.get('password')
            if not email or not password:
                return self._send_json(400, {"success": False, "error": "Email and password required"})
            
            if not psycopg2 or not DATABASE_URL:
                if password == ADMIN_PASSCODE:
                    return self._send_json(200, {"success": True, "token": ADMIN_PASSCODE})
                return self._send_json(401, {"success": False, "error": "Invalid Passcode"})
            
            import hashlib
            pw_hash = hashlib.sha256(password.encode()).hexdigest()
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("SELECT password_hash, role FROM admins WHERE email = %s AND status = 'ACTIVE'", (email,))
                row = cur.fetchone()
                cur.close()
                conn.close()
                if row and row[0] == pw_hash:
                    return self._send_json(200, {"success": True, "token": pw_hash, "role": row[1]})
            except Exception as e:
                print(f"Login error: {e}")
            return self._send_json(401, {"success": False, "error": "Invalid email or password"})

        elif self.path == '/api/admin/forgot-password':
            email = data.get('email')
            if email: email = email.strip().lower()
            if not email: return self._send_json(400, {"success": False, "error": "Email required"})
            if not psycopg2 or not DATABASE_URL:
                return self._send_json(400, {"success": False, "error": "Database not configured"})
            import random, datetime
            code = str(random.randint(100000, 999999))
            expires = datetime.datetime.now() + datetime.timedelta(minutes=15)
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("SELECT email FROM admins WHERE email = %s", (email,))
                if not cur.fetchone():
                    cur.close(); conn.close()
                    return self._send_json(400, {"success": False, "error": "This email is not registered as an Admin."})
                
                cur.execute("UPDATE admins SET reset_code = %s, reset_expires = %s WHERE email = %s", (code, expires, email))
                conn.commit()
                cur.close(); conn.close()
                
                # Send email via Resend
                resend_key = os.environ.get('RESEND_API_KEY')
                support_email = os.environ.get('SUPPORT_EMAIL', 'support@onlinerecharge-ai.com')
                if not resend_key:
                    print("ERROR: RESEND_API_KEY missing from environment variables.")
                    return self._send_json(500, {"success": False, "error": "Email service is temporarily unavailable. Please contact support."})
                if resend_key:
                    import urllib.request
                    req = urllib.request.Request("https://api.resend.com/emails", method="POST")
                    req.add_header("Authorization", f"Bearer {resend_key}")
                    req.add_header("Content-Type", "application/json")
                    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                    payload = json.dumps({
                        "from": f"MOMO Admin Support <{support_email}>",
                        "to": [email],
                        "subject": "Admin Password Reset Code",
                        "html": f"<p>Your password reset code is: <strong>{code}</strong></p><p>This code expires in 15 minutes.</p>"
                    }).encode()
                    urllib.request.urlopen(req, data=payload)
                return self._send_json(200, {"success": True})
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'read'):
                    try:
                        error_msg = e.read().decode('utf-8')
                    except:
                        pass
                print(f"Forgot password error: {error_msg}")
                return self._send_json(500, {"success": False, "error": f"Email service error: {error_msg}"})

        elif self.path == '/api/admin/reset-password':
            email = data.get('email')
            if email: email = email.strip().lower()
            code = data.get('code')
            new_password = data.get('new_password')
            if not email or not code or not new_password:
                return self._send_json(400, {"success": False, "error": "Missing fields"})
            if not psycopg2 or not DATABASE_URL:
                return self._send_json(400, {"success": False, "error": "Database not configured"})
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("SELECT reset_code, reset_expires FROM admins WHERE email = %s", (email,))
                row = cur.fetchone()
                if not row or row[0] != code:
                    return self._send_json(400, {"success": False, "error": "Invalid or expired code"})
                
                import datetime
                if row[1] and row[1] < datetime.datetime.now():
                    return self._send_json(400, {"success": False, "error": "Code has expired"})
                
                import hashlib
                pw_hash = hashlib.sha256(new_password.encode()).hexdigest()
                cur.execute("UPDATE admins SET password_hash = %s, reset_code = NULL, reset_expires = NULL WHERE email = %s", (pw_hash, email))
                conn.commit()
                cur.close(); conn.close()
                return self._send_json(200, {"success": True})
            except Exception as e:
                return self._send_json(500, {"success": False, "error": str(e)})

        # Parse data again for older endpoints that expect it parsed
        post_data_old = post_data

        if self.path == '/api/super-admin/promo':
            try:
                if not self.authenticate_admin(data):
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
            try:
                if not self.authenticate_admin(data):
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
            self._send_json(403, {"success": False, "error": "This endpoint has been deprecated and moved to Super Admin portal."})
            return
            
        if self.path == '/api/super-admin/data':
            try:
                if not self.authenticate_admin(data):
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

        if self.path == '/api/admin/data':
            try:
                # Use data parsed at top of do_POST
                if not self.authenticate_admin(data):
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                
                transactions = []
                purchases = []
                analytics_summary = {
                    'page_view': 0,
                    'entered_number': 0,
                    'logged_in': 0,
                    'checkout_started': 0,
                    'purchase_success': 0
                }
                
                users_list = []
                logins_list = []
                fraud_list = []
                business_metrics = {
                    "revenue": {"today": 0, "monthly": 0, "total": 0},
                    "recharge": {"total_count": 0, "success_pct": 0, "failure_pct": 0, "pending_pct": 0},
                    "users": {"new_today": 0, "active": 0, "returning": 0},
                    "operators": {"top_operator": "N/A", "top_plan": "N/A", "most_profitable": "N/A"}
                }
                marketing_data = {
                    "popular_plan": {"desc": "N/A", "count": 0},
                    "top_amounts": [],
                    "operator_share": [],
                    "acquisition": []
                }
                
                if DATABASE_URL and psycopg2:
                    try:
                        conn = psycopg2.connect(DATABASE_URL)
                        cur = conn.cursor(cursor_factory=RealDictCursor)
                        
                        cur.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 500")
                        transactions_raw = cur.fetchall()
                        for t in transactions_raw:
                            t['created_at'] = str(t['created_at'])
                            t['amount'] = float(t['amount'] or 0)
                            transactions.append(dict(t))
                            
                        cur.execute("SELECT * FROM purchases ORDER BY created_at DESC LIMIT 500")
                        purchases_raw = cur.fetchall()
                        for p in purchases_raw:
                            p['created_at'] = str(p['created_at'])
                            purchases.append(dict(p))
                    except Exception as e:
                        print(f"Error fetching transactions/purchases: {e}")
                        
                    try:
                        if 'conn' not in locals() or conn.closed:
                            conn = psycopg2.connect(DATABASE_URL)
                        cur = conn.cursor(cursor_factory=RealDictCursor)
                        cur.execute("SELECT event_type, COUNT(DISTINCT session_id) as count FROM analytics_events GROUP BY event_type")
                        analytics_raw = cur.fetchall()
                        for row in analytics_raw:
                            if row['event_type'] in analytics_summary:
                                analytics_summary[row['event_type']] = row['count']
                                
                        # Fetch Sales Leads
                        cur.execute("""
                            SELECT 
                                session_id,
                                MAX(event_data->>'mobile') as contact,
                                MAX(event_data->>'email') as email,
                                MAX(created_at) as last_active,
                                ARRAY_AGG(event_type ORDER BY created_at ASC) as funnel_path
                            FROM analytics_events 
                            WHERE event_data->>'mobile' IS NOT NULL OR event_data->>'email' IS NOT NULL
                            GROUP BY session_id 
                            ORDER BY last_active DESC 
                            LIMIT 100
                        """)
                        leads_raw = cur.fetchall()
                        leads = []
                        for lead in leads_raw:
                            furthest_stage = lead['funnel_path'][-1] if lead['funnel_path'] else 'Unknown'
                            # Format stage name
                            stage_map = {
                                'page_view': 'Clicked Link',
                                'entered_number': 'Entered Number',
                                'logged_in': 'Verified OTP',
                                'checkout_started': 'Started Checkout',
                                'purchase_success': 'Purchased'
                            }
                            leads.append({
                                'contact': lead['contact'],
                                'email': lead['email'],
                                'last_active': str(lead['last_active']),
                                'stage': stage_map.get(furthest_stage, furthest_stage)
                            })
                        analytics_summary['leads'] = leads
                        
                    except Exception as e:
                        print(f"Error fetching analytics (table might not exist yet): {e}")
                        
                    # Real Postgres Queries
                    try:
                        if 'conn' not in locals() or conn.closed:
                            conn = psycopg2.connect(DATABASE_URL)
                        cur = conn.cursor(cursor_factory=RealDictCursor)
                        cur.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 100")
                        for u in cur.fetchall():
                            d = dict(u)
                            d['created_at'] = str(d['created_at'])
                            d['wallet_balance'] = float(d.get('wallet_balance') or 0)
                            users_list.append(d)
                            
                        # If tables don't exist yet, we will catch errors gracefully later
                        try:
                            cur.execute("SELECT * FROM login_history ORDER BY created_at DESC LIMIT 100")
                            for l in cur.fetchall():
                                d = dict(l)
                                d['created_at'] = str(d['created_at'])
                                logins_list.append(d)
                        except Exception:
                            conn.rollback()
                            
                        try:
                            cur.execute("SELECT * FROM fraud_alerts ORDER BY created_at DESC LIMIT 100")
                            for f in cur.fetchall():
                                d = dict(f)
                                d['created_at'] = str(d['created_at'])
                                fraud_list.append(d)
                        except Exception:
                            conn.rollback()

                        # Business Metrics
                        try:
                            cur.execute("SELECT SUM(amount) as s FROM transactions WHERE LOWER(status) IN ('success', 'paid') AND DATE(created_at) = CURRENT_DATE")
                            row = cur.fetchone()
                            if row and row.get('s'): business_metrics['revenue']['today'] = float(row['s'])
                            
                            cur.execute("SELECT SUM(amount) as s FROM transactions WHERE LOWER(status) IN ('success', 'paid') AND TO_CHAR(created_at, 'YYYY-MM') = TO_CHAR(CURRENT_DATE, 'YYYY-MM')")
                            row = cur.fetchone()
                            if row and row.get('s'): business_metrics['revenue']['monthly'] = float(row['s'])
                            
                            cur.execute("SELECT SUM(amount) as s FROM transactions WHERE LOWER(status) IN ('success', 'paid')")
                            row = cur.fetchone()
                            if row and row.get('s'): business_metrics['revenue']['total'] = float(row['s'])
                            
                            cur.execute("SELECT COUNT(*) as c FROM transactions")
                            row = cur.fetchone()
                            total_tx = int(row['c']) if row and row.get('c') else 0
                            business_metrics['recharge']['total_count'] = total_tx
                            if total_tx > 0:
                                cur.execute("SELECT LOWER(status) as st, COUNT(*) as c FROM transactions GROUP BY LOWER(status)")
                                status_counts = {dict(r)['st']: int(dict(r)['c']) for r in cur.fetchall()}
                                success_c = status_counts.get('success', 0) + status_counts.get('paid', 0)
                                fail_c = status_counts.get('failed', 0) + status_counts.get('refunded', 0)
                                pending_c = total_tx - success_c - fail_c
                                business_metrics['recharge']['success_pct'] = round((success_c / total_tx) * 100, 1)
                                business_metrics['recharge']['failure_pct'] = round((fail_c / total_tx) * 100, 1)
                                business_metrics['recharge']['pending_pct'] = round((pending_c / total_tx) * 100, 1)
                                
                            cur.execute("SELECT COUNT(*) as c FROM users WHERE DATE(created_at) = CURRENT_DATE")
                            row = cur.fetchone()
                            if row and row.get('c'): business_metrics['users']['new_today'] = int(row['c'])
                            
                            cur.execute("SELECT COUNT(*) as c FROM users")
                            row = cur.fetchone()
                            if row and row.get('c'): business_metrics['users']['active'] = int(row['c'])
                            
                            cur.execute("SELECT COUNT(*) as c FROM (SELECT user_identifier FROM transactions WHERE LOWER(status) IN ('success', 'paid') GROUP BY user_identifier HAVING COUNT(*) > 1) AS rep")
                            row = cur.fetchone()
                            if row and row.get('c'): business_metrics['users']['returning'] = int(row['c'])
                            
                            cur.execute("SELECT brand_name, COUNT(*) as c FROM purchases GROUP BY brand_name ORDER BY c DESC LIMIT 1")
                            row = cur.fetchone()
                            if row and row.get('brand_name'): business_metrics['operators']['top_operator'] = row['brand_name']
                            
                            cur.execute("SELECT flow_type, COUNT(*) as c FROM purchases GROUP BY flow_type ORDER BY c DESC LIMIT 1")
                            row = cur.fetchone()
                            if row and row.get('flow_type'): business_metrics['operators']['top_plan'] = row['flow_type']
                            
                            cur.execute("SELECT brand_name, SUM(CAST(plan_details->>'price' AS DECIMAL)) as rev FROM purchases GROUP BY brand_name ORDER BY rev DESC LIMIT 1")
                            row = cur.fetchone()
                            if row and row.get('brand_name'): business_metrics['operators']['most_profitable'] = row['brand_name']
                            
                            # Operator Analytics for Recharge Management
                            cur.execute("""
                                SELECT 
                                    p.brand_name, 
                                    COUNT(*) as total, 
                                    SUM(CASE WHEN LOWER(t.status) IN ('success', 'paid') THEN 1 ELSE 0 END) as success,
                                    SUM(CASE WHEN LOWER(t.status) IN ('failed', 'refunded') THEN 1 ELSE 0 END) as failed
                                FROM purchases p
                                JOIN transactions t ON p.order_id = t.order_id
                                GROUP BY p.brand_name
                            """)
                            operator_analytics = []
                            for r in cur.fetchall():
                                total = r['total']
                                if total > 0:
                                    success_rate = (r['success'] / total) * 100
                                    operator_analytics.append({
                                        "operator": r['brand_name'],
                                        "total": int(total),
                                        "success_rate": round(success_rate, 1),
                                        "failed": int(r['failed'])
                                    })
                            business_metrics['operator_analytics'] = operator_analytics
                        except Exception as e:
                            print(f"Error fetching business metrics: {e}")
                            conn.rollback()

                        # Marketing Data
                        try:
                            cur.execute("SELECT plan_details->>'desc' as desc, COUNT(*) as c FROM purchases GROUP BY plan_details->>'desc' ORDER BY c DESC LIMIT 1")
                            row = cur.fetchone()
                            if row and row.get('desc'):
                                marketing_data['popular_plan'] = {"desc": row['desc'], "count": int(row['c'])}
                                
                            cur.execute("SELECT amount, COUNT(*) as count FROM transactions GROUP BY amount ORDER BY count DESC LIMIT 5")
                            marketing_data['top_amounts'] = [{"amount": float(r['amount']), "count": int(r['count'])} for r in cur.fetchall()]
                            
                            cur.execute("SELECT brand_name as operator, COUNT(*) as count FROM purchases GROUP BY brand_name ORDER BY count DESC LIMIT 5")
                            marketing_data['operator_share'] = [{"operator": r['operator'], "count": int(r['count'])} for r in cur.fetchall()]
                            
                            cur.execute("SELECT event_type as source, COUNT(*) as count FROM analytics_events GROUP BY event_type ORDER BY count DESC LIMIT 4")
                            marketing_data['acquisition'] = [{"source": r['source'], "count": int(r['count'])} for r in cur.fetchall()]
                        except Exception as e:
                            print(f"Error fetching marketing data: {e}")
                            conn.rollback()

                    except Exception as e:
                        print(f"Postgres error: {e}")
                        conn.rollback()


                    current_assistant_name = ""
                    try:
                        cur.execute("SELECT value FROM app_config WHERE key = 'assistant_name'")
                        row = cur.fetchone()
                        if row:
                            current_assistant_name = row['value']
                            
                        cur.execute("SELECT value FROM app_config WHERE key = 'referral_rules'")
                        ref_row = cur.fetchone()
                        referral_rules = json.loads(ref_row['value']) if ref_row else {"referrer_reward": 20, "referred_reward": 20}
                        
                        cur.execute("SELECT value FROM app_config WHERE key = 'cashback_rules'")
                        cb_row = cur.fetchone()
                        cashback_rules = json.loads(cb_row['value']) if cb_row else {"first_recharge": 0, "weekend": 0}
                        
                        cur.execute("SELECT value FROM app_config WHERE key = 'loyalty_rules'")
                        loy_row = cur.fetchone()
                        loyalty_rules = json.loads(loy_row['value']) if loy_row else {"silver_min": 0, "gold_min": 500, "platinum_min": 2000}
                        
                        growth_rules = {
                            "referral": referral_rules,
                            "cashback": cashback_rules,
                            "loyalty": loyalty_rules
                        }
                        
                        cur.execute("SELECT value FROM app_config WHERE key = 'admin_permissions'")
                        perm_row = cur.fetchone()
                        admin_permissions = json.loads(perm_row['value']) if perm_row else {"can_refund": True, "can_suspend_users": True, "can_edit_growth": True, "can_view_marketing": True}

                    except Exception as e:
                        print(f"Error fetching config: {e}")
                        growth_rules = {}
                        admin_permissions = {"can_refund": True, "can_suspend_users": True, "can_edit_growth": True, "can_view_marketing": True}
                        
                    cur.close()
                    conn.close()
                else:
                    transactions = [{"order_id": "TEST", "status": "SUCCESS", "amount": 0, "created_at": "N/A"}]
                    current_assistant_name = "Offline"
                    growth_rules = {}
                    admin_permissions = {"can_refund": True, "can_suspend_users": True, "can_edit_growth": True, "can_view_marketing": True}
                
                self._send_json(200, {
                    "success": True,
                    "transactions": transactions,
                    "purchases": purchases,
                    "analytics": analytics_summary,
                    "assistant_name": current_assistant_name,
                    "users": users_list,
                    "logins": logins_list,
                    "fraud_alerts": fraud_list,
                    "growth_rules": growth_rules,
                    "business_metrics": business_metrics,
                    "marketing_data": marketing_data,
                    "admin_permissions": admin_permissions
                })
            except Exception as e:
                print(f"Error fetching admin data: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/admin/users/action':
            if not self.authenticate_admin(data): return self._send_json(401, {"error": "Unauthorized"})
            action = data.get('action')
            phone = data.get('phone_number')
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    if action == 'reset':
                        cur.execute("UPDATE users SET device_id = NULL, last_ip = NULL WHERE phone_number = %s", (phone,))
                    else:
                        status = 'SUSPENDED' if action == 'suspend' else 'ACTIVE'
                        cur.execute("UPDATE users SET status = %s WHERE phone_number = %s", (status, phone))
                    conn.commit()
                    cur.close()
                    conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return
            
        elif self.path == '/api/admin/recharge/action':
            if not self.authenticate_admin(data): return self._send_json(401, {"error": "Unauthorized"})
            action = data.get('action')
            order_id = data.get('order_id')
            
            try:
                if action == 'requery':
                    provider = MockProvider()
                    result = provider.requery(order_id)
                    new_status = result.get('status', 'PENDING')
                    if DATABASE_URL and psycopg2:
                        conn = psycopg2.connect(DATABASE_URL)
                        cur = conn.cursor()
                        cur.execute("UPDATE transactions SET status = %s WHERE order_id = %s", (new_status, order_id))
                        conn.commit()
                        cur.close()
                        conn.close()
                    return self._send_json(200, {"success": True, "new_status": new_status})
                
                elif action == 'retry':
                    provider = MockProvider()
                    result = provider.retry(order_id)
                    new_status = result.get('status', 'FAILED')
                    if DATABASE_URL and psycopg2:
                        conn = psycopg2.connect(DATABASE_URL)
                        cur = conn.cursor()
                        cur.execute("UPDATE transactions SET status = %s WHERE order_id = %s", (new_status, order_id))
                        conn.commit()
                        cur.close()
                        conn.close()
                    return self._send_json(200, {"success": True, "new_status": new_status, "message": result.get('message')})
                
                elif action == 'force_status':
                    admin_permissions = {"can_refund": True, "can_suspend_users": True, "can_edit_growth": True, "can_view_marketing": True, "can_override_recharge": False}
                    if DATABASE_URL and psycopg2:
                        conn = psycopg2.connect(DATABASE_URL)
                        cur = conn.cursor()
                        cur.execute("SELECT value FROM app_config WHERE key = 'admin_permissions'")
                        perm_row = cur.fetchone()
                        if perm_row and perm_row[0]:
                            admin_permissions = json.loads(perm_row[0])
                        
                        if not admin_permissions.get('can_override_recharge', False):
                            cur.close()
                            conn.close()
                            return self._send_json(403, {"error": "Forbidden: You do not have permission to override recharge status."})
                        
                        status = data.get('status')
                        cur.execute("UPDATE transactions SET status = %s WHERE order_id = %s", (status, order_id))
                        conn.commit()
                        cur.close()
                        conn.close()
                    return self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return
        elif self.path == '/api/admin/growth/save':
            if not self.authenticate_admin(data): return self._send_json(401, {"error": "Unauthorized"})
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
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return


        elif self.path == '/api/admin/config':
            try:
                # Use data parsed at top of do_POST
                if not self.authenticate_admin(data):
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                
                new_name = data.get('assistant_name')
                if not new_name:
                    self._send_json(400, {"success": False, "error": "Missing assistant_name"})
                    return
                
                if not DATABASE_URL:
                    import sqlite3
                    conn = sqlite3.connect('/Users/pramod2.nayak/MOMO-AI/local_database.db', check_same_thread=False)
                    cur = conn.cursor()
                    cur.execute('''
                        INSERT INTO app_config (key, value) 
                        VALUES ('assistant_name', ?) 
                        ON CONFLICT (key) DO UPDATE SET value = excluded.value
                    ''', (new_name,))
                    conn.commit()
                    cur.close()
                    conn.close()
                    self._send_json(200, {"success": True})
                    return
                    
                if not psycopg2:
                    self._send_json(500, {"success": False, "error": "Python Database Driver failed to load. Check PYTHON_VERSION."})
                    return
                    
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO app_config (key, value) 
                    VALUES ('assistant_name', %s) 
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                ''', (new_name,))
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        elif self.path == '/api/admin/payments':
            admin = self.authenticate_admin(data)
            if not admin: return self._send_json(401, {"error": "Unauthorized"})
            if not DATABASE_URL or not psycopg2:
                return self._send_json(200, {"success": True, "transactions": [], "stats": {"initiated": 0, "success": 0, "pending": 0, "failed": 0, "revenue": 0, "refunds_amount": 0, "settlements_amount": 0}})
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # Fetch recent transactions
                cur.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 100")
                txns = cur.fetchall()
                for t in txns:
                    if 'created_at' in t and t['created_at']: t['created_at'] = t['created_at'].isoformat()
                
                # Fetch stats
                cur.execute("SELECT COUNT(*) as c FROM transactions WHERE created_at >= CURRENT_DATE")
                initiated = cur.fetchone()['c']
                
                cur.execute("SELECT COUNT(*) as c FROM transactions WHERE payment_status = 'SUCCESS' AND created_at >= CURRENT_DATE")
                success = cur.fetchone()['c']
                
                cur.execute("SELECT COUNT(*) as c FROM transactions WHERE payment_status = 'FAILED' AND created_at >= CURRENT_DATE")
                failed = cur.fetchone()['c']
                
                cur.execute("SELECT COUNT(*) as c FROM transactions WHERE payment_status = 'PENDING' AND created_at >= CURRENT_DATE")
                pending = cur.fetchone()['c']
                
                cur.execute("SELECT COALESCE(SUM(amount), 0) as r FROM transactions WHERE payment_status = 'SUCCESS' AND created_at >= CURRENT_DATE")
                revenue = float(cur.fetchone()['r'])
                
                cur.execute("SELECT COALESCE(SUM(amount), 0) as r FROM refunds WHERE status = 'Refunded' AND created_at >= CURRENT_DATE")
                refunds_amount = float(cur.fetchone()['r'])
                
                cur.execute("SELECT COALESCE(SUM(net_settlement), 0) as r FROM settlements WHERE status = 'SUCCESS' AND date >= CURRENT_DATE")
                settlements_amount = float(cur.fetchone()['r'])
                
                stats = {
                    "initiated": initiated,
                    "success": success,
                    "pending": pending,
                    "failed": failed,
                    "revenue": revenue,
                    "refunds_amount": refunds_amount,
                    "settlements_amount": settlements_amount
                }
                
                cur.close()
                conn.close()
                return self._send_json(200, {"success": True, "transactions": txns, "stats": stats})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        elif self.path == '/api/admin/refunds':
            admin = self.authenticate_admin(data)
            if not admin: return self._send_json(401, {"error": "Unauthorized"})
            if not DATABASE_URL or not psycopg2:
                return self._send_json(200, {"success": True, "refunds": []})
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT * FROM refund_requests ORDER BY requested_at DESC LIMIT 100")
                refunds = cur.fetchall()
                for r in refunds:
                    if 'requested_at' in r and r['requested_at']: r['requested_at'] = r['requested_at'].isoformat()
                    if 'refunded_at' in r and r['refunded_at']: r['refunded_at'] = r['refunded_at'].isoformat()
                cur.close()
                conn.close()
                return self._send_json(200, {"success": True, "refunds": refunds})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})
                
        elif self.path == '/api/admin/refunds/action':
            admin = self.authenticate_admin(data)
            if not admin: return self._send_json(401, {"error": "Unauthorized"})
            if admin['role'] not in ['operations', 'superadmin', 'admin']:
                return self._send_json(403, {"error": "Forbidden. Operations or Superadmin role required to process refunds."})
            
            refund_id = data.get('refund_id')
            action = data.get('action') # 'approve', 'reject', 'retry'
            if not refund_id or action not in ['approve', 'reject', 'retry']:
                return self._send_json(400, {"error": "Invalid refund_id or action"})
                
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                if action == 'approve':
                    new_status = 'APPROVED'
                elif action == 'reject':
                    new_status = 'REJECTED'
                elif action == 'retry':
                    new_status = 'RETRYING'
                    
                cur.execute("UPDATE refund_requests SET status = %s, approved_by = %s WHERE id = %s AND status = 'PENDING'", (new_status, admin['email'], refund_id))
                if cur.rowcount == 0:
                    conn.rollback()
                    return self._send_json(400, {"error": "Refund already processed or not found"})
                conn.commit()
                cur.close()
                conn.close()
                return self._send_json(200, {"success": True})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        elif self.path == '/api/admin/refunds/initiate':
            admin = self.authenticate_admin(data)
            if not admin: return self._send_json(401, {"error": "Unauthorized"})
            if admin['role'] not in ['operations', 'superadmin', 'admin']:
                return self._send_json(403, {"error": "Forbidden. Operations role required."})
            
            order_id = data.get('order_id')
            reason = data.get('reason', 'User requested')
            if not order_id:
                return self._send_json(400, {"error": "order_id required"})
            
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("SELECT amount FROM transactions WHERE order_id = %s", (order_id,))
                row = cur.fetchone()
                if not row:
                    return self._send_json(404, {"error": "Order not found"})
                amount = row[0]
                cur.execute("INSERT INTO refunds (order_id, amount, reason, status) VALUES (%s, %s, %s, 'Pending')", (order_id, amount, reason))
                conn.commit()
                cur.close()
                conn.close()
                return self._send_json(200, {"success": True})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        elif self.path == '/api/admin/settlements':
            admin = self.authenticate_admin(data)
            if not admin: return self._send_json(401, {"error": "Unauthorized"})
            if admin['role'] not in ['finance', 'superadmin', 'admin']:
                return self._send_json(403, {"error": "Forbidden. Finance role required."})
            if not DATABASE_URL or not psycopg2:
                return self._send_json(200, {"success": True, "settlements": []})
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT * FROM settlements ORDER BY date DESC LIMIT 30")
                settlements = cur.fetchall()
                for s in settlements:
                    if 'created_at' in s and s['created_at']: s['created_at'] = s['created_at'].isoformat()
                    if 'date' in s and s['date']: s['date'] = str(s['date'])
                cur.close()
                conn.close()
                return self._send_json(200, {"success": True, "settlements": settlements})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        elif self.path == '/api/admin/settlements/export':
            admin = self.authenticate_admin(data)
            if not admin: return self._send_json(401, {"error": "Unauthorized"})
            if admin['role'] not in ['finance', 'superadmin', 'admin']:
                return self._send_json(403, {"error": "Forbidden. Finance role required."})
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT date, total_collection, fees, net_settlement, status FROM settlements ORDER BY date DESC")
                settlements = cur.fetchall()
                cur.close()
                conn.close()
                
                # Generate CSV string
                csv_data = "Date,Total Collection,Fees,Net Settlement,Status\n"
                for s in settlements:
                    csv_data += f"{s['date']},{s['total_collection']},{s['fees']},{s['net_settlement']},{s['status']}\n"
                
                # Send as plain text so the frontend can download it
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv')
                self.send_header('Content-Disposition', 'attachment; filename="settlements.csv"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(csv_data.encode('utf-8'))
                return
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        elif self.path == '/api/admin/fraud':
            admin = self.authenticate_admin(data)
            if not admin: return self._send_json(401, {"error": "Unauthorized"})
            if admin['role'] not in ['superadmin', 'admin', 'operations']:
                return self._send_json(403, {"error": "Forbidden"})
            try:
                if not DATABASE_URL or not psycopg2:
                    return self._send_json(200, {
                        "success": True, 
                        "alerts": [], 
                        "stats": {"suspended_count": 0, "active_alerts": 0, "top_ips": []}
                    })

                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # Fetch recent alerts
                cur.execute("SELECT * FROM fraud_alerts ORDER BY created_at DESC LIMIT 50")
                alerts = cur.fetchall()
                for a in alerts:
                    if 'created_at' in a and a['created_at']: a['created_at'] = a['created_at'].isoformat()
                
                # Top Suspicious IPs (Failed Payments > 3 in last 24h)
                cur.execute("""
                    SELECT ip_address, COUNT(*) as fail_count 
                    FROM login_history 
                    WHERE ip_address IS NOT NULL AND created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY ip_address HAVING COUNT(*) > 3
                    ORDER BY fail_count DESC LIMIT 5
                """)
                top_ips = cur.fetchall()
                
                # Suspended Users Count
                cur.execute("SELECT COUNT(*) as c FROM users WHERE status = 'SUSPENDED'")
                suspended_count = cur.fetchone()['c']
                
                # Active Alerts Count
                cur.execute("SELECT COUNT(*) as c FROM fraud_alerts WHERE status = 'PENDING'")
                active_alerts = cur.fetchone()['c']

                cur.close()
                conn.close()
                
                stats = {
                    "suspended_count": suspended_count,
                    "active_alerts": active_alerts,
                    "top_ips": top_ips
                }
                
                return self._send_json(200, {"success": True, "alerts": alerts, "stats": stats})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        elif self.path == '/api/admin/fraud/action':
            admin = self.authenticate_admin(data)
            if not admin: return self._send_json(401, {"error": "Unauthorized"})
            if admin['role'] not in ['superadmin', 'admin', 'operations']:
                return self._send_json(403, {"error": "Forbidden"})
            
            action = data.get('action')
            alert_id = data.get('alert_id')
            user_phone = data.get('user_phone')
            
            try:
                if not DATABASE_URL or not psycopg2:
                    return self._send_json(200, {"success": True})

                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                if action == 'resolve_alert':
                    cur.execute("UPDATE fraud_alerts SET status = 'RESOLVED', action_taken = %s WHERE id = %s", (f"Resolved by {admin['email']}", alert_id))
                
                elif action == 'suspend_user':
                    cur.execute("UPDATE users SET status = 'SUSPENDED' WHERE phone_number = %s", (user_phone,))
                    cur.execute("UPDATE fraud_alerts SET status = 'RESOLVED', action_taken = %s WHERE user_phone = %s AND status = 'PENDING'", (f"Suspended by {admin['email']}", user_phone))
                
                elif action == 'unblock_user':
                    cur.execute("UPDATE users SET status = 'ACTIVE' WHERE phone_number = %s", (user_phone,))
                    cur.execute("UPDATE fraud_alerts SET status = 'RESOLVED', action_taken = %s WHERE user_phone = %s AND status = 'PENDING'", (f"Unblocked by {admin['email']}", user_phone))

                conn.commit()
                cur.close()
                conn.close()
                return self._send_json(200, {"success": True})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed_path = urlparse(self.path)
        
        try:
            import internal_api_handlers
            if internal_api_handlers.handle_internal_get(self, parsed_path):
                return
        except ImportError:
            pass
                    
        if parsed_path.path == '/api/support/tickets':
            query_params = parse_qs(parsed_path.query)
            user_phone = query_params.get('user_phone', [None])[0]
            
            if not DATABASE_URL or not psycopg2:
                return self._send_json(200, {"success": True, "tickets": []})
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                if user_phone:
                    cur.execute("SELECT * FROM support_tickets WHERE user_phone = %s ORDER BY created_at DESC", (user_phone,))
                else:
                    cur.execute("SELECT * FROM support_tickets ORDER BY created_at DESC")
                    
                tickets = cur.fetchall()
                for ticket in tickets:
                    if 'created_at' in ticket and ticket['created_at']:
                        ticket['created_at'] = ticket['created_at'].isoformat()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "tickets": tickets})
            except Exception as e:
                print(f"Error fetching tickets: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        else:
            if self.path == '/':
                self.send_response(302)
                self.send_header('Location', '/admin')
                self.end_headers()
                return
            if not os.path.exists(self.translate_path(self.path)):
                self.path = '/'
            super().do_GET()

    def do_PUT(self):
        from urllib.parse import urlparse
        parsed_path = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        
        if self.path.startswith('/api/internal/'):
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data) if post_data else {}
            except json.JSONDecodeError:
                data = {}
            try:
                import internal_api_handlers
                if internal_api_handlers.handle_internal_put(self, parsed_path, data):
                    return
            except ImportError:
                pass
                
        if self.path.startswith('/api/support/tickets/'):
            ticket_id = self.path.split('/')[-1]
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                new_status = data.get('status')
                if not new_status:
                    self._send_json(400, {"success": False, "error": "Status is required"})
                    return
                
                if not DATABASE_URL or not psycopg2:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                
                if new_status == 'REFUNDED':
                    cur.execute("SELECT value FROM app_config WHERE key = 'admin_permissions'")
                    perm_row = cur.fetchone()
                    perms = json.loads(perm_row[0]) if perm_row else {}
                    if not perms.get('can_refund', True):
                        self._send_json(403, {"success": False, "error": "Refund permission denied by Super Admin."})
                        cur.close()
                        conn.close()
                        return

                cur.execute("SELECT user_phone, status FROM support_tickets WHERE ticket_id = %s", (ticket_id,))
                ticket_row = cur.fetchone()
                
                if ticket_row and ticket_row[1] == 'REFUNDED':
                    self._send_json(400, {"success": False, "error": "Ticket is permanently locked because it has already been REFUNDED."})
                    cur.close()
                    conn.close()
                    return
                
                # Check if order_id column exists safely
                provided_order_id = None
                try:
                    # using a separate cursor for the safe check
                    with conn.cursor() as temp_cur:
                        temp_cur.execute("SELECT order_id FROM support_tickets WHERE ticket_id = %s", (ticket_id,))
                        temp_row = temp_cur.fetchone()
                        if temp_row and temp_row[0]:
                            provided_order_id = temp_row[0]
                except Exception:
                    conn.rollback()
                
                cur.execute(
                    "UPDATE support_tickets SET status = %s WHERE ticket_id = %s RETURNING id",
                    (new_status, ticket_id)
                )
                updated = cur.fetchone()
                
                refund_message = None
                
                if updated and new_status == 'REFUNDED' and ticket_row:
                    user_phone = ticket_row[0]
                    
                    if provided_order_id:
                        cur.execute("SELECT order_id, amount, status FROM transactions WHERE order_id = %s", (provided_order_id,))
                    else:
                        cur.execute(
                            "SELECT order_id, amount, status FROM transactions WHERE user_identifier = %s AND status IN ('success', 'PAID') ORDER BY created_at DESC LIMIT 1",
                            (user_phone,)
                        )
                    txn = cur.fetchone()
                    if txn:
                        order_id, amount, txn_status = txn
                        if txn_status == 'REFUNDED':
                            refund_message = f"Transaction {order_id} was already refunded previously."
                        elif CASHFREE_CLIENT_ID and CASHFREE_CLIENT_SECRET:
                            try:
                                cf_url = f"https://sandbox.cashfree.com/pg/orders/{order_id}/refunds"
                                import os
                                payload = json.dumps({
                                    "refund_amount": float(amount),
                                    "refund_id": f"ref_{ticket_id}_{os.urandom(4).hex()}",
                                    "refund_note": f"Refund for ticket {ticket_id}"
                                }).encode('utf-8')
                                
                                req = urllib.request.Request(cf_url, data=payload, method="POST")
                                for k, v in get_cashfree_headers().items():
                                    req.add_header(k, v)
                                    
                                with urllib.request.urlopen(req) as response:
                                    cf_res = json.loads(response.read().decode('utf-8'))
                                    refund_status = cf_res.get("refund_status")
                                    cur.execute("UPDATE transactions SET status = 'REFUNDED' WHERE order_id = %s", (order_id,))
                                    refund_message = f"Refunded ₹{amount} for order {order_id}. Status: {refund_status}"
                            except urllib.error.HTTPError as e:
                                refund_message = f"Cashfree Refund Failed: {e.read().decode('utf-8')}"
                            except Exception as e:
                                refund_message = f"Refund Error: {str(e)}"
                        else:
                            refund_message = "Cashfree credentials missing, could not refund."
                    else:
                        refund_message = "Transaction not found for refund."
                
                conn.commit()
                cur.close()
                conn.close()
                
                if updated:
                    res_data = {"success": True, "ticket_id": ticket_id, "status": new_status}
                    if refund_message:
                        res_data["refund_message"] = refund_message
                    self._send_json(200, res_data)
                else:
                    self._send_json(404, {"success": False, "error": "Ticket not found"})
            except Exception as e:
                print(f"Error updating ticket: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE, PUT')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, cls=CustomJSONEncoder).encode('utf-8'))

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), AdminAPIHandler) as httpd:
        print(f"Admin Server running at http://localhost:{PORT}")
        httpd.serve_forever()

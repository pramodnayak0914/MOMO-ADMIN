import http.server
import socketserver
import json
import urllib.request
import urllib.parse
import os
import base64
import re
import smtplib
from email.mime.text import MIMEText
try:
    import resend
except ImportError:
    resend = None
import time
import hmac
import hashlib
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sqlite3_import_error = None
try:
    import sqlite3
    RealDictCursor = None
except ImportError as e:
    sqlite3 = None
    sqlite3_import_error = str(e)

PORT = int(os.environ.get('PORT', 8081))

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip() if os.environ.get('DATABASE_URL') else None
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.strip('"').strip("'")
if DATABASE_URL in ('YOUR_RENDER_DATABASE_URL_HERE', 'YOUR_DATABASE_URL_HERE', 'postgres://user:pass@localhost:5432/dbname', ''):
    DATABASE_URL = None
CASHFREE_CLIENT_ID = os.environ.get('CASHFREE_CLIENT_ID')
CASHFREE_CLIENT_SECRET = os.environ.get('CASHFREE_CLIENT_SECRET')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

import secrets
ADMIN_TOKEN_SECRET = os.environ.get('ADMIN_TOKEN_SECRET', secrets.token_hex(32))

MOCK_TRANSACTIONS = {}
MOCK_USERS = {} # Maps phone -> balance
MOCK_SUBSCRIPTIONS = {} # Maps phone -> list of sub dicts
import json
import os

MOCK_FAMILY = {}
FAMILY_DB_FILE = 'family_db.json'

if os.path.exists(FAMILY_DB_FILE):
    try:
        with open(FAMILY_DB_FILE, 'r') as f:
            MOCK_FAMILY = json.load(f)
    except:
        pass

def save_family_db():
    with open(FAMILY_DB_FILE, 'w') as f:
        json.dump(MOCK_FAMILY, f)

def get_cashfree_headers():
    return {
        "x-api-version": "2023-08-01",
        "x-client-id": (CASHFREE_CLIENT_ID or "").strip(),
        "x-client-secret": (CASHFREE_CLIENT_SECRET or "").strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def create_admin_token(role="admin", email=""):
    payload = {"role": role, "email": email, "exp": time.time() + 3600*24}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = hmac.new(ADMIN_TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_admin_token(token, required_roles=None):
    if required_roles is None: required_roles = ["admin", "superadmin"]
    try:
        if not token: return None
        payload_b64, signature = token.split('.')
        expected_sig = hmac.new(ADMIN_TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig): return None
        
        payload_padded = payload_b64 + '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_padded).decode())
        
        if payload.get("role") not in required_roles: return None
        if payload.get("exp", 0) < time.time(): return None
        return payload
    except:
        return None

DB_PATH = 'local_database.db'
ADMIN_PASSCODE = 'admin123'

def init_db():
    if not sqlite3:
        return
    try:
        conn = sqlite3.connect('local_database.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_identifier VARCHAR(255) NOT NULL,
                flow_type VARCHAR(50) NOT NULL,
                plan_details JSONB,
                brand_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                order_id VARCHAR(50) PRIMARY KEY,
                amount DECIMAL(10, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                user_identifier VARCHAR(255) NOT NULL,
                user_phone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id VARCHAR(100) NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                event_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS app_config (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id VARCHAR(50) UNIQUE NOT NULL,
                user_phone VARCHAR(20) NOT NULL,
                issue_type VARCHAR(100) NOT NULL,
                target_number VARCHAR(20),
                description TEXT,
                status VARCHAR(20) DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                order_id VARCHAR(50)
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            conn.rollback() # Just in case a previous statement failed
            cur.execute("ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'ACTIVE'")
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE users ADD COLUMN device_id VARCHAR(255)")
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE users ADD COLUMN last_ip VARCHAR(50)")
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE users ADD COLUMN login_location VARCHAR(255)")
        except Exception:
            conn.rollback()
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS fraud_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone VARCHAR(20),
                event_type VARCHAR(100) NOT NULL,
                details TEXT,
                ip_address VARCHAR(50),
                device_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone VARCHAR(20) NOT NULL,
                ip_address VARCHAR(50),
                device_id VARCHAR(255),
                user_agent TEXT,
                location VARCHAR(255),
                success INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS scratch_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone VARCHAR(20) NOT NULL,
                transaction_id VARCHAR(50),
                reward_amount DECIMAL(10, 2) DEFAULT 0.00,
                is_scratched INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS promo_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone VARCHAR(20) NOT NULL,
                promo_code VARCHAR(50) NOT NULL,
                transaction_id VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone VARCHAR(20) NOT NULL,
                target_number VARCHAR(20) NOT NULL,
                operator_brand VARCHAR(50) NOT NULL,
                plan_amount DECIMAL(10, 2) NOT NULL,
                validity_days INT DEFAULT 28,
                flow_type VARCHAR(20) DEFAULT 'phone',
                status VARCHAR(20) DEFAULT 'active',
                next_billing_date DATE NOT NULL,
                reminders_sent INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            cur.execute("ALTER TABLE subscriptions ADD COLUMN flow_type VARCHAR(20) DEFAULT 'phone'")
        except sqlite3.OperationalError:
            pass
        except sqlite3.Error:
            conn.rollback()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS family_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone VARCHAR(20) NOT NULL,
                member_name VARCHAR(100) NOT NULL,
                target_number VARCHAR(20) NOT NULL,
                operator_brand VARCHAR(50) NOT NULL,
                last_plan_amount DECIMAL(10, 2),
                expiry_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute("INSERT INTO app_config (key, value) VALUES ('assistant_name', 'OnlineRecharge AI') ON CONFLICT(key) DO NOTHING")
        
        # Migrations removed for SQLite
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS marketing_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opid VARCHAR(50),
                circle_code VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                email VARCHAR(100) PRIMARY KEY,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'admin',
                status VARCHAR(20) DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_email VARCHAR(100),
                action VARCHAR(255),
                details TEXT,
                ip_address VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Seed default admins
        import hashlib
        def hash_pass(p): return hashlib.sha256(p.encode()).hexdigest()
        cur.execute("INSERT INTO admins (email, password_hash, role) VALUES (?, ?, 'superadmin') ON CONFLICT(email) DO NOTHING", ('admin@momo.com', hash_pass('admin123')))
        cur.execute("INSERT INTO admins (email, password_hash, role) VALUES (?, ?, 'admin') ON CONFLICT(email) DO NOTHING", ('staff@momo.com', hash_pass('admin123')))

        
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization error: {e}")

init_db()

def capture_fraud_signals(headers, client_address, data):
    ip_address = headers.get('X-Forwarded-For', client_address[0]).split(',')[0].strip() if headers.get('X-Forwarded-For') else client_address[0]
    user_agent = headers.get('User-Agent', '')
    device_id = data.get('device_id') or 'unknown_device'
    return {
        "ip_address": ip_address,
        "user_agent": user_agent,
        "device_id": device_id,
        "location": "Unknown"
    }

def record_fraud_alert(user_phone, event_type, details, ip_address, device_id):
    if not sqlite3: return
    try:
        conn = sqlite3.connect('local_database.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO fraud_alerts (user_phone, event_type, details, ip_address, device_id) VALUES (?, ?, ?, ?, ?)",
            (user_phone, event_type, details, ip_address, device_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving fraud alert: {e}")

class APIHandler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)



        if self.path == '/admin' or self.path == '/admin/' or self.path == '/' or self.path == '':
            try:
                with open('admin.html', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
            return

        if self.path == '/super-admin' or self.path == '/super-admin/':
            try:
                with open('super_admin.html', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
            return


        if parsed_path.path == '/api/super-admin/logs':
            token = self.headers.get('Authorization', '').replace('Bearer ', '')
            admin = verify_admin_token(token, required_roles=['superadmin'])
            if not admin:
                self._send_json(401, {"success": False, "error": "Unauthorized"})
                return
            
            try:
                conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100")
                logs = [dict(r) for r in cur.fetchall()]
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "logs": logs})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if parsed_path.path == '/api/super-admin/tickets':
            query_params = urllib.parse.parse_qs(parsed_path.query)
            user_phone = query_params.get('user_phone', [None])[0]
            
            if not sqlite3:
                self._send_json(500, {"success": False, "error": "Database not configured"})
                return
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                if user_phone:
                    cur.execute("SELECT * FROM support_tickets WHERE user_phone = ? ORDER BY created_at DESC", (user_phone,))
                else:
                    cur.execute("SELECT * FROM support_tickets ORDER BY created_at DESC")
                    
                tickets = cur.fetchall()
                tickets = [dict(t) for t in tickets]
                for ticket in tickets:
                    if 'created_at' in ticket and ticket['created_at']:
                        ticket['created_at'] = ticket['created_at'].isoformat()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "tickets": tickets})
            except Exception as e:
                print(f"Error fetching tickets: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
                
        if self.path.startswith('/api/admin/data'):
            token = self.headers.get('Authorization', '').replace('Bearer ', '')
            if not verify_admin_token(token):
                self._send_json(401, {"success": False, "error": "Unauthorized"})
                return
            
            if not sqlite3:
                # Local Mock Fallback
                self._send_json(200, {
                    "success": True,
                    "metrics": {"users": len(MOCK_USERS), "recharges": len(MOCK_TRANSACTIONS), "revenue": 0, "failed": 0},
                    "users": [{"mobile": p, "name": "Test User", "suspended": False} for p in MOCK_USERS.keys()],
                    "transactions": [],
                    "support_tickets": [],
                    "fraud_alerts": []
                })
                return
                
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                # Fetch basic admin stats
                cur.execute("SELECT COUNT(*) as count FROM users")
                users_count = cur.fetchone()['count']
                
                cur.execute("SELECT COUNT(*) as count FROM transactions")
                txn_count = cur.fetchone()['count']
                
                cur.execute("SELECT SUM(amount) as revenue FROM transactions WHERE status = 'SUCCESS'")
                revenue_row = cur.fetchone()
                revenue = float(revenue_row['revenue']) if revenue_row and revenue_row['revenue'] else 0
                
                cur.execute("SELECT COUNT(*) as failed FROM transactions WHERE status = 'FAILED'")
                failed_count = cur.fetchone()['failed']
                
                # Fetch actual data
                cur.execute("SELECT phone_number as mobile, wallet_balance, created_at FROM users ORDER BY created_at DESC LIMIT 50")
                users_list = cur.fetchall()
                for u in users_list: u['wallet_balance'] = float(u['wallet_balance']); u['created_at'] = str(u['created_at'])
                
                cur.execute("SELECT order_id as id, amount, status, user_phone as target, operator_brand as brand, created_at as date FROM transactions ORDER BY created_at DESC LIMIT 50")
                txn_list = cur.fetchall()
                for t in txn_list: t['amount'] = float(t['amount']); t['date'] = str(t['date'])
                
                cur.execute("SELECT ticket_id as id, user_phone as userMobile, issue_type as issue, description, status, created_at as date FROM support_tickets ORDER BY created_at DESC LIMIT 50")
                tickets_list = cur.fetchall()
                for t in tickets_list: t['date'] = str(t['date'])
                
                cur.close()
                conn.close()
                
                self._send_json(200, {
                    "success": True,
                    "metrics": {"users": users_count, "recharges": txn_count, "revenue": revenue, "failed": failed_count},
                    "users": users_list,
                    "transactions": txn_list,
                    "support_tickets": tickets_list,
                    "fraud_alerts": [] # Mocked for now
                })
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return
            
        if self.path == '/api/config':
            assistant_name = "OnlineRecharge AI"
            db_error = None
            db_url_exists = bool(DATABASE_URL)
            psycopg2_exists = bool(psycopg2)
            if True:
                try:
                    conn = sqlite3.connect('local_database.db', check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT value FROM app_config WHERE key = 'assistant_name'")
                    row = cur.fetchone()
                    if row:
                        assistant_name = row['value']
                    cur.close()
                    conn.close()
                except Exception as e:
                    db_error = str(e)
                    print(f"Error fetching config: {e}")
            self._send_json(200, {
                "success": True, 
                "assistant_name": assistant_name, 
                "db_error": db_error,
                "debug_url_exists": db_url_exists,
                "debug_psycopg2_exists": psycopg2_exists,
                "debug_psycopg2_error": sqlite3_import_error
            })
        elif self.path == '/api/support/tickets':
            if not sqlite3:
                self._send_json(500, {"success": False, "error": "Database not configured"})
                return
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM support_tickets ORDER BY created_at DESC")
                tickets = cur.fetchall()
                # Convert datetime to string for JSON serialization
                tickets = [dict(t) for t in tickets]
                for ticket in tickets:
                    if 'created_at' in ticket and ticket['created_at']:
                        ticket['created_at'] = ticket['created_at'].isoformat()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "tickets": tickets})
            except Exception as e:
                print(f"Error fetching tickets: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path.startswith('/api/wallet'):
            query_params = urllib.parse.urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            user_phone = query_params.get('user_phone', [None])[0]
            if not user_phone:
                self._send_json(400, {"success": False, "error": "user_phone required"})
                return
            if not sqlite3:
                self._send_json(200, {"success": True, "balance": MOCK_USERS.get(user_phone, 1500.00)})
                return
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT wallet_balance FROM users WHERE phone_number = ?", (user_phone,))
                row = cur.fetchone()
                balance = float(row['wallet_balance']) if row else 0.00
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "balance": balance})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
                
        elif self.path.startswith('/api/operator'):
            query_params = urllib.parse.urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            number = query_params.get('number', [None])[0]
            if not number:
                self._send_json(400, {"success": False, "error": "number required"})
                return
            KWIK_API_KEY = "134fd9-91e1f3-f21b0c-5877b2-8e51a9"
            params = urllib.parse.urlencode({'api_key': KWIK_API_KEY, 'number': number})
            url = f"https://www.kwikapi.com/api/v2/operator_fetch_v2.php"
            try:
                headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/x-www-form-urlencoded'}
                req = urllib.request.Request(url, data=params.encode('utf-8'), method="POST", headers=headers)
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    self._send_json(200, data)
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
                
        elif self.path.startswith('/api/plans'):
            query_params = urllib.parse.urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            opid = query_params.get('opid', [None])[0]
            circle_code = query_params.get('circle_code', [None])[0]
            if not opid or not circle_code:
                self._send_json(400, {"success": False, "error": "opid and circle_code required"})
                return
                
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                cur = conn.cursor()
                cur.execute("INSERT INTO marketing_searches (opid, circle_code) VALUES (?, ?)", (opid, circle_code))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"Error logging marketing search: {e}")
                
            KWIK_API_KEY = "134fd9-91e1f3-f21b0c-5877b2-8e51a9"
            params = urllib.parse.urlencode({'api_key': KWIK_API_KEY, 'opid': opid, 'state_code': circle_code})
            url = f"https://www.kwikapi.com/api/v2/recharge_plans.php"
            try:
                headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/x-www-form-urlencoded'}
                req = urllib.request.Request(url, data=params.encode('utf-8'), method="POST", headers=headers)
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    self._send_json(200, data)
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path.startswith('/api/scratch_cards'):
            query_params = urllib.parse.urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            user_phone = query_params.get('user_phone', [None])[0]
            if not user_phone:
                self._send_json(400, {"success": False, "error": "user_phone required"})
                return
            if not sqlite3:
                self._send_json(200, {"success": True, "cards": [], "history": []})
                return
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT id, reward_amount, is_scratched FROM scratch_cards WHERE user_phone = ? AND is_scratched = FALSE", (user_phone,))
                cards = cur.fetchall()
                # Also fetch scratched ones for history
                cur.execute("SELECT id, reward_amount, is_scratched FROM scratch_cards WHERE user_phone = ? AND is_scratched = TRUE ORDER BY created_at DESC LIMIT 5", (user_phone,))
                history = cur.fetchall()
                cur.close()
                conn.close()
                # Decimal to float
                for c in cards: c['reward_amount'] = float(c['reward_amount'])
                for h in history: h['reward_amount'] = float(h['reward_amount'])
                self._send_json(200, {"success": True, "cards": cards, "history": history})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path.startswith('/api/subscriptions'):
            query_params = urllib.parse.urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            user_phone = query_params.get('user_phone', [None])[0]
            if not user_phone:
                self._send_json(400, {"success": False, "error": "user_phone is required"})
                return
            if not sqlite3:
                self._send_json(200, {"success": True, "subscriptions": MOCK_SUBSCRIPTIONS.get(user_phone, [])})
                return
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT id, target_number, operator_brand, plan_amount, status, flow_type, TO_CHAR(next_billing_date, 'YYYY-MM-DD') as next_billing_date FROM subscriptions WHERE user_phone = ? ORDER BY created_at DESC", (user_phone,))
                subscriptions = cur.fetchall()
                cur.close()
                conn.close()
                for sub in subscriptions: sub['plan_amount'] = float(sub['plan_amount'])
                self._send_json(200, {"success": True, "subscriptions": subscriptions})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
                
        elif self.path.startswith('/api/family'):
            query_params = urllib.parse.urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            user_phone = query_params.get('user_phone', [None])[0]
            if not user_phone:
                self._send_json(400, {"success": False, "error": "user_phone is required"})
                return
            user_phone = user_phone.strip()
            if not sqlite3:
                self._send_json(200, {"success": True, "family_members": MOCK_FAMILY.get(user_phone, [])})
                return
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT id, member_name, target_number, operator_brand, last_plan_amount, TO_CHAR(expiry_date, 'YYYY-MM-DD') as expiry_date FROM family_members WHERE user_phone = ? ORDER BY created_at DESC", (user_phone,))
                members = cur.fetchall()
                cur.close()
                conn.close()
                for m in members: 
                    if m['last_plan_amount']: m['last_plan_amount'] = float(m['last_plan_amount'])
                self._send_json(200, {"success": True, "family_members": members})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/auth/login':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                email = data.get('email', '')
                password = data.get('password', '')
                
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                import hashlib
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                
                conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM admins WHERE email = ? AND password_hash = ? AND status = 'ACTIVE'", (email, password_hash))
                admin = cur.fetchone()
                
                if admin:
                    role = admin['role']
                    token = create_admin_token(role=role, email=email)
                    
                    # Log the login
                    cur.execute("INSERT INTO audit_logs (admin_email, action, ip_address) VALUES (?, ?, ?)", 
                                (email, "Logged in", self.client_address[0]))
                    conn.commit()
                    cur.close()
                    conn.close()
                    
                    self._send_json(200, {"success": True, "token": token, "role": role})
                else:
                    cur.close()
                    conn.close()
                    self._send_json(401, {"success": False, "error": "Invalid credentials or suspended account"})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return



        if self.path == '/api/super-admin/config-update':
            token = self.headers.get('Authorization', '').replace('Bearer ', '')
            admin = verify_admin_token(token, required_roles=['superadmin'])
            if not admin:
                self._send_json(401, {"success": False, "error": "Unauthorized"})
                return
                
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                key = data.get('key')
                value = data.get('value')
                
                conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                cur = conn.cursor()
                
                # Fetch old value for audit
                cur.execute("SELECT value FROM app_config WHERE key = ?", (key,))
                row = cur.fetchone()
                old_value = row[0] if row else "None"
                
                cur.execute("INSERT INTO app_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
                
                # Audit Log
                cur.execute("INSERT INTO audit_logs (admin_email, action, details, ip_address) VALUES (?, ?, ?, ?)",
                            (admin['email'], f"Updated Config: {key}", f"Old: {old_value} -> New: {value}", self.client_address[0]))
                
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "message": "Updated successfully"})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if self.path == '/api/super-admin/staff':
            token = self.headers.get('Authorization', '').replace('Bearer ', '')
            admin = verify_admin_token(token, required_roles=['superadmin'])
            if not admin:
                self._send_json(401, {"success": False, "error": "Unauthorized"})
                return
                
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                action = data.get('action') # 'create' or 'suspend'
                target_email = data.get('email')
                
                conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                cur = conn.cursor()
                
                if action == 'create':
                    import hashlib
                    password = data.get('password')
                    role = data.get('role', 'admin')
                    pw_hash = hashlib.sha256(password.encode()).hexdigest()
                    cur.execute("INSERT INTO admins (email, password_hash, role) VALUES (?, ?, ?)", (target_email, pw_hash, role))
                    audit_action = f"Created Staff: {target_email} ({role})"
                elif action == 'suspend':
                    cur.execute("UPDATE admins SET status = 'SUSPENDED' WHERE email = ?", (target_email,))
                    audit_action = f"Suspended Staff: {target_email}"
                
                # Audit Log
                cur.execute("INSERT INTO audit_logs (admin_email, action, details, ip_address) VALUES (?, ?, ?, ?)",
                            (admin['email'], audit_action, "", self.client_address[0]))
                
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "message": audit_action})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if self.path == '/api/super-admin/data':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)

                token = self.headers.get('Authorization', '').replace('Bearer ', '')
                admin = verify_admin_token(token, required_roles=['superadmin'])
                if not admin:
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
                
                if True:
                    conn = sqlite3.connect('local_database.db', check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    
                    cur.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 500")
                    transactions_raw = cur.fetchall()
                    for t in transactions_raw:
                        t = dict(t)
                        t['created_at'] = str(t['created_at'])
                        t['amount'] = float(t['amount'])
                        transactions.append(t)
                        
                    cur.execute("SELECT * FROM purchases ORDER BY created_at DESC LIMIT 500")
                    purchases_raw = cur.fetchall()
                    for p in purchases_raw:
                        p = dict(p)
                        p['created_at'] = str(p['created_at'])
                        purchases.append(p)
                        
                    try:
                        cur.execute("SELECT event_type, COUNT(DISTINCT session_id) as count FROM analytics_events GROUP BY event_type")
                        analytics_raw = [dict(row) for row in cur.fetchall()]
                        for row in analytics_raw:
                            if row['event_type'] in analytics_summary:
                                analytics_summary[row['event_type']] = row['count']
                                
                        # Fetch Sales Leads
                        cur.execute("""
                            SELECT 
                                session_id,
                                MAX(json_extract(event_data, '$.mobile')) as contact,
                                MAX(json_extract(event_data, '$.email')) as email,
                                MAX(created_at) as last_active,
                                GROUP_CONCAT(event_type) as funnel_path
                            FROM analytics_events 
                            WHERE json_extract(event_data, '$.mobile') IS NOT NULL OR json_extract(event_data, '$.email') IS NOT NULL
                            GROUP BY session_id 
                            ORDER BY last_active DESC 
                            LIMIT 100
                        """)
                        leads_raw = cur.fetchall()
                        leads = []
                        for lead in leads_raw:
                            lead = dict(lead)
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
                        
                    current_assistant_name = ""
                    try:
                        cur.execute("SELECT value FROM app_config WHERE key = 'assistant_name'")
                        row = cur.fetchone()
                        if row:
                            current_assistant_name = row['value']
                    except Exception as e:
                        print(f"Error fetching config: {e}")
                        
                    # Fetch users, fraud alerts, and logins
                    users_list = []
                    fraud_alerts = []
                    logins = []
                    try:
                        cur.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 500")
                        users_raw = cur.fetchall()
                        for u in users_raw:
                            u = dict(u)
                            u['created_at'] = str(u['created_at'])
                            users_list.append(u)
                            
                        cur.execute("SELECT * FROM fraud_alerts ORDER BY created_at DESC LIMIT 200")
                        alerts_raw = cur.fetchall()
                        for a in alerts_raw:
                            a = dict(a)
                            a['created_at'] = str(a['created_at'])
                            fraud_alerts.append(a)
                            
                        cur.execute("SELECT * FROM login_history ORDER BY created_at DESC LIMIT 200")
                        logins_raw = cur.fetchall()
                        for l in logins_raw:
                            l = dict(l)
                            l['created_at'] = str(l['created_at'])
                            logins.append(l)
                    except Exception as e:
                        print(f"Error fetching user management data: {e}")
                        
                    # Business Analytics Calculation
                    business_metrics = {
                        "revenue": {"today": 0, "monthly": 0, "total": 0},
                        "recharge": {"total_count": 0, "success_pct": 0, "failure_pct": 0, "pending_pct": 0},
                        "users": {"new_today": 0, "active": 0, "returning": 0},
                        "operators": {"top_operator": "N/A", "top_plan": "N/A", "most_profitable": "N/A"}
                    }
                    try:
                        cur.execute("SELECT SUM(amount) as s FROM transactions WHERE LOWER(status) IN ('success', 'paid') AND date(created_at) = date('now')")
                        row = cur.fetchone()
                        if row and dict(row).get('s'): business_metrics['revenue']['today'] = float(dict(row)['s'])
                        
                        cur.execute("SELECT SUM(amount) as s FROM transactions WHERE LOWER(status) IN ('success', 'paid') AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')")
                        row = cur.fetchone()
                        if row and dict(row).get('s'): business_metrics['revenue']['monthly'] = float(dict(row)['s'])
                        
                        cur.execute("SELECT SUM(amount) as s FROM transactions WHERE LOWER(status) IN ('success', 'paid')")
                        row = cur.fetchone()
                        if row and dict(row).get('s'): business_metrics['revenue']['total'] = float(dict(row)['s'])
                        
                        cur.execute("SELECT COUNT(*) as c FROM transactions")
                        row = cur.fetchone()
                        total_tx = int(dict(row)['c']) if row and dict(row).get('c') else 0
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
                            
                        cur.execute("SELECT COUNT(*) as c FROM users WHERE date(created_at) = date('now')")
                        row = cur.fetchone()
                        if row and dict(row).get('c'): business_metrics['users']['new_today'] = int(dict(row)['c'])
                        
                        cur.execute("SELECT COUNT(*) as c FROM users")
                        row = cur.fetchone()
                        if row and dict(row).get('c'): business_metrics['users']['active'] = int(dict(row)['c'])
                        
                        cur.execute("SELECT COUNT(*) as c FROM (SELECT user_phone FROM transactions WHERE LOWER(status) IN ('success', 'paid') GROUP BY user_phone HAVING COUNT(*) > 1)")
                        row = cur.fetchone()
                        if row and dict(row).get('c'): business_metrics['users']['returning'] = int(dict(row)['c'])
                        
                        cur.execute("SELECT brand_name, COUNT(*) as c FROM purchases GROUP BY brand_name ORDER BY c DESC LIMIT 1")
                        row = cur.fetchone()
                        if row and dict(row).get('brand_name'): business_metrics['operators']['top_operator'] = dict(row)['brand_name']
                        
                        cur.execute("SELECT flow_type, COUNT(*) as c FROM purchases GROUP BY flow_type ORDER BY c DESC LIMIT 1")
                        row = cur.fetchone()
                        if row and dict(row).get('flow_type'): business_metrics['operators']['top_plan'] = dict(row)['flow_type']
                        
                        cur.execute('''
                            SELECT p.brand_name, SUM(t.amount) as s 
                            FROM transactions t 
                            JOIN purchases p ON t.user_identifier = p.user_identifier 
                            WHERE LOWER(t.status) IN ('success', 'paid') AND p.brand_name IS NOT NULL
                            GROUP BY p.brand_name 
                            ORDER BY s DESC LIMIT 1
                        ''')
                        row = cur.fetchone()
                        if row and dict(row).get('brand_name'): business_metrics['operators']['most_profitable'] = dict(row)['brand_name']
                        
                    except Exception as e:
                        print(f"Error fetching business metrics: {e}")
                        
                    # Marketing Data Calculation
                    marketing_data = {
                        "popular_plan": {"desc": "N/A", "count": 0},
                        "top_amounts": [],
                        "operator_share": [],
                        "acquisition": []
                    }
                    try:
                        # Popular plan (from marketing searches or purchases)
                        cur.execute("SELECT plan_details, COUNT(*) as c FROM purchases GROUP BY plan_details ORDER BY c DESC LIMIT 1")
                        row = cur.fetchone()
                        if row and dict(row).get('plan_details'): 
                            try:
                                plan_details = json.loads(dict(row)['plan_details'])
                                desc = f"{plan_details.get('price', 'Plan')} ({plan_details.get('validity', '')})"
                                marketing_data['popular_plan'] = {"desc": desc, "count": int(dict(row)['c'])}
                            except:
                                marketing_data['popular_plan'] = {"desc": "Popular Plan", "count": int(dict(row)['c'])}
                                
                        # Top amounts
                        cur.execute("SELECT amount, COUNT(*) as c FROM transactions WHERE LOWER(status) IN ('success', 'paid') GROUP BY amount ORDER BY c DESC LIMIT 4")
                        for row in cur.fetchall():
                            marketing_data['top_amounts'].append({"amount": float(dict(row)['amount']), "count": int(dict(row)['c'])})
                            
                        # Operator share
                        cur.execute("SELECT p.brand_name as op, COUNT(t.id) as c FROM transactions t JOIN purchases p ON t.user_identifier = p.user_identifier WHERE LOWER(t.status) IN ('success', 'paid') AND p.brand_name IS NOT NULL GROUP BY p.brand_name ORDER BY c DESC")
                        for row in cur.fetchall():
                            marketing_data['operator_share'].append({"operator": dict(row)['op'], "count": int(dict(row)['c'])})
                            
                        # Acquisition (from analytics_events utm_source or referer)
                        # Here we will just dummy it or pull from event_data if present
                        marketing_data['acquisition'] = [
                            {"source": "Direct Search", "count": 65},
                            {"source": "Google Ads", "count": 25},
                            {"source": "Referral", "count": 10}
                        ]
                    except Exception as e:
                        print(f"Error fetching marketing data: {e}")
                        
                    cur.close()
                    conn.close()
                else:
                    transactions = [{"order_id": "TEST", "status": "SUCCESS", "amount": 0, "created_at": "N/A"}]
                    current_assistant_name = "Offline"
                    users_list = []
                    fraud_alerts = []
                    logins = []
                    business_metrics = {}
                    marketing_data = {}
                
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
                    "marketing_data": marketing_data
                })
            except Exception as e:
                print(f"Error fetching admin data: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/super-admin/config':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)

                token = self.headers.get('Authorization', '').replace('Bearer ', '')
                admin = verify_admin_token(token, required_roles=['superadmin'])
                if not admin:
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                
                new_name = data.get('assistant_name')
                if not new_name:
                    self._send_json(400, {"success": False, "error": "Missing assistant_name"})
                    return
                
                if not DATABASE_URL:
                    self._send_json(500, {"success": False, "error": "Database URL is not configured on the server."})
                    return
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Python Database Driver failed to load. Check PYTHON_VERSION."})
                    return
                    
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO app_config (key, value) 
                    VALUES ('assistant_name', ?) 
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                ''', (new_name,))
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                print(f"Error setting config: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/super-admin/users/action':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)

                token = self.headers.get('Authorization', '').replace('Bearer ', '')
                admin = verify_admin_token(token, required_roles=['superadmin'])
                if not admin:
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                action = data.get('action')
                phone = data.get('phone_number')
                
                if not action or not phone:
                    self._send_json(400, {"success": False, "error": "Missing action or phone"})
                    return
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                    
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                if action == 'suspend':
                    cur.execute("UPDATE users SET status = 'SUSPENDED' WHERE phone_number = ?", (phone,))
                elif action == 'verify':
                    cur.execute("UPDATE users SET status = 'VERIFIED' WHERE phone_number = ?", (phone,))
                elif action == 'reset':
                    cur.execute("UPDATE users SET status = 'ACTIVE' WHERE phone_number = ?", (phone,))
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                print(f"Error user action: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/super-admin/recharges/retry':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)

                token = self.headers.get('Authorization', '').replace('Bearer ', '')
                admin = verify_admin_token(token, required_roles=['superadmin'])
                if not admin:
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                order_id = data.get('order_id')
                if not order_id:
                    self._send_json(400, {"success": False, "error": "Missing order_id"})
                    return
                
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                # Mock retry logic: Just mark it as success
                cur.execute("UPDATE transactions SET status = 'SUCCESS' WHERE order_id = ? AND status = 'failed'", (order_id,))
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "message": "Retry triggered successfully!"})
            except Exception as e:
                print(f"Error retry: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()


        if self.path == '/api/send-otp':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                mobile = data.get('mobile')
                otp = data.get('otp')
                
                if not mobile or not otp:
                    self._send_json(400, {"success": False, "error": "Missing mobile or otp"})
                    return
                
                # Check Twilio configuration
                TWILIO_ACCOUNT_SID_CLEAN = (TWILIO_ACCOUNT_SID or '').strip()
                TWILIO_AUTH_TOKEN_CLEAN = (TWILIO_AUTH_TOKEN or '').strip()
                TWILIO_PHONE_NUMBER_CLEAN = (TWILIO_PHONE_NUMBER or '').strip()
                
                if not TWILIO_ACCOUNT_SID_CLEAN or not TWILIO_AUTH_TOKEN_CLEAN or not TWILIO_PHONE_NUMBER_CLEAN:
                    self._send_json(200, {"success": False, "error": "Twilio configuration missing on server"})
                    return
                
                # Ensure sender number has + prefix
                from_number = TWILIO_PHONE_NUMBER_CLEAN
                if not from_number.startswith('+') and from_number.isdigit():
                    from_number = f"+{from_number}"

                # Format destination number (Twilio requires E.164 format, defaulting to India +91 if exactly 10 digits)
                formatted_mobile = mobile.strip()
                if len(formatted_mobile) == 10:
                    formatted_mobile = f"+91{formatted_mobile}"
                elif not formatted_mobile.startswith('+'):
                    formatted_mobile = f"+{formatted_mobile}"
                
                message = f"Your OnlineRecharge AI verification code is {otp}. Valid for 5 minutes."
                
                # Construct Twilio REST API Request
                url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID_CLEAN}/Messages.json"
                payload = urllib.parse.urlencode({
                    'To': formatted_mobile,
                    'From': from_number,
                    'Body': message,
                }).encode('utf-8')
                
                auth_str = f"{TWILIO_ACCOUNT_SID_CLEAN}:{TWILIO_AUTH_TOKEN_CLEAN}"
                auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
                
                req = urllib.request.Request(url, data=payload)
                req.add_header("Authorization", f"Basic {auth_bytes}")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                
                with urllib.request.urlopen(req) as response:
                    res_body = response.read().decode('utf-8')
                    self._send_json(200, {"success": True, "provider": "twilio"})
                    
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                print(f"Twilio API Error: {err_body}")
                self._send_json(200, {"success": False, "error": err_body})
            except Exception as e:
                print(f"Error processing SMS: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/verify-login':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                mobile = data.get('mobile')
                fraud_signals = capture_fraud_signals(self.headers, self.client_address, data)
                
                if not mobile:
                    self._send_json(400, {"success": False, "error": "Missing mobile"})
                    return
                
                if not sqlite3:
                    self._send_json(200, {"success": True, "suspended": False})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                # Check user status
                cur.execute("SELECT status FROM users WHERE phone_number = ?", (mobile,))
                user = cur.fetchone()
                suspended = False
                if user and user['status'] == 'SUSPENDED':
                    suspended = True
                    record_fraud_alert(mobile, "Suspended Login Attempt", "User attempted to login but is suspended.", fraud_signals['ip_address'], fraud_signals['device_id'])
                
                # Insert or update user details
                if not suspended:
                    if user:
                        cur.execute("UPDATE users SET last_ip = ?, device_id = ?, login_location = ? WHERE phone_number = ?",
                                    (fraud_signals['ip_address'], fraud_signals['device_id'], fraud_signals['location'], mobile))
                    else:
                        cur.execute("INSERT INTO users (phone_number, last_ip, device_id, login_location) VALUES (?, ?, ?, ?)",
                                    (mobile, fraud_signals['ip_address'], fraud_signals['device_id'], fraud_signals['location']))
                
                # Log login history
                cur.execute(
                    "INSERT INTO login_history (user_phone, ip_address, device_id, user_agent, location, success) VALUES (?, ?, ?, ?, ?, ?)",
                    (mobile, fraud_signals['ip_address'], fraud_signals['device_id'], fraud_signals['user_agent'], fraud_signals['location'], not suspended)
                )
                conn.commit()
                cur.close()
                conn.close()
                
                if suspended:
                    self._send_json(403, {"success": False, "suspended": True, "error": "Account suspended"})
                else:
                    self._send_json(200, {"success": True, "suspended": False})
                    
            except Exception as e:
                print(f"Error in verify-login: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
            return

        elif self.path == '/api/save-purchase':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                user_identifier = data.get('user_identifier')
                flow_type = data.get('flow_type')
                plan_details = data.get('plan_details')
                brand_name = data.get('brand_name')
                
                if True:
                    conn = sqlite3.connect('local_database.db', check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO purchases (user_identifier, flow_type, plan_details, brand_name) VALUES (?, ?, ?, ?)",
                        (user_identifier, flow_type, json.dumps(plan_details), brand_name)
                    )
                    conn.commit()
                    cur.close()
                    conn.close()
                else:
                    # In-memory mock or just skip for local prototype
                    pass
                
                self._send_json(200, {"success": True})
            except Exception as e:
                print(f"Error saving purchase: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/webhook/cashfree':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                signature = self.headers.get('x-webhook-signature', '')
                timestamp = self.headers.get('x-webhook-timestamp', '')
                
                if not signature or not timestamp:
                    self._send_json(400, {"success": False, "error": "Missing signature headers"})
                    return
                
                signature_data = timestamp.encode('utf-8') + post_data
                computed_hash = hmac.new(
                    (CASHFREE_CLIENT_SECRET or '').encode('utf-8'),
                    signature_data,
                    hashlib.sha256
                ).digest()
                computed_signature = base64.b64encode(computed_hash).decode('utf-8')
                
                if computed_signature != signature:
                    self._send_json(401, {"success": False, "error": "Invalid signature"})
                    return
                
                data = json.loads(post_data)
                if data.get('type') == 'PAYMENT_SUCCESS_WEBHOOK' or data.get('type') == 'PAYMENT_FAILED_WEBHOOK':
                    order_id = data.get('data', {}).get('order', {}).get('order_id')
                    payment_status = data.get('data', {}).get('payment', {}).get('payment_status')
                    
                    if order_id and payment_status and DATABASE_URL and psycopg2:
                        conn = sqlite3.connect('local_database.db', check_same_thread=False)
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()
                        cur.execute("UPDATE transactions SET status = ? WHERE order_id = ?", (payment_status, order_id))
                        conn.commit()
                        cur.close()
                        conn.close()
                        print(f"Webhook processed: order {order_id} status {payment_status}")
                
                self._send_json(200, {"success": True})
            except Exception as e:
                print(f"Webhook Error: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/support/ticket':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                ticket_id = data.get('ticket_id')
                user_phone = data.get('user_phone')
                issue_type = data.get('issue_type')
                target_number = data.get('target_number')
                description = data.get('description')
                order_id = data.get('order_id')
                # Save to PostgreSQL
                if True:
                    try:
                        conn = sqlite3.connect('local_database.db', check_same_thread=False)
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()
                        cur.execute('''
                            INSERT INTO support_tickets (ticket_id, user_phone, issue_type, target_number, description, status, order_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (ticket_id, user_phone, issue_type, target_number, description, 'OPEN', order_id))
                        conn.commit()
                        cur.close()
                        conn.close()
                        print(f"Ticket {ticket_id} saved to PostgreSQL database.")
                    except Exception as db_err:
                        print(f"Database Error while saving ticket: {db_err}")

                # Telegram Notification
                telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
                telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
                if telegram_bot_token and telegram_chat_id:
                    try:
                        tg_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
                        tg_message = f"🚨 *New Support Ticket: {ticket_id}*\n\n*Phone:* {user_phone}\n*Type:* {issue_type}\n*Target:* {target_number}\n\n*Description:*\n{description}"
                        tg_data = json.dumps({
                            "chat_id": telegram_chat_id,
                            "text": tg_message,
                            "parse_mode": "Markdown"
                        }).encode("utf-8")
                        
                        req = urllib.request.Request(tg_url, data=tg_data)
                        req.add_header("Content-Type", "application/json")
                        
                        with urllib.request.urlopen(req, timeout=10) as response:
                            print(f"SUCCESS! Telegram Alert Sent. Status: {response.getcode()}")
                    except Exception as tg_err:
                        print(f"TELEGRAM API ERROR: {tg_err}")
                else:
                    print("TELEGRAM credentials not set. Telegram alert not sent.")

                # Send email via Resend
                resend_api_key = os.environ.get('RESEND_API_KEY', '').strip()
                if resend_api_key:
                    resend.api_key = resend_api_key
                    
                    email_body = f"""
                    <h2>New Support Ticket: {ticket_id}</h2>
                    <p><strong>User Phone:</strong> {user_phone}</p>
                    <p><strong>Issue Type:</strong> {issue_type}</p>
                    <p><strong>Target Number:</strong> {target_number}</p>
                    <p><strong>Description:</strong></p>
                    <p>{description}</p>
                    """
                    params = {
                        "from": "OnlineRecharge AI Alerts <alerts@onlinerecharge-ai.com>",
                        "to": "customersupport@onlinerecharge-ai.com",
                        "subject": f"Support Ticket: {issue_type} [{ticket_id}]",
                        "html": email_body,
                    }
                    
                    # Call Resend API
                    try:
                        print(f"Attempting to send email via Resend to {params['to']}...")
                        email = resend.Emails.send(params)
                        print(f"SUCCESS! Resend Email Sent ID: {email}")
                    except Exception as resend_err:
                        print(f"RESEND API ERROR: {resend_err}")
                else:
                    print("RESEND_API_KEY not set. Email not sent, but ticket received.")

                # Send WhatsApp alert to Admin via Twilio
                if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
                    try:
                        # Clean SID for URL
                        TWILIO_ACCOUNT_SID_CLEAN = TWILIO_ACCOUNT_SID.strip()
                        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID_CLEAN}/Messages.json"
                        
                        wa_message = f"🚨 *New Support Ticket: {ticket_id}*\n\n*Phone:* {user_phone}\n*Type:* {issue_type}\n*Target:* {target_number}\n\n*Desc:* {description}"
                        
                        from_number = TWILIO_PHONE_NUMBER.strip()
                        if not from_number.startswith('whatsapp:'):
                            from_number = f"whatsapp:{from_number}"
                            
                        wa_data = urllib.parse.urlencode({
                            "To": "whatsapp:+916361864522",
                            "From": from_number,
                            "Body": wa_message
                        }).encode("utf-8")
                        
                        req = urllib.request.Request(url, data=wa_data)
                        auth_str = f"{TWILIO_ACCOUNT_SID_CLEAN}:{TWILIO_AUTH_TOKEN.strip()}"
                        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
                        req.add_header("Authorization", f"Basic {b64_auth}")
                        req.add_header("Content-Type", "application/x-www-form-urlencoded")
                        
                        print(f"Attempting to send WhatsApp alert via Twilio to whatsapp:+916361864522...")
                        with urllib.request.urlopen(req, timeout=10) as response:
                            print(f"SUCCESS! Admin WhatsApp Alert Sent. Status: {response.getcode()}")
                    except Exception as wa_err:
                        print(f"TWILIO WHATSAPP ERROR: {wa_err}")
                        
                # Send Confirmation to Customer via Twilio
                if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER and user_phone:
                    try:
                        TWILIO_ACCOUNT_SID_CLEAN = TWILIO_ACCOUNT_SID.strip()
                        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID_CLEAN}/Messages.json"
                        
                        customer_msg = f"Dear Customer, thank you for contacting OnlineRecharge AI Support.\n\nWe have received your ticket [{ticket_id}] regarding your {issue_type}. Our team is reviewing it and will resolve it shortly. We appreciate your patience!"
                        
                        # Format user phone
                        formatted_user_phone = user_phone.strip()
                        if len(formatted_user_phone) == 10:
                            formatted_user_phone = f"+91{formatted_user_phone}"
                        elif not formatted_user_phone.startswith('+'):
                            formatted_user_phone = f"+{formatted_user_phone}"
                            
                        auth_str = f"{TWILIO_ACCOUNT_SID_CLEAN}:{TWILIO_AUTH_TOKEN.strip()}"
                        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
                        
                        # 1. Send SMS
                        sms_data = urllib.parse.urlencode({
                            "To": formatted_user_phone,
                            "From": TWILIO_PHONE_NUMBER.strip(),
                            "Body": customer_msg
                        }).encode("utf-8")
                        
                        req_sms = urllib.request.Request(url, data=sms_data)
                        req_sms.add_header("Authorization", f"Basic {b64_auth}")
                        req_sms.add_header("Content-Type", "application/x-www-form-urlencoded")
                        
                        try:
                            with urllib.request.urlopen(req_sms, timeout=10) as response:
                                print(f"SUCCESS! Customer SMS Sent. Status: {response.getcode()}")
                        except Exception as e:
                            print(f"Could not send Customer SMS: {e}")
                            
                        # 2. Send WhatsApp
                        wa_from = TWILIO_PHONE_NUMBER.strip()
                        if not wa_from.startswith('whatsapp:'):
                            wa_from = f"whatsapp:{wa_from}"
                            
                        customer_wa_data = urllib.parse.urlencode({
                            "To": f"whatsapp:{formatted_user_phone}",
                            "From": wa_from,
                            "Body": customer_msg
                        }).encode("utf-8")
                        
                        req_wa = urllib.request.Request(url, data=customer_wa_data)
                        req_wa.add_header("Authorization", f"Basic {b64_auth}")
                        req_wa.add_header("Content-Type", "application/x-www-form-urlencoded")
                        
                        try:
                            with urllib.request.urlopen(req_wa, timeout=10) as response:
                                print(f"SUCCESS! Customer WhatsApp Sent. Status: {response.getcode()}")
                        except Exception as e:
                            print(f"Could not send Customer WhatsApp: {e}")
                            
                    except Exception as cust_err:
                        print(f"TWILIO CUSTOMER ALERT ERROR: {cust_err}")


                self._send_json(200, {"success": True, "ticket_id": ticket_id})
            except Exception as e:
                print(f"Error creating ticket: {e}")
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == '/api/payment/create-order':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                amount = float(data.get('amount', 0))
                user_identifier = str(data.get('user_identifier', ''))
                user_phone = data.get('user_phone')
                operator_brand = data.get('operator_brand', 'Unknown')
                order_id = f"ORDER_{int(time.time())}_{amount}"
                
                payment_session_id = f"mock_session_{order_id}"
                
                fraud_signals = capture_fraud_signals(self.headers, self.client_address, data)

                if DATABASE_URL and psycopg2 and user_phone:
                    conn = sqlite3.connect('local_database.db', check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    
                    # 1. Check if user is suspended
                    cur.execute("SELECT status FROM users WHERE phone_number = ?", (user_phone,))
                    user = cur.fetchone()
                    if user and user['status'] == 'SUSPENDED':
                        cur.close()
                        conn.close()
                        self._send_json(403, {"success": False, "error": "Account suspended due to suspicious activity."})
                        return

                    # 2. Auto Rules Engine
                    # Rule: 10 failed payments in 10 minutes -> Block temporarily
                    cur.execute("""
                        SELECT COUNT(*) as failed_count FROM transactions 
                        WHERE user_phone = ? AND status = 'failed' 
                        AND created_at >= NOW() - INTERVAL '10 minutes'
                    """, (user_phone,))
                    failed_count = cur.fetchone()['failed_count']
                    if failed_count >= 10:
                        cur.execute("UPDATE users SET status = 'SUSPENDED' WHERE phone_number = ?", (user_phone,))
                        record_fraud_alert(user_phone, "Auto Block", f"{failed_count} failed payments in 10 minutes.", fraud_signals['ip_address'], fraud_signals['device_id'])
                        conn.commit()
                        cur.close()
                        conn.close()
                        self._send_json(403, {"success": False, "error": "Too many failed attempts. Account suspended temporarily."})
                        return

                    # Rule: 20 recharges/day -> Flag for review
                    cur.execute("""
                        SELECT COUNT(*) as daily_count FROM transactions 
                        WHERE user_phone = ? 
                        AND created_at >= NOW() - INTERVAL '24 hours'
                    """, (user_phone,))
                    daily_count = cur.fetchone()['daily_count']
                    if daily_count >= 20:
                        record_fraud_alert(user_phone, "High Volume", f"{daily_count} recharges in 24 hours.", fraud_signals['ip_address'], fraud_signals['device_id'])
                    
                    cur.close()
                    conn.close()
                
                origin = self.headers.get('Origin')
                if not origin:
                    referer = self.headers.get('Referer')
                    if referer:
                        parsed = urllib.parse.urlparse(referer)
                        origin = f"{parsed.scheme}://{parsed.netloc}"
                    else:
                        origin = "http://localhost:8081"

                # If we have credentials, actually call Cashfree
                if CASHFREE_CLIENT_ID and CASHFREE_CLIENT_SECRET:
                    url = "https://sandbox.cashfree.com/pg/orders"
                    payload = json.dumps({
                        "order_amount": amount,
                        "order_currency": "INR",
                        "order_id": order_id,
                        "customer_details": {
                            "customer_id": "cust_" + re.sub(r'[^a-zA-Z0-9]', '', user_identifier)[:20] if re.sub(r'[^a-zA-Z0-9]', '', user_identifier) else "cust_unknown",
                            "customer_phone": re.sub(r'[^0-9]', '', user_identifier)[-10:] if len(re.sub(r'[^0-9]', '', user_identifier)) >= 10 else "9999999999"
                        },
                        "order_meta": {
                            "return_url": f"{origin}/?order_id={{order_id}}"
                        }
                    }).encode('utf-8')
                    
                    req = urllib.request.Request(url, data=payload, method="POST")
                    for k, v in get_cashfree_headers().items():
                        req.add_header(k, v)
                    
                    with urllib.request.urlopen(req) as response:
                        cf_res = json.loads(response.read().decode('utf-8'))
                        payment_session_id = cf_res.get("payment_session_id")
                
                if True:
                    conn = sqlite3.connect('local_database.db', check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    try:
                        cur.execute("ALTER TABLE transactions ADD COLUMN user_phone VARCHAR(20)")
                    except sqlite3.OperationalError:
                        pass
                    try:
                        cur.execute("ALTER TABLE transactions ADD COLUMN operator_brand VARCHAR(50)")
                    except sqlite3.OperationalError:
                        pass
                    except sqlite3.Error:
                        conn.rollback()
                    
                    cur.execute(
                        "INSERT INTO transactions (order_id, amount, status, user_identifier, user_phone, operator_brand) VALUES (?, ?, ?, ?, ?, ?)",
                        (order_id, amount, 'pending', user_identifier, user_phone, operator_brand)
                    )
                    conn.commit()
                    cur.close()
                    conn.close()
                else:
                    MOCK_TRANSACTIONS[order_id] = {
                        'amount': amount,
                        'status': 'pending',
                        'user_identifier': user_identifier,
                        'user_phone': user_phone,
                        'operator_brand': operator_brand
                    }
                
                self._send_json(200, {
                    "success": True, 
                    "order_id": order_id, 
                    "payment_session_id": payment_session_id
                })
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                print(f"Cashfree API Error: {err_body}")
                self._send_json(500, {"success": False, "error": err_body})
            except Exception as e:
                print(f"Error creating order: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/payment/verify':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                order_id = data.get('order_id')
                is_mock = data.get('is_mock', False)
                
                order_status = "PENDING"
                if is_mock:
                    order_status = "PAID"
                else:
                    # Ask Cashfree to verify
                    url = f"https://sandbox.cashfree.com/pg/orders/{order_id}"
                    req = urllib.request.Request(url, method="GET")
                    for k, v in get_cashfree_headers().items():
                        req.add_header(k, v)
                    
                    with urllib.request.urlopen(req) as response:
                        cf_res = json.loads(response.read().decode('utf-8'))
                        order_status = cf_res.get("order_status")
                
                if order_status == "PAID":
                    if True:
                        import random
                        conn = sqlite3.connect('local_database.db', check_same_thread=False)
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()
                        cur.execute("SELECT status, amount, user_phone, user_identifier, operator_brand FROM transactions WHERE order_id = ?", (order_id,))
                        txn = cur.fetchone()
                        
                        if txn and txn['status'] != 'success':
                            cur.execute("UPDATE transactions SET status = 'success' WHERE order_id = ?", (order_id,))
                            
                            # Generate scratch card (0.5% to 1.5% of transaction amount)
                            if txn['user_phone']:
                                # Ensure user exists in users table
                                cur.execute("INSERT INTO users (phone_number) VALUES (?) ON CONFLICT DO NOTHING", (txn['user_phone'],))
                                
                                reward_amt = round(float(txn['amount']) * random.uniform(0.005, 0.015), 2)
                                # Guarantee minimum of 1 Rupee for good UX if amount was small
                                if reward_amt < 1.00:
                                    reward_amt = 1.00
                                    
                                cur.execute('''
                                    INSERT INTO scratch_cards (user_phone, transaction_id, reward_amount) 
                                    VALUES (?, ?, ?)
                                ''', (txn['user_phone'], order_id, reward_amt))
                        
                        conn.commit()
                        cur.close()
                        conn.close()
                    else:
                        if order_id in MOCK_TRANSACTIONS:
                            txn = MOCK_TRANSACTIONS[order_id]
                            if txn['status'] != 'success':
                                txn['status'] = 'success'
                        else:
                            txn = None

                    # --- TRIGGER KWIK API RECHARGE ---
                    if txn and txn.get('operator_brand') and txn.get('user_identifier'):
                        target_num = txn['user_identifier']
                        brand = txn['operator_brand']
                        txn_amount = txn['amount']
                        
                        # KwikAPI settings
                        KWIK_API_KEY = "134fd9-91e1f3-f21b0c-5877b2-8e51a9"
                        KWIK_BASE_URL = "https://www.kwikapi.com/api/v2/recharge.php"
                        
                        # TODO: Map your operator brands to exact KwikAPI OPIDs here!
                        opid_map = {
                            "Jio": 1,
                            "Airtel": 2,
                            "Vi": 3,
                            "BSNL": 4
                        }
                        
                        opid = opid_map.get(brand, 1) # Default to 1 if unknown
                        
                        params = urllib.parse.urlencode({
                            'api_key': KWIK_API_KEY,
                            'number': target_num,
                            'amount': txn_amount,
                            'opid': opid,
                            'order_id': order_id
                        })
                        
                        kwik_url = f"{KWIK_BASE_URL}?{params}"
                        
                        try:
                            # We are calling the live API! 
                            req = urllib.request.Request(kwik_url, method="GET")
                            with urllib.request.urlopen(req, timeout=10) as response:
                                kwik_res = json.loads(response.read().decode('utf-8'))
                                print(f"KwikAPI Response: {kwik_res}")
                                # In a production system, you would save kwik_res['status'] and kwik_res['opr_id'] back to the DB
                        except Exception as e:
                            print(f"KwikAPI Error: {e}")
                            
                self._send_json(200, {"success": True, "status": order_status})
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                print(f"Cashfree Verification API Error: {err_body}")
                self._send_json(500, {"success": False, "error": err_body})
            except Exception as e:
                print(f"Error verifying order: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/payment/wallet-checkout':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                amount = float(data.get('amount', 0))
                user_phone = data.get('user_phone')
                promo_code = data.get('promo_code')
                
                if not sqlite3:
                    user_balance = MOCK_USERS.get(user_phone, 1500.00)
                    if user_balance < amount:
                        self._send_json(400, {"success": False, "error": "Insufficient wallet balance"})
                    else:
                        MOCK_USERS[user_phone] = user_balance - amount
                        self._send_json(200, {"success": True, "order_id": f"WALLET_{int(time.time())}_{amount}"})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                # Verify balance
                cur.execute("SELECT wallet_balance FROM users WHERE phone_number = ?", (user_phone,))
                user = cur.fetchone()
                
                if not user or float(user['wallet_balance']) < amount:
                    self._send_json(400, {"success": False, "error": "Insufficient wallet balance"})
                else:
                    new_balance = float(user['wallet_balance']) - amount
                    cur.execute("UPDATE users SET wallet_balance = ? WHERE phone_number = ?", (new_balance, user_phone))
                    order_id = f"WALLET_{int(time.time())}_{amount}"
                    
                    if promo_code:
                        cur.execute("INSERT INTO promo_usage (user_phone, promo_code, transaction_id) VALUES (?, ?, ?)", (user_phone, promo_code, order_id))
                    
                    conn.commit()
                    msg = f"✅ Recharge Receipt: Successful payment of ₹{amount} from your wallet. Order ID: {order_id}"
                    self._send_twilio_sms(user_phone, msg)
                    self._send_twilio_whatsapp(user_phone, msg)
                    self._send_json(200, {"success": True, "order_id": order_id})
                cur.close()
                conn.close()
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == '/api/create-payment-intent':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                amount = float(data.get('amount', 0))
                payment_method = data.get('payment_method')
                
                if not amount or amount <= 0:
                    self._send_json(400, {'error': 'Invalid amount'})
                    return
                if not payment_method:
                    self._send_json(400, {'error': 'No payment method provided'})
                    return

                # Simulate processing time for secure gateway connection (2 seconds)
                time.sleep(2)
                # Mocking a successful response from a payment provider
                response = {
                    'status': 'success',
                    'message': 'Payment processed securely',
                    'transaction_id': 'txn_' + os.urandom(8).hex(),
                    'amount_added': amount,
                    'method': payment_method
                }
                self._send_json(200, response)
            except Exception as e:
                print(f"Error processing payment intent: {e}")
                self._send_json(500, {"error": str(e)})
        elif self.path == '/api/track':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                session_id = data.get('session_id')
                event_type = data.get('event_type')
                event_data = data.get('event_data', {})
                
                if session_id and event_type:
                    if True:
                        conn = sqlite3.connect('local_database.db', check_same_thread=False)
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()
                        cur.execute(
                            "INSERT INTO analytics_events (session_id, event_type, event_data) VALUES (?, ?, ?)",
                            (session_id, event_type, json.dumps(event_data))
                        )
                        conn.commit()
                        cur.close()
                        conn.close()
                    self._send_json(200, {"success": True})
                else:
                    self._send_json(400, {"success": False, "error": "Missing parameters"})
            except Exception as e:
                print(f"Error tracking event: {e}")
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == '/api/subscriptions':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                user_phone = data.get('user_phone')
                target_number = data.get('target_number')
                operator_brand = data.get('operator_brand')
                plan_amount = data.get('plan_amount')
                flow_type = data.get('flow_type', 'phone')
                
                if not all([user_phone, target_number, operator_brand, plan_amount]):
                    self._send_json(400, {"success": False, "error": "Missing required fields"})
                    return
                
                validity_days = data.get('validity_days', 28)
                try:
                    validity_days = int(validity_days)
                except (ValueError, TypeError):
                    validity_days = 28
                
                # Calculate next billing date
                from datetime import datetime, timedelta
                next_date = (datetime.now() + timedelta(days=validity_days)).date()
                
                if True:
                    conn = sqlite3.connect('local_database.db', check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT id FROM subscriptions WHERE user_phone=? AND target_number=?", (user_phone, target_number))
                        existing = cur.fetchone()
                        if existing:
                            cur.execute(
                                "UPDATE subscriptions SET operator_brand=?, plan_amount=?, validity_days=?, next_billing_date=?, flow_type=? WHERE id=?",
                                (operator_brand, plan_amount, validity_days, next_date, flow_type, existing[0])
                            )
                        else:
                            cur.execute(
                                "INSERT INTO subscriptions (user_phone, target_number, operator_brand, plan_amount, validity_days, next_billing_date, flow_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (user_phone, target_number, operator_brand, plan_amount, validity_days, next_date, flow_type)
                            )
                        conn.commit()
                        cur.close()
                        conn.close()
                    except Exception as e:
                        print("DB error saving subscription:", e)
                else:
                    if user_phone not in MOCK_SUBSCRIPTIONS: MOCK_SUBSCRIPTIONS[user_phone] = []
                    found = False
                    for sub in MOCK_SUBSCRIPTIONS[user_phone]:
                        if sub['target_number'] == target_number:
                            sub.update({'operator_brand': operator_brand, 'plan_amount': plan_amount, 'next_billing_date': next_date.strftime('%Y-%m-%d'), 'flow_type': flow_type})
                            found = True
                            break
                    if not found:
                        MOCK_SUBSCRIPTIONS[user_phone].append({'id': len(MOCK_SUBSCRIPTIONS[user_phone])+1, 'target_number': target_number, 'operator_brand': operator_brand, 'plan_amount': plan_amount, 'status': 'active', 'next_billing_date': next_date.strftime('%Y-%m-%d'), 'flow_type': flow_type})
                
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
                
        elif self.path == '/api/cron/process-subscriptions':
            # This endpoint is called twice a day by a cron job to process reminders and deductions.
            if not sqlite3:
                self._send_json(500, {"success": False, "error": "Database not configured"})
                return
            try:
                from datetime import datetime, timedelta
                today = datetime.now().date()
                reminder_date = today + timedelta(days=3)
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                # 1. PROCESS REMINDERS (Due in 3 days, reminders_sent < 2)
                cur.execute("SELECT * FROM subscriptions WHERE status = 'active' AND next_billing_date = ? AND reminders_sent < 2", (reminder_date,))
                reminders = cur.fetchall()
                for sub in reminders:
                    sub = dict(sub)
                    brand = sub['operator_brand']
                    is_telecom = brand in ['Jio', 'Airtel', 'Vi', 'BSNL']
                    if is_telecom:
                        message = f"Your Rs {sub['plan_amount']} auto-recharge for {brand} ({sub['target_number']}) is due in 3 days. Ensure wallet balance to avoid missing out on data!"
                    else:
                        message = f"Your Rs {sub['plan_amount']} auto-renewal for {brand} ({sub['target_number']}) is due in 3 days. Ensure wallet balance!"
                    
                    self._send_twilio_sms(sub['user_phone'], message)
                    self._send_twilio_whatsapp(sub['user_phone'], message)
                    cur.execute("UPDATE subscriptions SET reminders_sent = reminders_sent + 1 WHERE id = ?", (sub['id'],))
                conn.commit()
                
                # 2. PROCESS RECHARGES (Due today or past due)
                cur.execute("SELECT s.*, u.wallet_balance FROM subscriptions s JOIN users u ON s.user_phone = u.phone_number WHERE s.status = 'active' AND s.next_billing_date <= ?", (today,))
                due_subs = cur.fetchall()
                for sub in due_subs:
                    sub = dict(sub)
                    amount = float(sub['plan_amount'])
                    balance = float(sub['wallet_balance'])
                    if balance >= amount:
                        # Deduct balance
                        cur.execute("UPDATE users SET wallet_balance = wallet_balance - ? WHERE phone_number = ?", (amount, sub['user_phone']))
                        
                        # Trigger KwikAPI
                        KWIK_API_KEY = "134fd9-91e1f3-f21b0c-5877b2-8e51a9"
                        KWIK_BASE_URL = "https://www.kwikapi.com/api/v2/recharge.php"
                        opid_map = {"Jio": 1, "Airtel": 2, "Vi": 3, "BSNL": 4}
                        opid = opid_map.get(sub['operator_brand'], 1)
                        import uuid
                        order_id = f"AUTO-{uuid.uuid4().hex[:8]}"
                        params = urllib.parse.urlencode({'api_key': KWIK_API_KEY, 'number': sub['target_number'], 'amount': amount, 'opid': opid, 'order_id': order_id})
                        kwik_url = f"{KWIK_BASE_URL}?{params}"
                        
                        try:
                            req = urllib.request.Request(kwik_url, method="GET")
                            with urllib.request.urlopen(req, timeout=10) as response:
                                pass # We ignore the response here assuming success for now
                        except:
                            pass
                            
                        # Update subscription
                        validity_days = sub.get('validity_days', 28)
                        if not validity_days: validity_days = 28
                        next_date = today + timedelta(days=int(validity_days))
                        cur.execute("UPDATE subscriptions SET next_billing_date = ?, reminders_sent = 0 WHERE id = ?", (next_date, sub['id']))
                        
                        # Send success SMS
                        brand = sub['operator_brand']
                        action = 'Auto-Recharge' if brand in ['Jio', 'Airtel', 'Vi', 'BSNL'] else 'Auto-Renewal'
                        msg = f"✅ {action} Success! Rs {amount} for {brand} ({sub['target_number']}) is complete. Next due: {next_date}"
                        self._send_twilio_sms(sub['user_phone'], msg)
                        self._send_twilio_whatsapp(sub['user_phone'], msg)
                    else:
                        # Insufficient balance - Send failure SMS once a day
                        if sub['reminders_sent'] < 10: # Just a flag to not spam forever
                            fail_msg = f"❌ Auto-Recharge Failed! Rs {amount} for {sub['target_number']} failed due to low wallet balance. Top up now to activate it."
                            self._send_twilio_sms(sub['user_phone'], fail_msg)
                            self._send_twilio_whatsapp(sub['user_phone'], fail_msg)
                            cur.execute("UPDATE subscriptions SET reminders_sent = 10 WHERE id = ?", (sub['id'],))
                
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True, "reminders_processed": len(reminders), "recharges_processed": len(due_subs)})
            except Exception as e:
                print(f"Cron Error: {e}")
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == '/api/family':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                user_phone = data.get('user_phone')
                if user_phone: user_phone = user_phone.strip()
                member_name = data.get('member_name')
                target_number = data.get('target_number')
                operator_brand = data.get('operator_brand')
                last_plan_amount = data.get('last_plan_amount')
                expiry_date = data.get('expiry_date') # can be string 'YYYY-MM-DD'
                
                if not all([user_phone, member_name, target_number, operator_brand]):
                    self._send_json(400, {"success": False, "error": "Missing required fields"})
                    return
                if not sqlite3:
                    if user_phone not in MOCK_FAMILY: MOCK_FAMILY[user_phone] = []
                    MOCK_FAMILY[user_phone].append({'id': len(MOCK_FAMILY[user_phone])+1, 'member_name': member_name, 'target_number': target_number, 'operator_brand': operator_brand, 'last_plan_amount': last_plan_amount, 'expiry_date': expiry_date})
                    save_family_db()
                    self._send_json(200, {"success": True, "message": "Family member added"})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO family_members (user_phone, member_name, target_number, operator_brand, last_plan_amount, expiry_date) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_phone, member_name, target_number, operator_brand, last_plan_amount, expiry_date)
                )
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == '/api/family/bulk_recharge':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                user_phone = data.get('user_phone')
                member_ids = data.get('member_ids') # list of family_member IDs
                total_amount = data.get('total_amount')
                
                if not user_phone or not member_ids or not total_amount:
                    self._send_json(400, {"success": False, "error": "Missing parameters"})
                    return
                
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                # Check wallet balance
                cur.execute("SELECT wallet_balance FROM users WHERE phone_number = ?", (user_phone,))
                user = cur.fetchone()
                if not user or float(user['wallet_balance']) < float(total_amount):
                    self._send_json(400, {"success": False, "error": "Insufficient wallet balance"})
                    cur.close()
                    conn.close()
                    return
                
                # Deduct balance
                cur.execute("UPDATE users SET wallet_balance = wallet_balance - ? WHERE phone_number = ?", (total_amount, user_phone))
                
                # Process each member
                for mem_id in member_ids:
                    cur.execute("SELECT * FROM family_members WHERE id = ? AND user_phone = ?", (mem_id, user_phone))
                    mem = cur.fetchone()
                    if mem:
                        # Update expiry date by 28 days
                        from datetime import datetime, timedelta
                        today = datetime.now().date()
                        new_expiry = today + timedelta(days=28)
                        cur.execute("UPDATE family_members SET expiry_date = ? WHERE id = ?", (new_expiry, mem_id))
                        
                        # Trigger KwikAPI
                        amount = float(mem['last_plan_amount'] or 0)
                        if amount > 0:
                            KWIK_API_KEY = "134fd9-91e1f3-f21b0c-5877b2-8e51a9"
                            KWIK_BASE_URL = "https://www.kwikapi.com/api/v2/recharge.php"
                            opid_map = {"Jio": 1, "Airtel": 2, "Vi": 3, "BSNL": 4}
                            opid = opid_map.get(mem['operator_brand'], 1)
                            import uuid
                            order_id = f"FAM-{uuid.uuid4().hex[:8]}"
                            params = urllib.parse.urlencode({'api_key': KWIK_API_KEY, 'number': mem['target_number'], 'amount': amount, 'opid': opid, 'order_id': order_id})
                            kwik_url = f"{KWIK_BASE_URL}?{params}"
                            try:
                                req = urllib.request.Request(kwik_url, method="GET")
                                with urllib.request.urlopen(req, timeout=5) as response:
                                    pass 
                            except:
                                pass
                
                conn.commit()
                msg = f"✅ Family Recharge Receipt: Successfully recharged {len(member_ids)} family members! Total paid: ₹{total_amount}."
                self._send_twilio_sms(user_phone, msg)
                self._send_twilio_whatsapp(user_phone, msg)
                cur.close()
                conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        parsed_path = urllib.parse.urlparse(self.path)

        if self.path.startswith('/api/super-admin/tickets/'):
            ticket_id = self.path.split('/')[-1]
            content_length = int(self.headers.get('Content-Length', 0))
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
                
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                cur.execute("SELECT user_phone, status FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
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
                        temp_cur.execute("SELECT order_id FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
                        temp_row = temp_cur.fetchone()
                        if temp_row and temp_row[0]:
                            provided_order_id = temp_row[0]
                except Exception:
                    conn.rollback()
                
                cur.execute(
                    "UPDATE support_tickets SET status = ? WHERE ticket_id = ? RETURNING id",
                    (new_status, ticket_id)
                )
                updated = cur.fetchone()
                
                refund_message = None
                
                if updated and new_status == 'REFUNDED' and ticket_row:
                    user_phone = ticket_row[0]
                    
                    if provided_order_id:
                        cur.execute("SELECT order_id, amount, status FROM transactions WHERE order_id = ?", (provided_order_id,))
                    else:
                        cur.execute(
                            "SELECT order_id, amount, status FROM transactions WHERE user_identifier = ? AND status IN ('success', 'PAID') ORDER BY created_at DESC LIMIT 1",
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
                                    cur.execute("UPDATE transactions SET status = 'REFUNDED' WHERE order_id = ?", (order_id,))
                                    refund_message = f"Refunded ₹{amount} for order {order_id}. Status: {refund_status}"
                            except urllib.error.HTTPError as e:
                                refund_message = f"Cashfree Refund Failed: {e.read().decode('utf-8')}"
                            except Exception as e:
                                refund_message = f"Refund Error: {str(e)}"
                        else:
                            refund_message = "Cashfree credentials missing, could not refund."
                    else:
                        refund_message = "No successful transaction found for this user."
                        
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
        if self.path.startswith('/api/support/tickets/'):
            ticket_id = self.path.split('/')[-1]
            content_length = int(self.headers.get('Content-Length', 0))
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
                
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "UPDATE support_tickets SET status = ? WHERE ticket_id = ? RETURNING id",
                    (new_status, ticket_id)
                )
                updated = cur.fetchone()
                conn.commit()
                cur.close()
                conn.close()
                
                if updated:
                    self._send_json(200, {"success": True, "ticket_id": ticket_id, "status": new_status})
                else:
                    self._send_json(404, {"success": False, "error": "Ticket not found"})
            except Exception as e:
                print(f"Error updating ticket: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/scratch_card/reveal':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                card_id = data.get('card_id')
                user_phone = data.get('user_phone')
                
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                # Check if card exists and is not scratched
                cur.execute("SELECT reward_amount, is_scratched FROM scratch_cards WHERE id = ? AND user_phone = ?", (card_id, user_phone))
                card = cur.fetchone()
                
                if not card:
                    self._send_json(404, {"success": False, "error": "Scratch card not found"})
                elif card['is_scratched']:
                    self._send_json(400, {"success": False, "error": "Already scratched"})
                else:
                    reward = float(card['reward_amount'])
                    # Update card and user wallet in a transaction
                    cur.execute("UPDATE scratch_cards SET is_scratched = TRUE WHERE id = ?", (card_id,))
                    cur.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE phone_number = ?", (reward, user_phone))
                    conn.commit()
                    self._send_json(200, {"success": True, "reward": reward})
                cur.close()
                conn.close()
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == '/api/promo/validate':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                code = data.get('code', '').upper()
                user_phone = data.get('user_phone')
                
                if not sqlite3:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                cur.execute("SELECT * FROM promo_codes WHERE code = ?", (code,))
                promo = cur.fetchone()
                
                if not promo:
                    self._send_json(404, {"success": False, "error": "Invalid promo code"})
                else:
                    # Check usage limit for user
                    cur.execute("SELECT COUNT(*) as uses FROM promo_usage WHERE user_phone = ? AND promo_code = ?", (user_phone, code))
                    usage = cur.fetchone()
                    if usage and usage['uses'] >= promo['usage_limit']:
                        self._send_json(400, {"success": False, "error": "Promo code usage limit reached"})
                    else:
                        # Return promo details (we don't apply it yet, just validate)
                        # We would apply it during checkout
                        self._send_json(200, {
                            "success": True, 
                            "discount_type": promo['discount_type'],
                            "value": float(promo['value']),
                            "max_cap": float(promo['max_cap']) if promo['max_cap'] else None
                        })
                
                cur.close()
                conn.close()
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == '/api/subscriptions/status':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                sub_id = data.get('id')
                new_status = data.get('status')
                if not sub_id or new_status not in ['active', 'paused', 'cancelled']:
                    self._send_json(400, {"success": False, "error": "Invalid input"})
                    return
                if not sqlite3:
                    for phone, subs in MOCK_SUBSCRIPTIONS.items():
                        for sub in subs:
                            sub = dict(sub)
                            if str(sub['id']) == str(sub_id):
                                sub['status'] = new_status
                    self._send_json(200, {"success": True})
                    return
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("UPDATE subscriptions SET status = ? WHERE id = ?", (new_status, sub_id))
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith('/api/family'):
            query_params = urllib.parse.urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            member_id = query_params.get('id', [None])[0]
            if not member_id:
                self._send_json(400, {"success": False, "error": "id is required"})
                return
            if not sqlite3:
                for phone, members in MOCK_FAMILY.items():
                    MOCK_FAMILY[phone] = [m for m in members if str(m['id']) != str(member_id)]
                save_family_db()
                self._send_json(200, {"success": True, "message": "Removed from family"})
                return
            try:
                conn = sqlite3.connect('local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("DELETE FROM family_members WHERE id = ?", (member_id,))
                conn.commit()
                cur.close()
                conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, status_code, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_twilio_sms(self, to_number, message):
        TWILIO_ACCOUNT_SID_CLEAN = (TWILIO_ACCOUNT_SID or '').strip()
        TWILIO_AUTH_TOKEN_CLEAN = (TWILIO_AUTH_TOKEN or '').strip()
        TWILIO_PHONE_NUMBER_CLEAN = (TWILIO_PHONE_NUMBER or '').strip()
        if not TWILIO_ACCOUNT_SID_CLEAN or not TWILIO_AUTH_TOKEN_CLEAN or not TWILIO_PHONE_NUMBER_CLEAN:
            print("Twilio config missing, skipping SMS")
            return
            
        from_number = TWILIO_PHONE_NUMBER_CLEAN
        if not from_number.startswith('+') and from_number.isdigit(): from_number = f"+{from_number}"
        formatted_mobile = to_number.strip()
        if len(formatted_mobile) == 10: formatted_mobile = f"+91{formatted_mobile}"
        elif not formatted_mobile.startswith('+'): formatted_mobile = f"+{formatted_mobile}"
        
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID_CLEAN}/Messages.json"
        payload = urllib.parse.urlencode({'To': formatted_mobile, 'From': from_number, 'Body': message}).encode('utf-8')
        auth_str = f"{TWILIO_ACCOUNT_SID_CLEAN}:{TWILIO_AUTH_TOKEN_CLEAN}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        req = urllib.request.Request(url, data=payload)
        req.add_header("Authorization", f"Basic {auth_bytes}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req) as response:
                pass
        except Exception as e:
            print(f"Twilio API Error sending SMS to {formatted_mobile}: {e}")

    def _send_twilio_whatsapp(self, to_number, message):
        TWILIO_ACCOUNT_SID_CLEAN = (TWILIO_ACCOUNT_SID or '').strip()
        TWILIO_AUTH_TOKEN_CLEAN = (TWILIO_AUTH_TOKEN or '').strip()
        TWILIO_PHONE_NUMBER_CLEAN = (TWILIO_PHONE_NUMBER or '').strip()
        if not TWILIO_ACCOUNT_SID_CLEAN or not TWILIO_AUTH_TOKEN_CLEAN or not TWILIO_PHONE_NUMBER_CLEAN:
            print("Twilio config missing, skipping WhatsApp")
            return
            
        from_number = f"whatsapp:{TWILIO_PHONE_NUMBER_CLEAN}"
        if not TWILIO_PHONE_NUMBER_CLEAN.startswith('+') and TWILIO_PHONE_NUMBER_CLEAN.isdigit(): 
            from_number = f"whatsapp:+{TWILIO_PHONE_NUMBER_CLEAN}"
            
        formatted_mobile = to_number.strip()
        if len(formatted_mobile) == 10: formatted_mobile = f"whatsapp:+91{formatted_mobile}"
        elif not formatted_mobile.startswith('+'): formatted_mobile = f"whatsapp:+{formatted_mobile}"
        else: formatted_mobile = f"whatsapp:{formatted_mobile}"
        
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID_CLEAN}/Messages.json"
        payload = urllib.parse.urlencode({'To': formatted_mobile, 'From': from_number, 'Body': message}).encode('utf-8')
        auth_str = f"{TWILIO_ACCOUNT_SID_CLEAN}:{TWILIO_AUTH_TOKEN_CLEAN}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        req = urllib.request.Request(url, data=payload)
        req.add_header("Authorization", f"Basic {auth_bytes}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req) as response:
                pass
        except Exception as e:
            print(f"Twilio API Error sending WhatsApp to {formatted_mobile}: {e}")

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), APIHandler) as httpd:
        print(f"API Server running at http://localhost:{PORT}")
        httpd.serve_forever()

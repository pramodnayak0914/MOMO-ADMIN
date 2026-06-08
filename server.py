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

def init_db():
    if not DATABASE_URL or not psycopg2:
        return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
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
        conn.commit()
        cur.close()
        conn.close()
        print("momo-admin: Database verified successfully.")
    except Exception as e:
        print(f"momo-admin: Database initialization error: {e}")

init_db()

class AdminAPIHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/admin/data':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                if data.get('passcode') != ADMIN_PASSCODE:
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
                
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    
                    cur.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 500")
                    transactions_raw = cur.fetchall()
                    for t in transactions_raw:
                        t['created_at'] = str(t['created_at'])
                        t['amount'] = float(t['amount'])
                        transactions.append(dict(t))
                        
                    cur.execute("SELECT * FROM purchases ORDER BY created_at DESC LIMIT 500")
                    purchases_raw = cur.fetchall()
                    for p in purchases_raw:
                        p['created_at'] = str(p['created_at'])
                        purchases.append(dict(p))
                        
                    try:
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
                        
                    current_assistant_name = ""
                    try:
                        cur.execute("SELECT value FROM app_config WHERE key = 'assistant_name'")
                        row = cur.fetchone()
                        if row:
                            current_assistant_name = row['value']
                    except Exception as e:
                        print(f"Error fetching config: {e}")
                        
                    cur.close()
                    conn.close()
                else:
                    transactions = [{"order_id": "TEST", "status": "SUCCESS", "amount": 0, "created_at": "N/A"}]
                    current_assistant_name = "Offline"
                
                self._send_json(200, {
                    "success": True,
                    "transactions": transactions,
                    "purchases": purchases,
                    "analytics": analytics_summary,
                    "assistant_name": current_assistant_name
                })
            except Exception as e:
                print(f"Error fetching admin data: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        elif self.path == '/api/admin/config':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "No payload"})
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                if data.get('passcode') != ADMIN_PASSCODE:
                    self._send_json(401, {"success": False, "error": "Unauthorized"})
                    return
                
                new_name = data.get('assistant_name')
                if not new_name:
                    self._send_json(400, {"success": False, "error": "Missing assistant_name"})
                    return
                
                if not DATABASE_URL:
                    self._send_json(500, {"success": False, "error": "Database URL is not configured on the server."})
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
                print(f"Error setting config: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/support/tickets':
            query_params = parse_qs(parsed_path.query)
            user_phone = query_params.get('user_phone', [None])[0]
            
            if not DATABASE_URL or not psycopg2:
                self._send_json(500, {"success": False, "error": "Database not configured"})
                return
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
            super().do_GET()

    def do_PUT(self):
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
                
                if not DATABASE_URL or not psycopg2:
                    self._send_json(500, {"success": False, "error": "Database not configured"})
                    return
                
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                
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

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), AdminAPIHandler) as httpd:
        print(f"Admin Server running at http://localhost:{PORT}")
        httpd.serve_forever()

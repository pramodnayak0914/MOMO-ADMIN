import http.server
import socketserver
import json
import urllib.parse
import os

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

PORT = int(os.environ.get('PORT', 8080))
DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_PASSCODE = os.environ.get('ADMIN_PASSCODE', 'admin123')

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
                    except Exception as e:
                        print(f"Error fetching analytics (table might not exist yet): {e}")
                        
                    cur.close()
                    conn.close()
                else:
                    transactions = [{"order_id": "TEST", "status": "SUCCESS", "amount": 0, "created_at": "N/A"}]
                
                self._send_json(200, {
                    "success": True,
                    "transactions": transactions,
                    "purchases": purchases,
                    "analytics": analytics_summary
                })
            except Exception as e:
                print(f"Error fetching admin data: {e}")
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

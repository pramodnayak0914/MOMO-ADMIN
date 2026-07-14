import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'r') as f:
    content = f.read()

# 1. Insert GET endpoints
get_api_code = """
        if parsed_path.path == '/api/admin/notifications':
            try:
                from db_adapter import sqlite3_proxy as sqlite3
                conn = sqlite3.connect('../MOMO-AI/local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                query_params = dict(urllib.parse.parse_qsl(parsed_path.query))
                limit = int(query_params.get('limit', 50))
                offset = int(query_params.get('offset', 0))
                category = query_params.get('category')
                status = query_params.get('status') # 'unread' or 'read'
                
                # We assume admin is logged in. In a real app we'd get their role/email from session.
                # For now, we fetch notifications for 'admin' role or globally broadcasted.
                
                sql = "SELECT * FROM notifications WHERE target_role = 'admin' OR target_role IS NULL"
                params = []
                
                if category:
                    sql += " AND category = ?"
                    params.append(category)
                if status:
                    sql += " AND read_status = ?"
                    params.append(status)
                    
                # Expiry check
                sql += " AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"
                    
                sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cur.execute(sql, tuple(params))
                rows = [dict(r) for r in cur.fetchall()]
                
                # Count total
                count_sql = "SELECT COUNT(*) as cnt FROM notifications WHERE target_role = 'admin' OR target_role IS NULL"
                cur.execute(count_sql)
                total = cur.fetchone()['cnt']
                
                return self._send_json(200, {"success": True, "data": rows, "total": total})
            except Exception as e:
                return self._send_json(500, {"success": False, "error": str(e)})

        if parsed_path.path == '/api/admin/notifications/unread-count':
            try:
                from db_adapter import sqlite3_proxy as sqlite3
                conn = sqlite3.connect('../MOMO-AI/local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                sql = "SELECT COUNT(*) as cnt FROM notifications WHERE (target_role = 'admin' OR target_role IS NULL) AND read_status = 'unread' AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"
                cur.execute(sql)
                count = cur.fetchone()['cnt']
                
                return self._send_json(200, {"success": True, "count": count})
            except Exception as e:
                return self._send_json(500, {"success": False, "error": str(e)})
"""

# Insert GET endpoints after a known GET endpoint, e.g. dashboard_stats
if "/api/admin/notifications" not in content:
    content = content.replace("if parsed_path.path == '/api/admin/support/dashboard_stats':", get_api_code + "\n        if parsed_path.path == '/api/admin/support/dashboard_stats':")

# 2. Insert PATCH endpoints
patch_api_code = """
        if self.path.startswith('/api/admin/notifications/') and self.path.endswith('/read'):
            notif_id = self.path.split('/')[-2]
            try:
                from db_adapter import sqlite3_proxy as sqlite3
                conn = sqlite3.connect('../MOMO-AI/local_database.db', check_same_thread=False)
                cur = conn.cursor()
                cur.execute("UPDATE notifications SET read_status = 'read' WHERE id = ?", (notif_id,))
                conn.commit()
                return self._send_json(200, {"success": True})
            except Exception as e:
                return self._send_json(500, {"success": False, "error": str(e)})
                
        if self.path == '/api/admin/notifications/read-all':
            try:
                from db_adapter import sqlite3_proxy as sqlite3
                conn = sqlite3.connect('../MOMO-AI/local_database.db', check_same_thread=False)
                cur = conn.cursor()
                cur.execute("UPDATE notifications SET read_status = 'read' WHERE (target_role = 'admin' OR target_role IS NULL) AND read_status = 'unread'")
                conn.commit()
                return self._send_json(200, {"success": True})
            except Exception as e:
                return self._send_json(500, {"success": False, "error": str(e)})
"""

if "/api/admin/notifications/read-all" not in content:
    content = content.replace("def do_PATCH(self):", "def do_PATCH(self):\n" + patch_api_code)

# 3. Insert DELETE endpoint
delete_api_code = """
        if self.path.startswith('/api/admin/notifications/'):
            notif_id = self.path.split('/')[-1]
            try:
                from db_adapter import sqlite3_proxy as sqlite3
                conn = sqlite3.connect('../MOMO-AI/local_database.db', check_same_thread=False)
                cur = conn.cursor()
                cur.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
                conn.commit()
                return self._send_json(200, {"success": True})
            except Exception as e:
                return self._send_json(500, {"success": False, "error": str(e)})
"""

if "/api/admin/notifications/" not in content and "def do_DELETE" in content:
    content = content.replace("def do_DELETE(self):", "def do_DELETE(self):\n" + delete_api_code)
elif "def do_DELETE" not in content:
    # We must add do_DELETE entirely
    new_do_delete = f"""
    def do_DELETE(self):
        if not self.authenticate(): return
{delete_api_code}
        self._send_json(404, {{"success": False, "error": "Not found"}})
"""
    content = content.replace("def do_PATCH(self):", new_do_delete + "\n    def do_PATCH(self):")

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'w') as f:
    f.write(content)

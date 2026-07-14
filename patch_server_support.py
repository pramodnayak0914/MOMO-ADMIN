import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'r') as f:
    content = f.read()

# We'll replace the entire /api/support/tickets handler
new_handler = """        if parsed_path.path == '/api/support/tickets' or parsed_path.path == '/api/admin/support/tickets':
            query_params = parse_qs(parsed_path.query)
            user_phone = query_params.get('user_phone', [None])[0]
            ticket_id = query_params.get('ticket_id', [None])[0]
            mobile = query_params.get('mobile', [None])[0]
            service = query_params.get('service', [None])[0]
            operator = query_params.get('operator', [None])[0]
            status = query_params.get('status', [None])[0]
            priority = query_params.get('priority', [None])[0]
            ticket_type = query_params.get('ticket_type', [None])[0]
            assigned_agent = query_params.get('assigned_agent', [None])[0]
            refund_status = query_params.get('refund_status', [None])[0]
            date_range = query_params.get('date_range', [None])[0]
            
            page = int(query_params.get('page', [1])[0])
            limit = int(query_params.get('limit', [50])[0])
            offset = (page - 1) * limit
            
            import sqlite3
            try:
                conn = sqlite3.connect('/Users/pramod2.nayak/MOMO-AI/local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                query = "SELECT * FROM support_tickets WHERE 1=1"
                count_query = "SELECT COUNT(*) FROM support_tickets WHERE 1=1"
                params = []
                
                if user_phone:
                    query += " AND user_phone = ?"
                    count_query += " AND user_phone = ?"
                    params.append(user_phone)
                if ticket_id:
                    query += " AND ticket_id LIKE ?"
                    count_query += " AND ticket_id LIKE ?"
                    params.append(f"%{ticket_id}%")
                if mobile:
                    query += " AND user_phone LIKE ?"
                    count_query += " AND user_phone LIKE ?"
                    params.append(f"%{mobile}%")
                if status and status != 'All':
                    query += " AND status = ?"
                    count_query += " AND status = ?"
                    params.append(status)
                if priority and priority != 'All':
                    query += " AND priority = ?"
                    count_query += " AND priority = ?"
                    params.append(priority)
                if ticket_type and ticket_type != 'All':
                    query += " AND issue_type = ?"
                    count_query += " AND issue_type = ?"
                    params.append(ticket_type)
                if assigned_agent and assigned_agent != 'All':
                    query += " AND assigned_agent = ?"
                    count_query += " AND assigned_agent = ?"
                    params.append(assigned_agent)
                if date_range:
                    import datetime
                    today = datetime.datetime.now()
                    if date_range == 'today':
                        start_date = today.strftime('%Y-%m-%d 00:00:00')
                    elif date_range == 'week':
                        start_date = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
                    elif date_range == 'month':
                        start_date = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
                    else:
                        start_date = None
                        
                    if start_date:
                        query += " AND created_at >= ?"
                        count_query += " AND created_at >= ?"
                        params.append(start_date)

                # Execute count
                cur.execute(count_query, params)
                total_count = cur.fetchone()[0]
                
                # Execute data fetch
                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                cur.execute(query, params + [limit, offset])
                
                tickets = [dict(row) for row in cur.fetchall()]
                cur.close()
                conn.close()
                
                return self._send_json(200, {
                    "success": True, 
                    "tickets": tickets,
                    "pagination": {
                        "total": total_count,
                        "page": page,
                        "limit": limit,
                        "pages": (total_count + limit - 1) // limit
                    }
                })
            except Exception as e:
                print(f"Error fetching tickets from SQLite: {e}")
                return self._send_json(500, {"success": False, "error": str(e)})

        if parsed_path.path == '/api/admin/support/dashboard_stats':
            import sqlite3
            try:
                conn = sqlite3.connect('/Users/pramod2.nayak/MOMO-AI/local_database.db', check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                stats = {
                    "open": 0,
                    "critical": 0,
                    "pending_refunds": 0,
                    "resolved_today": 0,
                    "avg_resolution_time_hrs": 0,
                    "avg_first_response_time_hrs": 0,
                    "sla_breached": 0,
                    "ai_created": 0,
                    "manual_created": 0
                }
                
                cur.execute("SELECT status, priority, issue_type, ai_generated, created_at, resolved_at, sla_deadline FROM support_tickets")
                rows = cur.fetchall()
                
                import datetime
                now = datetime.datetime.now()
                today_str = now.strftime('%Y-%m-%d')
                
                resolution_times = []
                
                for row in rows:
                    st = row['status']
                    pr = row['priority']
                    it = row['issue_type']
                    ai = row['ai_generated']
                    ca = row['created_at']
                    ra = row['resolved_at']
                    sla = row['sla_deadline']
                    
                    if st in ['OPEN', 'IN_PROGRESS', 'Open', 'In Progress']:
                        stats['open'] += 1
                        if it == 'Refund':
                            stats['pending_refunds'] += 1
                    
                    if pr in ['High', 'Critical']:
                        stats['critical'] += 1
                        
                    if st in ['RESOLVED', 'CLOSED', 'Resolved', 'Closed']:
                        if ra and ra.startswith(today_str):
                            stats['resolved_today'] += 1
                            
                        if ra and ca:
                            try:
                                ca_dt = datetime.datetime.strptime(ca, '%Y-%m-%d %H:%M:%S')
                                ra_dt = datetime.datetime.strptime(ra, '%Y-%m-%d %H:%M:%S')
                                diff = (ra_dt - ca_dt).total_seconds() / 3600.0
                                resolution_times.append(diff)
                            except:
                                pass
                                
                    if ai == 1:
                        stats['ai_created'] += 1
                    else:
                        stats['manual_created'] += 1
                        
                    if sla:
                        try:
                            sla_dt = datetime.datetime.strptime(sla, '%Y-%m-%d %H:%M:%S')
                            if ra:
                                ra_dt = datetime.datetime.strptime(ra, '%Y-%m-%d %H:%M:%S')
                                if ra_dt > sla_dt:
                                    stats['sla_breached'] += 1
                            else:
                                if now > sla_dt:
                                    stats['sla_breached'] += 1
                        except:
                            pass
                            
                if resolution_times:
                    stats['avg_resolution_time_hrs'] = round(sum(resolution_times) / len(resolution_times), 2)
                    stats['avg_first_response_time_hrs'] = round(stats['avg_resolution_time_hrs'] / 3.0, 2) # Approximation for demo
                
                cur.close()
                conn.close()
                return self._send_json(200, {"success": True, "stats": stats})
            except Exception as e:
                print(f"Error fetching dashboard stats: {e}")
                return self._send_json(500, {"success": False, "error": str(e)})
"""

pattern = re.compile(r"        if parsed_path.path == '/api/support/tickets':.*?return self\._send_json\(500, \{\"success\": False, \"error\": str\(e\)\}\)", re.DOTALL)
if pattern.search(content):
    content = pattern.sub(new_handler, content)
    with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'w') as f:
        f.write(content)
    print("Successfully patched server.py")
else:
    print("Could not find the target block in server.py")

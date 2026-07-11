import urllib.parse
import json
import services_db

def handle_internal_get(handler, parsed_path):
    path = parsed_path.path
    
    if path == '/api/internal/services':
        if not check_auth(handler): return True
        try:
            query_params = urllib.parse.parse_qs(parsed_path.query)
            
            filters = {}
            if 'status' in query_params: filters['status'] = query_params['status'][0]
            if 'category' in query_params: filters['category'] = query_params['category'][0]
            if 'featured' in query_params: filters['featured'] = query_params['featured'][0]
            if 'show_homepage' in query_params: filters['show_homepage'] = query_params['show_homepage'][0]
            if 'coming_soon' in query_params: filters['coming_soon'] = query_params['coming_soon'][0]
            if 'is_archived' in query_params: filters['is_archived'] = query_params['is_archived'][0]
            
            page = int(query_params.get('page', ['1'])[0])
            limit = int(query_params.get('limit', ['50'])[0])
            offset = (page - 1) * limit
            
            services = services_db.fetch_services(filters=filters, limit=limit, offset=offset)
            handler._send_json(200, {"success": True, "services": services})
        except Exception as e:
            handler._send_json(500, {"success": False, "error": str(e)})
        return True
        
    if path == '/api/internal/service-health':
        if not check_auth(handler): return True
        try:
            health = services_db.get_service_health_stats()
            handler._send_json(200, {"success": True, "health": health})
        except Exception as e:
            handler._send_json(500, {"success": False, "error": str(e)})
        return True

    if path.startswith('/api/internal/service-workspace/'):
        if not check_auth(handler): return True
        service_id = path.split('/')[-1]
        try:
            workspace = services_db.fetch_service_workspace(service_id)
            if workspace:
                handler._send_json(200, {"success": True, "workspace": workspace})
            else:
                handler._send_json(404, {"success": False, "error": "Service not found"})
        except Exception as e:
            handler._send_json(500, {"success": False, "error": str(e)})
        return True

    return False

def handle_internal_put(handler, parsed_path, data):
    path = parsed_path.path
    
    if path.startswith('/api/internal/service/'):
        payload = check_auth(handler)
        if not payload: return True
        
        service_id = path.split('/')[-1]
        try:
            updated_by = payload.get('email', 'system')
            
            success = services_db.update_service_presentation(service_id, data, updated_by)
            if success:
                handler._send_json(200, {"success": True, "message": "Service updated successfully"})
            else:
                handler._send_json(404, {"success": False, "error": "Service not found or no changes provided"})
        except Exception as e:
            handler._send_json(500, {"success": False, "error": str(e)})
        return True
        
    if path.startswith('/api/internal/operator/'):
        payload = check_auth(handler)
        if not payload: return True
        
        operator_id = path.split('/')[-1]
        try:
            updated_by = payload.get('email', 'system')
            success = services_db.update_operator_presentation(operator_id, data, updated_by)
            if success:
                handler._send_json(200, {"success": True, "message": "Operator updated successfully"})
            else:
                handler._send_json(404, {"success": False, "error": "Operator not found or no changes provided"})
        except Exception as e:
            handler._send_json(500, {"success": False, "error": str(e)})
        return True
        
    return False

def handle_internal_post(handler, parsed_path, data):
    path = parsed_path.path
    if path == '/api/internal/service-sync':
        if not check_auth(handler): return True
        try:
            import service_sync_engine
            provider = data.get('provider')
            if provider == 'kwik':
                result = service_sync_engine.sync_kwik_services()
                handler._send_json(200, {"success": True, "result": result})
            else:
                handler._send_json(400, {"success": False, "error": "Unknown sync provider"})
        except Exception as e:
            handler._send_json(500, {"success": False, "error": str(e)})
        return True
    
    return False

def check_auth(handler):
    # Try to verify via header (standard Bearer token parsing)
    auth_header = handler.headers.get('Authorization')
    token = None
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        
    # In MOMO-ADMIN, tokens are SHA256 hashes of passwords.
    # To properly authenticate, we query the DB to get the admin's email and role.
    if token:
        import psycopg2
        import os
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if DATABASE_URL and psycopg2:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("SELECT email, role FROM admins WHERE password_hash = %s AND status = 'ACTIVE'", (token,))
                row = cur.fetchone()
                cur.close()
                conn.close()
                if row:
                    return {"email": row[0], "role": row[1]}
            except Exception as e:
                print(f"Auth verification error: {e}")
                pass
                
    # Fallback to Admin passcode if no DB or token matches
    import server
    if token == server.ADMIN_PASSCODE:
        return {"email": "superadmin@momo.com", "role": "superadmin"}
        
    handler._send_json(401, {"success": False, "error": "Unauthorized"})
    return None

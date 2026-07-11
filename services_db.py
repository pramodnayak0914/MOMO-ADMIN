import os
import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url or not psycopg2:
        return None
    return psycopg2.connect(db_url)

def init_schema():
    conn = get_db_connection()
    if not conn:
        print("Warning: DATABASE_URL not set or psycopg2 missing. Skipping services schema init.")
        return
        
    try:
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_providers (
                id VARCHAR(50) PRIMARY KEY,
                display_name VARCHAR(100) NOT NULL,
                priority INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                configuration JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service_master (
                id VARCHAR(50) PRIMARY KEY,
                internal_service_code VARCHAR(50) UNIQUE NOT NULL,
                slug VARCHAR(100) UNIQUE NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                description TEXT,
                icon_name VARCHAR(50),
                display_order INTEGER DEFAULT 0,
                category VARCHAR(50),
                status INTEGER DEFAULT 1,
                is_archived INTEGER DEFAULT 0,
                show_homepage INTEGER DEFAULT 0,
                featured INTEGER DEFAULT 0,
                coming_soon INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR(100)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operator_master (
                id VARCHAR(50) PRIMARY KEY,
                service_id VARCHAR(50) REFERENCES service_master(id),
                internal_operator_code VARCHAR(50) UNIQUE NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                status INTEGER DEFAULT 1,
                logo_url VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operator_provider_map (
                id SERIAL PRIMARY KEY,
                operator_id VARCHAR(50) REFERENCES operator_master(id),
                provider_id VARCHAR(50) REFERENCES api_providers(id),
                provider_operator_code VARCHAR(100) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                priority INTEGER DEFAULT 0,
                routing_rules JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(operator_id, provider_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_logs (
                id SERIAL PRIMARY KEY,
                provider_id VARCHAR(50) REFERENCES api_providers(id),
                sync_type VARCHAR(50) NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                status VARCHAR(20),
                total_services INTEGER DEFAULT 0,
                total_operators INTEGER DEFAULT 0,
                message TEXT,
                created_by VARCHAR(100)
            )
        ''')
        
        cursor.execute('''
            ALTER TABLE operator_master ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 0;
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_service_slug ON service_master(slug)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_operator_service_id ON operator_master(service_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_operator_prov_map_code ON operator_provider_map(provider_operator_code)')
        
    finally:
        conn.close()

def fetch_services(filters=None, limit=None, offset=None, sort_by="display_order ASC, display_name ASC"):
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT * FROM service_master WHERE 1=1"
        params = []
        
        if filters:
            if 'status' in filters and filters['status'] != '':
                query += " AND status = %s"
                params.append(int(filters['status']))
            if 'category' in filters and filters['category']:
                query += " AND category = %s"
                params.append(filters['category'])
            if 'featured' in filters:
                query += " AND featured = %s"
                params.append(int(filters['featured']))
            if 'show_homepage' in filters:
                query += " AND show_homepage = %s"
                params.append(int(filters['show_homepage']))
            if 'coming_soon' in filters:
                query += " AND coming_soon = %s"
                params.append(int(filters['coming_soon']))
            if 'is_archived' in filters:
                query += " AND is_archived = %s"
                params.append(int(filters['is_archived']))
            else:
                query += " AND is_archived = 0"
        else:
            query += " AND is_archived = 0"
            
        if sort_by:
            # ensure sort_by is safe from sql injection, or restrict it
            query += f" ORDER BY {sort_by}"
            
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
            if offset is not None:
                query += " OFFSET %s"
                params.append(offset)
                
        cursor.execute(query, tuple(params))
        res = cursor.fetchall()
        
        # Convert datetime objects to string for JSON serialization
        for r in res:
            for k, v in r.items():
                if isinstance(v, datetime.datetime):
                    r[k] = v.isoformat()
                    
        return res
    finally:
        conn.close()

def fetch_service_by_id_or_slug(identifier):
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM service_master WHERE (id = %s OR slug = %s) AND is_archived = 0", (identifier, identifier))
        res = cursor.fetchone()
        if res:
            for k, v in res.items():
                if isinstance(v, datetime.datetime):
                    res[k] = v.isoformat()
        return res
    finally:
        conn.close()

def update_service_presentation(service_id, data, updated_by):
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        
        allowed_fields = [
            'display_name', 'description', 'icon_name', 
            'show_homepage', 'featured', 'coming_soon', 
            'display_order', 'category', 'status'
        ]
        
        updates = []
        params = []
        
        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])
                
        if not updates:
            return False
            
        updates.append("updated_at = CURRENT_TIMESTAMP")
        updates.append("updated_by = %s")
        params.append(updated_by)
        
        query = f"UPDATE service_master SET {', '.join(updates)} WHERE id = %s"
        params.append(service_id)
        
        cursor.execute(query, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_service_health_stats():
    conn = get_db_connection()
    if not conn: return {}
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        stats = {}
        
        cursor.execute("SELECT COUNT(*) as count FROM service_master WHERE is_archived = 0")
        stats['total_services'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM service_master WHERE status = 1 AND is_archived = 0")
        stats['enabled_services'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM operator_master")
        stats['total_operators'] = cursor.fetchone()['count']
        
        return stats
    finally:
        conn.close()

def fetch_service_workspace(service_id):
    """
    Fetches the service summary and its associated operators in one go.
    """
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Fetch Service Details
        cursor.execute("SELECT * FROM service_master WHERE id = %s OR slug = %s", (service_id, service_id))
        service = cursor.fetchone()
        
        if not service:
            return None
            
        real_service_id = service['id']
        
        # 2. Fetch Operators with Provider stats
        cursor.execute('''
            SELECT 
                o.id,
                o.internal_operator_code,
                o.display_name,
                o.status,
                o.logo_url,
                o.priority,
                o.updated_at,
                COUNT(opm.provider_id) as provider_count,
                string_agg(p.display_name, ', ') as linked_providers
            FROM operator_master o
            LEFT JOIN operator_provider_map opm ON o.id = opm.operator_id
            LEFT JOIN api_providers p ON opm.provider_id = p.id
            WHERE o.service_id = %s
            GROUP BY o.id
            ORDER BY o.priority DESC, o.display_name ASC
        ''', (real_service_id,))
        operators = cursor.fetchall()
        
        # Formatting dates for JSON serialization
        if 'created_at' in service and service['created_at']:
            service['created_at'] = service['created_at'].isoformat()
        if 'updated_at' in service and service['updated_at']:
            service['updated_at'] = service['updated_at'].isoformat()
            
        for op in operators:
            if 'updated_at' in op and op['updated_at']:
                op['updated_at'] = op['updated_at'].isoformat()
                
        return {
            "service": service,
            "operators": operators
        }
    finally:
        conn.close()

def update_operator_presentation(operator_id, data, updated_by):
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if 'display_name' in data:
            updates.append("display_name = %s")
            params.append(data['display_name'])
        if 'logo_url' in data:
            updates.append("logo_url = %s")
            params.append(data['logo_url'])
        if 'status' in data:
            updates.append("status = %s")
            params.append(int(data['status']))
        if 'priority' in data:
            updates.append("priority = %s")
            params.append(int(data['priority']))
                
        if not updates:
            return False
            
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"UPDATE operator_master SET {', '.join(updates)} WHERE id = %s"
        params.append(operator_id)
        
        cursor.execute(query, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


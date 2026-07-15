import os
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None
import sqlite3 as real_sqlite3

DATABASE_URL = os.environ.get('DATABASE_URL')

def adapt_query(query):
    parts = query.split("'")
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace('?', '%s')
    query = "'".join(parts)
    query = query.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
    query = query.replace('PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
    query = query.replace('AUTOINCREMENT', 'SERIAL')
    return query

class PgCursor:
    def __init__(self, cursor):
        self._cursor = cursor
    
    def execute(self, query, params=None):
        query = adapt_query(query)
        if params:
            self._cursor.execute(query, params)
        else:
            self._cursor.execute(query)
            
    def _convert_dates(self, row):
        if not row: return row
        import datetime
        for k, v in row.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                row[k] = v.isoformat()
        return row

    def fetchone(self):
        res = self._cursor.fetchone()
        return self._convert_dates(dict(res)) if res else None
        
    def fetchall(self):
        res = self._cursor.fetchall()
        return [self._convert_dates(dict(r)) for r in res] if res else []
        
    def close(self):
        self._cursor.close()
        
class PgConnection:
    def __init__(self, conn):
        self._conn = conn
        self.row_factory = None
        
    def cursor(self):
        return PgCursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))
        
    def commit(self):
        self._conn.commit()
        
    def rollback(self):
        self._conn.rollback()
        
    def close(self):
        self._conn.close()

class FakeSqlite:
    Error = Exception
    OperationalError = Exception
    Row = real_sqlite3.Row
    
    def connect(self, db, check_same_thread=False):
        if not DATABASE_URL or not psycopg2:
            return real_sqlite3.connect(db, check_same_thread=check_same_thread)
        conn = psycopg2.connect(DATABASE_URL)
        return PgConnection(conn)

sqlite3_proxy = FakeSqlite()

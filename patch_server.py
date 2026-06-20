import re
with open('server.py', 'r') as f:
    content = f.read()

# Replace import sqlite3
content = content.replace('import sqlite3\n', '''sqlite3_import_error = None
try:
    from db_adapter import sqlite3_proxy as sqlite3
    RealDictCursor = None
except ImportError as e:
    sqlite3 = None
    sqlite3_import_error = str(e)
''')

# Add dotenv to requirements.txt if not exists
with open('requirements.txt', 'a') as f:
    f.write('\npsycopg2-binary==2.9.9\npython-dotenv==1.0.0\n')

# Also fix the init_db duplicate column bug in server.py
content = content.replace('''        except sqlite3.OperationalError:
            pass
        except sqlite3.Error:
            conn.rollback()''', '''        except Exception:
            conn.rollback()''')

with open('server.py', 'w') as f:
    f.write(content)

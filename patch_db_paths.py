import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'r') as f:
    content = f.read()

# Replace hardcoded sqlite imports and paths
new_db_import = """
            from db_adapter import sqlite3_proxy as sqlite3
            try:
                conn = sqlite3.connect('../MOMO-AI/local_database.db', check_same_thread=False)
"""
content = re.sub(
    r"import sqlite3\n\s*try:\n\s*conn = sqlite3\.connect\('/Users/pramod2\.nayak/MOMO-AI/local_database\.db', check_same_thread=False\)",
    new_db_import.strip(),
    content
)

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'w') as f:
    f.write(content)
print("Replaced DB paths in server.py")

import re

with open('server.py', 'r') as f:
    content = f.read()

data_orig = """            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)"""
data_new = """            try:
                if not DATABASE_URL or not psycopg2:
                    return self._send_json(200, {"success": True, "total_profit": 0, "audit_logs": [], "promo_codes": [], "api_provider": {"provider": "Local", "commission_margin": 0}})
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor(cursor_factory=RealDictCursor)"""

if data_orig in content:
    content = content.replace(data_orig, data_new)

action_orig = """            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()"""
action_new = """            try:
                if not DATABASE_URL or not psycopg2:
                    return self._send_json(200, {"success": True})
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()"""

if action_orig in content:
    content = content.replace(action_orig, action_new)

with open('server.py', 'w') as f:
    f.write(content)

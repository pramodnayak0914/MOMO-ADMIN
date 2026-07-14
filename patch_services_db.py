import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/services_db.py', 'r') as f:
    content = f.read()

migration_code = """
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute("SELECT migration_name FROM schema_migrations")
        applied_migrations = {row['migration_name'] for row in cursor.fetchall()}

        migrations = [
            {
                "name": "001_support_dashboard_indexes",
                "up": '''
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_user_phone ON support_tickets(user_phone);
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_priority ON support_tickets(priority);
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_issue_type ON support_tickets(issue_type);
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_assigned_agent ON support_tickets(assigned_agent);
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_ai_generated ON support_tickets(ai_generated);
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON support_tickets(created_at);
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_sla_deadline ON support_tickets(sla_deadline);
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_resolved_at ON support_tickets(resolved_at);
                '''
            },
            {
                "name": "002_support_ticket_notes",
                "up": '''
                    CREATE TABLE IF NOT EXISTS support_ticket_notes (
                        id SERIAL PRIMARY KEY,
                        ticket_id VARCHAR(50) NOT NULL,
                        note TEXT NOT NULL,
                        created_by VARCHAR(100) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_support_ticket_notes_ticket_id ON support_ticket_notes(ticket_id);
                '''
            }
        ]

        for migration in migrations:
            if migration["name"] not in applied_migrations:
                try:
                    cursor.execute(migration["up"])
                    cursor.execute("INSERT INTO schema_migrations (migration_name) VALUES (%s)", (migration["name"],))
                    print(f"Applied migration: {migration['name']}")
                except Exception as ex:
                    print(f"Error applying migration {migration['name']}: {ex}")
                    # Continue with other migrations or fail? 
                    # We will continue.
"""

# Insert this before conn.close() or at the end of the try block in init_schema
pattern = re.compile(r"(        print\(\"services schema initialized successfully\"\))")
if pattern.search(content):
    content = pattern.sub(migration_code + r"\n\1", content)
else:
    # try looking for conn.close()
    pattern = re.compile(r"(        if conn:\n            conn\.close\(\))")
    if pattern.search(content):
        content = pattern.sub(migration_code + r"\n\1", content)

with open('/Users/pramod2.nayak/MOMO-ADMIN/services_db.py', 'w') as f:
    f.write(content)
print("services_db.py patched.")

import os
import sqlite3

def run_migration():
    db_path = '/Users/pramod2.nayak/MOMO-AI/local_database.db'
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    
    # Create schema_migrations table if not exists (just to track our manual migrations going forward)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name VARCHAR(255) UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 001_support_dashboard_indexes
    cursor.execute("SELECT 1 FROM schema_migrations WHERE migration_name = '001_support_dashboard_indexes'")
    if not cursor.fetchone():
        print("Applying 001_support_dashboard_indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user_phone ON support_tickets(user_phone)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_priority ON support_tickets(priority)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_issue_type ON support_tickets(issue_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_assigned_agent ON support_tickets(assigned_agent)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_ai_generated ON support_tickets(ai_generated)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON support_tickets(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_sla_deadline ON support_tickets(sla_deadline)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_resolved_at ON support_tickets(resolved_at)")
        cursor.execute("INSERT INTO schema_migrations (migration_name) VALUES ('001_support_dashboard_indexes')")
        conn.commit()

    # 002_support_ticket_notes
    cursor.execute("SELECT 1 FROM schema_migrations WHERE migration_name = '002_support_ticket_notes'")
    if not cursor.fetchone():
        print("Applying 002_support_ticket_notes...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_ticket_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id VARCHAR(50) NOT NULL,
                note_text TEXT NOT NULL,
                added_by VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_ticket_notes_ticket_id ON support_ticket_notes(ticket_id)")
        cursor.execute("INSERT INTO schema_migrations (migration_name) VALUES ('002_support_ticket_notes')")
        conn.commit()
        
    # 003_notifications
    cursor.execute("SELECT 1 FROM schema_migrations WHERE migration_name = '003_notifications'")
    if not cursor.fetchone():
        print("Applying 003_notifications...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                category VARCHAR(100) NOT NULL,
                priority VARCHAR(50) DEFAULT 'medium',
                read_status VARCHAR(50) DEFAULT 'unread',
                action_url TEXT,
                deduplication_hash VARCHAR(255),
                expires_at TIMESTAMP,
                target_role VARCHAR(100),
                target_admin_email VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Indexes for querying by recipient/role and read status
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_read_status ON notifications(read_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_target_role ON notifications(target_role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_target_admin_email ON notifications(target_admin_email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_deduplication_hash ON notifications(deduplication_hash)")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_email VARCHAR(100) UNIQUE NOT NULL,
                email_enabled BOOLEAN DEFAULT 1,
                whatsapp_enabled BOOLEAN DEFAULT 1,
                in_app_enabled BOOLEAN DEFAULT 1,
                bill_reminder_enabled BOOLEAN DEFAULT 1,
                recharge_reminder_enabled BOOLEAN DEFAULT 1,
                support_updates_enabled BOOLEAN DEFAULT 1,
                refund_updates_enabled BOOLEAN DEFAULT 1,
                security_alerts_enabled BOOLEAN DEFAULT 1,
                retention_days INTEGER DEFAULT 30,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute("INSERT INTO schema_migrations (migration_name) VALUES ('003_notifications')")
        conn.commit()

    conn.close()
    print("Migrations complete.")

if __name__ == '__main__':
    run_migration()

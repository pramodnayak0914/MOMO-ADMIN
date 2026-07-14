import sys
import os

# Add parent directory to path so we can import db_adapter
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db_adapter import sqlite3_proxy as sqlite3

DATABASE_URL = os.environ.get('DATABASE_URL', '')
SQLITE_DB_PATH = '../MOMO-AI/local_database.db'

def get_db():
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    if hasattr(sqlite3, 'Row'):
        conn.row_factory = sqlite3.Row
    return conn

def get_ticket_details(ticket_id):
    conn = get_db()
    cur = conn.cursor()
    
    # 1. Fetch Ticket
    cur.execute("SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
    ticket_row = cur.fetchone()
    if not ticket_row:
        return None
        
    ticket = dict(ticket_row)
    
    # 2. Fetch Timeline (Events)
    cur.execute("SELECT * FROM support_ticket_events WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,))
    timeline = [dict(r) for r in cur.fetchall()]
    
    # 3. Fetch Conversation
    cur.execute("SELECT * FROM support_ticket_messages WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,))
    conversation = [dict(r) for r in cur.fetchall()]
    
    # 4. Fetch Notes
    try:
        cur.execute("SELECT * FROM support_ticket_notes WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,))
        notes = [dict(r) for r in cur.fetchall()]
    except:
        notes = [] # In case migration hasn't run yet
        
    # 5. Fetch Refund Status (if applicable)
    refund_status = None
    if ticket.get('order_id'):
        cur.execute("SELECT status, requested_at, processed_at, refund_reference FROM refund_requests WHERE order_id = ?", (ticket['order_id'],))
        ref_row = cur.fetchone()
        if ref_row:
            refund_status = dict(ref_row)
            
    # 6. Fetch Notification History
    cur.execute("SELECT * FROM notifications WHERE user_phone = ? AND related_entity_id = ? ORDER BY created_at DESC", (ticket.get('user_phone'), ticket_id))
    notifications = [dict(r) for r in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return {
        "ticket": ticket,
        "timeline": timeline,
        "conversation": conversation,
        "notes": notes,
        "refund_status": refund_status,
        "notifications": notifications
    }

def add_ticket_note(ticket_id, note_text, admin_email):
    conn = get_db()
    cur = conn.cursor()
    
    # Insert Note
    cur.execute(
        "INSERT INTO support_ticket_notes (ticket_id, note, created_by) VALUES (?, ?, ?)",
        (ticket_id, note_text, admin_email)
    )
    
    # Insert Timeline Event
    cur.execute(
        "INSERT INTO support_ticket_events (ticket_id, event_type, description, actor) VALUES (?, ?, ?, ?)",
        (ticket_id, 'NOTE_ADDED', f"Internal note added: {note_text[:50]}...", admin_email)
    )
    
    conn.commit()
    cur.close()
    conn.close()
    return True

def update_ticket_status(ticket_id, new_status, admin_email):
    conn = get_db()
    cur = conn.cursor()
    
    import datetime
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    update_q = "UPDATE support_tickets SET status = ?"
    params = [new_status]
    
    if new_status in ['RESOLVED', 'CLOSED', 'REFUNDED']:
        update_q += ", resolved_at = ?"
        params.append(now)
        
    update_q += " WHERE ticket_id = ?"
    params.append(ticket_id)
    
    cur.execute(update_q, params)
    
    # Insert Timeline Event
    cur.execute(
        "INSERT INTO support_ticket_events (ticket_id, event_type, description, actor) VALUES (?, ?, ?, ?)",
        (ticket_id, 'STATUS_CHANGE', f"Status updated to {new_status}", admin_email)
    )
    
    conn.commit()
    cur.close()
    conn.close()
    return True

def assign_ticket(ticket_id, agent_email, admin_email):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("UPDATE support_tickets SET assigned_agent = ? WHERE ticket_id = ?", (agent_email, ticket_id))
    
    cur.execute(
        "INSERT INTO support_ticket_events (ticket_id, event_type, description, actor) VALUES (?, ?, ?, ?)",
        (ticket_id, 'AGENT_ASSIGNED', f"Assigned to {agent_email}", admin_email)
    )
    
    conn.commit()
    cur.close()
    conn.close()
    return True

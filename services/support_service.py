import os
import sqlite3
import datetime
import uuid
import json

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

from .event_bus import event_bus

DATABASE_URL = os.environ.get('DATABASE_URL', '')
SQLITE_DB = '/Users/pramod2.nayak/MOMO-AI/local_database.db'

class SupportService:
    def __init__(self):
        pass

    def _execute_write(self, query, params):
        if DATABASE_URL and psycopg2:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                pg_query = query.replace('?', '%s')
                cur.execute(pg_query, params)
                conn.commit()
                row_id = cur.fetchone()[0] if 'RETURNING id' in pg_query else None
                cur.close()
                conn.close()
                return True, row_id
            except Exception as e:
                print(f"[SupportService] Postgres Write Error: {e}")
                return False, str(e)
        else:
            try:
                conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)
                cur = conn.cursor()
                # Remove 'RETURNING id' for sqlite compat if used standardly
                clean_query = query.replace('RETURNING id', '')
                cur.execute(clean_query, params)
                conn.commit()
                row_id = cur.lastrowid
                cur.close()
                conn.close()
                return True, row_id
            except Exception as e:
                print(f"[SupportService] SQLite Write Error: {e}")
                return False, str(e)

    def generate_ticket_id(self, issue_type=None, service_name=None, description=None):
        from .ticket_constants import get_ticket_type, get_service_code
        ticket_type = get_ticket_type(issue_type)
        service_code = get_service_code(service_name, issue_type, description)
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        # Atomic sequence generation
        if DATABASE_URL and psycopg2:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO ticket_sequence (date, ticket_type, service_code, last_sequence) "
                    "VALUES (%s, %s, %s, 1) "
                    "ON CONFLICT (date, ticket_type, service_code) "
                    "DO UPDATE SET last_sequence = ticket_sequence.last_sequence + 1 "
                    "RETURNING last_sequence",
                    (date_str, ticket_type, service_code)
                )
                seq = cur.fetchone()[0]
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"Error generating sequence in Postgres: {e}")
                seq = str(uuid.uuid4().int)[:6]
        else:
            try:
                conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)
                cur = conn.cursor()
                cur.execute("BEGIN IMMEDIATE")
                cur.execute(
                    "SELECT last_sequence FROM ticket_sequence WHERE date = ? AND ticket_type = ? AND service_code = ?",
                    (date_str, ticket_type, service_code)
                )
                row = cur.fetchone()
                if row:
                    seq = row[0] + 1
                    cur.execute(
                        "UPDATE ticket_sequence SET last_sequence = ? WHERE date = ? AND ticket_type = ? AND service_code = ?",
                        (seq, date_str, ticket_type, service_code)
                    )
                else:
                    seq = 1
                    cur.execute(
                        "INSERT INTO ticket_sequence (date, ticket_type, service_code, last_sequence) VALUES (?, ?, ?, ?)",
                        (date_str, ticket_type, service_code, seq)
                    )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"Error generating sequence in SQLite: {e}")
                seq = str(uuid.uuid4().int)[:6]

        return f"{ticket_type}-{service_code}-{date_str}-{str(seq).zfill(6)}"

    def create_ticket(self, user_phone, issue_type, target_number=None, description="", 
                      order_id=None, ai_generated=False, ai_category=None, confidence=None, ai_summary=None, service_name=None):
        
        ticket_id = self.generate_ticket_id(issue_type=issue_type, service_name=service_name, description=description)
        
        query = """
            INSERT INTO support_tickets (
                ticket_id, user_phone, issue_type, target_number, description, status, order_id,
                ai_generated, ai_category, confidence, ai_summary, priority, sla_deadline
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        priority = "High" if issue_type in ["Recharge Failed", "Refund", "Money Debited"] else "Medium"
        
        # Calculate SLA deadline
        sla_hours = 2 if priority == "High" else (24 if priority == "Medium" else 48)
        sla_deadline = (datetime.datetime.now() + datetime.timedelta(hours=sla_hours)).strftime("%Y-%m-%d %H:%M:%S")
        
        params = (
            ticket_id, user_phone, issue_type, target_number, description, 'OPEN', order_id,
            bool(ai_generated), ai_category, confidence, ai_summary, priority, sla_deadline
        )
        
        success, _ = self._execute_write(query, params)
        if success:
            # Add timeline event
            self.log_event(ticket_id, "TICKET_CREATED", "", "OPEN", "System")
            
            # Publish event
            ticket_data = {
                "ticket_id": ticket_id,
                "user_phone": user_phone,
                "issue_type": issue_type,
                "status": "OPEN",
                "priority": priority
            }
            event_bus.publish("support.ticket.created", ticket_data)
            return {"success": True, "ticket_id": ticket_id}
        
        return {"success": False, "error": "Database error"}

    def log_event(self, ticket_id, event_type, old_value, new_value, performed_by):
        query = """
            INSERT INTO support_ticket_events (ticket_id, event_type, old_value, new_value, performed_by)
            VALUES (?, ?, ?, ?, ?)
        """
        self._execute_write(query, (ticket_id, event_type, old_value, new_value, performed_by))
        
    def add_message(self, ticket_id, sender, message):
        query = """
            INSERT INTO support_ticket_messages (ticket_id, sender, message)
            VALUES (?, ?, ?)
        """
        self._execute_write(query, (ticket_id, sender, message))

    def update_status(self, ticket_id, new_status, performed_by="Admin", user_phone=None):
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if new_status in ["CLOSED", "RESOLVED"]:
            query = "UPDATE support_tickets SET status = ?, resolved_at = ? WHERE ticket_id = ?"
            params = (new_status, now_str, ticket_id)
        else:
            query = "UPDATE support_tickets SET status = ? WHERE ticket_id = ?"
            params = (new_status, ticket_id)
            
        success, _ = self._execute_write(query, params)
        if success:
            self.log_event(ticket_id, "STATUS_UPDATED", "", new_status, performed_by)
            event_bus.publish("support.ticket.updated", {
                "ticket_id": ticket_id,
                "new_status": new_status,
                "user_phone": user_phone
            })
            return True
        return False

    def assign_ticket(self, ticket_id, agent_name, performed_by="Admin"):
        query = "UPDATE support_tickets SET assigned_agent = ? WHERE ticket_id = ?"
        success, _ = self._execute_write(query, (agent_name, ticket_id))
        if success:
            self.log_event(ticket_id, "TICKET_ASSIGNED", "", agent_name, performed_by)
            return True
        return False
        
    def add_internal_note(self, ticket_id, note_text, added_by="Admin"):
        query = "INSERT INTO support_ticket_notes (ticket_id, note_text, added_by) VALUES (?, ?, ?)"
        success, _ = self._execute_write(query, (ticket_id, note_text, added_by))
        if success:
            self.log_event(ticket_id, "INTERNAL_NOTE_ADDED", "", "Note Added", added_by)
            return True
        return False

support_service = SupportService()

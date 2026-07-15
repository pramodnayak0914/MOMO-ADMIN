import threading
import sqlite3
import os
try:
    import psycopg2
except ImportError:
    psycopg2 = None

from .notification_providers import EmailProvider, WhatsAppProvider

DATABASE_URL = os.environ.get('DATABASE_URL', '')
SQLITE_DB = 'local_database.db'

class NotificationService:
    def __init__(self):
        self.email_provider = EmailProvider()
        self.whatsapp_provider = WhatsAppProvider()
        
    def _execute_db(self, query, params):
        """Helper to run a DB query against Postgres (if available) or SQLite."""
        if DATABASE_URL and psycopg2:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                # Replace SQLite '?' with Postgres '%s'
                pg_query = query.replace('?', '%s')
                cur.execute(pg_query, params)
                conn.commit()
                cur.close()
                conn.close()
                return True
            except Exception as e:
                print(f"[NotificationService] DB Error: {e}")
                return False
        else:
            try:
                conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)
                cur = conn.cursor()
                cur.execute(query, params)
                conn.commit()
                cur.close()
                conn.close()
                return True
            except Exception as e:
                print(f"[NotificationService] SQLite Error: {e}")
                return False

    def _log_history(self, ticket_id, channel, provider, recipient, status, error=""):
        query = """
            INSERT INTO notification_history (ticket_id, channel, provider, recipient, status, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self._execute_db(query, (ticket_id, channel, provider, recipient, status, error))

    def _send_async(self, notification_task):
        """Runs the notification task in a background thread."""
        thread = threading.Thread(target=notification_task)
        thread.daemon = True
        thread.start()

    def send_ticket_created_notification(self, ticket_data):
        """Dispatches notifications when a ticket is created."""
        def task():
            ticket_id = ticket_data.get('ticket_id', 'Unknown')
            user_phone = ticket_data.get('user_phone', '')
            issue_type = ticket_data.get('issue_type', '')
            
            # 1. Notify Support Team via Email
            support_email = "customersupport@onlinerecharge-ai.com"
            subject = f"New Support Ticket Created: {ticket_id}"
            body = f"<h2>New Ticket: {ticket_id}</h2><p><strong>Phone:</strong> {user_phone}</p><p><strong>Issue:</strong> {issue_type}</p>"
            
            email_res = self.email_provider.send_email(support_email, subject, body)
            self._log_history(
                ticket_id, 'Email', 'Resend', support_email, 
                'SUCCESS' if email_res.get('success') else 'FAILED', 
                email_res.get('error', '')
            )
            
            # 2. Notify User via WhatsApp (if phone provided)
            if user_phone:
                msg = f"Your support ticket ({ticket_id}) has been created successfully. We are looking into your issue: {issue_type}."
                wa_res = self.whatsapp_provider.send_message(user_phone, msg)
                self._log_history(
                    ticket_id, 'WhatsApp', 'MockProvider', user_phone, 
                    'SUCCESS' if wa_res.get('success') else 'FAILED', 
                    wa_res.get('error', '')
                )
                
            # 3. Notify Support Team via WhatsApp (as per original request)
            support_wa = "6361864522"
            support_msg = f"New ticket {ticket_id} from {user_phone} regarding {issue_type}."
            wa_res = self.whatsapp_provider.send_message(support_wa, support_msg)
            self._log_history(
                ticket_id, 'WhatsApp', 'MockProvider', support_wa, 
                'SUCCESS' if wa_res.get('success') else 'FAILED', 
                wa_res.get('error', '')
            )

        self._send_async(task)
        
    def send_ticket_status_updated(self, ticket_id, user_phone, new_status):
        \"\"\"Dispatches notifications when a ticket's status changes.\"\"\"
        def task():
            if not user_phone:
                return
                
            msg = f"Update on your ticket {ticket_id}: Status has been changed to {new_status}."
            wa_res = self.whatsapp_provider.send_message(user_phone, msg)
            self._log_history(
                ticket_id, 'WhatsApp', 'MockProvider', user_phone, 
                'SUCCESS' if wa_res.get('success') else 'FAILED', 
                wa_res.get('error', '')
            )
            
            # Insert In-App Notification
            title = "Ticket Status Updated"
            in_app_msg = f"Your support ticket {ticket_id} has been updated to {new_status}."
            query = \"\"\"
                INSERT INTO notifications (target_user_phone, title, message, category, read_status) 
                VALUES (?, ?, ?, ?, ?)
            \"\"\"
            self._execute_db(query, (user_phone, title, in_app_msg, "ticket", "unread"))
            
        self._send_async(task)

notification_service = NotificationService()

# Hook up event bus listeners
def setup_event_listeners(event_bus):
    event_bus.subscribe("support.ticket.created", notification_service.send_ticket_created_notification)
    
    def on_ticket_updated(data):
        ticket_id = data.get('ticket_id')
        new_status = data.get('new_status')
        user_phone = data.get('user_phone')
        # Only notify if status changed
        if new_status and user_phone:
            notification_service.send_ticket_status_updated(ticket_id, user_phone, new_status)
            
    event_bus.subscribe("support.ticket.updated", on_ticket_updated)

import os
import json
import urllib.request
import urllib.parse
from datetime import datetime

class EmailProvider:
    def send_email(self, recipient: str, subject: str, body: str) -> dict:
        """Sends an email using Resend API."""
        api_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            print(f"[EmailProvider] RESEND_API_KEY not found. Mocking email to {recipient}")
            return {"success": True, "message": "Mock email sent"}
            
        url = "https://api.resend.com/emails"
        payload = json.dumps({
            "from": "MOMO AI Support <support@onlinerecharge-ai.com>",
            "to": [recipient],
            "subject": subject,
            "html": body
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return {"success": True, "data": result}
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'read'):
                error_msg = e.read().decode('utf-8')
            return {"success": False, "error": error_msg}


class WhatsAppProvider:
    def send_message(self, recipient: str, message: str) -> dict:
        """Sends a WhatsApp message using a provider (e.g., Twilio, Meta Cloud API, Interakt)."""
        # For now, we mock this as per the architecture plan.
        print(f"[WhatsAppProvider] Mocking WhatsApp message to {recipient}: {message}")
        
        # In a real implementation, we would extract credentials from os.environ
        # and POST to the corresponding API.
        
        return {"success": True, "message": "Mock WhatsApp message sent"}

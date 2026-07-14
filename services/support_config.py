import os

class SupportConfig:
    @property
    def support_email(self):
        return os.environ.get("SUPPORT_EMAIL", "customersupport@onlinerecharge-ai.com")

    @property
    def support_phone(self):
        return os.environ.get("SUPPORT_PHONE", "6361864522")

    @property
    def default_priority(self):
        return os.environ.get("DEFAULT_TICKET_PRIORITY", "Medium")

    @property
    def notify_channels(self):
        # Could be 'email', 'whatsapp', 'both'
        return os.environ.get("NOTIFY_CHANNELS", "both").lower()

    @property
    def auto_create_from_ai(self):
        return os.environ.get("AI_AUTO_CREATE_TICKETS", "true").lower() == "true"

support_config = SupportConfig()

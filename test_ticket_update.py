import sys
sys.path.append("/Users/pramod2.nayak/MOMO-ADMIN/services")
from admin_support_service import update_ticket_status
print("Updating ticket...")
update_ticket_status("TEST-123", "IN_PROGRESS", "admin@momo.com")
print("Done")

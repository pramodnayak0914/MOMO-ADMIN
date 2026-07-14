"""
Ticket generation constants and mappings.
Shared between MOMO-AI and MOMO-ADMIN.
"""

TICKET_TYPE_CODES = {
    "Incident": "INC",
    "Service Request": "REQ",
    "Refund": "REF",
    "Complaint": "CMP",
    "General Enquiry": "ENQ",
    # Mappings from common issue types:
    "Recharge Failed": "INC",
    "Refund Request": "REF",
    "General": "ENQ",
    "Money Debited": "INC",
    "Offer/Plan Not Activated": "REQ"
}

DEFAULT_TICKET_TYPE = "INC"

SERVICE_CODE_MAP = {
    "Mobile Recharge": "MR",
    "DTH": "DTH",
    "Electricity": "EB",
    "Water": "WB",
    "Gas": "GB",
    "Broadband": "BB",
    "FASTag": "FT",
    "Cable TV": "CTV",
    "Credit Card": "CC",
    "Loan": "LN",
    "Insurance": "INS",
    "LPG Cylinder": "LPG",
    "Education Fees": "EDU",
    "Housing Society": "HS",
    "Municipal Tax": "MT",
    "Donation": "DON",
    "EV Recharge": "EV",
    "Fleet Card": "FC",
    "Landline": "LL",
    
    # Internal aliases:
    "OTT Subscription Issue": "OTT",
    "OTT": "OTT"
}

DEFAULT_SERVICE_CODE = "GEN"

def get_ticket_type(issue_type):
    if not issue_type:
        return DEFAULT_TICKET_TYPE
    
    # Direct match
    if issue_type in TICKET_TYPE_CODES:
        return TICKET_TYPE_CODES[issue_type]
    
    # Keyword search
    lower_issue = issue_type.lower()
    if 'refund' in lower_issue:
        return 'REF'
    if 'complaint' in lower_issue:
        return 'CMP'
    if 'enquiry' in lower_issue or 'question' in lower_issue:
        return 'ENQ'
    if 'request' in lower_issue:
        return 'REQ'
        
    return DEFAULT_TICKET_TYPE

def get_service_code(service_name, issue_type=None, description=None):
    if service_name and service_name in SERVICE_CODE_MAP:
        return SERVICE_CODE_MAP[service_name]
        
    # Attempt to derive from issue_type if not provided directly
    if issue_type:
        for k, v in SERVICE_CODE_MAP.items():
            if k.lower() in issue_type.lower():
                return v
                
    # Fallback to description
    if description:
        for k, v in SERVICE_CODE_MAP.items():
            if k.lower() in description.lower():
                return v
                
    return DEFAULT_SERVICE_CODE

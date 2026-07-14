import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'r') as f:
    content = f.read()

# Look for: "ticket_type = query_params.get('ticket_type', [None])[0]"
# and add "created_by = query_params.get('created_by', [None])[0]"
# Then look for "if ticket_type and ticket_type != 'All':"
# and add logic for created_by

new_param = "            created_by = query_params.get('created_by', [None])[0]\n"

if 'created_by = query_params.get' not in content:
    content = content.replace(
        "assigned_agent = query_params.get('assigned_agent', [None])[0]",
        "assigned_agent = query_params.get('assigned_agent', [None])[0]\n" + new_param
    )

new_logic = """
                if created_by and created_by != 'All':
                    val = 1 if created_by == 'AI' else 0
                    query += " AND ai_generated = ?"
                    count_query += " AND ai_generated = ?"
                    params.append(val)
"""

if 'created_by and created_by != \'All\'' not in content:
    content = content.replace(
        "if assigned_agent and assigned_agent != 'All':",
        new_logic.strip() + "\n                if assigned_agent and assigned_agent != 'All':"
    )

with open('/Users/pramod2.nayak/MOMO-ADMIN/server.py', 'w') as f:
    f.write(content)

print("Patched filters in server.py")

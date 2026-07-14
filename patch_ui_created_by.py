import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/script_1.js', 'r') as f:
    content = f.read()

if "created_by: 'All'" not in content:
    content = content.replace(
        "refund_status: 'All', date_range: ''",
        "refund_status: 'All', date_range: '', created_by: 'All'"
    )

created_by_html = """
                    <div>
                        <label class="block text-xs font-semibold text-slate-400 mb-1">Created By</label>
                        <select class="w-32 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500" onchange="updateFilter('created_by', this.value)">
                            <option value="All" ${currentFilters.created_by==='All'?'selected':''}>All</option>
                            <option value="AI" ${currentFilters.created_by==='AI'?'selected':''}>AI</option>
                            <option value="Manual" ${currentFilters.created_by==='Manual'?'selected':''}>Manual</option>
                        </select>
                    </div>
"""

if "updateFilter('created_by'" not in content:
    content = content.replace(
        "<div>\n                        <label class=\"block text-xs font-semibold text-slate-400 mb-1\">Date Range</label>",
        created_by_html.strip() + "\n                    <div>\n                        <label class=\"block text-xs font-semibold text-slate-400 mb-1\">Date Range</label>"
    )

if "created_by:'All'" not in content:
    content = content.replace(
        "refund_status:'All', date_range:''}",
        "refund_status:'All', date_range:'', created_by:'All'}"
    )

with open('/Users/pramod2.nayak/MOMO-ADMIN/script_1.js', 'w') as f:
    f.write(content)
print("Patched UI for created_by filter")

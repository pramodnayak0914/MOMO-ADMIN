import re

with open('/Users/pramod2.nayak/MOMO-ADMIN/script_1.js', 'r') as f:
    content = f.read()

new_code = """
        let allTickets = [];
        let expandedTicketId = null;
        
        let dashboardStats = {
            open: 0, critical: 0, pending_refunds: 0, resolved_today: 0,
            avg_resolution_time_hrs: 0, avg_first_response_time_hrs: 0,
            sla_breached: 0, ai_created: 0, manual_created: 0
        };
        
        let currentFilters = {
            page: 1, limit: 10, ticket_id: '', mobile: '', service: '', operator: '',
            status: 'All', priority: 'All', ticket_type: 'All', assigned_agent: 'All',
            refund_status: 'All', date_range: ''
        };
        
        let paginationInfo = { total: 0, page: 1, limit: 10, pages: 1 };

        function showModal(title, message, isConfirm, onConfirm) {
            const modal = document.getElementById('custom-modal');
            document.getElementById('modal-title').innerHTML = title;
            document.getElementById('modal-message').innerText = message;
            
            const btnContainer = document.getElementById('modal-buttons');
            if (isConfirm) {
                btnContainer.innerHTML = `
                    <button onclick="closeModal(); renderTicketsUI();" class="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white text-sm font-medium transition">Cancel</button>
                    <button onclick="closeModal(); ${onConfirm}" class="px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-bold transition shadow-[0_0_15px_rgba(239,68,68,0.3)]">Yes, Process Refund</button>
                `;
            } else {
                btnContainer.innerHTML = `
                    <button onclick="closeModal()" class="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm font-bold transition">OK</button>
                `;
            }
            modal.classList.remove('hidden');
        }

        function closeModal() {
            document.getElementById('custom-modal').classList.add('hidden');
        }

        function fetchDashboardStats() {
            fetch('/api/admin/support/dashboard_stats')
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        dashboardStats = data.stats;
                        renderTicketsUI();
                    }
                })
                .catch(err => console.error("Stats Error:", err));
        }

        function fetchTickets() {
            const root = document.getElementById('react-tickets-root');
            if(allTickets.length === 0) {
                root.innerHTML = '<div class="glass-card rounded-xl overflow-hidden relative" style="min-height: 400px;"><div class="p-6 border-b border-white/5 flex justify-between items-center bg-surface-light"><h2 class="text-lg font-bold">Support Center</h2></div><div class="p-8 text-center text-slate-500">Loading tickets...</div></div>';
            }
            
            fetchDashboardStats();
            
            let queryStr = Object.keys(currentFilters).map(k => k + '=' + encodeURIComponent(currentFilters[k])).join('&');
            
            fetch('/api/support/tickets?' + queryStr)
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        allTickets = data.tickets || [];
                        if (data.pagination) paginationInfo = data.pagination;
                        renderTicketsUI();
                    } else {
                        root.innerHTML = '<div class="p-4 text-red-400">Error: ' + data.error + '</div>';
                    }
                })
                .catch(err => {
                    root.innerHTML = '<div class="p-4 text-red-400">Failed to connect: ' + err.message + '</div>';
                });
        }
        
        function updateFilter(key, value) {
            currentFilters[key] = value;
            if (key !== 'page') currentFilters.page = 1;
            fetchTickets();
        }

        function processTicketStatusUpdate(ticketId, newStatus) {
            fetch('/api/support/tickets/' + ticketId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    if(data.refund_message) showModal("✅ Refund Successful", data.refund_message, false);
                    fetchTickets();
                } else {
                    showModal("❌ Failed", data.error, false);
                    fetchTickets();
                }
            })
            .catch(err => {
                showModal("❌ Error", err.message, false);
                fetchTickets();
            });
        }

        function updateTicketStatus(ticketId, newStatus) {
            if(newStatus === 'REFUNDED') {
                showModal(
                    "⚠️ Confirm Critical Action", 
                    "Are you sure you want to refund this ticket?\\n\\nThis will instantly return the money to the customer's bank account and CANNOT be undone!", 
                    true, 
                    `processTicketStatusUpdate('${ticketId}', '${newStatus}')`
                );
                return;
            }
            processTicketStatusUpdate(ticketId, newStatus);
        }
        
        function copyTicketId(id) {
            navigator.clipboard.writeText(id);
            alert("Copied Ticket ID: " + id);
        }

        function toggleTicketRow(ticketId) {
            expandedTicketId = (expandedTicketId === ticketId) ? null : ticketId;
            renderTicketsUI();
        }

        function getTicketBadge(status) {
            const base = "px-3 py-1 rounded-full text-xs font-bold border ";
            switch(status) {
                case 'OPEN': return base + 'bg-red-500/20 text-red-400 border-red-500/50';
                case 'IN_PROGRESS': return base + 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50';
                case 'RESOLVED': return base + 'bg-green-500/20 text-green-400 border-green-500/50';
                case 'REFUNDED': return base + 'bg-blue-500/20 text-blue-400 border-blue-500/50';
                case 'CLOSED': return base + 'bg-gray-500/20 text-gray-400 border-gray-500/50';
                default: return base + 'bg-gray-500/20 text-gray-400 border-gray-500/50';
            }
        }

        function renderTicketsUI() {
            const root = document.getElementById('react-tickets-root');
            
            let kpiHtml = `
                <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-6">
                    <div class="glass-card p-4 rounded-xl border border-white/10 bg-slate-800/50 text-center">
                        <div class="text-xs text-slate-400 font-bold tracking-wider mb-1">OPEN TICKETS</div>
                        <div class="text-2xl font-bold text-white">${dashboardStats.open}</div>
                    </div>
                    <div class="glass-card p-4 rounded-xl border border-white/10 bg-slate-800/50 text-center">
                        <div class="text-xs text-red-400 font-bold tracking-wider mb-1">CRITICAL</div>
                        <div class="text-2xl font-bold text-white">${dashboardStats.critical}</div>
                    </div>
                    <div class="glass-card p-4 rounded-xl border border-white/10 bg-slate-800/50 text-center">
                        <div class="text-xs text-yellow-400 font-bold tracking-wider mb-1">PENDING REFUNDS</div>
                        <div class="text-2xl font-bold text-white">${dashboardStats.pending_refunds}</div>
                    </div>
                    <div class="glass-card p-4 rounded-xl border border-white/10 bg-slate-800/50 text-center">
                        <div class="text-xs text-emerald-400 font-bold tracking-wider mb-1">RESOLVED TODAY</div>
                        <div class="text-2xl font-bold text-white">${dashboardStats.resolved_today}</div>
                    </div>
                    <div class="glass-card p-4 rounded-xl border border-white/10 bg-slate-800/50 text-center">
                        <div class="text-xs text-slate-400 font-bold tracking-wider mb-1">AVG RESOLUTION</div>
                        <div class="text-2xl font-bold text-white">${dashboardStats.avg_resolution_time_hrs}h</div>
                    </div>
                    <div class="glass-card p-4 rounded-xl border border-white/10 bg-slate-800/50 text-center">
                        <div class="text-xs text-slate-400 font-bold tracking-wider mb-1">AVG 1ST RESPONSE</div>
                        <div class="text-2xl font-bold text-white">${dashboardStats.avg_first_response_time_hrs}h</div>
                    </div>
                    <div class="glass-card p-4 rounded-xl border border-red-500/20 bg-red-500/10 text-center">
                        <div class="text-xs text-red-400 font-bold tracking-wider mb-1">SLA BREACHED</div>
                        <div class="text-2xl font-bold text-red-400">${dashboardStats.sla_breached}</div>
                    </div>
                    <div class="glass-card p-4 rounded-xl border border-purple-500/20 bg-purple-500/10 text-center">
                        <div class="text-xs text-purple-400 font-bold tracking-wider mb-1">AI CREATED</div>
                        <div class="text-2xl font-bold text-purple-400">${dashboardStats.ai_created}</div>
                    </div>
                    <div class="glass-card p-4 rounded-xl border border-blue-500/20 bg-blue-500/10 text-center">
                        <div class="text-xs text-blue-400 font-bold tracking-wider mb-1">MANUAL CREATED</div>
                        <div class="text-2xl font-bold text-blue-400">${dashboardStats.manual_created}</div>
                    </div>
                </div>
            `;
            
            let filtersHtml = `
                <div class="glass-card p-4 rounded-xl border border-white/10 bg-surface-light mb-6 flex flex-wrap gap-4 items-end">
                    <div>
                        <label class="block text-xs font-semibold text-slate-400 mb-1">Ticket ID</label>
                        <input type="text" class="w-32 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500" value="${currentFilters.ticket_id}" onchange="updateFilter('ticket_id', this.value)" placeholder="TKT-..." />
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-400 mb-1">Mobile</label>
                        <input type="text" class="w-32 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500" value="${currentFilters.mobile}" onchange="updateFilter('mobile', this.value)" placeholder="Phone" />
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-400 mb-1">Status</label>
                        <select class="w-32 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500" onchange="updateFilter('status', this.value)">
                            <option value="All" ${currentFilters.status==='All'?'selected':''}>All</option>
                            <option value="OPEN" ${currentFilters.status==='OPEN'?'selected':''}>OPEN</option>
                            <option value="IN_PROGRESS" ${currentFilters.status==='IN_PROGRESS'?'selected':''}>IN_PROGRESS</option>
                            <option value="RESOLVED" ${currentFilters.status==='RESOLVED'?'selected':''}>RESOLVED</option>
                            <option value="CLOSED" ${currentFilters.status==='CLOSED'?'selected':''}>CLOSED</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-400 mb-1">Priority</label>
                        <select class="w-32 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500" onchange="updateFilter('priority', this.value)">
                            <option value="All" ${currentFilters.priority==='All'?'selected':''}>All</option>
                            <option value="High" ${currentFilters.priority==='High'?'selected':''}>High</option>
                            <option value="Medium" ${currentFilters.priority==='Medium'?'selected':''}>Medium</option>
                            <option value="Low" ${currentFilters.priority==='Low'?'selected':''}>Low</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-400 mb-1">Ticket Type</label>
                        <select class="w-32 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500" onchange="updateFilter('ticket_type', this.value)">
                            <option value="All" ${currentFilters.ticket_type==='All'?'selected':''}>All</option>
                            <option value="Recharge Failed" ${currentFilters.ticket_type==='Recharge Failed'?'selected':''}>Recharge Failed</option>
                            <option value="Refund" ${currentFilters.ticket_type==='Refund'?'selected':''}>Refund</option>
                            <option value="General" ${currentFilters.ticket_type==='General'?'selected':''}>General</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-400 mb-1">Date Range</label>
                        <select class="w-32 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500" onchange="updateFilter('date_range', this.value)">
                            <option value="" ${currentFilters.date_range===''?'selected':''}>All Time</option>
                            <option value="today" ${currentFilters.date_range==='today'?'selected':''}>Today</option>
                            <option value="week" ${currentFilters.date_range==='week'?'selected':''}>Past 7 Days</option>
                            <option value="month" ${currentFilters.date_range==='month'?'selected':''}>Past 30 Days</option>
                        </select>
                    </div>
                    <div class="ml-auto flex gap-2">
                        <button onclick="currentFilters={page:1, limit:10, ticket_id:'', mobile:'', service:'', operator:'', status:'All', priority:'All', ticket_type:'All', assigned_agent:'All', refund_status:'All', date_range:''}; fetchTickets();" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-sm transition border border-white/10">Clear Filters</button>
                    </div>
                </div>
            `;
            
            let paginationHtml = `
                <div class="p-4 border-t border-white/5 flex justify-between items-center bg-surface-light">
                    <div class="text-sm text-slate-400">Showing page ${paginationInfo.page} of ${paginationInfo.pages} (${paginationInfo.total} total)</div>
                    <div class="flex gap-2">
                        <button onclick="if(currentFilters.page>1) { updateFilter('page', currentFilters.page - 1); }" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-sm transition border border-white/10 ${paginationInfo.page===1?'opacity-50 cursor-not-allowed':''}">Previous</button>
                        <button onclick="if(currentFilters.page<paginationInfo.pages) { updateFilter('page', currentFilters.page + 1); }" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-sm transition border border-white/10 ${paginationInfo.page===paginationInfo.pages?'opacity-50 cursor-not-allowed':''}">Next</button>
                    </div>
                </div>
            `;
            
            let html = kpiHtml + filtersHtml + `
                <div class="glass-card rounded-xl overflow-hidden relative" style="min-height: 400px;">
                    <div class="p-6 border-b border-white/5 flex justify-between items-center bg-surface-light">
                        <h2 class="text-lg font-bold">Support Tickets</h2>
                        <button onclick="fetchTickets()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm transition border border-white/10 flex items-center gap-2">
                            <i data-lucide="refresh-cw" class="w-4 h-4"></i> Refresh Data
                        </button>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="text-slate-400 text-sm border-b border-white/10 bg-white/5">
                                    <th class="p-4 font-semibold">Ticket ID / Source</th>
                                    <th class="p-4 font-semibold">Status / Priority</th>
                                    <th class="p-4 font-semibold">User Info</th>
                                    <th class="p-4 font-semibold">Issue Details</th>
                                    <th class="p-4 font-semibold">Timeline</th>
                                    <th class="p-4 font-semibold">Quick Actions</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

            if (allTickets.length === 0) {
                html += '<tr><td colspan="6" class="text-center py-8 text-slate-500">No tickets found.</td></tr>';
            } else {
                allTickets.forEach(ticket => {
                    const isExpanded = expandedTicketId === ticket.ticket_id;
                    const isRefunded = ticket.status === 'REFUNDED';
                    
                    let statusColorClass = 'text-white border-white/10 bg-black/50';
                    if (ticket.status === 'OPEN') statusColorClass = 'text-red-400 border-red-500/30 bg-red-500/10 font-bold';
                    if (ticket.status === 'IN_PROGRESS') statusColorClass = 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10 font-bold';
                    if (ticket.status === 'REFUNDED') statusColorClass = 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10 font-bold';
                    if (ticket.status === 'RESOLVED' || ticket.status === 'CLOSED') statusColorClass = 'text-blue-400 border-blue-500/30 bg-blue-500/10 font-bold';

                    let pColor = 'text-slate-400';
                    if(ticket.priority === 'High' || ticket.priority === 'Critical') pColor = 'text-red-400 font-bold';
                    
                    let aiBadge = ticket.ai_generated ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-400 border border-purple-500/30">AI CREATED</span>' : '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">MANUAL</span>';

                    html += `
                        <tr class="border-b border-white/5 hover:bg-white/5 transition group ${isExpanded ? 'bg-white/5' : ''}">
                            <td class="p-4">
                                <div class="font-mono text-sm text-blue-400 font-semibold mb-1 cursor-pointer hover:underline" onclick="toggleTicketRow('${ticket.ticket_id}')">${ticket.ticket_id}</div>
                                <div>${aiBadge}</div>
                            </td>
                            <td class="p-4">
                                <div class="mb-2"><span class="px-3 py-1 rounded-full text-xs border ${statusColorClass}">${ticket.status}</span></div>
                                <div class="text-xs ${pColor}">Pri: ${ticket.priority || 'Medium'}</div>
                            </td>
                            <td class="p-4">
                                <div class="font-medium">${ticket.user_phone || 'N/A'}</div>
                            </td>
                            <td class="p-4">
                                <div class="font-medium text-white">${ticket.issue_type || 'General Support'}</div>
                                <div class="text-xs text-slate-400 mt-1 truncate max-w-xs" title="${ticket.description || ''}">${ticket.description ? ticket.description.substring(0, 40) + '...' : ''}</div>
                            </td>
                            <td class="p-4 text-xs text-slate-400">
                                <div class="mb-1"><span class="font-semibold text-slate-300">Created:</span> ${ticket.created_at ? new Date(ticket.created_at).toLocaleString() : 'N/A'}</div>
                                <div><span class="font-semibold text-slate-300">SLA:</span> ${ticket.sla_deadline ? new Date(ticket.sla_deadline).toLocaleString() : 'N/A'}</div>
                            </td>
                            <td class="p-4">
                                <div class="flex flex-wrap gap-2">
                                    <button onclick="toggleTicketRow('${ticket.ticket_id}')" class="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs text-white transition">View</button>
                                    <button onclick="copyTicketId('${ticket.ticket_id}')" class="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs text-white transition">Copy ID</button>
                                    ${!isRefunded && (ticket.issue_type === 'Refund' || ticket.priority === 'High') ? `<button onclick="updateTicketStatus('${ticket.ticket_id}', 'REFUNDED')" class="px-2 py-1 bg-red-500/20 hover:bg-red-500/40 border border-red-500/50 rounded text-xs text-red-400 font-bold transition">Refund</button>` : ''}
                                    ${ticket.status !== 'RESOLVED' && ticket.status !== 'CLOSED' && ticket.status !== 'REFUNDED' ? `<button onclick="updateTicketStatus('${ticket.ticket_id}', 'RESOLVED')" class="px-2 py-1 bg-blue-500/20 hover:bg-blue-500/40 border border-blue-500/50 rounded text-xs text-blue-400 font-bold transition">Resolve</button>` : ''}
                                </div>
                            </td>
                        </tr>
                    `;

                    if (isExpanded) {
                        html += `
                            <tr class="bg-black/30 border-b border-white/5">
                                <td colspan="6" class="p-6">
                                    <div class="grid grid-cols-2 gap-8">
                                        <div>
                                            <h4 class="text-sm font-bold text-white mb-3">Ticket Details</h4>
                                            <div class="space-y-2 text-sm">
                                                <div class="flex justify-between"><span class="text-slate-400">Target Number:</span> <span class="text-white">${ticket.target_number || 'N/A'}</span></div>
                                                <div class="flex justify-between"><span class="text-slate-400">Order ID:</span> <span class="font-mono text-blue-400">${ticket.order_id || 'N/A'}</span></div>
                                                <div class="flex justify-between"><span class="text-slate-400">Assigned Agent:</span> <span class="text-white">${ticket.assigned_agent || 'Unassigned'}</span></div>
                                            </div>
                                            <div class="mt-4">
                                                <h4 class="text-sm font-bold text-white mb-2">Description / AI Summary</h4>
                                                <div class="p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-300 leading-relaxed max-h-40 overflow-y-auto">
                                                    ${ticket.description || 'No description provided.'}
                                                    ${ticket.ai_summary ? `<div class="mt-2 pt-2 border-t border-white/10"><strong class="text-purple-400">AI Summary:</strong> ${ticket.ai_summary}</div>` : ''}
                                                </div>
                                            </div>
                                        </div>
                                        <div>
                                            <h4 class="text-sm font-bold text-white mb-3 flex justify-between items-center">
                                                <span>Timeline / History</span>
                                                <button class="text-xs px-2 py-1 bg-white/10 hover:bg-white/20 rounded transition">Add Note</button>
                                            </h4>
                                            <div class="p-4 bg-white/5 border border-white/10 rounded-lg max-h-48 overflow-y-auto">
                                                <div class="relative pl-4 border-l border-slate-700 space-y-4">
                                                    <div class="relative">
                                                        <div class="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-blue-500 ring-4 ring-slate-900"></div>
                                                        <div class="text-xs text-slate-400">${ticket.created_at ? new Date(ticket.created_at).toLocaleString() : 'N/A'}</div>
                                                        <div class="text-sm font-medium text-white">Ticket Created</div>
                                                        <div class="text-xs text-slate-500">System</div>
                                                    </div>
                                                    ${ticket.status === 'REFUNDED' ? `
                                                    <div class="relative">
                                                        <div class="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-4 ring-slate-900"></div>
                                                        <div class="text-xs text-slate-400">Later</div>
                                                        <div class="text-sm font-medium text-emerald-400">Refund Processed</div>
                                                        <div class="text-xs text-slate-500">Admin Action</div>
                                                    </div>` : ''}
                                                </div>
                                            </div>
                                            
                                            <div class="mt-4 flex gap-2">
                                                <select class="flex-1 bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                                                    <option value="">Update Status...</option>
                                                    <option value="OPEN">Open</option>
                                                    <option value="IN_PROGRESS">In Progress</option>
                                                    <option value="RESOLVED">Resolved</option>
                                                    <option value="CLOSED">Closed</option>
                                                </select>
                                                <button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg text-sm transition shadow-[0_0_15px_rgba(37,99,235,0.3)]">Update</button>
                                            </div>
                                        </div>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }
                });
            }

            html += `
                            </tbody>
                        </table>
                    </div>
                    ${paginationHtml}
                </div>
            `;
            
            root.innerHTML = html;
            if(window.lucide) lucide.createIcons();
        }
"""

start_str = "let allTickets = [];"
end_str = "lucide.createIcons();\n        }"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx != -1 and end_idx != -1:
    end_idx += len(end_str)
    new_content = content[:start_idx] + new_code + content[end_idx:]
    with open('/Users/pramod2.nayak/MOMO-ADMIN/script_1.js', 'w') as f:
        f.write(new_content)
    print("Successfully patched script_1.js")
else:
    print("Could not find start/end markers in script_1.js")

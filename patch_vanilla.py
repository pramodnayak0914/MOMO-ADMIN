import re

with open('index.html', 'r') as f:
    content = f.read()

# Remove the React and Babel script tags
content = re.sub(r'<script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>\n', '', content)
content = re.sub(r'<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>\n', '', content)
content = re.sub(r'<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>\n', '', content)

# Remove the React Tickets Component block
start_tag = '    <!-- React Tickets Component -->'
end_tag = '    <!-- Vanilla JS Logic for existing features -->'
start_idx = content.find(start_tag)
end_idx = content.find(end_tag)

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + content[end_idx:]

# Inject Vanilla JS renderTickets
vanilla_js = """
    <!-- Vanilla JS Tickets Component -->
    <script>
        let allTickets = [];
        let expandedTicketId = null;

        function fetchTickets() {
            const root = document.getElementById('react-tickets-root');
            if(allTickets.length === 0) {
                root.innerHTML = '<div class="glass-card rounded-xl overflow-hidden relative" style="min-height: 400px;"><div class="p-6 border-b border-white/5 flex justify-between items-center bg-surface-light"><h2 class="text-lg font-bold">Support Center</h2></div><div class="p-8 text-center text-slate-500">Loading tickets...</div></div>';
            }
            
            fetch('/api/support/tickets')
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        allTickets = data.tickets || [];
                        renderTicketsUI();
                    } else {
                        root.innerHTML = '<div class="p-4 text-red-400">Error: ' + data.error + '</div>';
                    }
                })
                .catch(err => {
                    root.innerHTML = '<div class="p-4 text-red-400">Failed to connect: ' + err.message + '</div>';
                });
        }

        function updateTicketStatus(ticketId, newStatus) {
            if(newStatus === 'REFUNDED') {
                if(!confirm("Are you sure you want to refund this ticket?\\nThis cannot be undone!")) {
                    renderTicketsUI(); // Reset dropdown
                    return;
                }
            }
            
            fetch('/api/support/tickets/' + ticketId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    if(data.refund_message) alert("Refund: " + data.refund_message);
                    fetchTickets();
                } else {
                    alert("Failed: " + data.error);
                    fetchTickets();
                }
            })
            .catch(err => {
                alert("Error: " + err.message);
            });
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
                default: return base + 'bg-gray-500/20 text-gray-400 border-gray-500/50';
            }
        }

        function renderTicketsUI() {
            const root = document.getElementById('react-tickets-root');
            
            let html = `
                <div class="glass-card rounded-xl overflow-hidden relative" style="min-height: 400px;">
                    <div class="p-6 border-b border-white/5 flex justify-between items-center bg-surface-light">
                        <h2 class="text-lg font-bold">Support Center</h2>
                        <button onclick="fetchTickets()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm transition border border-white/10 flex items-center gap-2">
                            <i data-lucide="refresh-cw" class="w-4 h-4"></i> Refresh Data
                        </button>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="text-slate-400 text-sm border-b border-white/10 bg-white/5">
                                    <th class="p-4 font-semibold">Ticket ID</th>
                                    <th class="p-4 font-semibold">Status</th>
                                    <th class="p-4 font-semibold">User Phone</th>
                                    <th class="p-4 font-semibold">Issue Type</th>
                                    <th class="p-4 font-semibold">Target Number</th>
                                    <th class="p-4 font-semibold">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

            if (allTickets.length === 0) {
                html += '<tr><td colspan="6" class="text-center py-8 text-slate-500">No tickets found in database.</td></tr>';
            } else {
                allTickets.forEach(ticket => {
                    const isExpanded = expandedTicketId === ticket.ticket_id;
                    const isRefunded = ticket.status === 'REFUNDED';
                    
                    html += `
                        <tr class="border-b border-white/5 hover:bg-white/5 cursor-pointer transition" onclick="toggleTicketRow('${ticket.ticket_id}')">
                            <td class="p-4 font-semibold">${ticket.ticket_id}</td>
                            <td class="p-4">
                                <select 
                                    onchange="event.stopPropagation(); updateTicketStatus('${ticket.ticket_id}', this.value)"
                                    class="bg-black/50 border border-white/10 text-white text-xs rounded-lg p-2 outline-none ${isRefunded ? 'opacity-50' : ''}"
                                    ${isRefunded ? 'disabled' : ''}
                                >
                                    <option value="OPEN" ${ticket.status==='OPEN'?'selected':''}>OPEN</option>
                                    <option value="IN_PROGRESS" ${ticket.status==='IN_PROGRESS'?'selected':''}>IN PROGRESS</option>
                                    <option value="RESOLVED" ${ticket.status==='RESOLVED'?'selected':''}>RESOLVED</option>
                                    <option value="REFUNDED" ${ticket.status==='REFUNDED'?'selected':''}>REFUNDED</option>
                                </select>
                            </td>
                            <td class="p-4">${ticket.user_phone}</td>
                            <td class="p-4 text-accent">${ticket.issue_type}</td>
                            <td class="p-4">${ticket.target_number || 'N/A'}</td>
                            <td class="p-4 text-primary text-sm">${isExpanded ? 'Hide Details' : 'View Details'}</td>
                        </tr>
                    `;

                    if (isExpanded) {
                        html += `
                            <tr class="bg-black/20">
                                <td colspan="6" class="p-6">
                                    <div class="grid grid-cols-2 gap-8">
                                        <div>
                                            <h4 class="text-xs font-bold text-slate-500 uppercase mb-2">Description</h4>
                                            <p class="text-slate-300 text-sm whitespace-pre-wrap bg-black/40 p-4 rounded-lg border border-white/5">${ticket.description}</p>
                                        </div>
                                        <div>
                                            <h4 class="text-xs font-bold text-slate-500 uppercase mb-2">Metadata</h4>
                                            <div class="bg-black/40 p-4 rounded-lg border border-white/5 space-y-2 text-sm">
                                                <div class="flex justify-between border-b border-white/5 pb-2">
                                                    <span class="text-slate-400">Created At:</span>
                                                    <span>${new Date(ticket.created_at).toLocaleString()}</span>
                                                </div>
                                                <div class="flex justify-between border-b border-white/5 pb-2">
                                                    <span class="text-slate-400">Database ID:</span>
                                                    <span>${ticket.id}</span>
                                                </div>
                                                <div class="flex justify-between">
                                                    <span class="text-slate-400">Current Status:</span>
                                                    <span class="${getTicketBadge(ticket.status)}">${ticket.status}</span>
                                                </div>
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
                </div>
            `;

            root.innerHTML = html;
            lucide.createIcons();
        }

        window.addEventListener('admin-unlocked', fetchTickets);
        setInterval(() => {
            if (sessionStorage.getItem('admin-passcode')) fetchTickets();
        }, 10000);
    </script>
"""

content = content.replace('    <!-- Vanilla JS Logic for existing features -->', vanilla_js + '\n    <!-- Vanilla JS Logic for existing features -->')

with open('index.html', 'w') as f:
    f.write(content)

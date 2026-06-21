
        let allTickets = [];
        let expandedTicketId = null;

        
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
                    "Are you sure you want to refund this ticket?\n\nThis will instantly return the money to the customer's bank account and CANNOT be undone!", 
                    true, 
                    `processTicketStatusUpdate('${ticketId}', '${newStatus}')`
                );
                return;
            }
            processTicketStatusUpdate(ticketId, newStatus);
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
                    
                    let statusColorClass = 'text-white border-white/10 bg-black/50';
                    if (ticket.status === 'OPEN') statusColorClass = 'text-red-400 border-red-500/30 bg-red-500/10 font-bold';
                    if (ticket.status === 'IN_PROGRESS') statusColorClass = 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10 font-bold';
                    if (ticket.status === 'REFUNDED') statusColorClass = 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10 font-bold';
                    if (ticket.status === 'RESOLVED') statusColorClass = 'text-blue-400 border-blue-500/30 bg-blue-500/10 font-bold';

                    html += `
                        <tr class="border-b border-white/5 hover:bg-white/5 cursor-pointer transition" onclick="toggleTicketRow('${ticket.ticket_id}')">
                            <td class="p-4 font-semibold">${ticket.ticket_id}</td>
                            <td class="p-4">
                                <select 
                                    onclick="event.stopPropagation()"
                                    onchange="event.stopPropagation(); updateTicketStatus('${ticket.ticket_id}', this.value)"
                                    class="text-xs rounded-lg p-2 outline-none border ${statusColorClass} ${isRefunded ? 'opacity-50' : ''}"
                                    ${isRefunded ? 'disabled' : ''}
                                >
                                    <option value="OPEN" ${ticket.status==='OPEN'?'selected':''}>OPEN</option>
                                    <option value="IN_PROGRESS" ${ticket.status==='IN_PROGRESS'?'selected':''}>IN PROGRESS</option>
                                    <option value="RESOLVED" ${ticket.status==='RESOLVED'?'selected':''}>RESOLVED</option>
                                    ${(window.adminPermissions?.can_refund || ticket.status==='REFUNDED') ? `<option value="REFUNDED" ${ticket.status==='REFUNDED'?'selected':''}>REFUNDED</option>` : ''}
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
            if (sessionStorage.getItem('admin-token')) fetchTickets();
        }, 10000);
    
    <script>
        // Tab Navigation Logic
        const navBtns = document.querySelectorAll('.nav-btn[data-target]');
        const tabSections = document.querySelectorAll('.tab-section');

        navBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                navBtns.forEach(b => b.classList.remove('active'));
                tabSections.forEach(s => s.classList.remove('active'));
                
                btn.classList.add('active');
                document.getElementById(btn.getAttribute('data-target')).classList.add('active');
            });
        });

        // Authentication & Main Data Load
        let gPasscode = '';
        
        document.getElementById('login-btn').addEventListener('click', () => {
            const passcode = document.getElementById('admin-passcode').value;
            fetch('/api/admin/data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ passcode })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    gPasscode = passcode;
                    sessionStorage.setItem('admin-passcode', passcode);
                    document.getElementById('login-overlay').style.display = 'none';
                    document.getElementById('dashboard-content').classList.remove('hidden');
                    renderDashboard(data);
                    loadTickets();
                } else {
                    document.getElementById('login-error').innerText = "Error: " + (data.error || "Invalid Passcode");
                    document.getElementById('login-error').style.display = 'block';
                }
            })
            .catch(err => {
                console.error("Login Error:", err);
                document.getElementById('login-error').innerText = "Dashboard Error: " + err.message;
                document.getElementById('login-error').style.display = 'block';
            });
        });

        document.getElementById('logout-btn').addEventListener('click', () => {
            sessionStorage.removeItem('admin-passcode');
            gPasscode = '';
            document.getElementById('admin-passcode').value = '';
            document.getElementById('dashboard-content').classList.add('hidden');
            document.getElementById('login-overlay').style.display = 'flex';
        });

        function renderDashboard(data) {
            let totalRevenue = 0;
            let successCount = 0;
            const txBody = document.getElementById('tx-table-body');
            txBody.innerHTML = '';

            data.transactions.forEach(tx => {
                const statusStr = (tx.status || 'pending').toLowerCase();
                if (statusStr === 'success' || statusStr === 'paid') {
                    totalRevenue += tx.amount;
                    successCount++;
                }
                let statusClass = 'pending';
                if (statusStr === 'success' || statusStr === 'paid') statusClass = 'success';
                else if (statusStr === 'failed' || statusStr === 'refunded') statusClass = 'failed';

                txBody.innerHTML += `
                    <tr>
                        <td>${tx.order_id}</td>
                        <td>${tx.user_identifier}</td>
                        <td style="color: var(--primary-color); font-weight: bold;">₹${tx.amount.toFixed(2)}</td>
                        <td><span class="badge ${statusClass}">${tx.status.toUpperCase()}</span></td>
                        <td style="color: var(--text-muted);">${new Date(tx.created_at).toLocaleString()}</td>
                    </tr>
                `;
            });

            document.getElementById('metric-revenue').innerText = '₹' + totalRevenue.toLocaleString();
            document.getElementById('metric-tx-count').innerText = successCount;
            document.getElementById('metric-plans-count').innerText = data.purchases.length;

            const pBody = document.getElementById('purchases-table-body');
            pBody.innerHTML = '';
            data.purchases.forEach(p => {
                pBody.innerHTML += `
                    <tr>
                        <td style="font-weight: 600;">${p.user_identifier}</td>
                        <td>${p.brand_name}</td>
                        <td><span class="badge" style="background: rgba(255,255,255,0.1); color: white;">${(p.flow_type || 'N/A').toUpperCase()}</span></td>
                        <td style="color: var(--text-muted);">${new Date(p.created_at).toLocaleString()}</td>
                    </tr>
                `;
            });

            // Render Analytics
            if (data.analytics) {
                document.getElementById('funnel-visits').innerText = data.analytics.page_view || 0;
                document.getElementById('funnel-entered').innerText = data.analytics.entered_number || 0;
                document.getElementById('funnel-logged').innerText = data.analytics.logged_in || 0;
                document.getElementById('funnel-checkout').innerText = data.analytics.checkout_started || 0;
                document.getElementById('funnel-purchased').innerText = data.analytics.purchase_success || successCount;

                if (data.analytics.leads) {
                    const leadsBody = document.getElementById('leads-table-body');
                    leadsBody.innerHTML = '';
                    if (data.analytics.leads.length === 0) {
                        leadsBody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No leads captured yet.</td></tr>';
                    } else {
                        data.analytics.leads.forEach(lead => {
                            leadsBody.innerHTML += `
                                <tr>
                                    <td style="font-weight: bold; color: white;">${lead.contact}<br><span style="font-size: 0.8rem; font-weight: normal; color: var(--text-muted);">${lead.email || ''}</span></td>
                                    <td style="color: var(--accent);">${lead.stage}</td>
                                    <td style="color: var(--text-muted);">${new Date(lead.last_active).toLocaleString()}</td>
                                </tr>
                            `;
                        });
                    }
                }
            }
        }

        // Support Tickets Logic
        document.getElementById('refresh-tickets-btn').addEventListener('click', loadTickets);

        function loadTickets() {
            if (!gPasscode) return;
            fetch('/api/support/tickets')
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById('tickets-table-body');
                tbody.innerHTML = '';
                if(data.success && data.tickets) {
                    if(data.tickets.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No tickets found.</td></tr>';
                        return;
                    }
                    data.tickets.forEach(ticket => {
                        const statusClass = ticket.status === 'OPEN' ? 'failed' : ticket.status === 'RESOLVED' ? 'success' : 'pending';
                        const selectHtml = `
                            <select onchange="updateTicketStatus(${ticket.ticket_id}, this.value)" style="background: rgba(0,0,0,0.5); color: white; border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; padding: 4px;" ${ticket.status === 'REFUNDED' ? 'disabled' : ''}>
                                <option value="OPEN" ${ticket.status === 'OPEN' ? 'selected' : ''}>OPEN</option>
                                <option value="IN_PROGRESS" ${ticket.status === 'IN_PROGRESS' ? 'selected' : ''}>IN PROGRESS</option>
                                <option value="RESOLVED" ${ticket.status === 'RESOLVED' ? 'selected' : ''}>RESOLVED</option>
                                <option value="REFUNDED" ${ticket.status === 'REFUNDED' ? 'selected' : ''}>REFUNDED</option>
                            </select>
                        `;
                        tbody.innerHTML += `
                            <tr>
                                <td>${ticket.ticket_id}</td>
                                <td>${selectHtml}</td>
                                <td>${ticket.user_phone}</td>
                                <td style="color: var(--accent);">${ticket.issue_type}</td>
                                <td>${ticket.target_number || '-'}</td>
                                <td><button onclick="alert('Description:\\n${(ticket.description || 'No description').replace(/\"/g, '&quot;')}')" class="nav-btn" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;">View</button></td>
                            </tr>
                        `;
                    });
                }
            });
        }

        window.updateTicketStatus = function(ticketId, newStatus) {
            if (newStatus === 'REFUNDED') {
                if(!confirm("Are you sure you want to refund this ticket? This cannot be undone!")) {
                    loadTickets();
                    return;
                }
            }
            fetch(\`/api/support/tickets/\${ticketId}\`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    if(data.refund_message) alert("Refund Processed: " + data.refund_message);
                    loadTickets();
                } else {
                    alert("Error: " + data.error);
                    loadTickets();
                }
            });
        };
    </script>

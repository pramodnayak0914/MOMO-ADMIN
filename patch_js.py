import re

with open('index.html', 'r') as f:
    content = f.read()

# Replace renderDashboard and window.globalData
js_orig = """        function renderDashboard(data) {
            if (data.assistant_name) {
                document.getElementById('admin-assistant-name').value = data.assistant_name;
            }
            let totalRevenue = 0;
            let totalRefunded = 0;
            let successCount = 0;
            const txBody = document.getElementById('tx-table-body');
            txBody.innerHTML = '';

            data.transactions.forEach(tx => {
                if (tx.status.toLowerCase() === 'success' || tx.status.toLowerCase() === 'paid') {
                    totalRevenue += tx.amount;
                    successCount++;
                } else if (tx.status.toLowerCase() === 'refunded') {
                    totalRefunded += tx.amount;
                }
                
                let statusClass = 'pending';
                if (tx.status.toLowerCase() === 'success' || tx.status.toLowerCase() === 'paid') statusClass = 'success';
                else if (tx.status.toLowerCase() === 'failed') statusClass = 'failed';
                else if (tx.status.toLowerCase() === 'refunded') statusClass = 'failed'; // reuse failed class for red

                txBody.innerHTML += `
                    <tr>
                        <td>${tx.order_id}</td>
                        <td>${tx.user_identifier}</td>
                        <td class="font-bold text-primary">₹${tx.amount.toFixed(2)}</td>
                        <td><span class="badge ${statusClass}">${tx.status.toUpperCase()}</span></td>
                        <td class="text-slate-400 text-sm">${new Date(tx.created_at).toLocaleString()}</td>
                    </tr>
                `;
            });

            document.getElementById('metric-revenue').innerText = '₹' + totalRevenue.toLocaleString();
            document.getElementById('metric-refunded').innerText = '₹' + totalRefunded.toLocaleString();
            document.getElementById('metric-tx-count').innerText = successCount;
            document.getElementById('metric-plans-count').innerText = data.purchases.length;

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
                        leadsBody.innerHTML = '<tr><td colspan="3" class="text-center text-slate-500 py-8">No leads captured yet.</td></tr>';
                    } else {
                        data.analytics.leads.forEach(lead => {
                            leadsBody.innerHTML += `
                                <tr class="border-b border-white/5">
                                    <td class="py-4">
                                        <div class="font-bold text-white">${lead.contact}</div>
                                        <div class="text-xs text-slate-400 mt-1">${lead.email || 'No email provided'}</div>
                                    </td>
                                    <td class="py-4 text-accent">${lead.stage}</td>
                                    <td class="py-4 text-slate-400 text-sm">${new Date(lead.last_active).toLocaleString()}</td>
                                </tr>
                            `;
                        });
                    }
                }
            }
        }"""

js_new = """        window.globalData = null;
        function renderDashboard(data) {
            window.globalData = data;
            if (data.assistant_name) {
                document.getElementById('admin-assistant-name').value = data.assistant_name;
            }
            
            // 1. Render Business Metrics (Overview)
            if (data.business_metrics) {
                const bm = data.business_metrics;
                document.getElementById('metric-rev-today').innerText = '₹' + bm.revenue.today.toLocaleString();
                document.getElementById('metric-rev-month').innerText = '₹' + bm.revenue.monthly.toLocaleString();
                document.getElementById('metric-recharge-total').innerText = bm.recharge.total_count;
                document.getElementById('metric-recharge-succ').innerText = bm.recharge.success_pct;
                document.getElementById('metric-users-new').innerText = bm.users.new_today;
                document.getElementById('metric-users-active').innerText = bm.users.active;
                document.getElementById('metric-top-operator').innerText = bm.operators.top_operator || 'N/A';
                document.getElementById('metric-top-plan').innerText = 'Plan: ' + (bm.operators.top_plan || 'N/A');
            }

            // 2. Render Users Table
            const usersBody = document.getElementById('users-table-body');
            usersBody.innerHTML = '';
            if (data.users) {
                data.users.forEach(u => {
                    const statusClass = u.status === 'active' ? 'success' : 'failed';
                    usersBody.innerHTML += `
                        <tr class="border-b border-white/5">
                            <td class="py-4">${u.phone_number}</td>
                            <td class="py-4"><span class="badge ${statusClass}">${u.status.toUpperCase()}</span></td>
                            <td class="py-4 text-slate-400 text-sm">${new Date(u.created_at).toLocaleString()}</td>
                            <td class="py-4 text-right">
                                <button onclick="userAction('${u.phone_number}', 'suspend')" class="px-3 py-1 bg-red-500/10 text-red-400 rounded hover:bg-red-500/20 text-xs mr-2">Suspend</button>
                                <button onclick="userAction('${u.phone_number}', 'verify')" class="px-3 py-1 bg-green-500/10 text-green-400 rounded hover:bg-green-500/20 text-xs">Verify</button>
                            </td>
                        </tr>
                    `;
                });
            }

            // 3. Render Recharges & Payments
            renderRecharges(data);

            // 4. Render Fraud Alerts
            const fraudBody = document.getElementById('fraud-table-body');
            fraudBody.innerHTML = '';
            if (data.fraud_alerts) {
                data.fraud_alerts.forEach(f => {
                    fraudBody.innerHTML += `
                        <tr class="border-b border-white/5">
                            <td class="py-4 font-bold text-white">${f.user_phone}</td>
                            <td class="py-4 text-red-400">${f.event_type}</td>
                            <td class="py-4 text-sm">${f.details}</td>
                            <td class="py-4 text-slate-400 text-xs">${f.ip_address}<br/>${f.device_id.substring(0,8)}...</td>
                            <td class="py-4 text-slate-400 text-xs">${new Date(f.created_at).toLocaleString()}</td>
                        </tr>
                    `;
                });
            }

            // 5. Analytics Funnel
            if (data.analytics) {
                document.getElementById('funnel-visits').innerText = data.analytics.page_view || 0;
                document.getElementById('funnel-entered').innerText = data.analytics.entered_number || 0;
                document.getElementById('funnel-logged').innerText = data.analytics.logged_in || 0;
                document.getElementById('funnel-checkout').innerText = data.analytics.checkout_started || 0;
                document.getElementById('funnel-purchased').innerText = data.analytics.purchase_success || 0;

                if (data.analytics.leads) {
                    const leadsBody = document.getElementById('leads-table-body');
                    leadsBody.innerHTML = '';
                    if (data.analytics.leads.length === 0) {
                        leadsBody.innerHTML = '<tr><td colspan="3" class="text-center text-slate-500 py-8">No leads captured yet.</td></tr>';
                    } else {
                        data.analytics.leads.forEach(lead => {
                            leadsBody.innerHTML += `
                                <tr class="border-b border-white/5">
                                    <td class="py-4">
                                        <div class="font-bold text-white">${lead.contact}</div>
                                        <div class="text-xs text-slate-400 mt-1">${lead.email || 'No email provided'}</div>
                                    </td>
                                    <td class="py-4 text-accent">${lead.stage}</td>
                                    <td class="py-4 text-slate-400 text-sm">${new Date(lead.last_active).toLocaleString()}</td>
                                </tr>
                            `;
                        });
                    }
                }
            }
        }

        window.renderRecharges = function(data) {
            if(!data || !data.transactions) return;
            const filter = document.getElementById('recharge-filter') ? document.getElementById('recharge-filter').value : 'ALL';
            const rBody = document.getElementById('recharges-table-body');
            const pBody = document.getElementById('payments-table-body');
            if(rBody) rBody.innerHTML = '';
            if(pBody) pBody.innerHTML = '';

            data.transactions.forEach(tx => {
                const stat = tx.status.toUpperCase();
                if (filter !== 'ALL' && stat !== filter && !(filter === 'SUCCESS' && stat === 'PAID')) return;
                
                let statusClass = 'pending';
                if (stat === 'SUCCESS' || stat === 'PAID') statusClass = 'success';
                else if (stat === 'FAILED' || stat === 'REFUNDED') statusClass = 'failed';

                if(rBody) rBody.innerHTML += `
                    <tr class="border-b border-white/5">
                        <td class="py-4 text-xs font-mono">${tx.order_id}</td>
                        <td class="py-4">${tx.user_identifier}</td>
                        <td class="py-4 font-bold text-primary">₹${tx.amount.toFixed(2)}</td>
                        <td class="py-4"><span class="badge ${statusClass}">${stat}</span></td>
                        <td class="py-4 text-slate-400 text-xs">${new Date(tx.created_at).toLocaleString()}</td>
                        <td class="py-4 text-right">
                            <select onchange="updateRechargeStatus('${tx.order_id}', this.value)" class="bg-black/50 border border-white/10 rounded px-2 py-1 text-xs text-white outline-none mr-2">
                                <option value="">Set Status</option>
                                <option value="SUCCESS">SUCCESS</option>
                                <option value="FAILED">FAILED</option>
                                <option value="REFUNDED">REFUNDED</option>
                            </select>
                            <button onclick="retryRecharge('${tx.order_id}')" class="px-2 py-1 bg-blue-500/10 text-blue-400 rounded hover:bg-blue-500/20 text-xs">Retry</button>
                        </td>
                    </tr>
                `;

                if(pBody) pBody.innerHTML += `
                    <tr class="border-b border-white/5">
                        <td class="py-4 text-xs font-mono">${tx.order_id}</td>
                        <td class="py-4"><span class="badge ${statusClass}">${stat}</span></td>
                        <td class="py-4 font-bold text-emerald-400">₹${stat==='SUCCESS'||stat==='PAID'?tx.amount.toFixed(2):'0.00'}</td>
                        <td class="py-4 text-slate-400 text-xs">${new Date(tx.created_at).toLocaleString()}</td>
                    </tr>
                `;
            });
        };

        window.userAction = function(phone, action) {
            const status = action === 'suspend' ? 'suspended' : 'active';
            fetch('/api/admin/users/action', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({passcode: gPasscode, phone_number: phone, status: status})
            }).then(r=>r.json()).then(d=>{
                if(d.success) refreshData();
                else alert(d.error);
            });
        };

        window.updateRechargeStatus = function(orderId, status) {
            if(!status) return;
            fetch('/api/admin/recharge/status', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({passcode: gPasscode, order_id: orderId, status: status})
            }).then(r=>r.json()).then(d=>{
                if(d.success) refreshData();
                else alert(d.error);
            });
        };

        window.retryRecharge = function(orderId) {
            fetch('/api/admin/recharge/retry', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({passcode: gPasscode, order_id: orderId})
            }).then(r=>r.json()).then(d=>{
                if(d.success) refreshData();
                else alert(d.error);
            });
        };

        function refreshData() {
            if(!gPasscode) return;
            fetch('/api/admin/data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ passcode: gPasscode })
            }).then(r=>r.json()).then(d=>{
                if(d.success) renderDashboard(d);
            });
        }
"""

content = content.replace(js_orig, js_new)

with open('index.html', 'w') as f:
    f.write(content)

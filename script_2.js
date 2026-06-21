
        // Init Lucide Icons
        lucide.createIcons();

        // Tab Switching Logic
        const tabs = document.querySelectorAll('.sidebar-item[data-tab]');
        const contents = document.querySelectorAll('.tab-content');
        const pageTitle = document.getElementById('page-title');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                // Remove active class from all
                tabs.forEach(t => t.classList.remove('active'));
                contents.forEach(c => c.classList.remove('active'));
                
                // Add active to clicked
                tab.classList.add('active');
                const targetId = tab.getAttribute('data-tab');
                document.getElementById(targetId).classList.add('active');
                
                // Update title
                pageTitle.innerText = tab.querySelector('span').innerText;
            });
        });

        document.getElementById('login-btn').addEventListener('click', () => {
            const email = document.getElementById('admin-email').value;
            const password = document.getElementById('admin-password').value;
            fetch('/api/admin/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    sessionStorage.setItem('admin-email', email);
                    sessionStorage.setItem('admin-token', data.token);
                    document.getElementById('login-overlay').classList.add('hidden');
                    document.getElementById('dashboard-content').classList.remove('hidden');
                    // Fetch dashboard data
                    fetch('/api/admin/data', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, token: data.token })
                    }).then(r=>r.json()).then(dashData => {
                        if(dashData.success) {
                            renderDashboard(dashData);
                            window.dispatchEvent(new Event('admin-unlocked'));
                        }
                    });
                } else {
                    document.getElementById('login-error').innerText = data.error || "Invalid Credentials";
                    document.getElementById('login-error').classList.remove('hidden');
                }
            })
            .catch(err => {
                document.getElementById('login-error').innerText = "Network Error";
                document.getElementById('login-error').classList.remove('hidden');
            });
        });

        document.getElementById('logout-btn').addEventListener('click', () => {
            sessionStorage.removeItem('admin-email');
            sessionStorage.removeItem('admin-token');
            document.getElementById('admin-password').value = '';
            document.getElementById('dashboard-content').classList.add('hidden');
            document.getElementById('login-overlay').classList.remove('hidden');
            document.getElementById('login-error').classList.add('hidden');
        });

        window.showForgotPassword = function() {
            document.getElementById('forgot-password-modal').classList.remove('hidden');
            document.getElementById('fp-step-1').classList.remove('hidden');
            document.getElementById('fp-step-2').classList.add('hidden');
        };

        window.hideForgotPassword = function() {
            document.getElementById('forgot-password-modal').classList.add('hidden');
        };

        window.requestResetCode = function() {
            const email = document.getElementById('fp-email').value;
            if(!email) return alert("Enter your email");
            fetch('/api/admin/forgot-password', {
                method: 'POST', body: JSON.stringify({email})
            }).then(r=>r.json()).then(d => {
                if(d.success) {
                    document.getElementById('fp-step-1').classList.add('hidden');
                    document.getElementById('fp-step-2').classList.remove('hidden');
                } else {
                    alert(d.error || "Error requesting reset code");
                }
            });
        };

        window.resetPassword = function() {
            const email = document.getElementById('fp-email').value;
            const code = document.getElementById('fp-code').value;
            const new_password = document.getElementById('fp-new-password').value;
            if(!code || !new_password) return alert("Fill all fields");
            fetch('/api/admin/reset-password', {
                method: 'POST', body: JSON.stringify({email, code, new_password})
            }).then(r=>r.json()).then(d => {
                if(d.success) {
                    alert("Password reset successfully! You can now log in.");
                    hideForgotPassword();
                } else {
                    alert(d.error || "Error resetting password");
                }
            });
        };

        function renderDashboard(data) {
            if (data.assistant_name) {
                document.getElementById('admin-assistant-name').value = data.assistant_name;
            }
            if (data.admin_permissions) {
                window.adminPermissions = data.admin_permissions;
                
                // Enforce Marketing Visibility
                const marketingTab = document.querySelector('.sidebar-item[data-tab="tab-marketing"]');
                if (marketingTab) marketingTab.style.display = data.admin_permissions.can_view_marketing ? 'flex' : 'none';
                
                // Enforce Growth Engine Edits
                const growthInputs = document.querySelectorAll('#tab-growth input');
                const growthBtn = document.querySelector('#tab-growth button');
                growthInputs.forEach(inp => inp.disabled = !data.admin_permissions.can_edit_growth);
                if (growthBtn) growthBtn.style.display = data.admin_permissions.can_edit_growth ? 'block' : 'none';
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
            }

            const pBody = document.getElementById('purchases-table-body');
            pBody.innerHTML = '';
            data.purchases.forEach(p => {
                pBody.innerHTML += `
                    <tr>
                        <td class="font-semibold">${p.user_identifier}</td>
                        <td>${p.brand_name}</td>
                        <td><span class="badge" style="background: rgba(255,255,255,0.1); color: white;">${p.flow_type.toUpperCase()}</span></td>
                        <td class="text-slate-400 text-sm">${new Date(p.created_at).toLocaleString()}</td>
                    </tr>
                `;
            });

            if (data.analytics && data.analytics.leads) {
                const leadsBody = document.getElementById('leads-table-body');
                leadsBody.innerHTML = '';
                if (data.analytics.leads.length === 0) {
                    leadsBody.innerHTML = '<tr><td colspan="4" class="text-center py-8 text-slate-500">No leads captured yet.</td></tr>';
                } else {
                    data.analytics.leads.forEach(lead => {
                        let stageClass = 'text-slate-400';
                        if (lead.stage === 'Purchased') stageClass = 'text-green-400 font-bold';
                        else if (lead.stage === 'Started Checkout') stageClass = 'text-accent';
                        else if (lead.stage === 'Verified OTP') stageClass = 'text-yellow-400';
                        
                        leadsBody.innerHTML += `
                            <tr class="hover:bg-white/5 transition">
                                <td class="font-bold text-white">
                                    ${lead.contact || 'No Phone'}
                                    ${lead.email ? `<br><span class="text-xs text-slate-400 font-normal mt-1 block"><i data-lucide="mail" class="w-3 h-3 inline"></i> ${lead.email}</span>` : ''}
                                </td>
                                <td class="${stageClass}">${lead.stage}</td>
                                <td class="text-slate-400 text-sm">${new Date(lead.last_active).toLocaleString()}</td>
                                <td>
                                    ${lead.contact ? `<a href="https://wa.me/${lead.contact.replace('+','')}" target="_blank" class="px-3 py-1 bg-[#25D366]/20 text-[#25D366] hover:bg-[#25D366]/30 border border-[#25D366]/50 rounded text-xs font-bold transition flex items-center gap-1 w-max mb-1">
                                        <i data-lucide="message-circle" class="w-3 h-3"></i> WhatsApp
                                    </a>` : ''}
                                    ${lead.email ? `<a href="mailto:${lead.email}" target="_blank" class="px-3 py-1 bg-[#00BFFF]/20 text-[#00BFFF] hover:bg-[#00BFFF]/30 border border-[#00BFFF]/50 rounded text-xs font-bold transition flex items-center gap-1 w-max">
                                        <i data-lucide="mail" class="w-3 h-3"></i> Email
                                    </a>` : ''}
                                </td>
                            </tr>
                        `;
                    });
                    lucide.createIcons();
                }
            }
        }

        document.getElementById('save-assistant-name').addEventListener('click', () => {
            const newName = document.getElementById('admin-assistant-name').value.trim();
            if (!newName) return;

            const email = sessionStorage.getItem('admin-email');
            const token = sessionStorage.getItem('admin-token');
            fetch('/api/admin/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ email: email, token: token, assistant_name: newName })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    const msg = document.getElementById('save-settings-msg');
                    msg.classList.remove('hidden');
                    setTimeout(() => msg.classList.add('hidden'), 3000);
                } else {
                    alert('Error saving name: ' + data.error);
                }
            })
            .catch(err => console.error(err));
        });
    
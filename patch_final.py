import sys
with open('index.html', 'r') as f:
    html = f.read()

# Replace Login Overlay
old_modal = """    <!-- Login Overlay -->
    <div id="login-overlay" class="fixed inset-0 bg-slate-900 z-50 flex items-center justify-center">
        <div class="glass-card rounded-2xl p-10 max-w-md w-full text-center">
            <div class="mb-6 flex justify-center">
                <div class="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary">
                    <i data-lucide="shield" class="w-8 h-8"></i>
                </div>
            </div>
            <h2 class="text-3xl font-bold text-white mb-2">Portal Access</h2>
            <p class="text-slate-400 mb-8">Please sign in to continue</p>
            <div class="space-y-4">
                <input type="email" id="login-email" placeholder="Email Address" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:border-primary focus:outline-none">
                <input type="password" id="login-password" placeholder="Password" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:border-primary focus:outline-none">
                <button onclick="handleLogin()" class="w-full bg-primary text-white font-bold py-3 px-4 rounded-lg hover:bg-primary/90 transition-all">Sign In</button>
                <div id="login-error" class="text-red-400 text-sm mt-2 hidden">Invalid credentials</div>
            </div>
        </div>
    </div>"""

new_modal = """    <!-- Login Overlay -->
    <div id="login-overlay" class="fixed inset-0 bg-slate-900 z-50 flex items-center justify-center">
        <div class="glass-card rounded-2xl p-10 max-w-md w-full text-center">
            <div class="mb-6 flex justify-center">
                <div class="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary">
                    <i data-lucide="shield" class="w-8 h-8"></i>
                </div>
            </div>
            <h2 class="text-3xl font-bold text-white mb-2">Admin Portal</h2>
            <p class="text-slate-400 mb-8">Please enter your passcode</p>
            <div class="space-y-4">
                <input type="password" id="login-passcode" placeholder="Passcode" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:border-primary focus:outline-none">
                <button onclick="handleLogin()" class="w-full bg-primary text-white font-bold py-3 px-4 rounded-lg hover:bg-primary/90 transition-all">Unlock</button>
                <div id="login-error" class="text-red-400 text-sm mt-2 hidden">Invalid Passcode</div>
            </div>
        </div>
    </div>"""

html = html.replace(old_modal, new_modal)

old_script_auth = """        let authToken = sessionStorage.getItem('admin-token');
        let currentAssistantName = "OnlineRecharge AI";

        async function handleLogin() {
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email, password })
                });
                const data = await res.json();
                if (data.success) {
                    authToken = data.token;
                    sessionStorage.setItem('admin-token', authToken);
                    document.getElementById('login-overlay').classList.add('hidden');
                    window.dispatchEvent(new Event('admin-unlocked'));
                    
                    // Fetch data
                    fetch('/api/super-admin/data', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${authToken}` }
                    })
                    .then(r => r.json())
                    .then(d => {
                        if (d.success) renderDashboard(d);
                    });
                } else {
                    document.getElementById('login-error').innerText = data.error;
                    document.getElementById('login-error').classList.remove('hidden');
                }
            } catch (err) {
                document.getElementById('login-error').innerText = 'Network error: Is server running?';
                document.getElementById('login-error').classList.remove('hidden');
            }
        }

        function triggerRefresh() {
            if(authToken) {
                fetch('/api/super-admin/data', { method: 'POST', headers: { 'Authorization': `Bearer ${authToken}` }})
                .then(r => r.json())
                .then(d => { if(d.success) renderDashboard(d); });
            }
        }

        function logout() {
            sessionStorage.removeItem('admin-token');
            document.getElementById('login-overlay').classList.remove('hidden');
            document.getElementById('login-email').value = '';
            document.getElementById('login-password').value = '';
            authToken = null;
        }

        // On Load Check
        window.addEventListener('DOMContentLoaded', () => {
            if (authToken) {
                document.getElementById('login-overlay').classList.add('hidden');
                triggerRefresh();
                window.dispatchEvent(new Event('admin-unlocked'));
            }
        });"""

new_script_auth = """        let currentAssistantName = "OnlineRecharge AI";

        async function handleLogin() {
            const passcode = document.getElementById('login-passcode').value;
            if (!passcode) return;
            try {
                const res = await fetch('/api/admin/data', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ passcode })
                });
                const data = await res.json();
                if (data.success) {
                    sessionStorage.setItem('admin-passcode', passcode);
                    document.getElementById('login-overlay').classList.add('hidden');
                    window.dispatchEvent(new Event('admin-unlocked'));
                    renderDashboard(data);
                } else {
                    document.getElementById('login-error').innerText = "Invalid Passcode";
                    document.getElementById('login-error').classList.remove('hidden');
                }
            } catch (err) {
                document.getElementById('login-error').innerText = 'Network error: Is server running?';
                document.getElementById('login-error').classList.remove('hidden');
            }
        }

        function triggerRefresh() {
            const passcode = sessionStorage.getItem('admin-passcode');
            if(passcode) {
                fetch('/api/admin/data', { method: 'POST', headers: { 'Content-Type': 'application/json'}, body: JSON.stringify({ passcode })})
                .then(r => r.json())
                .then(d => { 
                    if(d.success) {
                        renderDashboard(d); 
                    } else {
                        logout();
                    }
                });
            }
        }

        function logout() {
            sessionStorage.removeItem('admin-passcode');
            document.getElementById('login-overlay').classList.remove('hidden');
            document.getElementById('login-passcode').value = '';
        }

        // On Load Check
        window.addEventListener('DOMContentLoaded', () => {
            if (sessionStorage.getItem('admin-passcode')) {
                document.getElementById('login-overlay').classList.add('hidden');
                triggerRefresh();
                window.dispatchEvent(new Event('admin-unlocked'));
            }
        });"""

html = html.replace(old_script_auth, new_script_auth)

# Fix action endpoints
html = html.replace('/api/super-admin/users/action', '/api/admin/users/action')
html = html.replace("headers: {'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json'}, body: JSON.stringify({action, phone_number: phone})", "headers: {'Content-Type': 'application/json'}, body: JSON.stringify({passcode: sessionStorage.getItem('admin-passcode'), action, phone_number: phone})")

html = html.replace('/api/super-admin/recharges/retry', '/api/admin/recharges/retry')
html = html.replace("headers: {'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json'}, body: JSON.stringify({order_id})", "headers: {'Content-Type': 'application/json'}, body: JSON.stringify({passcode: sessionStorage.getItem('admin-passcode'), order_id})")

# Also fix the React tickets fetch
old_react_fetch = """const res = await fetch('/api/super-admin/tickets', {headers: {'Authorization': `Bearer ${authToken}`}}));"""
new_react_fetch = """const res = await fetch('/api/admin/data', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({passcode: sessionStorage.getItem('admin-passcode')})
                    });"""
html = html.replace(old_react_fetch, new_react_fetch)

# Fix the response parsing for tickets
html = html.replace("setTickets(data.tickets || []);", "setTickets(data.support_tickets || []);")

# Fix `if (authToken && !confirmDialog) fetchTickets();`
html = html.replace("if (authToken && !confirmDialog) fetchTickets();", "if (sessionStorage.getItem('admin-passcode') && !confirmDialog) fetchTickets();")

with open('index.html', 'w') as f:
    f.write(html)
print("Finished!")

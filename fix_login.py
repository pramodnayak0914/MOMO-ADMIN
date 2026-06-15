import sys

with open('index.html', 'r') as f:
    html = f.read()

# 1. Replace the login modal inputs
modal_start = html.find('<div id="login-overlay"')
modal_end = html.find('</div>\n    </div>', modal_start) + 16
old_modal = html[modal_start:modal_end]

new_modal = """<div id="login-overlay" class="fixed inset-0 bg-slate-900 z-50 flex items-center justify-center">
        <div class="glass-card rounded-2xl p-10 max-w-md w-full text-center">
            <div class="mb-6 flex justify-center">
                <div class="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary">
                    <i data-lucide="shield" class="w-8 h-8"></i>
                </div>
            </div>
            <h2 class="text-3xl font-bold text-white mb-2">Portal Access</h2>
            <p class="text-slate-400 mb-8">Please enter your passcode to continue</p>
            <div class="space-y-4">
                <input type="password" id="login-passcode" placeholder="Passcode" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:border-primary focus:outline-none" onkeypress="if(event.key === 'Enter') handleLogin()">
                <button onclick="handleLogin()" class="w-full bg-primary text-white font-bold py-3 px-4 rounded-lg hover:bg-primary/90 transition-all">Unlock Dashboard</button>
                <div id="login-error" class="text-red-400 text-sm mt-2 hidden">Invalid Passcode</div>
            </div>
        </div>
    </div>"""

html = html.replace(old_modal, new_modal)
if old_modal not in html and new_modal in html:
    print("Modal Replaced")
else:
    print("Failed to replace modal")
    sys.exit(1)

# 2. Replace handleLogin
js_start = html.find('async function handleLogin() {')
js_end = html.find('        // Sidebar Navigation', js_start)
old_js = html[js_start:js_end]

new_js = """async function handleLogin() {
            const passcode = document.getElementById('login-passcode').value;
            if (!passcode) return;
            sessionStorage.setItem('admin-passcode', passcode);
            document.getElementById('login-overlay').classList.add('hidden');
            fetchData();
        }

        window.addEventListener('DOMContentLoaded', () => {
            if (sessionStorage.getItem('admin-passcode')) {
                document.getElementById('login-overlay').classList.add('hidden');
            } else {
                document.getElementById('login-overlay').classList.remove('hidden');
            }
        });

"""
html = html.replace(old_js, new_js)
if new_js in html:
    print("handleLogin replaced")
else:
    print("Failed to replace handleLogin")
    sys.exit(1)

# 3. Replace token auth
html = html.replace("sessionStorage.getItem('admin-jwt')", "sessionStorage.getItem('admin-passcode')")
html = html.replace("sessionStorage.getItem('admin-token')", "sessionStorage.getItem('admin-passcode')")
html = html.replace("sessionStorage.removeItem('admin-token')", "sessionStorage.removeItem('admin-passcode')")
html = html.replace("sessionStorage.removeItem('admin-jwt')", "sessionStorage.removeItem('admin-passcode')")

# 4. Replace fetchData to send passcode
fetch_data_start = html.find('async function fetchData() {')
fetch_data_end = html.find('if (data.success) {', fetch_data_start)
old_fetch = html[fetch_data_start:fetch_data_end]

new_fetch = """async function fetchData() {
            try {
                const pc = sessionStorage.getItem('admin-passcode');
                const res = await fetch('/api/admin/data', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({passcode: pc})
                });
                const data = await res.json();
                
                if (!data.success || res.status === 401 || res.status === 403) {
                    sessionStorage.removeItem('admin-passcode');
                    document.getElementById('login-overlay').classList.remove('hidden');
                    document.getElementById('login-error').innerText = "Invalid Passcode";
                    document.getElementById('login-error').classList.remove('hidden');
                    return;
                }
                
                """
html = html.replace(old_fetch, new_fetch)
if new_fetch in html:
    print("fetchData replaced")
else:
    print("Failed to replace fetchData")
    sys.exit(1)

# 5. Fix action fetches
html = html.replace("headers: {'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json'}, body: JSON.stringify({action, phone_number: phone})", "headers: {'Content-Type': 'application/json'}, body: JSON.stringify({passcode: sessionStorage.getItem('admin-passcode'), action, phone_number: phone})")
html = html.replace("headers: {'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json'}, body: JSON.stringify({order_id})", "headers: {'Content-Type': 'application/json'}, body: JSON.stringify({passcode: sessionStorage.getItem('admin-passcode'), order_id})")

# 6. Fix super-admin endpoint paths (since they are now /api/admin)
html = html.replace('/api/super-admin/', '/api/admin/')

# 7. Make sure `authToken` variables don't crash
html = html.replace('const authToken = sessionStorage.getItem(\'admin-token\');', 'const authToken = sessionStorage.getItem(\'admin-passcode\');')
html = html.replace('`Bearer ${authToken}`', '`Bearer ${authToken}`') # Wait, I changed the headers above.

# 8. Fix the React component fetch
react_fetch_start = html.find('const fetchTickets = async () => {')
react_fetch_end = html.find('const data = await res.json();', react_fetch_start)
old_react_fetch = html[react_fetch_start:react_fetch_end]
new_react_fetch = """const fetchTickets = async () => {
                setLoading(true);
                try {
                    const res = await fetch('/api/admin/data', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({passcode: sessionStorage.getItem('admin-passcode')})
                    });
                    """
html = html.replace(old_react_fetch, new_react_fetch)

# 9. One more fix for the dashboard render
html = html.replace('data.tickets || []', 'data.support_tickets || []')
html = html.replace('if (authToken && !confirmDialog) fetchTickets();', 'if (sessionStorage.getItem("admin-passcode") && !confirmDialog) fetchTickets();')

with open('index.html', 'w') as f:
    f.write(html)
print("SUCCESS!")

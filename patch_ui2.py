import re

with open('index.html', 'r') as f:
    html = f.read()

# Replace the login UI
old_modal_start = '    <!-- Login Overlay -->'
old_modal_end = '    <!-- Admin Dashboard Layout -->'

# We'll use regex to replace everything between these two markers
new_modal = '''    <!-- Login Overlay -->
    <div id="login-overlay" class="fixed inset-0 bg-slate-900 z-50 flex items-center justify-center">
        <div class="bg-slate-800 p-8 rounded-xl shadow-2xl max-w-md w-full border border-slate-700">
            <div class="text-center mb-8">
                <div class="bg-primary/20 p-4 rounded-full inline-block mb-4">
                    <i data-lucide="shield-check" class="w-8 h-8 text-primary"></i>
                </div>
                <h2 class="text-2xl font-bold text-white">Admin Access</h2>
                <p class="text-slate-400 mt-2">Enter your passcode to unlock dashboard</p>
            </div>
            <div class="space-y-4">
                <input type="password" id="login-passcode" placeholder="Passcode" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-white focus:border-primary focus:outline-none" onkeypress="if(event.key === 'Enter') handleLogin()">
                <button onclick="handleLogin()" class="w-full bg-primary text-white font-bold py-3 px-4 rounded-lg hover:bg-primary/90 transition-all">Unlock Dashboard</button>
                <div id="login-error" class="text-red-400 text-sm mt-2 hidden">Invalid passcode</div>
            </div>
        </div>
    </div>
'''

html = re.sub(r'    <!-- Login Overlay -->.*?    <!-- Admin Dashboard Layout -->', new_modal + '    <!-- Admin Dashboard Layout -->', html, flags=re.DOTALL)

# Replace the handleLogin function
old_js_start = '        async function handleLogin() {'
old_js_end = '        // Sidebar Navigation'

new_js = '''        async function handleLogin() {
            const pc = document.getElementById('login-passcode').value;
            if (!pc) return;
            sessionStorage.setItem('admin-passcode', pc);
            document.getElementById('login-overlay').classList.add('hidden');
            fetchData();
        }

        // Check authentication on load
        window.addEventListener('DOMContentLoaded', () => {
            const pc = sessionStorage.getItem('admin-passcode');
            if (pc) {
                document.getElementById('login-overlay').classList.add('hidden');
                fetchData();
            }
        });
        
'''

html = re.sub(r'        async function handleLogin\(\) \{.*?        // Sidebar Navigation', new_js + '        // Sidebar Navigation', html, flags=re.DOTALL)

# Update fetchData to send passcode
fetch_str_old = '''            try {
                const res = await fetch('/api/admin/data', {
                    headers: { 'Authorization': `Bearer ${sessionStorage.getItem('admin-token')}` }
                });'''

fetch_str_new = '''            try {
                const res = await fetch('/api/admin/data', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({passcode: sessionStorage.getItem('admin-passcode')})
                });'''
html = html.replace(fetch_str_old, fetch_str_new)

# Make sure if response fails it shows login modal
auth_check_old = '''                if (res.status === 401 || res.status === 403) {
                    sessionStorage.removeItem('admin-token');
                    window.location.reload();
                    return;
                }'''
                
auth_check_new = '''                const data = await res.json();
                if (!data.success || res.status === 401 || res.status === 403) {
                    sessionStorage.removeItem('admin-passcode');
                    document.getElementById('login-overlay').classList.remove('hidden');
                    document.getElementById('login-error').innerText = "Invalid Passcode";
                    document.getElementById('login-error').classList.remove('hidden');
                    return;
                }'''
                
html = re.sub(r'                if \(res\.status === 401 \|\| res\.status === 403\) \{.*?\n                \}', auth_check_new, html, flags=re.DOTALL)

# We need to remove the line "const data = await res.json();" that comes AFTER because we just added it above
html = html.replace(auth_check_new + '\n                const data = await res.json();', auth_check_new)


# Update users action fetch
html = html.replace('''                const res = await fetch('/api/admin/users/action', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${sessionStorage.getItem('admin-token')}`
                    },
                    body: JSON.stringify({ phone_number: phone, action: action })
                });''', '''                const res = await fetch('/api/admin/users/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ passcode: sessionStorage.getItem('admin-passcode'), phone_number: phone, action: action })
                });''')

# Update recharge retry fetch
html = html.replace('''                const res = await fetch('/api/admin/recharges/retry', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${sessionStorage.getItem('admin-token')}`
                    },
                    body: JSON.stringify({ order_id: orderId })
                });''', '''                const res = await fetch('/api/admin/recharges/retry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ passcode: sessionStorage.getItem('admin-passcode'), order_id: orderId })
                });''')

# Fix logout
html = html.replace("sessionStorage.removeItem('admin-token');", "sessionStorage.removeItem('admin-passcode');")

with open('index.html', 'w') as f:
    f.write(html)
print("index.html fully patched with regex!")

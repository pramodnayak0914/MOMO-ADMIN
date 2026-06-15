import re

with open('index.html', 'r') as f:
    content = f.read()

# 1. Add Sidebar items
sidebar_orig = """                <div class="sidebar-item" data-tab="tab-analytics">
                    <i data-lucide="bar-chart-2" class="w-5 h-5"></i>
                    <span>Analytics Funnel</span>
                </div>"""
sidebar_new = """                <div class="sidebar-item" data-tab="tab-users">
                    <i data-lucide="users" class="w-5 h-5"></i>
                    <span>User Management</span>
                </div>
                <div class="sidebar-item" data-tab="tab-recharges">
                    <i data-lucide="smartphone" class="w-5 h-5"></i>
                    <span>Recharges</span>
                </div>
                <div class="sidebar-item" data-tab="tab-payments">
                    <i data-lucide="credit-card" class="w-5 h-5"></i>
                    <span>Payment Logs</span>
                </div>
                <div class="sidebar-item" data-tab="tab-fraud">
                    <i data-lucide="shield-alert" class="w-5 h-5 text-red-400"></i>
                    <span class="text-red-400">Fraud Controls</span>
                </div>
                <div class="sidebar-item" data-tab="tab-analytics">
                    <i data-lucide="bar-chart-2" class="w-5 h-5"></i>
                    <span>Analytics Funnel</span>
                </div>"""
content = content.replace(sidebar_orig, sidebar_new)

# 2. Add Tab Containers before TAB 2: ANALYTICS
tabs_orig = "            <!-- TAB 2: ANALYTICS -->"
tabs_new = """            <!-- NEW TAB: USERS -->
            <div id="tab-users" class="tab-content">
                <div class="glass-card rounded-xl overflow-hidden mb-8">
                    <div class="p-6 border-b border-white/10 flex justify-between items-center">
                        <h2 class="text-xl font-bold">User Management</h2>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse react-table">
                            <thead>
                                <tr class="text-slate-400 text-sm border-b border-white/10 bg-white/5">
                                    <th class="p-4 font-semibold">Phone</th>
                                    <th class="p-4 font-semibold">Status</th>
                                    <th class="p-4 font-semibold">Created At</th>
                                    <th class="p-4 font-semibold text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="users-table-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- NEW TAB: RECHARGES -->
            <div id="tab-recharges" class="tab-content">
                <div class="glass-card rounded-xl overflow-hidden mb-8">
                    <div class="p-6 border-b border-white/10 flex justify-between items-center">
                        <h2 class="text-xl font-bold">Recharge Management</h2>
                        <select id="recharge-filter" onchange="renderRecharges(window.globalData)" class="bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white outline-none">
                            <option value="ALL">All</option>
                            <option value="SUCCESS">Success</option>
                            <option value="PENDING">Pending</option>
                            <option value="FAILED">Failed</option>
                        </select>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse react-table">
                            <thead>
                                <tr class="text-slate-400 text-sm border-b border-white/10 bg-white/5">
                                    <th class="p-4 font-semibold">Order ID</th>
                                    <th class="p-4 font-semibold">User</th>
                                    <th class="p-4 font-semibold">Amount</th>
                                    <th class="p-4 font-semibold">Status</th>
                                    <th class="p-4 font-semibold">Date</th>
                                    <th class="p-4 font-semibold text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="recharges-table-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- NEW TAB: PAYMENTS -->
            <div id="tab-payments" class="tab-content">
                <div class="glass-card rounded-xl overflow-hidden mb-8">
                    <div class="p-6 border-b border-white/10">
                        <h2 class="text-xl font-bold">Payment Gateway Logs (Cashfree)</h2>
                        <p class="text-sm text-slate-400">Payment intent and settlement status synced with recharges.</p>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse react-table">
                            <thead>
                                <tr class="text-slate-400 text-sm border-b border-white/10 bg-white/5">
                                    <th class="p-4 font-semibold">Order ID</th>
                                    <th class="p-4 font-semibold">Gateway Status</th>
                                    <th class="p-4 font-semibold">Amount Settled</th>
                                    <th class="p-4 font-semibold">Created At</th>
                                </tr>
                            </thead>
                            <tbody id="payments-table-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- NEW TAB: FRAUD CONTROLS -->
            <div id="tab-fraud" class="tab-content">
                <div class="glass-card rounded-xl overflow-hidden mb-8 border border-red-500/20">
                    <div class="p-6 border-b border-white/10 bg-red-500/5 flex justify-between items-center">
                        <div>
                            <h2 class="text-xl font-bold text-red-400 flex items-center gap-2">
                                <i data-lucide="shield-alert" class="w-6 h-6"></i>
                                Auto-Fraud Alerts
                            </h2>
                            <p class="text-sm text-slate-400 mt-1">Signals caught by the backend rules engine (IP, Device, Rate limits).</p>
                        </div>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse react-table">
                            <thead>
                                <tr class="text-slate-400 text-sm border-b border-white/10 bg-white/5">
                                    <th class="p-4 font-semibold">Phone</th>
                                    <th class="p-4 font-semibold">Event Type</th>
                                    <th class="p-4 font-semibold">Trigger Details</th>
                                    <th class="p-4 font-semibold">IP / Device</th>
                                    <th class="p-4 font-semibold">Time</th>
                                </tr>
                            </thead>
                            <tbody id="fraud-table-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- TAB 2: ANALYTICS -->"""
content = content.replace(tabs_orig, tabs_new)

# 3. Replace the Overview Metrics
overview_orig = """                <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <div class="glass-card p-6 rounded-xl text-center">
                        <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Total Revenue</h3>
                        <div class="text-4xl font-bold text-primary" id="metric-revenue">₹0</div>
                    </div>
                    <div class="glass-card p-6 rounded-xl text-center">
                        <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Total Refunded</h3>
                        <div class="text-4xl font-bold text-red-400" id="metric-refunded">₹0</div>
                    </div>
                    <div class="glass-card p-6 rounded-xl text-center">
                        <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Success Trans.</h3>
                        <div class="text-4xl font-bold text-white" id="metric-tx-count">0</div>
                    </div>
                    <div class="glass-card p-6 rounded-xl text-center">
                        <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Total Plans</h3>
                        <div class="text-4xl font-bold text-accent" id="metric-plans-count">0</div>
                    </div>
                </div>"""
overview_new = """                <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <div class="glass-card p-6 rounded-xl text-center border-l-4 border-l-blue-500">
                        <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Today's Revenue</h3>
                        <div class="text-4xl font-bold text-white" id="metric-rev-today">₹0</div>
                        <p class="text-xs text-slate-500 mt-2">Monthly: <span id="metric-rev-month">₹0</span></p>
                    </div>
                    <div class="glass-card p-6 rounded-xl text-center border-l-4 border-l-emerald-500">
                        <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Recharges</h3>
                        <div class="text-4xl font-bold text-white" id="metric-recharge-total">0</div>
                        <p class="text-xs text-emerald-400 mt-2"><span id="metric-recharge-succ">0</span>% Success</p>
                    </div>
                    <div class="glass-card p-6 rounded-xl text-center border-l-4 border-l-purple-500">
                        <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">New Users</h3>
                        <div class="text-4xl font-bold text-white" id="metric-users-new">0</div>
                        <p class="text-xs text-purple-400 mt-2"><span id="metric-users-active">0</span> Active</p>
                    </div>
                    <div class="glass-card p-6 rounded-xl text-center border-l-4 border-l-amber-500">
                        <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Top Operator</h3>
                        <div class="text-2xl font-bold text-white truncate" id="metric-top-operator">N/A</div>
                        <p class="text-xs text-amber-400 mt-2 truncate" id="metric-top-plan">Plan: N/A</p>
                    </div>
                </div>"""
content = content.replace(overview_orig, overview_new)

with open('index.html', 'w') as f:
    f.write(content)

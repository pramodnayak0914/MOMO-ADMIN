import re

with open('index.html', 'r') as f:
    content = f.read()

sidebar_orig = """                <div class="sidebar-item" data-tab="tab-analytics">
                    <i data-lucide="bar-chart-2" class="w-5 h-5"></i>
                    <span>Analytics Funnel</span>
                </div>"""
sidebar_new = """                <div class="sidebar-item" data-tab="tab-marketing">
                    <i data-lucide="trending-up" class="w-5 h-5 text-amber-400"></i>
                    <span class="text-amber-400">Marketing Data</span>
                </div>
                <div class="sidebar-item" data-tab="tab-growth">
                    <i data-lucide="zap" class="w-5 h-5 text-emerald-400"></i>
                    <span class="text-emerald-400">Growth Engine</span>
                </div>
                <div class="sidebar-item" data-tab="tab-analytics">
                    <i data-lucide="bar-chart-2" class="w-5 h-5"></i>
                    <span>Analytics Funnel</span>
                </div>"""
if sidebar_orig in content:
    content = content.replace(sidebar_orig, sidebar_new)

tabs_orig = "            <!-- TAB 2: ANALYTICS -->"
tabs_new = """            <!-- NEW TAB: MARKETING DATA -->
            <div id="tab-marketing" class="tab-content">
                <div class="glass-card rounded-xl overflow-hidden mb-8">
                    <div class="p-6 border-b border-white/10">
                        <h2 class="text-xl font-bold text-amber-400 flex items-center gap-2">
                            <i data-lucide="trending-up" class="w-6 h-6"></i>
                            Marketing Data (Gold Mine)
                        </h2>
                        <p class="text-sm text-slate-400 mt-1">Discover popular plans, most recharged amounts, and user acquisition.</p>
                    </div>
                    <div class="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div class="bg-black/30 p-6 rounded-xl border border-white/5">
                            <h3 class="font-bold text-lg mb-4 text-white">Most Searched Plans</h3>
                            <ul id="marketing-popular-plans" class="space-y-3">
                                <!-- Populated by JS -->
                                <li class="text-slate-400 text-sm">Loading...</li>
                            </ul>
                        </div>
                        <div class="bg-black/30 p-6 rounded-xl border border-white/5">
                            <h3 class="font-bold text-lg mb-4 text-white">Most Recharged Amounts</h3>
                            <div class="flex flex-wrap gap-2" id="marketing-top-amounts">
                                <!-- Populated by JS -->
                                <span class="px-3 py-1 bg-white/10 rounded-full text-sm text-white">Loading...</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- NEW TAB: GROWTH ENGINE -->
            <div id="tab-growth" class="tab-content">
                <div class="glass-card rounded-xl overflow-hidden mb-8">
                    <div class="p-6 border-b border-white/10">
                        <h2 class="text-xl font-bold text-emerald-400 flex items-center gap-2">
                            <i data-lucide="zap" class="w-6 h-6"></i>
                            Growth Engine Controls
                        </h2>
                        <p class="text-sm text-slate-400 mt-1">Manage Referrals, Smart Cashback, and Loyalty Levels.</p>
                    </div>
                    
                    <div class="p-6 space-y-8">
                        <!-- Referral System -->
                        <div>
                            <h3 class="text-lg font-bold mb-4 text-white flex items-center gap-2">🤝 Referral System</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm text-slate-400 mb-1">Referrer Reward (₹)</label>
                                    <input type="number" id="growth-ref-referrer" class="w-full bg-black/50 border border-white/20 rounded p-2 text-white" value="20">
                                </div>
                                <div>
                                    <label class="block text-sm text-slate-400 mb-1">New User Reward (₹)</label>
                                    <input type="number" id="growth-ref-referred" class="w-full bg-black/50 border border-white/20 rounded p-2 text-white" value="20">
                                </div>
                            </div>
                        </div>

                        <hr class="border-white/10">

                        <!-- Smart Cashback -->
                        <div>
                            <h3 class="text-lg font-bold mb-4 text-white flex items-center gap-2">💸 Smart Cashback</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm text-slate-400 mb-1">First Recharge Cashback (₹)</label>
                                    <input type="number" id="growth-cb-first" class="w-full bg-black/50 border border-white/20 rounded p-2 text-white" value="0">
                                </div>
                                <div>
                                    <label class="block text-sm text-slate-400 mb-1">Weekend Extra Cashback (₹)</label>
                                    <input type="number" id="growth-cb-weekend" class="w-full bg-black/50 border border-white/20 rounded p-2 text-white" value="0">
                                </div>
                            </div>
                        </div>
                        
                        <hr class="border-white/10">
                        
                        <!-- Loyalty Levels -->
                        <div>
                            <h3 class="text-lg font-bold mb-4 text-white flex items-center gap-2">🏅 Loyalty Levels (Min Points)</h3>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                                    <label class="block text-sm text-slate-400 mb-1">Silver Threshold</label>
                                    <input type="number" id="growth-loy-silver" class="w-full bg-black/50 border border-white/20 rounded p-2 text-white" value="0">
                                </div>
                                <div>
                                    <label class="block text-sm text-slate-400 mb-1">Gold Threshold</label>
                                    <input type="number" id="growth-loy-gold" class="w-full bg-black/50 border border-white/20 rounded p-2 text-white" value="500">
                                </div>
                                <div>
                                    <label class="block text-sm text-slate-400 mb-1">Platinum Threshold</label>
                                    <input type="number" id="growth-loy-platinum" class="w-full bg-black/50 border border-white/20 rounded p-2 text-white" value="2000">
                                </div>
                            </div>
                        </div>
                        
                        <div class="pt-4">
                            <button onclick="saveGrowthSettings()" class="bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-2 px-6 rounded-lg transition-colors">
                                Save Growth Rules
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: ANALYTICS -->"""
if tabs_orig in content:
    content = content.replace(tabs_orig, tabs_new)

# JS updates for Marketing and Growth
js_orig = "            // 5. Analytics Funnel"
js_new = """            // 5. Marketing Data
            if (data.marketing_data) {
                const mk = data.marketing_data;
                const plansEl = document.getElementById('marketing-popular-plans');
                if (plansEl && mk.popular_plans && mk.popular_plans.length > 0) {
                    plansEl.innerHTML = '';
                    mk.popular_plans.forEach(p => {
                        plansEl.innerHTML += `<li class="flex justify-between items-center bg-white/5 p-3 rounded">
                            <span class="text-white font-medium">${p.operator} - ${p.circle}</span>
                            <span class="text-amber-400 text-sm bg-amber-400/10 px-2 py-1 rounded">Searched ${p.search_count} times</span>
                        </li>`;
                    });
                } else if(plansEl) {
                    plansEl.innerHTML = '<li class="text-slate-400 text-sm">Not enough data yet.</li>';
                }

                const amountsEl = document.getElementById('marketing-top-amounts');
                if (amountsEl && mk.top_amounts && mk.top_amounts.length > 0) {
                    amountsEl.innerHTML = '';
                    mk.top_amounts.forEach(a => {
                        amountsEl.innerHTML += `<span class="px-4 py-2 bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 rounded-full">₹${a.amount} <span class="text-xs text-white opacity-70 font-normal">(${a.count} recharges)</span></span>`;
                    });
                } else if(amountsEl) {
                    amountsEl.innerHTML = '<span class="px-3 py-1 bg-white/10 rounded-full text-sm text-white">Not enough data yet.</span>';
                }
            }

            // 6. Growth Rules (Prefill forms)
            if (data.growth_rules) {
                const gr = data.growth_rules;
                if(document.getElementById('growth-ref-referrer')) {
                    document.getElementById('growth-ref-referrer').value = gr.referral.referrer_reward || 20;
                    document.getElementById('growth-ref-referred').value = gr.referral.referred_reward || 20;
                    document.getElementById('growth-cb-first').value = gr.cashback.first_recharge || 0;
                    document.getElementById('growth-cb-weekend').value = gr.cashback.weekend || 0;
                    document.getElementById('growth-loy-silver').value = gr.loyalty.silver_min || 0;
                    document.getElementById('growth-loy-gold').value = gr.loyalty.gold_min || 500;
                    document.getElementById('growth-loy-platinum').value = gr.loyalty.platinum_min || 2000;
                }
            }

            // 7. Analytics Funnel"""
if js_orig in content:
    content = content.replace(js_orig, js_new)

js_func_orig = "        function refreshData() {"
js_func_new = """        window.saveGrowthSettings = function() {
            const payload = {
                passcode: gPasscode,
                referral_rules: {
                    referrer_reward: parseInt(document.getElementById('growth-ref-referrer').value),
                    referred_reward: parseInt(document.getElementById('growth-ref-referred').value)
                },
                cashback_rules: {
                    first_recharge: parseInt(document.getElementById('growth-cb-first').value),
                    weekend: parseInt(document.getElementById('growth-cb-weekend').value),
                    operator_specific: {}
                },
                loyalty_rules: {
                    silver_min: parseInt(document.getElementById('growth-loy-silver').value),
                    gold_min: parseInt(document.getElementById('growth-loy-gold').value),
                    platinum_min: parseInt(document.getElementById('growth-loy-platinum').value)
                }
            };
            fetch('/api/admin/growth/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(r=>r.json()).then(d=>{
                if(d.success) {
                    alert('Growth Rules saved successfully!');
                    refreshData();
                } else alert(d.error);
            });
        };

        function refreshData() {"""
if js_func_orig in content:
    content = content.replace(js_func_orig, js_func_new)

with open('index.html', 'w') as f:
    f.write(content)

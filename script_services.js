let currentWorkspaceData = null;
let currentWorkspaceModule = 'overview';

function loadServicesData() {
    const token = sessionStorage.getItem('admin-token');
    if(!token) return;
    
    // Read filter states
    const searchVal = document.getElementById('search-services').value.toLowerCase();
    const statusVal = document.getElementById('filter-service-status').value;
    
    let url = '/api/internal/services?limit=100';
    if(statusVal !== '') url += `&status=${statusVal}`;
    
    fetch(url, {
        headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(res => res.json())
    .then(data => {
        if(data.success) {
            let services = data.services || [];
            
            // Client-side search filter
            if(searchVal) {
                services = services.filter(s => 
                    (s.display_name && s.display_name.toLowerCase().includes(searchVal)) ||
                    (s.slug && s.slug.toLowerCase().includes(searchVal)) ||
                    (s.category && s.category.toLowerCase().includes(searchVal))
                );
            }
            
            renderServicesTable(services);
            updateServicesStats(services);
        }
    })
    .catch(err => console.error("Error loading services:", err));
}

function updateServicesStats(services) {
    const total = services.length;
    const active = services.filter(s => parseInt(s.status) === 1).length;
    
    document.getElementById('stat-total-services').innerText = total;
    document.getElementById('stat-active-services').innerText = active;
    
    const token = sessionStorage.getItem('admin-token');
    fetch('/api/internal/service-health', {
        headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(res => res.json())
    .then(data => {
        if(data.success && data.health) {
            document.getElementById('stat-total-operators').innerText = data.health.total_operators || 0;
        }
    })
    .catch(e => console.error(e));
}

function renderServicesTable(services) {
    const tbody = document.getElementById('services-table-body');
    tbody.innerHTML = '';
    
    if(services.length === 0) {
        tbody.innerHTML = `<tr><td colspan="2" class="text-center py-8 text-gray-500">No services found</td></tr>`;
        document.getElementById('services-pagination-info').innerText = 'Showing 0';
        return;
    }
    
    document.getElementById('services-pagination-info').innerText = `Showing ${services.length}`;
    
    services.forEach(s => {
        const isActive = parseInt(s.status) === 1;
        
        const tr = document.createElement('tr');
        tr.className = "border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer group focus-within:bg-white/5 outline-none";
        tr.dataset.serviceId = s.id;
        tr.tabIndex = 0;
        tr.setAttribute('role', 'button');
        tr.setAttribute('aria-label', `Select service ${s.display_name}`);
        tr.onclick = () => selectService(s.id);
        tr.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectService(s.id); } };
        
        tr.innerHTML = `
            <td class="py-3 px-3">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded bg-black/40 border border-white/5 shadow-inner flex items-center justify-center text-gray-400 group-hover:text-white group-focus:text-white transition-colors">
                        <i data-lucide="${s.icon_name || 'layers'}" class="w-4 h-4"></i>
                    </div>
                    <div>
                        <div class="font-medium text-gray-200 group-hover:text-white group-focus:text-white transition-colors">${s.display_name}</div>
                        <div class="text-[11px] font-medium text-gray-500 uppercase tracking-wider">${s.category || 'Other'}</div>
                    </div>
                </div>
            </td>
            <td class="py-3 px-3 text-center">
                <div class="w-2.5 h-2.5 rounded-full mx-auto ${isActive ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.4)]' : 'bg-gray-600 shadow-sm'}"></div>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    if(window.lucide) {
        lucide.createIcons();
    }
}

function selectService(serviceId) {
    const token = sessionStorage.getItem('admin-token');
    
    // Visual selection state
    document.querySelectorAll('#services-table-body tr').forEach(tr => {
        tr.classList.remove('bg-white/10', 'border-l-2', 'border-blue-500');
        if(tr.dataset.serviceId === serviceId) {
            tr.classList.add('bg-white/10', 'border-l-2', 'border-blue-500');
        }
    });

    // Show loading skeleton
    document.getElementById('workspace-empty').classList.add('hidden');
    document.getElementById('workspace-active').classList.remove('hidden');
    const loadingEl = document.getElementById('workspace-loading');
    if (loadingEl) loadingEl.classList.remove('hidden');
    
    fetch(`/api/internal/service-workspace/${serviceId}`, {
        headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(res => {
        if (!res.ok) throw new Error("API request failed");
        return res.json();
    })
    .then(data => {
        if(data.success && data.workspace) {
            currentWorkspaceData = data.workspace;
            if (loadingEl) loadingEl.classList.add('hidden');
            
            // Setup Workspace Header
            const svc = data.workspace.service;
            const ops = data.workspace.operators || [];
            const isActive = parseInt(svc.status) === 1;

            document.getElementById('ws-title').innerText = svc.display_name;
            
            const badge = document.getElementById('ws-badge-status');
            if (isActive) {
                badge.className = "px-2.5 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
                badge.innerText = "Active";
            } else {
                badge.className = "px-2.5 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wider bg-gray-500/10 text-gray-400 border border-gray-500/20";
                badge.innerText = "Inactive";
            }

            document.getElementById('ws-category').innerText = svc.category || 'Other';
            document.getElementById('ws-operator-count').innerHTML = `<i data-lucide="users" class="w-4 h-4"></i> ${ops.length} Operator${ops.length !== 1 ? 's' : ''}`;
            
            const updatedDate = new Date(svc.updated_at);
            document.getElementById('ws-last-updated').innerText = `Updated ${updatedDate.toLocaleDateString()}`;

            const iconEl = document.getElementById('ws-icon');
            iconEl.setAttribute('data-lucide', svc.icon_name || 'layers');
            
            if(window.lucide) lucide.createIcons();
            
            renderWorkspace();
        } else {
            throw new Error(data.error || "Failed to load workspace data");
        }
    })
    .catch(err => {
        console.error("Error loading workspace:", err);
        if (loadingEl) loadingEl.classList.add('hidden');
        if (window.showToast) {
            window.showToast("Unable to load workspace details at this time.", "error");
        } else {
            alert("Unable to load workspace details at this time.");
        }
    });
}

function switchWorkspaceTab(tabName) {
    currentWorkspaceModule = tabName;
    
    // Update Tab UI
    document.querySelectorAll('#workspace-tabs button').forEach(btn => {
        if(btn.dataset.module === tabName) {
            btn.className = "pb-3 border-b-2 border-blue-500 text-blue-400 transition-colors";
        } else {
            btn.className = "pb-3 border-b-2 border-transparent text-gray-400 hover:text-white transition-colors";
        }
    });
    
    renderWorkspace();
}

function renderWorkspace() {
    if(!currentWorkspaceData) return;
    
    const container = document.getElementById('workspace-module-container');
    const actionsContainer = document.getElementById('ws-header-actions');
    
    container.innerHTML = '';
    actionsContainer.innerHTML = '';
    
    if(currentWorkspaceModule === 'overview') {
        renderOverviewModule(container, actionsContainer);
    } else if(currentWorkspaceModule === 'operators') {
        renderOperatorsModule(container, actionsContainer);
    }
}

function renderOverviewModule(container, actionsContainer) {
    const svc = currentWorkspaceData.service;
    
    actionsContainer.innerHTML = `
        <button onclick="openServiceEditModalFromWorkspace()" class="px-5 py-2.5 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 hover:text-blue-300 rounded-xl text-sm font-semibold transition-colors flex items-center gap-2 border border-blue-500/20">
            <i data-lucide="edit-3" class="w-4 h-4"></i> Edit Summary
        </button>
    `;
    
    container.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 pb-8 pt-2">
            <div class="space-y-8">
                <div class="bg-black/20 p-6 rounded-2xl border border-white/5 shadow-sm">
                    <h4 class="text-xs font-semibold tracking-wider text-gray-500 uppercase mb-3">Internal Code</h4>
                    <p class="text-xl font-mono text-blue-400 bg-blue-500/10 px-4 py-2 rounded-xl inline-block border border-blue-500/10">${svc.internal_service_code}</p>
                </div>
                
                <div class="bg-black/20 p-6 rounded-2xl border border-white/5 shadow-sm">
                    <h4 class="text-xs font-semibold tracking-wider text-gray-500 uppercase mb-3">Description</h4>
                    <p class="text-gray-300 leading-relaxed text-sm">${svc.description || '<span class="text-gray-600 italic">No description provided</span>'}</p>
                </div>
            </div>
            
            <div class="space-y-8">
                <div class="grid grid-cols-2 gap-6">
                    <div class="bg-black/20 p-6 rounded-2xl border border-white/5 shadow-sm">
                        <div class="text-xs font-semibold tracking-wider text-gray-500 uppercase mb-2">Display Order</div>
                        <div class="text-3xl font-bold text-white">${svc.display_order}</div>
                    </div>
                    
                    <div class="bg-black/20 p-6 rounded-2xl border border-white/5 shadow-sm">
                        <div class="text-xs font-semibold tracking-wider text-gray-500 uppercase mb-2">Updated By</div>
                        <div class="text-lg font-medium text-gray-300 pt-1">${svc.updated_by || 'System User'}</div>
                    </div>
                </div>

                <div class="bg-black/20 p-6 rounded-2xl border border-white/5 shadow-sm">
                    <h4 class="text-xs font-semibold tracking-wider text-gray-500 uppercase mb-4">Features</h4>
                    <div class="flex flex-wrap gap-3">
                        ${parseInt(svc.featured) ? `<span class="px-3.5 py-1.5 rounded-lg text-xs font-bold border bg-indigo-500/10 text-indigo-400 border-indigo-500/20 shadow-sm flex items-center gap-1.5"><i data-lucide="star" class="w-3.5 h-3.5"></i> Featured</span>` : ''}
                        ${parseInt(svc.show_homepage) ? `<span class="px-3.5 py-1.5 rounded-lg text-xs font-bold border bg-purple-500/10 text-purple-400 border-purple-500/20 shadow-sm flex items-center gap-1.5"><i data-lucide="home" class="w-3.5 h-3.5"></i> Homepage</span>` : ''}
                        ${parseInt(svc.coming_soon) ? `<span class="px-3.5 py-1.5 rounded-lg text-xs font-bold border bg-amber-500/10 text-amber-400 border-amber-500/20 shadow-sm flex items-center gap-1.5"><i data-lucide="clock" class="w-3.5 h-3.5"></i> Coming Soon</span>` : ''}
                        ${(!parseInt(svc.featured) && !parseInt(svc.show_homepage) && !parseInt(svc.coming_soon)) ? '<span class="text-gray-600 text-sm italic">No special features active</span>' : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    if(window.lucide) lucide.createIcons();
}

function renderOperatorsModule(container, actionsContainer) {
    const ops = currentWorkspaceData.operators || [];
    
    let tableHtml = `
        <div class="overflow-x-auto pb-8 pt-2">
            <table class="w-full text-sm">
                <thead>
                    <tr class="text-left text-xs font-semibold tracking-wider text-gray-500 uppercase border-b border-white/10">
                        <th class="pb-4 pl-4">Operator</th>
                        <th class="pb-4">Internal Code</th>
                        <th class="pb-4 text-center">Priority</th>
                        <th class="pb-4 text-center">Providers</th>
                        <th class="pb-4 text-center">Status</th>
                        <th class="pb-4 pr-4 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-white/5">
    `;
    
    if(ops.length === 0) {
        tableHtml += `
            <tr>
                <td colspan="6" class="text-center py-16">
                    <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-white/5 text-gray-500 mb-3">
                        <i data-lucide="users" class="w-6 h-6"></i>
                    </div>
                    <p class="text-gray-400 font-medium">No operators mapped</p>
                    <p class="text-gray-600 text-xs mt-1">This service currently has no operators.</p>
                </td>
            </tr>
        `;
    } else {
        ops.forEach(op => {
            const isActive = parseInt(op.status) === 1;
            const provCount = parseInt(op.provider_count) || 0;
            
            tableHtml += `
                <tr class="hover:bg-white/[0.02] transition-colors group">
                    <td class="py-4 pl-4">
                        <div class="flex items-center gap-4">
                            <div class="w-10 h-10 rounded-xl bg-black/40 border border-white/5 shadow-inner flex items-center justify-center overflow-hidden transition-transform group-hover:scale-105">
                                ${op.logo_url ? `<img src="${op.logo_url}" class="w-full h-full object-cover">` : `<span class="text-xs font-bold text-gray-400">${op.display_name.substring(0,2).toUpperCase()}</span>`}
                            </div>
                            <div class="font-bold text-gray-200 tracking-wide">${op.display_name}</div>
                        </div>
                    </td>
                    <td class="py-4 text-gray-400 font-mono text-xs">${op.internal_operator_code}</td>
                    <td class="py-4 text-center text-gray-300 font-medium">${op.priority}</td>
                    <td class="py-4 text-center">
                        <div class="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-blue-500/10 text-blue-400 text-xs font-bold border border-blue-500/20" title="${op.linked_providers || 'None'}">
                            ${provCount}
                        </div>
                    </td>
                    <td class="py-4 text-center">
                        <span class="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider ${isActive ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-gray-500/10 text-gray-400 border border-gray-500/20'} shadow-sm">
                            ${isActive ? 'Active' : 'Inactive'}
                        </span>
                    </td>
                    <td class="py-4 pr-4 text-right">
                        <button onclick="openOperatorEditModal('${op.id}')" class="p-2 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 hover:text-blue-300 rounded-lg transition-all border border-blue-500/20 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-[#1a1a24]" aria-label="Edit Operator">
                            <i data-lucide="edit-2" class="w-4 h-4"></i>
                        </button>
                    </td>
                </tr>
            `;
        });
    }
    
    tableHtml += `</tbody></table></div>`;
    container.innerHTML = tableHtml;
    if(window.lucide) lucide.createIcons();
}

function openServiceEditModalFromWorkspace() {
    if(!currentWorkspaceData) return;
    openServiceEditModal(JSON.stringify(currentWorkspaceData.service));
}

function openOperatorEditModal(operatorId) {
    if(!currentWorkspaceData) return;
    const op = currentWorkspaceData.operators.find(o => o.id === operatorId);
    if(!op) return;
    
    document.getElementById('edit-operator-id').value = op.id;
    document.getElementById('edit-operator-name').value = op.display_name || '';
    document.getElementById('edit-operator-logo').value = op.logo_url || '';
    document.getElementById('edit-operator-priority').value = op.priority || 0;
    document.getElementById('edit-operator-status').value = op.status;
    
    const modal = document.getElementById('edit-operator-modal');
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modal.querySelector('div').classList.remove('scale-95');
    }, 10);
}

function closeOperatorModal() {
    const modal = document.getElementById('edit-operator-modal');
    modal.classList.add('opacity-0');
    modal.querySelector('div').classList.add('scale-95');
    setTimeout(() => {
        modal.classList.add('hidden');
    }, 300);
}

function saveOperator() {
    const id = document.getElementById('edit-operator-id').value;
    if(!id) return;
    
    const data = {
        display_name: document.getElementById('edit-operator-name').value,
        logo_url: document.getElementById('edit-operator-logo').value,
        priority: parseInt(document.getElementById('edit-operator-priority').value) || 0,
        status: parseInt(document.getElementById('edit-operator-status').value)
    };
    
    const token = sessionStorage.getItem('admin-token');
    fetch(`/api/internal/operator/${id}`, {
        method: 'PUT',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(res => {
        if(res.success) {
            closeOperatorModal();
            // Reload the workspace data seamlessly
            if(currentWorkspaceData) {
                selectService(currentWorkspaceData.service.id);
            }
            if(window.showToast) window.showToast("Operator updated successfully", "success");
            else alert("Operator updated successfully");
        } else {
            if(window.showToast) window.showToast("Error: " + res.error, "error");
            else alert("Error: " + res.error);
        }
    })
    .catch(err => console.error(err));
}

// ----------------------------------------------------------------------
// Existing Service Modal Logic (Reused)
// ----------------------------------------------------------------------

function openServiceEditModal(serviceStr) {
    let service;
    try {
        service = JSON.parse(serviceStr);
    } catch(e) { return; }
    
    document.getElementById('edit-service-id').value = service.id;
    document.getElementById('edit-service-name').value = service.display_name || '';
    document.getElementById('edit-service-desc').value = service.description || '';
    document.getElementById('edit-service-category').value = service.category || 'other';
    document.getElementById('edit-service-icon').value = service.icon_name || 'layers';
    document.getElementById('edit-service-order').value = service.display_order || 0;
    document.getElementById('edit-service-status').value = service.status;
    
    document.getElementById('edit-service-featured').checked = (parseInt(service.featured) === 1);
    document.getElementById('edit-service-homepage').checked = (parseInt(service.show_homepage) === 1);
    document.getElementById('edit-service-comingsoon').checked = (parseInt(service.coming_soon) === 1);
    
    const modal = document.getElementById('edit-service-modal');
    modal.classList.remove('hidden');
    // Animate in
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modal.querySelector('div').classList.remove('scale-95');
    }, 10);
    
    // Setup unsaved changes detection
    window._serviceInitialState = getServiceFormState();
    window._serviceIsDirty = false;
    
    const inputs = modal.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.addEventListener('change', markServiceDirty);
        input.addEventListener('keyup', markServiceDirty);
    });
}

function getServiceFormState() {
    return JSON.stringify({
        name: document.getElementById('edit-service-name').value,
        desc: document.getElementById('edit-service-desc').value,
        cat: document.getElementById('edit-service-category').value,
        icon: document.getElementById('edit-service-icon').value,
        order: document.getElementById('edit-service-order').value,
        status: document.getElementById('edit-service-status').value,
        feat: document.getElementById('edit-service-featured').checked,
        home: document.getElementById('edit-service-homepage').checked,
        soon: document.getElementById('edit-service-comingsoon').checked
    });
}

function markServiceDirty() {
    if(getServiceFormState() !== window._serviceInitialState) {
        window._serviceIsDirty = true;
    } else {
        window._serviceIsDirty = false;
    }
}

function closeServiceModal() {
    if(window._serviceIsDirty) {
        if(!confirm("You have unsaved changes. Discard them?")) {
            return;
        }
    }
    
    const modal = document.getElementById('edit-service-modal');
    modal.classList.add('opacity-0');
    modal.querySelector('div').classList.add('scale-95');
    setTimeout(() => {
        modal.classList.add('hidden');
    }, 300);
}

function saveService() {
    const id = document.getElementById('edit-service-id').value;
    if(!id) return;
    
    const data = {
        display_name: document.getElementById('edit-service-name').value,
        description: document.getElementById('edit-service-desc').value,
        category: document.getElementById('edit-service-category').value,
        icon_name: document.getElementById('edit-service-icon').value,
        display_order: parseInt(document.getElementById('edit-service-order').value) || 0,
        status: parseInt(document.getElementById('edit-service-status').value),
        featured: document.getElementById('edit-service-featured').checked ? 1 : 0,
        show_homepage: document.getElementById('edit-service-homepage').checked ? 1 : 0,
        coming_soon: document.getElementById('edit-service-comingsoon').checked ? 1 : 0
    };
    
    const token = sessionStorage.getItem('admin-token');
    fetch(`/api/internal/service/${id}`, {
        method: 'PUT',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(res => {
        if(res.success) {
            window._serviceIsDirty = false;
            closeServiceModal();
            loadServicesData();
            // Also refresh workspace if it was open for this service
            if(currentWorkspaceData && currentWorkspaceData.service.id === id) {
                selectService(id);
            }
            if(window.showToast) window.showToast("Service updated successfully", "success");
            else alert("Service updated successfully");
        } else {
            if(window.showToast) window.showToast("Error: " + res.error, "error");
            else alert("Error: " + res.error);
        }
    })
    .catch(err => console.error(err));
}

function syncServices() {
    if(!confirm("Force synchronization with KwikAPI? This will update operators and services.")) return;
    
    const btn = document.getElementById('btn-sync-services');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-8 h-8 mb-2 animate-spin"></i><span class="font-medium">Syncing...</span>`;
    if(window.lucide) lucide.createIcons();
    
    const token = sessionStorage.getItem('admin-token');
    fetch('/api/internal/service-sync', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify({ provider: 'kwik' })
    })
    .then(res => res.json())
    .then(data => {
        btn.innerHTML = originalHtml;
        if(window.lucide) lucide.createIcons();
        
        if(data.success) {
            if(window.showToast) window.showToast("Sync completed successfully", "success");
            else alert("Sync completed");
            loadServicesData();
        } else {
            if(window.showToast) window.showToast("Sync failed: " + data.error, "error");
            else alert("Sync failed: " + data.error);
        }
    })
    .catch(err => {
        btn.innerHTML = originalHtml;
        if(window.lucide) lucide.createIcons();
        if(window.showToast) window.showToast("Sync error: " + err.message, "error");
        else alert("Sync error: " + err.message);
    });
}

// Hook into the tab switching or initialization
document.addEventListener('DOMContentLoaded', () => {
    // Listen to tab clicks to load data when Services tab is opened
    const tabs = document.querySelectorAll('.sidebar-item[data-tab]');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if(tab.getAttribute('data-tab') === 'tab-services') {
                loadServicesData();
            }
        });
    });
    
    // Add event listeners for filters
    const searchInput = document.getElementById('search-services');
    if(searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            if(e.key === 'Enter') loadServicesData();
        });
        searchInput.addEventListener('input', () => {
            // Debounce or just load
            clearTimeout(window._searchTimer);
            window._searchTimer = setTimeout(loadServicesData, 500);
        });
    }
    
    const statusFilter = document.getElementById('filter-service-status');
    if(statusFilter) {
        statusFilter.addEventListener('change', loadServicesData);
    }
});

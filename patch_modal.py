with open('index.html', 'r') as f:
    content = f.read()

# Replace native alert/confirm with custom modal logic
custom_modal_html = """
    <!-- Custom Modal Overlay -->
    <div id="custom-modal" class="hidden absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
        <div class="bg-[#1a1a24] border border-red-500/30 rounded-xl max-w-md w-full shadow-2xl overflow-hidden">
            <div class="p-4 border-b border-white/5 bg-red-500/10 flex items-center gap-3">
                <h3 id="modal-title" class="text-red-400 font-bold flex items-center gap-2">⚠️ Confirm Action</h3>
            </div>
            <div class="p-6">
                <p id="modal-message" class="text-slate-300 text-sm whitespace-pre-wrap mb-6 leading-relaxed"></p>
                <div class="flex gap-3 justify-end" id="modal-buttons">
                    <!-- Buttons injected here -->
                </div>
            </div>
        </div>
    </div>
"""

# Insert modal HTML just inside the react-tickets-root wrapper
content = content.replace("let html = `\n                <div class=\"glass-card rounded-xl overflow-hidden relative\" style=\"min-height: 400px;\">",
    "let html = `\n                <div class=\"glass-card rounded-xl overflow-hidden relative\" style=\"min-height: 400px;\">" + custom_modal_html)

# Add modal JS functions
modal_js = """
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
"""

content = content.replace('function fetchTickets() {', modal_js + '\n        function fetchTickets() {')

# Replace confirm and alert in updateTicketStatus
old_update = """
        function updateTicketStatus(ticketId, newStatus) {
            if(newStatus === 'REFUNDED') {
                if(!confirm("Are you sure you want to refund this ticket?\\nThis cannot be undone!")) {
                    renderTicketsUI(); // Reset dropdown
                    return;
                }
            }
            
            fetch('/api/support/tickets/' + ticketId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    if(data.refund_message) alert("Refund: " + data.refund_message);
                    fetchTickets();
                } else {
                    alert("Failed: " + data.error);
                    fetchTickets();
                }
            })
            .catch(err => {
                alert("Error: " + err.message);
            });
        }
"""

new_update = """
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
                    "Are you sure you want to refund this ticket?\\n\\nThis will instantly return the money to the customer's bank account and CANNOT be undone!", 
                    true, 
                    `processTicketStatusUpdate('${ticketId}', '${newStatus}')`
                );
                return;
            }
            processTicketStatusUpdate(ticketId, newStatus);
        }
"""

content = content.replace(old_update.strip(), new_update.strip())

with open('index.html', 'w') as f:
    f.write(content)

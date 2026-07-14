with open("/Users/pramod2.nayak/MOMO-ADMIN/script_1.js", "a") as f:
    f.write("""

// Notification Preferences
document.addEventListener('DOMContentLoaded', () => {
    const savePrefsBtn = document.getElementById('save-notification-prefs');
    const savePrefsMsg = document.getElementById('save-prefs-msg');
    
    if (savePrefsBtn) {
        savePrefsBtn.addEventListener('click', () => {
            const originalText = savePrefsBtn.innerText;
            savePrefsBtn.innerText = 'Saving...';
            
            // Mock API call
            setTimeout(() => {
                savePrefsBtn.innerText = originalText;
                savePrefsMsg.classList.remove('hidden');
                
                setTimeout(() => {
                    savePrefsMsg.classList.add('hidden');
                }, 3000);
            }, 800);
        });
    }
});
""")

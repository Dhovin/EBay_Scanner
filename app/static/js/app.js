// JavaScript helpers for eBay Deal Monitor

document.addEventListener('DOMContentLoaded', () => {
    // Update local system clock in footer if present
    const timeEl = document.getElementById('system-time');
    if (timeEl) {
        const updateClock = () => {
            const now = new Date();
            timeEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        };
        updateClock();
        setInterval(updateClock, 1000);
    }
});

// Close modal on Escape key press
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('rule-edit-modal');
        if (modal) {
            modal.remove();
        }
    }
});

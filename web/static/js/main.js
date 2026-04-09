/* =============================================
   Production Manager — Global JS
   ============================================= */

// Toast Notifications JS
function showToast(message, type = 'info') {
    // Check if toast container exists
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.position = 'fixed';
        container.style.bottom = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.gap = '10px';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Icon based on type
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    if (type === 'warning') icon = '⚠️';

    toast.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
            <span>${icon}</span>
            <span style="flex:1;">${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" style="background:none; border:none; color:inherit; cursor:pointer;">✖</button>
        </div>
    `;

    // Basic styling (can be overridden in CSS)
    toast.style.minWidth = '250px';
    toast.style.padding = '12px 16px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)';
    toast.style.color = '#fff';
    toast.style.animation = 'slideInRight 0.3s ease-out forwards';
    toast.style.fontWeight = '500';

    if (type === 'success') toast.style.backgroundColor = '#10b981';
    else if (type === 'error') toast.style.backgroundColor = '#ef4444';
    else if (type === 'warning') toast.style.backgroundColor = '#f59e0b';
    else toast.style.backgroundColor = '#6366f1'; // info

    container.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.animation = 'fadeOut 0.3s ease-out forwards';
            setTimeout(() => {
                if (toast.parentElement) toast.remove();
            }, 300);
        }
    }, 5000);
}

// Override default window.alert optionally
const originalAlert = window.alert;
window.alert = function(message) {
    if (message.toString().toLowerCase().includes('ошибка')) {
        showToast(message, 'error');
    } else if (message.toString().toLowerCase().includes('успех') || message.toString().toLowerCase().includes('удалено')) {
        showToast(message, 'success');
    } else {
        showToast(message, 'info');
    }
};

// Animation keyframes injected dynamically
const style = document.createElement('style');
style.innerHTML = `
@keyframes slideInRight {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}
@keyframes fadeOut {
    from { opacity: 1; }
    to { opacity: 0; }
}
`;
document.head.appendChild(style);

// Sidebar toggle for mobile
document.addEventListener('DOMContentLoaded', () => {
    // Mobile Nav Toggle setup
    if(window.innerWidth <= 768) {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            const toggleBtn = document.createElement('button');
            toggleBtn.innerHTML = '☰';
            toggleBtn.style.position = 'fixed';
            toggleBtn.style.top = '10px';
            toggleBtn.style.left = '10px';
            toggleBtn.style.zIndex = '1001';
            toggleBtn.style.background = 'var(--primary)';
            toggleBtn.style.color = '#fff';
            toggleBtn.style.border = 'none';
            toggleBtn.style.padding = '8px 12px';
            toggleBtn.style.borderRadius = '4px';
            toggleBtn.style.cursor = 'pointer';
            
            document.body.appendChild(toggleBtn);
            
            toggleBtn.addEventListener('click', () => {
                const currentLeft = parseInt(window.getComputedStyle(sidebar).left);
                if (currentLeft < 0) {
                    sidebar.style.left = '0px';
                } else {
                    sidebar.style.left = '-260px';
                }
            });
        }
    }
});

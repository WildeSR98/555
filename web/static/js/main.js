/* =============================================
   Production Manager — Global JS
   ============================================= */

// Toast Notifications JS
function showToast(message, type = 'info') {
    // Format message if it's an object (common for API errors)
    let displayMessage = message;
    if (typeof message === 'object' && message !== null) {
        if (message.detail) {
            if (Array.isArray(message.detail)) {
                displayMessage = message.detail.map(d => d.msg || JSON.stringify(d)).join(', ');
            } else if (typeof message.detail === 'string') {
                displayMessage = message.detail;
            } else {
                displayMessage = JSON.stringify(message.detail);
            }
        } else if (message.message) {
            displayMessage = message.message;
        } else {
            displayMessage = JSON.stringify(message);
        }
    }

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
            <span style="flex:1;">${escapeHTML(displayMessage)}</span>
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
    let msgStr = '';
    if (typeof message === 'object' && message !== null) {
        msgStr = JSON.stringify(message).toLowerCase();
    } else {
        msgStr = String(message).toLowerCase();
    }

    if (msgStr.includes('ошибка') || msgStr.includes('error') || msgStr.includes('invalid') || msgStr.includes('failed')) {
        showToast(message, 'error');
    } else if (msgStr.includes('успех') || msgStr.includes('success') || msgStr.includes('удалено') || msgStr.includes('ok')) {
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

    // CSRF Global Fetch Handler
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
        let [resource, config] = args;
        
        // Ensure config exists
        if (!config) config = {};
        if (!config.headers) config.headers = {};

        const method = (config.method || 'GET').toUpperCase();
        const safeMethods = ['GET', 'HEAD', 'OPTIONS', 'TRACE'];

        if (!safeMethods.includes(method)) {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
            if (csrfToken) {
                // If headers is Headers object
                if (config.headers instanceof Headers) {
                    config.headers.set('X-CSRF-Token', csrfToken);
                } else {
                    config.headers['X-CSRF-Token'] = csrfToken;
                }
            }
        }
        
        return originalFetch(resource, config);
    };

    // Health Monitoring
    const checkHealth = async () => {
        const dot = document.getElementById('health-dot');
        const text = document.getElementById('health-text');
        if (!dot || !text) return;

        try {
            const resp = await fetch('/api/health');
            const data = await resp.json();
            
            if (data.overall === 'OK') {
                dot.style.background = '#10b981'; // Green
                text.textContent = 'Система: ОК';
            } else if (data.overall === 'CRITICAL' || data.database === 'ERROR') {
                dot.style.background = '#ef4444'; // Red
                text.textContent = 'Система: ОШИБКА';
            } else if (data.storage === 'LOW_SPACE') {
                dot.style.background = '#f59e0b'; // Yellow
                text.textContent = 'Система: МАЛО МЕСТА';
            }
        } catch (e) {
            dot.style.background = '#94a3b8'; // Grey
            text.textContent = 'Система: НЕВЕРНО';
        }
    };

    if (document.getElementById('health-indicator')) {
        checkHealth();
        setInterval(checkHealth, 60000); // Раз в минуту
    }
});

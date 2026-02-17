/**
 * CPR Tracking System - JavaScript Initialization
 * Ember Dark Theme
 */

// ===== Chart.js Warm Dark Theme Defaults =====
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#a8a0a0';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.10)';
    Chart.defaults.plugins.legend.labels.color = '#a8a0a0';
    Chart.defaults.plugins.tooltip.backgroundColor = '#3e3a46';
    Chart.defaults.plugins.tooltip.titleColor = '#ede8e6';
    Chart.defaults.plugins.tooltip.bodyColor = '#a8a0a0';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.14)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.scale.grid = Chart.defaults.scale.grid || {};
    Chart.defaults.scale.grid.color = 'rgba(255, 255, 255, 0.08)';
}

// ===== Toast Notifications =====
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');

    const baseClasses = 'px-4 py-3 rounded-[6px] shadow-lg text-sm font-medium transform transition-all duration-300';
    const typeClasses = {
        success: 'bg-green-900/20 text-green-400 border border-green-500/30',
        error: 'bg-red-900/20 text-red-400 border border-red-500/30',
        info: 'bg-blue-900/20 text-blue-400 border border-blue-500/30',
        warning: 'bg-amber-900/20 text-amber-400 border border-amber-500/30'
    };

    toast.className = `${baseClasses} ${typeClasses[type] || typeClasses.info} translate-x-full`;
    toast.textContent = message;

    container.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.remove('translate-x-full');
    });

    setTimeout(() => {
        toast.classList.add('translate-x-full');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
}

window.showToast = showToast;

// ===== Modal Helpers =====
function closeModal() {
    const container = document.getElementById('modal-container');
    if (container) {
        container.innerHTML = '';
    }
}

window.closeModal = closeModal;

// ===== Utility Functions =====
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

window.debounce = debounce;
window.formatDate = formatDate;

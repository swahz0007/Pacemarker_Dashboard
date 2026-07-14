import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);
window.Chart = Chart;

function activatePublicDemo() {
    const app = document.getElementById('appContainer');
    if (app) app.hidden = false;

    const isLocalMode = window.location.protocol === 'file:'
        || window.location.hostname === 'localhost'
        || window.location.hostname === '127.0.0.1';

    const state = {
        authenticated: true,
        user: null,
        mode: isLocalMode ? 'offline-local' : 'public-demo',
        logout: async () => state,
    };

    const userLabel = document.querySelector('.auth-user-label');
    if (userLabel) {
        userLabel.textContent = isLocalMode ? '本地离线模式' : '公开脱敏演示';
    }

    window.PM_AUTH = state;
    window.dispatchEvent(new CustomEvent('pm:auth-ready', { detail: state }));
    return state;
}

window.PM_AUTH_READY = new Promise((resolve) => {
    const boot = () => resolve(activatePublicDemo());
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot, { once: true });
    } else {
        boot();
    }
});

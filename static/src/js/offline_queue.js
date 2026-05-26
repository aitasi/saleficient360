/** Lightweight offline indicator and queue helper for Field Sales dashboards. */
(function () {
    'use strict';
    const KEY = 'field_sales_route_plan.offline_queue';
    window.FieldSalesOfflineQueue = {
        add(item) {
            const queue = JSON.parse(localStorage.getItem(KEY) || '[]');
            queue.push(Object.assign({created_at: new Date().toISOString(), state: 'pending'}, item || {}));
            localStorage.setItem(KEY, JSON.stringify(queue));
            window.dispatchEvent(new CustomEvent('field_sales_offline_queue_changed', {detail: {count: queue.length}}));
        },
        list() { return JSON.parse(localStorage.getItem(KEY) || '[]'); },
        clear() { localStorage.removeItem(KEY); window.dispatchEvent(new CustomEvent('field_sales_offline_queue_changed', {detail: {count: 0}})); },
        count() { return this.list().length; },
    };
    function updateBodyState() {
        document.body.classList.toggle('o_field_sales_offline', !navigator.onLine);
        document.body.classList.toggle('o_field_sales_online', navigator.onLine);
    }
    window.addEventListener('online', updateBodyState);
    window.addEventListener('offline', updateBodyState);
    document.addEventListener('DOMContentLoaded', updateBodyState);
})();

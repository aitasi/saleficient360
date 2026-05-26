/** @odoo-module **/

import { registry } from "@web/core/registry";

async function collectDeviceStatus() {
    const nav = window.navigator || {};
    const connection = nav.connection || nav.mozConnection || nav.webkitConnection || {};
    const status = {
        battery_supported: false,
        battery_level: 0,
        battery_charging: false,
        network_online: nav.onLine !== false,
        network_type: connection.type || "",
        effective_type: connection.effectiveType || "",
        downlink_mbps: connection.downlink || 0,
        rtt_ms: connection.rtt || 0,
        save_data: Boolean(connection.saveData),
        page_url: window.location.href,
        user_agent: nav.userAgent || "",
        platform: nav.platform || "",
    };
    if (nav.getBattery) {
        try {
            const battery = await nav.getBattery();
            status.battery_supported = true;
            status.battery_level = Math.round((battery.level || 0) * 10000) / 100;
            status.battery_charging = Boolean(battery.charging);
        } catch (e) {
            status.battery_supported = false;
        }
    }
    return status;
}

async function sendDeviceStatus(env) {
    try {
        const rpc = env.services.rpc;
        if (!rpc) { return; }
        const payload = await collectDeviceStatus();
        const result = await rpc("/field_sales/device/status", payload);
        window.fieldSalesLastDeviceStatus = result;
        window.dispatchEvent(new CustomEvent("field_sales_device_status", { detail: result }));
    } catch (e) {
        // Silent by design: device monitoring should never disturb field users.
    }
}

const service = {
    start(env) {
        const run = () => sendDeviceStatus(env);
        setTimeout(run, 2500);
        window.addEventListener("online", run);
        window.addEventListener("offline", run);
        const nav = window.navigator || {};
        const connection = nav.connection || nav.mozConnection || nav.webkitConnection;
        if (connection && connection.addEventListener) {
            connection.addEventListener("change", run);
        }
        window.setInterval(run, 2 * 60 * 1000);
        document.addEventListener("visibilitychange", () => { if (!document.hidden) { run(); } });
        window.fieldSalesSendDeviceStatus = run;
    },
};

registry.category("services").add("field_sales_device_status", service);

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FieldSimpleMode extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, data: {}, device: {}, date_from: this._todayISO(), date_to: this._todayISO(), showMorningBriefing: false, sections: { actions: true, period: true, today: true, mtd: false, ytd: false, overview: false, targets: false, alerts: false, assistant: true } });
        this._isMounted = true;
        this._deviceListener = (ev) => {
            if (this._isMounted && ev.detail && ev.detail.ok) {
                this.state.device = ev.detail;
            }
        };
        onWillUnmount(() => {
            this._isMounted = false;
            window.removeEventListener('field_sales_device_status', this._deviceListener);
        });
        onMounted(async () => {
            window.addEventListener('field_sales_device_status', this._deviceListener);
            await this.load();
            await this.refreshDeviceStatus();
            this._maybeShowMorningBriefing();
            this._maybeStartFirstTimeTour();
        });
    }

    _todayISO() { return new Date().toISOString().slice(0, 10); }

    _morningBriefingKey() {
        const userId = ((this.state.data || {}).user || {}).id || 'user';
        return `field_sales_morning_briefing_seen_${userId}_${this._todayISO()}`;
    }
    _maybeShowMorningBriefing() {
        try {
            if ((this.state.data || {}).morning_briefing && !localStorage.getItem(this._morningBriefingKey())) {
                this.state.showMorningBriefing = true;
                localStorage.setItem(this._morningBriefingKey(), '1');
            }
        } catch (e) {
            if ((this.state.data || {}).morning_briefing) { this.state.showMorningBriefing = true; }
        }
    }
    openMorningBriefing() {
        if ((this.state.data || {}).morning_briefing) { this.state.showMorningBriefing = true; }
    }
    closeMorningBriefing() {
        this.state.showMorningBriefing = false;
    }
    setDateFrom(ev) { this.state.date_from = ev.target.value || this._todayISO(); }
    setDateTo(ev) { this.state.date_to = ev.target.value || this.state.date_from || this._todayISO(); }
    async applyDateFilter() { await this.load(); }
    async resetDateFilter() { this.state.date_from = this._todayISO(); this.state.date_to = this._todayISO(); await this.load(); }

    toggleSection(name) {
        this.state.sections[name] = !this.state.sections[name];
    }

    _tourKey() {
        return "field_sales_route_plan_tour_seen_field_user_v93";
    }
    _maybeStartFirstTimeTour() {
        setTimeout(() => {
            if (!this._isMounted) { return; }
            try {
                if (!localStorage.getItem(this._tourKey())) {
                    this.startTour(true);
                }
            } catch (e) {}
        }, 700);
    }
    startTour(auto=false) {
        const steps = [
            { selector: ".fsrp-simple-hero", title: "Welcome to My Field Work", text: "This is your daily mobile workbench for planning, visiting, selling, navigation, and follow-up." },
            { selector: ".fsrp-action-board", title: "Quick Actions", text: "Use these buttons to create a route plan, start or continue visits, open the map, and ask the sales assistant." },
            { selector: ".fsrp-action-primary", title: "Start / New Route Plan", text: "Create a new route plan first, then use Start / Continue to open the next client visit." },
            { selector: ".fsrp-live-kpi-strip", title: "Today’s KPI Summary", text: "Track visit progress, productivity, targets, and POS settlement performance for the day." },
            { selector: ".fsrp-section-toggle", title: "Collapsible Sections", text: "Open only the information you need. This keeps the mobile screen clean and fast." },
            { selector: ".fsrp-modern-workbench", title: "Sales Assistant", text: "Review the next client, client health, and suggested actions before you visit." },
        ];
        this._runGuidedTour(steps, auto, this._tourKey());
    }
    _runGuidedTour(steps, auto, storageKey) {
        const old = document.querySelector(".fsrp-tour-overlay");
        if (old) { old.remove(); }
        let index = 0;
        const overlay = document.createElement("div");
        overlay.className = "fsrp-tour-overlay";
        overlay.innerHTML = `<div class="fsrp-tour-dim"></div><div class="fsrp-tour-card"><div class="fsrp-tour-step"></div><h3></h3><p></p><div class="fsrp-tour-actions"><button class="btn btn-link fsrp-tour-skip">Skip</button><button class="btn btn-primary fsrp-tour-next">Next</button></div></div>`;
        document.body.appendChild(overlay);
        const card = overlay.querySelector(".fsrp-tour-card");
        const dim = overlay.querySelector(".fsrp-tour-dim");
        const stepNo = overlay.querySelector(".fsrp-tour-step");
        const title = overlay.querySelector("h3");
        const text = overlay.querySelector("p");
        const nextBtn = overlay.querySelector(".fsrp-tour-next");
        const skipBtn = overlay.querySelector(".fsrp-tour-skip");
        const finish = () => {
            document.querySelectorAll(".fsrp-tour-highlight").forEach(el => el.classList.remove("fsrp-tour-highlight"));
            try { localStorage.setItem(storageKey, "1"); } catch (e) {}
            overlay.remove();
        };
        const show = () => {
            document.querySelectorAll(".fsrp-tour-highlight").forEach(el => el.classList.remove("fsrp-tour-highlight"));
            const step = steps[index];
            let target = document.querySelector(step.selector);
            if (!target) {
                index += 1;
                if (index >= steps.length) { finish(); }
                else { show(); }
                return;
            }
            target.classList.add("fsrp-tour-highlight");
            target.scrollIntoView({ behavior: "smooth", block: "center" });
            title.textContent = step.title;
            text.textContent = step.text;
            stepNo.textContent = `Step ${index + 1} of ${steps.length}`;
            nextBtn.textContent = index === steps.length - 1 ? "Finish" : "Next";
            const rect = target.getBoundingClientRect();
            const top = Math.min(window.innerHeight - 230, Math.max(20, rect.bottom + 12));
            const left = Math.min(window.innerWidth - 360, Math.max(12, rect.left));
            card.style.top = `${top}px`;
            card.style.left = `${left}px`;
        };
        nextBtn.onclick = () => { index += 1; if (index >= steps.length) { finish(); } else { show(); } };
        skipBtn.onclick = finish;
        dim.onclick = finish;
        show();
    }

    async load() {
        if (!this._isMounted) { return; }
        this.state.loading = true;
        try {
            const data = await this.rpc("/field_sales/simple_mode/data", { date_from: this.state.date_from, date_to: this.state.date_to });
            if (!this._isMounted) { return; }
            this.state.data = data || {};
            this._maybeShowMorningBriefing();
        } finally {
            if (this._isMounted) { this.state.loading = false; }
        }
    }
    async startMyDay() {
        const res = await this.rpc("/field_sales/simple_mode/start", { plan_id: this.state.data.plan_id || false });
        if (!res.ok) { this.notification.add(res.error || "Could not start day", { type: "danger" }); return; }
        await this.action.doAction(res.action);
    }
    async nextClient() { await this.startMyDay(); }
    async openClientMap() { await this.action.doAction("field_sales_route_plan.action_client_map"); }
    async openQuickSalesOrder() {
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "field_sales_route_plan.sale_terminal",
            name: "Van Sales",
            target: "current",
            context: { quick_sale_unrestricted: true },
        });
    }
    async openDeliveryMode() { await this.action.doAction("field_sales_route_plan.action_delivery_app_mode"); }
    async openLiveNavigation() {
        await this.action.doAction("field_sales_route_plan.action_client_map", {
            additionalContext: { fsrp_navigation_mode: true }
        });
    }
    async askSalesAssistant() {
        const lineId = this.state.data.next_line_id || false;
        const res = await this.rpc("/field_sales/sales_assistant/context", { visit_id: false, partner_id: this.state.data.next_partner_id || false });
        if (res && res.ok) {
            const msg = (res.messages || []).join("\n") || "No assistant suggestion yet.";
            this.notification.add(msg, { title: "Sales Assistant: " + (res.client || "Client"), type: "info", sticky: true });
        } else {
            this.notification.add((res && res.error) || "No client selected for assistant.", { type: "warning" });
        }
    }

    async openRequests() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Requests",
            res_model: "field.sales.commercial.request",
            views: [[false, "kanban"], [false, "tree"], [false, "form"]],
            view_mode: "kanban,tree,form",
            target: "current",
            context: {
                search_default_my_requests: 1,
                default_requested_by_id: (((this.state.data || {}).user || {}).id) || false,
            },
        });
    }
    async createRoutePlan() {
        await this.action.doAction("field_sales_route_plan.action_quick_route_plan_wizard", {
            onClose: async () => { await this.load(); },
        });
    }
    async refreshDeviceStatus() {
        try {
            if (window.fieldSalesSendDeviceStatus) { await window.fieldSalesSendDeviceStatus(); }
            const res = await this.rpc('/field_sales/device/my_status', {});
            if (this._isMounted && res && res.ok) { this.state.device = res.status || {}; }
        } catch (e) {}
    }
    async refresh() { await this.load(); await this.refreshDeviceStatus(); }
}
FieldSimpleMode.template = "field_sales_route_plan.FieldSimpleMode";
registry.category("actions").add("field_sales_route_plan.simple_mode", FieldSimpleMode);

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FieldSalesManagerPanel extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({ loading: true, data: {}, date_from: this._todayISO(), date_to: this._todayISO(), sections: { performance: true, period: true, today: true, mtd: true, ytd: true } });
        onMounted(async () => { await this.load(); this._maybeStartFirstTimeTour(); });
    }

    _tourKey() { return "field_sales_route_plan_tour_seen_manager_v93"; }
    _maybeStartFirstTimeTour() {
        setTimeout(() => {
            try { if (!localStorage.getItem(this._tourKey())) { this.startTour(true); } } catch (e) {}
        }, 700);
    }
    startTour(auto=false) {
        const steps = [
            { selector: ".fsrp-manager-header", title: "Manager Control Panel", text: "This page gives supervisors one place to monitor routes, visits, sales, devices, and team execution." },
            { selector: ".fsrp-manager-actions", title: "Manager Actions", text: "Open maps, live team view, route visits, or refresh the dashboard from here." },
            { selector: ".fsrp-manager-kpis", title: "Team KPI Cards", text: "Quickly review planned calls, visits, productivity, sales, active visits, POS settlement, and device alerts." },
            { selector: ".fsrp-device-alerts-box", title: "Device Monitoring", text: "Track low battery, offline users, poor network, and stale device status." },
            { selector: ".fsrp-manager-targets", title: "Group Targets", text: "Review all-route and group target progress separately from individual salesperson targets." },
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
            const target = document.querySelector(step.selector);
            if (!target) { index += 1; if (index >= steps.length) { finish(); } else { show(); } return; }
            target.classList.add("fsrp-tour-highlight");
            target.scrollIntoView({ behavior: "smooth", block: "center" });
            title.textContent = step.title;
            text.textContent = step.text;
            stepNo.textContent = `Step ${index + 1} of ${steps.length}`;
            nextBtn.textContent = index === steps.length - 1 ? "Finish" : "Next";
            const rect = target.getBoundingClientRect();
            card.style.top = `${Math.min(window.innerHeight - 230, Math.max(20, rect.bottom + 12))}px`;
            card.style.left = `${Math.min(window.innerWidth - 360, Math.max(12, rect.left))}px`;
        };
        nextBtn.onclick = () => { index += 1; if (index >= steps.length) { finish(); } else { show(); } };
        skipBtn.onclick = finish;
        dim.onclick = finish;
        show();
    }

    _todayISO() { return new Date().toISOString().slice(0, 10); }
    setDateFrom(ev) { this.state.date_from = ev.target.value || this._todayISO(); }
    setDateTo(ev) { this.state.date_to = ev.target.value || this.state.date_from || this._todayISO(); }
    async applyDateFilter() { await this.load(); }
    async resetDateFilter() { this.state.date_from = this._todayISO(); this.state.date_to = this._todayISO(); await this.load(); }

    async applyMarketingPeriod(period) {
        const now = new Date();
        const year = now.getFullYear();
        const fmt = (d) => d.toISOString().slice(0, 10);
        if (period === 'jan_apr') {
            this.state.date_from = `${year}-01-01`;
            this.state.date_to = `${year}-04-30`;
        } else if (period === 'may_aug') {
            this.state.date_from = `${year}-05-01`;
            this.state.date_to = `${year}-08-31`;
        } else if (period === 'sep_dec') {
            this.state.date_from = `${year}-09-01`;
            this.state.date_to = `${year}-12-31`;
        } else {
            const month = now.getMonth() + 1;
            if (month <= 4) { this.state.date_from = `${year}-01-01`; this.state.date_to = `${year}-04-30`; }
            else if (month <= 8) { this.state.date_from = `${year}-05-01`; this.state.date_to = `${year}-08-31`; }
            else { this.state.date_from = `${year}-09-01`; this.state.date_to = `${year}-12-31`; }
        }
        await this.load();
    }

    toggleSection(name) {
        this.state.sections[name] = !this.state.sections[name];
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.rpc("/field_sales/manager_panel/data", { date_from: this.state.date_from, date_to: this.state.date_to });
        this.state.loading = false;
    }
    async openMap() { await this.action.doAction("field_sales_route_plan.action_client_map"); }
    async openLiveTeamMap() { await this.action.doAction("field_sales_route_plan.action_client_map", { additionalContext: { fsrp_navigation_mode: true } }); }
    async openVisits() { await this.action.doAction("field_sales_route_plan.action_route_visit"); }
    async openRouteClients() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Route Client Intelligence",
            res_model: "res.partner",
            views: [[false, "list"], [false, "form"]],
            domain: [["route_id", "!=", false]],
            context: { search_default_customer: 1, default_customer_rank: 1 },
            target: "current",
        });
    }

    async openMarketingHistory() {
        await this.action.doAction("field_sales_route_plan.action_marketing_history", {
            additionalContext: { search_default_today: 1, search_default_group_route: 1, search_default_group_day: 1 }
        });
    }
    async openSalesPersonProfiles() { await this.action.doAction("field_sales_route_plan.action_sales_person_profile"); }
    async openLicense() { await this.action.doAction("field_sales_route_plan.action_sales_route_license"); }
}
FieldSalesManagerPanel.template = "field_sales_route_plan.ManagerPanel";
registry.category("actions").add("field_sales_route_plan.manager_panel", FieldSalesManagerPanel);

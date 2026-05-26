/** @odoo-module **/


async function fsrpReverseGeocodeForGpsAction(latitude, longitude) {
    const coords = `${Number(latitude).toFixed(7)}, ${Number(longitude).toFixed(7)}`;
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        const url = new URL("https://api.bigdatacloud.net/data/reverse-geocode-client");
        url.searchParams.set("latitude", latitude);
        url.searchParams.set("longitude", longitude);
        url.searchParams.set("localityLanguage", "en");
        const response = await fetch(url.toString(), { signal: controller.signal, headers: { "Accept": "application/json" } });
        clearTimeout(timeout);
        if (response.ok) {
            const data = await response.json();
            const area = data.locality || data.city || data.principalSubdivision || data.countryName || "";
            const address = data.display_name || [data.locality, data.city, data.principalSubdivision, data.countryName].filter(Boolean).join(", ") || coords;
            return { place: area || address || coords, address, area, geocode_raw: JSON.stringify({ source: "bigdatacloud", data }) };
        }
    } catch (e) {}
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        const url = new URL("https://nominatim.openstreetmap.org/reverse");
        url.searchParams.set("format", "jsonv2");
        url.searchParams.set("lat", latitude);
        url.searchParams.set("lon", longitude);
        url.searchParams.set("addressdetails", "1");
        url.searchParams.set("zoom", "18");
        const response = await fetch(url.toString(), { signal: controller.signal, headers: { "Accept": "application/json" } });
        clearTimeout(timeout);
        if (response.ok) {
            const data = await response.json();
            const parts = data.address || {};
            const area = parts.suburb || parts.neighbourhood || parts.village || parts.town || parts.city || parts.county || parts.state || "";
            const address = data.display_name || coords;
            return { place: data.name || area || address || coords, address, area, geocode_raw: JSON.stringify({ source: "nominatim", data }) };
        }
    } catch (e) {}
    return { place: "", address: "", area: "", geocode_raw: JSON.stringify({ source: "browser_failed", latitude, longitude }) };
}

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

let leafletLoadPromise = null;
function loadLeaflet() {
    if (window.L) { return Promise.resolve(window.L); }
    if (leafletLoadPromise) { return leafletLoadPromise; }
    leafletLoadPromise = new Promise((resolve, reject) => {
        const cssId = "fsrp_leaflet_css";
        if (!document.getElementById(cssId)) {
            const link = document.createElement("link");
            link.id = cssId;
            link.rel = "stylesheet";
            link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
            document.head.appendChild(link);
        }
        const script = document.createElement("script");
        script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
        script.onload = () => resolve(window.L);
        script.onerror = () => reject(new Error("Could not load Leaflet map library."));
        document.head.appendChild(script);
    });
    return leafletLoadPromise;
}

export class FieldSalesClientMap extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            routes: [],
            selectedRouteId: 0,
            selectedMode: (this.props.action && this.props.action.context && this.props.action.context.fsrp_navigation_mode) ? "today_planned" : "today",
            dateFrom: this.todayString(),
            dateTo: this.todayString(),
            clients: [],
            summary: {},
            fullScreen: false,
            showRouteLine: true,
            showHeat: false,
            showTeam: false,
            navigationMode: !!(this.props.action && this.props.action.context && this.props.action.context.fsrp_navigation_mode),
            teamMembers: [],
        });
        this.map = null;
        this.markersLayer = null;
        this.routeLayer = null;
        this.heatLayer = null;
        onWillStart(async () => { await this.loadRoutes(); });
        onMounted(async () => { await this.loadClients(); });
    }
    async loadRoutes() {
        this.state.routes = await this.orm.searchRead("sales.route", [], ["name"], { order: "name" });
    }
    async loadClients() {
        this.state.loading = true;
        const data = await this.rpc("/field_sales/client_map/data", {
            route_id: parseInt(this.state.selectedRouteId || 0),
            mode: this.state.selectedMode || "today",
            date_from: this.state.dateFrom || false,
            date_to: this.state.dateTo || false,
        });
        this.state.clients = (data && data.clients) || [];
        this.state.summary = (data && data.summary) || {};
        this.state.loading = false;
        if (this.state.showTeam) { await this.loadTeamMembers(); }
        await this.renderMap();
    }
    async loadTeamMembers() {
        try {
            const data = await this.rpc("/field_sales/live_team_map/data", {});
            this.state.teamMembers = (data && data.members) || [];
        } catch (e) { this.state.teamMembers = []; }
    }
    async onRouteChange(ev) {
        this.state.selectedRouteId = ev.target.value;
        await this.loadClients();
    }
    async onModeChange(ev) {
        this.state.selectedMode = ev.target.value;
        await this.loadClients();
    }
    async onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
        if (this.state.dateTo && this.state.dateFrom && this.state.dateFrom > this.state.dateTo) {
            this.state.dateTo = this.state.dateFrom;
        }
        await this.loadClients();
    }
    async onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
        if (this.state.dateFrom && this.state.dateTo && this.state.dateTo < this.state.dateFrom) {
            this.state.dateFrom = this.state.dateTo;
        }
        await this.loadClients();
    }
    async resetToday() {
        const today = this.todayString();
        this.state.dateFrom = today;
        this.state.dateTo = today;
        await this.loadClients();
    }
    todayString() {
        const d = new Date();
        const offset = d.getTimezoneOffset();
        const local = new Date(d.getTime() - offset * 60000);
        return local.toISOString().slice(0, 10);
    }
    async toggleFullScreen() {
        this.state.fullScreen = !this.state.fullScreen;
        await this.nextMapResize();
    }
    async toggleRouteLine() {
        this.state.showRouteLine = !this.state.showRouteLine;
        await this.renderMap();
    }
    async toggleHeat() {
        this.state.showHeat = !this.state.showHeat;
        await this.renderMap();
    }
    async toggleTeamMap() {
        this.state.showTeam = !this.state.showTeam;
        if (this.state.showTeam) { await this.loadTeamMembers(); }
        await this.renderMap();
    }
    async toggleNavigationMode() {
        this.state.navigationMode = !this.state.navigationMode;
        if (this.state.navigationMode) {
            this.state.selectedMode = "today_planned";
            this.state.showRouteLine = true;
        }
        await this.loadClients();
    }
    async focusNextStop() {
        const routePoints = this.state.clients
            .filter((p) => p.planned_order && p.latitude && p.longitude)
            .sort((a, b) => (a.planned_order || 0) - (b.planned_order || 0));
        const next = routePoints.find((p) => p.map_status !== "planned_visited" && p.map_status !== "visited") || routePoints[0];
        if (next && this.map) { this.map.setView([next.latitude, next.longitude], 17); }
    }
    async nextMapResize() {
        await new Promise((resolve) => setTimeout(resolve, 80));
        if (this.map) {
            this.map.invalidateSize();
            await this.renderMap();
        }
    }
    markerColor(client) {
        if (client.map_status === "planned_visited") { return "green"; }
        if (client.map_status === "visited") { return "blue"; }
        if (client.map_status === "purchased") { return "purple"; }
        if (client.map_status === "planned") { return "orange"; }
        return "grey";
    }
    async renderMap() {
        const mapEl = document.getElementById("fsrp_client_map_canvas");
        if (!mapEl) { return; }
        const points = this.state.clients.filter((c) => c.latitude && c.longitude);
        if (!points.length) {
            mapEl.innerHTML = '<div class="fsrp-map-empty">No clients with latitude/longitude for this filter.</div>';
            this.map = null;
            this.markersLayer = null;
            return;
        }
        try {
            const L = await loadLeaflet();
            if (!this.map) {
                mapEl.innerHTML = "";
                this.map = L.map(mapEl).setView([points[0].latitude, points[0].longitude], 13);
                L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                    maxZoom: 19,
                    attribution: "&copy; OpenStreetMap contributors",
                }).addTo(this.map);
                this.markersLayer = L.layerGroup().addTo(this.map);
                this.routeLayer = L.layerGroup().addTo(this.map);
                this.heatLayer = L.layerGroup().addTo(this.map);
            }
            this.markersLayer.clearLayers();
            if (!this.heatLayer) { this.heatLayer = L.layerGroup().addTo(this.map); }
            if (this.routeLayer) { this.routeLayer.clearLayers(); }
            if (this.heatLayer) { this.heatLayer.clearLayers(); }
            const bounds = [];
            for (const p of points) {
                const status = p.status_label || "Client";
                const title = `${p.name}`;
                const color = this.markerColor(p);
                const marker = L.circleMarker([p.latitude, p.longitude], {
                    radius: 9,
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.85,
                    weight: 2,
                });
                const placeDetails = [
                    `<strong>${this.escapeHtml(p.name)}</strong>`,
                    this.escapeHtml(status),
                    this.escapeHtml(p.route || "No Route"),
                    `<em>${this.escapeHtml(p.coordinate_source_label || "")}</em>`,
                    this.escapeHtml(p.address || "")
                ].filter(Boolean).join("<br/>");
                // Show place details by default as a permanent label. Popup still opens on click.
                marker.bindTooltip(placeDetails, {
                    direction: "top",
                    permanent: true,
                    sticky: false,
                    opacity: 0.95,
                    className: "fsrp-client-place-tooltip",
                    offset: [0, -10],
                });
                marker.bindPopup(placeDetails);
                marker.addTo(this.markersLayer);
                bounds.push([p.latitude, p.longitude]);
            }
            const routePoints = points
                .filter((p) => p.planned_today && p.planned_order && p.latitude && p.longitude)
                .sort((a, b) => (a.planned_order || 0) - (b.planned_order || 0));
            if (this.state.showRouteLine && routePoints.length > 1 && this.routeLayer) {
                const latLngs = routePoints.map((p) => [p.latitude, p.longitude]);
                // High visibility route: white halo underneath + solid red line on top.
                L.polyline(latLngs, { color: '#ffffff', weight: this.state.navigationMode ? 18 : 14, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }).addTo(this.routeLayer);
                L.polyline(latLngs, { color: this.state.navigationMode ? '#00a3ff' : '#ff1f1f', weight: this.state.navigationMode ? 11 : 8, opacity: 1, lineCap: 'round', lineJoin: 'round' }).addTo(this.routeLayer);
                L.polyline(latLngs, { color: '#111111', weight: 2, opacity: 0.55, dashArray: '12,14', lineCap: 'round', lineJoin: 'round' }).addTo(this.routeLayer);

                // Direction arrows at the midpoint of every route segment.
                for (let i = 0; i < routePoints.length - 1; i++) {
                    const a = routePoints[i];
                    const b = routePoints[i + 1];
                    const midLat = (a.latitude + b.latitude) / 2;
                    const midLng = (a.longitude + b.longitude) / 2;
                    const angle = Math.atan2(b.longitude - a.longitude, b.latitude - a.latitude) * 180 / Math.PI;
                    const arrow = L.divIcon({
                        className: 'fsrp-route-arrow',
                        html: `<span style="transform: rotate(${angle}deg);">➜</span>`,
                        iconSize: [34, 34],
                        iconAnchor: [17, 17],
                    });
                    L.marker([midLat, midLng], { icon: arrow, interactive: false }).addTo(this.routeLayer);
                }

                routePoints.forEach((p, idx) => {
                    const badge = L.divIcon({
                        className: 'fsrp-route-sequence-pin',
                        html: `<span>${idx + 1}</span>`,
                        iconSize: [34, 34],
                        iconAnchor: [17, 17],
                    });
                    L.marker([p.latitude, p.longitude], { icon: badge, interactive: false }).addTo(this.routeLayer);
                });
            }
            if (this.state.showTeam && this.routeLayer && (this.state.teamMembers || []).length) {
                for (const m of this.state.teamMembers) {
                    if (!m.latitude || !m.longitude) { continue; }
                    const icon = L.divIcon({
                        className: 'fsrp-team-live-pin',
                        html: `<span>👤</span>`,
                        iconSize: [34, 34],
                        iconAnchor: [17, 17],
                    });
                    const marker = L.marker([m.latitude, m.longitude], { icon: icon });
                    marker.bindPopup(`<strong>${this.escapeHtml(m.user)}</strong><br/>${this.escapeHtml(m.client)}<br/>${this.escapeHtml(m.route)}<br/>${this.escapeHtml(m.check_in)}<br/>${this.escapeHtml(m.address || '')}`);
                    marker.addTo(this.routeLayer);
                }
            }
            if (this.state.navigationMode) {
                setTimeout(() => this.focusNextStop(), 120);
            }
            if (this.state.showHeat && this.heatLayer) {
                points.forEach((p) => {
                    const radius = 120 + ((p.heat_weight || 1) * 80);
                    L.circle([p.latitude, p.longitude], {
                        radius: radius,
                        color: '#ef4444',
                        fillColor: '#f97316',
                        fillOpacity: 0.18,
                        weight: 1,
                    }).addTo(this.heatLayer);
                });
            }
            if (bounds.length === 1) {
                this.map.setView(bounds[0], 15);
            } else {
                this.map.fitBounds(bounds, { padding: [40, 40] });
            }
        } catch (error) {
            // Fallback: show a readable list of coordinates if CDN map library cannot load.
            mapEl.innerHTML = `<div class="fsrp-map-empty">Map library could not load. Showing client list below.<br/>${this.escapeHtml(error.message || error.toString())}</div>`;
        }
    }
    escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}
FieldSalesClientMap.template = "field_sales_route_plan.ClientMap";
registry.category("actions").add("field_sales_route_plan.client_map", FieldSalesClientMap);

export class FieldSalesGPSCapture extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ message: "Getting device GPS...", working: true, result: null });
        this.visitId = this.props.action.context.visit_id;
        this.mode = this.props.action.context.gps_mode || "checkin";
        this.autoBackToVisit = !!this.props.action.context.auto_back_to_visit;
        onMounted(async () => { await this.capture(); });
    }
    get title() { return this.mode === "checkout" ? "GPS Check Out" : "GPS Check In"; }
    async capture() {
        if (!navigator.geolocation) {
            this.state.message = "This browser does not support GPS location.";
            this.state.working = false;
            return;
        }
        navigator.geolocation.getCurrentPosition(async (pos) => {
            const latitude = pos.coords.latitude;
            const longitude = pos.coords.longitude;
            this.state.message = `${this.title}: resolving place details...`;
            const details = await fsrpReverseGeocodeForGpsAction(latitude, longitude);
            const url = this.mode === "checkout" ? "/field_sales/visit/checkout" : "/field_sales/visit/checkin";
            const result = await this.rpc(url, {
                visit_id: this.visitId,
                latitude,
                longitude,
                place: details.place,
                address: details.address,
                area: details.area,
                geocode_raw: details.geocode_raw,
            });
            this.state.result = result;
            this.state.working = false;
            if (result.ok) {
                const place = result.address || result.place || `${latitude}, ${longitude}`;
                this.state.message = `${this.title} saved: ${place}`;
                this.notification.add(this.state.message, { type: "success", sticky: false });
                if (this.autoBackToVisit) {
                    setTimeout(() => this.backToVisit(), 1200);
                }
            } else {
                this.state.message = result.error || "GPS action failed.";
                this.notification.add(this.state.message, { type: "danger", sticky: true });
            }
        }, (err) => {
            this.state.message = `Could not get GPS: ${err.message}`;
            this.state.working = false;
            this.notification.add(this.state.message, { type: "danger", sticky: true });
        }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
    }
    backToVisit() {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "sales.route.visit", res_id: this.visitId, views: [[false, "form"]], view_mode: "form", target: "current" });
    }
}
FieldSalesGPSCapture.template = "field_sales_route_plan.GPSCapture";
registry.category("actions").add("field_sales_route_plan.gps_capture", FieldSalesGPSCapture);

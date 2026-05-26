/** @odoo-module **/

/*
 * Robust inline GPS capture for Field Visits.
 *
 * Earlier builds relied only on patching the FormController button method. On some
 * Odoo 16 themes/builds that method is not called before the server object button,
 * so users only saw the fallback message. This file now has two layers:
 *   1) FormController patch when available.
 *   2) DOM capture listener that intercepts the GPS buttons before Odoo posts them.
 *
 * The user remains on the same visit screen. GPS is captured in the browser,
 * reverse-geocoded in the browser when possible, sent to Odoo, then the same form
 * is refreshed after the success message.
 */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";

function fsrpVisitIdFromHash() {
    const hash = (window.location.hash || "").replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const model = params.get("model");
    const id = parseInt(params.get("id") || "0", 10);
    if (model === "sales.route.visit" && id) {
        return id;
    }
    return 0;
}

function fsrpToast(message, type = "info", sticky = false) {
    // Lightweight status notification that does not depend on Odoo services.
    let box = document.querySelector(".fsrp-inline-gps-toast");
    if (!box) {
        box = document.createElement("div");
        box.className = "fsrp-inline-gps-toast";
        document.body.appendChild(box);
    }
    box.textContent = message;
    box.className = `fsrp-inline-gps-toast fsrp-inline-gps-${type}`;
    box.style.display = "block";
    if (!sticky) {
        window.clearTimeout(box.__fsrpTimer);
        box.__fsrpTimer = window.setTimeout(() => { box.style.display = "none"; }, 8000);
    }
}

async function fsrpJsonRpc(route, params) {
    const response = await fetch(route, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {}, id: Date.now() }),
    });
    const payload = await response.json();
    if (payload.error) {
        const msg = payload.error.data && payload.error.data.message ? payload.error.data.message : payload.error.message;
        throw new Error(msg || "Odoo RPC error");
    }
    return payload.result;
}

function fsrpOfflineEnqueue(payloadType, payload) { return null; }

async function fsrpGetPosition() {
    if (!navigator.geolocation) {
        throw new Error("This browser does not support GPS location.");
    }
    return await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true,
            timeout: 45000,
            maximumAge: 0,
        });
    });
}

function fsrpGpsErrorMessage(error) {
    if (error && error.code === 1) {
        return "Location permission was denied. Please allow location access for this site and try again.";
    }
    if (error && error.code === 2) {
        return "Location is unavailable. Please enable GPS/location services and try again.";
    }
    if (error && error.code === 3) {
        return "Location request timed out. Please move to an open area and try again.";
    }
    return error && error.message ? error.message : String(error || "Unknown GPS error");
}

async function fsrpReverseGeocode(latitude, longitude) {
    const coords = `${latitude.toFixed(7)}, ${longitude.toFixed(7)}`;

    // CORS-friendly public reverse-geocode endpoint. Good browser fallback when
    // the Odoo server cannot reach external APIs.
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
            const addressParts = [
                data.locality,
                data.city,
                data.principalSubdivision,
                data.countryName,
            ].filter(Boolean);
            const address = data.display_name || addressParts.join(", ") || coords;
            return {
                place: area || address || coords,
                address: address,
                area: area,
                geocode_raw: JSON.stringify({ source: "bigdatacloud", data }),
            };
        }
    } catch (e) {
        // Continue to Nominatim fallback.
    }

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
            return {
                place: data.name || area || address || coords,
                address: address,
                area: area,
                geocode_raw: JSON.stringify({ source: "nominatim", data }),
            };
        }
    } catch (e) {
        // Server-side geocoder will still be tried after the RPC call.
    }

    return {
        place: "",
        address: "",
        area: "",
        geocode_raw: JSON.stringify({ source: "browser_failed", latitude, longitude }),
    };
}

async function fsrpCaptureVisitGps(visitId, mode) {
    const isCheckout = mode === "checkout";
    const label = isCheckout ? "GPS Check Out" : "GPS Check In";
    const route = isCheckout ? "/field_sales/visit/checkout" : "/field_sales/visit/checkin";

    fsrpToast(`${label}: requesting phone GPS...`, "info", true);
    const position = await fsrpGetPosition();
    const latitude = position.coords.latitude;
    const longitude = position.coords.longitude;

    fsrpToast(`${label}: resolving place details...`, "info", true);
    const placeDetails = await fsrpReverseGeocode(latitude, longitude);

    const offlinePayload = {
        visit_id: visitId,
        mode: isCheckout ? "checkout" : "checkin",
        latitude,
        longitude,
        place: placeDetails.place,
        address: placeDetails.address,
        area: placeDetails.area,
        geocode_raw: placeDetails.geocode_raw,
        captured_at: new Date().toISOString(),
    };

    if (!navigator.onLine) {
        fsrpToast(`${label} captured, but internet is required to save and resolve place details. Please reconnect and try again.`, "warning", false);
        return;
    }

    fsrpToast(`${label}: saving visit location...`, "info", true);
    let result = null;
    try {
        result = await fsrpJsonRpc(route, offlinePayload);
    } catch (e) {
        throw e;
    }

    if (!result || !result.ok) {
        throw new Error((result && result.error) || `${label} failed.`);
    }

    const displayPlace = result.address || result.place || placeDetails.address || `${latitude.toFixed(7)}, ${longitude.toFixed(7)}`;
    fsrpToast(`${label} saved: ${displayPlace}`, "success", false);

    // Refresh the same form, not a redirect to a separate GPS page.
    setTimeout(() => window.location.reload(), 1200);
}

// Layer 1: patch Odoo's form controller where this hook exists.
patch(FormController.prototype, "field_sales_route_plan.inline_visit_gps.v100", {
    setup() {
        this._super(...arguments);
        this.fsrpNotification = useService("notification");
    },

    async _callButton(params) {
        const attrs = params && params.attrs ? params.attrs : {};
        const buttonName = attrs.name;
        const isVisitForm = this.props && this.props.resModel === "sales.route.visit";
        const isGpsButton = buttonName === "action_open_gps_checkin" || buttonName === "action_open_gps_checkout";
        if (!isVisitForm || !isGpsButton) {
            return this._super(...arguments);
        }
        const visitId = this.model && this.model.root && this.model.root.resId;
        if (!visitId) {
            this.fsrpNotification.add("Please save the visit before capturing GPS.", { type: "warning" });
            return;
        }
        try {
            await fsrpCaptureVisitGps(visitId, buttonName === "action_open_gps_checkout" ? "checkout" : "checkin");
        } catch (error) {
            this.fsrpNotification.add(fsrpGpsErrorMessage(error), { type: "danger", sticky: true });
        }
    },
});

// Layer 2: capture DOM clicks before Odoo executes the object button. This is the
// reliability fix for cases where the FormController patch is not invoked.
// Do not require a special form CSS class here: header buttons may be rendered
// outside the form node by some Odoo themes, and kanban/mobile cards also use
// the same object button names.
async function fsrpInlineGpsButtonHandler(ev) {
    const button = ev.target && ev.target.closest ? ev.target.closest("button[name='action_open_gps_checkin'], button[name='action_open_gps_checkout']") : null;
    if (!button || button.__fsrpGpsBusy) {
        return;
    }
    const visitId = fsrpVisitIdFromHash();
    // Only intercept when we are on an actual visit form URL. If the same button
    // appears in kanban/list cards, let the server fallback client action handle it
    // using the record id from Odoo.
    if (!visitId) {
        return;
    }
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();

    button.__fsrpGpsBusy = true;
    button.setAttribute("disabled", "disabled");
    try {
        await fsrpCaptureVisitGps(visitId, button.getAttribute("name") === "action_open_gps_checkout" ? "checkout" : "checkin");
    } catch (error) {
        fsrpToast(`GPS failed: ${fsrpGpsErrorMessage(error)}`, "danger", true);
        button.__fsrpGpsBusy = false;
        button.removeAttribute("disabled");
    }
}
document.addEventListener("click", fsrpInlineGpsButtonHandler, true);

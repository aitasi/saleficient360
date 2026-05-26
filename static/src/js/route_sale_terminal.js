/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class RouteSaleTerminal extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            search: "",
            selectedCategoryId: 0,
            data: {},
            quickMode: false,
            customerSearch: "",
            customerSearchLoading: false,
            customerResults: [],
            selectedPartnerId: false,
            selectedPartnerName: "",
            selectedRouteId: false,
            selectedRouteName: "",
            selectedSalesUserId: false,
            selectedSalesUserName: "",
            salespersonSearch: "",
            salespersonSearchLoading: false,
            salespersonResults: [],
            showNewCustomerPanel: false,
            newCustomerName: "",
            newCustomerPhone: "",
            products: [],
            categories: [],
            cart: {},
            previousOrders: [],
            editingOrderId: false,
            editingOrderName: "",
            showRecreatePanel: false,
            orderSearch: "",
            orderSearchLoading: false,
            successMessage: "",
            successOrderName: "",
            lastOrderId: false,
            mobilePanel: "products",
        });
        this.planLineId = this.props.action.context.plan_line_id || false;
        onWillStart(async () => {
            await this.loadTerminal();
        });
    }

    async loadTerminal() {
        const data = await this.orm.call("route.sale.terminal.wizard", "get_terminal_data", [this.planLineId]);
        this.state.data = data;
        this.state.quickMode = !!data.quick_mode;
        this.state.selectedPartnerId = data.partner_id || false;
        this.state.selectedPartnerName = data.partner_name || "";
        this.state.selectedRouteId = data.route_id || false;
        this.state.selectedRouteName = data.route_name || "";
        this.state.selectedSalesUserId = data.selected_sales_user_id || false;
        this.state.selectedSalesUserName = data.selected_sales_user_name || "";
        this.state.salespersonSearch = this.state.selectedSalesUserName || "";
        this.state.products = data.products || [];
        this.state.categories = data.categories || [];
        this.state.cart = {};
        this.state.previousOrders = data.previous_orders || [];
        this.state.editingOrderId = data.editing_order_id || false;
        this.state.editingOrderName = data.editing_order_name || "";
        for (const line of data.cart || []) {
            this.state.cart[line.product_id] = {
                product_id: line.product_id,
                name: line.name,
                qty: line.qty,
                price_unit: line.price_unit,
                subtotal: line.qty * line.price_unit,
            };
        }
        this.state.loading = false;
    }

    get filteredProducts() {
        const query = (this.state.search || "").toLowerCase();
        const categoryId = parseInt(this.state.selectedCategoryId || 0);
        return this.state.products.filter((p) => {
            const matchesCategory = !categoryId || ((p.category_ids || []).includes(categoryId));
            const matchesSearch = !query ||
                (p.name || "").toLowerCase().includes(query) ||
                (p.default_code || "").toLowerCase().includes(query);
            return matchesCategory && matchesSearch;
        });
    }

    get filteredPreviousOrders() {
        const query = (this.state.orderSearch || "").toLowerCase();
        if (!query) {
            return this.state.previousOrders;
        }
        return this.state.previousOrders.filter((order) =>
            (order.name || "").toLowerCase().includes(query) ||
            (order.partner_name || "").toLowerCase().includes(query) ||
            (order.amount_display || "").toLowerCase().includes(query)
        );
    }

    async searchPreviousOrders() {
        this.state.orderSearchLoading = true;
        try {
            this.state.previousOrders = await this.orm.call(
                "route.sale.terminal.wizard",
                "search_recreatable_orders",
                [this.planLineId || false, this.state.orderSearch || "", 50, this.state.selectedPartnerId || false]
            );
        } finally {
            this.state.orderSearchLoading = false;
        }
    }

    get cartLines() {
        return Object.values(this.state.cart).filter((line) => line.qty > 0);
    }

    get cartTotal() {
        return this.cartLines.reduce((total, line) => total + (line.qty * line.price_unit), 0);
    }

    addProduct(product) {
        const existing = this.state.cart[product.id];
        if (existing) {
            existing.qty += 1;
            existing.subtotal = existing.qty * existing.price_unit;
        } else {
            this.state.cart[product.id] = {
                product_id: product.id,
                name: product.name,
                qty: 1,
                price_unit: product.price_unit,
                subtotal: product.price_unit,
            };
        }
    }

    changeQty(productId, qty) {
        const line = this.state.cart[productId];
        if (!line) {
            return;
        }
        const newQty = parseFloat(qty) || 0;
        if (newQty <= 0) {
            delete this.state.cart[productId];
        } else {
            line.qty = newQty;
            line.subtotal = line.qty * line.price_unit;
        }
    }

    increase(productId) {
        const line = this.state.cart[productId];
        if (line) {
            line.qty += 1;
            line.subtotal = line.qty * line.price_unit;
        }
    }

    decrease(productId) {
        const line = this.state.cart[productId];
        if (line) {
            this.changeQty(productId, line.qty - 1);
        }
    }

    clearCart() {
        this.state.cart = {};
        this.state.editingOrderId = false;
        this.state.editingOrderName = "";
    }

    toggleRecreatePanel() {
        this.state.showRecreatePanel = !this.state.showRecreatePanel;
        if (this.state.showRecreatePanel) {
            this.searchPreviousOrders();
        }
    }

    async recreateOrder(orderId) {
        if (!orderId) {
            this.notification.add("Please select a previous order.", { type: "warning" });
            return;
        }
        const result = await this.orm.call("route.sale.terminal.wizard", "get_recreate_order_lines", [this.planLineId || false, orderId, this.state.selectedPartnerId || false]);
        this.state.cart = {};
        for (const line of result.cart || []) {
            this.state.cart[line.product_id] = {
                product_id: line.product_id,
                name: line.name,
                qty: line.qty,
                price_unit: line.price_unit,
                subtotal: line.qty * line.price_unit,
            };
        }
        if (this.state.quickMode && result.partner_id) {
            this.state.selectedPartnerId = result.partner_id;
            this.state.selectedPartnerName = result.partner_name || "";
            this.state.selectedRouteId = result.route_id || false;
            this.state.selectedRouteName = result.route_name || "";
        }
        this.state.editingOrderId = result.sale_order_id;
        this.state.editingOrderName = result.sale_order_name || "";
        this.state.showRecreatePanel = false;
        this.showCart();
        this.notification.add(result.message || "Previous order loaded.", { type: "info" });
    }

    showProducts() {
        this.state.mobilePanel = "products";
    }

    showCart() {
        this.state.mobilePanel = "cart";
    }

    backToVisit() {
        if (this.state.quickMode) {
            this.action.doAction("field_sales_route_plan.action_simple_field_mode");
            return;
        }
        if (this.state.data.visit_id) {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "Field Visit",
                res_model: "sales.route.visit",
                res_id: this.state.data.visit_id,
                view_mode: "form",
                views: [[false, "form"]],
                target: "current",
                context: { create: false },
            });
        } else {
            this.backToPlan();
        }
    }

    async confirmOrder() {
        const lines = this.cartLines.map((line) => ({
            product_id: line.product_id,
            qty: line.qty,
            price_unit: line.price_unit,
        }));
        if (!lines.length) {
            this.notification.add("Please add at least one product to the cart.", { type: "warning" });
            return;
        }
        let result = null;
        try {
            if (!navigator.onLine) {
                this.notification.add("Internet connection is required to create the Sales Order.", { type: "warning" });
                return;
            }
            if (this.state.quickMode && !this.state.selectedPartnerId) {
                this.notification.add("Please select a customer before creating the quick sales order.", { type: "warning" });
                return;
            }
            result = await this.orm.call("route.sale.terminal.wizard", "confirm_terminal_order", [this.planLineId || false, lines, this.state.editingOrderId || false, this.state.selectedPartnerId || false, this.state.selectedRouteId || false, this.state.selectedSalesUserId || false]);
        } catch (error) {
            throw error;
        }
        const message = (result && result.message) || "Sales Order saved successfully.";
        if (result && result.sale_order_id) {
            this.state.data.sale_order_id = result.sale_order_id;
            this.state.data.sale_order_name = result.sale_order_name || "";
            this.state.successOrderName = result.sale_order_name || "";
            this.state.lastOrderId = result.sale_order_id;
            if (result.assigned_sales_user_id) {
                this.state.selectedSalesUserId = result.assigned_sales_user_id;
                this.state.selectedSalesUserName = result.assigned_sales_user_name || this.state.selectedSalesUserName;
                this.state.salespersonSearch = this.state.selectedSalesUserName;
            }
            this.state.editingOrderId = false;
            this.state.editingOrderName = "";
            await this.loadTerminal();
        }
        this.state.successMessage = message;
        this.clearCart();
        this.notification.add(message, { type: "success", sticky: false });
        this.speakSuccessMessage(message);
        window.clearTimeout(this._successTimeout);
        this._successTimeout = window.setTimeout(() => {
            this.state.successMessage = "";
        }, 60000);
    }


    async printReceipt() {
        if (!this.state.lastOrderId && !this.state.data.sale_order_id) {
            this.notification.add("Please create or update a sales order before printing a receipt.", { type: "warning" });
            return;
        }
        const orderId = this.state.lastOrderId || this.state.data.sale_order_id;
        const action = await this.orm.call("route.sale.terminal.wizard", "action_print_pos_receipt", [orderId]);
        await this.action.doAction(action);
    }

    speakSuccessMessage(message) {
        try {
            if (window.speechSynthesis && message) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(message);
                utterance.rate = 0.95;
                window.speechSynthesis.speak(utterance);
            }
        } catch (error) {
            // Voice feedback is optional; ignore browsers/devices that block speech synthesis.
        }
    }

    async searchCustomers() {
        if (!this.state.quickMode) { return; }
        const query = (this.state.customerSearch || "").trim();
        if (!query) {
            this.state.customerResults = [];
            return;
        }
        this.state.customerSearchLoading = true;
        try {
            this.state.customerResults = await this.orm.call("route.sale.terminal.wizard", "search_quick_sale_customers", [query, 30]);
        } finally {
            this.state.customerSearchLoading = false;
        }
    }

    async selectCustomer(customer) {
        if (!customer) { return; }
        const data = await this.orm.call("route.sale.terminal.wizard", "get_quick_sale_customer_context", [customer.id]);
        this.state.selectedPartnerId = data.partner_id;
        this.state.selectedPartnerName = data.partner_name || customer.name || "";
        this.state.selectedRouteId = data.route_id || false;
        this.state.selectedRouteName = data.route_name || "";
        this.state.customerSearch = this.state.selectedPartnerName;
        this.state.customerResults = [];
        this.state.previousOrders = [];
        this.state.editingOrderId = false;
        this.state.editingOrderName = "";
        this.notification.add("Customer selected: " + this.state.selectedPartnerName, { type: "success" });
    }

    async searchSalespersons() {
        if (!this.state.quickMode) { return; }
        const query = (this.state.salespersonSearch || "").trim();
        this.state.salespersonSearchLoading = true;
        try {
            this.state.salespersonResults = await this.orm.call("route.sale.terminal.wizard", "search_quick_sale_salespersons", [query, 30]);
        } finally {
            this.state.salespersonSearchLoading = false;
        }
    }

    selectSalesperson(user) {
        if (!user) { return; }
        this.state.selectedSalesUserId = user.id;
        this.state.selectedSalesUserName = user.name || user.login || "";
        this.state.salespersonSearch = this.state.selectedSalesUserName;
        this.state.salespersonResults = [];
        this.notification.add("Salesperson assigned: " + this.state.selectedSalesUserName, { type: "success" });
    }

    toggleNewCustomerPanel() {
        this.state.showNewCustomerPanel = !this.state.showNewCustomerPanel;
        if (this.state.showNewCustomerPanel && this.state.customerSearch && !this.state.newCustomerName) {
            this.state.newCustomerName = this.state.customerSearch;
        }
    }

    async createNewCustomer() {
        if (!this.state.quickMode) { return; }
        const name = (this.state.newCustomerName || "").trim();
        if (!name) {
            this.notification.add("Please enter the new client name.", { type: "warning" });
            return;
        }
        const customer = await this.orm.call("route.sale.terminal.wizard", "create_quick_sale_customer", [name, this.state.newCustomerPhone || "", this.state.selectedRouteId || false]);
        await this.selectCustomer(customer);
        this.state.customerResults = [];
        this.state.customerSearch = customer.name;
        this.state.newCustomerName = "";
        this.state.newCustomerPhone = "";
        this.state.showNewCustomerPanel = false;
        this.notification.add("New client created and selected: " + customer.name, { type: "success" });
    }

    backToPlan() {
        if (this.state.quickMode) {
            this.action.doAction("field_sales_route_plan.action_simple_field_mode");
            return;
        }
        if (this.state.data.plan_id) {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "Daily Route Plan",
                res_model: "sales.route.plan",
                res_id: this.state.data.plan_id,
                view_mode: "form",
                views: [[false, "form"]],
                target: "current",
            });
        } else {
            this.action.doAction({ type: "ir.actions.act_window_close" });
        }
    }
}

RouteSaleTerminal.template = "field_sales_route_plan.RouteSaleTerminal";
registry.category("actions").add("field_sales_route_plan.sale_terminal", RouteSaleTerminal);

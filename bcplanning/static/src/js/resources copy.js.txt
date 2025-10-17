/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.PartnerResources = publicWidget.Widget.extend({
    // Support either wrapper id you might have used
    selector: "#partner-resources-app, #task_wrap",

    events: {
        "click #btn-add-resource": "_onAddResource",
        "click .btn-edit": "_onEditResource",
        "click .btn-delete": "_onDeleteResource",
        "submit #resource-form": "_onSubmitResourceForm",
    },

    // ------------- lifecycle -------------
    start: function () {
        this._loadResources();
        return this._super.apply(this, arguments);
    },

    // ------------- helpers -------------
    _setFeedback(msg, isError = true) {
        const $box = this.$("#resources-feedback");
        if (!$box.length) return;
        $box.text(msg || "");
        $box.toggleClass("text-danger", !!(msg && isError));
        $box.toggleClass("text-success", !!(msg && !isError));
        if (msg) {
            setTimeout(() => this._setFeedback(""), 4000);
        }
    },

    _renderRowHtml(resource) {
        // resource: { res_id, res_name }
        return `
            <tr data-res-id="${resource.res_id}">
                <td>${resource.res_id}</td>
                <td class="res-name">${this._escape(resource.res_name || "")}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-primary me-1 btn-edit">Edit</button>
                    <button class="btn btn-sm btn-outline-danger btn-delete">Delete</button>
                </td>
            </tr>
        `;
    },

    _renderEmptyTbody() {
        return `
            <tr data-empty="true">
                <td colspan="3" class="text-center text-muted">No resources found.</td>
            </tr>
        `;
    },

    _fillTable(resources) {
        const $tbody = this.$("#resources-tbody");
        if (!$tbody.length) return;
        if (!resources || !resources.length) {
            $tbody.html(this._renderEmptyTbody());
            return;
        }
        const rows = resources.map((r) => this._renderRowHtml(r)).join("");
        $tbody.html(rows);
    },

    _escape(str) {
        return String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    },

    _openModal({ title, resId = "", name = "" }) {
        const $modal = this.$("#resourceModal");
        if (!$modal.length) return;
        this.$("#resourceModalLabel").text(title);
        this.$("#resource-id").val(resId);
        this.$("#resource-name").val(name);
        this.$("#resource-form-feedback").text("");

        // Prefer Bootstrap 5 if available; fallback to manual show
        const modalEl = $modal[0];
        const hasBootstrap = typeof window.bootstrap !== "undefined" && window.bootstrap?.Modal;
        if (hasBootstrap) {
            window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
        } else {
            $modal.addClass("show").css("display", "block").attr("aria-hidden", null);
        }
    },

    _closeModal() {
        const $modal = this.$("#resourceModal");
        if (!$modal.length) return;
        const modalEl = $modal[0];
        const hasBootstrap = typeof window.bootstrap !== "undefined" && window.bootstrap?.Modal;
        if (hasBootstrap) {
            window.bootstrap.Modal.getInstance(modalEl)?.hide();
        } else {
            $modal.removeClass("show").css("display", "none").attr("aria-hidden", "true");
        }
    },

    // ------------- RPC -------------
    async _loadResources() {
        // Keep "Loading..." placeholder until data arrives
        try {
            const res = await rpc("/partner/resources/data", {});
            if (!res || res.ok !== true) {
                throw new Error((res && res.error) || "Failed to load resources");
            }
            // Update partner metadata (optional)
            this.$("#partner-name").text(res.partner_name || "");
            this.$("#partner-id").text(res.partner_id || "");
            // Render table
            this._fillTable(res.resources);
        } catch (e) {
            console.error("[bcplanning] loadResources error:", e);
            this._setFeedback(e.message || "Error loading resources");
            const $tbody = this.$("#resources-tbody");
            $tbody.html(this._renderEmptyTbody());
        }
    },

    async _rpcCreate(name) {
        return await rpc("/partner/resources/create", { name });
    },

    async _rpcUpdate(res_id, name) {
        return await rpc("/partner/resources/update", { res_id, name });
    },

    async _rpcDelete(res_id) {
        return await rpc("/partner/resources/delete", { res_id });
    },

    // ------------- events -------------
    _onAddResource(ev) {
        ev.preventDefault();
        this._openModal({ title: "Add Resource" });
    },

    _onEditResource(ev) {
        ev.preventDefault();
        const $row = $(ev.currentTarget).closest("tr[data-res-id]");
        if (!$row.length) return;
        const resId = parseInt($row.data("res-id"), 10);
        const name = $row.find(".res-name").text().trim();
        this._openModal({ title: "Edit Resource", resId, name });
    },

    async _onDeleteResource(ev) {
        ev.preventDefault();
        const $row = $(ev.currentTarget).closest("tr[data-res-id]");
        if (!$row.length) return;
        const resId = parseInt($row.data("res-id"), 10);

        if (!confirm("Are you sure you want to delete this resource?")) {
            return;
        }
        try {
            const out = await this._rpcDelete(resId);
            if (!out.ok) throw new Error(out.error || "Delete failed");
            $row.remove();
            const $tbody = this.$("#resources-tbody");
            if (!$tbody.find("tr[data-res-id]").length) {
                $tbody.html(this._renderEmptyTbody());
            }
            this._setFeedback("Resource deleted successfully.", false);
        } catch (e) {
            console.error("[bcplanning] delete error:", e);
            this._setFeedback(e.message || "Error deleting resource");
        }
    },

    async _onSubmitResourceForm(ev) {
        ev.preventDefault();
        const $feedback = this.$("#resource-form-feedback").text("");
        const resIdRaw = this.$("#resource-id").val();
        const name = (this.$("#resource-name").val() || "").trim();

        if (!name) {
            $feedback.text("Name is required.");
            return;
        }

        const isEdit = !!resIdRaw;
        try {
            const out = isEdit
                ? await this._rpcUpdate(parseInt(resIdRaw, 10), name)
                : await this._rpcCreate(name);

            if (!out.ok) throw new Error(out.error || "Operation failed");

            this._closeModal();

            if (isEdit) {
                const $row = this.$(`tr[data-res-id="${resIdRaw}"]`);
                $row.find(".res-name").text(out.resource.res_name || "");
                this._setFeedback("Resource updated successfully.", false);
            } else {
                // prepend new row
                const $tbody = this.$("#resources-tbody");
                $tbody.find('tr[data-empty="true"]').remove();
                $tbody.prepend(this._renderRowHtml(out.resource));
                this._setFeedback("Resource created successfully.", false);
            }
        } catch (e) {
            console.error("[bcplanning] submit error:", e);
            $feedback.text(e.message || "Error performing operation.");
        }
    },
});
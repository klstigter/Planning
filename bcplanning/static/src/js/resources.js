/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.PartnerResources = publicWidget.Widget.extend({
    selector: "#resource_wrap",

    events: {
        "click #btn-add-resource": "_onAddResource",
        "click .btn-edit": "_onEditResource",
        "click .btn-delete": "_onDeleteResource",
        "click .btn-grant-portal": "_onGrantPortal",
        "click .btn-grant-portal-wizard": "_onGrantPortalWizard",
        "click .menu-toggle": "_onMenuToggle",
        "submit #resource-form": "_onSubmitResourceForm",
    },

    start: function () {
        // debug: confirm widget started
        try {
            this._loadResources();
        } catch (e) {
            console.error("[bcplanning] start error", e);
        }
        return this._super.apply(this, arguments);
    },

    _setFeedback(msg, isError = true) {
        const $box = this.$("#resources-feedback");
        if (!$box.length) return;
        $box.text(msg || "");
        $box.toggleClass("text-danger", !!(msg && isError));
        $box.toggleClass("text-success", !!(msg && !isError));
        if (msg) setTimeout(() => this._setFeedback(""), 5000);
    },

    _escape(str) {
        return String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    },

    _menuCellHtml(isEnabled, menuKey, resId) {
        const cls = isEnabled ? 'text-success' : 'text-muted';
        const icon = isEnabled ? '<i class="fa fa-check" aria-hidden="true"></i>' : '<i class="fa fa-times" aria-hidden="true"></i>';
        return `<td class="text-center"><a href="#" class="menu-toggle ${cls}" data-menu="${menuKey}" data-res-id="${resId}" title="${menuKey}">${icon}</a></td>`;
    },

    _renderRowHtml(resource) {
        // Portal indicator small icon (not clickable)
        const portalCell = resource.has_portal
            ? `<td class="text-center portal-indicator" title="Portal: ${this._escape(resource.login || '—')}"><span class="portal-icon text-success"><i class="fa fa-check" aria-hidden="true"></i></span></td>`
            : `<td class="text-center portal-indicator" title="No portal access"><span class="portal-icon text-muted"><i class="fa fa-times" aria-hidden="true"></i></span></td>`;

        const projectsCell = this._menuCellHtml(resource.bc_projects_menu, 'bc_projects_menu', resource.res_id);
        const teamsCell = this._menuCellHtml(resource.bc_teams_menu, 'bc_teams_menu', resource.res_id);
        const partnerCell = this._menuCellHtml(resource.bc_partner_menu, 'bc_partner_menu', resource.res_id);
        const borCell = this._menuCellHtml(resource.bc_bor_menu, 'bc_bor_menu', resource.res_id);
        const resourceCell = this._menuCellHtml(resource.bc_resource_menu, 'bc_resource_menu', resource.res_id);

        const actionsHtml = `
            <td class="text-center">
                <div class="dropdown resource-action-dropdown d-inline-block">
                    <button class="btn btn-sm btn-light dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                        <i class="fa fa-cog" aria-hidden="true"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end">
                        <li><a class="dropdown-item btn-edit" href="#" data-res-id="${resource.res_id}" data-res-name="${this._escape(resource.res_name)}" data-res-email="${this._escape(resource.email)}">Edit Properties</a></li>
                        <li><a class="dropdown-item btn-delete text-danger" href="#" data-res-id="${resource.res_id}">Delete</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item btn-grant-portal-wizard" href="#" data-partner-id="${resource.res_id}">Grant portal access</a></li>
                    </ul>
                </div>
            </td>`;

        return `
            <tr data-res-id="${resource.res_id}">
                <td>${resource.res_id}</td>
                <td class="res-name">${this._escape(resource.res_name || "")}</td>
                <td class="res-email">${this._escape(resource.email || "")}</td>
                ${portalCell}
                ${projectsCell}
                ${teamsCell}
                ${partnerCell}
                ${borCell}
                ${resourceCell}
                ${actionsHtml}
            </tr>
        `;
    },

    _renderEmptyTbody() {
        return `<tr data-empty="true"><td colspan="10" class="text-center text-muted">No resources found.</td></tr>`;
    },

    _fillTable(resources) {
        const $tbody = this.$("#resources-tbody");
        if (!$tbody.length) return;
        if (!resources || !resources.length) {
            $tbody.html(this._renderEmptyTbody());
            return;
        }
        $tbody.html(resources.map(r => this._renderRowHtml(r)).join(''));
    },

    async _loadResources() {
        try {
            const res = await rpc("/partner/resources/data", {});
            if (!res || res.ok !== true) throw new Error((res && res.error) || "Failed to load resources");
            this.$("#partner-name").text(res.partner_name || "");
            this.$("#partner-id").text(res.partner_id || "");
            this._fillTable(res.resources);
        } catch (e) {
            console.error("[bcplanning] loadResources error:", e);
            this._setFeedback(e.message || "Error loading resources");
            this.$("#resources-tbody").html(this._renderEmptyTbody());
        }
    },

    /* RPC wrappers */
    _rpcCreate(name, email) { return rpc("/partner/resources/create", { name, email }); },
    _rpcUpdate(res_id, name, email) { return rpc("/partner/resources/update", { res_id, name, email }); },
    _rpcDelete(res_id) { return rpc("/partner/resources/delete", { res_id }); },
    _rpcGrantPortal(res_id, create = false) { return rpc("/partner/resources/grant_portal", { res_id, create }); },
    _rpcToggleMenu(res_id, menu_field, value) { return rpc("/partner/resources/toggle_menu", { res_id, menu_field, value }); },

    /* Events */
    _onAddResource(ev) { ev.preventDefault(); this._openModal({ title: "Add Resource" }); },

    _onEditResource(ev) {
        ev.preventDefault();
        const $a = $(ev.currentTarget);
        const $row = $a.closest("tr[data-res-id]");
        if (!$row.length) return;
        const resId = parseInt($row.data("res-id"), 10);
        const name = $row.find(".res-name").text().trim();
        const email = $row.find(".res-email").text().trim();
        this._openModal({ title: "Edit Resource", resId, name, email });
    },

    async _onDeleteResource(ev) {
        ev.preventDefault();
        const $row = $(ev.currentTarget).closest("tr[data-res-id]");
        if (!$row.length) return;
        const resId = parseInt($row.data("res-id"), 10);
        if (!confirm("Are you sure you want to delete this resource? This will remove any linked portal user(s).")) return;
        try {
            const out = await this._rpcDelete(resId);
            if (!out.ok) throw new Error(out.error || "Delete failed");
            $row.remove();
            if (!this.$("#resources-tbody").find("tr[data-res-id]").length) this.$("#resources-tbody").html(this._renderEmptyTbody());
            this._setFeedback("Resource deleted successfully.", false);
        } catch (e) {
            console.error("[bcplanning] delete error:", e);
            this._setFeedback(e.message || "Error deleting resource");
        }
    },

    async _onGrantPortal(ev) {
        // kept for compatibility (not used in actions menu)
        ev.preventDefault();
        const $row = $(ev.currentTarget).closest("tr[data-res-id]");
        if (!$row.length) return;
        const resId = parseInt($row.data("res-id"), 10);
        if (!confirm("Grant portal access to this resource?")) return;
        const $btn = $(ev.currentTarget);
        $btn.prop("disabled", true).text("Processing...");
        try {
            const out = await this._rpcGrantPortal(resId, false);
            if (!out.ok) throw new Error(out.error || out.message || "Grant portal failed");
            $row.find('.portal-indicator .portal-icon').removeClass('text-muted').addClass('text-success').html('<i class="fa fa-check" aria-hidden="true"></i>');
            $btn.prop("disabled", true).text("Portal granted");
            this._setFeedback(out.message || "Portal access granted.", false);
        } catch (e) {
            console.error("[bcplanning] grant portal error:", e);
            $btn.prop("disabled", false).text("Grant portal");
            this._setFeedback(e.message || "Error granting portal access");
        }
    },

    async _onGrantPortalWizard(ev) {
        ev.preventDefault();
        const $a = $(ev.currentTarget);
        const partnerId = parseInt($a.data("partner-id"), 10);
        if (!partnerId) return this._setFeedback("Partner id missing", true);
        if (!confirm("Grant portal access to this partner?")) return;
        $a.addClass('disabled').attr('aria-disabled', 'true');
        try {
            const out = await this._rpcGrantPortal(partnerId, false);
            if (!out || out.ok !== true) {
                const msg = (out && (out.error || out.message)) || "Grant portal failed";
                if (msg && msg.toLowerCase().includes('no existing user found')) {
                    if (confirm("No existing user found. Create & invite this user?")) {
                        const out2 = await this._rpcGrantPortal(partnerId, true);
                        if (!out2 || out2.ok !== true) throw new Error((out2 && (out2.error || out2.message)) || "Create & grant failed");
                        this.$(`tr[data-res-id="${partnerId}"]`).find('.portal-indicator .portal-icon').removeClass('text-muted').addClass('text-success').html('<i class="fa fa-check" aria-hidden="true"></i>');
                        this._setFeedback(out2.message || "Portal user created and invited.", false);
                        return;
                    } else {
                        this._setFeedback("Operation cancelled.", true);
                        return;
                    }
                }
                throw new Error(msg);
            }
            this.$(`tr[data-res-id="${partnerId}"]`).find('.portal-indicator .portal-icon').removeClass('text-muted').addClass('text-success').html('<i class="fa fa-check" aria-hidden="true"></i>');
            this._setFeedback(out.message || "Portal access granted.", false);
        } catch (err) {
            console.error("[bcplanning] grant portal wizard error:", err);
            this._setFeedback(err.message || "Grant portal failed");
        } finally {
            $a.removeClass('disabled').removeAttr('aria-disabled');
        }
    },

    async _onMenuToggle(ev) {
        ev.preventDefault();
        const $a = $(ev.currentTarget);
        const resId = parseInt($a.data("res-id"), 10);
        const menu = $a.data("menu");
        if (!resId || !menu) return;
        // disable while processing
        $a.addClass('disabled').attr('aria-disabled', 'true');
        const origHtml = $a.html();
        $a.html('<i class="fa fa-spinner fa-spin" aria-hidden="true"></i>');
        try {
            const isEnabled = $a.hasClass('text-success');
            const toValue = !isEnabled;
            const out = await this._rpcToggleMenu(resId, menu, toValue);
            if (!out || out.ok !== true) throw new Error((out && out.error) || 'Toggle failed');
            const serverVal = !!out.value;
            if (serverVal) {
                $a.removeClass('text-muted').addClass('text-success').html('<i class="fa fa-check" aria-hidden="true"></i>');
            } else {
                $a.removeClass('text-success').addClass('text-muted').html('<i class="fa fa-times" aria-hidden="true"></i>');
            }
            this._setFeedback('Updated setting', false);
        } catch (err) {
            console.error("[bcplanning] toggle menu error:", err);
            $a.html(origHtml);
            this._setFeedback(err.message || 'Failed updating setting');
        } finally {
            $a.removeClass('disabled').removeAttr('aria-disabled');
        }
    },

    _openModal({ title, resId = "", name = "", email = "" }) {
        const $modal = this.$("#resourceModal");
        if (!$modal.length) return;
        this.$("#resourceModalLabel").text(title);
        this.$("#resource-id").val(resId);
        this.$("#resource-name").val(name);
        this.$("#resource-email").val(email);
        this.$("#resource-form-feedback").text("");
        const modalEl = $modal[0];
        const hasBootstrap = typeof window.bootstrap !== "undefined" && window.bootstrap?.Modal;
        if (hasBootstrap) window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
        else {
            $modal.addClass("show").css("display", "block").attr("aria-hidden", null);
            this._modalDismissHandler = (ev) => {
                const $t = $(ev.target);
                if ($t.is('[data-bs-dismiss="modal"]') || $t.closest('[data-bs-dismiss="modal"]').length) {
                    ev.preventDefault(); this._closeModal();
                }
            };
            modalEl.addEventListener("click", this._modalDismissHandler);
            this._modalKeydownHandler = (ev) => { if (ev.key === "Escape" || ev.key === "Esc") this._closeModal(); };
            document.addEventListener("keydown", this._modalKeydownHandler);
        }
    },

    _closeModal() {
        const $modal = this.$("#resourceModal"); if (!$modal.length) return;
        const modalEl = $modal[0];
        const hasBootstrap = typeof window.bootstrap !== "undefined" && window.bootstrap?.Modal;
        if (hasBootstrap) window.bootstrap.Modal.getInstance(modalEl)?.hide();
        else {
            $modal.removeClass("show").css("display", "none").attr("aria-hidden", "true");
            if (this._modalDismissHandler) { modalEl.removeEventListener("click", this._modalDismissHandler); this._modalDismissHandler = null; }
            if (this._modalKeydownHandler) { document.removeEventListener("keydown", this._modalKeydownHandler); this._modalKeydownHandler = null; }
        }
    },

    async _onSubmitResourceForm(ev) {
        ev.preventDefault();
        const $feedback = this.$("#resource-form-feedback").text("");
        const resIdRaw = this.$("#resource-id").val();
        const name = (this.$("#resource-name").val() || "").trim();
        const email = (this.$("#resource-email").val() || "").trim();

        if (!name) { $feedback.text("Name is required."); return; }
        if (!email) { $feedback.text("Email is required."); return; }
        if (email.indexOf('@') === -1) { $feedback.text("Enter a valid email address."); return; }

        const isEdit = !!resIdRaw;
        try {
            const out = isEdit ? await this._rpcUpdate(parseInt(resIdRaw, 10), name, email) : await this._rpcCreate(name, email);
            if (!out.ok) throw new Error(out.error || "Operation failed");
            this._closeModal();
            if (isEdit) {
                const $row = this.$(`tr[data-res-id="${resIdRaw}"]`);
                $row.find(".res-name").text(out.resource.res_name || "");
                $row.find(".res-email").text(out.resource.email || "");
                this._setFeedback("Resource updated successfully.", false);
            } else {
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
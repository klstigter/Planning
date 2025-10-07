/** @odoo-module **/

import { jsonrpc } from "@web/core/network/rpc_service";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.ResourceTable = publicWidget.Widget.extend({
    selector: ".table.table-bordered", // Table containing planning lines

    events: {
        'click .remove-resource-row': '_onRemoveResourceRow',
        'click .add-resource-row': '_onAddResourceRow',
        'change .resource-select': '_onResourceChanged',
    },

    /**
     * Remove a planning line (resource row).
     * Triggers backend delete, then removes from DOM.
     */
    _onRemoveResourceRow: function(ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const $tr = $btn.closest('tr');
        const planninglineId = $tr.data('planninglineId');

        if (!planninglineId) {
            $tr.remove();
            return;
        }

        jsonrpc('/bcplanningline/delete', { planningline_id: planninglineId }).then(() => {
            $tr.fadeOut(200, function() { $tr.remove(); });
        });
    },

    /**
     * Add a new planning line (resource row) for the given task.
     * Triggers backend add, then inserts into DOM.
     */
    _onAddResourceRow: function(ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        // Find task_id (from closest parent row)
        const $taskRow = $btn.closest('tr').prevAll('tr').first();
        const taskId = $taskRow.data('taskId');
        if (!taskId) return;

        jsonrpc('/bcplanningline/add', { task_id: taskId }).then((result) => {
            // Insert new row after last planning line row
            const $table = $btn.closest('table');
            const $newRow = $(`
                <tr data-planningline-id="${result.planningline_id}">
                  <td>
                    <select class="resource-select">
                      ${result.resource_options}
                    </select>
                  </td>
                  <td style="padding-left: 32px;">
                    <button type="button" class="btn btn-sm btn-danger remove-resource-row" aria-label="Delete">
                      <i class="bi bi-x"></i>
                    </button>
                  </td>
                </tr>
            `);
            $table.find('tr').last().before($newRow);
        });
    },

    /**
     * Update the resource of a planning line.
     */
    _onResourceChanged: function(ev) {
        const $select = $(ev.currentTarget);
        const $tr = $select.closest('tr');
        const planninglineId = $tr.data('planninglineId');
        const resourceId = $select.val();

        if (!planninglineId) return;

        jsonrpc('/bcplanningline/update', {
            planningline_id: planninglineId,
            resource_id: resourceId
        }).then(() => {
            // Optionally show a success notification
        });
    },

    /**
     * On widget start, set data-planningline-id and data-task-id for rows.
     */
    start: function () {
        this.$('tr').each(function() {
            const $tr = $(this);
            // Set planningline_id
            const planninglineId = $tr.find('select.resource-select').data('planningline-id');
            if (planninglineId) {
                $tr.attr('data-planningline-id', planninglineId);
            }
            // Set task_id if available
            const taskId = $tr.find('td').first().data('task-id');
            if (taskId) {
                $tr.attr('data-task-id', taskId);
            }
        });
        return this._super.apply(this, arguments);
    },
});
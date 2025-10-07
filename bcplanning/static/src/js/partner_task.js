/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.ResourceTable = publicWidget.Widget.extend({
    selector: "#task_wrap",

    events: {
        'click .remove-resource-row': '_onRemoveResourceRow',
        'click .add-resource-row': '_onAddResourceRow',
        'change .resource-select': '_onResourceChanged',
    },

    _onRemoveResourceRow: function(ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const $tr = $btn.closest('tr');
        const planninglineId = $tr.data('planninglineId');

        if (!planninglineId) {
            $tr.remove();
            return;
        }

        rpc('/bcplanningline/delete', { planningline_id: planninglineId }).then(() => {
            $tr.fadeOut(200, function() { $tr.remove(); });
        });
    },

    _onAddResourceRow: function(ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        // Find the closest parent table with the attribute
        const $planningTable = $btn.closest('td').find('table[data-task-id]').first();
        let taskId = $planningTable.data('taskId');
        
        // If not found, go up from the button in case the button is not inside <td>
        if (!taskId) {
            taskId = $btn.closest('table[data-task-id]').data('taskId');
        }
        if (!taskId) {
            alert("Task ID not found!");
            return;
        }

        rpc('/bcplanningline/add', { task_id: taskId }).then((result) => {
            console.log(result);
            const $table = $btn.closest('table');
            const $newRow = $(`
                <tr>
                <td>
                    <span class="data_task_id" style="display:none">${result.planningline_id}</span>
                    <select class="resource-select">
                    <option value=""> - </option>
                    ${result.resource_options}
                    </select>
                </td>
                <td style="padding-left: 32px;">
                    <button type="button" class="btn btn-sm btn-secondary remove-resource-row">
                    Remove
                    </button>
                </td>
                </tr>
            `);
            $planningTable.find('tbody').append($newRow);
        });
    },

    // _onAddResourceRow: function(ev) {
    //     ev.preventDefault();
    //     const $btn = $(ev.currentTarget);

    //     // Find the closest planning line table with the data-task-id attribute
    //     const $planningTable = $btn.closest('td').find('table[data-task-id]').first();
    //     let taskId = $planningTable.data('taskId');        
    //     // If not found, go up from the button in case the button is not inside <td>
    //     if (!taskId) {
    //         taskId = $btn.closest('table[data-task-id]').data('taskId');
    //     }
    //     if (!taskId) {
    //         alert("Task ID not found!");
    //         return;
    //     }

    //     rpc('/bcplanningline/add', { task_id: taskId }).then((result) => {
    //         console.log(result);

    //         // Insert the new row into the planning lines table's tbody
    //         const $newRow = $(`
    //             <tr>
    //             <td>
    //                 <span class="data_task_id" style="display:none">${result.planningline_id}</span>
    //                 <select class="resource-select">
    //                 ${result.resource_options}
    //                 </select>
    //             </td>
    //             <td style="padding-left: 32px;">
    //                 <button type="button" class="btn btn-sm btn-danger remove-resource-row" aria-label="Delete">
    //                 <i class="bi bi-x"></i>
    //                 </button>
    //             </td>
    //             </tr>
    //         `);

    //         // Always append to tbody, not before the last row
    //         $planningTable.find('tbody').append($newRow);
    //     });
    // },

    _onResourceChanged: function(ev) {
        const $select = $(ev.currentTarget);
        const $td = $select.closest('td'); // Get current td
        const planninglineId = $td.find('.data_planningline_id').text().trim();
        const resourceId = $select.val();

        if (!planninglineId) return;

        rpc('/bcplanningline/update', {
            planningline_id: planninglineId,
            resource_id: resourceId
        }).then(function(result) {
            alert((result.result || 'Unknown result'));
        });
    },

    start: function () {
        this.$('tr').each(function() {
            const $tr = $(this);
            const planninglineId = $tr.find('select.resource-select').data('planningline-id');
            if (planninglineId) {
                $tr.attr('data-planningline-id', planninglineId);
            }
            const taskId = $tr.find('td').first().data('task-id');
            if (taskId) {
                $tr.attr('data-task-id', taskId);
            }
        });
        return this._super.apply(this, arguments);
    },
});
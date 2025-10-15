/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.ResourceTable = publicWidget.Widget.extend({
    selector: "#task_wrap",

    events: {
        'click .edit-row': '_onEditRow',
        'click .save-row': '_onSaveRow',
        'click .cancel-row': '_onCancelRow',
    },

    _onEditRow: function(ev) {
        const $btn = $(ev.currentTarget);
        const $tr = $btn.closest('tr.planningline-row');
        $tr.attr('data-editing', '1');
        // Hide views, show inputs
        $tr.find('.start-datetime-view, .end-datetime-view, .resource-view').addClass('d-none');
        $tr.find('.start-datetime-input, .end-datetime-input, .resource-select').removeClass('d-none');
        $tr.find('.edit-row').addClass('d-none');
        $tr.find('.save-row, .cancel-row').removeClass('d-none');
    },

    _onCancelRow: function(ev) {
        const $btn = $(ev.currentTarget);
        const $tr = $btn.closest('tr.planningline-row');
        $tr.attr('data-editing', '0');
        // Restore values from view
        $tr.find('.start-datetime-input').val(
            $tr.find('.start-datetime-input').attr('value')
        );
        $tr.find('.end-datetime-input').val(
            $tr.find('.end-datetime-input').attr('value')
        );
        $tr.find('.resource-select').val(
            $tr.find('.resource-select').find('option[selected]').val() || ''
        );
        // Hide inputs, show views
        $tr.find('.start-datetime-view, .end-datetime-view, .resource-view').removeClass('d-none');
        $tr.find('.start-datetime-input, .end-datetime-input, .resource-select').addClass('d-none');
        $tr.find('.edit-row').removeClass('d-none');
        $tr.find('.save-row, .cancel-row').addClass('d-none');
    },

    _onSaveRow: function(ev) {
        const $btn = $(ev.currentTarget);
        const $tr = $btn.closest('tr.planningline-row');
        const planninglineId = $tr.find('.data_planningline_id').text().trim();
        const startDatetime = $tr.find('.start-datetime-input').val();
        const endDatetime = $tr.find('.end-datetime-input').val();
        const resourceId = $tr.find('.resource-select').val();

        rpc('/bcplanningline/save', {
            planningline_id: planninglineId,
            start_datetime: startDatetime,
            end_datetime: endDatetime,
            resource_id: resourceId,
        }).then(function(result) {
            if (result.result === 'updated') {
                $tr.find('.start-datetime-view').text(startDatetime ? startDatetime.replace('T', ' ') : '');
                $tr.find('.end-datetime-view').text(endDatetime ? endDatetime.replace('T', ' ') : '');
                $tr.find('.resource-view').text($tr.find('.resource-select option:selected').text());
                $tr.attr('data-editing', '0');
                $tr.find('.start-datetime-view, .end-datetime-view, .resource-view').removeClass('d-none');
                $tr.find('.start-datetime-input, .end-datetime-input, .resource-select').addClass('d-none');
                $tr.find('.edit-row').removeClass('d-none');
                $tr.find('.save-row, .cancel-row').addClass('d-none');
                // Show success alert ONLY after full success
                alert('Data updated successfully.');
            } else {
                alert(result.result || 'Update failed');
                if (result.old_start_datetime !== undefined) {
                    $tr.find('.start-datetime-input').val(result.old_start_datetime);
                }
                if (result.old_end_datetime !== undefined) {
                    $tr.find('.end-datetime-input').val(result.old_end_datetime);
                }
                if (result.old_resource_id !== undefined) {
                    $tr.find('.resource-select').val(result.old_resource_id);
                }
            }
        });
    },
});
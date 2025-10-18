/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.ResourceTable = publicWidget.Widget.extend({
    selector: "#task_wrap",

    events: {
        'click .edit-row': '_onEditRow',
        'click .save-row': '_onSaveRow',
        'click .cancel-row': '_onCancelRow',
        'click #btn-prev-day': '_onPrevDay',
        'click #btn-next-day': '_onNextDay',
        'click #btn-today': '_onTodayClick',
        'click #btn-clear': '_onClearClick',
    },

    start: function () {
        this._super.apply(this, arguments);
        const params = new URLSearchParams(window.location.search);
        const urlDate = params.get('date');
        const noDate = params.get('no_date');
        const lbl = this.el.querySelector('#selected-date-label');

        if (urlDate) {
            this._currentDate = this._parseDateString(urlDate);
            if (lbl) { lbl.textContent = urlDate; }
        } else if (noDate) {
            // explicit no-date requested -> show special message
            this._currentDate = new Date(); // internal default for prev/next
            if (lbl) { lbl.textContent = "No filtered on Start Date"; }
        } else {
            // default behavior: no params -> use today filter
            this._currentDate = new Date();
            if (lbl) { lbl.textContent = this._formatDate(this._currentDate); }
        }

        if (!(this._currentDate instanceof Date) || isNaN(this._currentDate)) {
            this._currentDate = new Date();
            if (lbl) { lbl.textContent = this._formatDate(this._currentDate); }
        }
    },

    // helpers
    _formatDate: function (d) {
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    },

    _parseDateString: function (s) {
        const parts = (s || '').split('-');
        if (parts.length !== 3) { return new Date(); }
        const y = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10) - 1;
        const d = parseInt(parts[2], 10);
        return new Date(y, m, d);
    },

    _changeDateAndReload: function (dateObj) {
        this._currentDate = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate());
        const params = new URLSearchParams(window.location.search);
        // remove no_date if present when selecting an explicit date
        if (params.has('no_date')) { params.delete('no_date'); }
        params.set('date', this._formatDate(this._currentDate));
        window.location.search = params.toString();
    },

    // toolbar handlers
    _onPrevDay: function (ev) {
        ev.preventDefault();
        const d = new Date(this._currentDate);
        d.setDate(d.getDate() - 1);
        this._changeDateAndReload(d);
    },

    _onNextDay: function (ev) {
        ev.preventDefault();
        const d = new Date(this._currentDate);
        d.setDate(d.getDate() + 1);
        this._changeDateAndReload(d);
    },

    _onTodayClick: function (ev) {
        ev.preventDefault();
        // Robust native picker opener
        var existing = document.getElementById('__bcplanning_date_picker');
        if (existing) {
            if (typeof existing.showPicker === 'function') {
                try { existing.showPicker(); } catch (e) { existing.focus(); existing.click(); }
            } else {
                existing.focus();
                existing.click();
            }
            return;
        }

        var btn = ev.currentTarget;
        var rect = btn && btn.getBoundingClientRect ? btn.getBoundingClientRect() : { left: 10, bottom: 10 };
        var inp = document.createElement('input');
        inp.type = 'date';
        inp.id = '__bcplanning_date_picker';
        inp.style.position = 'absolute';
        inp.style.top = (rect.bottom + window.scrollY + 4) + 'px';
        inp.style.left = (rect.left + window.scrollX) + 'px';
        inp.style.zIndex = 2147483647;
        inp.style.width = '1px';
        inp.style.height = '1px';
        inp.style.padding = '0';
        inp.style.border = 'none';
        inp.style.background = 'transparent';
        inp.style.opacity = '0';
        try {
            inp.value = this._formatDate(this._currentDate || new Date());
        } catch (e) {
            inp.value = '';
        }

        document.body.appendChild(inp);
        var self = this;
        var cleanup = function () {
            try { if (inp && inp.parentNode) inp.parentNode.removeChild(inp); } catch (e) {}
        };
        inp.addEventListener('change', function (ev2) {
            var val = ev2.target.value;
            if (val) {
                var picked = self._parseDateString(val);
                self._changeDateAndReload(picked);
            }
            setTimeout(cleanup, 0);
        });
        inp.addEventListener('blur', function () {
            setTimeout(cleanup, 300);
        });
        if (typeof inp.showPicker === 'function') {
            try {
                inp.showPicker();
            } catch (e) {
                inp.focus();
                inp.click();
            }
        } else {
            inp.focus();
            inp.click();
        }
    },

    /**
     * Clear date filter — set no_date=1 and remove date param, then reload.
     */
    _onClearClick: function (ev) {
        ev.preventDefault();
        const params = new URLSearchParams(window.location.search);
        if (params.has('date')) { params.delete('date'); }
        // Set no_date flag so server will return all records and selected_date=''
        params.set('no_date', '1');
        window.location.search = '?' + params.toString();
    },

    // helper: find context (row or card) for a clicked button
    _getContextElement: function ($btn) {
        const $tr = $btn.closest('tr.planningline-row');
        if ($tr && $tr.length) {
            return { type: 'row', el: $tr };
        }
        const $card = $btn.closest('.mobile-planning-card');
        if ($card && $card.length) {
            return { type: 'card', el: $card };
        }
        return { type: null, el: null };
    },

    _onEditRow: function (ev) {
        const $btn = $(ev.currentTarget);
        const ctx = this._getContextElement($btn);
        if (ctx.type === 'row') {
            const $tr = ctx.el;
            $tr.attr('data-editing', '1');
            $tr.find('.start-datetime-view, .end-datetime-view, .resource-view').addClass('d-none');
            $tr.find('.start-datetime-input, .end-datetime-input, .resource-select').removeClass('d-none');
            $tr.find('.edit-row').addClass('d-none');
            $tr.find('.save-row, .cancel-row').removeClass('d-none');
        } else if (ctx.type === 'card') {
            const $card = ctx.el;
            $card.find('.start-datetime-view, .end-datetime-view, .resource-view').addClass('d-none');
            $card.find('.start-datetime-input, .end-datetime-input, .resource-select').removeClass('d-none');
            $card.find('.edit-row').addClass('d-none');
            $card.find('.save-row, .cancel-row').removeClass('d-none');
            $card.attr('data-editing', '1');
        } else {
            console.warn('Edit button context not found');
        }
    },

    _onCancelRow: function (ev) {
        const $btn = $(ev.currentTarget);
        const ctx = this._getContextElement($btn);
        if (ctx.type === 'row') {
            const $tr = ctx.el;
            $tr.attr('data-editing', '0');
            $tr.find('.start-datetime-input').val($tr.find('.start-datetime-input').attr('value'));
            $tr.find('.end-datetime-input').val($tr.find('.end-datetime-input').attr('value'));
            $tr.find('.resource-select').val($tr.find('.resource-select').find('option[selected]').val() || '');
            $tr.find('.start-datetime-view, .end-datetime-view, .resource-view').removeClass('d-none');
            $tr.find('.start-datetime-input, .end-datetime-input, .resource-select').addClass('d-none');
            $tr.find('.edit-row').removeClass('d-none');
            $tr.find('.save-row, .cancel-row').addClass('d-none');
        } else if (ctx.type === 'card') {
            const $card = ctx.el;
            $card.attr('data-editing', '0');
            $card.find('.start-datetime-input').val($card.find('.start-datetime-input').attr('value'));
            $card.find('.end-datetime-input').val($card.find('.end-datetime-input').attr('value'));
            $card.find('.resource-select').val($card.find('.resource-select').find('option[selected]').val() || '');
            $card.find('.start-datetime-view, .end-datetime-view, .resource-view').removeClass('d-none');
            $card.find('.start-datetime-input, .end-datetime-input, .resource-select').addClass('d-none');
            $card.find('.edit-row').removeClass('d-none');
            $card.find('.save-row, .cancel-row').removeClass('d-none'); // keep consistent
        } else {
            console.warn('Cancel button context not found');
        }
    },

    _onSaveRow: function (ev) {
        const $btn = $(ev.currentTarget);
        const ctx = this._getContextElement($btn);
        let planninglineId, startDatetime, endDatetime, resourceId;
        let $contextEl;

        if (ctx.type === 'row') {
            $contextEl = ctx.el;
            planninglineId = $contextEl.find('.data_planningline_id').text().trim();
            startDatetime = $contextEl.find('.start-datetime-input').val();
            endDatetime = $contextEl.find('.end-datetime-input').val();
            resourceId = $contextEl.find('.resource-select').val();
        } else if (ctx.type === 'card') {
            $contextEl = ctx.el;
            planninglineId = $contextEl.find('.data_planningline_id').text().trim();
            startDatetime = $contextEl.find('.start-datetime-input').val();
            endDatetime = $contextEl.find('.end-datetime-input').val();
            resourceId = $contextEl.find('.resource-select').val();
        } else {
            console.warn('Save button context not found');
            return;
        }

        // Basic validation
        if (!planninglineId) {
            alert('Planning line id not available. Cannot save.');
            return;
        }

        // call JSON-RPC controller
        rpc('/bcplanningline/save', {
            planningline_id: planninglineId,
            start_datetime: startDatetime,
            end_datetime: endDatetime,
            resource_id: resourceId,
        }).then(function(result) {
            if (result && result.result === 'updated') {
                // success: update view text & hide inputs
                $contextEl.find('.start-datetime-view').text(startDatetime ? startDatetime.replace('T', ' ') : '');
                $contextEl.find('.end-datetime-view').text(endDatetime ? endDatetime.replace('T', ' ') : '');
                $contextEl.find('.resource-view').text($contextEl.find('.resource-select option:selected').text());
                $contextEl.attr('data-editing', '0');
                $contextEl.find('.start-datetime-view, .end-datetime-view, .resource-view').removeClass('d-none');
                $contextEl.find('.start-datetime-input, .end-datetime-input, .resource-select').addClass('d-none');
                $contextEl.find('.edit-row').removeClass('d-none');
                $contextEl.find('.save-row, .cancel-row').addClass('d-none');
                alert('Data updated successfully.');
            } else {
                // Show server-provided message if present
                const msg = (result && result.result) ? result.result : 'Update failed';
                alert(msg);
                if (result && result.old_start_datetime !== undefined) {
                    $contextEl.find('.start-datetime-input').val(result.old_start_datetime);
                }
                if (result && result.old_end_datetime !== undefined) {
                    $contextEl.find('.end-datetime-input').val(result.old_end_datetime);
                }
                if (result && result.old_resource_id !== undefined) {
                    $contextEl.find('.resource-select').val(result.old_resource_id);
                }
            }
        }).catch(function (err) {
            console.error('RPC error (network or server):', err);
            // Attempt to show meaningful server-side message if present
            var userMsg = 'Update failed (network or permissions).';
            try {
                if (err && err.data && err.data.message) {
                    userMsg = err.data.message;
                } else if (err && err.data && err.data.debug && typeof err.data.debug === 'string') {
                    // sometimes Odoo returns a debug string with the exception message
                    // show the first line to keep it readable
                    userMsg = err.data.debug.split('\n')[0];
                }
            } catch (e) {
                // ignore parsing errors
            }
            alert(userMsg);
        });
    },

});
/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.Bor = publicWidget.Widget.extend({
    selector: "#bor_wrap",

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
            this._currentDate = new Date();
            if (lbl) { lbl.textContent = ''; }
        } else {
            this._currentDate = new Date();
            if (lbl) { lbl.textContent = this._formatDate(this._currentDate); }
        }

        if (!(this._currentDate instanceof Date) || isNaN(this._currentDate)) {
            this._currentDate = new Date();
            if (lbl) { lbl.textContent = this._formatDate(this._currentDate); }
        }
    },

    _showOverlay: function () {
        var el = document.getElementById('bcplanning-overlay');
        if (el) { el.classList.remove('d-none'); }
    },
    _hideOverlay: function () {
        var el = document.getElementById('bcplanning-overlay');
        if (el) { el.classList.add('d-none'); }
    },

    _setContextButtonsDisabled: function ($contextEl, disabled) {
        try {
            $contextEl.find('button, input, select').prop('disabled', !!disabled);
        } catch (e) {
            // ignore
        }
    },

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
        if (params.has('no_date')) { params.delete('no_date'); }
        params.set('date', this._formatDate(this._currentDate));
        window.location.search = params.toString();
    },

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

    _onClearClick: function (ev) {
        ev.preventDefault();
        const params = new URLSearchParams(window.location.search);
        if (params.has('date')) { params.delete('date'); }
        params.set('no_date', '1');
        window.location.search = '?' + params.toString();
    },

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

    // Build full datetime string "YYYY-MM-DDTHH:MM:SS" from time-only input and stored date metadata.
    _buildDatetimeFromTime: function ($contextEl, viewSelector, timeValue, defaultDateFallback) {
        // If empty or falsy, return null (we'll send null to indicate no change)
        if (!timeValue) { return null; }

        // Prefer data-date attribute on the view element
        let $view = $contextEl.find(viewSelector);
        let datePart = $view.attr('data-start-date') || $view.attr('data-end-date') || '';
        // fallback to full-datetime attribute and extract date
        if (!datePart) {
            let full = $view.attr('data-start-datetime') || $view.attr('data-end-datetime') || '';
            if (full && full.indexOf('T') !== -1) {
                datePart = full.split('T')[0];
            } else if (full && full.indexOf(' ') !== -1) {
                datePart = full.split(' ')[0];
            }
        }
        // fallback to page-selected date (if page filtered by date)
        if (!datePart && defaultDateFallback) {
            datePart = defaultDateFallback;
        }
        // final fallback: today
        if (!datePart) {
            const d = new Date();
            datePart = d.toISOString().slice(0,10);
        }
        // timeValue is expected "HH:MM" (24h). Append seconds to send canonical "HH:MM:SS"
        // Ensure timeValue is two-component "HH:MM"
        const timeParts = (timeValue || '').split(':');
        let hhmm = timeValue;
        if (timeParts.length >= 2) {
            hhmm = `${String(timeParts[0]).padStart(2,'0')}:${String(timeParts[1]).padStart(2,'0')}`;
        } else {
            // if user entered single number, normalize to HH:00
            hhmm = `${String(timeValue).padStart(2,'0')}:00`;
        }
        // Return canonical ISO-like datetime with seconds
        return `${datePart}T${hhmm}:00`;
    },

    _onEditRow: function (ev) {
        const $btn = $(ev.currentTarget);
        const ctx = this._getContextElement($btn);
        if (ctx.type === 'row') {
            const $tr = ctx.el;
            $tr.attr('data-editing', '1');
            $tr.find('.start-datetime-view, .end-datetime-view, .product-view, .qty-view, .depth-view').addClass('d-none');
            $tr.find('.start-datetime-input, .end-datetime-input, .product-select, .qty-input, .depth-input').removeClass('d-none');
            $tr.find('.edit-row').addClass('d-none');
            $tr.find('.save-row, .cancel-row').removeClass('d-none');
        } else if (ctx.type === 'card') {
            const $card = ctx.el;
            $card.find('.start-datetime-view, .end-datetime-view, .product-view, .qty-view, .depth-view').addClass('d-none');
            $card.find('.start-datetime-input, .end-datetime-input, .product-select, .qty-input, .depth-input').removeClass('d-none');
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
            $tr.find('.product-select').val($tr.find('.product-select').find('option[selected]').val() || '');
            $tr.find('.qty-input').val($tr.find('.qty-input').attr('value'));
            $tr.find('.depth-input').val($tr.find('.depth-input').attr('value'));

            $tr.find('.start-datetime-view, .end-datetime-view, .product-view, .qty-view, .depth-view').removeClass('d-none');
            $tr.find('.start-datetime-input, .end-datetime-input, .product-select, .qty-input, .depth-input').addClass('d-none');
            $tr.find('.edit-row').removeClass('d-none');
            $tr.find('.save-row, .cancel-row').addClass('d-none');
        } else if (ctx.type === 'card') {
            const $card = ctx.el;
            $card.attr('data-editing', '0');
            $card.find('.start-datetime-input').val($card.find('.start-datetime-input').attr('value'));
            $card.find('.end-datetime-input').val($card.find('.end-datetime-input').attr('value'));
            $card.find('.product-select').val($card.find('.product-select').find('option[selected]').val() || '');
            $card.find('.qty-input').val($card.find('.qty-input').attr('value'));
            $card.find('.depth-input').val($card.find('.depth-input').attr('value'));

            $card.find('.start-datetime-view, .end-datetime-view, .product-view, .qty-view, .depth-view').removeClass('d-none');
            $card.find('.start-datetime-input, .end-datetime-input, .product-select, .qty-input, .depth-input').addClass('d-none');
            $card.find('.edit-row').removeClass('d-none');
            $card.find('.save-row, .cancel-row').addClass('d-none');
        } else {
            console.warn('Cancel button context not found');
        }
    },

    _onSaveRow: function (ev) {
        const $btn = $(ev.currentTarget);
        const ctx = this._getContextElement($btn);
        let planninglineId, startTime, endTime, resourceId;
        let productId, qtyVal, depthVal;
        let $contextEl;

        if (ctx.type === 'row') {
            $contextEl = ctx.el;
            planninglineId = $contextEl.find('.data_planningline_id').text().trim();
            startTime = $contextEl.find('.start-datetime-input').val(); // "HH:MM"
            endTime = $contextEl.find('.end-datetime-input').val();     // "HH:MM"
            resourceId = $contextEl.find('.resource-select').val(); // if used elsewhere
            productId = $contextEl.find('.product-select').val();
            qtyVal = $contextEl.find('.qty-input').val();
            depthVal = $contextEl.find('.depth-input').val();
        } else if (ctx.type === 'card') {
            $contextEl = ctx.el;
            planninglineId = $contextEl.find('.data_planningline_id').text().trim();
            startTime = $contextEl.find('.start-datetime-input').val();
            endTime = $contextEl.find('.end-datetime-input').val();
            resourceId = $contextEl.find('.resource-select').val();
            productId = $contextEl.find('.product-select').val();
            qtyVal = $contextEl.find('.qty-input').val();
            depthVal = $contextEl.find('.depth-input').val();
        } else {
            console.warn('Save button context not found');
            return;
        }

        if (!planninglineId) {
            alert('Planning line id not available. Cannot save.');
            return;
        }

        // Build full datetime strings (ISO-like) using date metadata + time-only inputs.
        const pageDateText = (document.querySelector('#selected-date-label') && document.querySelector('#selected-date-label').textContent) ? document.querySelector('#selected-date-label').textContent.trim() : '';
        const fallbackDate = (pageDateText && pageDateText !== 'All dates') ? pageDateText : null;

        const startDatetime = this._buildDatetimeFromTime($contextEl, '.start-datetime-view', startTime, fallbackDate); // "YYYY-MM-DDTHH:MM:SS" or null
        const endDatetime = this._buildDatetimeFromTime($contextEl, '.end-datetime-view', endTime, fallbackDate);     // "YYYY-MM-DDTHH:MM:SS" or null

        // show spinner and disable controls to prevent multi-click
        this._showOverlay();
        this._setContextButtonsDisabled($contextEl, true);
        $btn.prop('disabled', true);

        const self = this;
        // NOTE: call the controller route you told me to keep: '/planningline/bor/save'
        rpc('/planningline/bor/save', {
            planningline_id: planninglineId,
            // send datetime strings or null (controller will be tolerant)
            start_datetime: startDatetime,
            end_datetime: endDatetime,
            product_id: productId,
            qty: qtyVal,
            depth: depthVal,
        }).then(function(result) {
            if (result && result.result === 'updated') {
                // update UI: times (as before)
                if (startTime !== undefined) {
                    $contextEl.find('.start-datetime-view').text(startTime ? startTime : '');
                    const newStart = (result && result.new_start_datetime) ? result.new_start_datetime : startDatetime;
                    if (newStart) {
                        const parts = newStart.split('T');
                        $contextEl.find('.start-datetime-view').attr('data-start-datetime', newStart);
                        $contextEl.find('.start-datetime-view').attr('data-start-date', parts[0]);
                    } else if (startDatetime) {
                        const parts = startDatetime.split('T');
                        $contextEl.find('.start-datetime-view').attr('data-start-datetime', startDatetime);
                        $contextEl.find('.start-datetime-view').attr('data-start-date', parts[0]);
                    }
                }
                if (endTime !== undefined) {
                    $contextEl.find('.end-datetime-view').text(endTime ? endTime : '');
                    const newEnd = (result && result.new_end_datetime) ? result.new_end_datetime : endDatetime;
                    if (newEnd) {
                        const parts = newEnd.split('T');
                        $contextEl.find('.end-datetime-view').attr('data-end-datetime', newEnd);
                        $contextEl.find('.end-datetime-view').attr('data-end-date', parts[0]);
                    } else if (endDatetime) {
                        const parts = endDatetime.split('T');
                        $contextEl.find('.end-datetime-view').attr('data-end-datetime', endDatetime);
                        $contextEl.find('.end-datetime-view').attr('data-end-date', parts[0]);
                    }
                }

                // update product, qty, depth UI
                try {
                    const newProd = (result && result.new_pl_product_id) ? result.new_pl_product_id : productId;
                    if (newProd !== undefined && newProd !== null) {
                        const optText = $contextEl.find('.product-select option[value="' + newProd + '"]').text() || '-';
                        $contextEl.find('.product-view').text(optText);
                        $contextEl.find('.product-select').val(newProd);
                    }
                    const newQty = (result && (result.new_pl_qty !== undefined)) ? result.new_pl_qty : qtyVal;
                    if (newQty !== undefined && newQty !== null) {
                        $contextEl.find('.qty-view').text(newQty);
                        $contextEl.find('.qty-input').val(newQty);
                        $contextEl.find('.qty-input').attr('value', newQty);
                    }
                    const newDepth = (result && (result.new_pl_depth !== undefined)) ? result.new_pl_depth : depthVal;
                    if (newDepth !== undefined && newDepth !== null) {
                        $contextEl.find('.depth-view').text(newDepth);
                        $contextEl.find('.depth-input').val(newDepth);
                        $contextEl.find('.depth-input').attr('value', newDepth);
                    }
                } catch (e) {
                    console.error('Error updating product/qty/depth after save', e);
                }

                // restore normal view mode
                $contextEl.attr('data-editing', '0');
                $contextEl.find('.start-datetime-view, .end-datetime-view, .product-view, .qty-view, .depth-view').removeClass('d-none');
                $contextEl.find('.start-datetime-input, .end-datetime-input, .product-select, .qty-input, .depth-input').addClass('d-none');
                $contextEl.find('.edit-row').removeClass('d-none');
                $contextEl.find('.save-row, .cancel-row').addClass('d-none');
                alert('Data updated successfully.');
                return;
            }

            // failure path...
            const msg = (result && result.result) ? result.result : 'Update failed';
            alert(msg);

            try {
                if (result && result.old_start_datetime !== undefined) {
                    let old = result.old_start_datetime || '';
                    let timeOnly = '';
                    let dateOnly = '';
                    if (old.indexOf('T') !== -1) {
                        const parts = old.split('T');
                        dateOnly = parts[0];
                        timeOnly = (parts[1] || '').slice(0,5);
                    } else {
                        timeOnly = old.slice(0,5);
                    }
                    $contextEl.find('.start-datetime-input').val(timeOnly);
                    $contextEl.find('.start-datetime-input').attr('value', timeOnly);
                    $contextEl.find('.start-datetime-view').text(timeOnly ? timeOnly : '');
                    if (dateOnly) {
                        $contextEl.find('.start-datetime-view').attr('data-start-date', dateOnly);
                        $contextEl.find('.start-datetime-view').attr('data-start-datetime', result.old_start_datetime);
                    }
                }
                if (result && result.old_end_datetime !== undefined) {
                    let old = result.old_end_datetime || '';
                    let timeOnly = '';
                    let dateOnly = '';
                    if (old.indexOf('T') !== -1) {
                        const parts = old.split('T');
                        dateOnly = parts[0];
                        timeOnly = (parts[1] || '').slice(0,5);
                    } else {
                        timeOnly = old.slice(0,5);
                    }
                    $contextEl.find('.end-datetime-input').val(timeOnly);
                    $contextEl.find('.end-datetime-input').attr('value', timeOnly);
                    $contextEl.find('.end-datetime-view').text(timeOnly ? timeOnly : '');
                    if (dateOnly) {
                        $contextEl.find('.end-datetime-view').attr('data-end-date', dateOnly);
                        $contextEl.find('.end-datetime-view').attr('data-end-datetime', result.old_end_datetime);
                    }
                }

                if (result && result.old_pl_product_id !== undefined) {
                    const oldProd = result.old_pl_product_id || '';
                    const optText = $contextEl.find('.product-select option[value="' + oldProd + '"]').text() || '-';
                    $contextEl.find('.product-select').val(oldProd);
                    $contextEl.find('.product-view').text(optText);
                } else {
                    $contextEl.find('.product-select').val($contextEl.find('.product-select').find('option[selected]').val() || '');
                }

                if (result && result.old_pl_qty !== undefined) {
                    $contextEl.find('.qty-input').val(result.old_pl_qty);
                    $contextEl.find('.qty-input').attr('value', result.old_pl_qty);
                    $contextEl.find('.qty-view').text(result.old_pl_qty);
                } else {
                    $contextEl.find('.qty-input').val($contextEl.find('.qty-input').attr('value'));
                }

                if (result && result.old_pl_depth !== undefined) {
                    $contextEl.find('.depth-input').val(result.old_pl_depth);
                    $contextEl.find('.depth-input').attr('value', result.old_pl_depth);
                    $contextEl.find('.depth-view').text(result.old_pl_depth);
                } else {
                    $contextEl.find('.depth-input').val($contextEl.find('.depth-input').attr('value'));
                }

            } catch (e) {
                console.error('Error restoring values after failed save', e);
            }

            try {
                $contextEl.find('.cancel-row').trigger('click');
            } catch (e) {
                console.error('Error triggering cancel after failure', e);
            }
        }).catch(function (err) {
            console.error('RPC error (network or server):', err);
            var userMsg = 'Update failed (network or permissions).';
            try {
                if (err && err.data && err.data.message) {
                    userMsg = err.data.message;
                } else if (err && err.data && err.data.debug && typeof err.data.debug === 'string') {
                    userMsg = err.data.debug.split('\n')[0];
                }
            } catch (e) {}
            alert(userMsg);
            try {
                $contextEl.find('.cancel-row').trigger('click');
            } catch (e) {
                console.error('Error triggering cancel after RPC error', e);
            }
        }).finally(function() {
            try {
                self._hideOverlay();
                self._setContextButtonsDisabled($contextEl, false);
                $btn.prop('disabled', false);
            } catch (e) {
                console.error('Error hiding overlay / re-enabling buttons', e);
            }
        });
    },

});
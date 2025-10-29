from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied, ValidationError
import json
from odoo.http import Response
import time
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

import psycopg2
from psycopg2 import errorcodes


class BorApiController(http.Controller):

    @http.route('/partner/bor', type='http', auth='user', website=True)
    def partner_bor(self, job_id=None, job_no=None, job_name=None, date=None, **kwargs):
        """
        Behavior:
        - If ?date=YYYY-MM-DD present -> filter by that date.
        - Else if ?no_date=1 present -> DO NOT apply date filter (show all).
        - Else (no date param, no no_date) -> default to today's date filter.
        """
        user = request.env.user

        # Get Vendor from res.partner (adapt if your mapping differs)
        vendors = []
        if user.partner_id.parent_id:
            vendors = request.env['res.partner'].sudo().search([('id', '=', user.partner_id.parent_id.id)], limit=1)
        else:
            vendors = request.env['res.partner'].sudo().search([('id', '=', user.partner_id.id)], limit=1)
        if not vendors:
            datas = {
                'message_title': "No vendor mapping",
                'message_text': "No vendor mapping found for your account. Please contact your administrator.",
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)

        vendor = vendors[0]
        partner_id = vendor.id

        # Detect parameters
        date_str = request.params.get('date') or date
        no_date_flag = request.params.get('no_date')

        date_filter = False
        selected_date = None

        if date_str:
            # explicit date provided in URL
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                date_filter = True
            except Exception:
                # invalid date -> fallback to today's filter
                selected_date = datetime.now().date()
                date_filter = True
        elif no_date_flag:
            # explicit "no date" requested -> show all records
            date_filter = False
            selected_date = None
        else:
            # no params -> default to today's date filter
            selected_date = datetime.now().date()
            date_filter = True

        if date_filter and selected_date:
            start_dt_str = f"{selected_date.strftime('%Y-%m-%d')} 00:00:00"
            end_dt_str = f"{selected_date.strftime('%Y-%m-%d')} 23:59:59"

        # Build domains conditionally
        task_data = []
        project_data = []

        # If a specific job_id is requested
        if job_id:
            project = request.env['bcproject'].with_user(user.id).search([('id', '=', int(job_id))], limit=1)
            if not project:
                raise ValidationError(f"Project {job_no} for user {user.name} is not found!")

            pl_domain = [
                ('task_id.job_id.id', '=', project.id),
                ('vendor_id', '=', partner_id),
                ('resource_id', '=', user.partner_id.id)  # filter planning line per resource
            ]
            if date_filter:
                pl_domain += [('start_datetime', '>=', start_dt_str), ('start_datetime', '<=', end_dt_str)]

            planninglines = request.env['bcplanningline'].with_user(user.id).search(pl_domain)
            if planninglines:
                task_ids = planninglines.mapped('task_id.id')
                tasks = request.env['bctask'].with_user(user.id).search([('id', 'in', task_ids)])
            else:
                tasks = request.env['bctask'].with_user(user.id).browse([])
        else:
            # all planninglines for this vendor (maybe filtered by date)
            pl_domain = [
                ('vendor_id', '=', partner_id),
                ('resource_id', '=', user.partner_id.id)  # filter planning line per resource
            ]
            if date_filter:
                pl_domain += [('start_datetime', '>=', start_dt_str), ('start_datetime', '<=', end_dt_str)]

            planninglines = request.env['bcplanningline'].with_user(user.id).search(pl_domain)
            job_ids = planninglines.mapped('job_id.id')
            projects = request.env['bcproject'].with_user(user.id).search([('id', 'in', job_ids)]) if job_ids else request.env['bcproject'].with_user(user.id).browse([])
            tasks = request.env['bctask'].with_user(user.id).search([('id', 'in', planninglines.mapped('task_id.id'))]) if planninglines else request.env['bctask'].with_user(user.id).browse([])

            # Build project_data (same logic as before)
            if projects:
                for p in projects:
                    pl_for_project_domain = [
                        ('task_id.job_id.id', '=', p.id),
                        ('vendor_id', '=', vendor.id),
                    ]
                    if date_filter:
                        pl_for_project_domain += [('start_datetime', '>=', start_dt_str), ('start_datetime', '<=', end_dt_str)]
                    pl_for_project = request.env['bcplanningline'].with_user(user.id).search(pl_for_project_domain)
                    if pl_for_project:
                        task_ids = pl_for_project.mapped('task_id.id')
                        project_data.append({
                            'id': p.id,
                            'job_no': p.job_no or '-',
                            'job_desc': p.job_desc or '-',
                            'task_count': len(task_ids),
                            'partner_name': (request.env['res.partner'].sudo().browse(vendor.id).name if vendor else ''),
                        })

        # Build task data (include planning lines only if they match date filter when enabled)
        for t in tasks:
            pl_data = []
            pl_domain = [
                ('task_id', '=', t.id),
                ('vendor_id', '=', partner_id),
                ('resource_id', '=', user.partner_id.id),  # filter planning line per resource
            ]
            if date_filter:
                pl_domain += [('start_datetime', '>=', start_dt_str), ('start_datetime', '<=', end_dt_str)]

            earliest_start = False
            planninglines = request.env['bcplanningline'].with_user(user.id).search(pl_domain)
            if planninglines:
                for pl in planninglines:
                    pl_data.append({
                        'id': pl.id,
                        'pl_no': pl.planning_line_no,
                        'pl_desc': pl.planning_line_desc,
                        'pl_resource_id': pl.resource_id.id if pl.resource_id else None,
                        'pl_start_datetime': pl.start_datetime,
                        'pl_end_datetime': pl.end_datetime,
                        'pl_product_id': pl.product_id.id if pl.product_id else None,
                        'pl_qty': pl.quantity,
                        'pl_depth': pl.depth,
                    })

                # Compute earliest start for this set of planning lines (when date_filter is applied, earliest among filtered lines)
                starts = [pl.start_datetime for pl in planninglines if pl.start_datetime]
                if starts:
                    earliest_start = min(starts)
            else:
                earliest_start = t.earliest_start_datetime or False

            task_data.append({
                'id': t.id,
                'task_no': t.task_no,
                'task_desc': t.task_desc,
                'job_no': t.job_id.job_no,
                'planningline_count': len(planninglines),
                'planninglines': pl_data,
                'earliest_start': earliest_start,
            })

        # Products
        product_data = []
        products = request.env['product.product'].sudo().search([('product_tmpl_id.type', '=', 'service'), ('active', '=', True)])
        if products:
            for prod in products:
                product_data.append({
                    'id': prod.id,
                    'name': prod.name,
                })

        datas = {
            'tasks': task_data,
            'products': product_data,
            'job_id': job_id,
            'job_no': job_no,
            'job_desc': job_name,
            'partner_name': vendor.name if vendor else 'No partner found.',
            'selected_date': selected_date.strftime('%Y-%m-%d') if date_filter and selected_date else '',
        }
        return request.render('bcplanning.web_partner_bor_template', datas)

    @http.route('/planningline/bor/save', type='jsonrpc', auth='user', methods=['POST'])
    def save_planningline_bor(self, planningline_id, start_datetime=None, end_datetime=None, product_id=None, qty=None, depth=None):
        """
        Save planning line coming from BOR page.
        This method is tolerant about incoming datetime strings: supports with or without seconds,
        supports 'T' or space separation. It returns old_* and new_* values to let frontend restore or update UI.
        It uses the existing '/planningline/bor/save' route (keeps your route & function name).
        """

        def _parse_datetime_lenient(value):
            if not value:
                return False
            # Try common patterns
            fmts = (
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
            )
            for f in fmts:
                try:
                    return datetime.strptime(value, f)
                except (ValueError, TypeError):
                    continue
            # Last attempt: strip trailing :00 (seconds) and try without seconds
            try:
                if isinstance(value, str) and value.endswith(':00'):
                    trimmed = value[:-3]
                    return datetime.strptime(trimmed, '%Y-%m-%dT%H:%M')
            except Exception:
                pass
            raise ValidationError(f'Invalid datetime: {value}')

        # Basic validation
        try:
            pl_id = int(planningline_id)
        except Exception:
            return {'result': 'Invalid planning line id', 'error': True}

        line = request.env['bcplanningline'].sudo().browse(pl_id)
        if not line.exists():
            return {'result': 'Planning line not found', 'error': True}

        # Old values for fallback
        old_start = line.start_datetime
        old_end = line.end_datetime
        old_product_id = line.product_id.id if line.product_id else None
        old_qty = line.quantity if line.quantity is not None else 0
        old_depth = line.depth if line.depth is not None else 0

        # Parse incoming datetimes leniently
        try:
            parsed_start = _parse_datetime_lenient(start_datetime) if start_datetime is not None else False
            parsed_end = _parse_datetime_lenient(end_datetime) if end_datetime is not None else False
        except ValidationError as e:
            return {
                'result': str(e),
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M:%S') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M:%S') if old_end else '',
                'old_product_id': old_product_id,
                'old_qty': old_qty,
                'old_depth': old_depth,
                'error': True,
            }

        # Prepare BC payload datetimes (ensure seconds present)
        def _ensure_seconds(ts):
            if not ts:
                return ''
            # If string already contains seconds (three parts after split(':')), keep it.
            try:
                if isinstance(ts, str):
                    if len(ts.split('T')[-1].split(':')) == 3:
                        return ts
                    # if format is YYYY-MM-DDTHH:MM, append :00
                    return f"{ts}:00"
                # if ts is datetime object, format with seconds
                if isinstance(ts, datetime):
                    return ts.strftime('%Y-%m-%dT%H:%M:%S')
            except Exception:
                pass
            return ts

        sd = _ensure_seconds(start_datetime) if start_datetime else (line.start_datetime.strftime('%Y-%m-%dT%H:%M:%S') if line.start_datetime else '')
        ed = _ensure_seconds(end_datetime) if end_datetime else (line.end_datetime.strftime('%Y-%m-%dT%H:%M:%S') if line.end_datetime else '')

        # Resolve product object safely
        product = False
        if product_id not in (None, '', False):
            try:
                product = request.env['product.product'].sudo().browse(int(product_id))
            except Exception:
                product = False

        # Build payload for BC call (same fields you used)
        payload = {
            "jobNo": line.task_id.job_id.job_no,
            "jobTaskNo": line.task_id.task_no,
            "lineNo": str(line.planning_line_lineno),
            "type": "Item" if product else "Text",
            "no": product.name if product else (line.planning_line_no or 'VACANT'),
            "planning_product_id": f"{product.id if product else 0}",
            "planning_vendor_id": f"{line.vendor_id.sudo().id if line.vendor_id.sudo() else 0}",
            "startDateTime": sd,
            "endDateTime": ed,
            "description": product.name if product else line.planning_line_desc,
            "qty": qty,
            "depth": depth,
        }

        # Call BC safely
        try:
            success = request.env['bcplanning_utils'].update_bc_planningline_item(payload=payload)
        except Exception as e:
            _logger.exception("External BC update failed for planningline %s", pl_id)
            return {
                'result': f'External update failed: {str(e)}',
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M:%S') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M:%S') if old_end else '',
                'old_product_id': old_product_id,
                'old_qty': old_qty,
                'old_depth': old_depth,
                'error': True,
            }

        # Handle BC response
        if success is True:
            # Write only if BC succeeded
            try:
                write_vals = {}
                if parsed_start is not False:
                    write_vals['start_datetime'] = parsed_start
                if parsed_end is not False:
                    write_vals['end_datetime'] = parsed_end
                if product_id is not None and product_id != '':
                    try:
                        write_vals['product_id'] = int(product_id)
                    except Exception:
                        write_vals['product_id'] = False
                elif product_id == "" or product_id is None:
                    write_vals['product_id'] = False
                if qty not in (None, '', False):
                    try:
                        write_vals['quantity'] = float(qty)
                    except Exception:
                        write_vals['quantity'] = qty
                if depth not in (None, '', False):
                    try:
                        write_vals['depth'] = float(depth)
                    except Exception:
                        write_vals['depth'] = depth

                if write_vals:
                    line.sudo().write(write_vals)
            except Exception as e:
                _logger.exception("Failed to write bcplanningline %s after BC success: %s", pl_id, e)
                return {
                    'result': f'Updated in BC but local save failed: {str(e)}',
                    'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M:%S') if old_start else '',
                    'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M:%S') if old_end else '',
                    'old_product_id': old_product_id,
                    'old_qty': old_qty,
                    'old_depth': old_depth,
                    'error': True,
                }

            # Prepare canonical new values for the frontend
            new_vals = {
                'new_start_datetime': line.start_datetime.strftime('%Y-%m-%dT%H:%M:%S') if line.start_datetime else '',
                'new_end_datetime': line.end_datetime.strftime('%Y-%m-%dT%H:%M:%S') if line.end_datetime else '',
                'new_pl_product_id': line.product_id.id if line.product_id else False,
                'new_pl_qty': line.quantity,
                'new_pl_depth': line.depth,
            }
            return {'result': 'updated', **new_vals}
        else:
            # BC returned False (failure) — return old values so frontend can restore
            return {
                'result': 'Update to BC failed',
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M:%S') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M:%S') if old_end else '',
                'old_product_id': old_product_id,
                'old_qty': old_qty,
                'old_depth': old_depth,
                'error': True,
            }
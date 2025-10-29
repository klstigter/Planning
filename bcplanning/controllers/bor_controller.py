from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied
import json
from odoo.http import Response
from odoo.exceptions import ValidationError
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
                ('resource_id', '=', user.partner_id.id) # filter planning line per resource
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
                    ('resource_id', '=', user.partner_id.id) # filter planning line per resource
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
                ('resource_id', '=', user.partner_id.id), # filter planning line per resource
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
        products = request.env['product.product'].sudo().search([('product_tmpl_id.type','=','service'), ('active', '=', True)])
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
        Minimal, safe save:
        - Parse inputs, keep old values.
        - Call external BC update inside try/except to prevent 500.
        - Only write Odoo fields if BC call returns success (True).
        - Return structured JSON for frontend to restore old values on failure.
        """
        # Basic validation
        try:
            pl_id = int(planningline_id)
        except Exception:
            return {'result': 'Invalid planning line id', 'error': True}

        line = request.env['bcplanningline'].sudo().browse(pl_id)
        if not line.exists():
            return {'result': 'Planning line not found', 'error': True}

        old_start = line.start_datetime
        old_end = line.end_datetime
        old_product_id = line.product_id.id if line.product_id else None
        old_qty = line.quantity if line.quantity else 0
        old_depth = line.depth if line.depth else 0

        # Parse new datetimes (expecting 'YYYY-MM-DDTHH:MM' from the client)
        try:
            new_start = old_start
            new_end = old_end
            if start_datetime:
                new_start = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
            if end_datetime:
                new_end = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
        except Exception as e:
            return {
                'result': f'Invalid datetime: {e}',
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
                'old_product_id': old_product_id,
                'old_qty': old_qty,
                'old_depth': old_depth,
                'error': True,
            }

        # Prepare payload for BC (include seconds)
        sd = f'{start_datetime}:00' if start_datetime else (line.start_datetime and line.start_datetime.strftime('%Y-%m-%dT%H:%M:%S'))
        ed = f'{end_datetime}:00' if end_datetime else (line.end_datetime and line.end_datetime.strftime('%Y-%m-%dT%H:%M:%S'))

        product = False
        if product_id:
            try:
                product = request.env['product.product'].sudo().browse(int(product_id))
            except Exception:
                product = False

        payload = {
            "jobNo": line.task_id.job_id.job_no,
            "jobTaskNo": line.task_id.task_no,
            "lineNo": str(line.planning_line_lineno),
            "type": "Item" if product else "Text",
            "no": product.name if product else 'VACANT',
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
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
                'old_product_id': old_product_id,
                'old_qty': old_qty,
                'old_depth': old_depth,
                'error': True,
            }

        # Handle result
        if success is True:
            # Only write Odoo fields on BC success
            try:
                if start_datetime:
                    line.sudo().write({'start_datetime': new_start})
                if end_datetime:
                    line.sudo().write({'end_datetime': new_end})
                if product_id is not None and product_id != '':
                    line.sudo().write({'product_id': int(product_id)})
                elif product_id == "" or product_id is None:
                    line.sudo().write({'product_id': False})
                if qty:
                    line.sudo().write({'quantity': qty})
                if depth:
                    line.sudo().write({'depth': depth})
            except Exception as e:
                _logger.exception("Failed to write bcplanningline %s after BC success: %s", pl_id, e)
                # If local write fails, return an error but indicate BC succeeded
                return {
                    'result': f'Updated in BC but local save failed: {str(e)}',
                    'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
                    'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
                    'old_product_id': old_product_id,
                    'old_qty': old_qty,
                    'old_depth': old_depth,
                    'error': True,
                }
            return {'result': 'updated'}
        else:
            # BC returned False (failure) — return old values so frontend can restore
            return {
                'result': 'Update to BC failed',
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
                'old_product_id': old_product_id,
                'old_qty': old_qty,
                'old_depth': old_depth,
                'error': True,
            }
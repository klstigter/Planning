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
                    })

                task_data.append({
                    'id': t.id,
                    'task_no': t.task_no,
                    'task_desc': t.task_desc,
                    'job_no': t.job_id.job_no,
                    'planningline_count': len(planninglines),
                    'planninglines': pl_data
                })

        # # Resources
        # resource_data = []
        # res = request.env['res.partner'].sudo().search([('id', '=', vendor.id)])
        # if res.child_ids:
        #     for contact in res.child_ids:
        #         resource_data.append({
        #             'id': contact.id,
        #             'name': contact.name,
        #         })

        datas = {
            'tasks': task_data,
            # 'resources': resource_data,
            'job_id': job_id,
            'job_no': job_no,
            'job_desc': job_name,
            'partner_name': vendor.name if vendor else 'No partner found.',
            'selected_date': selected_date.strftime('%Y-%m-%d') if date_filter and selected_date else '',
        }
        return request.render('bcplanning.web_partner_bor_template', datas)
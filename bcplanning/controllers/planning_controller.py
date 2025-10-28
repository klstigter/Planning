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

class PlanningApiController(http.Controller):

    # ********************* api_key group ********************************************************
    @http.route('/hello', type='http', auth='api_key', methods=['GET'], csrf=False)
    def test_hello(self, **post):
        user = request.env.user
        rtv = []
        # job_vals = {
        #     'user': user.name,            
        # }
        # rtv.append(job_vals)
        projects = request.env['bcproject'].with_user(user.id).search([])
        for job in projects:
            job_vals = {
              'job_no': job.job_no,
              'job_desc': job.job_desc,
            }
            rtv.append(job_vals)

        return Response(json.dumps(rtv),content_type='application/json;charset=utf-8',status=200)
    
    @http.route('/planning/partners', type='http', auth='api_key', methods=['GET'], csrf=False)
    def getpartners(self):
        """
        this endpoint will access by BC
        """
        vendor_recs = []
        vendors = request.env['res.partner'].search([('is_company','=',True), ('category_id','in',['Partner'])])
        if vendors:
            for ven in vendors:
                vendor_recs.append({
                    'vendor_id': ven.id,
                    'vendor_name': ven.name,
                })
        return Response(json.dumps(vendor_recs),content_type='application/json;charset=utf-8',status=200)

    @http.route('/planning/products', type='http', auth='api_key', methods=['GET'], csrf=False)
    def getpartners(self):
        """
        this endpoint will access by BC
        """
        product_recs = []
        products = request.env['product.product'].search([('product_tmpl_id.type','=','service'), ('active', '=', True)])
        if products:
            for prod in products:
                product_recs.append({
                    'product_id': prod.id,
                    'product_name': prod.name,
                })
        return Response(json.dumps(product_recs),content_type='application/json;charset=utf-8',status=200)

    @http.route('/planning/contacts', type='http', auth='api_key', methods=['POST'], csrf=False)
    def getcontacts(self):    
        """
        this endpoint will access by BC
        Body params:
        {
            "vendors":[{
                            "id": 7
                        },
                        {
                            "id": 13
                        }
                    ]
        }
        """    
        contact_recs = []
        domain = []
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
            vendor_ids = [vendor['id'] for vendor in data['vendors']]
            if vendor_ids:
                domain = [('id', 'in', vendor_ids)]        
        except Exception as e:
            domain = []
        vendors = request.env['res.partner'].search(domain)
        if vendors:
            for ven in vendors:                
                res = request.env['res.partner'].sudo().search([('id','=',ven.id)])
                if res.child_ids:
                    for contact in res.child_ids:
                        contact_recs.append({
                            'vendor_id': ven.id,
                            'vendor_name': ven.name,
                            'contact_id': contact.id,
                            'contact_name': contact.name,
                        })
        return Response(json.dumps(contact_recs),content_type='application/json;charset=utf-8',status=200)

    @http.route('/planning/deleteplanningline', type='http', auth='api_key', methods=['POST'], csrf=False)
    def deleteplanningline(self, **kwargs):
        posted_data = {}
        try:
            posted_data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception as e:                
            raise ValidationError(f"submitted data is invalid: {str(request.httprequest.data.decode('utf-8'))}")

        planning_line_jobno = posted_data.get('bc_jobplanningline_jobno')
        planning_line_taskno = posted_data.get('bc_jobplanningline_taskno')
        planning_line_lineno = posted_data.get('bc_jobplanningline_lineno')

        # Check Job/Project 
        project = request.env['bcproject'].sudo().search([('job_no','=',planning_line_jobno)], limit=1)
        if not project:
            raise ValidationError(f'Project not found for job_no {planning_line_jobno}')

        # Check Task
        task = request.env['bctask'].sudo().search([('task_no','=',planning_line_taskno), ('job_id','=', project.id)], limit=1)
        if not task:
            raise ValidationError(f'Task not found for job_no {planning_line_jobno} and task_no {planning_line_taskno}')

        # Planning Line
        planningline_rec = request.env['bcplanningline'].sudo().search([('planning_line_lineno','=',planning_line_lineno), ('task_id','=',task.id)], limit=1)
        if planningline_rec:
            for rec in planningline_rec:
                rec.unlink()
            result = {
                        'job_no': planning_line_jobno,
                        'task_no': planning_line_taskno,
                        'planning_lineno': planning_line_lineno,
                        'deleted': 'ok',
                    }
            response = json.dumps({'status': 'success', 'received': result})
            return request.make_response(response, headers=[('Content-Type', 'application/json')])
        else:
            result = {
                        'job_no': 'not found',
                        'task_no': 'not found',
                        'planning_lineno': 0,
                        'deleted': 'record not found',
                    }
            response = json.dumps({'status': 'error', 'received': result})
            return request.make_response(response, headers=[('Content-Type', 'application/json')])


    @http.route('/planning/planninglinefrombc', type='http', auth='api_key', methods=['POST'], csrf=False)
    def planninglinefrombc(self, **kwargs):
        """
        {
            "bc_jobplanningline_jobno": xxx,
            "bc_jobplanningline_taskno": xxx,
            "bc_jobplanningline_lineno":50000,
            "bc_jobplanningline_type":"Text",
            "bc_jobplanningline_no":"VACANT",
            "bc_jobplanningline_resid":0,
            "bc_jobplanningline_desc":"Vacant Resource",
            "bc_jobplanningline_vendorid":13,
            "bc_jobplanningline_datetimestart":"2025-10-11T07:00:00",
            "bc_jobplanningline_datetimeend":"2025-10-11T11:00:00"
        }
        """
        posted_data = {}
        try:
            posted_data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception as e:
            # print("Error parsing JSON payload:", e)                
            raise ValidationError(f"submitted data is invalid: {str(request.httprequest.data.decode('utf-8'))}")
        result = request.env['bcplanningline'].planninglinefrombc(posted_data)    
        # Return as JSON
        response = json.dumps({'status': 'success', 'received': result})
        return request.make_response(response, headers=[('Content-Type', 'application/json')])


    @http.route('/planning/projectcreationfrombc', type='http', auth='api_key', methods=['POST'], csrf=False)
    def projectcreationfrombc(self, **kwargs):
        posted_data = {}
        try:
            posted_data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception as e:
            # print("Error parsing JSON payload:", e)                
            raise ValidationError(f"submitted data is invalid: {str(request.httprequest.data.decode('utf-8'))}")

        result = request.env['bcproject'].projectcreationfrombc(posted_data)    
        # Return as JSON
        response = json.dumps({'status': 'success', 'received': result})
        return request.make_response(response, headers=[('Content-Type', 'application/json')])


    # ********************* end of api_key group *****************************************************


    # ********************* http group ********************************************************    
    @http.route('/partner/projects', type='http', auth='user', website=True)
    def partner_project(self):
        user = request.env.user
        # Get Vendor
        vendor = []
        if user.partner_id.parent_id:
            vendor = request.env['res.partner'].sudo().search([('id','=',user.partner_id.parent_id.id)], limit=1)
        else:
            vendor = request.env['res.partner'].sudo().search([('id','=',user.partner_id.id)], limit=1)
        if not vendor:
            # raise ValidationError("setting of user vs vendor does not exist!")
            # No vendor mapping found -> show dedicated "no records" template
            datas = {
                'message_title': "No vendor mapping",
                'message_text': "No vendor mapping found for your account. Please contact your administrator.",
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)

        number_of_project = 0
        project_data = []
        datas = {}
        planninglines = request.env['bcplanningline'].with_user(user.id).search([('vendor_id','=',vendor.id)])
        if planninglines:
            job_ids = planninglines.mapped('job_id.id')
            number_of_project = len(job_ids) if job_ids else 0
            projects = request.env['bcproject'].with_user(user.id).search([('id','in',job_ids)])
            if projects:
                for p in projects:                
                    planninglines = request.env['bcplanningline'].with_user(user.id).search([('task_id.job_id.id','=',p.id), ('vendor_id','=',vendor.id)])
                    if planninglines:
                        task_ids = planninglines.mapped('task_id.id')
                        project_data.append({
                            'id': p.id,
                            'job_no': p.job_no if p.job_no else '-',
                            'job_desc': p.job_desc if p.job_desc else '-',
                            'task_count': len(task_ids),
                            'partner_name': vendor.name if vendor else '',
                        })
            datas = {
                'partner_id': vendor.id,
                'partner_name': vendor.name if vendor else '',
                'number_of_project':  number_of_project,
                'projects': project_data,
            }
        return request.render('bcplanning.web_partner_project_template',datas)

    @http.route('/partner/tasks', type='http', auth='user', website=True)
    def partner_tasks(self, job_id=None, job_no=None, job_name=None, date=None, **kwargs):
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
            pl_domain = [('vendor_id', '=', partner_id)]
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

        # Resources
        resource_data = []
        res = request.env['res.partner'].sudo().search([('id', '=', vendor.id)])
        if res.child_ids:
            for contact in res.child_ids:
                resource_data.append({
                    'id': contact.id,
                    'name': contact.name,
                })

        datas = {
            'tasks': task_data,
            'resources': resource_data,
            'job_id': job_id,
            'job_no': job_no,
            'job_desc': job_name,
            'partner_name': vendor.name if vendor else 'No partner found.',
            'selected_date': selected_date.strftime('%Y-%m-%d') if date_filter and selected_date else '',
        }
        return request.render('bcplanning.web_partner_task_template', datas)
    
    # ********************* end of http group ********************************************************


    # ********************* jsonrpc ********************************************************

    @http.route('/bcplanningline/save', type='jsonrpc', auth='user', methods=['POST'])
    def save_planningline(self, planningline_id, start_datetime=None, end_datetime=None, resource_id=None):
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
        old_resource_id = line.resource_id.id if line.resource_id else None

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
                'old_resource_id': old_resource_id,
                'error': True,
            }

        # Prepare payload for BC (include seconds)
        sd = f'{start_datetime}:00' if start_datetime else (line.start_datetime and line.start_datetime.strftime('%Y-%m-%dT%H:%M:%S'))
        ed = f'{end_datetime}:00' if end_datetime else (line.end_datetime and line.end_datetime.strftime('%Y-%m-%dT%H:%M:%S'))

        resource = False
        if resource_id:
            try:
                resource = request.env['res.partner'].sudo().browse(int(resource_id))
            except Exception:
                resource = False

        payload = {
            "jobNo": line.task_id.job_id.job_no,
            "jobTaskNo": line.task_id.task_no,
            "lineNo": str(line.planning_line_lineno),
            "type": "Resource" if resource else "Text",
            "no": resource.name if resource else 'VACANT',
            "planning_resource_id": f"{resource.id if resource else 0}",
            "planning_vendor_id": f"{line.vendor_id.sudo().id if line.vendor_id.sudo() else 0}",
            "startDateTime": sd,
            "endDateTime": ed,
            "description": resource.name if resource else line.planning_line_desc,
        }

        # Call BC safely
        try:
            success = request.env['bcplanning_utils'].update_bc_planningline(payload=payload)
        except Exception as e:
            _logger.exception("External BC update failed for planningline %s", pl_id)
            return {
                'result': f'External update failed: {str(e)}',
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
                'old_resource_id': old_resource_id,
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
                if resource_id is not None and resource_id != '':
                    line.sudo().write({'resource_id': int(resource_id)})
                elif resource_id == "" or resource_id is None:
                    line.sudo().write({'resource_id': False})
            except Exception as e:
                _logger.exception("Failed to write bcplanningline %s after BC success: %s", pl_id, e)
                # If local write fails, return an error but indicate BC succeeded
                return {
                    'result': f'Updated in BC but local save failed: {str(e)}',
                    'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
                    'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
                    'old_resource_id': old_resource_id,
                    'error': True,
                }
            return {'result': 'updated'}
        else:
            # BC returned False (failure) — return old values so frontend can restore
            return {
                'result': 'Update to BC failed',
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
                'old_resource_id': old_resource_id,
                'error': True,
            }

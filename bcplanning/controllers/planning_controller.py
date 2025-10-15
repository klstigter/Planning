from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied
import json
from odoo.http import Response
from odoo.exceptions import ValidationError
from datetime import datetime

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
        vendor_recs = []
        vendors = request.env['bcexternaluser'].search([])
        if vendors:
            vendors = vendors.mapped('vendor_id')
        if vendors:
            for ven in vendors:
                vendor_recs.append({
                    'vendor_id': ven.id,
                    'vendor_name': ven.name,
                })
        return Response(json.dumps(vendor_recs),content_type='application/json;charset=utf-8',status=200)

    @http.route('/planning/contacts', type='http', auth='api_key', methods=['POST'], csrf=False)
    def getcontacts(self):    
        """
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
                domain = [('vendor_id.id', 'in', vendor_ids)]        
        except Exception as e:
            domain = []
        vendors = request.env['bcexternaluser'].search(domain)
        if vendors:
            vendors = vendors.mapped('vendor_id')
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


    @http.route('/planning/projectcreationfrombc', type='http', auth='api_key', methods=['POST'], csrf=False)
    def projectcreationfrombc(self, **kwargs):
        try:
            posted_data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception as e:
            # print("Error parsing JSON payload:", e)
            posted_data = {}    
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
        vendors = request.env['bcexternaluser'].with_user(user.id).search([('user_id','=',user.id)], limit=1)
        if not vendors:
            raise ValidationError("setting of user vs vendor does not exist!")
        vendor = vendors[0]
        res = request.env['res.partner'].sudo().search([('id','=',vendor.vendor_id.id)])

        project_data = []
        datas = {}
        planninglines = request.env['bcplanningline'].with_user(user.id).search([('vendor_id','=',vendor.vendor_id.id)])
        if planninglines:
            job_ids = planninglines.mapped('job_id.id')
            projects = request.env['bcproject'].with_user(user.id).search([('id','in',job_ids)])
            if projects:
                for p in projects:                
                    project_data.append({
                        'id': p.id,
                        'job_no': p.job_no if p.job_no else '-',
                        'job_desc': p.job_desc if p.job_desc else '-',
                        'task_count': len(p.task_line),
                        'partner_name': res.name if res else '',
                    })
            datas = {
                'partner_id': vendor.vendor_id,
                'partner_name': res.name if res else '',
                'projects': project_data,
            }
        return request.render('bcplanning.web_partner_project_template',datas)

    @http.route('/partner/tasks', type='http', auth='user', website=True)
    def partner_tasks(self, job_id=None, job_no=None, job_name=None, **kwargs):
        # print(job_id)
        # print(job_no)
        # print(job_name)        
        user = request.env.user

        # Get Vendor from bcexternaluser (adapt this if your vendor relation is different)
        vendors = request.env['bcexternaluser'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not vendors:
            raise ValidationError("User to vendor mapping not found!")
        vendor = vendors[0]
        partner_id = vendor.vendor_id.id

        # Get projects for vendor
        project = request.env['bcproject'].with_user(user.id).search([('id', '=', job_id)])
        if not project:
            raise ValidationError(f"Project {job_no} for user {user.name} is not found!")

        # Get tasks for projects
        tasks = request.env['bctask'].with_user(user.id).search([('job_id', '=', project.id)])

        # Build task data
        task_data = []
        for t in tasks:
            # Attach Planning Lines
            pl_data = []
            planninglines = t.planning_line.search([('task_id', '=' , t.id),('vendor_id', '=' , partner_id)])
            if planninglines:
                for pl in planninglines:
                    pl_data.append({
                        'id': pl.id,
                        'pl_no': pl.planning_line_no,
                        'pl_desc': pl.planning_line_desc,
                        'pl_resource_id': pl.resource_id.id,
                        'pl_start_datetime': pl.start_datetime,
                        'pl_end_datetime': pl.end_datetime,
                    })

                # Task
                task_data.append({
                    'id': t.id,
                    'task_no': t.task_no,
                    'task_desc': t.task_desc,   
                    'planningline_count': len(t.planning_line), 
                    'planninglines': pl_data
                })            

        # Resources
        resource_data = []
        res = request.env['res.partner'].sudo().search([('id','=',vendor.vendor_id.id)])
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
            'partner_name': vendor.vendor_id.name if vendor.vendor_id else 'No partner found.',
        }
        return request.render('bcplanning.web_partner_task_template', datas)
    
    # ********************* end of http group ********************************************************


    # ********************* jsonrpc ********************************************************

    @http.route('/bcplanningline/save', type='jsonrpc', auth='user', methods=['POST'])
    def save_planningline(self, planningline_id, start_datetime=None, end_datetime=None, resource_id=None):
        user = request.env.user
        line = request.env['bcplanningline'].with_user(user.id).browse(int(planningline_id))
        if not line.exists():
            return {'result': 'Planning line not found'}

        old_start = line.start_datetime
        old_end = line.end_datetime
        old_resource_id = line.resource_id.id if line.resource_id else None

        # Parse new values
        new_start = old_start
        new_end = old_end
        try:
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
            }

        # Update to BC first (pass all fields together)
        start_datetime = f'{start_datetime}:00'
        end_datetime = f'{end_datetime}:00'
        success = line[0].updatetobc_all(
            start_datetime=start_datetime if start_datetime else None,
            end_datetime=end_datetime if end_datetime else None,
            resource_id=resource_id
        )

        if success:
            # Only update Odoo if BC succeeds
            if start_datetime:
                line.start_datetime = new_start
            if end_datetime:
                line.end_datetime = new_end
            if resource_id:
                line.resource_id = int(resource_id)
            elif resource_id == "" or resource_id is None:
                line.resource_id = False
            return {'result': 'updated'}
        else:
            return {
                'result': 'Update to BC failed',
                'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
                'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
                'old_resource_id': old_resource_id,
            }

    # @http.route('/bcplanningline/update', type='jsonrpc', auth='user', methods=['POST'])
    # def update_resource(self, planningline_id, resource_id):
    #     user = request.env.user
        
    #     # Get Vendor from bcexternaluser (adapt this if your vendor relation is different)
    #     vendors = request.env['bcexternaluser'].sudo().search([('user_id', '=', user.id)], limit=1)
    #     if not vendors:
    #         raise ValidationError("User to vendor mapping not found!")
    #     vendor = vendors[0]
    #     vendor_id = vendor.vendor_id.id

    #     line = request.env['bcplanningline'].with_user(user.id).browse(int(planningline_id))
    #     if not line.exists():
    #         return {'result': 'Planning line not found'}

    #     new_resource = False
    #     if resource_id:
    #         new_resource = self.env['res.partner'].sudo().search([('id','=',int(resource_id))])
    #         if new_resource:
    #             new_resource = new_resource[0]

    #     # make request into BC
    #     if line[0].updatetobc(resource_id):
    #         if resource_id:
    #             line.resource_id = int(resource_id)
    #             line.planning_line_no = new_resource.name
    #             line.planning_line_desc = new_resource.name if new_resource else ''
    #         else:
    #             line.resource_id = False
    #         return {'result': 'updated'}
    #     else:
    #         return {'result': 'Update to BC failed'}

    # @http.route('/bcplanningline/update_datetime', type='jsonrpc', auth='user', methods=['POST'])
    # def update_datetime(self, planningline_id, start_datetime=None, end_datetime=None):
    #     user = request.env.user
    #     # Get Vendor from bcexternaluser (adapt this if your vendor relation is different)
    #     vendors = request.env['bcexternaluser'].sudo().search([('user_id', '=', user.id)], limit=1)
    #     if not vendors:
    #         raise ValidationError("User to vendor mapping not found!")

    #     line = request.env['bcplanningline'].with_user(user.id).browse(int(planningline_id))
    #     if not line.exists():
    #         return {'result': 'Planning line not found'}

    #     # Save old values for restoring if BC fails
    #     old_start = line.start_datetime
    #     old_end = line.end_datetime

    #     # Parse new values, but don't assign yet!
    #     new_start = old_start
    #     new_end = old_end
    #     try:
    #         if start_datetime:
    #             new_start = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
    #         if end_datetime:
    #             new_end = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
    #     except Exception as e:
    #         return {'result': f'Invalid datetime: {e}',
    #                 'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
    #                 'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else ''}

    #     # ---- 1. Try to update in D365BC ----
    #     # updatetobc_datetime should return True/False for success
    #     success = line[0].updatetobc_datetime(
    #         start_datetime=start_datetime if start_datetime else None,
    #         end_datetime=end_datetime if end_datetime else None
    #     )

    #     if success:
    #         # ---- 2. Update Odoo only if BC is OK ----
    #         if start_datetime:
    #             line.start_datetime = new_start
    #         if end_datetime:
    #             line.end_datetime = new_end
    #         return {'result': 'updated'}
    #     else:
    #         # ---- 3. Restore previous value in website ----
    #         return {
    #             'result': 'Update to BC failed',
    #             'old_start_datetime': old_start.strftime('%Y-%m-%dT%H:%M') if old_start else '',
    #             'old_end_datetime': old_end.strftime('%Y-%m-%dT%H:%M') if old_end else '',
    #         }

    # @http.route('/bcplanningline/add', type='jsonrpc', auth='user', methods=['POST'])
    # def add_planningline(self, task_id):
    #     user = request.env.user

    #     # Get Vendor from bcexternaluser (adapt this if your vendor relation is different)
    #     vendors = request.env['bcexternaluser'].sudo().search([('user_id', '=', user.id)], limit=1)
    #     if not vendors:
    #         raise ValidationError("User to vendor mapping not found!")
    #     vendor = vendors[0]
    #     vendor_id = vendor.vendor_id.id

    #     # Validate task_id
    #     task = request.env['bctask'].with_user(user.id).browse(int(task_id))
    #     if not task.exists():
    #         return {'result': 'Task not found'}
        
    #     # Generate a unique planning_line_no (can be customized)
    #     planning_line_lineno = 10000
    #     last_pl = request.env['bcplanningline'].sudo().search(
    #                 [('task_id', '=', task.id)],
    #                 order='planning_line_lineno desc',
    #                 limit=1
    #             )
    #     if last_pl:
    #         planning_line_lineno = str(last_pl.planning_line_lineno + 10000)
        
    #     # Create the new planning line
    #     planning_line = request.env['bcplanningline'].sudo().create({
    #         'planning_line_lineno': planning_line_lineno,
    #         'vendor_id': vendor_id,
    #         'planning_line_desc': 'New Planning Line',
    #         'task_id': task.id,
    #     })

    #     # Get Vendor from bcexternaluser (adapt this if your vendor relation is different)
    #     resource_options = ""        
    #     res = request.env['res.partner'].sudo().search([('id','=',vendor_id)])
    #     if res.child_ids:
    #         for contact in res.child_ids:
    #             resource_options += f'<option value="{contact.id}">{contact.name}</option>'

    #     return {
    #         'result': {
    #             'planningline_id': planning_line.id,
    #             'resource_options': resource_options,
    #         },            
    #     }

    
    # @http.route('/bcplanningline/delete', type='jsonrpc', auth='user', methods=['POST'])
    # def delete_planningline(self, planningline_id):
    #     """Delete a bcplanningline record by its ID."""
    #     # Validate input
    #     if not planningline_id:
    #         return {'success': False, 'error': 'No planning line id provided.'}

    #     # Search for the record
    #     record = request.env['bcplanningline'].sudo().browse(int(planningline_id))
    #     if not record.exists():
    #         return {'success': False, 'error': 'Planning line not found.'}

    #     # Delete the record
    #     try:
    #         record.unlink()
    #         return {'success': True}
    #     except Exception as e:
    #         return {'success': False, 'error': str(e)}

    # ********************* end of jsonrpc ********************************************************
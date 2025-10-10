from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json

class bcplanning_project(models.Model):
    _name = 'bcproject'
    _description = 'bcproject'
    _rec_name = 'job_no'
    
    job_no = fields.Char(string="Job No.", required=True)
    job_desc = fields.Char(string="Description")
    task_line = fields.One2many(
        comodel_name='bctask',
        inverse_name='job_id',
        string="Task Lines",
        copy=True, bypass_search_access=True)
    number_of_tasks = fields.Integer(
        string="Number of Tasks",
        compute="_get_numberoftasks", store=False)

    @api.constrains('job_no')
    def _check_job_no_unique(self):
        for record in self:
            # search for another record with the same job_no
            existing = self.env['bcproject'].search([
                ('job_no', '=', record.job_no),
                ('id', '!=', record.id)
            ], limit=1)
            if existing:
                raise ValidationError('Job No must be unique!')

    def _get_numberoftasks(self):
        for rec in self:
            rec.number_of_tasks = len(rec.task_line)

    def projectcreationfrombc(self, posted_data):
        if isinstance(posted_data, str):
            posted_data = json.loads(posted_data)
        job_no = posted_data.get('bc_project_no')
        job_desc = posted_data.get('bc_project_desc')

        tasks = posted_data.get('tasks', [])

        Job_id = False
        job_rec = self.env['bcproject'].search([('job_no','=',job_no)], limit=1)
        if job_rec:
            job_rec.job_desc = job_desc
            Job_id = job_rec.id
        else:    
            # Create the job_rec record
            job_rec = self.env['bcproject'].create({
                'job_no': job_no,
                'job_desc': job_desc,
            })
            Job_id = job_rec.id

        for task_data in tasks:
            task_no = task_data.get('bc_task_no')
            task_desc = task_data.get('bc_task_desc')
            planninglines = task_data.get('bc_planninglines', [])

            bctask = self.env['bctask'].search([('task_no','=',task_no), ('job_id','=',Job_id)], limit=1)
            if bctask:
                bctask.task_desc = task_desc                
            else:
                bctask = self.env['bctask'].create({
                    'task_no': task_no,
                    'task_desc': task_desc,
                    'job_id': Job_id,
                })

            for pl_data in planninglines:
                planning_line_lineno = pl_data.get('bc_jobplanningline_lineno')
                planning_line_no = pl_data.get('bc_jobplanningline_no')
                planning_line_desc = pl_data.get('bc_jobplanningline_desc')
                planningline_resid = pl_data.get('bc_jobplanningline_resid')
                planningline_vendorid = pl_data.get('bc_jobplanningline_vendorid')

                # Check partner ID
                if planningline_vendorid:                    
                    res_partner = self.env['res.partner'].sudo().search([('id', '=', planningline_vendorid)])
                    if not res_partner:
                        raise ValidationError(f'Partner not found for partner id {planningline_vendorid}')                    

                # Manage bc_jobplanningline_type
                # if Resource then attached to contact (resource_id has a value)
                # if Text then no contact (resource_id false)
                resource_id = False
                planning_line_type = pl_data.get('bc_jobplanningline_type')
                if planning_line_type == 'Source':
                    resource_id = planningline_resid

                # Check resource id
                if resource_id:
                    res_partner = self.env['res.partner'].sudo().search([('id', '=', resource_id)])
                    if not res_partner:
                        raise ValidationError(f'Resource not found for partner id {resource_id}')

                planningline_rec = self.env['bcplanningline'].search([('planning_line_lineno','=',planning_line_lineno), ('task_id','=',bctask.id)], limit=1)
                if planningline_rec:
                    planningline_rec.planning_line_no = planning_line_no
                    planningline_rec.planning_line_desc= planning_line_desc
                    planningline_rec.resource_id = resource_id
                    planningline_rec.vendor_id = planningline_vendorid if planningline_vendorid else False
                else:
                    self.env['bcplanningline'].create({
                        'planning_line_lineno': planning_line_lineno or 0,
                        'planning_line_no': planning_line_no or '',  # required field fallback
                        'planning_line_desc': planning_line_desc,
                        'resource_id': resource_id,
                        'vendor_id': planningline_vendorid if planningline_vendorid else False,
                        'task_id': bctask.id,
                    })

        return {
            'job_id': Job_id,
            'job_no': job_rec.job_no,
            'created_tasks': len(tasks),
        }



class bcplanning_task(models.Model):
    _name = 'bctask'
    _description = 'bctask'
    _rec_name = 'task_no'

    task_no = fields.Char(required=True)
    task_desc = fields.Char()
    job_id = fields.Many2one(
        comodel_name='bcproject',
        string="Project Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    planning_line = fields.One2many(
        comodel_name='bcplanningline',
        inverse_name='task_id',
        string="Planning Lines",
        copy=True, bypass_search_access=True)
    number_of_lines = fields.Integer(
        string="Planning Lines",
        compute="_get_numberofplanninglines", store=False)    
    supervisor_id = fields.Many2one('res.partner', string='Supervisor', domain="[]")

    @api.constrains('task_no', 'job_id')
    def _check_job_no_unique(self):
        for record in self:
            # search for another record with the same task_no and job_id
            existing = self.env['bctask'].search([
                ('task_no', '=', record.task_no),
                ('job_id', '=', record.job_id.id),
                ('id', '!=', record.id)
            ], limit=1)
            if existing:
                raise ValidationError('Task No must be unique per Job No.!')

    def _get_numberofplanninglines(self):
        for rec in self:
            rec.number_of_lines = len(rec.planning_line)

class bcplanning_line(models.Model):
    _name = 'bcplanningline'
    _description = 'bcplanningline'
    _rec_name = 'planning_line_no'

    planning_line_lineno = fields.Integer(required=True)
    planning_line_no = fields.Char()
    planning_line_desc = fields.Char()    

    task_id = fields.Many2one(
        comodel_name='bctask',
        string="Task Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    job_id = fields.Many2one(
        comodel_name='bcproject',
        string="Project Reference",
        compute="_get_job_id", store=True)
    
    resource_id = fields.Many2one('res.partner', string='Resource', domain="[]")
    vendor_id = fields.Many2one('res.partner', string='Vendor', domain="[]")
    
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',        
        ondelete='restrict',
        index=True,
    )
    quantity = fields.Integer(string="Quantity")
    depth = fields.Float(string="Depth")

    start_datetime = fields.Datetime(string="Start Date-Time")
    end_datetime = fields.Datetime(string="End Date-Time")

    @api.depends('task_id')
    def _get_job_id(self):
        for record in self:
            record.job_id = False
            task = self.env['bctask'].search([('id','=',record.task_id.id)])
            if task:
                record.job_id = task[0].job_id.id

    @api.constrains('planning_line_lineno', 'task_id')
    def _check_job_no_unique(self):
        for record in self:
            # search for another record with the same planning_line_no, task_id
            existing = self.env['bcplanningline'].search([
                ('planning_line_lineno', '=', record.planning_line_lineno),
                ('task_id', '=', record.task_id.id),            
                ('id', '!=', record.id)
            ], limit=1)
            if existing:
                raise ValidationError(f'Planning Line No must be unique per Task No.!, duplicates on planning_line_lineno = {record.planning_line_lineno}, task No = {record.task_id.task_no}, Job No = {record.job_id.job_no}')

    def updatetobc(self, new_resource_id):
        new_resource = self.env['res.partner'].sudo().search([('id','=',int(new_resource_id))])
        if new_resource:
            new_resource = new_resource[0]
        rtv = False
        url = 'https://api.businesscentral.dynamics.com/v2.0/NL_Copy20240710/api/ddsia/planning/v1.0/companies(5cd9e171-71ab-ee11-a56d-6045bde98add)/jobPlanningLines'
        payload = {
            "jobNo": self.task_id.job_id.job_no,
            "jobTaskNo": self.task_id.task_no,
            "lineNo": f"{self.planning_line_lineno}",
            "type": "Resource" if new_resource_id else "Text",
            "no": new_resource.name if new_resource else 'NONE',
            "planning_resource_id": f"{int(new_resource_id) if new_resource_id else 0}",
            "planning_vendor_id": f"{self.vendor_id.id if self.vendor_id else 0}",
            "description": self.planning_line_desc,
        }
        response = self.env['bcplanning_utils'].post_request(url,payload)
        if response.status_code in (200, 201):
            print(response)
            rtv = True
        else:
            print(f"POST failed: {response.status_code} {response.text}")
        return rtv


        # If you want Odoo's logging: _logger.info(response.text)
        # if response.status_code == 201 or response.status_code == 200:
        #     return response.json()
        # else:
        #     raise Exception(f"POST failed: {response.status_code} {response.text}")
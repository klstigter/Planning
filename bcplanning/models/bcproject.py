from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
from odoo.fields import Domain
from datetime import datetime

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
    task_line_filtered = fields.One2many(
        'bctask', 'job_id', string='My Task Lines', compute='_compute_task_line_filtered'
    )
    number_of_tasks = fields.Integer(
        string="Number of Tasks",
        compute="_get_numberoftasks", store=False)
    number_of_tasks_per_user = fields.Integer(
        string="Number of Tasks (User Owner)",
        compute="_get_numberoftasks_user", store=False)

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

    @api.depends('task_line')
    def _compute_task_line_filtered(self):
        current_user_id = self.env.uid
        for record in self:
            record.task_line_filtered = record.task_line.filtered(lambda t: t.data_owner_id.id == current_user_id)
            
    def _get_numberoftasks(self):
        for rec in self:
            rec.number_of_tasks = len(rec.task_line)

    def _get_numberoftasks_user(self):
        for rec in self:
            rec.number_of_tasks_per_user = len(rec.task_line_filtered)

    def projectcreationfrombc(self, posted_data):
        if isinstance(posted_data, str):
            posted_data = json.loads(posted_data)
        job_no = posted_data.get('bc_project_no')
        job_desc = posted_data.get('bc_project_desc')

        tasks = posted_data.get('tasks', [])

        job_rec = self.env['bcproject'].search([('job_no','=',job_no)], limit=1)
        if job_rec:
            job_rec.job_desc = job_desc
        else:    
            # Create the job_rec record
            job_rec = self.env['bcproject'].create({
                'job_no': job_no,
                'job_desc': job_desc,
            })

        for task_data in tasks:
            task_no = task_data.get('bc_task_no')
            task_desc = task_data.get('bc_task_desc')
            task_planning_id = task_data.get('planning_user_id')
            
            planninglines = task_data.get('bc_planninglines', [])

            task = self.env['bctask'].sudo().search([('task_no','=',task_no), ('job_id','=',job_rec.id)], limit=1) 
            # apply sudo due to Odoo ORM respects record rules and access rights. 
            # If your current user doesn't have permission to read the record, 
            # search() will return an empty recordset even if it exists in the database.
            if task:
                task.task_desc = task_desc                
                task.data_owner_id = task_planning_id 
            else:
                task = self.env['bctask'].create({
                    'task_no': task_no,
                    'job_id': job_rec.id,
                    'task_desc': task_desc,
                    'data_owner_id': task_planning_id,                    
                })

            for pl_data in planninglines:
                planning_line_lineno = pl_data.get('bc_jobplanningline_lineno')
                planning_line_no = pl_data.get('bc_jobplanningline_no')
                planning_line_desc = pl_data.get('bc_jobplanningline_desc')
                planningline_resid = pl_data.get('bc_jobplanningline_resid')
                planningline_vendorid = pl_data.get('bc_jobplanningline_vendorid')
                planningline_datetimestart = pl_data.get('bc_jobplanningline_datetimestart') # start_datetime
                planningline_datetimeend = pl_data.get('bc_jobplanningline_datetimeend')   # end_datetime


                # Check partner ID
                res_partner = False
                if planningline_vendorid:                    
                    res_partner = self.env['res.partner'].sudo().search([('id', '=', planningline_vendorid)])
                    if not res_partner:
                        raise ValidationError(f'Partner not found for partner id {planningline_vendorid}')                    

                # Manage bc_jobplanningline_type
                # if Resource then attached to contact (resource_id has a value)
                # if Text then no contact (resource_id false)
                resource_id = False
                planning_line_type = pl_data.get('bc_jobplanningline_type')
                if planning_line_type == 'Resource':
                    resource_id = planningline_resid

                # Check resource id
                if resource_id:
                    res_partner = self.env['res.partner'].sudo().search([('id', '=', resource_id)])
                    if not res_partner:
                        raise ValidationError(f'Resource not found for partner id {resource_id}')
                        # to avoid above error:
                        # in BC the Resource card should be link with Odoo Contact. BC Field = Planning Resource Id
                        # but how to do that in BC? at the moment it no intarface in BC to link BC Resource with Odoo Contact.

                planningline_rec = self.env['bcplanningline'].search([('planning_line_lineno','=',planning_line_lineno), ('task_id','=',task.id)], limit=1)
                if planningline_rec:
                    planningline_rec.planning_line_no = planning_line_no
                    planningline_rec.planning_line_desc= planning_line_desc
                    planningline_rec.resource_id = resource_id
                    planningline_rec.vendor_id = planningline_vendorid if planningline_vendorid else False
                    planningline_rec.start_datetime = datetime.strptime(planningline_datetimestart, '%Y-%m-%dT%H:%M:%S') if planningline_datetimestart else False
                    planningline_rec.end_datetime = datetime.strptime(planningline_datetimeend, '%Y-%m-%dT%H:%M:%S') if planningline_datetimeend else False
                else:
                    self.env['bcplanningline'].create({
                        'planning_line_lineno': planning_line_lineno or 0,
                        'planning_line_no': planning_line_no or '',  # required field fallback
                        'planning_line_desc': planning_line_desc,
                        'resource_id': resource_id,
                        'vendor_id': planningline_vendorid if planningline_vendorid else False,
                        'task_id': task.id,
                        'start_datetime': datetime.strptime(planningline_datetimestart, '%Y-%m-%dT%H:%M:%S') if planningline_datetimestart else False,
                        'end_datetime': datetime.strptime(planningline_datetimeend, '%Y-%m-%dT%H:%M:%S') if planningline_datetimeend else False,
                    })

        return {
            'job_id': job_rec.id,
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
        required=True, ondelete='cascade', index=True)
    planning_line = fields.One2many(
        comodel_name='bcplanningline',
        inverse_name='task_id',
        string="Planning Lines",
        copy=True, bypass_search_access=True)
    number_of_lines = fields.Integer(
        string="Planning Lines",
        compute="_get_numberofplanninglines", store=False)    
    data_owner_id = fields.Many2one('res.users', string='Data Owner', domain="[]")

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

    # @api.model
    # def _search(self, domain, *args, **kwargs):
    #     domain = Domain(domain) & Domain('data_owner_id', '=', self.env.user.id)
    #     return super()._search(domain, *args, **kwargs)

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

    
    def planninglinefrombc(self, posted_data):
        if isinstance(posted_data, str):
            posted_data = json.loads(posted_data)
        
        planning_line_jobno = posted_data.get('bc_jobplanningline_jobno')
        planning_line_taskno = posted_data.get('bc_jobplanningline_taskno')
        planning_line_lineno = posted_data.get('bc_jobplanningline_lineno')
        planning_line_type = posted_data.get('bc_jobplanningline_type')
        planning_line_no = posted_data.get('bc_jobplanningline_no')
        planning_line_desc = posted_data.get('bc_jobplanningline_desc')
        planningline_resid = posted_data.get('bc_jobplanningline_resid')
        planningline_vendorid = posted_data.get('bc_jobplanningline_vendorid')
        planningline_datetimestart = posted_data.get('bc_jobplanningline_datetimestart')
        planningline_datetimeend = posted_data.get('bc_jobplanningline_datetimeend')

        # Check partner ID
        res_partner = False
        if planningline_vendorid:                    
            res_partner = self.env['res.partner'].sudo().search([('id', '=', planningline_vendorid)])
            if not res_partner:
                raise ValidationError(f'Partner not found for partner id {planningline_vendorid}')

        # Check Job/Project 
        project = self.env['bcproject'].sudo().search([('job_no','=',planning_line_jobno)], limit=1)
        if not project:
            raise ValidationError(f'Project not found for job_no {planning_line_jobno}')

        # Check Task
        task = self.env['bctask'].sudo().search([('task_no','=',planning_line_taskno), ('job_id','=', project.id)])
        if not task:
            raise ValidationError(f'Task not found for job_no {planning_line_jobno} and task_no {planning_line_taskno}')

        # Manage bc_jobplanningline_type
        # if Resource then attached to contact (resource_id has a value)
        # if Text then no contact (resource_id false)
        resource_id = False        
        if planning_line_type == 'Resource':
            resource_id = planningline_resid

        # Check resource id
        if resource_id:
            res_partner = self.env['res.partner'].sudo().search([('id', '=', resource_id)])
            if not res_partner:
                raise ValidationError(f'Resource not found for partner id {resource_id}')
                # to avoid above error:
                # in BC the Resource card should be link with Odoo Contact. BC Field = Planning Resource Id
                # but how to do that in BC? at the moment it no intarface in BC to link BC Resource with Odoo Contact.

        planningline_rec = self.env['bcplanningline'].sudo().search([('planning_line_lineno','=',planning_line_lineno), ('task_id','=',task.id)], limit=1)
        if planningline_rec:
            planningline_rec.planning_line_no = planning_line_no
            planningline_rec.planning_line_desc= planning_line_desc
            planningline_rec.resource_id = resource_id
            planningline_rec.vendor_id = planningline_vendorid if planningline_vendorid else False
            planningline_rec.start_datetime = datetime.strptime(planningline_datetimestart, '%Y-%m-%dT%H:%M:%S') if planningline_datetimestart else False
            planningline_rec.end_datetime = datetime.strptime(planningline_datetimeend, '%Y-%m-%dT%H:%M:%S') if planningline_datetimeend else False
        else:
            planningline_rec = self.env['bcplanningline'].sudo().create({
                'planning_line_lineno': planning_line_lineno or 0,
                'planning_line_no': planning_line_no or '',  # required field fallback
                'planning_line_desc': planning_line_desc,
                'resource_id': resource_id,
                'vendor_id': planningline_vendorid if planningline_vendorid else False,
                'task_id': task.id,
                'start_datetime': datetime.strptime(planningline_datetimestart, '%Y-%m-%dT%H:%M:%S') if planningline_datetimestart else False,
                'end_datetime': datetime.strptime(planningline_datetimeend, '%Y-%m-%dT%H:%M:%S') if planningline_datetimeend else False,
            })
                

        return {
            'job_no': project.job_no,
            'task_no': task.task_no,
            'planning_lineno': planningline_rec.planning_line_lineno,
            'updated_line': len(planningline_rec),
        }
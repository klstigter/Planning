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
    
    number_of_tasks = fields.Integer(
        string="Number of Tasks",
        compute="_get_numberoftasks", store=False)
    
    @api.constrains('job_no')
    def _check_job_no_unique(self):
        for record in self:
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
            task_date = task_data.get('bc_task_date')
            task_address = task_data.get('bc_task_address')            
            planninglines = task_data.get('bc_planninglines', [])

            task = self.env['bctask'].sudo().search([('task_no','=',task_no), ('job_id','=',job_rec.id)], limit=1) 
            # apply sudo due to Odoo ORM respects record rules and access rights. 
            # If your current user doesn't have permission to read the record, 
            # search() will return an empty recordset even if it exists in the database.
            if task:
                task.task_desc = task_desc                 
                task.task_date = task_date
                task.task_address = task_address
            else:
                task = self.env['bctask'].create({
                    'task_no': task_no,
                    'job_id': job_rec.id,
                    'task_desc': task_desc,                    
                    'task_date': datetime.strptime(task_date, '%Y-%m-%d') if task_date else False,
                    'task_address': task_address,
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
                resource_id = 0
                product_id = 0
                text_val = ''
                planning_line_type_odoo = False
                planning_line_type = pl_data.get('bc_jobplanningline_type')
                if planning_line_type == 'Resource':
                    resource_id = planningline_resid
                    planning_line_type_odoo = 'resource'
                if planning_line_type == 'Item':
                    product_id = planningline_resid
                    planning_line_type_odoo = 'item'
                if planning_line_type == 'Text':
                    text_val = planning_line_no
                    planning_line_type_odoo = 'text'

                # Check resource id
                if resource_id:
                    res_partner = self.env['res.partner'].sudo().search([('id', '=', resource_id)])
                    if not res_partner:
                        raise ValidationError(f'Resource not found for partner id {resource_id}')
                        # to avoid above error:
                        # in BC the Resource card should be link with Odoo Contact. BC Field = Planning Resource Id
                        # but how to do that in BC? at the moment it no intarface in BC to link BC Resource with Odoo Contact.
                # Check product id
                if product_id:
                    product = self.env['product.product'].sudo().search([('id', '=', product_id)])
                    if not product:
                        raise ValidationError(f'Product not found for product id {product_id}')
                        # to avoid above error:
                        # in BC the Item card should be link with Odoo product.product. BC Field = No.
                        # but how to do that in BC? at the moment it no intarface in BC to link BC Item with Odoo product.product.

                planningline_rec = self.env['bcplanningline'].search([('planning_line_lineno','=',planning_line_lineno), ('task_id','=',task.id)], limit=1)
                if planningline_rec:
                    planningline_rec.planning_line_no = planning_line_no
                    planningline_rec.planning_line_desc= planning_line_desc
                    
                    planningline_rec.planning_line_type = planning_line_type_odoo
                    planningline_rec.resource_id = resource_id                    
                    planningline_rec.product_id = product_id
                    planningline_rec.text_value = text_val
                    
                    planningline_rec.vendor_id = planningline_vendorid if planningline_vendorid else False
                    planningline_rec.start_datetime = datetime.strptime(planningline_datetimestart, '%Y-%m-%dT%H:%M:%S') if planningline_datetimestart else False
                    planningline_rec.end_datetime = datetime.strptime(planningline_datetimeend, '%Y-%m-%dT%H:%M:%S') if planningline_datetimeend else False
                else:
                    self.env['bcplanningline'].create({
                        'planning_line_lineno': planning_line_lineno or 0,
                        'planning_line_no': planning_line_no or '',  # required field fallback
                        'planning_line_desc': planning_line_desc,
                        
                        'planning_line_type': planning_line_type_odoo,
                        'resource_id': resource_id,                    
                        'product_id': product_id,
                        'text_value': text_val,

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
    task_date = fields.Date(string="Date")
    task_address = fields.Char(string="Address")
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

    earliest_start_datetime = fields.Datetime(
        string='Earliest Start',
        compute='_compute_earliest_start',
        store=True,
    )

    @api.depends('planning_line.start_datetime')
    def _compute_earliest_start(self):
        for rec in self:
            # collect non-false datetimes
            dates = rec.planning_line.mapped('start_datetime')
            dates = [d for d in dates if d]
            rec.earliest_start_datetime = min(dates) if dates else False


class bcplanning_line(models.Model):
    _name = 'bcplanningline'
    _description = 'bcplanningline'
    _rec_name = 'planning_line_no'

    planning_line_lineno = fields.Integer(required=True) # BC: "Job Planning Line"."Line No."
    
    #region ***** Many2one depend on selection
    planning_line_type = fields.Selection(string="Planning Line Type",
                                        selection=[
                                            ('resource','Resource'),
                                            ('item','Item'),
                                            ('text','Text')
                                        ], required=True) # BC: "Job Planning Line".Type

    resource_id = fields.Many2one(
        comodel_name='res.partner', 
        string='Resource',
        ondelete='restrict',
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',        
        ondelete='restrict',
        index=True,
    )
    text_value = fields.Char(string='Text')
    
    # a computed helper to get the currently selected "target"
    # They are not required in data entry scope, 
    # but are useful whenever you need a single place to read a target record 
    # (for reports, generic processing, API, templates, or to build a Reference-like behavior without changing your DB schema).
    target_model = fields.Char(string='Target model', compute='_compute_target_model')
    target_id = fields.Integer(string='Target id', compute='_compute_target_model')

    @api.depends('planning_line_type', 'resource_id', 'product_id', 'text_value')
    def _compute_target_model(self):
        for rec in self:
            rec.target_model = False
            rec.target_id = False
            if rec.planning_line_type == 'resource' and rec.resource_id:
                rec.target_model = 'res.partner'
                rec.target_id = rec.resource_id.id
            elif rec.planning_line_type == 'item' and rec.product_id:
                rec.target_model = 'product.product'
                rec.target_id = rec.product_id.id
            elif rec.planning_line_type == 'text' and rec.text_value:
                rec.target_model = 'ir.char'  # example placeholder
                rec.target_id = 0

    @api.onchange('planning_line_type')
    def _onchange_planning_line_type(self):
        # clear irrelevant fields when switching type (so only the current one is used)
        for rec in self:
            if rec.planning_line_type != 'resource':
                rec.resource_id = False
            if rec.planning_line_type != 'item':
                rec.product_id = False
            if rec.planning_line_type != 'text':
                rec.text_value = False

    @api.constrains('planning_line_type', 'resource_id', 'product_id', 'text_value')
    def _check_one_target_filled(self):
        for rec in self:
            if rec.planning_line_type == 'resource' and not rec.resource_id:
                raise ValidationError("Resource is required when type is 'Resource'.")
            if rec.planning_line_type == 'item' and not rec.product_id:
                raise ValidationError("Item is required when type is 'Item'.")
            if rec.planning_line_type == 'text' and not rec.text_value:
                raise ValidationError("Text is required when type is 'Text'.")

    #endregion of Many2one depend on selection
    
    planning_line_no = fields.Char()    # BC: "Job Planning Line"."No."
    planning_line_desc = fields.Char()  # BC: "Job Planning Line".Description   

    task_id = fields.Many2one(
        comodel_name='bctask',
        string="Task Reference",
        required=True, ondelete='cascade', index=True, copy=False) # BC: "Job Planning Line"."Job Task No."

    job_id = fields.Many2one(
        comodel_name='bcproject',
        string="Project Reference",
        compute="_get_job_id", store=True) # BC: "Job Planning Line"."Job No."
        
    vendor_id = fields.Many2one('res.partner', string='Vendor', domain="[]")
        
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
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json

class bcplanning_project(models.Model):
    _name = 'bcproject'
    _description = 'bcproject'
    _rec_name = 'job_no'
    
    job_no = fields.Char(string="Job No.", required=True)
    job_desc = fields.Char(string="Description")
    partner_id = fields.Many2one('res.partner', string='Partner', domain="[]")
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
        job_partner_id = posted_data.get('partner_id')
        if not job_partner_id:
            raise ValidationError(f'Parner id not found for Project No. {job_no}')
        res_partner = self.env['res.partner'].sudo().search([('id','=',job_partner_id)])
        if not res_partner:
            raise ValidationError(f'Parner not found for partner id {job_partner_id}')
        res_partner = res_partner[0]

        tasks = posted_data.get('tasks', [])

        # Create the bcproject record
        bcproject = self.env['bcproject'].create({
            'job_no': job_no,
            'job_desc': job_desc,
            'partner_id': res_partner.id,
        })

        for task_data in tasks:
            task_no = task_data.get('bc_task_no')
            task_desc = task_data.get('bc_task_desc')
            planninglines = task_data.get('bc_planninglines', [])

            bctask = self.env['bctask'].create({
                'task_no': task_no,
                'task_desc': task_desc,
                'job_id': bcproject.id,
            })

            for pl_data in planninglines:
                planning_line_no = pl_data.get('bc_jobplanningline_lineno')
                planning_line_desc = pl_data.get('bc_jobplanningline_no') + ' - ' + pl_data.get('bc_jobplanningline_desc')

                self.env['bcplanningline'].create({
                    'planning_line_no': planning_line_no or '',  # required field fallback
                    'planning_line_desc': planning_line_desc,
                    'task_id': bctask.id,
                })

        return {
            'job_id': bcproject.id,
            'job_no': bcproject.job_no,
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

    planning_line_no = fields.Char(required=True)
    planning_line_desc = fields.Char()    
    task_id = fields.Many2one(
        comodel_name='bctask',
        string="Task Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    job_id = fields.Many2one(
        comodel_name='bcproject',
        string="Project Reference",
        compute="_get_job_id", store=True)
    resource_id = fields.Many2one('res.partner', string='Partner', domain="[]")
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',        
        ondelete='restrict',
        index=True,
    )

    @api.depends('task_id')
    def _get_job_id(self):
        for record in self:
            record.job_id = False
            task = self.env['bctask'].search([('id','=',record.task_id)])
            if task:
                record.job_id = task[0].job_id.id

    @api.constrains('planning_line_no', 'task_id')
    def _check_job_no_unique(self):
        for record in self:
            # search for another record with the same planning_line_no, task_id
            existing = self.env['bcplanningline'].search([
                ('planning_line_no', '=', record.planning_line_no),
                ('task_id', '=', record.task_id.id),            
                ('id', '!=', record.id)
            ], limit=1)
            if existing:
                raise ValidationError(f'Planning Line No must be unique per Task No.!, duplicates on planning_line_no = {record.planning_line_no}, task No = {record.task_id.task_no}, Job No = {record.job_id.job_no}')
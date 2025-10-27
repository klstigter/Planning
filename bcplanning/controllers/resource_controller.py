# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

class ResourceApiController(http.Controller):

    def _get_user_vendor(self):
        """Resolve the current user's mapped vendor via res.partner."""
        user = request.env.user
        mapping = []
        if user.partner_id.parent_id:
            mapping = request.env['res.partner'].sudo().search([('id', '=', user.partner_id.parent_id.id)], limit=1)
        else:
            mapping = request.env['res.partner'].sudo().search([('id', '=', user.partner_id.id)], limit=1)
        if not mapping:
            #raise ValidationError("Setting of user vs vendor does not exist!")
            return False

        return mapping.sudo()

    def _resource_to_dict(self, partner):
        return {
            'res_id': partner.id,
            'res_name': partner.name or '',
        }

    @http.route('/partner/resources', type='http', auth='user', website=True, methods=['GET'])
    def partner_resources(self, **kwargs):
        """Render the website page. Data is reloaded via JSON for CRUD."""
        vendor = self._get_user_vendor()
        if not vendor:
            datas = {
                'message_title': "No vendor mapping",
                'message_text': "No vendor mapping found for your account. Please contact your administrator.",
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)

        datas = {
            'partner_id': vendor.id,
            'partner_name': vendor.name or '',
        }
        return request.render('bcplanning.web_partner_resource_template', datas)

    @http.route('/partner/resources/data', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_data(self):
        """Return the list of child resources for the current user's vendor."""
        vendor = self._get_user_vendor()
        if not vendor:
            datas = {
                'message_title': "No vendor mapping",
                'message_text': "No vendor mapping found for your account. Please contact your administrator.",
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)

        children = request.env['res.partner'].sudo().search([('parent_id', '=', vendor.id)])
        return {
            'ok': True,
            'partner_id': vendor.id,
            'partner_name': vendor.name or '',
            'resources': [self._resource_to_dict(c) for c in children],
        }

    @http.route('/partner/resources/create', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_create(self, name=None):
        """Create a new child resource (res.partner) under the user's vendor."""
        if not name or not name.strip():
            return {'ok': False, 'error': 'Name is required.'}
        vendor = self._get_user_vendor()
        if not vendor:
            datas = {
                'message_title': "No vendor mapping",
                'message_text': "No vendor mapping found for your account. Please contact your administrator.",
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)

        vals = {
            'name': name.strip(),
            'parent_id': vendor.id,
            # Optional: enforce as contact (not company)
            'company_type': 'person',
            'type': 'contact',
        }
        rec = request.env['res.partner'].sudo().create(vals)
        return {'ok': True, 'resource': self._resource_to_dict(rec)}

    @http.route('/partner/resources/update', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_update(self, res_id=None, name=None):
        """Update an existing child resource's name."""
        if not res_id:
            return {'ok': False, 'error': 'res_id is required.'}
        if not name or not name.strip():
            return {'ok': False, 'error': 'Name is required.'}

        vendor = self._get_user_vendor()
        if not vendor:
            datas = {
                'message_title': "No vendor mapping",
                'message_text': "No vendor mapping found for your account. Please contact your administrator.",
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)

        rp = request.env['res.partner'].sudo().browse(int(res_id))
        if not rp.exists():
            return {'ok': False, 'error': 'Resource not found.'}
        if rp.parent_id.id != vendor.id:
            return {'ok': False, 'error': 'Access denied for this resource.'}

        rp.write({'name': name.strip()})
        return {'ok': True, 'resource': self._resource_to_dict(rp)}

    @http.route('/partner/resources/delete', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_delete(self, res_id=None):
        """Delete an existing child resource."""
        if not res_id:
            return {'ok': False, 'error': 'res_id is required.'}

        vendor = self._get_user_vendor()
        if not vendor:
            datas = {
                'message_title': "No vendor mapping",
                'message_text': "No vendor mapping found for your account. Please contact your administrator.",
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)
            
        rp = request.env['res.partner'].sudo().browse(int(res_id))
        if not rp.exists():
            return {'ok': False, 'error': 'Resource not found.'}
        if rp.parent_id.id != vendor.id:
            return {'ok': False, 'error': 'Access denied for this resource.'}

        rp.unlink()
        return {'ok': True}
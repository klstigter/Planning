# -*- coding: utf-8 -*-
"""
Controller for partner resources list and CRUD with email field included.

Endpoints:
 - /partner/resources             (GET)  : render page
 - /partner/resources/data        (POST) : return resources with has_portal/login/email
 - /partner/resources/create      (POST) : create new resource, requires name+email
 - /partner/resources/update      (POST) : update resource name+email
 - /partner/resources/delete      (POST) : delete resource
 - /partner/resources/grant_portal(...) : existing grant logic (unchanged)
"""
import logging
import traceback

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class ResourceApiController(http.Controller):

    def _get_user_vendor(self):
        """Return mapped vendor partner for current user (commercial parent or partner)."""
        user = request.env.user
        if user.partner_id.parent_id:
            mapping = request.env['res.partner'].sudo().search([('id', '=', user.partner_id.parent_id.id)], limit=1)
        else:
            mapping = request.env['res.partner'].sudo().search([('id', '=', user.partner_id.id)], limit=1)
        return mapping.sudo() if mapping else False

    def _resource_to_dict(self, partner, has_portal=False, login=False):
        return {
            'res_id': partner.id,
            'res_name': partner.name or '',
            'email': partner.email or '',
            'has_portal': bool(has_portal),
            'login': login or False,
        }

    @http.route('/partner/resources', type='http', auth='user', website=True, methods=['GET'])
    def partner_resources(self, **kwargs):
        user = request.env.user
        if not user.has_group('bcplanning.group_bc_resources'):
            return request.redirect('/')

        vendor = self._get_user_vendor()
        if not vendor:
            datas = {
                'message_title': _("No vendor mapping"),
                'message_text': _("No vendor mapping found for your account. Please contact your administrator."),
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)
        
        return request.render('bcplanning.web_partner_resource_template', {
            'partner_id': vendor.id,
            'partner_name': vendor.name or '',
        })

    @http.route('/partner/resources/data', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_data(self):
        """Return child partners (resources) for vendor with portal indicator and email."""
        try:
            vendor = self._get_user_vendor()
            if not vendor:
                return {'ok': False, 'error': _('No vendor mapping found for your account.')}
            Partner = request.env['res.partner'].sudo()
            partners = Partner.search([('parent_id', '=', vendor.id)])
            partner_ids = partners.ids or []

            Users = request.env['res.users']
            # portal group check
            try:
                portal_group = request.env.ref('base.group_portal')
                portal_group_id = portal_group.id
            except Exception:
                portal_group = None
                portal_group_id = False

            portal_partner_ids = set()
            portal_login_map = {}

            if partner_ids and portal_group_id:
                portal_users = Users.sudo().search([
                    ('partner_id', 'in', partner_ids),
                    ('group_ids', 'in', portal_group_id),
                ])
                for u in portal_users:
                    if u.partner_id and u.partner_id.id:
                        portal_partner_ids.add(u.partner_id.id)
                        portal_login_map[u.partner_id.id] = u.login or portal_login_map.get(u.partner_id.id)

            resources = []
            for p in partners:
                if p.id in portal_partner_ids:
                    resources.append(self._resource_to_dict(p, has_portal=True, login=portal_login_map.get(p.id)))
                else:
                    resources.append(self._resource_to_dict(p, has_portal=False, login=False))
            return {'ok': True, 'partner_id': vendor.id, 'partner_name': vendor.name or '', 'resources': resources}
        except Exception:
            _logger.exception("Error in partner_resources_data: %s", traceback.format_exc())
            return {'ok': False, 'error': _('Failed to load resources.')}

    @http.route('/partner/resources/create', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_create(self, name=None, email=None):
        """Create a new child resource (res.partner) under the user's vendor.
        Email is required by your instance; we validate basic email presence/format here.
        """
        if not name or not name.strip():
            return {'ok': False, 'error': _('Name is required.')}
        if not email or not email.strip():
            return {'ok': False, 'error': _('Email is required.')}
        email = email.strip()
        # very basic email validation
        if '@' not in email:
            return {'ok': False, 'error': _('Invalid email address.')}
        vendor = self._get_user_vendor()
        if not vendor:
            return {'ok': False, 'error': _('No vendor mapping found for your account.')}
        vals = {
            'name': name.strip(),
            'email': email,
            'parent_id': vendor.id,
            'company_type': 'person',
            'type': 'contact',
        }
        try:
            rec = request.env['res.partner'].sudo().create(vals)
        except Exception as e:
            _logger.exception("Failed to create partner resource: %s", traceback.format_exc())
            return {'ok': False, 'error': _('Failed to create resource: %s') % str(e)}
        return {'ok': True, 'resource': self._resource_to_dict(rec)}

    @http.route('/partner/resources/update', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_update(self, res_id=None, name=None, email=None):
        """Update an existing child resource's name and email."""
        if not res_id:
            return {'ok': False, 'error': _('res_id is required.')}
        if not name or not name.strip():
            return {'ok': False, 'error': _('Name is required.')}
        if not email or not email.strip():
            return {'ok': False, 'error': _('Email is required.')}
        email = email.strip()
        if '@' not in email:
            return {'ok': False, 'error': _('Invalid email address.')}
        vendor = self._get_user_vendor()
        if not vendor:
            return {'ok': False, 'error': _('No vendor mapping found for your account.')}
        rp = request.env['res.partner'].sudo().browse(int(res_id))
        if not rp.exists():
            return {'ok': False, 'error': _('Resource not found.')}
        if rp.parent_id.id != vendor.id:
            return {'ok': False, 'error': _('Access denied for this resource.')}
        try:
            rp.write({'name': name.strip(), 'email': email})
        except Exception as e:
            _logger.exception("Failed to update partner resource %s: %s", res_id, traceback.format_exc())
            return {'ok': False, 'error': _('Failed to update resource: %s') % str(e)}
        return {'ok': True, 'resource': self._resource_to_dict(rp)}

    @http.route('/partner/resources/delete', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_delete(self, res_id=None):
        if not res_id:
            return {'ok': False, 'error': _('res_id is required.')}
        vendor = self._get_user_vendor()
        if not vendor:
            return {'ok': False, 'error': _('No vendor mapping found for your account.')}
        rp = request.env['res.partner'].sudo().browse(int(res_id))
        if not rp.exists():
            return {'ok': False, 'error': _('Resource not found.')}
        if rp.parent_id.id != vendor.id:
            return {'ok': False, 'error': _('Access denied for this resource.')}
        try:
            rp.unlink()
        except Exception as e:
            _logger.exception("Failed to delete partner resource %s: %s", res_id, traceback.format_exc())
            return {'ok': False, 'error': _('Failed to delete resource: %s') % str(e)}
        return {'ok': True}

    # partner_resources_grant_portal kept from previous implementation (unchanged here)
    @http.route('/partner/resources/grant_portal', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_grant_portal(self, res_id=None, create=False):
        """
        Grant portal access for a resource partner.
        Preferred: use portal.wizard.user.action_grant_access when portal installed.
        Fallback: link/grant existing user or, if create=True, create user.
        """
        try:
            if not res_id:
                return {'ok': False, 'error': _('res_id is required.')}
            vendor = self._get_user_vendor()
            if not vendor:
                return {'ok': False, 'error': _('No vendor mapping found for your account.')}
            rp = request.env['res.partner'].sudo().browse(int(res_id))
            if not rp.exists():
                return {'ok': False, 'error': _('Resource not found.')}
            if rp.parent_id.id != vendor.id:
                return {'ok': False, 'error': _('Access denied for this resource.')}

            Users = request.env['res.users']

            # Try portal wizard first
            try:
                portal_user_model = request.env['portal.wizard.user']
                if portal_user_model:
                    wizard_vals = {'partner_id': rp.id, 'email': rp.email or False}
                    wizard_user = portal_user_model.sudo().create(wizard_vals)
                    try:
                        wizard_user.action_grant_access()
                        user = Users.sudo().search([('partner_id', '=', rp.id)], limit=1)
                        if user and user.exists():
                            return {'ok': True, 'created': True, 'message': _('Portal access granted (portal wizard).'), 'login': user.login, 'user_id': user.id}
                    except (UserError, ValidationError) as e:
                        return {'ok': False, 'error': str(e)}
                    except Exception:
                        _logger.exception("portal wizard path failed; falling back: %s", traceback.format_exc())
            except Exception:
                pass

            # Fallback
            try:
                portal_group = request.env.ref('base.group_portal')
                portal_group_id = portal_group.id
            except Exception:
                portal_group = None
                portal_group_id = False

            if not portal_group:
                return {'ok': False, 'error': _('Portal group not found on this database.')}

            user_linked = Users.sudo().search([('partner_id', '=', rp.id)], limit=1)
            if user_linked and user_linked.exists():
                user_linked = user_linked.sudo()
                if portal_group_id not in user_linked.group_ids.ids:
                    user_linked.write({'group_ids': [(4, portal_group_id)]})
                return {'ok': True, 'created': False, 'message': _('Portal group added to existing user linked to partner.'), 'login': user_linked.login, 'user_id': user_linked.id}

            if rp.email:
                existing_user = Users.sudo().search([('login', '=', rp.email)], limit=1)
                if existing_user and existing_user.exists():
                    existing_user = existing_user.sudo()
                    existing_user.write({'partner_id': rp.id})
                    if portal_group_id not in existing_user.group_ids.ids:
                        existing_user.write({'group_ids': [(4, portal_group_id)]})
                    return {'ok': True, 'created': False, 'linked_existing': True, 'message': _('Existing user linked to partner and granted portal access.'), 'login': existing_user.login, 'user_id': existing_user.id}

            if create:
                if not rp.email:
                    return {'ok': False, 'error': _('Partner has no email. Email is required to create a user.')}
                conflict = Users.sudo().search([('login', '=', rp.email)], limit=1)
                if conflict and conflict.exists():
                    return {'ok': False, 'error': _('A user with this login already exists. Please link it manually.')}
                user_vals = {'name': rp.name or rp.display_name or 'Portal User', 'login': rp.email, 'partner_id': rp.id, 'group_ids': [(4, portal_group_id)]}
                try:
                    new_user = Users.sudo().create(user_vals)
                    return {'ok': True, 'created': True, 'message': _('Portal user created and granted portal access.'), 'login': new_user.login, 'user_id': new_user.id}
                except Exception:
                    _logger.exception("Failed to create user for partner %s: %s", rp.id, traceback.format_exc())
                    return {'ok': False, 'error': _('Failed to create user.')}
            return {'ok': False, 'created': False, 'message': _('No existing user found. Automatic user creation is disabled. Would you like to create and invite this user?')}
        except (UserError, ValidationError) as e:
            _logger.warning("Grant portal user-facing error: %s", e)
            return {'ok': False, 'error': str(e)}
        except Exception as e:
            _logger.exception("Unexpected error in partner_resources_grant_portal: %s", traceback.format_exc())
            return {'ok': False, 'error': _('Grant portal failed: %s') % (str(e) or _('unknown error'))}
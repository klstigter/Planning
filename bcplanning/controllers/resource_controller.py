# -*- coding: utf-8 -*-
"""
Complete controller for bcplanning partner resources.

Routes (JSON-RPC endpoints):
 - /partner/resources            (GET)   : render partner resources page (website)
 - /partner/resources/data       (POST)  : return resources list (JSON)
 - /partner/resources/create     (POST)  : create resource (JSON)
 - /partner/resources/update     (POST)  : update resource (JSON)
 - /partner/resources/delete     (POST)  : delete resource and linked users (JSON)
 - /partner/resources/toggle_menu(type=jsonrpc)
                                 (POST)  : toggle a menu flag (authoritative)
 - /partner/resources/grant_portal(type=jsonrpc)
                                 (POST)  : grant portal access / create user
"""
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError
import logging
import traceback
import re

_logger = logging.getLogger(__name__)


class ResourceApiController(http.Controller):
    # Mapping partner boolean fields -> ir.config_parameter keys (groups)
    MENU_PARAM_MAP = {
        'bc_projects_menu': 'bcplanning.setting.project_group_id',
        'bc_teams_menu': 'bcplanning.setting.team_group_id',
        'bc_partner_menu': 'bcplanning.setting.task_group_id',         # per your config
        'bc_bor_menu': 'bcplanning.setting.bor_group_id',
        'bc_resource_menu': 'bcplanning.setting.taskresource_group_id',
    }

    # ---------------------------
    # Helpers
    # ---------------------------
    def _get_user_vendor(self):
        """Return vendor partner for current user (commercial parent if present)."""
        try:
            user = request.env.user
            if user.partner_id and user.partner_id.parent_id:
                partner = request.env['res.partner'].sudo().browse(user.partner_id.parent_id.id)
            else:
                partner = request.env['res.partner'].sudo().browse(user.partner_id.id)
            return partner if partner.exists() else False
        except Exception:
            _logger.exception("Failed to resolve vendor for user %s", request.env.user.id)
            return False

    def _get_group_from_param(self, param_key):
        """Return res.groups record configured in ir.config_parameter (or None)."""
        try:
            val = request.env['ir.config_parameter'].sudo().get_param(param_key)
            if not val:
                return None
            try:
                gid = int(val)
            except Exception:
                m = re.search(r'(\d+)', str(val))
                gid = int(m.group(1)) if m else None
            if not gid:
                return None
            group = request.env['res.groups'].sudo().browse(gid)
            return group if group.exists() else None
        except Exception:
            _logger.exception("Failed to read group from param %s", param_key)
            return None

    def _sync_partner_user_group(self, partner, group_param_key, add=True):
        """
        Ensure that any existing res.users linked to partner have (or don't have) the group.
        Does not create users.
        """
        if not partner:
            return
        group = self._get_group_from_param(group_param_key)
        if not group:
            return
        Users = request.env['res.users'].sudo()
        users = Users.search([('partner_id', '=', partner.id)])
        for u in users:
            try:
                if add:
                    if group.id not in u.group_ids.ids:
                        u.write({'group_ids': [(4, group.id, 0)]})
                else:
                    if group.id in u.group_ids.ids:
                        u.write({'group_ids': [(3, group.id, 0)]})
            except Exception:
                _logger.exception("Failed to %s group %s for user %s", 'add' if add else 'remove', group_param_key, u.id)

    def _collect_relevant_group_ids(self):
        """Return a list of group ids that should be removed when deleting a resource."""
        gids = set()
        # portal
        try:
            portal = request.env.ref('base.group_portal')
            if portal and portal.id:
                gids.add(portal.id)
        except Exception:
            pass
        # base planning group
        try:
            base_group = self._get_group_from_param('bcplanning.setting.base_group_id')
            if base_group and base_group.id:
                gids.add(base_group.id)
        except Exception:
            pass
        # configured menu groups
        for param in set(self.MENU_PARAM_MAP.values()):
            try:
                grp = self._get_group_from_param(param)
                if grp and grp.id:
                    gids.add(grp.id)
            except Exception:
                _logger.exception("Failed reading menu group param %s", param)
        return list(gids)

    def _resource_to_dict(self, partner, portal_partner_ids=None, portal_login_map=None):
        return {
            'res_id': partner.id,
            'res_name': partner.name or '',
            'email': partner.email or '',
            'has_portal': bool(portal_partner_ids and partner.id in portal_partner_ids),
            'login': (portal_login_map.get(partner.id) if portal_login_map else False),
            'bc_projects_menu': bool(partner.bc_projects_menu),
            'bc_teams_menu': bool(partner.bc_teams_menu),
            'bc_partner_menu': bool(partner.bc_partner_menu),
            'bc_bor_menu': bool(partner.bc_bor_menu),
            'bc_resource_menu': bool(partner.bc_resource_menu),
        }

    # ---------------------------
    # Website page
    # ---------------------------
    @http.route('/partner/resources', type='http', auth='user', website=True, methods=['GET'])
    def partner_resources(self, **kwargs):
        user = request.env.user
        if not user.has_group('bcplanning.group_bc_resources'):
            return request.redirect('/')
        vendor = self._get_user_vendor()
        if not vendor:
            return request.render('bcplanning.web_partner_no_records_template', {
                'message_title': _("No vendor mapping"),
                'message_text': _("No vendor mapping found for your account. Please contact your administrator."),
            })
        return request.render('bcplanning.web_partner_resource_template', {
            'partner_id': vendor.id,
            'partner_name': vendor.name or '',
        })

    # ---------------------------
    # JSON endpoints (data)
    # ---------------------------
    @http.route('/partner/resources/data', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_data(self):
        try:
            vendor = self._get_user_vendor()
            if not vendor:
                return {'ok': False, 'error': _('No vendor mapping found for your account.')}
            Partner = request.env['res.partner'].sudo()
            partners = Partner.search([('parent_id', '=', vendor.id)])
            partner_ids = partners.ids or []

            Users = request.env['res.users'].sudo()
            portal_partner_ids = set()
            portal_login_map = {}
            try:
                portal_group = request.env.ref('base.group_portal')
                portal_group_id = portal_group.id
            except Exception:
                portal_group_id = False

            if partner_ids and portal_group_id:
                portal_users = Users.search([('partner_id', 'in', partner_ids), ('group_ids', 'in', portal_group_id)])
                for u in portal_users:
                    if u.partner_id and u.partner_id.id:
                        portal_partner_ids.add(u.partner_id.id)
                        portal_login_map[u.partner_id.id] = u.login or portal_login_map.get(u.partner_id.id)

            resources = [self._resource_to_dict(p, portal_partner_ids, portal_login_map) for p in partners]
            return {'ok': True, 'partner_id': vendor.id, 'partner_name': vendor.name or '', 'resources': resources}
        except Exception:
            _logger.exception("Error in partner_resources_data: %s", traceback.format_exc())
            return {'ok': False, 'error': _('Failed to load resources.')}

    @http.route('/partner/resources/create', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_create(self, name=None, email=None, **kwargs):
        try:
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
            vals = {'name': name.strip(), 'email': email, 'parent_id': vendor.id, 'company_type': 'person', 'type': 'contact'}
            for field in self.MENU_PARAM_MAP.keys():
                if field in kwargs:
                    val = kwargs.get(field)
                    vals[field] = True if str(val).lower() in ('1', 'true', 'yes', 'on') else False
            rec = request.env['res.partner'].sudo().create(vals)
            # sync groups for true flags (affects existing users)
            for field, param in self.MENU_PARAM_MAP.items():
                if vals.get(field):
                    self._sync_partner_user_group(rec, param, add=True)
            return {'ok': True, 'resource': self._resource_to_dict(rec)}
        except Exception:
            _logger.exception("Failed to create partner resource: %s", traceback.format_exc())
            return {'ok': False, 'error': _('Failed to create resource.')}

    @http.route('/partner/resources/update', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_update(self, res_id=None, name=None, email=None, **kwargs):
        try:
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
            write_vals = {'name': name.strip(), 'email': email}
            toggles = {}
            for field in self.MENU_PARAM_MAP.keys():
                if field in kwargs:
                    val = kwargs.get(field)
                    b = True if str(val).lower() in ('1', 'true', 'yes', 'on') else False
                    write_vals[field] = b
                    toggles[field] = b
            rp.sudo().write(write_vals)
            for field, new_val in toggles.items():
                param = self.MENU_PARAM_MAP.get(field)
                if param:
                    self._sync_partner_user_group(rp, param, add=new_val)
            return {'ok': True, 'resource': self._resource_to_dict(rp)}
        except Exception:
            _logger.exception("Failed to update partner resource %s: %s", res_id, traceback.format_exc())
            return {'ok': False, 'error': _('Failed to update resource.')}

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
        Users = request.env['res.users'].sudo()
        linked_users = Users.search([('partner_id', '=', rp.id)])
        try:
            group_ids_to_remove = self._collect_relevant_group_ids()
            # Pre-checks
            for u in linked_users:
                try:
                    if u.has_group('base.group_system'):
                        return {'ok': False, 'error': _('Cannot delete resource: linked user %s is a system user.') % (u.login or u.name)}
                except Exception:
                    return {'ok': False, 'error': _('Cannot verify linked user groups for %s') % (u.login or u.name)}
                if u.id == request.env.uid:
                    return {'ok': False, 'error': _('Cannot delete resource: linked user is the current logged-in user.')}
            # Remove groups and unlink users
            for u in linked_users:
                if group_ids_to_remove:
                    ops = []
                    for gid in group_ids_to_remove:
                        if gid in u.group_ids.ids:
                            ops.append((3, gid))
                    if ops:
                        try:
                            u.write({'group_ids': ops})
                        except Exception:
                            _logger.exception("Failed removing groups from user %s", u.id)
                try:
                    u.unlink()
                except Exception:
                    _logger.exception("Failed to unlink/delete user %s", u.id)
                    return {'ok': False, 'error': _('Failed to delete linked user %s. Please remove dependencies and try again.') % (u.login or u.name)}
            # unlink partner
            try:
                rp.unlink()
            except Exception:
                _logger.exception("Failed to delete partner %s", rp.id)
                return {'ok': False, 'error': _('Failed to delete resource partner. Ensure no other records reference it and try again.')}
            return {'ok': True}
        except Exception:
            _logger.exception("Unexpected error deleting resource %s: %s", res_id, traceback.format_exc())
            return {'ok': False, 'error': _('Failed to delete resource.')}

    # ---------------------------
    # Toggle menu (authoritative)
    # ---------------------------
    @http.route('/partner/resources/toggle_menu', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_toggle_menu(self, res_id=None, menu_field=None, value=None):
        if not res_id:
            return {'ok': False, 'error': _('res_id is required.')}
        if not menu_field or menu_field not in self.MENU_PARAM_MAP:
            return {'ok': False, 'error': _('Invalid menu field.')}
        vendor = self._get_user_vendor()
        if not vendor:
            return {'ok': False, 'error': _('No vendor mapping found for your account.')}
        rp = request.env['res.partner'].sudo().browse(int(res_id))
        if not rp.exists():
            return {'ok': False, 'error': _('Resource not found.')}
        if rp.parent_id.id != vendor.id:
            return {'ok': False, 'error': _('Access denied for this resource.')}
        b = True if str(value).lower() in ('1', 'true', 'yes', 'on') else False
        try:
            rp.sudo().write({menu_field: b})
            param = self.MENU_PARAM_MAP.get(menu_field)
            if param:
                self._sync_partner_user_group(rp, param, add=b)
            # authoritative values
            fresh = request.env['res.partner'].sudo().browse(rp.id)
            final_val = bool(fresh[menu_field])
            user_group_applied = False
            if param:
                grp = self._get_group_from_param(param)
                if grp:
                    users = request.env['res.users'].sudo().search([('partner_id', '=', fresh.id), ('group_ids', 'in', grp.id)], limit=1)
                    user_group_applied = bool(users)
            return {'ok': True, 'menu_field': menu_field, 'value': final_val, 'user_group_applied': user_group_applied}
        except Exception:
            _logger.exception("Failed to toggle menu %s for partner %s: %s", menu_field, res_id, traceback.format_exc())
            return {'ok': False, 'error': _('Failed to update setting.')}

    # ---------------------------
    # Grant portal (create/link/grant)
    # ---------------------------
    @http.route('/partner/resources/grant_portal', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_grant_portal(self, res_id=None, create=False):
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
            Users = request.env['res.users'].sudo()
            # Try portal wizard first (if available)
            try:
                portal_wizard_model = request.env['portal.wizard.user']
                if portal_wizard_model:
                    wiz = portal_wizard_model.sudo().create({'partner_id': rp.id, 'email': rp.email or False})
                    try:
                        wiz.action_grant_access()
                        user = Users.sudo().search([('partner_id', '=', rp.id)], limit=1)
                        if user and user.exists():
                            base_group = self._get_group_from_param('bcplanning.setting.base_group_id')
                            if base_group and base_group.id and base_group.id not in user.group_ids.ids:
                                user.write({'group_ids': [(4, base_group.id, 0)]})
                            # best-effort: set default password if none
                            try:
                                if not getattr(user, 'password_crypt', None):
                                    user.sudo().write({'password': '123'})
                            except Exception:
                                _logger.exception("Failed setting default password for wizard user %s", user.id)
                            return {'ok': True, 'created': True, 'message': _('Portal access granted (portal wizard).'), 'login': user.login, 'user_id': user.id}
                    except (UserError, ValidationError) as e:
                        return {'ok': False, 'error': str(e)}
                    except Exception:
                        _logger.exception("portal wizard flow failed; falling back: %s", traceback.format_exc())
            except Exception:
                pass
            # fallback grant/link/create
            try:
                portal_group = request.env.ref('base.group_portal')
                portal_group_id = portal_group.id
            except Exception:
                portal_group_id = False
            if not portal_group_id:
                return {'ok': False, 'error': _('Portal group not found on this database.')}
            # 1) existing linked user
            user_linked = Users.sudo().search([('partner_id', '=', rp.id)], limit=1)
            if user_linked and user_linked.exists():
                user_linked = user_linked.sudo()
                if portal_group_id not in user_linked.group_ids.ids:
                    user_linked.write({'group_ids': [(4, portal_group_id)]})
                base_group = self._get_group_from_param('bcplanning.setting.base_group_id')
                if base_group and base_group.id and base_group.id not in user_linked.group_ids.ids:
                    user_linked.write({'group_ids': [(4, base_group.id, 0)]})
                return {'ok': True, 'created': False, 'message': _('Portal group added to existing user linked to partner.'), 'login': user_linked.login, 'user_id': user_linked.id}
            # 2) existing user by email
            if rp.email:
                existing = Users.sudo().search([('login', '=', rp.email)], limit=1)
                if existing and existing.exists():
                    existing = existing.sudo()
                    existing.write({'partner_id': rp.id})
                    if portal_group_id not in existing.group_ids.ids:
                        existing.write({'group_ids': [(4, portal_group_id)]})
                    base_group = self._get_group_from_param('bcplanning.setting.base_group_id')
                    if base_group and base_group.id and base_group.id not in existing.group_ids.ids:
                        existing.write({'group_ids': [(4, base_group.id, 0)]})
                    return {'ok': True, 'created': False, 'linked_existing': True, 'message': _('Existing user linked to partner and granted portal access.'), 'login': existing.login, 'user_id': existing.id}
            # 3) create new user if requested
            if create:
                if not rp.email:
                    return {'ok': False, 'error': _('Partner has no email. Email is required to create a user.')}
                conflict = Users.sudo().search([('login', '=', rp.email)], limit=1)
                if conflict and conflict.exists():
                    return {'ok': False, 'error': _('A user with this login already exists. Please link it manually.')}
                base_group = self._get_group_from_param('bcplanning.setting.base_group_id')
                group_vals = [(4, portal_group_id)]
                if base_group and base_group.id:
                    group_vals.append((4, base_group.id))
                user_vals = {'name': rp.name or rp.display_name or 'Portal User', 'login': rp.email, 'partner_id': rp.id, 'group_ids': group_vals, 'password': '123'}
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
        except Exception:
            _logger.exception("Unexpected error in partner_resources_grant_portal: %s", traceback.format_exc())
            return {'ok': False, 'error': _('Grant portal failed.')}
# -*- coding: utf-8 -*-
"""
Controller for bcplanning partner resources with linked-user awareness.

Provides endpoints:
 - GET  /partner/resources            -> render partner resources page (website)
 - POST /partner/resources/data       -> JSONRPC: list resources for vendor (includes has_user/user_id)
 - POST /partner/resources/create     -> JSONRPC: create res.partner (resource)
 - POST /partner/resources/update     -> JSONRPC: update resource
 - POST /partner/resources/delete     -> JSONRPC: delete resource (safe flow)
 - POST /partner/resources/toggle_menu-> JSONRPC: toggle a menu flag (authoritative; disallow if no linked user)
 - POST /partner/resources/grant_portal-> JSONRPC: grant portal + apply base group / create user
"""
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError
import logging
import traceback
import re

_logger = logging.getLogger(__name__)


class ResourceApiController(http.Controller):
    # Keep mapping as per your configuration
    MENU_PARAM_MAP = {
        'bc_projects_menu': 'bcplanning.setting.project_group_id',
        'bc_teams_menu': 'bcplanning.setting.team_group_id',
        'bc_planning_menu': 'bcplanning.setting.planning_group_id',
        'bc_bor_menu': 'bcplanning.setting.bor_group_id',
        'bc_resource_menu': 'bcplanning.setting.taskresource_group_id',
    }

    # ---------------------------
    # Helpers
    # ---------------------------
    def _get_user_vendor(self):
        """Return mapped vendor partner for current user (commercial parent or partner)."""
        user = request.env.user
        try:
            if user.partner_id and user.partner_id.parent_id:
                partner = request.env['res.partner'].sudo().browse(user.partner_id.parent_id.id)
            else:
                partner = request.env['res.partner'].sudo().browse(user.partner_id.id)
            return partner if partner.exists() else False
        except Exception:
            _logger.exception("Failed to resolve vendor for user %s", request.env.user.id)
            return False

    def _get_group_from_param(self, param_key):
        """Return res.groups record based on stored config parameter (string id)."""
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
        Ensure linked user(s) of partner have (or do not have) the group.
        Affects only existing linked users.
        """
        if not partner:
            return
        group = self._get_group_from_param(group_param_key)
        if not group:
            return
        Users = request.env['res.users'].sudo()
        users = Users.search([('partner_id', '=', partner.id)])
        for user in users:
            try:
                if add:
                    if group.id not in user.group_ids.ids:
                        user.write({'group_ids': [(4, group.id, 0)]})
                else:
                    if group.id in user.group_ids.ids:
                        user.write({'group_ids': [(3, group.id, 0)]})
            except Exception:
                _logger.exception("Failed to modify group %s for user %s", group_param_key, user.id)

    def _collect_relevant_group_ids(self):
        """
        Collect group ids that should be removed from linked users when deleting a resource:
          - portal group (base.group_portal)
          - BC Planning base group (bcplanning.setting.base_group_id)
          - any groups configured in MENU_PARAM_MAP
        """
        gids = set()
        try:
            portal = request.env.ref('base.group_portal')
            if portal and portal.id:
                gids.add(portal.id)
        except Exception:
            pass
        try:
            base_group = self._get_group_from_param('bcplanning.setting.base_group_id')
            if base_group and base_group.id:
                gids.add(base_group.id)
        except Exception:
            pass
        for param in set(self.MENU_PARAM_MAP.values()):
            try:
                grp = self._get_group_from_param(param)
                if grp and grp.id:
                    gids.add(grp.id)
            except Exception:
                _logger.exception("Failed reading menu group param %s", param)
        return list(gids)

    def _resource_to_dict(self, partner, portal_partner_ids=None, portal_login_map=None, user_map=None):
        has_user = bool(user_map and partner.id in user_map)
        return {
            'res_id': partner.id,
            'res_name': partner.name or '',
            'email': partner.email or '',
            'has_portal': bool(portal_partner_ids and partner.id in portal_partner_ids),
            'login': (portal_login_map.get(partner.id) if portal_login_map else False),
            'has_user': has_user,
            'user_id': (user_map.get(partner.id) if user_map else False),
            'bc_projects_menu': bool(partner.bc_projects_menu),
            'bc_teams_menu': bool(partner.bc_teams_menu),
            'bc_planning_menu': bool(partner.bc_planning_menu),
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
            datas = {
                'message_title': _("No vendor mapping"),
                'message_text': _("No vendor mapping found for your account. Please contact your administrator."),
            }
            return request.render('bcplanning.web_partner_no_records_template', datas)
        return request.render('bcplanning.web_partner_resource_template', {
            'partner_id': vendor.id,
            'partner_name': vendor.name or '',
        })

    # ---------------------------
    # Data endpoints
    # ---------------------------
    @http.route('/partner/resources/data', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def partner_resources_data(self):
        """Return child partners (resources) for vendor with portal indicator, menu flags and user presence."""
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

            # Map any linked users to partner_id (for has_user)
            user_map = {}
            if partner_ids:
                linked_users = Users.search([('partner_id', 'in', partner_ids)])
                for u in linked_users:
                    if u.partner_id and u.partner_id.id:
                        user_map.setdefault(u.partner_id.id, u.id)

            resources = [self._resource_to_dict(p, portal_partner_ids, portal_login_map, user_map) for p in partners]
            return {'ok': True, 'partner_id': vendor.id, 'partner_name': vendor.name or '', 'resources': resources}
        except Exception:
            _logger.exception("Error in partner_resources_data: %s", traceback.format_exc())
            return {'ok': False, 'error': _('Failed to load resources.')}

    # ---------------------------
    # Create / Update / Delete
    # ---------------------------
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
            for u in linked_users:
                try:
                    if u.has_group('base.group_system'):
                        return {'ok': False, 'error': _('Cannot delete resource: linked user %s is a system user.') % (u.login or u.name)}
                except Exception:
                    return {'ok': False, 'error': _('Cannot verify linked user groups for %s') % (u.login or u.name)}
                if u.id == request.env.uid:
                    return {'ok': False, 'error': _('Cannot delete resource: linked user is the current logged-in user.')}
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
    # Toggle menu (authoritative; require linked user)
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

        # enforce linked user presence
        Users = request.env['res.users'].sudo()
        linked_user = Users.search([('partner_id', '=', rp.id)], limit=1)
        if not linked_user:
            return {'ok': False, 'error': _('No linked user found for this resource. Grant portal access before toggling menus.')}

        b = True if str(value).lower() in ('1', 'true', 'yes', 'on') else False
        try:
            rp.sudo().write({menu_field: b})
            param = self.MENU_PARAM_MAP.get(menu_field)
            if param:
                self._sync_partner_user_group(rp, param, add=b)
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

            # fallback: portal group
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
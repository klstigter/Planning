from odoo import models, fields, api
import re
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    MENU_PARAM_MAP = {
        'bc_projects_menu': 'bcplanning.setting.project_group_id',
        'bc_teams_menu': 'bcplanning.setting.team_group_id',
        'bc_planning_menu': 'bcplanning.setting.planning_group_id',
        'bc_bor_menu': 'bcplanning.setting.bor_group_id',
        'bc_resource_menu': 'bcplanning.setting.taskresource_group_id',
    }

    # Computed fields that reflect whether any linked user has the configured group.
    # They are computed from user group membership but have an inverse so UI can write them.
    bc_projects_menu = fields.Boolean(
        string="BC Projects Menu",
        compute="_compute_menu_flags",
        inverse="_inverse_menu_flags",
        store=False,
    )
    bc_teams_menu = fields.Boolean(
        string="BC Teams Menu",
        compute="_compute_menu_flags",
        inverse="_inverse_menu_flags",
        store=False,
    )
    bc_planning_menu = fields.Boolean(
        string="BC Partner Menu",
        compute="_compute_menu_flags",
        inverse="_inverse_menu_flags",
        store=False,
    )
    bc_bor_menu = fields.Boolean(
        string="BC BOR Menu",
        compute="_compute_menu_flags",
        inverse="_inverse_menu_flags",
        store=False,
    )
    bc_resource_menu = fields.Boolean(
        string="BC Resource Menu",
        compute="_compute_menu_flags",
        inverse="_inverse_menu_flags",
        store=False,
    )

    def _get_group_from_param(self, param_key):
        """Read the configured group id from ir.config_parameter and return res.groups record or None."""
        try:
            val = self.env['ir.config_parameter'].sudo().get_param(param_key)
            if not val:
                return None
            # param may be numeric id or string like 'res.groups,12' - extract digits
            try:
                gid = int(val)
            except Exception:
                m = re.search(r'(\d+)', str(val))
                gid = int(m.group(1)) if m else None
            if not gid:
                return None
            grp = self.env['res.groups'].sudo().browse(gid)
            return grp if grp.exists() else None
        except Exception:
            _logger.exception("Failed to read group param %s", param_key)
            return None

    def _compute_menu_flags(self):
        """Compute whether any linked user of the partner has the configured group."""
        for rec in self:
            for field_name, param_key in self.MENU_PARAM_MAP.items():
                value = False
                grp = self._get_group_from_param(param_key)
                if grp:
                    # check any res.users linked to this partner that have the group
                    users = self.env['res.users'].sudo().search([
                        ('partner_id', '=', rec.id),
                        ('group_ids', 'in', grp.id),
                    ], limit=1)
                    value = bool(users)
                # set computed field
                rec[field_name] = value

    def _inverse_menu_flags(self):
        """
        Inverse handler: when UI writes to the computed field, add/remove the configured group
        from existing linked users of the partner. If there is no linked user, do nothing.
        """
        Users = self.env['res.users'].sudo()
        for rec in self:
            for field_name, param_key in self.MENU_PARAM_MAP.items():
                try:
                    grp = self._get_group_from_param(param_key)
                    if not grp:
                        # nothing to do if group is not configured
                        continue
                    wanted = bool(rec[field_name])
                    # find all users linked to this partner
                    linked_users = Users.search([('partner_id', '=', rec.id)])
                    if not linked_users:
                        # conservative: do not auto-create users here
                        continue
                    for u in linked_users:
                        if wanted:
                            if grp.id not in u.group_ids.ids:
                                u.write({'group_ids': [(4, grp.id)]})
                        else:
                            if grp.id in u.group_ids.ids:
                                u.write({'group_ids': [(3, grp.id)]})
                except Exception:
                    _logger.exception("Inverse menu flag failed for partner %s field %s", rec.id, field_name)
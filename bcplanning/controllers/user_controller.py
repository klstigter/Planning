from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied
import json
from odoo.http import Response
from odoo.exceptions import ValidationError

class UserApiController(http.Controller):

    @http.route('/planning/users', type='http', auth='api_key', methods=['GET'], csrf=False)
    def getpartners(self):
        user_recs = []
        internal_users = request.env['res.users'].sudo().search([('share', '=', False),('active','=',True)])
        if internal_users:
            for _user in internal_users:
                user_recs.append({
                    'user_id': _user.id,
                    'user_name': _user.name,
                })
        return Response(json.dumps(user_recs),content_type='application/json;charset=utf-8',status=200)
from odoo import models
from odoo.exceptions import ValidationError
import requests
import json
import logging
_logger = logging.getLogger(__name__)

class bcplanning_utils(models.Model):
    _name = 'bcplanning_utils'

    def _get_token(self):
        client_id = self.env['ir.config_parameter'].sudo().get_param('bcplanning.setting.client.id')
        if not client_id:
            raise ValidationError("Client Id not found!")
        client_secret = self.env['ir.config_parameter'].sudo().get_param('bcplanning.setting.client.secret')
        if not client_secret:
            raise ValidationError("Client Secret not found!")
        tenant_id = self.env['ir.config_parameter'].sudo().get_param('bcplanning.setting.tenant.id')
        if not tenant_id:
            raise ValidationError("Tenant Id not found!")
        access_token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
        scope = 'https://api.businesscentral.dynamics.com/.default'

        payload = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': scope
        }

        response = requests.post(access_token_url, data=payload)
        response.raise_for_status()
        token_data = response.json()
        return token_data['access_token']

    def post_request(self,url, payload):
        token = self._get_token()
        if not token:
            raise Exception(f"get token failed")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(url, headers=headers, data=json.dumps(payload))        
        return response

    def update_bc_planningline(self, payload=None):
        env_name = self.env['ir.config_parameter'].sudo().get_param('bcplanning.setting.env.name')
        if not env_name:
            raise ValidationError("BC Environment name not found!")
        company_id = self.env['ir.config_parameter'].sudo().get_param('bcplanning.setting.company.id')
        if not company_id:
            raise ValidationError("BC Company Id not found!")
        url = f'https://api.businesscentral.dynamics.com/v2.0/{env_name}/api/ddsia/planning/v1.0/companies({company_id})/jobPlanningLines'
        response = self.post_request(url, payload)
        if response.status_code in (200, 201):
            return True
        else:
            return False

    def update_bc_planningline_item(self, payload=None):
        
        _logger.exception("payload for BC: %s", payload)

        env_name = self.env['ir.config_parameter'].sudo().get_param('bcplanning.setting.env.name')
        if not env_name:
            raise ValidationError("BC Environment name not found!")
        company_id = self.env['ir.config_parameter'].sudo().get_param('bcplanning.setting.company.id')
        if not company_id:
            raise ValidationError("BC Company Id not found!")
        url = f'https://api.businesscentral.dynamics.com/v2.0/{env_name}/api/ddsia/planning/v1.0/companies({company_id})/jobPlanningLinebors'
        response = self.post_request(url, payload)
        if response.status_code in (200, 201):
            return True
        else:
            return False
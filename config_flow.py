from homeassistant import config_entries
import voluptuous as vol

from .const import DOMAIN, CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY

class CoralMyloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="Coral Mylo", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_IP_ADDRESS): str,
            vol.Required(CONF_REFRESH_TOKEN): str,
            vol.Required(CONF_API_KEY): str,
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN

DATA_SCHEMA = vol.Schema({
    vol.Required("ip_address"): str,
    vol.Required("api_key"): str,
    vol.Required("refresh_token"): str,
})

class CoralMyloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coral Mylo."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input["ip_address"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"Mylo ({user_input['ip_address']})", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA
        )

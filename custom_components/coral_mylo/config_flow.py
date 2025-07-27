"""Configuration flow for the Coral Mylo integration."""

from homeassistant import config_entries
import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN, CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY

class CoralMyloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the config flow."""

        _LOGGER.debug("Starting config flow user step")
        errors = {}

        if user_input is not None:
            _LOGGER.debug("Creating entry for %s", user_input.get(CONF_IP_ADDRESS))
            return self.async_create_entry(title="Coral Mylo", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_IP_ADDRESS): str,
            vol.Required(CONF_REFRESH_TOKEN): str,
            vol.Required(CONF_API_KEY): str,
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

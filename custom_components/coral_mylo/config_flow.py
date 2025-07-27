"""Config flow for the Coral Mylo integration."""

import logging
from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)


class CoralMyloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for Coral Mylo."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user provides credentials."""
        errors = {}
        _LOGGER.debug("Starting config flow user step")

        if user_input is not None:
            return self.async_create_entry(title="Coral Mylo", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Required(CONF_REFRESH_TOKEN): str,
                vol.Required(CONF_API_KEY): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

import logging
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN, DEFAULT_REFRESH_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up number entity for refresh interval."""
    camera = hass.data.get(DOMAIN, {}).get("cameras", {}).get(entry.entry_id)
    if not camera:
        _LOGGER.error("Camera entity not available for number setup")
        return
    async_add_entities([MyloRefreshIntervalNumber(camera)])


class MyloRefreshIntervalNumber(RestoreEntity, NumberEntity):
    """Number entity to control automatic refresh interval."""

    def __init__(self, camera):
        self._camera = camera
        device_id = camera._device_id
        self._attr_name = "Mylo Refresh Interval"
        self._attr_unique_id = f"mylo_refresh_interval_{device_id}"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 3600
        self._attr_native_step = 10
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_device_info = camera.device_info
        self._value = DEFAULT_REFRESH_INTERVAL

    @property
    def native_value(self):
        return self._value

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            try:
                self._value = int(float(state.state))
            except ValueError:
                self._value = DEFAULT_REFRESH_INTERVAL
            await self._camera.set_refresh_interval(self._value)

    async def async_set_native_value(self, value: float) -> None:
        self._value = int(value)
        await self._camera.set_refresh_interval(self._value)

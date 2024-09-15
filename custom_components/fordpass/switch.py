"""Fordpass Switch Entities"""
import logging

from homeassistant.components.switch import SwitchEntity

from . import FordPassEntity
from .const import DOMAIN, SWITCHES, COORDINATOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Switch from the config."""
    entry = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # switches = [Switch(entry)]
    # async_add_entities(switches, False)
    for key, value in SWITCHES.items():
        sw = Switch(entry, key, config_entry.options)
        async_add_entities([sw], False)


class Switch(FordPassEntity, SwitchEntity):
    """Define the Switch for turning ignition off/on"""

    def __init__(self, coordinator, switch, options):
        """Initialize"""
        self._device_id = "fordpass_" + switch
        self.switch = switch
        self.coordinator = coordinator
        self.data = coordinator.data["metrics"]
        # Required for HA 2022.7
        self.coordinator_context = object()

    async def async_turn_on(self, **kwargs):
        """Send request to vehicle on switch status on"""
        if self.switch == "ignition":
            await self.coordinator.hass.async_add_executor_job(
                self.coordinator.vehicle.start
            )
            await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Send request to vehicle on switch status off"""
        if self.switch == "ignition":
            await self.coordinator.hass.async_add_executor_job(
                self.coordinator.vehicle.stop
            )
            await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def name(self):
        """return switch name"""
        return "fordpass_" + self.switch + "_Switch"

    @property
    def device_id(self):
        """return switch device id"""
        return self.device_id

    @property
    def is_on(self):
        """Check status of switch"""
        if self.switch == "ignition":
            metrics = self.coordinator.data.get("metrics", {})

            ignition_status = metrics.get("ignitionStatus", {})
            remote_start_status = metrics.get("remoteStartStatus", {})

            _LOGGER.debug(ignition_status)
            _LOGGER.debug(remote_start_status)

            if ignition_status.get("value", "OFF") == "ENGINE_RUNNING":
                return True

            if remote_start_status.get("status", "OFF") == "ENGINE_RUNNING":
                return True

        return False

    @property
    def icon(self):
        """Return icon for switch"""
        return SWITCHES[self.switch]["icon"]

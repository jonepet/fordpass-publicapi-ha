"""Config flow for FordPass integration."""
import logging
import re
import random
import string
import hashlib
import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from base64 import urlsafe_b64encode


from .const import (  # pylint:disable=unused-import
    CONF_DISTANCE_UNIT,
    CONF_PRESSURE_UNIT,
    DEFAULT_DISTANCE_UNIT,
    DEFAULT_PRESSURE_UNIT,
    DISTANCE_UNITS,
    DOMAIN,
    PRESSURE_UNITS,
    VIN,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_DEFAULT,
    DISTANCE_CONVERSION_DISABLED,
    DISTANCE_CONVERSION_DISABLED_DEFAULT
)
from .fordpass_new import Vehicle

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("client_id"): str,
        vol.Required("client_secret"): str
    }
)



VIN_SCHEME = vol.Schema(
    {
        vol.Required(VIN, default=""): str,
    }
)

@callback
def configured_vehicles(hass):
    """Return a list of configured vehicles"""
    return {
        entry.data[VIN]
        for entry in hass.config_entries.async_entries(DOMAIN)
    }

async def validate_token(hass: core.HomeAssistant, data):
    vehicle = Vehicle(data["client_id"], data["client_secret"], "")
    results = await hass.async_add_executor_job(
        vehicle.generate_tokens,
        data["tokenstr"]
        )

    if results:
        _LOGGER.debug("Getting Vehicles")
        vehicles = await(hass.async_add_executor_job(vehicle.vehicles))
        _LOGGER.debug(vehicles)
        return vehicles

async def validate_vin(hass: core.HomeAssistant, data):
    vehicle = Vehicle(data['client_id'], data['client_secret'], data[VIN])
    test = await(hass.async_add_executor_job(vehicle.get_status))
    _LOGGER.debug("GOT SOMETHING BACK?")
    _LOGGER.debug(test)
    if test and test.status_code == 200:
        _LOGGER.debug("200 Code")
        return True
    if not test:
        raise InvalidVin
    return False

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FordPass."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    client_secret = None
    client_id = None
    login_input = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self.client_id = user_input['client_id']
                self.client_secret = user_input['client_secret']

                return await self.async_step_token(None)
            except CannotConnect:
                print("EXCEPT")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_token(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                token = user_input["tokenstr"]

                if self.check_token(token):
                    user_input["client_id"] = self.client_id
                    user_input["client_secret"] = self.client_secret
                    _LOGGER.debug(user_input)
                    info = await validate_token(self.hass, user_input)
                    self.login_input = user_input
                    if info is None:
                        self.vehicles = None
                        _LOGGER.debug("NO VEHICLES FOUND")
                    else:
                        self.vehicles = info

                    if self.vehicles is None:
                        return await self.async_step_vin()

                    return await self.async_step_vehicle()

                else:
                    errors["base"] = "invalid_token"

            except CannotConnect:
                print("EXCEPT")
                errors["base"] = "cannot_connect"

        if self.client_id is not None:
            return self.async_show_form(
                step_id="token", data_schema=
                    vol.Schema(
                    {
                        vol.Required("tokenstr"): str,
                    }
                    )
                , errors=errors
            )

    def check_token(self, token):
        if "https://localhost:3000/?state=123&code=" in token:
            return True
        return False
    


    async def async_step_vin(self, user_input=None):
        """Handle manual VIN entry"""
        errors = {}
        if user_input is not None:
            data = self.login_input
            data["vin"] = user_input["vin"]
            vehicle = None
            try:
                vehicle = await validate_vin(self.hass, data)
            except InvalidVin:
                errors["base"] = "invalid_vin"
            except Exception:
                errors["base"] = "unknown"

            if vehicle :
                return self.async_create_entry(title=f"Vehicle ({user_input[VIN]})", data=self.login_input)

            # return self.async_create_entry(title=f"Enter VIN", data=self.login_input)
        _LOGGER.debug(self.login_input)
        return self.async_show_form(step_id="vin", data_schema=VIN_SCHEME, errors=errors)
    
    async def async_step_vehicle(self, user_input=None):
        if user_input is not None:
            _LOGGER.debug("Checking Vehicle is accessible")
            self.login_input[VIN] = user_input["vin"]
            _LOGGER.debug(self.login_input)
            return self.async_create_entry(title=f"Vehicle ({user_input[VIN]})", data=self.login_input)
        
        _LOGGER.debug(self.vehicles)

        configured = configured_vehicles(self.hass)
        _LOGGER.debug(configured)
        avaliable_vehicles = {}
        for vehicle in self.vehicles:
            _LOGGER.debug(vehicle)
            if vehicle["vehicleId"] not in configured:
                if "nickName" in vehicle:
                    avaliable_vehicles[vehicle["vehicleId"]] = vehicle["nickName"] + f" ({vehicle['vehicleId']})"
                else:
                    avaliable_vehicles[vehicle["vehicleId"]] = f" ({vehicle['vehicleId']})"

        if not avaliable_vehicles:
            _LOGGER.debug("No Vehicles?")
            return self.async_abort(reason="no_vehicles")

        return self.async_show_form(
            step_id="vehicle",
            data_schema = vol.Schema(
            { vol.Required(VIN): vol.In(avaliable_vehicles)}
            ),
            errors = {}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = {
            vol.Optional(
                CONF_PRESSURE_UNIT,
                default=self.config_entry.options.get(
                    CONF_PRESSURE_UNIT, DEFAULT_PRESSURE_UNIT
                ),
            ): vol.In(PRESSURE_UNITS),
            vol.Optional(
                CONF_DISTANCE_UNIT,
                default=self.config_entry.options.get(
                    CONF_DISTANCE_UNIT, DEFAULT_DISTANCE_UNIT
                ),
            ): vol.In(DISTANCE_UNITS),
            vol.Optional(
                DISTANCE_CONVERSION_DISABLED,
                default = self.config_entry.options.get(
                    DISTANCE_CONVERSION_DISABLED, DISTANCE_CONVERSION_DISABLED_DEFAULT
                ),
            ): bool,
            vol.Optional(
                UPDATE_INTERVAL,
                default=self.config_entry.options.get(
                    UPDATE_INTERVAL, UPDATE_INTERVAL_DEFAULT
                ),
            ): int,
            
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidToken(exceptions.HomeAssistantError):
    """Error to indicate there is invalid token."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidVin(exceptions.HomeAssistantError):
    """Error to indicate the wrong vin"""

class InvalidMobile(exceptions.HomeAssistantError):
    """Error to no mobile specified for South African Account"""

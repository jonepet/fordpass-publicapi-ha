"""All vehicle sensors from the accessible by the API"""

import logging
from datetime import datetime, timedelta
import json

from homeassistant.const import (
    UnitOfTemperature,
    UnitOfLength
)
from homeassistant.util import dt

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass
)


from . import FordPassEntity
from .const import CONF_DISTANCE_UNIT, CONF_PRESSURE_UNIT, DOMAIN, SENSORS, COORDINATOR


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Entities from the config."""
    entry = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    sensors = []
    for key, value in SENSORS.items():
        sensor = CarSensor(entry, key, config_entry.options)
        api_key = value["api_key"]
        api_class = value.get("api_class", None)
        sensor_type = value.get("sensor_type", None)
        string =  isinstance(api_key, str)
        if string and sensor_type == "single":
            sensors.append(sensor)
        elif string:
            if api_key and api_class and api_key in sensor.coordinator.data.get(api_class, {}):
                sensors.append(sensor)
                continue
            if api_key and api_key in sensor.coordinator.data.get("metrics", {}):
                sensors.append(sensor)
        else:
            for key in api_key:
                if key and key in sensor.coordinator.data.get("metrics", {}):
                    sensors.append(sensor)
                    continue
    _LOGGER.debug(hass.config.units)
    async_add_entities(sensors, True)


class CarSensor(
    FordPassEntity,
    SensorEntity,
):
    def __init__(self, coordinator, sensor, options):

        super().__init__(
            device_id="fordpass_" + sensor,
            name="fordpass_" + sensor,
            coordinator=coordinator
        )

        self.sensor = sensor
        self.fordoptions = options
        self._attr = {}
        self.coordinator = coordinator

        self.data = self.coordinator.data.get("vehicle", {})
        self.metrics = self.data.get("metrics", {})
        self.units = self.coordinator.hass.config.units

        self._device_id = "fordpass_" + sensor
        # Required for HA 2022.7
        self.coordinator_context = object()

    def parse_datestr(self, str):
        return dt.as_local(datetime.strptime(str + " +0000", "%m-%d-%Y %H:%M:%S %z"))

    def get_value(self, ftype):
        """Get sensor value and attributes from coordinator data"""

        self.data = self.coordinator.data
        self.metrics = self.data.get("metrics", {})
        self.units = self.coordinator.hass.config.units

        if ftype == "state":
            if self.sensor == "odometer":
                odometer = self.metrics.get("odometer", None)

                if odometer is not None:
                    return round(odometer)

                return None

            if self.sensor == "fuel":
                fuel_level = self.metrics.get("fuelLevel", None)

                if fuel_level is not None:
                    return round(fuel_level.get("value", 0))

                return None

            if self.sensor == "hvBattery":
                soc = self.metrics.get("batteryChargeLevel", None)

                if soc is not None:
                    return round(soc.get("value", 0))

                return None
            if self.sensor == "tirePressure":
                return self.metrics.get("tirePressureWarning", "Unsupported")

            if self.sensor == "gps":
                return self.metrics.get("vehicleLocation", {}).get("value", "Unsupported")

            if self.sensor == "alarm":
                return self.metrics.get("alarmStatus", {}).get("value", "Unsupported")

            if self.sensor == "ignitionStatus":
                return self.metrics.get("ignitionStatus", {}).get("value", "Unsupported")

            if self.sensor == "firmwareUpgInProgress":
                return self.metrics.get("firmwareUpgradeInProgress", "Unsupported")

            if self.sensor == "deepSleepInProgress":
                return self.metrics.get("deepSleepInProgress", "Unsupported")

            if self.sensor == "hvChargingStatus":
                return self.metrics.get("chargingStatus", {}).get("value", "Unsupported")

            if self.sensor == "hvPlugStatus":
                return self.metrics.get("plugStatus", {}).get("value", "Unsupported")

            if self.sensor == "doorStatus":
                for value in self.metrics.get("doorStatus", []):
                    if value["value"] in ["CLOSED", "Invalid", "UNKNOWN"]:
                        continue
                    return "Open"
                if  self.data.get("hoodStatus", {}).get("value") == "OPEN":
                    return "Open"
                return "Closed"

            if self.sensor == "windowPosition":
                for window in self.data.get("windowStatus", []):
                    windowrange = window.get("value", {}).get("doubleRange", {})
                    if windowrange.get("lowerBound", 0.0) != 0.0 or windowrange.get("upperBound", 0.0) != 0.0:
                        return "Open"
                return "Closed"

            if self.sensor == "lastRefresh":
                return self.parse_datestr(self.data.get("lastUpdated", ""))

            if self.sensor == "remoteStartStatus":
                countdown_timer = self.data.get("remoteStartCountdownTimer", {}).get("value", 0)
                return "Active" if countdown_timer > 0 else "Inactive"

            if self.sensor == "speed":
                return self.data.get("vehicleLocation", {}).get("speed", "Unsupported")

            if self.sensor == "deepSleep":
                return self.metrics.get("deepSleepStatus", "Unsupported")

            return None
        if ftype == "measurement":
            return SENSORS.get(self.sensor, {}).get("measurement", None)
        if ftype == "attribute":
            if self.sensor == "odometer":
                return {}
            if self.sensor == "alarm":
                return self.data.get("alarmStatus", {})
            if self.sensor == "ignitionStatus":
                return self.data.get("ignitionStatus", {})
            if self.sensor == "firmwareUpgradeInProgress":
                return self.data.get("firmwareUpgradeInProgress", {})
            if self.sensor == "deepSleep":
                return None
            if self.sensor == "doorStatus":
                doors = {}
                for value in self.data.get(self.sensor, []):
                    if "vehicleSide" in value:
                        if value['vehicleDoor'] == "UNSPECIFIED_FRONT":
                            doors[value['vehicleSide']] = value['value']
                        else:
                            doors[value['vehicleDoor']] = value['value']
                    else:
                        doors[value["vehicleDoor"]] = value['value']
                if "hoodStatus" in self.data:
                    doors["HOOD"] = self.data["hoodStatus"]["value"]
                return doors or None
            if self.sensor == "windowPosition":
                windows = {}
                for window in self.data.get("windowStatus", []):
                    if window["vehicleWindow"] == "UNSPECIFIED_FRONT":
                        windows[window["vehicleSide"]] = window
                    else:
                        windows[window["vehicleWindow"]] = window
                return windows
            if self.sensor == "lastRefresh":
                return None

            if self.sensor == "remoteStartStatus":
                return {"Countdown:": self.data.get("remoteStartCountdownTimer", {}).get("value", 0)}

        return None



    @property
    def name(self):
        """Return Sensor Name"""
        return "fordpass_" + self.sensor

    # @property
    # def state(self):
    #    """Return Sensor State"""
    #    return self.get_value("state")

    @property
    def device_id(self):
        """Return Sensor Device ID"""
        return self.device_id

    @property
    def extra_state_attributes(self):
        """Return sensor attributes"""
        return self.get_value("attribute")

    @property
    def native_unit_of_measurement(self):
        """Return sensor measurement"""
        return self.get_value("measurement")

    @property
    def native_value(self):
        """Return Native Value"""
        return self.get_value("state")

    @property
    def icon(self):
        """Return sensor icon"""
        return SENSORS[self.sensor]["icon"]

    @property
    def state_class(self):
        """Return sensor state_class for statistics"""
        if "state_class" in SENSORS[self.sensor]:
            if SENSORS[self.sensor]["state_class"] == "total":
                return SensorStateClass.TOTAL
            if SENSORS[self.sensor]["state_class"] == "measurement":
                return SensorStateClass.MEASUREMENT
            if SENSORS[self.sensor]["state_class"] == "total_increasing":
                return SensorStateClass.TOTAL_INCREASING
            return None
        return None

    @property
    def device_class(self):
        """Return sensor device class for statistics"""
        if "device_class" in SENSORS[self.sensor]:
            if SENSORS[self.sensor]["device_class"] == "distance":
                return SensorDeviceClass.DISTANCE
            if SENSORS[self.sensor]["device_class"] == "timestamp":
                return SensorDeviceClass.TIMESTAMP
            if SENSORS[self.sensor]["device_class"] == "temperature":
                return SensorDeviceClass.TEMPERATURE
            if SENSORS[self.sensor]["device_class"] == "battery":
                return SensorDeviceClass.BATTERY
            if SENSORS[self.sensor]["device_class"] == "speed":
                return SensorDeviceClass.SPEED
        return None
 
    @property
    def entity_registry_enabled_default(self):
        """Return if entity should be enabled when first added to the entity registry."""
        if "debug" in SENSORS[self.sensor]:
            return False
        return True

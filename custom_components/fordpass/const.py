"""Constants for the FordPass integration."""

DOMAIN = "fordpass"

VIN = "vin"

MANUFACTURER = "Ford Motor Company"

VEHICLE = "Ford Vehicle"

DEFAULT_PRESSURE_UNIT = "kPa"
DEFAULT_DISTANCE_UNIT = "km"

CONF_PRESSURE_UNIT = "pressure_unit"
CONF_DISTANCE_UNIT = "distance_unit"

PRESSURE_UNITS = ["PSI", "kPa", "BAR"]
DISTANCE_UNITS = ["mi", "km"]
DISTANCE_CONVERSION_DISABLED = "distance_conversion"
DISTANCE_CONVERSION_DISABLED_DEFAULT = False

UPDATE_INTERVAL = "update_interval"
UPDATE_INTERVAL_DEFAULT = 900

COORDINATOR = "coordinator"

SENSORS = {
    "odometer": {"icon": "mdi:counter", "state_class": "total", "device_class": "distance", "api_key": "odometer", "measurement": "km"},
    "fuel": {"icon": "mdi:gas-station", "api_key": ["fuelLevel"], "measurement": "%"},
    "hvBattery": {"icon": "mdi:battery", "api_key": ["batteryChargeLevel"], "measurement": "%"},
    "hvChargingStatus": {"icon": "mdi:power-plug-battery", "api_key": ["chargingStatus"]},
    "hvPlugStatus": {"icon": "mdi:power-plug-outline", "api_key": ["plugStatus"]},
    "tirePressure": {"icon": "mdi:car-tire-alert", "api_key": "tirePressureAlert"},
    "alarm": {"icon": "mdi:bell", "api_key": "alarmStatus"},
    "ignitionStatus": {"icon": "hass:power", "api_key": "ignitionStatus"},
    "doorStatus": {"icon": "mdi:car-door", "api_key": "doorStatus"},
    "windowPosition": {"icon": "mdi:car-door", "api_key": "windowStatus"},
    "lastRefresh": {"icon": "mdi:clock", "device_class": "timestamp", "api_key": "lastRefresh" , "sensor_type": "single"},
    "speed": {"icon": "mdi:speedometer", "device_class": "speed", "state_class": "measurement", "api_key": "vehicleLocation", "measurement": "km/h"},
    "deepSleep": {"icon": "mdi:power-sleep", "name": "Deep Sleep Mode Active", "api_key": "commandPreclusion", "api_class": "states"},
    "remoteStartStatus": {"icon": "mdi:remote", "api_key": "remoteStartCountdownTimer"},
}

SWITCHES = {
    "ignition": {"icon": "hass:power"},
}

WINDOW_POSITIONS = {
    "CLOSED": {
        "Fully_Closed": "Closed",
        "Fully_closed_position": "Closed",
        "Fully closed position": "Closed",
    },
    "OPEN": {
        "Fully open position": "Open",
        "Fully_Open": "Open",
        "Btwn 10% and 60% open": "Open-Partial",
    },
}
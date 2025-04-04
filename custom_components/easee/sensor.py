"""Easee charger sensor.

Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, MANUFACTURER, MODEL_EQUALIZER
from .entity import ChargerEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_sensor_entities()
    async_add_entities(entities)
    await controller.async_setup_done("sensor")


class ChargerSensor(ChargerEntity, SensorEntity):
    """Implementation of Easee charger sensor."""

    @property
    def native_value(self) -> StateType:
        """Return native value of sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return native unit of measurement for sensor."""
        if self._state_key == "site.costPerKWh":
            return self.data.site.get("currencyId", "")
        elif self._state_key == "cost_day.totalCost":
            if not (unit := self.data.cost_day.get("currencyId", "")):
                unit = self.data.site.get("currencyId", "")
            return unit
        elif self._state_key == "cost_month.totalCost":
            if not (unit := self.data.cost_month.get("currencyId", "")):
                unit = self.data.site.get("currencyId", "")
            return unit
        elif self._state_key == "cost_year.totalCost":
            if not (unit := self.data.cost_year.get("currencyId", "")):
                unit = self.data.site.get("currencyId", "")
            return unit

        return self._units


class EqualizerSensor(ChargerEntity, SensorEntity):
    """Implementation of Easee equalizer sensor."""

    @property
    def native_value(self) -> StateType:
        """Return native value of sensor."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.data.product.id)},
            serial_number=self.data.product.id,
            name=self.data.product.name,
            manufacturer=MANUFACTURER,
            model=MODEL_EQUALIZER,
            configuration_url=f"https://easee.cloud/mypage/products/{self.data.product.id}",
        )

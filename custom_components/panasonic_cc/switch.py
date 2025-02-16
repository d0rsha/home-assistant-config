"""Support for Panasonic Nanoe."""
import logging
from typing import Callable
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from aio_panasonic_comfort_cloud import constants, PanasonicDevice, PanasonicDeviceZone, ChangeRequestBuilder


from . import DOMAIN
from .const import DATA_COORDINATORS, CONF_FORCE_ENABLE_NANOE,DEFAULT_FORCE_ENABLE_NANOE
from .coordinator import PanasonicDeviceCoordinator
from .base import PanasonicDataEntity

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class PanasonicSwitchEntityDescription(SwitchEntityDescription):
    """Describes Panasonic Switch entity."""

    on_func: Callable[[ChangeRequestBuilder], ChangeRequestBuilder]
    off_func: Callable[[ChangeRequestBuilder], ChangeRequestBuilder]
    get_state: Callable[[PanasonicDevice], bool]
    is_available: Callable[[PanasonicDevice], bool]


NANOE_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="nanoe",
    translation_key="nanoe",
    name="Nanoe",
    icon="mdi:virus-off",
    on_func = lambda builder: builder.set_nanoe_mode(constants.NanoeMode.On),
    off_func= lambda builder: builder.set_nanoe_mode(constants.NanoeMode.Off),
    get_state = lambda device: device.parameters.nanoe_mode in [constants.NanoeMode.On, constants.NanoeMode.ModeG, constants.NanoeMode.All],
    is_available = lambda device: device.has_nanoe
)
ECONAVI_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="eco-navi",
    translation_key="eco-navi",
    name="ECONAVI",
    icon="mdi:leaf",
    on_func = lambda builder: builder.set_eco_navi_mode(constants.EcoNaviMode.On),
    off_func= lambda builder: builder.set_eco_navi_mode(constants.EcoNaviMode.Off),
    get_state = lambda device: device.parameters.eco_navi_mode == constants.EcoNaviMode.On,
    is_available = lambda device: device.has_eco_navi
)
ECO_FUNCTION_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="eco-function",
    translation_key="eco-function",
    name="AI ECO",
    icon="mdi:leaf",
    on_func = lambda builder: builder.set_eco_function_mode(constants.EcoFunctionMode.On),
    off_func= lambda builder: builder.set_eco_function_mode(constants.EcoFunctionMode.Off),
    get_state = lambda device: device.parameters.eco_function_mode == constants.EcoFunctionMode.On,
    is_available = lambda device: device.has_eco_function
)
IAUTOX_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="iauto-x",
    translation_key="iauto-x",
    name="iAUTO-X",
    icon="mdi:snowflake",
    on_func = lambda builder: builder.set_iautox_mode(constants.IAutoXMode.On),
    off_func= lambda builder: builder.set_iautox_mode(constants.IAutoXMode.Off),
    get_state = lambda device: device.parameters.iautox_mode == constants.IAutoXMode.On and device.parameters.mode == constants.OperationMode.Auto,
    is_available = lambda device: device.has_iauto_x
)

def create_zone_mode_description(zone: PanasonicDeviceZone):
    return PanasonicSwitchEntityDescription(
        key = f"zone-{zone.id}",
        translation_key=f"zone-{zone.id}",
        name = zone.name,
        icon="mdi:thermostat",
        off_func=lambda builder: builder.set_zone_mode(zone.id, constants.ZoneMode.Off),
        on_func=lambda builder: builder.set_zone_mode(zone.id, constants.ZoneMode.On),
        get_state=lambda device: device.parameters.get_zone(zone.id).mode == constants.ZoneMode.On,
        is_available=lambda device: True
    )

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    devices = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    force_enable_nanoe = entry.options.get(CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE)
    for data_coordinator in data_coordinators:
        devices.append(PanasonicSwitchEntity(data_coordinator, NANOE_DESCRIPTION, always_available=force_enable_nanoe))
        devices.append(PanasonicSwitchEntity(data_coordinator, ECONAVI_DESCRIPTION))
        devices.append(PanasonicSwitchEntity(data_coordinator, ECO_FUNCTION_DESCRIPTION))
        devices.append(PanasonicSwitchEntity(data_coordinator, IAUTOX_DESCRIPTION))
        if data_coordinator.device.has_zones:
            for zone in data_coordinator.device.parameters.zones:
                devices.append(PanasonicSwitchEntity(
                    data_coordinator,
                    create_zone_mode_description(zone)))

    async_add_entities(devices)

class PanasonicSwitchEntityBase(SwitchEntity):
    """Base class for all Panasonic switch entities."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: PanasonicSwitchEntityDescription

class PanasonicSwitchEntity(PanasonicDataEntity, PanasonicSwitchEntityBase):
    """Representation of a Panasonic switch."""

    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicSwitchEntityDescription, always_available: bool = False):
        """Initialize the Switch."""
        self.entity_description = description
        self._always_available = always_available
        super().__init__(coordinator, description.key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._always_available or self.entity_description.is_available(self.coordinator.device)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_available = self.entity_description.is_available(self.coordinator.device)
        self._attr_is_on = self.entity_description.get_state(self.coordinator.device)
        

    async def async_turn_on(self, **kwargs):
        """Turn on the Switch."""
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.on_func(builder)
        await self.coordinator.async_apply_changes(builder)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the Switch."""
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.off_func(builder)
        await self.coordinator.async_apply_changes(builder)
        self._attr_is_on = False
        self.async_write_ha_state()

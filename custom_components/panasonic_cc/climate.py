"""Support for the Panasonic HVAC."""
from typing import Callable, Any
from dataclasses import dataclass
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription, HVACAction, HVACMode, ATTR_HVAC_MODE
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.components.climate.const import ClimateEntityFeature


from .base import PanasonicDataEntity, AquareaDataEntity
from .coordinator import PanasonicDeviceCoordinator, AquareaDeviceCoordinator
from aio_panasonic_comfort_cloud import PanasonicDeviceParameters, ChangeRequestBuilder, constants
from aioaquarea import (
    ExtendedOperationMode as AquareaExtendedOperationMode,
    OperationStatus as AquareaZoneOperationStatus,
    DeviceAction as AquareaDeviceAction,
    UpdateOperationMode as AquareaUpdateOperationMode
    )

from .const import (
    SUPPORT_FLAGS,
    SERVICE_SET_SWING_LR_MODE,
    PRESET_8_15, 
    PRESET_NONE, 
    PRESET_ECO, 
    PRESET_BOOST, 
    PRESET_QUIET, 
    PRESET_POWERFUL,
    DOMAIN,
    DATA_COORDINATORS,
    AQUAREA_COORDINATORS,
    CONF_USE_PANASONIC_PRESET_NAMES)

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class PanasonicClimateEntityDescription(ClimateEntityDescription):
    """Describes a Panasonic climate entity."""

@dataclass(frozen=True, kw_only=True)
class AquareaClimateEntityDescription(ClimateEntityDescription):
    """Describes a Aquarea climate entity."""
    zone_id:int

PANASONIC_CLIMATE_DESCRIPTION = PanasonicClimateEntityDescription(
    key="climate",
    translation_key="climate",
)

def convert_operation_mode_to_hvac_mode(operation_mode: constants.OperationMode, iauto: bool) -> HVACMode | None:
    """Convert OperationMode to HVAC mode."""
    match operation_mode:
        case constants.OperationMode.Auto:
            return HVACMode.COOL if iauto else HVACMode.HEAT_COOL
        case constants.OperationMode.Cool:
            return HVACMode.COOL
        case constants.OperationMode.Dry:
            return HVACMode.DRY
        case constants.OperationMode.Fan:
            return HVACMode.FAN_ONLY
        case constants.OperationMode.Heat:
            return HVACMode.HEAT
        
def convert_hvac_mode_to_operation_mode(hvac_mode: HVACMode) -> constants.OperationMode | None:
    """Convert HVAC mode to OperationMode."""
    match hvac_mode:
        case HVACMode.HEAT_COOL:
            return constants.OperationMode.Auto
        case HVACMode.COOL:
            return constants.OperationMode.Cool
        case HVACMode.DRY:
            return constants.OperationMode.Dry
        case HVACMode.FAN_ONLY:
            return constants.OperationMode.Fan
        case HVACMode.HEAT:
            return constants.OperationMode.Heat
        
def convert_state_to_hvac_action(state: PanasonicDeviceParameters) -> HVACAction | None:
    """Convert state to HVAC action."""
    if state.power == constants.Power.Off:
        return HVACAction.OFF
    
    match state.mode:
        case constants.OperationMode.Auto:
            auto_diff = state.target_temperature - state.inside_temperature
            if auto_diff >= 1:
                return HVACAction.HEATING
            elif auto_diff <= -1:
                return HVACAction.COOLING
            return HVACAction.IDLE
        case constants.OperationMode.Cool:
            return HVACAction.COOLING if state.target_temperature < state.inside_temperature else HVACAction.IDLE
        case constants.OperationMode.Dry:
            return HVACAction.DRYING
        case constants.OperationMode.Fan:
            return HVACAction.FAN
        case constants.OperationMode.Heat:
            return HVACAction.HEATING if state.target_temperature > state.inside_temperature else HVACAction.IDLE
        
def convert_mode_and_status_to_hvac_mode(
    mode: AquareaExtendedOperationMode, zone_status: AquareaZoneOperationStatus
) -> HVACMode:
    if zone_status == AquareaZoneOperationStatus.OFF:
        return HVACMode.OFF
    match mode:
        case AquareaExtendedOperationMode.HEAT:
            return HVACMode.HEAT
        case AquareaExtendedOperationMode.COOL:
            return HVACMode.COOL
        case AquareaExtendedOperationMode.AUTO_COOL:
            return HVACMode.HEAT_COOL
        case AquareaExtendedOperationMode.AUTO_HEAT:
            return HVACMode.HEAT_COOL

    return HVACMode.OFF

def convert_aquarea_action_to_hvac_action(action: AquareaDeviceAction) -> HVACAction:
    """Convert device action to HVAC action."""
    match action:
        case AquareaDeviceAction.COOLING:
            return HVACAction.COOLING
        case AquareaDeviceAction.HEATING:
            return HVACAction.HEATING
    return HVACAction.IDLE

def convert_hvac_mode_to_aquarea_operation_mode(mode: HVACMode) -> AquareaUpdateOperationMode:
    """Convert HVAC mode to update operation mode."""
    match mode:
        case HVACMode.HEAT:
            return AquareaUpdateOperationMode.HEAT
        case HVACMode.COOL:
            return AquareaUpdateOperationMode.COOL
        case HVACMode.HEAT_COOL:
            return AquareaUpdateOperationMode.AUTO
    return AquareaUpdateOperationMode.OFF

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][AQUAREA_COORDINATORS]
    use_panasonic_preset_names = entry.options.get(CONF_USE_PANASONIC_PRESET_NAMES, False)
    for coordinator in data_coordinators:
        entities.append(PanasonicClimateEntity(coordinator, PANASONIC_CLIMATE_DESCRIPTION, use_panasonic_preset_names))
    for aquarea_coordinator in aquarea_coordinators:
        for zone_id in aquarea_coordinator.device.zones:            
            entities.append(AquareaClimateEntity(
                aquarea_coordinator,
                AquareaClimateEntityDescription(
                    zone_id=zone_id,
                    name=aquarea_coordinator.device.zones.get(zone_id).name,
                    key=f"zone-{zone_id}-climate",
                    translation_key=f"zone-{zone_id}-climate"
                )))
    async_add_entities(entities)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_SWING_LR_MODE,
        {
            vol.Required('swing_mode'): cv.string,
        },
        "async_set_horizontal_swing_mode",
    )


class PanasonicClimateEntity(PanasonicDataEntity, ClimateEntity):
    """Representation of a Panasonic Climate Device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_supported_features = SUPPORT_FLAGS
    _attr_fan_modes = [f.name for f in constants.FanSpeed]
    _attr_name = None

    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicClimateEntityDescription, use_panasonic_preset_names: bool):
        """Initialize the climate entity."""
        self.entity_description = description     
        device = coordinator.device
        hvac_modes = [HVACMode.OFF]
        if device.features.auto_mode:
            hvac_modes += [HVACMode.HEAT_COOL]
        if device.features.cool_mode:
            hvac_modes += [HVACMode.COOL]
        if device.features.dry_mode:
            hvac_modes += [HVACMode.DRY]
        hvac_modes += [HVACMode.FAN_ONLY]
        if device.features.heat_mode:
            hvac_modes += [HVACMode.HEAT]
        self._attr_hvac_modes = hvac_modes

        self._quiet_preset = PRESET_QUIET if use_panasonic_preset_names else PRESET_ECO
        self._powerful_preset = PRESET_POWERFUL if use_panasonic_preset_names else PRESET_BOOST

        preset_modes = [PRESET_NONE]
        if device.features.quiet_mode:
            preset_modes += [self._quiet_preset]
        if device.features.powerful_mode:
            preset_modes += [self._powerful_preset]
        if device.features.summer_house > 0:
            preset_modes += [PRESET_8_15]
        self._attr_preset_modes = preset_modes
        
        self._attr_swing_modes = [opt.name for opt in constants.AirSwingUD if opt != constants.AirSwingUD.Swing or device.features.auto_swing_ud]

        if device.has_horizontal_swing:
            self._attr_supported_features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
            self._attr_swing_horizontal_modes = [opt.name for opt in constants.AirSwingLR if opt != constants.AirSwingLR.Unavailable]

        super().__init__(coordinator, description.key)
        _LOGGER.info(f"Registing Climate entity: '{self._attr_unique_id}'")
        



    def _async_update_attrs(self) -> None:
        """Update attributes."""
        state = self.coordinator.device.parameters
        self._attr_hvac_mode = (HVACMode.OFF 
                                if state.power == constants.Power.Off 
                                else convert_operation_mode_to_hvac_mode(
                                    state.mode, 
                                    state.iautox_mode == constants.IAutoXMode.On))
        

        self._set_temp_range()
        self._attr_current_temperature = state.inside_temperature
        self._attr_target_temperature = state.target_temperature
        self._attr_fan_mode = state.fan_speed.name
        self._attr_swing_mode = state.vertical_swing_mode.name
        if self.coordinator.device.has_horizontal_swing:
            self._attr_swing_horizontal_mode = state.horizontal_swing_mode.name

        if self.coordinator.device.in_summer_house_mode:
            self._attr_preset_mode = PRESET_8_15
        elif state.eco_mode == constants.EcoMode.Quiet:
            self._attr_preset_mode = self._quiet_preset
        elif state.eco_mode == constants.EcoMode.Powerful:
            self._attr_preset_mode = self._powerful_preset
        else:
            self._attr_preset_mode = PRESET_NONE
        if self.coordinator.device.has_inside_temperature:
            self._attr_hvac_action = convert_state_to_hvac_action(state)
        

    def _set_temp_range(self) -> None:
        """Set new target temperature range."""
        device = self.coordinator.device
        self._attr_min_temp = 8 if device.in_summer_house_mode else 16
        if device.in_summer_house_mode:
            self._attr_max_temp = 15 if device.features.summer_house == 2 else 10
        else:
            self._attr_max_temp = 30

    def _update_attributes(self, builder: ChangeRequestBuilder) -> None:
        """Update attributes."""
        if builder.power_mode == constants.Power.Off:
            self._attr_hvac_mode = HVACMode.OFF
        default_preset = PRESET_NONE
        if builder.target_temperature:
            self._attr_target_temperature = builder.target_temperature
            if builder.target_temperature > 15 and self._attr_preset_mode == PRESET_8_15:
                self._attr_preset_mode = default_preset
            elif builder.target_temperature < 15 and self._attr_preset_mode != PRESET_8_15:
                self._attr_preset_mode = default_preset = PRESET_8_15
                
        if builder.eco_mode:
            if builder.eco_mode.name in (PRESET_QUIET, PRESET_ECO):
                self._attr_preset_mode = self._quiet_preset
            elif builder.eco_mode.name in (PRESET_POWERFUL, PRESET_BOOST):
                self._attr_preset_mode = self._powerful_preset
            else:
                self._attr_preset_mode = default_preset

        if builder.fan_speed:
            self._attr_fan_mode = builder.fan_speed.name
        if builder.vertical_swing:
            self._attr_swing_mode = builder.vertical_swing.name
        if builder.horizontal_swing:
            self._attr_swing_horizontal_mode = builder.horizontal_swing.name
        if builder.hvac_mode:
            self._attr_hvac_mode = convert_operation_mode_to_hvac_mode(builder.hvac_mode, False)
        self.async_write_ha_state()


    async def _async_enter_summer_house_mode(self, builder: ChangeRequestBuilder):
        """Enter summer house mode."""
        device = self.coordinator.device
        stored_data = await self.coordinator.async_get_stored_data()

        stored_data['mode'] = device.parameters.mode.value
        stored_data['ecoMode'] = device.parameters.eco_mode.value
        stored_data['targetTemperature'] = device.parameters.target_temperature
        stored_data['fanSpeed'] = device.parameters.fan_speed.value
        await self.coordinator.async_store_data(stored_data)

        builder.set_hvac_mode(constants.OperationMode.Heat)
        builder.set_eco_mode(constants.EcoMode.Powerful)
        builder.set_target_temperature(8)
        builder.set_fan_speed(constants.FanSpeed.High)

        self._attr_min_temp = 8
        self._attr_max_temp = 15 if device.features.summer_house == 2 else 10

    async def _async_exit_summer_house_mode(self, builder: ChangeRequestBuilder) -> Callable[[ClimateEntity], None]:
        """Exit summer house mode."""
        self._attr_min_temp = 16
        self._attr_max_temp = 30
        if not self.coordinator.device.in_summer_house_mode:
            return
        stored_data = await self.coordinator.async_get_stored_data()
        try:
            hvac_mode = constants.OperationMode(stored_data['mode']) if 'mode' in stored_data else constants.OperationMode.Heat
        except:
            hvac_mode = constants.OperationMode.Heat
        try:
            eco_mode = constants.EcoMode(stored_data['ecoMode']) if 'ecoMode' in stored_data else constants.EcoMode.Auto
        except:
            eco_mode = constants.EcoMode.Auto        
        target_temperature = stored_data['targetTemperature'] if 'targetTemperature' in stored_data else 20
        try:
            fan_speed = constants.FanSpeed(stored_data['fanSpeed']) if 'fanSpeed' in stored_data else constants.FanSpeed.Auto
        except:
            fan_speed = constants.FanSpeed.Auto

        builder.set_hvac_mode(hvac_mode)
        builder.set_eco_mode(eco_mode)
        builder.set_target_temperature(target_temperature)
        builder.set_fan_speed(fan_speed)

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""
        builder = self.coordinator.get_change_request_builder()
        builder.set_power_mode(constants.Power.On)
        await self.coordinator.async_apply_changes(builder)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""
        builder = self.coordinator.get_change_request_builder()
        builder.set_power_mode(constants.Power.Off)
        await self.coordinator.async_apply_changes(builder)
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""
        builder = self.coordinator.get_change_request_builder()
        if temp := kwargs.get(ATTR_TEMPERATURE):
            builder.set_target_temperature(temp)
        if mode := kwargs.get(ATTR_HVAC_MODE):
            if op_mode := convert_hvac_mode_to_operation_mode(mode):
                builder.set_hvac_mode(op_mode)
            else:
                mode = None
        await self.coordinator.async_apply_changes(builder)        
        self._update_attributes(builder)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        if not (op_mode := convert_hvac_mode_to_operation_mode(hvac_mode)):
            raise ValueError(f"Invalid hvac mode {hvac_mode}")
        
        builder = self.coordinator.get_change_request_builder()
        await self._async_exit_summer_house_mode(builder)
        builder.set_hvac_mode(op_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)
        
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode not in self.preset_modes:
            raise ValueError(f"Unsupported preset_mode '{preset_mode}'")
        
        builder = self.coordinator.get_change_request_builder()
        await self._async_exit_summer_house_mode(builder)
        builder.set_eco_mode(constants.EcoMode.Auto)
        if preset_mode in (PRESET_QUIET, PRESET_ECO):
            builder.set_eco_mode(constants.EcoMode.Quiet)
        elif preset_mode in (PRESET_POWERFUL, PRESET_BOOST):
            builder.set_eco_mode(constants.EcoMode.Powerful)
        elif preset_mode == PRESET_8_15:
            await self._async_enter_summer_house_mode(builder)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)
        await self.coordinator.async_request_refresh()
        
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode not in self.fan_modes:
            raise ValueError(f"Unsupported fan_mode '{fan_mode}'")
        
        builder = self.coordinator.get_change_request_builder()
        builder.set_fan_speed(fan_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)

    async def async_set_swing_mode(self, swing_mode: str):
        """Set new target swing mode."""
        if swing_mode not in self.swing_modes:
            raise ValueError(f"Unsupported swing mode '{swing_mode}'")
        
        builder = self.coordinator.get_change_request_builder()
        builder.set_vertical_swing(swing_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)

    async def async_set_swing_horizontal_mode(self, swing_mode: str):
        """Set new target swing mode."""
        if swing_mode not in self.swing_horizontal_modes:
            raise ValueError(f"Unsupported swing mode '{swing_mode}'")
        
        builder = self.coordinator.get_change_request_builder()
        builder.set_horizontal_swing(swing_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)

class AquareaClimateEntity(AquareaDataEntity, ClimateEntity):
    """Representation of a Aquarea Climate Device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    entity_description: AquareaClimateEntityDescription

    def __init__(self, coordinator: AquareaDeviceCoordinator, description: AquareaClimateEntityDescription):
        """Initialize the climate entity."""
        self.entity_description = description
        device = coordinator.device

        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        

        if device.support_cooling(description.zone_id):
            self._attr_hvac_modes.extend([HVACMode.COOL, HVACMode.HEAT_COOL])

        super().__init__(coordinator, description.key)
        _LOGGER.info(f"Registing Climate entity: '{self._attr_unique_id}'")

    def _async_update_attrs(self) -> None:
        """Update attributes."""
        device = self.coordinator.device
        zone = device.zones.get(self.entity_description.zone_id)
        self._attr_hvac_mode = convert_mode_and_status_to_hvac_mode(device.mode, zone.operation_status)
        self._attr_hvac_action = convert_aquarea_action_to_hvac_action(device.current_action)
        self._attr_current_temperature = zone.temperature

        self._attr_max_temp = zone.temperature
        self._attr_min_temp = zone.temperature

        if zone.supports_set_temperature and device.mode != AquareaExtendedOperationMode.OFF:
            self._attr_max_temp = (
                zone.cool_max
                if device.mode
                in (AquareaExtendedOperationMode.COOL, AquareaExtendedOperationMode.AUTO_COOL)
                else zone.heat_max
            )
            self._attr_min_temp = (
                zone.cool_min
                if device.mode
                in (AquareaExtendedOperationMode.COOL, AquareaExtendedOperationMode.AUTO_COOL)
                else zone.heat_min
            )
            self._attr_target_temperature = (
                zone.cool_target_temperature
                if device.mode
                in (
                    AquareaExtendedOperationMode.COOL,
                    AquareaExtendedOperationMode.AUTO_COOL,
                )
                else zone.heat_target_temperature
            )

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""
        await self.coordinator.device.turn_on()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""
        await self.coordinator.device.turn_off()
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""
        device = self.coordinator.device
        zone = device.zones.get(self.entity_description.zone_id)
        if mode := kwargs.get(ATTR_HVAC_MODE):
            await self.set_hvac_mode(mode)
        if temp := kwargs.get(ATTR_TEMPERATURE) and zone.supports_set_temperature:
            await self.coordinator.device.set_temperature(int(temp), zone.zone_id)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        if not (op_mode := convert_hvac_mode_to_aquarea_operation_mode(hvac_mode)):
            raise ValueError(f"Invalid hvac mode {hvac_mode}")
        await self.coordinator.device.set_mode(op_mode, self.entity_description.zone_id)

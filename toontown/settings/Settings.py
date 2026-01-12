from dataclasses import asdict, dataclass, field
import json
from typing import Union, Any, List
from pathlib import Path

from direct.showbase.MessengerGlobal import messenger
# Valid types for a setting.
# ControlSetting can be either dict[str, str] (old format) or dict[str, list[str]] (new format)
ControlSetting = dict[str, Union[str, list[str]]]
Setting = Union[str, int, bool, list, float, ControlSetting]


@dataclass
class ControlSettings:
    # Each control now stores a list of up to 2 keybinds
    # The first bind is the primary, second is optional (empty string if not set)
    MOVE_UP: List[str] = field(default_factory=lambda: ["arrow_up", ""])
    MOVE_DOWN: List[str] = field(default_factory=lambda: ["arrow_down", ""])
    MOVE_LEFT: List[str] = field(default_factory=lambda: ["arrow_left", ""])
    MOVE_RIGHT: List[str] = field(default_factory=lambda: ["arrow_right", ""])
    JUMP: List[str] = field(default_factory=lambda: ["control", ""])
    SPRINT: List[str] = field(default_factory=lambda: ["shift", ""])
    SCREENSHOT: List[str] = field(default_factory=lambda: ["f9", ""])
    MAP_PAGE_HOTKEY: List[str] = field(default_factory=lambda: ["escape", ""])
    FRIENDS_LIST_HOTKEY: List[str] = field(default_factory=lambda: ["f7", ""])
    STREET_MAP_HOTKEY: List[str] = field(default_factory=lambda: ["alt", ""])
    INVENTORY_HOTKEY: List[str] = field(default_factory=lambda: ["home", ""])
    QUEST_HOTKEY: List[str] = field(default_factory=lambda: ["end", ""])
    GALLERY_HOTKEY: List[str] = field(default_factory=lambda: ["g", ""])
    CRANE_GRAB_KEY: List[str] = field(default_factory=lambda: ["control", ""])
    CRANE_EXIT_KEY: List[str] = field(default_factory=lambda: ["escape", ""])
    CRANE_EXTEND_KEY: List[str] = field(default_factory=lambda: ["page_up", ""])
    CRANE_RETRACT_KEY: List[str] = field(default_factory=lambda: ["page_down", ""])
    CRANE_SPEED_INCREASE_KEY: List[str] = field(default_factory=lambda: ["bracketright", ""])
    CRANE_SPEED_DECREASE_KEY: List[str] = field(default_factory=lambda: ["bracketleft", ""])
    DRONE_SLOT_0_KEY: List[str] = field(default_factory=lambda: ["f", ""])
    DRONE_SLOT_1_KEY: List[str] = field(default_factory=lambda: ["g", ""])
    DRONE_SLOT_2_KEY: List[str] = field(default_factory=lambda: ["h", ""])
    ACTION_BUTTON: List[str] = field(default_factory=lambda: ["delete", ""])
    SECONDARY_ACTION: List[str] = field(default_factory=lambda: ["insert", ""])
    CHAT_HOTKEY: List[str] = field(default_factory=lambda: ["t", ""])
    
    def __getattribute__(self, name: str) -> Any:
        """Override to provide backward compatibility: return first bind as string when accessed as attribute"""
        value = super().__getattribute__(name)
        if isinstance(value, list) and len(value) > 0:
            # Return the first bind as a string for backward compatibility
            return value[0]
        return value


class Settings:
    # All controls with their respective default values.
    controls = ControlSettings()

    # All settings with their respective default values.
    defaultSettings = {
        "borderless": False,
        "music": True,
        "sfx": True,
        "toon-chat-sounds": True,
        "resolution": [1280, 720],
        "music-volume": 0.4,
        "sfx-volume": 0.4,
        "report-errors": True,
        "anti-aliasing": 0,
        "anisotropic-filter": 8,
        "frame-blending": True,
        "controls": asdict(controls),  # This will be a dict with list values
        "vertical-sync": True,
        "frame-rate-meter": False,
        "fovEffects": True,
        "cam-toggle-lock": False,
        "movement_mode": "TTCC",
        "sprint_mode": "Hold",
        "magic-word-activator": 0,
        "camSensitivityX": 0.25,
        "camSensitivityY": 0.1,
        "fps-limit": 0,
        # Options below this comment will not be exposed by OptionsPage
        # They can still be configurable by the end user
        "want-legacy-models": False,
        "experimental-multithreading": False,
        'discord-rich-presence': False,
        "archipelago-textsize": 0.5,
        "color-blind-mode": False,
        'laff-display': True
    }
    settingsFile = Path.home() / "Documents" / "Toontown-Ranked" / "settings.json"


    def __init__(self) -> None:
        try:
            with self.settingsFile.open(encoding='utf-8') as f:
                self._settings = json.load(f)
        except FileNotFoundError:
            self.settingsFile.parent.mkdir(parents=True, exist_ok=True)
            self._settings = self.defaultSettings.copy()
        except Exception as e:
            raise e

        # Check if controls need migration from old string format to new list format
        controls = self.get("controls")
        needs_migration = False
        if isinstance(controls, dict):
            # Check if any control is still in old string format
            for key, value in controls.items():
                if isinstance(value, str):
                    needs_migration = True
                    break
        
        # Only call updateControls if migration is needed, otherwise preserve existing list format
        if needs_migration:
            print(f"[DEBUG Settings] Migrating controls from old string format to new list format")
            # Re-instantiate the ControlSettings with our saved controls.
            # This will migrate old string format to new list format
            self.updateControls(controls)
            self.write()
            print(f"[DEBUG Settings] Migration complete - settings file updated")
        else:
            # No migration needed - just ensure the dataclass is in sync with _settings
            # This preserves secondary binds that were already set
            print(f"[DEBUG Settings] No migration needed - preserving existing control bindings")
            # Update dataclass from _settings without overwriting _settings
            if isinstance(controls, dict):
                # Convert any remaining strings to lists, but preserve existing lists
                converted_controls = {}
                valid_fields = {field.name for field in ControlSettings.__dataclass_fields__.values()}
                default_controls = asdict(ControlSettings())
                
                for key in valid_fields:
                    if key in controls:
                        value = controls[key]
                        if isinstance(value, str):
                            converted_controls[key] = [value, ""]
                        elif isinstance(value, list):
                            # Preserve the list as-is (including secondary binds)
                            converted_controls[key] = list(value[:2]) + [""] * (2 - len(value[:2]))
                        else:
                            # Fallback to default
                            converted_controls[key] = default_controls.get(key, ["", ""])
                    else:
                        # Use default if not present
                        converted_controls[key] = default_controls.get(key, ["", ""])
                
                # Update dataclass fields directly without calling updateControls
                # This preserves _settings["controls"] which has the secondary binds
                for key, value in converted_controls.items():
                    setattr(self.controls, key, value)
                
                print(f"[DEBUG Settings] Synced dataclass with _settings (preserving secondary binds)")

    def get(self, setting: str) -> Setting:
        return self._settings.get(setting, self.defaultSettings.get(setting))

    def set(self, setting: str, value: Setting) -> None:
        # Special handling for controls - allow dict with list values even if default is different
        if setting == "controls":
            # Controls can be dict with either string or list values (for migration)
            if isinstance(value, dict):
                self._settings[setting] = value
                return
        
        # For other settings, check type compatibility
        default_type = type(self.defaultSettings.get(setting))
        if default_type is not None and not isinstance(value, default_type):
            return
        self._settings[setting] = value

    def setControl(self, control: str, keybind: str, bind_index: int = 0) -> None:
        """
        Set a control keybind.
        Args:
            control: The control name (e.g., "MOVE_UP")
            keybind: The keybind string (e.g., "arrow_up")
            bind_index: Which bind to set (0 for primary, 1 for secondary). Defaults to 0 for backward compatibility.
        """
        print(f"[DEBUG Settings] setControl called: control={control}, keybind={keybind}, bind_index={bind_index}")
        
        # First, get the control setting.
        controls: ControlSetting = self.get("controls")
        print(f"[DEBUG Settings] Current controls dict type: {type(controls)}")
        print(f"[DEBUG Settings] Current value for {control}: {controls.get(control, 'NOT FOUND')} (type: {type(controls.get(control, []))})")
        
        # Get current binds for this control, handling both old (string) and new (list) formats
        current_value = controls.get(control, [])
        if isinstance(current_value, str):
            # Old format: convert to list
            current_binds = [current_value, ""]
            print(f"[DEBUG Settings] Converted old string format to list: {current_binds}")
        elif isinstance(current_value, list):
            # Ensure we have at least 2 elements
            current_binds = list(current_value) + [""] * (2 - len(current_value))
            current_binds = current_binds[:2]  # Ensure max 2 binds
            print(f"[DEBUG Settings] Using existing list format: {current_binds}")
        else:
            current_binds = ["", ""]
            print(f"[DEBUG Settings] Unknown format, using empty list: {current_binds}")
        
        # Update the specified bind
        if 0 <= bind_index < 2:
            print(f"[DEBUG Settings] Updating bind_index {bind_index} from '{current_binds[bind_index]}' to '{keybind}'")
            current_binds[bind_index] = keybind
            print(f"[DEBUG Settings] After update: {current_binds}")
        else:
            print(f"[DEBUG Settings] ERROR: bind_index {bind_index} is out of range!")
        
        controls[control] = current_binds
        print(f"[DEBUG Settings] Setting controls[{control}] = {current_binds}")
        
        # IMPORTANT: Save the modified controls dict back to _settings
        self._settings["controls"] = controls
        print(f"[DEBUG Settings] Saved to _settings['controls'][{control}] = {controls[control]}")
        
        # Update the control dataclass directly without calling updateControls
        # updateControls would read from _settings and might overwrite our changes
        # Instead, we'll update the dataclass field directly
        if hasattr(self.controls, control):
            # Convert the list to the dataclass format
            setattr(self.controls, control, current_binds)
            print(f"[DEBUG Settings] Updated dataclass field {control} = {current_binds}")
        else:
            print(f"[DEBUG Settings] WARNING: Control {control} not found in dataclass!")
        
        # Also update _settings["controls"] to ensure it's in list format for this control
        # This ensures consistency
        if control in self._settings.get("controls", {}):
            self._settings["controls"][control] = current_binds
            print(f"[DEBUG Settings] Ensured _settings['controls'][{control}] = {current_binds}")
        
        # Verify it was saved
        verify_binds = self.getControlBinds(control)
        print(f"[DEBUG Settings] Verification - getControlBinds({control}) = {verify_binds}")
        verify_settings = self._settings.get('controls', {}).get(control, 'NOT FOUND')
        print(f"[DEBUG Settings] Verification - _settings['controls'][{control}] = {verify_settings} (type: {type(verify_settings)})")

    def getControl(self, control: str) -> str:
        """Get the primary (first) bind for a control. Returns empty string if not found.
        This method maintains backward compatibility by returning a string."""
        binds = self.getControlBinds(control)
        return binds[0] if binds else ""

    def getControlBinds(self, control: str) -> List[str]:
        """Get both binds for a control. Returns a list with up to 2 elements."""
        # Read directly from _settings first to get the most up-to-date value
        # This ensures we get the value that was just set, not the dataclass which might be stale
        controls_dict = self._settings.get("controls", {})
        value = controls_dict.get(control, None)
        
        # If not in _settings, fall back to dataclass
        if value is None:
            controls_dict = self.getControls()
            value = controls_dict.get(control, ["", ""])
        
        # Handle backward compatibility: if it's a string, convert to list
        if isinstance(value, str):
            return [value, ""]
        elif isinstance(value, list):
            # Ensure we return exactly 2 elements
            return list(value[:2]) + [""] * (2 - len(value[:2]))
        else:
            return ["", ""]

    def getControls(self) -> dict[str, Any]:
        """Get all controls. Returns dict where values are lists of keybinds."""
        return asdict(self.controls)

    def updateControls(self, controls: dict[str, Union[str, list[str]]]) -> None:
        """
        Update controls, handling migration from old string format to new list format.
        This ensures backward compatibility with older settings files.
        """
        # Filter out any keys that aren't valid ControlSettings fields
        # This handles migration from old settings files (e.g., removing DRONE_DEPLOY_KEY)
        valid_fields = {field.name for field in ControlSettings.__dataclass_fields__.values()}
        filtered_controls = {k: v for k, v in controls.items() if k in valid_fields}
        
        # Convert old string format to new list format for backward compatibility
        converted_controls = {}
        default_controls = asdict(ControlSettings())
        
        for key in valid_fields:
            if key in filtered_controls:
                value = filtered_controls[key]
                # Convert old string format to list format
                if isinstance(value, str):
                    converted_controls[key] = [value, ""]
                elif isinstance(value, list):
                    # Ensure list has exactly 2 elements
                    converted_controls[key] = list(value[:2]) + [""] * (2 - len(value[:2]))
                else:
                    # Fallback to default
                    converted_controls[key] = default_controls[key]
            else:
                # Use default if not present
                converted_controls[key] = default_controls[key]
        
        self.controls = ControlSettings(**converted_controls)
        # Save the converted controls (now in list format) to _settings
        # IMPORTANT: Use converted_controls dict directly, not asdict(self.controls)
        # This preserves any secondary binds that were in the original controls dict
        print(f"[DEBUG Settings] updateControls - saving converted controls (list format) to _settings")
        # Merge converted_controls with any existing list values from the original controls
        # This ensures we don't lose secondary binds that were already set
        final_controls = {}
        for key in valid_fields:
            if key in filtered_controls:
                original_value = filtered_controls[key]
                # If original was already a list with 2 elements, preserve it
                if isinstance(original_value, list) and len(original_value) >= 2:
                    final_controls[key] = original_value[:2] + [""] * (2 - len(original_value[:2]))
                else:
                    # Otherwise use the converted value
                    final_controls[key] = converted_controls[key]
            else:
                final_controls[key] = converted_controls[key]
        
        self._settings["controls"] = final_controls
        # Also update the dataclass to match
        for key, value in final_controls.items():
            setattr(self.controls, key, value)
        # Also call set to ensure it's properly stored
        self.set("controls", final_controls)

    def write(self) -> None:
        with self.settingsFile.open("w", encoding='utf-8') as _settings:
            # Clean the settings dictionary before saving it to the file.
            self.clean()
            json.dump(self._settings, _settings, sort_keys=True, indent=4)

    def clean(self) -> None:
        """
        Removes all keys in settings which shouldn't exist.
        (they don't exist in defaultSettings)
        """
        for setting in list(self._settings):
            if setting not in self.defaultSettings:
                del self._settings[setting]

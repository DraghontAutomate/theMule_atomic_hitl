import json
import os
from typing import Dict, Any, Optional

DEFAULT_CONFIG_FILENAME = "default_config.json"

DEFAULT_CONFIG = {
    "fields": [
        {"name": "status", "label": "Status", "type": "label", "placement": "header"},
        {
            "name": "main_diff",
            "type": "diff-editor",
            "placement": "mainbody",
            "originalDataField": "originalText",
            "modifiedDataField": "editedText"
        }
    ],
    "actions": [
        {
            "name": "approve_main_content", # Changed from "approve" to be more specific
            "label": "Approve & End Session",
            "placement": "header",
            "isPrimary": True,
            # "editorName": "main_diff" # This might be implicitly handled or configured differently
        }
    ],
    "settings": {
        "defaultWindowTitle": "HITL Review Tool"
    }
}

class Config:
    """
    Manages the configuration for the HITL tool.
    It loads a default configuration and can override it with a user-provided JSON file or dictionary.
    """
    def __init__(self,
                 custom_config_path: Optional[str] = None,
                 custom_config_dict: Optional[Dict[str, Any]] = None):
        self._config = self._load_default_config()

        if custom_config_dict: # Prioritize dict if provided
            # Ensure deep copy of custom_config_dict before merging to avoid modifying original dict
            self._config = self._merge_configs(self._config, json.loads(json.dumps(custom_config_dict)))
        elif custom_config_path:
            custom_config = self._load_custom_config(custom_config_path)
            if custom_config:
                self._config = self._merge_configs(self._config, custom_config)

    def _load_default_config(self) -> Dict[str, Any]:
        """Loads the default configuration."""
        # In a real package, this might load from a file included with the package
        # For now, we'll use the hardcoded DEFAULT_CONFIG
        # Alternatively, could try to load DEFAULT_CONFIG_FILENAME from package data
        return json.loads(json.dumps(DEFAULT_CONFIG)) # Deep copy

    def _load_custom_config(self, path: str) -> Optional[Dict[str, Any]]:
        """Loads a custom configuration from a JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Custom config file not found at {path}. Using default.")
            return None
        except json.JSONDecodeError as e:
            print(f"Error: Could not decode JSON from {path}: {e}. Using default.")
            return None

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merges the override config into the base config.
        For lists like 'fields' and 'actions', the override completely replaces the base.
        For dictionaries like 'settings', it performs a deep merge.
        """
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            elif isinstance(value, list): # For lists like fields/actions, override replaces
                merged[key] = value
            else:
                merged[key] = value
        return merged

    def get_config(self) -> Dict[str, Any]:
        """Returns the fully resolved configuration dictionary."""
        return self._config

    def get_field_config(self, field_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves configuration for a specific field."""
        for field in self._config.get("fields", []):
            if field.get("name") == field_name:
                return field
        return None

    def get_action_config(self, action_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves configuration for a specific action."""
        for action in self._config.get("actions", []):
            if action.get("name") == action_name:
                return action
        return None

    @property
    def main_editor_original_field(self) -> str:
        """Gets the data field name for the original text in the main diff editor."""
        for field_config in self._config.get('fields', []):
            if field_config.get('type') == 'diff-editor':
                return field_config.get('originalDataField', 'originalText')
        return 'originalText' # Fallback

    @property
    def main_editor_modified_field(self) -> str:
        """Gets the data field name for the modified text in the main diff editor."""
        for field_config in self._config.get('fields', []):
            if field_config.get('type') == 'diff-editor':
                return field_config.get('modifiedDataField', 'editedText')
        return 'editedText' # Fallback

    @property
    def window_title(self) -> str:
        """Gets the window title from settings or a default."""
        return self._config.get("settings", {}).get("defaultWindowTitle", "HITL Review Tool")

# Example usage (for testing purposes, would be removed or in a test file)
if __name__ == '__main__':
    # Test with no custom config
    config_manager_default = Config()
    print("Default Config:")
    print(json.dumps(config_manager_default.get_config(), indent=2))
    print(f"Original field: {config_manager_default.main_editor_original_field}")
    print(f"Modified field: {config_manager_default.main_editor_modified_field}")

    # Test with a custom config (assuming examples/config.json exists relative to project root)
    # This path needs to be relative to where this script is run from, or absolute.
    # For testing, let's assume we are in the project root.
    custom_path = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "config.json")
    # Corrected path assuming this file is in src/themule_atomic_hitl/

    if os.path.exists(custom_path):
        print(f"\nLoading custom config from: {custom_path}")
        config_manager_custom = Config(custom_config_path=custom_path)
        print("\nCustom Config (merged):")
        print(json.dumps(config_manager_custom.get_config(), indent=2))
        print(f"Original field: {config_manager_custom.main_editor_original_field}")
        print(f"Modified field: {config_manager_custom.main_editor_modified_field}")

        # Test specific field retrieval
        author_field = config_manager_custom.get_field_config("author")
        if author_field:
            print(f"\nAuthor field config: {author_field}")
        else:
            print("\nAuthor field not found in custom config.")

        approve_action = config_manager_custom.get_action_config("approve")
        if approve_action:
            print(f"\nApprove action config: {approve_action}")
        else:
            print("\nApprove action not found in custom config.")

    else:
        print(f"\nCustom config file not found at {custom_path}, skipping custom config test.")

    # Test with a non-existent custom config
    print("\nTesting with non-existent custom config path:")
    config_manager_non_existent = Config(custom_config_path="non_existent_config.json")
    print(json.dumps(config_manager_non_existent.get_config(), indent=2))

    # Test the property for window title
    print(f"\nWindow Title (default): {config_manager_default.window_title}")
    if os.path.exists(custom_path):
         print(f"Window Title (custom): {config_manager_custom.window_title}") # Will be default if not in custom

    # Create a dummy custom config to test settings merge
    dummy_custom_settings_path = "dummy_custom_config.json"
    with open(dummy_custom_settings_path, "w") as f:
        json.dump({
            "settings": {
                "defaultWindowTitle": "My Custom HITL Tool",
                "customSetting": "TestValue"
            },
            "fields": [
                 {"name": "custom_field", "label": "My Custom Field", "type": "text-input", "placement": "sidebar" }
            ]
        }, f)

    config_manager_dummy = Config(custom_config_path=dummy_custom_settings_path)
    print("\nMerged with dummy_custom_config.json:")
    print(json.dumps(config_manager_dummy.get_config(), indent=2))
    print(f"Window Title (dummy): {config_manager_dummy.window_title}")
    os.remove(dummy_custom_settings_path)

    print("\nDefault config fields:")
    for field in config_manager_default.get_config().get('fields', []):
        print(field)

    print("\nDummy config fields (should replace default fields):")
    for field in config_manager_dummy.get_config().get('fields', []):
        print(field)


print("Config class created and basic tests run.")

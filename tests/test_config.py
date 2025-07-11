import unittest
import json
import os
import sys

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.themule_atomic_hitl.config import Config, DEFAULT_CONFIG

class TestConfig(unittest.TestCase):

    def setUp(self):
        # Create a dummy custom config file for testing
        self.custom_config_data = {
            "fields": [
                {"name": "custom_field", "label": "My Custom Field", "type": "text-input", "placement": "sidebar"},
                {
                    "name": "main_diff_custom",
                    "type": "diff-editor",
                    "placement": "mainbody",
                    "originalDataField": "customOriginal",
                    "modifiedDataField": "customModified"
                }
            ],
            "actions": [
                {"name": "custom_action", "label": "Do Custom Thing", "placement": "footer"}
            ],
            "settings": {
                "defaultWindowTitle": "My Custom Test Window",
                "anotherSetting": "customValue"
            }
        }
        self.custom_config_path = "test_custom_config.json"
        with open(self.custom_config_path, 'w') as f:
            json.dump(self.custom_config_data, f)

        # Create another dummy config for deep merge testing of settings
        self.partial_custom_config_data = {
            "settings": {
                "anotherSetting": "overriddenValue",
                "newSetting": "newValueFromPartial"
            }
        }
        self.partial_custom_config_path = "test_partial_custom_config.json"
        with open(self.partial_custom_config_path, 'w') as f:
            json.dump(self.partial_custom_config_data, f)


    def tearDown(self):
        # Remove the dummy custom config file
        if os.path.exists(self.custom_config_path):
            os.remove(self.custom_config_path)
        if os.path.exists(self.partial_custom_config_path):
            os.remove(self.partial_custom_config_path)

    def test_load_default_config(self):
        """
        Tests loading the default configuration.
        - What it tests: Verifies that when Config is instantiated without a custom path,
          it loads and provides access to the DEFAULT_CONFIG.
        - Expected outcome: The config manager's internal config matches DEFAULT_CONFIG,
          and properties derived from settings (like window_title) are correctly set.
        - Reason for failure: DEFAULT_CONFIG might be corrupted, the loading mechanism
          for defaults might be broken, or property accessors might be faulty.
        """
        config_manager = Config()
        self.assertEqual(config_manager.get_config(), DEFAULT_CONFIG)
        self.assertEqual(config_manager.window_title, DEFAULT_CONFIG["settings"]["defaultWindowTitle"])
        self.assertEqual(config_manager.main_editor_original_field, "originalText") # From DEFAULT_CONFIG
        self.assertEqual(config_manager.main_editor_modified_field, "editedText") # From DEFAULT_CONFIG

    def test_load_custom_config(self):
        """
        Tests loading a custom configuration file.
        - What it tests: Verifies that a provided custom config file correctly overrides
          default fields and actions, and merges settings.
        - Expected outcome: Loaded fields and actions should match the custom config.
          Settings should be a merge of custom and default, with custom taking precedence.
          Properties like window_title and editor fields should reflect the custom config.
        - Reason for failure: Issues with file reading, JSON parsing, the override logic for
          fields/actions, or the settings merge logic.
        """
        config_manager = Config(custom_config_path=self.custom_config_path)
        loaded_config = config_manager.get_config()

        # Fields and actions should be entirely replaced by custom_config_data
        self.assertEqual(loaded_config["fields"], self.custom_config_data["fields"])
        self.assertEqual(loaded_config["actions"], self.custom_config_data["actions"])

        # Settings should be merged: default ones persist if not overridden, new ones added/overridden
        self.assertEqual(loaded_config["settings"]["defaultWindowTitle"], self.custom_config_data["settings"]["defaultWindowTitle"])
        self.assertEqual(loaded_config["settings"]["anotherSetting"], self.custom_config_data["settings"]["anotherSetting"])

        # Check properties
        self.assertEqual(config_manager.window_title, self.custom_config_data["settings"]["defaultWindowTitle"])
        self.assertEqual(config_manager.main_editor_original_field, "customOriginal")
        self.assertEqual(config_manager.main_editor_modified_field, "customModified")


    def test_merge_settings_deeply(self):
        """
        Tests the deep merging capabilities for the 'settings' section of the config.
        - What it tests: Ensures that when a custom config provides only a subset of settings,
          those settings override or add to the defaults, while unspecified default
          settings are retained. Fields and actions should remain default if not in custom config.
        - Expected outcome: The 'settings' dictionary in the loaded config should be a
          combination of defaults and custom values, with custom values taking precedence
          for overlapping keys. Fields and actions should match DEFAULT_CONFIG.
        - Reason for failure: The merge logic for settings might be incorrect (e.g., shallow
          copy instead of deep, or incorrect precedence). Fallback for fields/actions
          might not be working when settings are custom.
        """
        # Default settings: {"defaultWindowTitle": "HITL Review Tool"}
        # Partial custom: {"anotherSetting": "overriddenValue", "newSetting": "newValueFromPartial"}
        config_manager = Config(custom_config_path=self.partial_custom_config_path)
        loaded_config = config_manager.get_config()

        # Check that default window title is still there
        self.assertEqual(loaded_config["settings"]["defaultWindowTitle"], DEFAULT_CONFIG["settings"]["defaultWindowTitle"])
        # Check that new settings from partial custom config are present
        self.assertEqual(loaded_config["settings"]["anotherSetting"], self.partial_custom_config_data["settings"]["anotherSetting"])
        self.assertEqual(loaded_config["settings"]["newSetting"], self.partial_custom_config_data["settings"]["newSetting"])

        # Fields and actions should be from DEFAULT_CONFIG as partial_custom_config_data doesn't define them
        self.assertEqual(loaded_config["fields"], DEFAULT_CONFIG["fields"])
        self.assertEqual(loaded_config["actions"], DEFAULT_CONFIG["actions"])


    def test_non_existent_custom_config(self):
        """
        Tests behavior when a specified custom config path does not exist.
        - What it tests: Ensures that if the custom_config_path points to a non-existent
          file, the Config class gracefully falls back to loading the DEFAULT_CONFIG.
        - Expected outcome: The config manager's internal config should be identical to
          DEFAULT_CONFIG. No error should be raised during instantiation.
        - Reason for failure: The file existence check or fallback mechanism might be broken,
          leading to an error or incorrect configuration being loaded.
        """
        config_manager = Config(custom_config_path="non_existent_file.json")
        # Should load default config without errors, possibly with a warning printed (not tested here)
        self.assertEqual(config_manager.get_config(), DEFAULT_CONFIG)

    def test_get_field_config(self):
        """
        Tests the retrieval of specific field configurations.
        - What it tests: Verifies that `get_field_config` correctly returns the
          configuration for a given field name from both custom and default configs.
          Also tests retrieval of a non-existent field.
        - Expected outcome: For existing field names, the corresponding field dictionary
          should be returned. For a non-existent field name, None should be returned.
        - Reason for failure: The lookup logic in `get_field_config` might be flawed,
          or the internal representation of fields might be incorrect.
        """
        config_manager = Config(custom_config_path=self.custom_config_path)
        field_conf = config_manager.get_field_config("custom_field")
        self.assertIsNotNone(field_conf)
        self.assertEqual(field_conf["label"], "My Custom Field")

        default_config_manager = Config()
        status_field_conf = default_config_manager.get_field_config("status")
        self.assertIsNotNone(status_field_conf)
        self.assertEqual(status_field_conf["type"], "label")

        self.assertIsNone(config_manager.get_field_config("non_existent_field"))

    def test_get_action_config(self):
        """
        Tests the retrieval of specific action configurations.
        - What it tests: Verifies that `get_action_config` correctly returns the
          configuration for a given action name from both custom and default configs.
          Also tests retrieval of a non-existent action.
        - Expected outcome: For existing action names, the corresponding action dictionary
          should be returned. For a non-existent action name, None should be returned.
        - Reason for failure: The lookup logic in `get_action_config` might be flawed,
          or the internal representation of actions might be incorrect.
        """
        config_manager = Config(custom_config_path=self.custom_config_path)
        action_conf = config_manager.get_action_config("custom_action")
        self.assertIsNotNone(action_conf)
        self.assertEqual(action_conf["label"], "Do Custom Thing")

        default_config_manager = Config()
        approve_action_conf = default_config_manager.get_action_config("approve_main_content")
        self.assertIsNotNone(approve_action_conf)
        self.assertTrue(approve_action_conf["isPrimary"])

        self.assertIsNone(config_manager.get_action_config("non_existent_action"))

    def test_main_editor_fields_fallback(self):
        """
        Tests the fallback mechanism for main editor field names.
        - What it tests: Ensures that if a configuration (custom or default) does not
          define a 'diff-editor' field, the `main_editor_original_field` and
          `main_editor_modified_field` properties default to "originalText" and
          "editedText" respectively.
        - Expected outcome: The properties should return the default fallback names when
          no 'diff-editor' is configured.
        - Reason for failure: The logic for identifying the 'diff-editor' or the
          fallback mechanism for these properties might be broken.
        """
        # Test fallback when no diff-editor is defined in config
        empty_config_data = {"fields": [{"name": "a", "type": "label"}], "actions": [], "settings": {}}
        empty_config_path = "empty_fields_config.json"
        with open(empty_config_path, 'w') as f:
            json.dump(empty_config_data, f)

        config_manager = Config(custom_config_path=empty_config_path)
        self.assertEqual(config_manager.main_editor_original_field, "originalText") # Default fallback
        self.assertEqual(config_manager.main_editor_modified_field, "editedText") # Default fallback

        os.remove(empty_config_path)

if __name__ == '__main__':
    unittest.main()

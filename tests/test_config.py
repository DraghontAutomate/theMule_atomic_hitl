import unittest
import json
import os
import sys
import tempfile
import shutil

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.themule_atomic_hitl.config import Config, DEFAULT_CONFIG

class TestConfig(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for config files
        self.test_dir = tempfile.mkdtemp()

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
        self.custom_config_path = os.path.join(self.test_dir, "test_custom_config.json")
        with open(self.custom_config_path, 'w') as f:
            json.dump(self.custom_config_data, f)

        # Create another dummy config for deep merge testing of settings
        self.partial_custom_config_data = {
            "settings": {
                "anotherSetting": "overriddenValue",
                "newSetting": "newValueFromPartial"
            }
        }
        self.partial_custom_config_path = os.path.join(self.test_dir, "test_partial_custom_config.json")
        with open(self.partial_custom_config_path, 'w') as f:
            json.dump(self.partial_custom_config_data, f)

    def tearDown(self):
        # Remove the temporary directory and its contents
        shutil.rmtree(self.test_dir)

    def test_load_default_config(self):
        """Verify that Config loads the DEFAULT_CONFIG correctly when no custom path is provided."""
        config_manager = Config()
        self.assertEqual(config_manager.get_config(), DEFAULT_CONFIG, "Default config content should match DEFAULT_CONFIG constant.")
        self.assertEqual(config_manager.window_title, DEFAULT_CONFIG["settings"]["defaultWindowTitle"], "Default window title should be loaded.")
        self.assertEqual(config_manager.main_editor_original_field, "originalText", "Default original text field name should be 'originalText'.")
        self.assertEqual(config_manager.main_editor_modified_field, "editedText", "Default modified text field name should be 'editedText'.")

    def test_load_custom_config(self):
        """Verify that Config correctly loads and merges a custom configuration file."""
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
        self.assertEqual(config_manager.main_editor_modified_field, "customModified", "Custom modified field name should be loaded.")


    def test_merge_settings_deeply(self):
        """Test that settings are deeply merged, not overwritten, when a partial custom config is used."""
        config_manager = Config(custom_config_path=self.partial_custom_config_path)
        loaded_config = config_manager.get_config()

        # Check that default window title is still there
        self.assertEqual(loaded_config["settings"]["defaultWindowTitle"], DEFAULT_CONFIG["settings"]["defaultWindowTitle"],
                         "Default settings should persist if not in partial custom config.")
        # Check that new settings from partial custom config are present
        self.assertEqual(loaded_config["settings"]["anotherSetting"], self.partial_custom_config_data["settings"]["anotherSetting"],
                         "Partially overridden settings should take new value.")
        self.assertEqual(loaded_config["settings"]["newSetting"], self.partial_custom_config_data["settings"]["newSetting"],
                         "New settings from partial config should be added.")

        # Fields and actions should be from DEFAULT_CONFIG as partial_custom_config_data doesn't define them
        self.assertEqual(loaded_config["fields"], DEFAULT_CONFIG["fields"],
                         "Fields should remain default if not specified in partial settings config.")
        self.assertEqual(loaded_config["actions"], DEFAULT_CONFIG["actions"],
                         "Actions should remain default if not specified in partial settings config.")


    def test_non_existent_custom_config(self):
        """Verify that Config loads default settings if a non-existent custom config path is given."""
        config_manager = Config(custom_config_path="non_existent_file.json")
        self.assertEqual(config_manager.get_config(), DEFAULT_CONFIG,
                         "Should load default config when custom config path is invalid.")

    def test_get_field_config(self):
        """Test retrieval of specific field configurations by name from both custom and default configs."""
        config_manager = Config(custom_config_path=self.custom_config_path)
        field_conf = config_manager.get_field_config("custom_field")
        self.assertIsNotNone(field_conf, "Custom field 'custom_field' should be found.")
        self.assertEqual(field_conf["label"], "My Custom Field", "Label for custom field is incorrect.")

        default_config_manager = Config()
        status_field_conf = default_config_manager.get_field_config("status")
        self.assertIsNotNone(status_field_conf, "Default field 'status' should be found.")
        self.assertEqual(status_field_conf["type"], "label", "Type for default field 'status' is incorrect.")

        self.assertIsNone(config_manager.get_field_config("non_existent_field"),
                          "Getting a non-existent field should return None.")

    def test_get_action_config(self):
        """Test retrieval of specific action configurations by name from both custom and default configs."""
        config_manager = Config(custom_config_path=self.custom_config_path)
        action_conf = config_manager.get_action_config("custom_action")
        self.assertIsNotNone(action_conf, "Custom action 'custom_action' should be found.")
        self.assertEqual(action_conf["label"], "Do Custom Thing", "Label for custom action is incorrect.")

        default_config_manager = Config()
        approve_action_conf = default_config_manager.get_action_config("approve_main_content")
        self.assertIsNotNone(approve_action_conf, "Default action 'approve_main_content' should be found.")
        self.assertTrue(approve_action_conf["isPrimary"], "Default action 'approve_main_content' should be primary.")

        self.assertIsNone(config_manager.get_action_config("non_existent_action"),
                          "Getting a non-existent action should return None.")

    def test_main_editor_fields_fallback(self):
        """Test that main editor field names fallback to defaults if no diff-editor is configured."""
        empty_config_data = {"fields": [{"name": "a", "type": "label"}], "actions": [], "settings": {}}
        empty_config_path = os.path.join(self.test_dir, "empty_fields_config.json")
        with open(empty_config_path, 'w') as f:
            json.dump(empty_config_data, f)

        config_manager = Config(custom_config_path=empty_config_path)
        self.assertEqual(config_manager.main_editor_original_field, "originalText", "Fallback original field name is incorrect.")
        self.assertEqual(config_manager.main_editor_modified_field, "editedText", "Fallback modified field name is incorrect.")

     


if __name__ == '__main__':
    unittest.main()

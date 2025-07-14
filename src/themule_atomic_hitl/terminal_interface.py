# src/themule_atomic_hitl/terminal_interface.py
import json
from typing import Dict, Any, Optional

from .core import SurgicalEditorLogic
from .config import Config

class TerminalInterface:
    """
    A terminal-based interface for the Surgical Editor.
    This class orchestrates the user interaction in the terminal,
    receiving input and displaying information from the core logic.
    """

    def __init__(self, initial_data: Dict[str, Any], config: Config):
        """
        Initializes the TerminalInterface.

        Args:
            initial_data (Dict[str, Any]): The initial data for the editor.
            config (Config): The configuration object.
        """
        self.config = config
        self.is_session_active = True

        # Define callbacks that SurgicalEditorLogic will use to communicate back
        logic_callbacks = {
            'update_view': self.on_update_view,
            'show_diff_preview': self.on_show_diff_preview,
            'request_clarification': self.on_request_clarification,
            'show_error': self.on_show_error,
            'confirm_location_details': self.on_confirm_location_details,
        }

        # Instantiate the core logic engine
        self.logic = SurgicalEditorLogic(initial_data, self.config, logic_callbacks)

    def run(self) -> Dict[str, Any]:
        """
        Starts the main loop for the terminal interface.

        Returns:
            Dict[str, Any]: The final data after the session is terminated.
        """
        print("--- Terminal Surgical Editor ---")
        self.logic.start_session() # Start the logic processing loop

        while self.is_session_active:
            # The core logic runs in a separate thread, so the main loop here
            # is for handling user input when the logic is idle.
            self.display_main_menu()

        print("\n--- Session Terminated ---")
        return self.logic.get_final_data()

    def display_main_menu(self):
        """
        Displays the main menu of options to the user.
        """
        print("\n--- Main Menu ---")
        print("1. Request New Edit")
        print("2. View Current Data")
        print("3. View Edit Queue")
        print("4. Terminate Session")

        choice = input("Enter your choice: ")
        if choice == '1':
            self.handle_new_edit_request()
        elif choice == '2':
            self.display_current_data()
        elif choice == '3':
            self.display_queue_status()
        elif choice == '4':
            self.logic.perform_action("terminate", {})
            self.is_session_active = False
        else:
            print("Invalid choice. Please try again.")

    def handle_new_edit_request(self):
        """
        Handles the process of creating a new edit request from the user.
        """
        print("\n--- New Edit Request ---")
        hint = input("Enter hint (where to edit): ")
        instruction = input("Enter instruction (what to apply): ")

        self.logic.add_edit_request(
            instruction=instruction,
            request_type="hint_based",
            hint=hint,
            selection_details=None
        )

    def display_current_data(self):
        """
        Displays the current state of the data.
        """
        print("\n--- Current Data ---")
        print(json.dumps(self.logic.data, indent=2))

    def display_queue_status(self):
        """
        Displays the current status of the edit queue.
        """
        queue_info = self.logic.get_queue_info()
        print("\n--- Queue Status ---")
        print(f"Queue size: {queue_info['size']}")
        print(f"Is processing: {queue_info['is_processing']}")
        if queue_info['is_processing']:
            print(f"Active task hint: {queue_info['active_task_hint']}")
            print(f"Active task status: {queue_info['active_task_status']}")

    # --- Callbacks from SurgicalEditorLogic ---

    def on_update_view(self, data: Dict[str, Any], config_dict: Dict[str, Any], queue_info: Dict[str, Any]):
        """
        Callback executed by SurgicalEditorLogic to update the view.
        In the terminal, this might just be a notification.
        """
        print("\n[SYSTEM] View updated.")
        self.display_queue_status()

    def on_show_diff_preview(self, original_snippet: str, edited_snippet: str, before_context: str, after_context: str):
        """
        Callback to show a diff preview to the user in the terminal.
        """
        print("\n--- Review Proposed Edit ---")
        print("Original Snippet:")
        print(original_snippet)
        print("\nEdited Snippet:")
        print(edited_snippet)

        decision = input("Approve (a), Reject (r), or Cancel (c)? ").lower()
        if decision == 'a':
            self.logic.process_llm_task_decision('approve', edited_snippet)
        elif decision == 'r':
            self.logic.process_llm_task_decision('reject', None)
        else:
            self.logic.process_llm_task_decision('cancel', None)

    def on_request_clarification(self):
        """
        Callback to request clarification from the user.
        """
        print("\n--- Clarification Needed ---")
        new_hint = input("Enter a new or revised hint: ")
        new_instruction = input("Enter a new or revised instruction: ")
        self.logic.update_active_task_and_retry(new_hint, new_instruction)

    def on_show_error(self, msg: str):
        """
        Callback to display an error message.
        """
        print(f"\n[ERROR] {msg}")

    def on_confirm_location_details(self, location_info: dict, original_hint: str, original_instruction: str):
        """
        Callback to ask the user to confirm a located text snippet.
        """
        print("\n--- Confirm Location ---")
        print(f"Original Hint: {original_hint}")
        print("Located Snippet:")
        print(location_info['snippet'])

        confirmed = input("Is this the correct location? (y/n): ").lower()
        if confirmed == 'y':
            self.logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)
        else:
            # If the user rejects, we can treat it as a cancellation of this task
            print("Location rejected. Cancelling this edit task.")
            self.logic.process_llm_task_decision('cancel', None)


def run_terminal_interface(initial_data: Dict[str, Any], config: Config) -> Dict[str, Any]:
    """
    Sets up and runs the terminal-based interface.

    Args:
        initial_data (Dict[str, Any]): The initial data for the editor.
        config (Config): The configuration object.

    Returns:
        Dict[str, Any]: The final data after the session.
    """
    terminal_app = TerminalInterface(initial_data, config)
    return terminal_app.run()

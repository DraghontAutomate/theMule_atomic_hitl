# theMule_atomic_hitl
Human-in-the-Loop for Close Guidance

## General Overview

`theMule_atomic_hitl` (Human-in-the-Loop) is a desktop application designed to facilitate precise, reviewed modifications to text-based data. It provides a controlled environment where a user can guide an automated editing process, review proposed changes in a diff view, and then approve, reject, or refine them.

The tool is highly configurable, allowing users to define the data fields to be displayed (including labels, text inputs, and a central diff editor) and the actions that can be performed. This makes it adaptable for various scenarios where careful, step-by-step oversight of textual changes is critical, such as data curation, content moderation, or guided document editing. Edit requests are managed in a queue, ensuring that each proposed change is handled atomically and with user validation at key stages.

## Workflow

The typical workflow when using `theMule_atomic_hitl` involves the following steps:

1.  **Initialization:**
    *   The application loads with initial data (e.g., from `examples/data.json`) and a UI configuration (e.g., from `examples/config.json`).
    *   The main interface displays the data according to the configured fields, often featuring a central diff editor for viewing and managing changes to a primary text field.

2.  **Requesting an Edit:**
    *   The user initiates an edit by clicking "Request New Edit".
    *   They provide a "Hint" (a piece of text or description to help the system locate the section to be edited within the current content) and an "Instruction" (a description of the change to be made).
    *   This request is added to an internal processing queue.

3.  **Location Confirmation (Gatekeeper Loop):**
    *   The system takes the first request from the queue.
    *   It attempts to locate the text snippet identified by the "Hint" in a snapshot of the content taken when the request was made. (Currently, this uses a mock LLM locator).
    *   The located snippet is presented to the user.
    *   The user must confirm if this is the correct snippet to edit. They can also provide a revised hint if the initial location was inaccurate.
    *   If the user cancels at this stage, the edit task is discarded.

4.  **Edit Proposal & Review (Worker Loop):**
    *   Once the location is confirmed, the system generates a proposed modification to the snippet based on the user's "Instruction". (Currently, this uses a mock LLM editor).
    *   The UI displays a diff view comparing the original snippet with the LLM's proposed change.

5.  **Decision & Iteration:**
    *   The user reviews the diff and chooses an action:
        *   **Approve This Edit:** The proposed change is applied to the main content. The task is complete.
        *   **Refine This Edit:** The user is prompted to provide a new hint and/or instruction for the current task. The task then re-enters the "Location Confirmation" or "Edit Proposal" phase with the new information.
        *   **Discard This Edit Task:** The proposed change is rejected, and the current edit task is abandoned.
    *   If there are more requests in the queue, the system proceeds to the next one.

6.  **General Actions & Session Management:**
    *   Throughout the session, the user can perform other general actions defined in the configuration (e.g., "Increment Version," "Revert All Changes").
    *   A primary "Approve & End Session" action allows the user to finalize all accepted changes and terminate the application. The final state of the data and an audit trail of edits are then typically available (currently printed to the console on termination).

This iterative process of request, location, proposal, and review allows for fine-grained control over modifications to the data.

## Running Locally

This application is built using Python and PyQt5 for the graphical interface.

### Dependencies

**1. Python:**
   - Ensure you have Python 3.6+ installed.

**2. System Dependencies (for Linux):**
   - If you are running on a Linux system (especially headless or in some containerized environments), you will need to install X11 client libraries and Xvfb (X Virtual FrameBuffer) for the application to run. The specific packages can vary by distribution, but for Debian/Ubuntu-based systems, you can install them with:
     ```bash
     sudo apt-get update
     sudo apt-get install -y xvfb libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xfixes0 libxcb-xinerama0 libx11-xcb1 \
     libxcb-randr0-dev libxcb-xtest0-dev libxcb-xinerama0-dev libxcb-shape0-dev libxcb-xkb-dev libxkbcommon-x11-dev libx11-xcb-dev libxcb-cursor-dev libxcb-util0-dev libxcb-keysyms1-dev libxcb-icccm4-dev libxcb-image0-dev libxcb-render-util0-dev libxcb-xfixes0-dev libxcb1-dev
     ```
   - For other operating systems (Windows, macOS), these are typically handled by the Qt installation itself, but ensure your X11 environment (like XQuartz on macOS) is set up if needed.

**3. Python Packages:**
   - Install the required Python packages using the provided `requirements.txt` file:
     ```bash
     pip install -r requirements.txt
     ```
     This will install `PyQt5` and `PyQtWebEngine`.

### Launching the Example

Once dependencies are installed:

- **On a desktop environment (Windows, macOS, Linux with a display server):**
  Navigate to the repository root and run:
  ```bash
  python examples/run_tool.py
  ```

- **On a headless Linux environment (or if you encounter Qt platform errors):**
  You can use `xvfb-run` to provide a virtual display:
  ```bash
  xvfb-run -a python examples/run_tool.py
  ```

This will launch the example application using the configuration and data found in the `examples/` directory. The application window should appear.
The Monaco editor component used in the frontend is loaded from a CDN, so an active internet connection is required when running the application.

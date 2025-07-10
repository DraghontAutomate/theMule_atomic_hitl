// Configure the AMD loader for Monaco editor.
// This tells the loader where to find the editor's source files.
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs' } });

/**
 * Main application state object.
 * @property {object} config - Loaded from config.json via Python backend. Defines UI structure (fields, actions, placements).
 * @property {object} data - Loaded from data.json via Python backend. Contains the actual data being edited.
 * @property {object} widgets - Stores references to dynamically created UI elements (Monaco editors, input fields, labels) based on config.
 * @property {object|null} api - Reference to the Python backend object exposed via QWebChannel. Used to call Python methods.
 * @property {object} ui - Stores references to static HITL (Human-in-the-Loop) UI elements defined in index.html.
 * @property {object} activeTaskDetails - Stores details of the current HITL task being processed (e.g., original hint, instruction, located snippet info).
 */
let app = {
  config: {},
  data: {},
  widgets: {},
  api: null,
  ui: {},
  activeTaskDetails: {}
};

/**
 * Manages the visibility of different UI sections by adding or removing the 'hidden' class.
 * @param {string} sectionId - The ID of the HTML element (section) to show or hide.
 * @param {boolean} makeVisible - True to show the section, false to hide it.
 */
function showSection(sectionId, makeVisible) {
    const section = document.getElementById(sectionId);
    if (section) {
        if (makeVisible) {
            section.classList.remove('hidden');
        } else {
            section.classList.add('hidden');
        }
    }
}

/**
 * Renders the configurable parts of the UI based on `app.config`.
 * This includes creating input fields, labels, buttons, and the Monaco diff editor
 * as defined in the `fields` and `actions` arrays in `config.json`.
 * It attempts to preserve the main Monaco diff editor instance if it already exists
 * to avoid re-initialization costs and losing its state unnecessarily.
 */
function renderConfigurableUI() {
  // IDs of containers that can be populated by config.json
  const configurableContainers = ['header-container', 'sidebar-container', 'mainbody-container', 'footer-container'];
  let mainDiffEditorElement = null; // To store the DOM element of the main diff editor if it exists

  // Check if the main diff editor (assumed to be named 'main_diff' in app.widgets) exists and is part of the DOM.
  // This is to preserve it across re-renders if possible.
  const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
  const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff'; // Default name or from config

  if (app.widgets[mainDiffWidgetName] && app.widgets[mainDiffWidgetName].instance) {
      const mainBody = document.getElementById('mainbody-container');
      const editorDomNode = app.widgets[mainDiffWidgetName].instance.getDomNode();
      if (mainBody && editorDomNode && mainBody.contains(editorDomNode)) {
          mainDiffEditorElement = editorDomNode.parentElement; // The div wrapping the editor
      }
  }

  // Clear existing content from configurable containers, except for preserved elements.
  configurableContainers.forEach(id => {
    const container = document.getElementById(id);
    if (container) {
        // If this is the main body and we have a preserved diff editor,
        // only remove children that are NOT the editor or the HITL-specific areas.
        if (id === 'mainbody-container' && mainDiffEditorElement) {
            Array.from(container.childNodes).forEach(child => {
                if (child !== mainDiffEditorElement && !mainDiffEditorElement.contains(child) &&
                    child.id !== 'location-confirmation-area' && child.id !== 'inner-loop-decision-area') {
                    container.removeChild(child);
                }
            });
        } else if (id !== 'mainbody-container') {
            // For other containers, or if mainbody has no preserved editor, clear them.
            container.innerHTML = '';
        }
    }
  });

  app.widgets = {}; // Reset config-driven widgets (new ones will be created or existing ones re-linked)

  // Create UI elements for fields defined in config.json
  if (app.config.fields) {
    app.config.fields.forEach(field => {
        const container = document.getElementById(`${field.placement}-container`);
        if (!container && field.placement !== 'none') { // 'none' placement means it's data-only
            console.warn(`Container for placement '${field.placement}-container' not found for field '${field.name}'.`);
            return;
        }

        if (field.type === 'diff-editor') {
            // If this is the main diff editor and it was preserved, re-link it.
            if (field.name === mainDiffWidgetName && mainDiffEditorElement) {
                app.widgets[field.name] = { type: 'diff-editor', instance: app.widgets[mainDiffWidgetName].instance, config: field };
            } else { // Otherwise, create a new editor instance
                const editorDiv = document.createElement('div');
                if (field.placement === 'mainbody') { // Main editor needs explicit sizing
                    editorDiv.style.height = "calc(100% - 120px)"; // Adjust based on surrounding elements
                    editorDiv.style.width = "100%";
                    editorDiv.style.border = "1px solid #ccc"; // Visual cue for editor area
                } else { // Other diff editors might need different styling/sizing
                    editorDiv.style.height = "200px"; // Default for non-mainbody diff editors
                    editorDiv.style.minWidth = "100px";
                }
                if (container) container.appendChild(editorDiv); // Append if container exists

                const editor = monaco.editor.createDiffEditor(editorDiv, {
                    automaticLayout: true,       // Adjusts layout on container resize
                    originalEditable: field.originalEditable === true, // Whether original pane is editable
                    readOnly: field.readOnly === true // Whether modified pane is initially read-only
                });
                editor.setModel({
                    original: monaco.editor.createModel('', field.language || 'text/plain'),
                    modified: monaco.editor.createModel('', field.language || 'text/plain')
                });
                app.widgets[field.name] = { type: 'diff-editor', instance: editor, config: field };
            }
        } else if (field.placement !== 'none') { // Handle non-editor fields that have a placement
          const group = document.createElement('div'); group.className = 'field-group';
          const label = document.createElement('label'); label.htmlFor = `field-${field.name}`; label.textContent = field.label; group.appendChild(label);
          let element;
          if (field.type === 'text-input') {
            element = document.createElement('input');
            element.type = 'text';
            element.readOnly = field.readOnly === true;
          } else if (field.type === 'textarea') {
            element = document.createElement('textarea');
            element.readOnly = field.readOnly === true;
          } else { // Default to a span for 'label', 'label-bold', etc.
            element = document.createElement('span');
            if (field.type === 'label-bold') element.classList.add('label-bold');
          }
          element.id = `field-${field.name}`;
          group.appendChild(element);
          app.widgets[field.name] = { type: 'field', element: element, config: field };
          if (container) container.appendChild(group);
        }
    });
  }

  // Create UI elements for actions (buttons) defined in config.json
  if (app.config.actions) {
    app.config.actions.forEach(action => {
        const container = document.getElementById(`${action.placement}-container`);
        if (!container) {
            console.warn(`Container for placement '${action.placement}-container' not found for action '${action.name}'.`);
            return;
        }
        const button = document.createElement('button');
        button.textContent = action.label;
        button.className = 'action-button';
        if (action.isPrimary) button.classList.add('primary');
        button.onclick = () => {
          const payload = getPayloadFromUI(action); // Get data from UI fields relevant to this action
          if (app.api) app.api.performAction(action.name, payload);
        };
        container.appendChild(button);
    });
  }
}

/**
 * Populates the UI elements (widgets) with data from `app.data`.
 * Handles different widget types (diff-editor, input fields, labels).
 * For the main diff editor, its content update is often handled by specific
 * HITL signal handlers to reflect the current task state (e.g., showing a diff).
 */
function renderData() {
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    const fieldConfig = widget.config; // The config for this specific widget

    if (widget.type === 'diff-editor') {
      // The main diff editor's content is highly contextual to the HITL state.
      // It's usually updated by `showDiffPreviewSignal` or reset by `updateGlobalUIState`.
      // This part handles other diff editors or ensures the main one is initialized if data exists.
      const originalValue = app.data[fieldConfig.originalDataField] || '';
      const modifiedValue = app.data[fieldConfig.modifiedDataField] || '';

      if (widget.instance.getModel()) {
          widget.instance.getModel().original.setValue(originalValue);
          widget.instance.getModel().modified.setValue(modifiedValue);
      } else {
          console.warn(`Diff editor '${name}' has no model to set value.`);
      }

    } else if (widget.type === 'field') {
      const value = app.data[fieldConfig.name] || ''; // Get data using the field's name
      if (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA') {
        widget.element.value = value;
      } else { // For spans, labels
        widget.element.textContent = value;
      }
    }
  }

  // Special handling for the main diff editor when the application is idle (no active HITL task).
  // It should display the current main content in both panes.
  const mainDiffConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
  if (mainDiffConfig && app.widgets[mainDiffConfig.name] && app.widgets[mainDiffConfig.name].instance) {
      const editor = app.widgets[mainDiffConfig.name].instance;
      const currentContent = app.data[mainDiffConfig.modifiedDataField] || '';
      // If no active task or task is not in a state that uses the diff editor for preview
      if (!app.activeTaskDetails || !app.activeTaskDetails.status ||
          (app.activeTaskDetails.status !== 'awaiting_diff_approval' &&
           app.activeTaskDetails.status !== 'awaiting_location_confirmation' && // During location confirm, editor might be blank or show full doc
           app.activeTaskDetails.status !== 'locating_snippet')) { // Also when locating, keep editor content stable
          if (editor.getModel()) {
              editor.getModel().original.setValue(currentContent);
              editor.getModel().modified.setValue(currentContent);
          }
      }
  }
}

/**
 * Collects data from UI input fields to be sent as a payload with an action.
 * If the action is associated with an editor (via `action.editorName`),
 * it includes the modified content of that editor.
 * @param {object} action - The action object from `app.config.actions`.
 * @returns {object} payload - An object containing data from relevant UI fields.
 */
function getPayloadFromUI(action) {
  const payload = {};
  // Collect data from all standard input/textarea widgets
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    if (widget.type === 'field' && (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA')) {
      payload[widget.config.name] = widget.element.value;
    }
  }
  // If the action specifies an editor, get its modified content
  if (action.editorName && app.widgets[action.editorName] && app.widgets[action.editorName].type === 'diff-editor') {
    const editorWidget = app.widgets[action.editorName];
    payload[editorWidget.config.modifiedDataField] = editorWidget.instance.getModifiedEditor().getValue();
  }
  return payload;
}

/**
 * Initializes references to static HITL UI elements and sets up their event listeners.
 * This function is called once the QWebChannel is established.
 */
function initializeHitlUIElements() {
    // Store references to HTML elements for easy access
    app.ui.btnApproveEndSession = document.getElementById('btn-approve-end-session');
    app.ui.btnRequestNewEdit = document.getElementById('btn-request-new-edit');
    app.ui.queueStatusDisplay = document.getElementById('queue-status-display');
    app.ui.editRequestInputArea = document.getElementById('edit-request-input-area');
    app.ui.inputHint = document.getElementById('input-hint');
    app.ui.inputInstruction = document.getElementById('input-instruction');
    app.ui.btnAddtoQueue = document.getElementById('btn-add-to-queue');
    app.ui.locationConfirmationArea = document.getElementById('location-confirmation-area');
    app.ui.originalHintDisplay = document.getElementById('original-hint-display');
    app.ui.locatedSnippetPreview = document.getElementById('located-snippet-preview');
    app.ui.inputRevisedHint = document.getElementById('input-revised-hint');
    app.ui.btnConfirmLocation = document.getElementById('btn-confirm-location');
    app.ui.btnCancelLocationStage = document.getElementById('btn-cancel-location-stage');
    app.ui.innerLoopDecisionArea = document.getElementById('inner-loop-decision-area');
    app.ui.btnApproveThisEdit = document.getElementById('btn-approve-this-edit');
    app.ui.btnRefineThisEdit = document.getElementById('btn-refine-this-edit');
    app.ui.btnDiscardThisEdit = document.getElementById('btn-discard-this-edit');

    // Initially hide HITL-specific sections
    showSection('edit-request-input-area', false);
    showSection('location-confirmation-area', false);
    showSection('inner-loop-decision-area', false);

    // --- Event Listeners for HITL controls ---
    if (app.ui.btnApproveEndSession) {
        app.ui.btnApproveEndSession.onclick = () => {
            if (confirm("Are you sure you want to approve and end the session?")) {
                if (app.api) app.api.terminateSession(); // Calls Python backend's terminateSession
            }
        };
    }
    if (app.ui.btnRequestNewEdit) {
        app.ui.btnRequestNewEdit.onclick = () => {
            const editArea = app.ui.editRequestInputArea;
            if (editArea) {
                // Only allow opening if not currently processing another task
                const isProcessing = app.ui.queueStatusDisplay ? app.ui.queueStatusDisplay.textContent.includes("Processing") : false;
                if (!isProcessing) {
                    const currentlyOpen = !editArea.classList.contains('hidden');
                    showSection(editArea.id, !currentlyOpen); // Toggle visibility
                    // Mark if user explicitly opened it, for state management in updateGlobalUIState
                    if (!currentlyOpen) editArea.classList.add('user-opened');
                    else editArea.classList.remove('user-opened');

                    if (!editArea.classList.contains('hidden') && app.ui.inputHint) app.ui.inputHint.focus();
                } else {
                    alert("Cannot request new edit while another task is processing.");
                }
            }
            // If the edit request area is now shown, ensure other HITL sections are hidden
             if (editArea && !editArea.classList.contains('hidden')) {
                 updateGlobalUIState(false, null); // Pass false for isProcessing to hide other sections
             }
        };
    }
    if (app.ui.btnAddtoQueue) {
        app.ui.btnAddtoQueue.onclick = () => {
            const hint = app.ui.inputHint ? app.ui.inputHint.value.trim() : '';
            const instruction = app.ui.inputInstruction ? app.ui.inputInstruction.value.trim() : '';
            if (!hint || !instruction) {
                alert("Please provide both 'Where to Edit?' (Hint) and 'What to Apply?' (Instruction).");
                return;
            }
            if (app.api) {
                app.api.submitEditRequest(hint, instruction); // Calls Python backend
                if (app.ui.inputHint) app.ui.inputHint.value = ''; // Clear fields
                if (app.ui.inputInstruction) app.ui.inputInstruction.value = '';
                if (app.ui.editRequestInputArea) { // Hide input area after submission
                     app.ui.editRequestInputArea.classList.remove('user-opened');
                     showSection('edit-request-input-area', false);
                }
            }
        };
    }
    if (app.ui.btnConfirmLocation) {
        app.ui.btnConfirmLocation.onclick = () => {
            if (app.api && app.activeTaskDetails && app.activeTaskDetails.location_info) {
                // For now, the revised_hint is not directly used to re-locate on the JS side.
                // The backend's `proceed_with_edit_after_location_confirmation` receives the
                // original_location_info and the original_instruction.
                // If a revised_hint was intended to trigger re-location, the flow would be more complex,
                // potentially involving a new type of call to the backend.
                // Current behavior: User confirms the snippet as presented (based on original_hint or its auto-location).
                // The `inputRevisedHint` might be used if the user *rejects* and then clarifies.
                app.api.submitConfirmedLocationAndInstruction(app.activeTaskDetails.location_info, app.activeTaskDetails.user_instruction);
            }
        };
    }
    if (app.ui.btnCancelLocationStage) {
        app.ui.btnCancelLocationStage.onclick = () => {
            // This cancels the *active* task at the location confirmation stage.
            if (app.api) app.api.submitLLMTaskDecision('cancel');
        };
    }
    if (app.ui.btnApproveThisEdit) {
        app.ui.btnApproveThisEdit.onclick = () => {
            let contentToApprove = '';
            const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
            const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';

            // Get content from the modified pane of the main diff editor
            if (mainDiffWidgetConfig && app.widgets[mainDiffWidgetName] && app.widgets[mainDiffWidgetName].instance) {
                contentToApprove = app.widgets[mainDiffWidgetName].instance.getModifiedEditor().getValue();
            } else if (app.activeTaskDetails && app.activeTaskDetails.llmProposedSnippet !== undefined) {
                // Fallback if editor not found, though it should be there for diff preview
                contentToApprove = app.activeTaskDetails.llmProposedSnippet;
            }
            if (app.api) app.api.submitLLMTaskDecisionWithEdit('approve', contentToApprove);
        };
    }
    if (app.ui.btnRefineThisEdit) { // Currently mapped to 'reject' to trigger clarification
        app.ui.btnRefineThisEdit.onclick = () => {
            // This effectively means "I don't like this edit, let me clarify"
            if (app.api) app.api.submitLLMTaskDecision('reject');
        };
    }
    if (app.ui.btnDiscardThisEdit) { // Mapped to 'cancel'
        app.ui.btnDiscardThisEdit.onclick = () => {
            // This cancels the *active* task at the diff approval stage.
            if (app.api) app.api.submitLLMTaskDecision('cancel');
        };
    }
}


// --- Main Execution Block ---
// This code runs after the Monaco editor AMD modules are loaded.
require(['vs/editor/editor.main'], () => {
  // Establish connection with Python backend via QWebChannel
  new QWebChannel(qt.webChannelTransport, channel => {
    if (!channel.objects.backend) {
        console.error("ERROR: 'backend' object not found in QWebChannel. Ensure it's registered in Python.");
        alert("Critical Error: Could not connect to Python backend. Frontend functionality will be limited.");
        return;
    }
    app.api = channel.objects.backend; // Store backend reference
    initializeHitlUIElements(); // Setup static UI elements and listeners

    // --- Connect Python signals to JavaScript handlers ---

    // Handles updates to data, config, and queue status from Python
    if (app.api.updateViewSignal) {
        app.api.updateViewSignal.connect((data, config, queue_info) => {
            console.log("JS: updateViewSignal received.", {data, config, queue_info});
            app.data = data;
            const prevConfigStr = JSON.stringify(app.config); // For comparison
            app.config = config;

            // Re-render configurable UI if config changed or widgets not yet initialized
            if (JSON.stringify(config) !== prevConfigStr || Object.keys(app.widgets).length === 0) {
                 renderConfigurableUI();
            }
            renderData(); // Populate UI with new data

            // Update queue status display
            if (app.ui.queueStatusDisplay) {
                let statusText = `Queue: ${queue_info.size} | `;
                if (queue_info.is_processing && queue_info.active_task_hint) {
                    statusText += `Processing "${queue_info.active_task_hint}" (${queue_info.active_task_status || 'busy'})...`;
                } else if (queue_info.is_processing) {
                    statusText += `Processing... (${queue_info.active_task_status || 'busy'})`;
                } else {
                    statusText += 'Idle';
                }
                app.ui.queueStatusDisplay.textContent = statusText;
            }
            // Update visibility/state of HITL UI sections based on current task status
            updateGlobalUIState(queue_info.is_processing, queue_info.active_task_status);
        });
    } else {
        console.error("JS Error: Python 'updateViewSignal' not found on backend object.");
    }

    // Handles request from Python to confirm a located snippet
    if (app.api.promptUserToConfirmLocationSignal) {
        app.api.promptUserToConfirmLocationSignal.connect((location_info, original_hint, original_instruction) => {
            console.log("JS: promptUserToConfirmLocationSignal received.", {location_info, original_hint, original_instruction});
            // Store details of the task for later use (e.g., when 'Confirm Location' is clicked)
            app.activeTaskDetails = { location_info, original_hint, user_instruction: original_instruction, status: 'awaiting_location_confirmation' };
            if (app.ui.originalHintDisplay) app.ui.originalHintDisplay.textContent = original_hint;
            if (app.ui.locatedSnippetPreview) app.ui.locatedSnippetPreview.textContent = location_info.snippet;
            if (app.ui.inputRevisedHint) app.ui.inputRevisedHint.value = original_hint; // Pre-fill revised hint input

            updateGlobalUIState(true, 'awaiting_location_confirmation'); // Show location confirmation UI
            if (app.ui.inputRevisedHint) app.ui.inputRevisedHint.focus();
        });
    } else {
        console.error("JS Error: Python 'promptUserToConfirmLocationSignal' not found.");
    }

    // Handles request from Python to show a diff preview
    if (app.api.showDiffPreviewSignal) {
        app.api.showDiffPreviewSignal.connect((originalSnippet, editedSnippet/*, contextBefore, contextAfter */) => {
            console.log("JS: showDiffPreviewSignal received.");
            const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
            const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';

            if (mainDiffWidgetConfig && app.widgets[mainDiffWidgetName] && app.widgets[mainDiffWidgetName].instance) {
                const editorInstance = app.widgets[mainDiffWidgetName].instance;
                if (editorInstance.getModel()) {
                    editorInstance.getModel().original.setValue(originalSnippet || '');
                    editorInstance.getModel().modified.setValue(editedSnippet || '');
                }
                // Store the LLM's proposed snippet in case user approves without manual edit in diff
                if (app.activeTaskDetails) app.activeTaskDetails.llmProposedSnippet = editedSnippet;
            } else {
                // Fallback if Monaco editor isn't configured/found for the main diff
                alert(`DIFF PREVIEW (Monaco editor not found for main_diff):\n--- ORIGINAL ---\n${originalSnippet}\n--- EDITED ---\n${editedSnippet}`);
            }
            if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_diff_approval';
            updateGlobalUIState(true, 'awaiting_diff_approval'); // Show diff approval UI
        });
    } else {
         console.error("JS Error: Python 'showDiffPreviewSignal' not found.");
    }

    // Handles request from Python to ask for clarification from the user
    if (app.api.requestClarificationSignal) {
        app.api.requestClarificationSignal.connect(() => {
            console.log("JS: requestClarificationSignal received.");
            if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_clarification';
            updateGlobalUIState(true, 'awaiting_clarification'); // Update UI for clarification state

            const currentHint = app.activeTaskDetails ? app.activeTaskDetails.original_hint : '';
            const currentInstruction = app.activeTaskDetails ? app.activeTaskDetails.user_instruction : '';

            // Use prompt for simplicity; a modal dialog would be better for a real application
            const newHint = prompt(`REFINE TASK:\nOriginal Hint: ${currentHint}\nEnter new/revised Hint (or leave blank to keep current):`, currentHint);
            if (newHint !== null) { // User didn't cancel the first prompt
                const newInstruction = prompt(`Original Instruction: ${currentInstruction}\nEnter new/revised Instruction for this task:`, currentInstruction);
                if (newInstruction !== null) { // User didn't cancel the second prompt
                    if (app.api) app.api.submitClarificationForActiveTask(newHint, newInstruction);
                } else {
                    // User cancelled instruction prompt, potentially revert UI or treat as no change.
                    // For now, assume task stays in clarification or backend handles it.
                    // Or, revert UI to previous state (e.g., diff approval if that was the state before reject)
                    if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_diff_approval'; // Example: revert status
                    updateGlobalUIState(true, 'awaiting_diff_approval');
                }
            } else {
                // User cancelled hint prompt.
                if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_diff_approval'; // Example: revert status
                updateGlobalUIState(true, 'awaiting_diff_approval');
            }
        });
    } else {
        console.error("JS Error: Python 'requestClarificationSignal' not found.");
    }

    // Handles error messages from Python
    if (app.api.showErrorSignal) {
        app.api.showErrorSignal.connect((errorMessage) => {
            console.error("JS: showErrorSignal received:", errorMessage);
            alert("Error from backend: " + errorMessage);
        });
    } else {
        console.error("JS Error: Python 'showErrorSignal' not found.");
    }


    // Fetch initial data and config from Python, then start the session
    if (app.api.getInitialPayload) {
        app.api.getInitialPayload().then(payload => {
          console.log("JS: Initial payload received.", payload);
          app.config = payload.config;
          app.data = payload.data;
          // After getting initial payload, tell Python to start the session (which might trigger first updateView)
          if (app.api.startSession) {
            app.api.startSession();
          } else {
            console.error("JS Error: Python 'startSession' method not found on backend object.");
          }
        }).catch(error => {
            console.error("JS: Error calling getInitialPayload:", error);
            alert("Critical Error: Could not fetch initial data from backend. Please check console.");
        });
    } else {
        console.error("JS Error: Python 'getInitialPayload' method not found on backend object.");
        alert("Critical Error: Backend API is incomplete. Cannot initialize.");
    }
  });
});

/**
 * Updates the global UI state based on whether a task is processing and its status.
 * Manages visibility of HITL sections and enabled/disabled state of buttons.
 * @param {boolean} isProcessing - True if an edit task is currently being processed by the backend.
 * @param {string|null} activeTaskStatus - The status of the active task (e.g., 'locating_snippet', 'awaiting_diff_approval').
 */
function updateGlobalUIState(isProcessing, activeTaskStatus) {
    console.log("JS: Updating global UI state. isProcessing:", isProcessing, "activeTaskStatus:", activeTaskStatus);

    // Manage visibility of the 'New Edit Request' area
    // It should be hidden if processing, or if not processing AND not explicitly opened by user.
    const userOpenedEditRequest = app.ui.editRequestInputArea ? app.ui.editRequestInputArea.classList.contains('user-opened') : false;
    showSection('edit-request-input-area', !isProcessing && userOpenedEditRequest);

    // Show/hide HITL-specific sections based on active task status
    showSection('location-confirmation-area', isProcessing && activeTaskStatus === 'awaiting_location_confirmation');
    showSection('inner-loop-decision-area', isProcessing && activeTaskStatus === 'awaiting_diff_approval');

    // If in clarification state, typically all other specific HITL sections are hidden
    // as the clarification is handled by prompts or a dedicated (future) UI.
    if (isProcessing && activeTaskStatus === 'awaiting_clarification') {
        showSection('location-confirmation-area', false);
        showSection('inner-loop-decision-area', false);
    }

    // Disable/enable global control buttons based on processing state
    if (app.ui.btnRequestNewEdit) app.ui.btnRequestNewEdit.disabled = isProcessing;
    if (app.ui.btnApproveEndSession) app.ui.btnApproveEndSession.disabled = isProcessing;
    // Also disable "Add to Queue" button if processing, as new requests are queued via btnRequestNewEdit flow
    if (app.ui.btnAddtoQueue) app.ui.btnAddtoQueue.disabled = isProcessing;


    // Disable/enable dynamically generated action buttons (e.g., in sidebar/footer)
    // Avoid disabling buttons within the active HITL UI sections themselves (e.g., "Approve This Edit")
    const configActionButtons = document.querySelectorAll(
        '#header-container .action-button, #sidebar-container .action-button, #footer-container .action-button'
    );
    configActionButtons.forEach(button => {
        // Check if the button is part of a specific HITL interaction area that manages its own state
        const isWithinActiveHitlSection = button.closest('#location-confirmation-area') ||
                                          button.closest('#inner-loop-decision-area') ||
                                          button.closest('#edit-request-input-area');
        if (!isWithinActiveHitlSection) {
            button.disabled = isProcessing;
        }
    });
}

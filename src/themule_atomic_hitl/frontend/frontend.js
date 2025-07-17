import loader from 'https://cdn.jsdelivr.net/npm/@monaco-editor/loader@1.4.0/+esm';

// Log that the script execution has started.
console.log("JS TRACE (1): Script execution started.");
// Log that the frontend.js script is starting.
console.log("frontend.js starting");
// Configure the AMD loader for Monaco editor.
// This tells the loader where to find the editor's source files.
// Log that the Monaco loader path is being configured.
console.log("JS TRACE (2): Configuring Monaco loader path.");

/**
 * Main application state object.
 * @property {object} config - Loaded from Python backend. Defines UI structure.
 * @property {object} data - Loaded from Python backend. Contains the actual data being edited.
 * @property {object} widgets - Stores references to dynamically created UI elements (Monaco editors, input fields, labels).
 * @property {object|null} api - Reference to the Python backend object exposed via QWebChannel.
 * @property {object} ui - Stores references to static HITL (Human-in-the-Loop) UI elements from index.html.
 * @property {object} activeTaskDetails - Stores details of the current HITL task.
 */
let app = {
  config: {},
  data: {},
  widgets: {},
  api: null,
  ui: {},
  activeTaskDetails: {},
  activeSelectionDetails: null, // To store captured selection { text, startLine, startColumn, endLine, endColumn }
  isBackendBusy: false // Flag to track if backend is processing a task
};

/**
 * Manages the visibility of different UI sections.
 * @param {string} sectionId - The ID of the HTML element (section) to show or hide.
 * @param {boolean} makeVisible - True to show the section, false to hide it.
 */
function showSection(sectionId, makeVisible) {
    console.log(`showSection called with sectionId: ${sectionId} and makeVisible: ${makeVisible}`);
    // Get the section element by its ID.
    const section = document.getElementById(sectionId);
    // If the section exists,
    if (section) {
        // If we want to make it visible,
        if (makeVisible) {
            // remove the 'hidden' class.
            section.classList.remove('hidden');
        } else {
            // Otherwise, add the 'hidden' class.
            section.classList.add('hidden');
        }
    }
}

/**
 * Renders the configurable parts of the UI based on `app.config`.
 * Creates input fields, labels, buttons, and potentially the Monaco diff editor.
 * Attempts to preserve the main Monaco diff editor instance if it exists.
 */
function renderConfigurableUI() {
  // Log that the function has been called and the current app configuration.
  console.log("JS: renderConfigurableUI called. Current app.config:", app.config);
  // An array of container IDs that can be configured.
  const configurableContainers = ['header-container', 'sidebar-container', 'mainbody-container', 'footer-container'];
  // The main diff editor element, initially null.
  let mainDiffEditorElement = null;
  // The configuration for the main diff editor widget.
  const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
  // The name of the main diff editor widget.
  const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';

  // Preserve existing Monaco editor instance if it's already in the DOM and valid
  if (app.widgets[mainDiffWidgetName] && app.widgets[mainDiffWidgetName].instance && typeof app.widgets[mainDiffWidgetName].instance.getDomNode === 'function') {
      // Get the main body container.
      const mainBody = document.getElementById('mainbody-container');
      // Get the editor's DOM node.
      const editorDomNode = app.widgets[mainDiffWidgetName].instance.getDomNode();
      // If the main body and editor DOM node exist, and the main body contains the editor DOM node,
      if (mainBody && editorDomNode && mainBody.contains(editorDomNode)) {
          // set the main diff editor element to the parent of the editor DOM node.
          mainDiffEditorElement = editorDomNode.parentElement;
      }
  }

  // For each container ID,
  configurableContainers.forEach(id => {
    // get the container element.
    const container = document.getElementById(id);
    // If the container exists,
    if (container) {
        // If the container is the main body and there's a main diff editor element,
        if (id === 'mainbody-container' && mainDiffEditorElement) {
            // remove all children of the container except the main diff editor element and some other specific elements.
            Array.from(container.childNodes).forEach(child => {
                if (child !== mainDiffEditorElement && !mainDiffEditorElement.contains(child) &&
                    child.id !== 'location-confirmation-area' && child.id !== 'inner-loop-decision-area') {
                    container.removeChild(child);
                }
            });
        } else if (id !== 'mainbody-container' || (id === 'mainbody-container' && !mainDiffEditorElement) ) {
             // Otherwise, clear the container's inner HTML.
             container.innerHTML = ''; // Clear if not mainbody, or if mainbody without preserved editor
        }
    } else {
        // If the container doesn't exist, log a warning.
        console.warn(`renderConfigurableUI: Container ID '${id}' not found in HTML.`);
    }
  });

  // Keep a reference to the old widgets.
  const oldWidgets = app.widgets; // Keep a reference if needed for complex preservation, otherwise reset
  // Reset the widgets.
  app.widgets = {};

  // If there are fields in the app configuration,
  if (app.config.fields) {
    // for each field,
    app.config.fields.forEach(field => {
        // get the container for the field's placement.
        const container = document.getElementById(`${field.placement}-container`);
        // If the container doesn't exist and the placement is not 'none',
        if (!container && field.placement !== 'none') {
            // log a warning and return.
            console.warn(`Container for placement '${field.placement}-container' not found for field '${field.name}'.`);
            return;
        }

        // If the field is a diff editor,
        if (field.type === 'diff-editor') {
            // Attempt to reuse existing editor instance if it matches and was preserved
            if (field.name === mainDiffWidgetName && mainDiffEditorElement && oldWidgets[mainDiffWidgetName]?.instance?.getDomNode) {
                // Relink the preserved widget.
                app.widgets[field.name] = oldWidgets[mainDiffWidgetName]; // Relink preserved widget
                // Log that the editor has been re-linked.
                console.log(`JS: Re-linked preserved Monaco editor for '${field.name}'.`);

                // Add selection change listener for the "Use Selection as Context" button
                // Ensure this is the main editor expected to provide context
                const editorInstance = app.widgets[field.name].instance;
                // If the editor instance exists and has a getModifiedEditor method,
                if (editorInstance && editorInstance.getModifiedEditor) {
                    // get the modified editor.
                    const modifiedEditor = editorInstance.getModifiedEditor();
                    // It's possible the listener already exists if the editor instance is truly preserved.
                    // Monaco editor might handle duplicate event subscriptions gracefully, or one might
                    // consider storing a flag or using disposable event listeners if issues arise.
                    // For now, re-adding is simpler if Monaco handles it.
                    // Add a listener for when the cursor selection changes.
                    modifiedEditor.onDidChangeCursorSelection(() => {
                        // If the "Use Selection as Context" button exists,
                        if (app.ui.btnUseSelectionContext) {
                            // get the selection.
                            const selection = modifiedEditor.getSelection();
                            // Check if there is a selection.
                            const hasSelection = selection && !selection.isEmpty();
                            // Check if the edit request area is visible.
                            const editRequestAreaVisible = app.ui.editRequestInputArea ? !app.ui.editRequestInputArea.classList.contains('hidden') : false;

                            // If the edit request area is visible and the backend is not busy,
                            if (editRequestAreaVisible && !app.isBackendBusy) {
                                // If there is an active selection,
                                if (app.activeSelectionDetails) {
                                    // enable the "Clear" button.
                                    app.ui.btnUseSelectionContext.disabled = false;
                                } else {
                                    // Otherwise, enable the "Use Selection" button only if there's text selected.
                                    app.ui.btnUseSelectionContext.disabled = !hasSelection;
                                }
                            } else {
                                // If the edit area is not visible or the backend is busy, disable the button.
                                app.ui.btnUseSelectionContext.disabled = true;
                            }
                        }
                    });
                }
            } else {
                // Otherwise, create a new editor div.
                const editorDiv = document.createElement('div');
                // Set the editor div's ID.
                editorDiv.id = `editor-${field.name}`;
                // If the field is in the main body,
                if (field.placement === 'mainbody') {
                    // Use class for styling now, defined in index.html
                    editorDiv.className = 'editor-container-style';
                    // Clear inline styles that might conflict
                    editorDiv.style.height = "";
                    editorDiv.style.width = "";
                    editorDiv.style.border = "";
                } else {
                    // Otherwise, set some default styles.
                    editorDiv.style.height = "200px"; // Keep for non-mainbody editors if any
                    editorDiv.style.minWidth = "100px";
                    editorDiv.style.border = "1px solid #dee2e6"; // Use new border color
                }
                // If the container exists, append the editor div to it.
                if (container) container.appendChild(editorDiv);

                // If the Monaco editor API is available,
                if (typeof monaco !== 'undefined' && typeof monaco.editor !== 'undefined') {
                    try {
                        // create a new diff editor.
                        const editor = monaco.editor.createDiffEditor(editorDiv, {
                            automaticLayout: true,
                            originalEditable: field.originalEditable === true,
                            readOnly: field.readOnly === true,
                            lineNumbers: 'on' // Added line numbers
                        });
                        // Set the editor's model.
                        editor.setModel({
                            original: monaco.editor.createModel('', field.language || 'text/plain'),
                            modified: monaco.editor.createModel('', field.language || 'text/plain')
                        });
                        // Add the editor to the widgets.
                        app.widgets[field.name] = { type: 'diff-editor', instance: editor, config: field };
                        // Log that a new editor has been created.
                        console.log(`JS: Created new Monaco editor for '${field.name}'.`);

                        // Add selection change listener for the "Use Selection as Context" button
                        if (field.name === mainDiffWidgetName) { // Assuming this is the main editor
                            // get the modified editor.
                            const modifiedEditor = editor.getModifiedEditor();
                            // Add a listener for when the cursor selection changes.
                            modifiedEditor.onDidChangeCursorSelection(() => {
                                // If the "Use Selection as Context" button exists,
                                if (app.ui.btnUseSelectionContext) {
                                    // get the selection.
                                    const selection = modifiedEditor.getSelection();
                                    // Check if there is a selection.
                                    const hasSelection = selection && !selection.isEmpty();
                                    // Check if the edit request area is visible.
                                    const editRequestAreaVisible = app.ui.editRequestInputArea ? !app.ui.editRequestInputArea.classList.contains('hidden') : false;

                                    // If the edit request area is visible and the backend is not busy,
                                    if (editRequestAreaVisible && !app.isBackendBusy) {
                                         // If there is an active selection,
                                         if (app.activeSelectionDetails) {
                                            // enable the "Clear" button.
                                            // It's enabled unless the overall conditions (area visible, not busy) are false (handled by updateGlobalUIState).
                                            app.ui.btnUseSelectionContext.disabled = false;
                                        } else {
                                            // Otherwise, enable the "Use Selection" button only if there's text selected.
                                            app.ui.btnUseSelectionContext.disabled = !hasSelection;
                                        }
                                    } else {
                                        // If the edit area is not visible or the backend is busy, disable the button.
                                        // This is also set by updateGlobalUIState, but good to be explicit here too.
                                        app.ui.btnUseSelectionContext.disabled = true;
                                    }
                                }
                            });
                        }
                    } catch (e) {
                        // If there's an error creating the editor, log it.
                        console.error("Error creating Monaco editor for field:", field.name, e);
                        // Show an error message in the editor div.
                        editorDiv.textContent = `Error creating Monaco editor for '${field.name}'. See console.`;
                        // Add a placeholder widget.
                        app.widgets[field.name] = { type: 'diff-editor', instance: null, config: field, domElement: editorDiv };
                    }
                } else {
                    // If the Monaco editor API is not available, log a warning.
                    console.warn("Monaco editor API not available. Diff editor UI will be a placeholder for field:", field.name);
                    // Show a message in the editor div.
                    editorDiv.textContent = `Monaco editor for '${field.name}' could not be loaded.`;
                    // Add a placeholder widget.
                    app.widgets[field.name] = { type: 'diff-editor', instance: null, config: field, domElement: editorDiv };
                }
            }
        } else if (field.placement !== 'none') {
          // Otherwise, if the placement is not 'none', create a new field group.
          const group = document.createElement('div'); group.className = 'field-group';
          // Create a label for the field.
          const label = document.createElement('label'); label.htmlFor = `field-${field.name}`; label.textContent = field.label; group.appendChild(label);
          // The element for the field.
          let element;
          // If the field is a text input,
          if (field.type === 'text-input') {
            // create a text input.
            element = document.createElement('input');
            element.type = 'text';
            element.readOnly = field.readOnly === true;
          } else if (field.type === 'textarea') {
            // Otherwise, if the field is a textarea, create a textarea.
            element = document.createElement('textarea');
            element.readOnly = field.readOnly === true;
          } else {
            // Otherwise, create a span.
            element = document.createElement('span');
            // If the field is a bold label, add the 'label-bold' class.
            if (field.type === 'label-bold') element.classList.add('label-bold');
          }
          // Set the element's ID.
          element.id = `field-${field.name}`;
          // Append the element to the group.
          group.appendChild(element);
          // Add the widget to the widgets.
          app.widgets[field.name] = { type: 'field', element: element, config: field };
          // If the container exists, append the group to it.
          if (container) container.appendChild(group);
        }
    });
  }

  // If there are actions in the app configuration,
  if (app.config.actions) {
    // for each action,
    app.config.actions.forEach(action => {
        // get the container for the action's placement.
        const container = document.getElementById(`${action.placement}-container`);
        // If the container doesn't exist,
        if (!container) {
            // log a warning and return.
            console.warn(`Container for placement '${action.placement}-container' not found for action '${action.name}'.`);
            return;
        }
        // Create a button for the action.
        const button = document.createElement('button');
        // Set the button's text content.
        button.textContent = action.label;
        // Set the button's class name.
        button.className = 'action-button';
        // If the action is primary, add the 'primary' class.
        if (action.isPrimary) button.classList.add('primary');
        // Set the button's onclick handler.
        button.onclick = () => {
          // If the API is not available,
          if (!app.api) {
            // alert the user and log an error.
            alert("Backend API not available. Action cannot be performed.");
            console.error("PerformAction: app.api is not available.");
            return;
          }
          // Get the payload from the UI.
          const payload = getPayloadFromUI(action);
          // Perform the action.
          app.api.performAction(action.name, payload);
        };
        // Append the button to the container.
        container.appendChild(button);
    });
  }
}

/**
 * Populates UI elements with data from `app.data`.
 */
function renderData() {
  // Log that the function has been called and the current app data.
  console.log("JS: renderData called. Current app.data:", app.data);
  // For each widget,
  for (const name in app.widgets) {
    // get the widget.
    const widget = app.widgets[name];
    // Get the field configuration.
    const fieldConfig = widget.config;

    // If the widget is a diff editor,
    if (widget.type === 'diff-editor') {
      // get the original and modified values.
      const originalValue = app.data[fieldConfig.originalDataField] || '';
      const modifiedValue = app.data[fieldConfig.modifiedDataField] || '';
      // If the editor instance exists,
      if (widget.instance && widget.instance.getModel) { // Monaco editor instance exists
          // set the original and modified values.
          widget.instance.getModel().original.setValue(originalValue);
          widget.instance.getModel().modified.setValue(modifiedValue);
      } else if (widget.domElement) { // Placeholder div exists
          // Otherwise, if the placeholder div exists, set its text content.
          widget.domElement.textContent = `(Monaco N/A) Original: ${originalValue}\nModified: ${modifiedValue}`;
      }
    } else if (widget.type === 'field') {
      // Otherwise, if the widget is a field,
      // get the value.
      const value = app.data[fieldConfig.name] || '';
      // If the element is an input or textarea,
      if (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA') {
        // set its value.
        widget.element.value = value;
      } else {
        // Otherwise, set its text content.
        widget.element.textContent = value;
      }
    }
  }

  // Get the main diff editor configuration.
  const mainDiffConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
  // If the main diff editor configuration exists and the widget exists,
  if (mainDiffConfig && app.widgets[mainDiffConfig.name]) {
      // get the editor widget.
      const editorWidget = app.widgets[mainDiffConfig.name];
      // Get the current modified content.
      const currentModifiedContent = app.data[mainDiffConfig.modifiedDataField] || '';
      // The original content for diff should ideally come from a snapshot or the originalDataField
      const currentOriginalContent = app.data[mainDiffConfig.originalDataField] || currentModifiedContent;

      // If there are no active task details, or the status is not 'awaiting_diff_approval' or 'awaiting_location_confirmation',
      if (!app.activeTaskDetails || !app.activeTaskDetails.status ||
          (app.activeTaskDetails.status !== 'awaiting_diff_approval' &&
           app.activeTaskDetails.status !== 'awaiting_location_confirmation')) {
          // If the editor instance exists,
          if (editorWidget.instance && editorWidget.instance.getModel) {
              // When idle, show current state or make original and modified same
              // set the original and modified values.
              editorWidget.instance.getModel().original.setValue(currentOriginalContent);
              editorWidget.instance.getModel().modified.setValue(currentModifiedContent);
          } else if (editorWidget.domElement) {
              // Otherwise, if the placeholder div exists, set its text content.
              editorWidget.domElement.textContent = `(Monaco N/A) Original: ${currentOriginalContent}\nModified: ${currentModifiedContent}`;
          }
      }
  }
}

/**
 * Collects data from UI input fields to be sent as a payload with an action.
 * @param {object} action - The action object from `app.config.actions`.
 * @returns {object} payload - An object containing data from relevant UI fields.
 */
function getPayloadFromUI(action) {
    console.log(`getPayloadFromUI called with action: ${JSON.stringify(action)}`);
  // The payload to be sent.
  const payload = {};
  // For each widget,
  for (const name in app.widgets) {
    // get the widget.
    const widget = app.widgets[name];
    // If the widget is a field and an input or textarea,
    if (widget.type === 'field' && (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA')) {
      // add its value to the payload.
      payload[widget.config.name] = widget.element.value;
    }
  }
  // If the action has an editor name and the widget exists and is a diff editor,
  if (action.editorName && app.widgets[action.editorName] && app.widgets[action.editorName].type === 'diff-editor') {
    // get the editor widget.
    const editorWidget = app.widgets[action.editorName];
    // If the editor instance exists and has a getModifiedEditor method,
    if (editorWidget.instance && editorWidget.instance.getModifiedEditor) {
        // add the modified editor's value to the payload.
        payload[editorWidget.config.modifiedDataField] = editorWidget.instance.getModifiedEditor().getValue();
    } else {
        // Otherwise, add the current data for the field to the payload and log a warning.
        payload[editorWidget.config.modifiedDataField] = app.data[editorWidget.config.modifiedDataField] || '';
        console.warn(`Monaco editor '${action.editorName}' not available, sending current data for field '${editorWidget.config.modifiedDataField}'.`);
    }
  }
  // Return the payload.
  return payload;
}

/**
 * Initializes references to static HITL UI elements and sets up their event listeners.
 */
function initializeHitlUIElements() {
    console.log('initializeHitlUIElements called');
    // Get references to all the UI elements.
    app.ui.btnApproveEndSession = document.getElementById('btn-approve-end-session');
    app.ui.btnRequestNewEdit = document.getElementById('btn-request-new-edit');
    app.ui.queueStatusDisplay = document.getElementById('queue-status-display');
    app.ui.editRequestInputArea = document.getElementById('edit-request-input-area');
    app.ui.inputHint = document.getElementById('input-hint');
    app.ui.inputInstruction = document.getElementById('input-instruction');
    app.ui.btnAddtoQueue = document.getElementById('btn-add-to-queue');
    app.ui.btnUseSelectionContext = document.getElementById('btn-use-selection-context');
    app.ui.selectionContextStatus = document.getElementById('selection-context-status');
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
    app.ui.loadingSpinner = document.getElementById('loading-spinner'); // Get spinner
    // Inner loop display elements
    app.ui.innerLoopHintDisplay = document.getElementById('inner-loop-hint-display');
    app.ui.innerLoopInstructionDisplay = document.getElementById('inner-loop-instruction-display');
    app.ui.innerLoopLlmDisplay = document.getElementById('inner-loop-llm-display');


    // Hide the edit request input area, location confirmation area, and inner loop decision area by default.
    showSection('edit-request-input-area', false);
    showSection('location-confirmation-area', false);
    showSection('inner-loop-decision-area', false);
    // Update the selection context status.
    updateSelectionContextStatus(); // Initial call

    // If the "Approve and End Session" button exists,
    if (app.ui.btnApproveEndSession) {
        // set its onclick handler.
        app.ui.btnApproveEndSession.onclick = () => {
            // If the user confirms,
            if (confirm("Are you sure you want to approve and end the session?")) {
                // terminate the session.
                if (app.api) app.api.terminateSession();
                else console.error("TerminateSession: app.api not available.");
            }
        };
    }
    // If the "Request New Edit" button exists,
    if (app.ui.btnRequestNewEdit) {
        // set its onclick handler.
        app.ui.btnRequestNewEdit.onclick = () => {
            // Get the edit area.
            const editArea = app.ui.editRequestInputArea;
            // If the edit area exists,
            if (editArea) {
                // check if a task is processing.
                const isProcessing = app.ui.queueStatusDisplay ? app.ui.queueStatusDisplay.textContent.includes("Processing") : false;
                // If a task is not processing or the API is not available,
                if (!isProcessing || !app.api) {
                    // toggle the visibility of the edit area.
                    const currentlyOpen = !editArea.classList.contains('hidden');
                    showSection(editArea.id, !currentlyOpen);
                    // If the edit area is now open, add the 'user-opened' class.
                    if (!currentlyOpen) editArea.classList.add('user-opened');
                    else editArea.classList.remove('user-opened');
                    // If the edit area is open, focus on the input hint.
                    if (!editArea.classList.contains('hidden') && app.ui.inputHint) app.ui.inputHint.focus();
                } else {
                    // Otherwise, alert the user.
                    alert("Cannot request new edit while another task is processing.");
                }
            }
             // If the edit area is open, update the global UI state.
             if (editArea && !editArea.classList.contains('hidden')) {
                 updateGlobalUIState(false, null);
             }
        };
    }
    // If the "Add to Queue" button exists,
    if (app.ui.btnAddtoQueue) {
        // set its onclick handler.
        app.ui.btnAddtoQueue.onclick = () => {
            // Get the hint and instruction.
            const hint = app.ui.inputHint ? app.ui.inputHint.value.trim() : '';
            const instruction = app.ui.inputInstruction ? app.ui.inputInstruction.value.trim() : '';
            // If the hint or instruction is empty, alert the user.
            if (!hint || !instruction) {
                alert("Please provide both 'Where to Edit?' (Hint) and 'What to Apply?' (Instruction).");
                return;
            }
            // If the API is available,
            if (app.api) {
                // create a request payload.
                let requestPayload = {
                    instruction: instruction,
                    type: '',
                    selection_details: null,
                    hint: null
                };

                // If there is an active selection,
                if (app.activeSelectionDetails) {
                    // set the request type to 'selection_specific' and add the selection details to the payload.
                    requestPayload.type = 'selection_specific';
                    requestPayload.selection_details = app.activeSelectionDetails;
                    console.log("JS: Submitting selection_specific request", requestPayload);
                } else {
                    // Otherwise, if there is no hint, alert the user.
                    if (!hint) { // Ensure hint is provided if not using selection
                        alert("Please provide 'Where to Edit?' (Hint) or use 'Use Editor Selection as Context'.");
                        return;
                    }
                    // Set the request type to 'hint_based' and add the hint to the payload.
                    requestPayload.type = 'hint_based';
                    requestPayload.hint = hint;
                    console.log("JS: Submitting hint_based request", requestPayload);
                }

                // Submit the edit request.
                app.api.submitEditRequest(JSON.stringify(requestPayload)); // Send as JSON string

                // Reset UI
                // Clear the input hint and instruction.
                if (app.ui.inputHint) app.ui.inputHint.value = '';
                if (app.ui.inputInstruction) app.ui.inputInstruction.value = '';
                // Clear the active selection details.
                app.activeSelectionDetails = null;
                // Update the selection context status.
                updateSelectionContextStatus(); // Update button and status text
                // Enable the input hint.
                if (app.ui.inputHint) app.ui.inputHint.disabled = false;


                // If the edit request input area exists,
                if (app.ui.editRequestInputArea) {
                     // remove the 'user-opened' class and hide it.
                     app.ui.editRequestInputArea.classList.remove('user-opened');
                     showSection('edit-request-input-area', false);
                }
            } else {
                // Otherwise, alert the user.
                alert("Backend not available to submit edit request.");
            }
        };
    }

    // If the "Use Selection as Context" button exists,
    if (app.ui.btnUseSelectionContext) {
        // set its onclick handler.
        app.ui.btnUseSelectionContext.onclick = () => {
            // If there is an active selection,
            if (app.activeSelectionDetails) {
                // Clear current selection context
                app.activeSelectionDetails = null;
                // Enable the input hint.
                if (app.ui.inputHint) app.ui.inputHint.disabled = false;
                // Update the selection context status.
                updateSelectionContextStatus();
            } else {
                // Capture new selection context
                // Get the main diff editor widget configuration.
                const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
                // Get the main diff editor widget name.
                const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';
                // Get the editor widget.
                const editorWidget = app.widgets[mainDiffWidgetName];

                // If the editor widget exists and has a getModifiedEditor method,
                if (editorWidget && editorWidget.instance && editorWidget.instance.getModifiedEditor) {
                    // get the modified editor.
                    const modifiedEditor = editorWidget.instance.getModifiedEditor();
                    // Get the selection.
                    const selection = modifiedEditor.getSelection(); // This is a Monaco ISelection

                    // If there is a selection,
                    if (selection && !selection.isEmpty()) {
                        // get the selected text.
                        const selectedText = modifiedEditor.getModel().getValueInRange(selection);
                        // Set the active selection details.
                        app.activeSelectionDetails = {
                            text: selectedText,
                            startLineNumber: selection.startLineNumber,
                            startColumn: selection.startColumn,
                            endLineNumber: selection.endLineNumber,
                            endColumn: selection.endColumn
                        };
                        // If the input hint exists,
                        if (app.ui.inputHint) {
                            // set its value and disable it.
                            app.ui.inputHint.value = `Selection: Lines ${selection.startLineNumber}-${selection.endLineNumber}`;
                            app.ui.inputHint.disabled = true;
                        }
                        // Update the selection context status.
                        updateSelectionContextStatus();
                    } else {
                        // Otherwise, alert the user.
                        alert("No text selected in the editor's modified view.");
                    }
                } else {
                    // Otherwise, alert the user.
                    alert("Editor not available to get selection.");
                }
            }
        };
    }

    // If the "Confirm Location" button exists,
    if (app.ui.btnConfirmLocation) {
        // set its onclick handler.
        app.ui.btnConfirmLocation.onclick = () => {
            // If the API is available and there are active task details with location info,
            if (app.api && app.activeTaskDetails && app.activeTaskDetails.location_info) {
                // submit the confirmed location and instruction.
                app.api.submitConfirmedLocationAndInstruction(app.activeTaskDetails.location_info, app.activeTaskDetails.user_instruction);
            } else if (!app.api) console.error("ConfirmLocation: app.api not available.");
        };
    }
    // If the "Cancel Location Stage" button exists,
    if (app.ui.btnCancelLocationStage) {
        // set its onclick handler.
        app.ui.btnCancelLocationStage.onclick = () => {
            // If the API is available, submit a 'cancel' decision.
            if (app.api) app.api.submitLLMTaskDecision('cancel');
            else console.error("CancelLocationStage: app.api not available.");
        };
    }
    // If the "Approve This Edit" button exists,
    if (app.ui.btnApproveThisEdit) {
        // set its onclick handler.
        app.ui.btnApproveThisEdit.onclick = () => {
            // The content to be approved.
            let contentToApprove = '';
            // Get the main diff editor widget configuration.
            const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
            // Get the main diff editor widget name.
            const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';
            // If the main diff editor widget exists and has a getModifiedEditor method,
            if (mainDiffWidgetConfig && app.widgets[mainDiffWidgetName] && app.widgets[mainDiffWidgetName].instance && app.widgets[mainDiffWidgetName].instance.getModifiedEditor) {
                // get the modified editor's value.
                contentToApprove = app.widgets[mainDiffWidgetName].instance.getModifiedEditor().getValue();
            } else if (app.activeTaskDetails && app.activeTaskDetails.llmProposedSnippet !== undefined) {
                // Otherwise, if there is a proposed snippet, use it.
                contentToApprove = app.activeTaskDetails.llmProposedSnippet;
            }
            // If the API is available, submit an 'approve' decision with the content to approve.
            if (app.api) app.api.submitLLMTaskDecisionWithEdit('approve', contentToApprove);
            else console.error("ApproveThisEdit: app.api not available.");
        };
    }
    // If the "Refine This Edit" button exists,
    if (app.ui.btnRefineThisEdit) {
        // set its onclick handler.
        app.ui.btnRefineThisEdit.onclick = () => {
            // If the API is available, submit a 'reject' decision.
            if (app.api) app.api.submitLLMTaskDecision('reject');
            else console.error("RefineThisEdit: app.api not available.");
        };
    }
    // If the "Discard This Edit" button exists,
    if (app.ui.btnDiscardThisEdit) {
        // set its onclick handler.
        app.ui.btnDiscardThisEdit.onclick = () => {
            // If the API is available, submit a 'cancel' decision.
            if (app.api) app.api.submitLLMTaskDecision('cancel');
            else console.error("DiscardThisEdit: app.api not available.");
        };
    }
}

/**
 * Updates the selection context status display and button.
 */
function updateSelectionContextStatus() {
    console.log('updateSelectionContextStatus called');
    // If the "Use Selection as Context" button or the selection context status display doesn't exist, return.
    if (!app.ui.btnUseSelectionContext || !app.ui.selectionContextStatus) return;

    // If there are active selection details,
    if (app.activeSelectionDetails) {
        // change the button text and style to indicate that it will clear the context.
        app.ui.btnUseSelectionContext.textContent = 'Clear Editor Selection Context';
        app.ui.btnUseSelectionContext.classList.add('danger'); // Make it look like a "clear" or "cancel" action
        // Truncate the display text if it's too long.
        let displayText = app.activeSelectionDetails.text;
        if (displayText.length > 50) {
            displayText = displayText.substring(0, 47) + "...";
        }
        // Update the selection context status display.
        app.ui.selectionContextStatus.textContent = `Context: "${displayText}" (Lines ${app.activeSelectionDetails.startLineNumber}-${app.activeSelectionDetails.endLineNumber})`;
        // Disable the input hint.
        if (app.ui.inputHint) app.ui.inputHint.disabled = true;
    } else {
        // Otherwise, change the button text and style to indicate that it will use the selection as context.
        app.ui.btnUseSelectionContext.textContent = 'Use Editor Selection as Context';
        app.ui.btnUseSelectionContext.classList.remove('danger');
        // Clear the selection context status display.
        app.ui.selectionContextStatus.textContent = '';
        // If the input hint exists,
        if (app.ui.inputHint) {
            // Only enable if the edit request area is actually open and not processing
             const editAreaOpenAndNotProcessing = app.ui.editRequestInputArea &&
                                             !app.ui.editRequestInputArea.classList.contains('hidden') &&
                                             (!app.activeTaskDetails || !app.activeTaskDetails.status || app.activeTaskDetails.status === 'idle'); // Simplified check
            // If the edit area is open and not processing, enable the input hint.
            if(editAreaOpenAndNotProcessing) app.ui.inputHint.disabled = false;
        }
    }
    // The general enabled/disabled state of btnUseSelectionContext itself
    // will be handled by updateGlobalUIState and editor selection change events.
}

// --- Main Execution Block ---
// Log that the main Monaco script is being loaded.
console.log("JS TRACE (3): Triggering main Monaco script load.");
// Load the main Monaco editor script.
loader.init().then(monaco => { // Monaco loader uncommented
  // Log that the Monaco script has loaded and the callback is running.
  console.log("JS TRACE (4): Monaco script has loaded, AMD callback is running.");
  // Log that the Monaco editor has been loaded and check for the qt object.
  console.log("JS: Monaco editor loaded via require. Checking for qt object before QWebChannel setup...");
  // If the qt object and webChannelTransport exist,
  if (typeof qt !== 'undefined' && qt.webChannelTransport) {
    // log that they were found and proceed with QWebChannel.
    console.log("JS: qt object and qt.webChannelTransport found. Proceeding with QWebChannel.");
    // Create a new QWebChannel.
    new QWebChannel(qt.webChannelTransport, channel => {
      // If the backend object is not found in the channel,
      if (!channel.objects || !channel.objects.backend) {
          // log an error and alert the user.
          console.error("ERROR: 'backend' object not found in QWebChannel. Ensure it's registered in Python and QWebChannel is working.");
          alert("Critical Error: Could not connect to Python backend. Frontend functionality will be limited.");
          // Set the API to null.
          app.api = null;
          // Initialize the HITL UI elements.
          initializeHitlUIElements();
          // Display an error message in the queue status display.
          if(app.ui.queueStatusDisplay) app.ui.queueStatusDisplay.textContent = "Error: Backend not available.";
          // Return.
          return;
      }
      // Set the API to the backend object.
      app.api = channel.objects.backend;
      // Log that the backend object has been received.
      console.log("JS: app.api (backend object) received:", app.api);
      // Initialize the HITL UI elements.
      initializeHitlUIElements();

      // Log that the signals are being connected.
      console.log("JS: Attempting to connect signals...");

      // If the updateViewSignal exists,
      if (app.api && app.api.updateViewSignal) {
          // connect to it.
          app.api.updateViewSignal.connect((data_json, config_json, queue_info_json) => {
            // Log that the signal was received.
            console.log("JS: updateViewSignal received (raw JSON strings):", data_json, config_json, queue_info_json);
            // Parse the data, config, and queue info.
            const data = JSON.parse(data_json);
            const config = JSON.parse(config_json);
            const queue_info = JSON.parse(queue_info_json);

            // Update the app data and config.
            app.data = data;
            app.config = config;
            // If the widgets are empty or the config has changed,
            if (Object.keys(app.widgets).length === 0 || JSON.stringify(app.config) !== JSON.stringify(config)) { // Basic check
                 // render the configurable UI.
                 renderConfigurableUI();
            }
            // Render the data.
            renderData();
            // If the queue status display exists,
            if (app.ui.queueStatusDisplay) {
                // update its text content.
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
            // Update the global UI state.
            updateGlobalUIState(queue_info.is_processing, queue_info.active_task_status);
        });
    } else if (app.api) {
        // Otherwise, log an error.
        console.error("JS Error: Python 'updateViewSignal' not found on backend object.");
    }

    // If the promptUserToConfirmLocationSignal exists,
    if (app.api && app.api.promptUserToConfirmLocationSignal) {
        // connect to it.
        app.api.promptUserToConfirmLocationSignal.connect((location_info_json, original_hint, original_instruction) => {
            // Parse the location info.
            const location_info = JSON.parse(location_info_json); // <-- Add this parsing line

            // Log that the signal was received.
            console.log("JS: promptUserToConfirmLocationSignal received.", {location_info, original_hint, original_instruction});
            // Update the active task details.
            app.activeTaskDetails = { location_info, original_hint, user_instruction: original_instruction, status: 'awaiting_location_confirmation' };
            // Update the original hint display, located snippet preview, and revised hint input.
            if (app.ui.originalHintDisplay) app.ui.originalHintDisplay.textContent = original_hint;
            if (app.ui.locatedSnippetPreview) app.ui.locatedSnippetPreview.textContent = location_info.snippet;
            if (app.ui.inputRevisedHint) app.ui.inputRevisedHint.value = original_hint;
            // Update the global UI state.
            updateGlobalUIState(true, 'awaiting_location_confirmation');
            // Focus on the revised hint input.
            if (app.ui.inputRevisedHint) app.ui.inputRevisedHint.focus();
        });
    } else if (app.api) {
        // Otherwise, log an error.
        console.error("JS Error: Python 'promptUserToConfirmLocationSignal' not found.");
    }

    // If the showDiffPreviewSignal exists,
    if (app.api && app.api.showDiffPreviewSignal) {
        // connect to it.
        app.api.showDiffPreviewSignal.connect((originalSnippet, editedSnippet/*, contextBefore, contextAfter */) => {
            // Log that the signal was received.
            console.log("JS: showDiffPreviewSignal received.");
            // Get the main diff editor widget configuration.
            const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
            // Get the main diff editor widget name.
            const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';
            // If the main diff editor widget exists,
            if (mainDiffWidgetConfig && app.widgets[mainDiffWidgetName]) {
                // get the editor widget.
                const editorWidget = app.widgets[mainDiffWidgetName];
                // If the editor instance exists and the Monaco editor is available,
                if (editorWidget.instance && typeof monaco !== 'undefined' && typeof monaco.editor !== 'undefined' && editorWidget.instance.getModel) {
                    // set the original and modified values.
                    editorWidget.instance.getModel().original.setValue(originalSnippet || '');
                    editorWidget.instance.getModel().modified.setValue(editedSnippet || '');
                } else {
                     // Otherwise, log a warning and show an alert or a placeholder.
                     console.warn("Monaco editor or its model not available for diff preview. Using placeholder or alert.");
                     if (editorWidget.domElement) editorWidget.domElement.textContent = `(Monaco N/A) Diff: Original vs Edited`;
                     else alert(`DIFF PREVIEW (Editor N/A):\n--- ORIGINAL ---\n${originalSnippet}\n--- EDITED ---\n${editedSnippet}`);
                }
                // Update the proposed snippet in the active task details.
                if (app.activeTaskDetails) app.activeTaskDetails.llmProposedSnippet = editedSnippet;
            } else {
                 // Otherwise, log a warning and show an alert.
                 console.warn(`Diff editor widget not found for '${mainDiffWidgetName}'. Preview via alert.`);
                 alert(`DIFF PREVIEW (Widget N/A):\n--- ORIGINAL ---\n${originalSnippet}\n--- EDITED ---\n${editedSnippet}`);
            }
            // Update the status in the active task details.
            if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_diff_approval';

            // Populate task details in inner loop
            // If the inner loop hint display exists, update its text content.
            if (app.ui.innerLoopHintDisplay && app.activeTaskDetails) {
                app.ui.innerLoopHintDisplay.textContent = app.activeTaskDetails.original_hint || 'N/A';
            }
            // If the inner loop instruction display exists, update its text content.
            if (app.ui.innerLoopInstructionDisplay && app.activeTaskDetails) {
                app.ui.innerLoopInstructionDisplay.textContent = app.activeTaskDetails.user_instruction || 'N/A';
            }
            // LLM info placeholder - can be updated if backend sends this data
            // If the inner loop LLM display exists, update its text content.
            if (app.ui.innerLoopLlmDisplay && app.activeTaskDetails) {
                 // Example: if app.activeTaskDetails.llm_model was available
                 // app.ui.innerLoopLlmDisplay.textContent = app.activeTaskDetails.llm_model || 'N/A';
                 // For now, we leave it as N/A or set a default if no specific info
                 app.ui.innerLoopLlmDisplay.textContent = app.activeTaskDetails.llm_model || 'Default LLM (info not specified)';
            }

            // Update the global UI state.
            updateGlobalUIState(true, 'awaiting_diff_approval');
        });
    } else if (app.api) {
         // Otherwise, log an error.
         console.error("JS Error: Python 'showDiffPreviewSignal' not found.");
    }

    // If the requestClarificationSignal exists,
    if (app.api && app.api.requestClarificationSignal) {
        // connect to it.
        app.api.requestClarificationSignal.connect(() => {
            // Log that the signal was received.
            console.log("JS: requestClarificationSignal received.");
            // Update the status in the active task details.
            if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_clarification';
            // Update the global UI state.
            updateGlobalUIState(true, 'awaiting_clarification');
            // Get the current hint and instruction.
            const currentHint = app.activeTaskDetails ? app.activeTaskDetails.original_hint : '';
            const currentInstruction = app.activeTaskDetails ? app.activeTaskDetails.user_instruction : '';
            // Prompt the user for a new hint.
            const newHint = prompt(`REFINE TASK:\nOriginal Hint: ${currentHint}\nEnter new/revised Hint (or leave blank to keep current):`, currentHint);
            // If the user provided a new hint,
            if (newHint !== null) {
                // prompt for a new instruction.
                const newInstruction = prompt(`Original Instruction: ${currentInstruction}\nEnter new/revised Instruction for this task:`, currentInstruction);
                // If the user provided a new instruction,
                if (newInstruction !== null) {
                    // User provided both hint and instruction
                    if (app.api) {
                        // submit the clarification.
                        app.api.submitClarificationForActiveTask(newHint, newInstruction);
                        // UI remains in 'awaiting_clarification' controlled by updateGlobalUIState, backend will send new signals
                    }
                } else {
                    // User cancelled the instruction prompt
                    // Log that the user cancelled the instruction prompt.
                    console.log("JS: User cancelled instruction prompt during clarification.");
                    // If the API is available, cancel the task.
                    if (app.api) app.api.submitLLMTaskDecision('cancel'); // Cancel the task
                    // Reset UI to idle or let backend dictate next state via updateViewSignal
                    // Update the status in the active task details.
                    if (app.activeTaskDetails) app.activeTaskDetails.status = 'idle'; // Or some other neutral status
                    // Update the global UI state.
                    updateGlobalUIState(false, 'idle'); // Attempt to reset UI
                }
            } else {
                // User cancelled the hint prompt
                // Log that the user cancelled the hint prompt.
                console.log("JS: User cancelled hint prompt during clarification.");
                // If the API is available, cancel the task.
                if (app.api) app.api.submitLLMTaskDecision('cancel'); // Cancel the task
                // Update the status in the active task details.
                if (app.activeTaskDetails) app.activeTaskDetails.status = 'idle';
                // Update the global UI state.
                updateGlobalUIState(false, 'idle');
            }
        });
    } else if (app.api) {
        // Otherwise, log an error.
        console.error("JS Error: Python 'requestClarificationSignal' not found.");
    }

    // If the showErrorSignal exists,
    if (app.api && app.api.showErrorSignal) {
        // connect to it.
        app.api.showErrorSignal.connect((errorMessage) => {
            // Log the error and alert the user.
            console.error("JS: showErrorSignal received:", errorMessage);
            alert("Error from backend: " + errorMessage);
        });
    } else if (app.api) {
        // Otherwise, log an error.
        console.error("JS Error: Python 'showErrorSignal' not found.");
    }

    if (app.api && app.api.showLlmDisabledWarningSignal) {
        app.api.showLlmDisabledWarningSignal.connect(() => {
            console.log("JS: showLlmDisabledWarningSignal received.");
            const warningDiv = document.createElement('div');
            warningDiv.className = 'llm-disabled-warning';
            warningDiv.innerHTML = '<strong>LLM features are not available.</strong> No LLM provider is configured. You can still review and approve the content, but you cannot request new edits.';
            const mainBody = document.getElementById('mainbody-container');
            if (mainBody) {
                mainBody.prepend(warningDiv);
            }
            if (app.ui.btnRequestNewEdit) {
                app.ui.btnRequestNewEdit.style.display = 'none';
            }
        });
    } else if (app.api) {
        console.error("JS Error: Python 'showLlmDisabledWarningSignal' not found.");
    }

    // If the getInitialPayload method exists,
    if (app.api && app.api.getInitialPayload) {
        // log that the QWebChannel is set up and the initial payload is being requested.
        console.log("JS TRACE (5): QWebChannel is set up. About to request initial payload from Python.");
        // get the initial payload.
        app.api.getInitialPayload().then(response_str => {
          // Log that the response was received and is being parsed.
          console.log("JS TRACE (6): Received response from getInitialPayload. About to parse and render.");
          // Log the initial response.
          console.log("JS: Initial response from getInitialPayload (string):", response_str);
          try {
            // Parse the payload.
            const payload = JSON.parse(response_str);
            // If there's an error in the payload,
            if (payload.error) {
                // log the error and alert the user.
                console.error("JS: Error in payload from getInitialPayload:", payload.error, payload.message);
                alert("Error fetching initial data: " + payload.message);
                // Display an error message in the queue status display.
                if(app.ui.queueStatusDisplay) app.ui.queueStatusDisplay.textContent = "Error: Failed to load initial data.";
                // Return.
                return;
            }
            // Set the app config and data.
            app.config = payload.config;
            app.data = payload.data;
            // Log that the initial payload has been parsed and set.
            console.log("JS: Parsed initial payload. Config and Data set.");

            // Render the configurable UI and data.
            renderConfigurableUI();
            renderData();

            // If the startSession method exists,
            if (app.api && app.api.startSession) {
              // log that the session is being started.
              console.log("JS: Attempting to call startSession.");
              // Start the session.
              app.api.startSession();
            } else {
              // Otherwise, log an error.
              console.error("JS Error: Python 'startSession' method not found on backend object (or app.api is null).");
            }
          } catch (e) {
            // If there's an error parsing the JSON, log it and alert the user.
            console.error("JS: Error parsing JSON from getInitialPayload:", e, "Received string:", response_str);
            alert("Critical Error: Could not parse initial data from backend.");
          }
        }).catch(error => {
            // If there's an error calling getInitialPayload, log it and alert the user.
            console.error("JS: Error calling getInitialPayload:", error);
            alert("Critical Error: Could not fetch initial data/string from backend. Please check console.");
        });
    } else if (app.api) {
        // Otherwise, log an error and alert the user.
        console.error("JS Error: Python 'getInitialPayload' method not found on backend object.");
        alert("Critical Error: Backend API is incomplete (missing getInitialPayload). Cannot initialize.");
    }
  });
} else {
    // Otherwise, log an error and alert the user.
    console.error("JS Error: qt object or qt.webChannelTransport not defined. QWebChannel cannot be initialized.");
    alert("Critical Error: Qt WebChannel prerequisites not found. Frontend cannot communicate with Python backend.");
    // If the document is loading,
    if (document.readyState === "loading") {
        // add an event listener for DOMContentLoaded.
        document.addEventListener("DOMContentLoaded", initializeHitlUIElements);
    } else {
        // Otherwise, initialize the HITL UI elements.
        initializeHitlUIElements();
    }
    // Display an error message in the queue status display.
    if(document.getElementById('queue-status-display')) document.getElementById('queue-status-display').textContent = "Error: Frontend-Backend communication disabled.";
}
});

/**
 * Updates the global UI state based on whether the backend is processing a task.
 * @param {boolean} isProcessing - Whether the backend is busy.
 * @param {string|null} activeTaskStatus - The status of the currently active task, if any.
 */
function updateGlobalUIState(isProcessing, activeTaskStatus) {
    console.log(`updateGlobalUIState called with isProcessing: ${isProcessing}, activeTaskStatus: ${activeTaskStatus}`);
    // Set the global flag.
    app.isBackendBusy = isProcessing; // Set the global flag
    // Log the current state.
    console.log("JS: Updating global UI state. isProcessing:", isProcessing, "activeTaskStatus:", activeTaskStatus, "app.isBackendBusy:", app.isBackendBusy);
    // Check if the user opened the edit request area.
    const userOpenedEditRequest = app.ui.editRequestInputArea ? app.ui.editRequestInputArea.classList.contains('user-opened') : false;
    // Show or hide the edit request input area.
    showSection('edit-request-input-area', !isProcessing && userOpenedEditRequest);
    // Show or hide the location confirmation area.
    showSection('location-confirmation-area', isProcessing && activeTaskStatus === 'awaiting_location_confirmation');

    // Check if the inner loop should be shown.
    const showInnerLoop = isProcessing && activeTaskStatus === 'awaiting_diff_approval';
    // Show or hide the inner loop decision area.
    showSection('inner-loop-decision-area', showInnerLoop);

    // If the inner loop is shown,
    if (showInnerLoop) {
        // update the hint, instruction, and LLM displays.
        if (app.ui.innerLoopHintDisplay && app.activeTaskDetails) {
            app.ui.innerLoopHintDisplay.textContent = app.activeTaskDetails.original_hint || 'N/A';
        }
        if (app.ui.innerLoopInstructionDisplay && app.activeTaskDetails) {
            app.ui.innerLoopInstructionDisplay.textContent = app.activeTaskDetails.user_instruction || 'N/A';
        }
        if (app.ui.innerLoopLlmDisplay && app.activeTaskDetails) {
            // Assuming activeTaskDetails might be populated with llm_model by the backend in the future
            app.ui.innerLoopLlmDisplay.textContent = app.activeTaskDetails.llm_model || 'Default LLM (info not specified)';
        }
    }

    // If the loading spinner exists,
    if (app.ui.loadingSpinner) {
        // show or hide it based on whether a task is processing.
        if (isProcessing) {
            app.ui.loadingSpinner.classList.remove('hidden');
        } else {
            app.ui.loadingSpinner.classList.add('hidden');
        }
    }

    // If a task is processing and the status is 'awaiting_clarification',
    if (isProcessing && activeTaskStatus === 'awaiting_clarification') {
        // hide the location confirmation and inner loop decision areas.
        showSection('location-confirmation-area', false);
        showSection('inner-loop-decision-area', false);
    }

    // General flag for when the backend is busy.
    const disableControls = isProcessing && app.api; // General flag for when backend is busy
    // Check if the edit request input area is visible.
    const editRequestInputAreaVisible = app.ui.editRequestInputArea ? !app.ui.editRequestInputArea.classList.contains('hidden') : false;

    // General controls
    // Disable the "Request New Edit" and "Approve and End Session" buttons if the backend is busy.
    if (app.ui.btnRequestNewEdit) app.ui.btnRequestNewEdit.disabled = disableControls;
    if (app.ui.btnApproveEndSession) app.ui.btnApproveEndSession.disabled = disableControls;

    // Controls within the edit request input area
    // These should be disabled if the area isn't visible OR if the backend is processing.
    const disableEditRequestInputs = !editRequestInputAreaVisible || disableControls;

    // Disable the "Add to Queue" button and instruction input if the edit request inputs are disabled.
    if (app.ui.btnAddtoQueue) app.ui.btnAddtoQueue.disabled = disableEditRequestInputs;
    if (app.ui.inputInstruction) app.ui.inputInstruction.disabled = disableEditRequestInputs;

    // Special handling for inputHint and btnUseSelectionContext
    // If the input hint exists,
    if (app.ui.inputHint) {
        // disable it if the edit request inputs are disabled or there is an active selection.
        // Disabled if: edit area hidden, OR backend busy, OR a selection context is active
        app.ui.inputHint.disabled = disableEditRequestInputs || (app.activeSelectionDetails != null);
    }

    // If the "Use Selection as Context" button exists,
    if (app.ui.btnUseSelectionContext) {
        // disable it if the edit request inputs are disabled.
        // Disabled if: edit area hidden, OR backend busy.
        // Enabling based on actual editor selection will be handled by onDidChangeCursorSelection (Step 2)
        // For now, if it *would* be enabled by those conditions, ensure it's not overridden here.
        app.ui.btnUseSelectionContext.disabled = disableEditRequestInputs;
    }

    // Always call this to ensure button text/status message is up-to-date
    // Update the selection context status.
    updateSelectionContextStatus();

    // Get all the action buttons in the header, sidebar, and footer.
    const configActionButtons = document.querySelectorAll(
        '#header-container .action-button, #sidebar-container .action-button, #footer-container .action-button'
    );
    // For each button,
    configActionButtons.forEach(button => {
        // check if it's within an active HITL section.
        const isWithinActiveHitlSection = button.closest('#location-confirmation-area') ||
                                          button.closest('#inner-loop-decision-area') ||
                                          button.closest('#edit-request-input-area');
        // If it's not, disable it if the backend is busy.
        if (!isWithinActiveHitlSection) {
            button.disabled = disableControls;
        }
    });
}

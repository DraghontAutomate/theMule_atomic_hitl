console.log("frontend.js starting");
// Configure the AMD loader for Monaco editor.
// This tells the loader where to find the editor's source files.
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs' } });

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
 * Creates input fields, labels, buttons, and potentially the Monaco diff editor.
 * Attempts to preserve the main Monaco diff editor instance if it exists.
 */
function renderConfigurableUI() {
  console.log("JS: renderConfigurableUI called. Current app.config:", app.config);
  const configurableContainers = ['header-container', 'sidebar-container', 'mainbody-container', 'footer-container'];
  let mainDiffEditorElement = null;
  const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
  const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';

  // Preserve existing Monaco editor instance if it's already in the DOM and valid
  if (app.widgets[mainDiffWidgetName] && app.widgets[mainDiffWidgetName].instance && typeof app.widgets[mainDiffWidgetName].instance.getDomNode === 'function') {
      const mainBody = document.getElementById('mainbody-container');
      const editorDomNode = app.widgets[mainDiffWidgetName].instance.getDomNode();
      if (mainBody && editorDomNode && mainBody.contains(editorDomNode)) {
          mainDiffEditorElement = editorDomNode.parentElement;
      }
  }

  configurableContainers.forEach(id => {
    const container = document.getElementById(id);
    if (container) {
        if (id === 'mainbody-container' && mainDiffEditorElement) {
            Array.from(container.childNodes).forEach(child => {
                if (child !== mainDiffEditorElement && !mainDiffEditorElement.contains(child) &&
                    child.id !== 'location-confirmation-area' && child.id !== 'inner-loop-decision-area') {
                    container.removeChild(child);
                }
            });
        } else if (id !== 'mainbody-container' || (id === 'mainbody-container' && !mainDiffEditorElement) ) {
             container.innerHTML = ''; // Clear if not mainbody, or if mainbody without preserved editor
        }
    } else {
        console.warn(`renderConfigurableUI: Container ID '${id}' not found in HTML.`);
    }
  });

  const oldWidgets = app.widgets; // Keep a reference if needed for complex preservation, otherwise reset
  app.widgets = {};

  if (app.config.fields) {
    app.config.fields.forEach(field => {
        const container = document.getElementById(`${field.placement}-container`);
        if (!container && field.placement !== 'none') {
            console.warn(`Container for placement '${field.placement}-container' not found for field '${field.name}'.`);
            return;
        }

        if (field.type === 'diff-editor') {
            // Attempt to reuse existing editor instance if it matches and was preserved
            if (field.name === mainDiffWidgetName && mainDiffEditorElement && oldWidgets[mainDiffWidgetName]?.instance?.getDomNode) {
                app.widgets[field.name] = oldWidgets[mainDiffWidgetName]; // Relink preserved widget
                console.log(`JS: Re-linked preserved Monaco editor for '${field.name}'.`);

                // Add selection change listener for the "Use Selection as Context" button
                // Ensure this is the main editor expected to provide context
                const editorInstance = app.widgets[field.name].instance;
                if (editorInstance && editorInstance.getModifiedEditor) {
                    const modifiedEditor = editorInstance.getModifiedEditor();
                    // It's possible the listener already exists if the editor instance is truly preserved.
                    // Monaco editor might handle duplicate event subscriptions gracefully, or one might
                    // consider storing a flag or using disposable event listeners if issues arise.
                    // For now, re-adding is simpler if Monaco handles it.
                    modifiedEditor.onDidChangeCursorSelection(() => {
                        if (app.ui.btnUseSelectionContext) {
                            const selection = modifiedEditor.getSelection();
                            const hasSelection = selection && !selection.isEmpty();
                            const editRequestAreaVisible = app.ui.editRequestInputArea ? !app.ui.editRequestInputArea.classList.contains('hidden') : false;

                            if (editRequestAreaVisible && !app.isBackendBusy) {
                                if (app.activeSelectionDetails) {
                                    // If a context is already active, the button is for "Clear".
                                    app.ui.btnUseSelectionContext.disabled = false;
                                } else {
                                    // No active context, button is for "Use Selection". Enable only if there's text selected.
                                    app.ui.btnUseSelectionContext.disabled = !hasSelection;
                                }
                            } else {
                                // If edit area not visible or backend is busy, button should be disabled.
                                app.ui.btnUseSelectionContext.disabled = true;
                            }
                        }
                    });
                }
            } else {
                const editorDiv = document.createElement('div');
                editorDiv.id = `editor-${field.name}`;
                if (field.placement === 'mainbody') {
                    // Use class for styling now, defined in index.html
                    editorDiv.className = 'editor-container-style';
                    // Clear inline styles that might conflict
                    editorDiv.style.height = "";
                    editorDiv.style.width = "";
                    editorDiv.style.border = "";
                } else {
                    editorDiv.style.height = "200px"; // Keep for non-mainbody editors if any
                    editorDiv.style.minWidth = "100px";
                    editorDiv.style.border = "1px solid #dee2e6"; // Use new border color
                }
                if (container) container.appendChild(editorDiv);

                if (typeof monaco !== 'undefined' && typeof monaco.editor !== 'undefined') {
                    try {
                        const editor = monaco.editor.createDiffEditor(editorDiv, {
                            automaticLayout: true,
                            originalEditable: field.originalEditable === true,
                            readOnly: field.readOnly === true,
                            lineNumbers: 'on' // Added line numbers
                        });
                        editor.setModel({
                            original: monaco.editor.createModel('', field.language || 'text/plain'),
                            modified: monaco.editor.createModel('', field.language || 'text/plain')
                        });
                        app.widgets[field.name] = { type: 'diff-editor', instance: editor, config: field };
                        console.log(`JS: Created new Monaco editor for '${field.name}'.`);

                        // Add selection change listener for the "Use Selection as Context" button
                        if (field.name === mainDiffWidgetName) { // Assuming this is the main editor
                            const modifiedEditor = editor.getModifiedEditor();
                            modifiedEditor.onDidChangeCursorSelection(() => {
                                if (app.ui.btnUseSelectionContext) {
                                    const selection = modifiedEditor.getSelection();
                                    const hasSelection = selection && !selection.isEmpty();
                                    const editRequestAreaVisible = app.ui.editRequestInputArea ? !app.ui.editRequestInputArea.classList.contains('hidden') : false;

                                    if (editRequestAreaVisible && !app.isBackendBusy) {
                                         if (app.activeSelectionDetails) {
                                            // If a context is already active, the button is for "Clear".
                                            // It's enabled unless the overall conditions (area visible, not busy) are false (handled by updateGlobalUIState).
                                            app.ui.btnUseSelectionContext.disabled = false;
                                        } else {
                                            // No active context, button is for "Use Selection". Enable only if there's text selected.
                                            app.ui.btnUseSelectionContext.disabled = !hasSelection;
                                        }
                                    } else {
                                        // If edit area not visible or backend is busy, button should be disabled.
                                        // This is also set by updateGlobalUIState, but good to be explicit here too.
                                        app.ui.btnUseSelectionContext.disabled = true;
                                    }
                                }
                            });
                        }
                    } catch (e) {
                        console.error("Error creating Monaco editor for field:", field.name, e);
                        editorDiv.textContent = `Error creating Monaco editor for '${field.name}'. See console.`;
                        app.widgets[field.name] = { type: 'diff-editor', instance: null, config: field, domElement: editorDiv };
                    }
                } else {
                    console.warn("Monaco editor API not available. Diff editor UI will be a placeholder for field:", field.name);
                    editorDiv.textContent = `Monaco editor for '${field.name}' could not be loaded.`;
                    app.widgets[field.name] = { type: 'diff-editor', instance: null, config: field, domElement: editorDiv };
                }
            }
        } else if (field.placement !== 'none') {
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
          } else {
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
          if (!app.api) {
            alert("Backend API not available. Action cannot be performed.");
            console.error("PerformAction: app.api is not available.");
            return;
          }
          const payload = getPayloadFromUI(action);
          app.api.performAction(action.name, payload);
        };
        container.appendChild(button);
    });
  }
}

/**
 * Populates UI elements with data from `app.data`.
 */
function renderData() {
  console.log("JS: renderData called. Current app.data:", app.data);
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    const fieldConfig = widget.config;

    if (widget.type === 'diff-editor') {
      const originalValue = app.data[fieldConfig.originalDataField] || '';
      const modifiedValue = app.data[fieldConfig.modifiedDataField] || '';
      if (widget.instance && widget.instance.getModel) { // Monaco editor instance exists
          widget.instance.getModel().original.setValue(originalValue);
          widget.instance.getModel().modified.setValue(modifiedValue);
      } else if (widget.domElement) { // Placeholder div exists
          widget.domElement.textContent = `(Monaco N/A) Original: ${originalValue}\nModified: ${modifiedValue}`;
      }
    } else if (widget.type === 'field') {
      const value = app.data[fieldConfig.name] || '';
      if (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA') {
        widget.element.value = value;
      } else {
        widget.element.textContent = value;
      }
    }
  }

  const mainDiffConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
  if (mainDiffConfig && app.widgets[mainDiffConfig.name]) {
      const editorWidget = app.widgets[mainDiffConfig.name];
      const currentModifiedContent = app.data[mainDiffConfig.modifiedDataField] || '';
      // The original content for diff should ideally come from a snapshot or the originalDataField
      const currentOriginalContent = app.data[mainDiffConfig.originalDataField] || currentModifiedContent;

      if (!app.activeTaskDetails || !app.activeTaskDetails.status ||
          (app.activeTaskDetails.status !== 'awaiting_diff_approval' &&
           app.activeTaskDetails.status !== 'awaiting_location_confirmation')) {
          if (editorWidget.instance && editorWidget.instance.getModel) {
              // When idle, show current state or make original and modified same
              editorWidget.instance.getModel().original.setValue(currentOriginalContent);
              editorWidget.instance.getModel().modified.setValue(currentModifiedContent);
          } else if (editorWidget.domElement) {
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
  const payload = {};
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    if (widget.type === 'field' && (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA')) {
      payload[widget.config.name] = widget.element.value;
    }
  }
  if (action.editorName && app.widgets[action.editorName] && app.widgets[action.editorName].type === 'diff-editor') {
    const editorWidget = app.widgets[action.editorName];
    if (editorWidget.instance && editorWidget.instance.getModifiedEditor) {
        payload[editorWidget.config.modifiedDataField] = editorWidget.instance.getModifiedEditor().getValue();
    } else {
        payload[editorWidget.config.modifiedDataField] = app.data[editorWidget.config.modifiedDataField] || '';
        console.warn(`Monaco editor '${action.editorName}' not available, sending current data for field '${editorWidget.config.modifiedDataField}'.`);
    }
  }
  return payload;
}

/**
 * Initializes references to static HITL UI elements and sets up their event listeners.
 */
function initializeHitlUIElements() {
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


    showSection('edit-request-input-area', false);
    showSection('location-confirmation-area', false);
    showSection('inner-loop-decision-area', false);
    updateSelectionContextStatus(); // Initial call

    if (app.ui.btnApproveEndSession) {
        app.ui.btnApproveEndSession.onclick = () => {
            if (confirm("Are you sure you want to approve and end the session?")) {
                if (app.api) app.api.terminateSession();
                else console.error("TerminateSession: app.api not available.");
            }
        };
    }
    if (app.ui.btnRequestNewEdit) {
        app.ui.btnRequestNewEdit.onclick = () => {
            const editArea = app.ui.editRequestInputArea;
            if (editArea) {
                const isProcessing = app.ui.queueStatusDisplay ? app.ui.queueStatusDisplay.textContent.includes("Processing") : false;
                if (!isProcessing || !app.api) {
                    const currentlyOpen = !editArea.classList.contains('hidden');
                    showSection(editArea.id, !currentlyOpen);
                    if (!currentlyOpen) editArea.classList.add('user-opened');
                    else editArea.classList.remove('user-opened');
                    if (!editArea.classList.contains('hidden') && app.ui.inputHint) app.ui.inputHint.focus();
                } else {
                    alert("Cannot request new edit while another task is processing.");
                }
            }
             if (editArea && !editArea.classList.contains('hidden')) {
                 updateGlobalUIState(false, null);
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
                let requestPayload = {
                    instruction: instruction,
                    type: '',
                    selection_details: null,
                    hint: null
                };

                if (app.activeSelectionDetails) {
                    requestPayload.type = 'selection_specific';
                    requestPayload.selection_details = app.activeSelectionDetails;
                    console.log("JS: Submitting selection_specific request", requestPayload);
                } else {
                    if (!hint) { // Ensure hint is provided if not using selection
                        alert("Please provide 'Where to Edit?' (Hint) or use 'Use Editor Selection as Context'.");
                        return;
                    }
                    requestPayload.type = 'hint_based';
                    requestPayload.hint = hint;
                    console.log("JS: Submitting hint_based request", requestPayload);
                }

                app.api.submitEditRequest(JSON.stringify(requestPayload)); // Send as JSON string

                // Reset UI
                if (app.ui.inputHint) app.ui.inputHint.value = '';
                if (app.ui.inputInstruction) app.ui.inputInstruction.value = '';
                app.activeSelectionDetails = null;
                updateSelectionContextStatus(); // Update button and status text
                if (app.ui.inputHint) app.ui.inputHint.disabled = false;


                if (app.ui.editRequestInputArea) {
                     app.ui.editRequestInputArea.classList.remove('user-opened');
                     showSection('edit-request-input-area', false);
                }
            } else {
                alert("Backend not available to submit edit request.");
            }
        };
    }

    if (app.ui.btnUseSelectionContext) {
        app.ui.btnUseSelectionContext.onclick = () => {
            if (app.activeSelectionDetails) {
                // Clear current selection context
                app.activeSelectionDetails = null;
                if (app.ui.inputHint) app.ui.inputHint.disabled = false;
                updateSelectionContextStatus();
            } else {
                // Capture new selection context
                const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
                const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';
                const editorWidget = app.widgets[mainDiffWidgetName];

                if (editorWidget && editorWidget.instance && editorWidget.instance.getModifiedEditor) {
                    const modifiedEditor = editorWidget.instance.getModifiedEditor();
                    const selection = modifiedEditor.getSelection(); // This is a Monaco ISelection

                    if (selection && !selection.isEmpty()) {
                        const selectedText = modifiedEditor.getModel().getValueInRange(selection);
                        app.activeSelectionDetails = {
                            text: selectedText,
                            startLineNumber: selection.startLineNumber,
                            startColumn: selection.startColumn,
                            endLineNumber: selection.endLineNumber,
                            endColumn: selection.endColumn
                        };
                        if (app.ui.inputHint) {
                            app.ui.inputHint.value = `Selection: Lines ${selection.startLineNumber}-${selection.endLineNumber}`;
                            app.ui.inputHint.disabled = true;
                        }
                        updateSelectionContextStatus();
                    } else {
                        alert("No text selected in the editor's modified view.");
                    }
                } else {
                    alert("Editor not available to get selection.");
                }
            }
        };
    }

    if (app.ui.btnConfirmLocation) {
        app.ui.btnConfirmLocation.onclick = () => {
            if (app.api && app.activeTaskDetails && app.activeTaskDetails.location_info) {
                app.api.submitConfirmedLocationAndInstruction(app.activeTaskDetails.location_info, app.activeTaskDetails.user_instruction);
            } else if (!app.api) console.error("ConfirmLocation: app.api not available.");
        };
    }
    if (app.ui.btnCancelLocationStage) {
        app.ui.btnCancelLocationStage.onclick = () => {
            if (app.api) app.api.submitLLMTaskDecision('cancel');
            else console.error("CancelLocationStage: app.api not available.");
        };
    }
    if (app.ui.btnApproveThisEdit) {
        app.ui.btnApproveThisEdit.onclick = () => {
            let contentToApprove = '';
            const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
            const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';
            if (mainDiffWidgetConfig && app.widgets[mainDiffWidgetName] && app.widgets[mainDiffWidgetName].instance && app.widgets[mainDiffWidgetName].instance.getModifiedEditor) {
                contentToApprove = app.widgets[mainDiffWidgetName].instance.getModifiedEditor().getValue();
            } else if (app.activeTaskDetails && app.activeTaskDetails.llmProposedSnippet !== undefined) {
                contentToApprove = app.activeTaskDetails.llmProposedSnippet;
            }
            if (app.api) app.api.submitLLMTaskDecisionWithEdit('approve', contentToApprove);
            else console.error("ApproveThisEdit: app.api not available.");
        };
    }
    if (app.ui.btnRefineThisEdit) {
        app.ui.btnRefineThisEdit.onclick = () => {
            if (app.api) app.api.submitLLMTaskDecision('reject');
            else console.error("RefineThisEdit: app.api not available.");
        };
    }
    if (app.ui.btnDiscardThisEdit) {
        app.ui.btnDiscardThisEdit.onclick = () => {
            if (app.api) app.api.submitLLMTaskDecision('cancel');
            else console.error("DiscardThisEdit: app.api not available.");
        };
    }
}

function updateSelectionContextStatus() {
    if (!app.ui.btnUseSelectionContext || !app.ui.selectionContextStatus) return;

    if (app.activeSelectionDetails) {
        app.ui.btnUseSelectionContext.textContent = 'Clear Editor Selection Context';
        app.ui.btnUseSelectionContext.classList.add('danger'); // Make it look like a "clear" or "cancel" action
        let displayText = app.activeSelectionDetails.text;
        if (displayText.length > 50) {
            displayText = displayText.substring(0, 47) + "...";
        }
        app.ui.selectionContextStatus.textContent = `Context: "${displayText}" (Lines ${app.activeSelectionDetails.startLineNumber}-${app.activeSelectionDetails.endLineNumber})`;
        if (app.ui.inputHint) app.ui.inputHint.disabled = true;
    } else {
        app.ui.btnUseSelectionContext.textContent = 'Use Editor Selection as Context';
        app.ui.btnUseSelectionContext.classList.remove('danger');
        app.ui.selectionContextStatus.textContent = '';
        if (app.ui.inputHint) {
            // Only enable if the edit request area is actually open and not processing
             const editAreaOpenAndNotProcessing = app.ui.editRequestInputArea &&
                                             !app.ui.editRequestInputArea.classList.contains('hidden') &&
                                             (!app.activeTaskDetails || !app.activeTaskDetails.status || app.activeTaskDetails.status === 'idle'); // Simplified check
            if(editAreaOpenAndNotProcessing) app.ui.inputHint.disabled = false;
        }
    }
    // The general enabled/disabled state of btnUseSelectionContext itself
    // will be handled by updateGlobalUIState and editor selection change events.
}

// --- Main Execution Block ---
require(['vs/editor/editor.main'], () => { // Monaco loader uncommented
  console.log("JS: Monaco editor loaded via require. Checking for qt object before QWebChannel setup...");
  if (typeof qt !== 'undefined' && qt.webChannelTransport) {
    console.log("JS: qt object and qt.webChannelTransport found. Proceeding with QWebChannel.");
    new QWebChannel(qt.webChannelTransport, channel => {
      if (!channel.objects || !channel.objects.backend) {
          console.error("ERROR: 'backend' object not found in QWebChannel. Ensure it's registered in Python and QWebChannel is working.");
          alert("Critical Error: Could not connect to Python backend. Frontend functionality will be limited.");
          app.api = null;
          initializeHitlUIElements();
          if(app.ui.queueStatusDisplay) app.ui.queueStatusDisplay.textContent = "Error: Backend not available.";
          return;
      }
      app.api = channel.objects.backend;
      console.log("JS: app.api (backend object) received:", app.api);
      initializeHitlUIElements();

      console.log("JS: Attempting to connect signals...");

      if (app.api && app.api.updateViewSignal) {
          app.api.updateViewSignal.connect((data, config, queue_info) => {
              console.log("JS: updateViewSignal received (raw data):", data, config, queue_info);
            app.data = data;
            app.config = config;
            if (Object.keys(app.widgets).length === 0 || JSON.stringify(app.config) !== JSON.stringify(config)) { // Basic check
                 renderConfigurableUI();
            }
            renderData();
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
            updateGlobalUIState(queue_info.is_processing, queue_info.active_task_status);
        });
    } else if (app.api) {
        console.error("JS Error: Python 'updateViewSignal' not found on backend object.");
    }

    if (app.api && app.api.promptUserToConfirmLocationSignal) {
        app.api.promptUserToConfirmLocationSignal.connect((location_info, original_hint, original_instruction) => {
            console.log("JS: promptUserToConfirmLocationSignal received.", {location_info, original_hint, original_instruction});
            app.activeTaskDetails = { location_info, original_hint, user_instruction: original_instruction, status: 'awaiting_location_confirmation' };
            if (app.ui.originalHintDisplay) app.ui.originalHintDisplay.textContent = original_hint;
            if (app.ui.locatedSnippetPreview) app.ui.locatedSnippetPreview.textContent = location_info.snippet;
            if (app.ui.inputRevisedHint) app.ui.inputRevisedHint.value = original_hint;
            updateGlobalUIState(true, 'awaiting_location_confirmation');
            if (app.ui.inputRevisedHint) app.ui.inputRevisedHint.focus();
        });
    } else if (app.api) {
        console.error("JS Error: Python 'promptUserToConfirmLocationSignal' not found.");
    }

    if (app.api && app.api.showDiffPreviewSignal) {
        app.api.showDiffPreviewSignal.connect((originalSnippet, editedSnippet/*, contextBefore, contextAfter */) => {
            console.log("JS: showDiffPreviewSignal received.");
            const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
            const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';
            if (mainDiffWidgetConfig && app.widgets[mainDiffWidgetName]) {
                const editorWidget = app.widgets[mainDiffWidgetName];
                if (editorWidget.instance && typeof monaco !== 'undefined' && typeof monaco.editor !== 'undefined' && editorWidget.instance.getModel) {
                    editorWidget.instance.getModel().original.setValue(originalSnippet || '');
                    editorWidget.instance.getModel().modified.setValue(editedSnippet || '');
                } else {
                     console.warn("Monaco editor or its model not available for diff preview. Using placeholder or alert.");
                     if (editorWidget.domElement) editorWidget.domElement.textContent = `(Monaco N/A) Diff: Original vs Edited`;
                     else alert(`DIFF PREVIEW (Editor N/A):\n--- ORIGINAL ---\n${originalSnippet}\n--- EDITED ---\n${editedSnippet}`);
                }
                if (app.activeTaskDetails) app.activeTaskDetails.llmProposedSnippet = editedSnippet;
            } else {
                 console.warn(`Diff editor widget not found for '${mainDiffWidgetName}'. Preview via alert.`);
                 alert(`DIFF PREVIEW (Widget N/A):\n--- ORIGINAL ---\n${originalSnippet}\n--- EDITED ---\n${editedSnippet}`);
            }
            if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_diff_approval';

            // Populate task details in inner loop
            if (app.ui.innerLoopHintDisplay && app.activeTaskDetails) {
                app.ui.innerLoopHintDisplay.textContent = app.activeTaskDetails.original_hint || 'N/A';
            }
            if (app.ui.innerLoopInstructionDisplay && app.activeTaskDetails) {
                app.ui.innerLoopInstructionDisplay.textContent = app.activeTaskDetails.user_instruction || 'N/A';
            }
            // LLM info placeholder - can be updated if backend sends this data
            if (app.ui.innerLoopLlmDisplay && app.activeTaskDetails) {
                 // Example: if app.activeTaskDetails.llm_model was available
                 // app.ui.innerLoopLlmDisplay.textContent = app.activeTaskDetails.llm_model || 'N/A';
                 // For now, we leave it as N/A or set a default if no specific info
                 app.ui.innerLoopLlmDisplay.textContent = app.activeTaskDetails.llm_model || 'Default LLM (info not specified)';
            }

            updateGlobalUIState(true, 'awaiting_diff_approval');
        });
    } else if (app.api) {
         console.error("JS Error: Python 'showDiffPreviewSignal' not found.");
    }

    if (app.api && app.api.requestClarificationSignal) {
        app.api.requestClarificationSignal.connect(() => {
            console.log("JS: requestClarificationSignal received.");
            if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_clarification';
            updateGlobalUIState(true, 'awaiting_clarification');
            const currentHint = app.activeTaskDetails ? app.activeTaskDetails.original_hint : '';
            const currentInstruction = app.activeTaskDetails ? app.activeTaskDetails.user_instruction : '';
            const newHint = prompt(`REFINE TASK:\nOriginal Hint: ${currentHint}\nEnter new/revised Hint (or leave blank to keep current):`, currentHint);
            if (newHint !== null) {
                const newInstruction = prompt(`Original Instruction: ${currentInstruction}\nEnter new/revised Instruction for this task:`, currentInstruction);
                if (newInstruction !== null) {
                    // User provided both hint and instruction
                    if (app.api) {
                        app.api.submitClarificationForActiveTask(newHint, newInstruction);
                        // UI remains in 'awaiting_clarification' controlled by updateGlobalUIState, backend will send new signals
                    }
                } else {
                    // User cancelled the instruction prompt
                    console.log("JS: User cancelled instruction prompt during clarification.");
                    if (app.api) app.api.submitLLMTaskDecision('cancel'); // Cancel the task
                    // Reset UI to idle or let backend dictate next state via updateViewSignal
                    if (app.activeTaskDetails) app.activeTaskDetails.status = 'idle'; // Or some other neutral status
                    updateGlobalUIState(false, 'idle'); // Attempt to reset UI
                }
            } else {
                // User cancelled the hint prompt
                console.log("JS: User cancelled hint prompt during clarification.");
                if (app.api) app.api.submitLLMTaskDecision('cancel'); // Cancel the task
                if (app.activeTaskDetails) app.activeTaskDetails.status = 'idle';
                updateGlobalUIState(false, 'idle');
            }
        });
    } else if (app.api) {
        console.error("JS Error: Python 'requestClarificationSignal' not found.");
    }

    if (app.api && app.api.showErrorSignal) {
        app.api.showErrorSignal.connect((errorMessage) => {
            console.error("JS: showErrorSignal received:", errorMessage);
            alert("Error from backend: " + errorMessage);
        });
    } else if (app.api) {
        console.error("JS Error: Python 'showErrorSignal' not found.");
    }

    if (app.api && app.api.getInitialPayload) {
        app.api.getInitialPayload().then(response_str => {
          console.log("JS: Initial response from getInitialPayload (string):", response_str);
          try {
            const payload = JSON.parse(response_str);
            if (payload.error) {
                console.error("JS: Error in payload from getInitialPayload:", payload.error, payload.message);
                alert("Error fetching initial data: " + payload.message);
                if(app.ui.queueStatusDisplay) app.ui.queueStatusDisplay.textContent = "Error: Failed to load initial data.";
                return;
            }
            app.config = payload.config;
            app.data = payload.data;
            console.log("JS: Parsed initial payload. Config and Data set.");

            renderConfigurableUI();
            renderData();

            if (app.api && app.api.startSession) {
              console.log("JS: Attempting to call startSession.");
              app.api.startSession();
            } else {
              console.error("JS Error: Python 'startSession' method not found on backend object (or app.api is null).");
            }
          } catch (e) {
            console.error("JS: Error parsing JSON from getInitialPayload:", e, "Received string:", response_str);
            alert("Critical Error: Could not parse initial data from backend.");
          }
        }).catch(error => {
            console.error("JS: Error calling getInitialPayload:", error);
            alert("Critical Error: Could not fetch initial data/string from backend. Please check console.");
        });
    } else if (app.api) {
        console.error("JS Error: Python 'getInitialPayload' method not found on backend object.");
        alert("Critical Error: Backend API is incomplete (missing getInitialPayload). Cannot initialize.");
    }
  });
} else {
    console.error("JS Error: qt object or qt.webChannelTransport not defined. QWebChannel cannot be initialized.");
    alert("Critical Error: Qt WebChannel prerequisites not found. Frontend cannot communicate with Python backend.");
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeHitlUIElements);
    } else {
        initializeHitlUIElements();
    }
    if(document.getElementById('queue-status-display')) document.getElementById('queue-status-display').textContent = "Error: Frontend-Backend communication disabled.";
}
}); // Monaco loader uncommented

function updateGlobalUIState(isProcessing, activeTaskStatus) {
    app.isBackendBusy = isProcessing; // Set the global flag
    console.log("JS: Updating global UI state. isProcessing:", isProcessing, "activeTaskStatus:", activeTaskStatus, "app.isBackendBusy:", app.isBackendBusy);
    const userOpenedEditRequest = app.ui.editRequestInputArea ? app.ui.editRequestInputArea.classList.contains('user-opened') : false;
    showSection('edit-request-input-area', !isProcessing && userOpenedEditRequest);
    showSection('location-confirmation-area', isProcessing && activeTaskStatus === 'awaiting_location_confirmation');

    const showInnerLoop = isProcessing && activeTaskStatus === 'awaiting_diff_approval';
    showSection('inner-loop-decision-area', showInnerLoop);

    if (showInnerLoop) {
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

    if (app.ui.loadingSpinner) {
        if (isProcessing) {
            app.ui.loadingSpinner.classList.remove('hidden');
        } else {
            app.ui.loadingSpinner.classList.add('hidden');
        }
    }

    if (isProcessing && activeTaskStatus === 'awaiting_clarification') {
        showSection('location-confirmation-area', false);
        showSection('inner-loop-decision-area', false);
    }

    const disableControls = isProcessing && app.api; // General flag for when backend is busy
    const editRequestInputAreaVisible = app.ui.editRequestInputArea ? !app.ui.editRequestInputArea.classList.contains('hidden') : false;

    // General controls
    if (app.ui.btnRequestNewEdit) app.ui.btnRequestNewEdit.disabled = disableControls;
    if (app.ui.btnApproveEndSession) app.ui.btnApproveEndSession.disabled = disableControls;

    // Controls within the edit request input area
    // These should be disabled if the area isn't visible OR if the backend is processing.
    const disableEditRequestInputs = !editRequestInputAreaVisible || disableControls;

    if (app.ui.btnAddtoQueue) app.ui.btnAddtoQueue.disabled = disableEditRequestInputs;
    if (app.ui.inputInstruction) app.ui.inputInstruction.disabled = disableEditRequestInputs;

    // Special handling for inputHint and btnUseSelectionContext
    if (app.ui.inputHint) {
        // Disabled if: edit area hidden, OR backend busy, OR a selection context is active
        app.ui.inputHint.disabled = disableEditRequestInputs || (app.activeSelectionDetails != null);
    }

    if (app.ui.btnUseSelectionContext) {
        // Disabled if: edit area hidden, OR backend busy.
        // Enabling based on actual editor selection will be handled by onDidChangeCursorSelection (Step 2)
        // For now, if it *would* be enabled by those conditions, ensure it's not overridden here.
        app.ui.btnUseSelectionContext.disabled = disableEditRequestInputs;
    }

    // Always call this to ensure button text/status message is up-to-date
    updateSelectionContextStatus();

    const configActionButtons = document.querySelectorAll(
        '#header-container .action-button, #sidebar-container .action-button, #footer-container .action-button'
    );
    configActionButtons.forEach(button => {
        const isWithinActiveHitlSection = button.closest('#location-confirmation-area') ||
                                          button.closest('#inner-loop-decision-area') ||
                                          button.closest('#edit-request-input-area');
        if (!isWithinActiveHitlSection) {
            button.disabled = disableControls;
        }
    });
}

console.log("frontend.js starting");
// Configure the AMD loader for Monaco editor.
// This tells the loader where to find the editor's source files.
// require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs' } }); // Commented out for now

let app = {
  config: {},
  data: {},
  widgets: {},
  api: null,
  ui: {},
  activeTaskDetails: {}
};

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

function renderConfigurableUI() {
  const configurableContainers = ['header-container', 'sidebar-container', 'mainbody-container', 'footer-container'];
  let mainDiffEditorElement = null;
  const mainDiffWidgetConfig = app.config.fields?.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
  const mainDiffWidgetName = mainDiffWidgetConfig?.name || 'main_diff';

  if (app.widgets[mainDiffWidgetName] && app.widgets[mainDiffWidgetName].instance) {
      const mainBody = document.getElementById('mainbody-container');
      // Check if getDomNode method exists, as instance might not be a Monaco editor if Monaco failed to load
      const editorDomNode = app.widgets[mainDiffWidgetName].instance.getDomNode ? app.widgets[mainDiffWidgetName].instance.getDomNode() : null;
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
        } else if (id !== 'mainbody-container') { // Also clear mainbody if no editor was preserved
            container.innerHTML = '';
        } else if (id === 'mainbody-container' && !mainDiffEditorElement) { // Explicitly clear mainbody if no editor preserved
             container.innerHTML = '';
        }
    }
  });

  app.widgets = {};

  if (app.config.fields) {
    app.config.fields.forEach(field => {
        const container = document.getElementById(`${field.placement}-container`);
        if (!container && field.placement !== 'none') {
            console.warn(`Container for placement '${field.placement}-container' not found for field '${field.name}'.`);
            return;
        }

        if (field.type === 'diff-editor') {
            if (field.name === mainDiffWidgetName && mainDiffEditorElement && app.widgets[mainDiffWidgetName]?.instance?.getDomNode) { // Check if instance is a Monaco editor
                app.widgets[field.name] = { type: 'diff-editor', instance: app.widgets[mainDiffWidgetName].instance, config: field };
            } else {
                const editorDiv = document.createElement('div');
                editorDiv.id = `editor-${field.name}`; // Give a unique ID for potential targeting
                if (field.placement === 'mainbody') {
                    editorDiv.style.height = "calc(100% - 120px)";
                    editorDiv.style.width = "100%";
                    editorDiv.style.border = "1px solid #ccc";
                } else {
                    editorDiv.style.height = "200px";
                    editorDiv.style.minWidth = "100px";
                }
                if (container) container.appendChild(editorDiv);

                if (typeof monaco !== 'undefined' && typeof monaco.editor !== 'undefined') {
                    const editor = monaco.editor.createDiffEditor(editorDiv, {
                        automaticLayout: true,
                        originalEditable: field.originalEditable === true,
                        readOnly: field.readOnly === true
                    });
                    editor.setModel({
                        original: monaco.editor.createModel('', field.language || 'text/plain'),
                        modified: monaco.editor.createModel('', field.language || 'text/plain')
                    });
                    app.widgets[field.name] = { type: 'diff-editor', instance: editor, config: field };
                } else {
                    console.warn("Monaco editor not available. Diff editor UI will not be created for field:", field.name);
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
          const payload = getPayloadFromUI(action);
          if (app.api) app.api.performAction(action.name, payload);
        };
        container.appendChild(button);
    });
  }
}

function renderData() {
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    const fieldConfig = widget.config;

    if (widget.type === 'diff-editor') {
      const originalValue = app.data[fieldConfig.originalDataField] || '';
      const modifiedValue = app.data[fieldConfig.modifiedDataField] || '';
      if (widget.instance && widget.instance.getModel) {
          widget.instance.getModel().original.setValue(originalValue);
          widget.instance.getModel().modified.setValue(modifiedValue);
      } else if (widget.domElement) {
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
      const currentContent = app.data[mainDiffConfig.modifiedDataField] || '';
      if (!app.activeTaskDetails || !app.activeTaskDetails.status ||
          (app.activeTaskDetails.status !== 'awaiting_diff_approval' &&
           app.activeTaskDetails.status !== 'awaiting_location_confirmation' &&
           app.activeTaskDetails.status !== 'locating_snippet')) {
          if (editorWidget.instance && editorWidget.instance.getModel) {
              editorWidget.instance.getModel().original.setValue(currentContent);
              editorWidget.instance.getModel().modified.setValue(currentContent);
          } else if (editorWidget.domElement) {
              editorWidget.domElement.textContent = `(Monaco N/A) Current Content: ${currentContent}`;
          }
      }
  }
}

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

function initializeHitlUIElements() {
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

    showSection('edit-request-input-area', false);
    showSection('location-confirmation-area', false);
    showSection('inner-loop-decision-area', false);

    if (app.ui.btnApproveEndSession) {
        app.ui.btnApproveEndSession.onclick = () => {
            if (confirm("Are you sure you want to approve and end the session?")) {
                if (app.api) app.api.terminateSession();
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
                app.api.submitEditRequest(hint, instruction);
                if (app.ui.inputHint) app.ui.inputHint.value = '';
                if (app.ui.inputInstruction) app.ui.inputInstruction.value = '';
                if (app.ui.editRequestInputArea) {
                     app.ui.editRequestInputArea.classList.remove('user-opened');
                     showSection('edit-request-input-area', false);
                }
            } else {
                alert("Backend not available to submit edit request.");
            }
        };
    }
    if (app.ui.btnConfirmLocation) {
        app.ui.btnConfirmLocation.onclick = () => {
            if (app.api && app.activeTaskDetails && app.activeTaskDetails.location_info) {
                app.api.submitConfirmedLocationAndInstruction(app.activeTaskDetails.location_info, app.activeTaskDetails.user_instruction);
            }
        };
    }
    if (app.ui.btnCancelLocationStage) {
        app.ui.btnCancelLocationStage.onclick = () => {
            if (app.api) app.api.submitLLMTaskDecision('cancel');
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
        };
    }
    if (app.ui.btnRefineThisEdit) {
        app.ui.btnRefineThisEdit.onclick = () => {
            if (app.api) app.api.submitLLMTaskDecision('reject');
        };
    }
    if (app.ui.btnDiscardThisEdit) {
        app.ui.btnDiscardThisEdit.onclick = () => {
            if (app.api) app.api.submitLLMTaskDecision('cancel');
        };
    }
}

// --- Main Execution Block ---
// require(['vs/editor/editor.main'], () => { // Monaco loader commented out
  console.log("JS: Checking for qt object before QWebChannel setup...");
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
      console.error("JS: app.api (backend object) received (as error log):", app.api); // Changed to console.error
      initializeHitlUIElements();

      // --- Connect Python signals to JavaScript handlers ---
      console.log("JS: Attempting to connect signals...");

      if (app.api && app.api.updateViewSignal) {
          app.api.updateViewSignal.connect((data, config, queue_info) => {
              console.log("JS: updateViewSignal received (raw data):", data, config, queue_info);
            app.data = data;
            app.config = config;
            if (Object.keys(app.widgets).length === 0 || JSON.stringify(app.config) !== JSON.stringify(config)) {
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
                    if (app.api) app.api.submitClarificationForActiveTask(newHint, newInstruction);
                } else {
                    if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_diff_approval';
                    updateGlobalUIState(true, 'awaiting_diff_approval');
                }
            } else {
                if (app.activeTaskDetails) app.activeTaskDetails.status = 'awaiting_diff_approval';
                updateGlobalUIState(true, 'awaiting_diff_approval');
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
// }); // Monaco loader commented out

function updateGlobalUIState(isProcessing, activeTaskStatus) {
    console.log("JS: Updating global UI state. isProcessing:", isProcessing, "activeTaskStatus:", activeTaskStatus);
    const userOpenedEditRequest = app.ui.editRequestInputArea ? app.ui.editRequestInputArea.classList.contains('user-opened') : false;
    showSection('edit-request-input-area', !isProcessing && userOpenedEditRequest);
    showSection('location-confirmation-area', isProcessing && activeTaskStatus === 'awaiting_location_confirmation');
    showSection('inner-loop-decision-area', isProcessing && activeTaskStatus === 'awaiting_diff_approval');

    if (isProcessing && activeTaskStatus === 'awaiting_clarification') {
        showSection('location-confirmation-area', false);
        showSection('inner-loop-decision-area', false);
    }

    const disableControls = isProcessing && app.api;
    if (app.ui.btnRequestNewEdit) app.ui.btnRequestNewEdit.disabled = disableControls;
    if (app.ui.btnApproveEndSession) app.ui.btnApproveEndSession.disabled = disableControls;
    if (app.ui.btnAddtoQueue) app.ui.btnAddtoQueue.disabled = disableControls;

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

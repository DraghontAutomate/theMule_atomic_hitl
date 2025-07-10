require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs' } });

let app = {
  config: {}, // From config.json, defines UI structure (fields, actions)
  data: {},   // From data.json, the actual data content
  widgets: {}, // For config.json driven widgets (Monaco, inputs, labels)
  api: null,    // Connection to Python backend
  ui: {},       // References to static HITL UI elements from index.html
  activeTaskDetails: {} // Stores details of current task being processed (hint, instruction, location_info)
};

// Function to manage visibility of different UI sections
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

// Costruisce la UI basandosi sulla configurazione from config.json
function renderConfigurableUI() {
  const configurableContainers = ['header-container', 'sidebar-container', 'mainbody-container', 'footer-container'];
  let mainDiffEditorElement = null;
  if (app.widgets.main_diff && app.widgets.main_diff.instance) {
      const mainBody = document.getElementById('mainbody-container');
      if (mainBody && mainBody.contains(app.widgets.main_diff.instance.getDomNode())) {
          mainDiffEditorElement = app.widgets.main_diff.instance.getDomNode().parentElement;
      }
  }

  configurableContainers.forEach(id => {
    const container = document.getElementById(id);
    if (container) {
        if (id === 'mainbody-container' && mainDiffEditorElement) {
            Array.from(container.childNodes).forEach(child => {
                if (child !== mainDiffEditorElement && !mainDiffEditorElement.contains(child) &&
                    child.id !== 'location-confirmation-area' && child.id !== 'inner-loop-decision-area') { // Keep new areas
                    container.removeChild(child);
                }
            });
        } else if (id !== 'mainbody-container') { // Don't clear mainbody if editor is there, also don't clear its new sub-sections
            container.innerHTML = '';
        }
    }
  });

  app.widgets = {}; // Reset only config-driven widgets

  if (app.config.fields) {
    app.config.fields.forEach(field => {
        const container = document.getElementById(`${field.placement}-container`);
        if (!container) return;

        if (field.type === 'diff-editor') {
            // Only create if it doesn't exist or wasn't preserved
            if (!mainDiffEditorElement || field.name !== "main_diff") { // Assuming "main_diff" is the key for the main editor
                const editorDiv = document.createElement('div');
                // Important: Give the div for Monaco a specific size or it won't show.
                // This should ideally be handled by CSS for 'mainbody-container' or a dedicated editor wrapper.
                // For now, let's add a default style if it's in mainbody.
                if (field.placement === 'mainbody') {
                    editorDiv.style.height = "calc(100% - 100px)"; // Example, adjust as needed
                    editorDiv.style.width = "100%";
                }
                container.appendChild(editorDiv);
                const editor = monaco.editor.createDiffEditor(editorDiv, { automaticLayout: true, originalEditable: false });
                editor.setModel({ original: monaco.editor.createModel('', 'text/plain'), modified: monaco.editor.createModel('', 'text/plain') });
                app.widgets[field.name] = { type: 'diff-editor', instance: editor, config: field };
            } else if (field.name === "main_diff" && mainDiffEditorElement && app.widgets.main_diff) {
                // Editor already exists and was preserved, do nothing to recreate
            }
        } else {
          const group = document.createElement('div'); group.className = 'field-group';
          const label = document.createElement('label'); label.textContent = field.label; group.appendChild(label);
          let element;
          if (field.type === 'text-input') element = document.createElement('input');
          else if (field.type === 'textarea') element = document.createElement('textarea');
          else { element = document.createElement('span'); if (field.type === 'label-bold') element.classList.add('label-bold'); }
          group.appendChild(element);
          app.widgets[field.name] = { type: 'field', element: element, config: field };
          container.appendChild(group);
        }
    });
  }

  if (app.config.actions) {
    app.config.actions.forEach(action => {
        const container = document.getElementById(`${action.placement}-container`);
        if (!container) return;
        const button = document.createElement('button'); button.textContent = action.label; button.className = 'action-button';
        if (action.isPrimary) button.classList.add('primary');
        button.onclick = () => {
          const payload = getPayloadFromUI(action);
          app.api.performAction(action.name, payload); // Backend expects object, not JSON string for payload
        };
        container.appendChild(button);
    });
  }
}

function renderData() {
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    if (widget.type === 'diff-editor') {
      // This part is tricky because the diff editor content is highly contextual (HITL state)
      // For now, let the specific HITL signal handlers manage the main_diff editor's content.
      // Only set general data fields if they are NOT the main diff editor.
      if (name !== (app.config.fields.find(f => f.type === 'diff-editor')?.name || 'main_diff')) {
          widget.instance.getModel().original.setValue(app.data[widget.config.originalDataField] || '');
          widget.instance.getModel().modified.setValue(app.data[widget.config.modifiedDataField] || '');
      }
    } else if (widget.type === 'field') {
      const value = app.data[widget.config.name] || '';
      if (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA') widget.element.value = value;
      else widget.element.textContent = value;
    }
  }
  // Ensure main_diff editor (if exists) reflects current_main_content when idle
  const mainDiffConfig = app.config.fields.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
  if (mainDiffConfig && app.widgets[mainDiffConfig.name] && app.widgets[mainDiffConfig.name].instance) {
      const editor = app.widgets[mainDiffConfig.name].instance;
      const currentContent = app.data[mainDiffConfig.modifiedDataField] || '';
      if (!app.activeTaskDetails || !app.activeTaskDetails.status ||
          (app.activeTaskDetails.status !== 'awaiting_diff_approval' && app.activeTaskDetails.status !== 'awaiting_location_confirmation')) {
          editor.getModel().original.setValue(currentContent);
          editor.getModel().modified.setValue(currentContent);
      }
  }
}

function getPayloadFromUI(action) {
  const payload = {};
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    if (widget.type === 'field' && (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA')) {
      payload[widget.config.name] = widget.element.value; // Use field name from config
    }
  }
  if (action.editorName && app.widgets[action.editorName] && app.widgets[action.editorName].type === 'diff-editor') {
    payload[app.widgets[action.editorName].config.modifiedDataField] = app.widgets[action.editorName].instance.getModifiedEditor().getValue();
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
                if (!isProcessing) {
                    const currentlyOpen = !editArea.classList.contains('hidden');
                    showSection(editArea.id, !currentlyOpen);
                    if (!currentlyOpen) editArea.classList.add('user-opened');
                    else editArea.classList.remove('user-opened');

                    if (!editArea.classList.contains('hidden') && app.ui.inputHint) app.ui.inputHint.focus();
                } else {
                    alert("Cannot request new edit while another is processing.");
                }
            }
             if (!editArea.classList.contains('hidden')) { // if shown
                 updateGlobalUIState(false, null); // Ensure other HITL sections are hidden
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
            }
        };
    }
    if (app.ui.btnConfirmLocation) {
        app.ui.btnConfirmLocation.onclick = () => {
            if (app.api && app.activeTaskDetails && app.activeTaskDetails.location_info) {
                const revisedHint = app.ui.inputRevisedHint ? app.ui.inputRevisedHint.value.trim() : app.activeTaskDetails.original_hint;
                // Decision for Part 3, Step 10: JS sends (revised_hint_string, original_location_info_object, original_instruction_string)
                // Backend slot `submitConfirmedLocationAndInstruction` expects (dict_location_info, original_instruction_str)
                // For now, if revisedHint is different from original_hint, we will pass the original location_info
                // and the backend's `proceed_with_edit_after_location_confirmation` will need to be smart about using
                // the revised hint if it's different. This is a slight deferral of fully implementing the re-location on hint change.
                // Or, simpler: the button *confirms the visually presented snippet*. Revised hint is for *next* clarification if needed.
                // Let's use the original location_info from activeTaskDetails for now.
                // The backend `submitConfirmedLocationAndInstruction` takes (dict, str)
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
            const mainDiffWidget = app.config.fields.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
            if (mainDiffWidget && app.widgets[mainDiffWidget.name] && app.widgets[mainDiffWidget.name].instance) {
                contentToApprove = app.widgets[mainDiffWidget.name].instance.getModifiedEditor().getValue();
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

require(['vs/editor/editor.main'], () => {
  new QWebChannel(qt.webChannelTransport, channel => {
    if (!channel.objects.backend) {
        console.error("ERROR: 'backend' object not found in QWebChannel.");
        alert("Critical Error: Could not connect to Python backend.");
        return;
    }
    app.api = channel.objects.backend;
    initializeHitlUIElements();

    if (app.api.updateViewSignal) {
        app.api.updateViewSignal.connect((data, config, queue_info) => {
            console.log("JS: updateViewSignal", data, config, queue_info);
            app.data = data;
            const prevConfigStr = JSON.stringify(app.config);
            app.config = config;
            if (JSON.stringify(config) !== prevConfigStr || Object.keys(app.widgets).length === 0) {
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
    } else {
        console.error("JS: updateViewSignal not found.");
    }
    if (app.api.promptUserToConfirmLocationSignal) {
        app.api.promptUserToConfirmLocationSignal.connect((location_info, original_hint, original_instruction) => {
            app.activeTaskDetails = { location_info, original_hint, user_instruction: original_instruction };
            if (app.ui.originalHintDisplay) app.ui.originalHintDisplay.textContent = original_hint;
            if (app.ui.locatedSnippetPreview) app.ui.locatedSnippetPreview.textContent = location_info.snippet;
            if (app.ui.inputRevisedHint) app.ui.inputRevisedHint.value = original_hint;
            updateGlobalUIState(true, 'awaiting_location_confirmation');
            if (app.ui.inputRevisedHint) app.ui.inputRevisedHint.focus();
        });
    } else {
        console.error("JS: promptUserToConfirmLocationSignal not found.");
    }
    if (app.api.showDiffPreviewSignal) {
        app.api.showDiffPreviewSignal.connect((originalSnippet, editedSnippet) => {
            const mainDiffWidget = app.config.fields.find(f => f.type === 'diff-editor' && f.placement === 'mainbody');
            if (mainDiffWidget && app.widgets[mainDiffWidget.name] && app.widgets[mainDiffWidget.name].instance) {
                const editorInstance = app.widgets[mainDiffWidget.name].instance;
                editorInstance.getModel().original.setValue(originalSnippet || '');
                editorInstance.getModel().modified.setValue(editedSnippet || '');
                if (app.activeTaskDetails) app.activeTaskDetails.llmProposedSnippet = editedSnippet;
            } else {
                alert(`DIFF PREVIEW:\n--- ORIGINAL ---\n${originalSnippet}\n--- EDITED ---\n${editedSnippet}`);
            }
            updateGlobalUIState(true, 'awaiting_diff_approval');
        });
    } else {
         console.error("JS: showDiffPreviewSignal not found.");
    }
    if (app.api.requestClarificationSignal) {
        app.api.requestClarificationSignal.connect(() => {
            updateGlobalUIState(true, 'awaiting_clarification');
            const currentHint = app.activeTaskDetails ? app.activeTaskDetails.original_hint : '';
            const currentInstruction = app.activeTaskDetails ? app.activeTaskDetails.user_instruction : '';
            const newHint = prompt(`REFINE TASK:\nOriginal Hint: ${currentHint}\nEnter new/revised Hint (or leave blank to keep current):`, currentHint);
            if (newHint !== null) {
                const newInstruction = prompt(`Original Instruction: ${currentInstruction}\nEnter new/revised Instruction for this task:`, currentInstruction);
                if (newInstruction !== null) {
                    app.api.submitClarificationForActiveTask(newHint, newInstruction);
                } else {
                    updateGlobalUIState(true, 'awaiting_diff_approval'); // Revert UI to show diff decisions
                }
            } else {
                updateGlobalUIState(true, 'awaiting_diff_approval'); // Revert UI
            }
        });
    } else {
        console.error("JS: requestClarificationSignal not found.");
    }
    if (app.api.showErrorSignal) {
        app.api.showErrorSignal.connect((errorMessage) => {
            alert("Error from backend: " + errorMessage);
        });
    }

    app.api.getInitialPayload().then(payload => {
      app.config = payload.config;
      app.data = payload.data;
      if (app.api.startSession) app.api.startSession();
      else console.error("JS: startSession method not found.");
    }).catch(error => {
        console.error("JS: Error calling getInitialPayload:", error);
        alert("Critical Error: Could not fetch initial data.");
    });
  });
});

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

    if (app.ui.btnRequestNewEdit) app.ui.btnRequestNewEdit.disabled = isProcessing;
    if (app.ui.btnApproveEndSession) app.ui.btnApproveEndSession.disabled = isProcessing;
    if (app.ui.btnAddtoQueue) app.ui.btnAddtoQueue.disabled = isProcessing;

    const configActionButtons = document.querySelectorAll(
        '#header-container .action-button, #sidebar-container .action-button, #footer-container .action-button'
    );
    configActionButtons.forEach(button => {
        const parentDivId = button.closest('div')?.id; // check if it's one of our HITL areas
        const isHitlButton = parentDivId === 'location-confirmation-area' || parentDivId === 'inner-loop-decision-area' || parentDivId === 'app-controls-container' || parentDivId === 'edit-request-input-area';
        if (!isHitlButton) { // Only disable non-HITL specific config buttons
            button.disabled = isProcessing;
        }
    });
}

require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs' } });

let app = {
  config: {},
  data: {},
  widgets: {}, // Registro centrale per tutti gli elementi della UI
  api: null,
};

// Costruisce la UI basandosi sulla configurazione
function renderUI() {
  ['header', 'sidebar', 'mainbody', 'footer'].forEach(p => {
    const container = document.getElementById(`${p}-container`);
    if (container) container.innerHTML = '';
  });
  app.widgets = {};

  app.config.fields.forEach(field => {
    const container = document.getElementById(`${field.placement}-container`);
    if (!container) return;

    if (field.type === 'diff-editor') {
      const editor = monaco.editor.createDiffEditor(container, { automaticLayout: true, originalEditable: false });
      editor.setModel({ original: monaco.editor.createModel('', 'text/plain'), modified: monaco.editor.createModel('', 'text/plain') });
      app.widgets[field.name] = { type: 'diff-editor', instance: editor, config: field };
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

  app.config.actions.forEach(action => {
    const container = document.getElementById(`${action.placement}-container`);
    if (!container) return;
    const button = document.createElement('button'); button.textContent = action.label; button.className = 'action-button';
    if (action.isPrimary) button.classList.add('primary');
    button.onclick = () => {
      const payload = getPayloadFromUI(action);
      app.api.performAction(action.name, JSON.stringify(payload));
    };
    container.appendChild(button);
  });
}

// Popola la UI con i dati
function renderData() {
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    if (widget.type === 'diff-editor') {
      widget.instance.getModel().original.setValue(app.data[widget.config.originalDataField] || '');
      widget.instance.getModel().modified.setValue(app.data[widget.config.modifiedDataField] || '');
    } else if (widget.type === 'field') {
      const value = app.data[widget.config.name] || '';
      if (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA') widget.element.value = value;
      else widget.element.textContent = value;
    }
  }
}

// Raccoglie i dati dai campi di input prima di inviarli al backend
function getPayloadFromUI(action) {
  const payload = {};
  for (const name in app.widgets) {
    const widget = app.widgets[name];
    if (widget.type === 'field' && (widget.element.tagName === 'INPUT' || widget.element.tagName === 'TEXTAREA')) {
      payload[name] = widget.element.value;
    }
  }
  if (action.editorName && app.widgets[action.editorName]) {
    payload.editorName = action.editorName;
    payload.mergedText = app.widgets[action.editorName].instance.getModifiedEditor().getValue();
  }
  return payload;
}

// Logica principale di avvio
require(['vs/editor/editor.main'], () => {
  new QWebChannel(qt.webChannelTransport, channel => {
    app.api = channel.objects.bridge; // JS frontend expects 'bridge'
    // Python backend in runner.py exposes 'backend'
    // This needs to be consistent. Let's assume JS should use 'backend'.
    // app.api = channel.objects.backend;

    // Let's check if the backend object matches what we exposed in runner.py
    if (!channel.objects.backend) {
        console.error("ERROR: 'backend' object not found in QWebChannel. Available objects:", Object.keys(channel.objects));
        alert("Critical Error: Could not connect to Python backend. 'backend' object missing.");
        return;
    }
    app.api = channel.objects.backend;


    // Connect to the new updateViewSignal from Python backend
    // This signal sends two dictionaries: data and config
    if (app.api.updateViewSignal) { // Check if the signal exists
        app.api.updateViewSignal.connect((data, config) => {
            console.log("JS: Received updateViewSignal with data and config.");
            app.data = data;
            app.config = config; // Potentially update config if it can change dynamically
            // Re-render UI if config changes, or just data if only data changes
            // For now, assume config is static after initial load for simplicity with current renderUI
            renderData();
        });
    } else {
        console.error("JS: updateViewSignal not found on backend object.");
    }

    // Connect to other signals from Python backend that are still relevant
    if (app.api.showDiffPreviewSignal) {
        app.api.showDiffPreviewSignal.connect((originalSnippet, editedSnippet, beforeContext, afterContext) => {
            console.log("JS: Received showDiffPreviewSignal.");
            // This is the new frontend.js from the "Fully Configurable Tool" example.
            // It doesn't have a dedicated diff preview modal like the original SurgicalEditor.
            // For now, we'll log it. A proper UI element would be needed to display this.
            console.log("Original Snippet:", originalSnippet);
            console.log("Edited Snippet:", editedSnippet);
            console.log("Context Before:", beforeContext);
            console.log("Context After:", afterContext);
            // Perhaps show an alert or a dedicated small modal if we design one.
            // alert(`Diff Preview:\nOriginal: ${originalSnippet}\nEdited: ${editedSnippet}`);
        });
    }

    if (app.api.requestClarificationSignal) {
        app.api.requestClarificationSignal.connect(() => {
            console.log("JS: Received requestClarificationSignal.");
            // The "Fully Configurable Tool" frontend.js doesn't have a specific clarification UI.
            // This was for the SurgicalEditor's internal loop.
            // We might need a generic way to prompt user or integrate this differently.
            const newHint = prompt("Python backend requests clarification. Enter new hint (or leave blank):");
            const newInstruction = prompt("Enter new instruction (or leave blank):");
            if (newHint !== null || newInstruction !== null) { // User didn't cancel both prompts
                 // Assuming the backend is expecting submitClarificationForSnippet
                app.api.submitClarificationForSnippet(newHint || "", newInstruction || "");
            }
        });
    }

    if (app.api.showErrorSignal) {
        app.api.showErrorSignal.connect((errorMessage) => {
            console.error("JS: Received showErrorSignal:", errorMessage);
            alert("Error from backend: " + errorMessage);
        });
    }

    // Initial data and config load
    // Use getInitialPayload which returns both config and data
    app.api.getInitialPayload().then(payload => { // payload is already an object here {config: ..., data: ...}
      console.log("JS: Received initial payload:", payload);
      app.config = payload.config;
      app.data = payload.data;
      renderUI(); // Build UI based on config
      renderData(); // Populate UI with data

      // After initial load, explicitly call startSession on backend
      // This ensures the backend's state machine (if any) is correctly initialized,
      // and it might trigger an initial updateViewSignal if core.py's start_session does so.
      if (app.api.startSession) {
        app.api.startSession();
      } else {
        console.error("JS: startSession method not found on backend object.");
      }

    }).catch(error => {
        console.error("JS: Error calling getInitialPayload:", error);
        alert("Critical Error: Could not fetch initial data from Python backend.");
    });
  });
});

import loader from 'https://cdn.jsdelivr.net/npm/@monaco-editor/loader@1.4.0/+esm';

let backend;

new QWebChannel(qt.webChannelTransport, function (channel) {
    backend = channel.objects.backend;
});

loader.init().then(monaco => {
    const originalModel = monaco.editor.createModel("hello world", "text/plain");
    const modifiedModel = monaco.editor.createModel("hello world 2", "text/plain");

    const diffEditor = monaco.editor.createDiffEditor(document.getElementById("editor-container"), {
        enableSplitViewResizing: false,
        renderSideBySide: true
    });

    diffEditor.setModel({
        original: originalModel,
        modified: modifiedModel
    });

    document.getElementById("test-button").addEventListener("click", () => {
        if (backend) {
            const originalValue = diffEditor.getOriginalEditor().getValue();
            const modifiedValue = diffEditor.getModifiedEditor().getValue();
            const message = JSON.stringify({
                original: originalValue,
                modified: modifiedValue
            });
            backend.on_message(message);
        } else {
            console.error("Backend not available");
        }
    });
});

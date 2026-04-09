(function () {
    // @ts-ignore
    const vscode = acquireVsCodeApi();

    const messagesEl = document.getElementById('messages');
    const questionEl = document.getElementById('question');
    const sendBtn = document.getElementById('send-btn');

    let currentAssistantMsg = null;
    let isStreaming = false;

    // Send question on button click
    sendBtn.addEventListener('click', sendQuestion);

    // Send on Enter (Shift+Enter for newline)
    questionEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });

    function sendQuestion() {
        const question = questionEl.value.trim();
        if (!question || isStreaming) return;

        // Show user message
        addMessage(question, 'user');
        questionEl.value = '';

        // Disable input while streaming
        isStreaming = true;
        sendBtn.disabled = true;

        // Create assistant message placeholder
        currentAssistantMsg = addMessage('', 'assistant');
        currentAssistantMsg.classList.add('typing-indicator');
        currentAssistantMsg.textContent = 'Thinking...';

        // Send to extension
        vscode.postMessage({ type: 'ask', question: question });
    }

    function addMessage(text, role) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.textContent = text;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return div;
    }

    // Handle messages from the extension
    window.addEventListener('message', (event) => {
        const message = event.data;

        switch (message.type) {
            case 'responseChunk':
                if (currentAssistantMsg) {
                    if (currentAssistantMsg.classList.contains('typing-indicator')) {
                        currentAssistantMsg.classList.remove('typing-indicator');
                        currentAssistantMsg.textContent = '';
                    }
                    currentAssistantMsg.textContent += message.text;
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                }
                break;

            case 'responseDone':
                isStreaming = false;
                sendBtn.disabled = false;
                currentAssistantMsg = null;
                questionEl.focus();
                break;

            case 'response':
                // Non-streamed full response (errors, etc.)
                if (currentAssistantMsg) {
                    currentAssistantMsg.classList.remove('typing-indicator');
                    currentAssistantMsg.textContent = message.text;
                    if (message.text.startsWith('Error:')) {
                        currentAssistantMsg.classList.add('error');
                    }
                }
                isStreaming = false;
                sendBtn.disabled = false;
                currentAssistantMsg = null;
                break;
        }
    });
})();

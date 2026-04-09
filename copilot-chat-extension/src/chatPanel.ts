import * as vscode from 'vscode';

export class ChatViewProvider implements vscode.WebviewViewProvider {
    private static currentPanel: vscode.WebviewPanel | undefined;
    private webviewView: vscode.WebviewView | undefined;

    constructor(private readonly extensionUri: vscode.Uri) {}

    // Sidebar webview
    public resolveWebviewView(webviewView: vscode.WebviewView) {
        this.webviewView = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.joinPath(this.extensionUri, 'media')],
        };

        webviewView.webview.html = this.getHtml(webviewView.webview);
        this.setupMessageHandler(webviewView.webview);
    }

    // Full editor panel
    public static createOrShowPanel(extensionUri: vscode.Uri) {
        if (ChatViewProvider.currentPanel) {
            ChatViewProvider.currentPanel.reveal();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'copilotChat',
            'Copilot Chat',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')],
            }
        );

        const provider = new ChatViewProvider(extensionUri);
        panel.webview.html = provider.getHtml(panel.webview);
        provider.setupMessageHandler(panel.webview);

        panel.onDidDispose(() => {
            ChatViewProvider.currentPanel = undefined;
        });

        ChatViewProvider.currentPanel = panel;
    }

    private setupMessageHandler(webview: vscode.Webview) {
        webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case 'ask':
                    await this.handleQuestion(webview, message.question);
                    break;
            }
        });
    }

    private async handleQuestion(webview: vscode.Webview, question: string) {
        try {
            // Select a Copilot model via VS Code LM API
            const models = await vscode.lm.selectChatModels({
                vendor: 'copilot',
                family: 'gpt-4o',
            });

            if (models.length === 0) {
                webview.postMessage({
                    type: 'response',
                    text: 'No Copilot model available. Make sure GitHub Copilot is installed and you are signed in.',
                });
                return;
            }

            const model = models[0];

            const messages = [
                vscode.LanguageModelChatMessage.User(question),
            ];

            // Send request and stream the response
            const response = await model.sendRequest(messages, {}, new vscode.CancellationTokenSource().token);

            let fullResponse = '';
            for await (const chunk of response.text) {
                fullResponse += chunk;
                // Stream chunks to the webview
                webview.postMessage({
                    type: 'responseChunk',
                    text: chunk,
                });
            }

            // Signal that streaming is done
            webview.postMessage({ type: 'responseDone' });

        } catch (error: any) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            webview.postMessage({
                type: 'response',
                text: `Error: ${errorMessage}`,
            });
        }
    }

    private getHtml(webview: vscode.Webview): string {
        const cssUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this.extensionUri, 'media', 'chat.css')
        );
        const jsUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this.extensionUri, 'media', 'chat.js')
        );

        return /*html*/ `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="${cssUri}">
    <title>Copilot Chat</title>
</head>
<body>
    <div id="chat-container">
        <div id="messages"></div>
        <div id="input-area">
            <textarea id="question" placeholder="Ask Copilot a question..." rows="2"></textarea>
            <button id="send-btn">Send</button>
        </div>
    </div>
    <script src="${jsUri}"></script>
</body>
</html>`;
    }
}

import * as vscode from 'vscode';
import { ChatViewProvider } from './chatPanel';
import { startBridgeServer, stopBridgeServer } from './bridge';

export function activate(context: vscode.ExtensionContext) {
    const chatProvider = new ChatViewProvider(context.extensionUri);

    // Register the webview view provider for the sidebar
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('copilotChat.chatView', chatProvider)
    );

    // Register the command to open chat in a full panel
    context.subscriptions.push(
        vscode.commands.registerCommand('copilotChat.open', () => {
            ChatViewProvider.createOrShowPanel(context.extensionUri);
        })
    );

    // Start the HTTP bridge server so Streamlit can call vscode.lm
    startBridgeServer(3001);

    // Clean up on deactivation
    context.subscriptions.push({
        dispose: () => stopBridgeServer(),
    });
}

export function deactivate() {
    stopBridgeServer();
}

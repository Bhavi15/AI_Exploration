import * as http from 'http';
import * as vscode from 'vscode';

let server: http.Server | undefined;

export function startBridgeServer(port: number = 3001): http.Server {
    if (server) {
        return server;
    }

    server = http.createServer(async (req, res) => {
        // CORS headers so Streamlit (different port) can call us
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

        // Handle preflight
        if (req.method === 'OPTIONS') {
            res.writeHead(204);
            res.end();
            return;
        }

        if (req.method === 'POST' && req.url === '/chat') {
            await handleChatRequest(req, res);
            return;
        }

        if (req.method === 'GET' && req.url === '/health') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ok' }));
            return;
        }

        if (req.method === 'GET' && req.url === '/models') {
            await handleListModels(req, res);
            return;
        }

        res.writeHead(404);
        res.end(JSON.stringify({ error: 'Not found' }));
    });

    server.listen(port, () => {
        vscode.window.showInformationMessage(`Copilot Bridge running on http://localhost:${port}`);
    });

    return server;
}

export function stopBridgeServer() {
    if (server) {
        server.close();
        server = undefined;
    }
}

async function handleListModels(req: http.IncomingMessage, res: http.ServerResponse) {
    try {
        const models = await vscode.lm.selectChatModels();
        const modelList = models.map(m => ({
            id: m.id,
            name: m.name,
            vendor: m.vendor,
            family: m.family,
        }));
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(modelList));
    } catch (error: any) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: error.message }));
    }
}

async function handleChatRequest(req: http.IncomingMessage, res: http.ServerResponse) {
    // Read request body
    let body = '';
    for await (const chunk of req) {
        body += chunk;
    }

    let parsed: { question: string; vendor?: string; family?: string };
    try {
        parsed = JSON.parse(body);
    } catch {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
        return;
    }

    if (!parsed.question) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Missing "question" field' }));
        return;
    }

    try {
        // Select model — match by vendor + family from request, no hardcoded filter
        const selector: vscode.LanguageModelChatSelector = {};
        if (parsed.vendor) {
            selector.vendor = parsed.vendor;
        }
        if (parsed.family) {
            selector.family = parsed.family;
        }

        const models = await vscode.lm.selectChatModels(selector);
        if (models.length === 0) {
            res.writeHead(503, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'No Copilot model available. Is GitHub Copilot signed in?' }));
            return;
        }

        const model = models[0];
        const messages = [vscode.LanguageModelChatMessage.User(parsed.question)];
        const response = await model.sendRequest(messages, {}, new vscode.CancellationTokenSource().token);

        // Stream response using Server-Sent Events (SSE)
        res.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        });

        for await (const chunk of response.text) {
            res.write(`data: ${JSON.stringify({ chunk })}\n\n`);
        }

        res.write('data: [DONE]\n\n');
        res.end();

    } catch (error: any) {
        if (!res.headersSent) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: error.message }));
        }
    }
}

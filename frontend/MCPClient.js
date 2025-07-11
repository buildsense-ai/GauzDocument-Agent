import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import fs from 'fs';
import { promises as fsPromises } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { HttpClientTransport } from "./HttpClientTransport.js";
import { FastAPIMCPClient } from "./FastAPIMCPClient.js";
import { GeminiLLM } from "./GeminiLLM.js";
import { config } from "./config.js";
// import mcpServers from "./mcp-server-config.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class MCPClient {
    constructor(openRouterApiKey = null) {
        this.openRouterApiKey = openRouterApiKey || config.openRouterApiKey;
        this.llm = new GeminiLLM(this.openRouterApiKey, config.geminiModel);
        this.clients = new Map();
        this.allTools = [];
        this.config = config;
    }

    async initialize() {
        console.log("🚀 Initializing MCP Client...");
        const mcpServers = this.getServerConfigs();

        // Connect to all enabled MCP servers
        for (const serverConfig of mcpServers) {
            if (serverConfig.isOpen) {
                try {
                    const fullServerConfig = {
                        ...serverConfig,
                        apiKey: this.openRouterApiKey,
                    };
                    await this.connectToServer(fullServerConfig);
                } catch (error) {
                    // Log the error but don't crash the application
                    console.error(`-- SKIPPING SERVER: Failed to connect to ${serverConfig.name} on startup --`);
                }
            }
        }

        console.log(`✅ Initialization complete. Connected to ${this.clients.size} MCP server(s)`);
        console.log(`🔧 Total available tools: ${this.allTools.length}`);
    }

    getServerConfigs() {
        const configPath = path.resolve(__dirname, 'mcp-server-config.json');
        try {
            const fileContent = fs.readFileSync(configPath, 'utf-8');
            return JSON.parse(fileContent);
        } catch (error) {
            console.error("❌ Error reading or parsing mcp-server-config.json:", error);
            return [];
        }
    }

    async connectToServer(serverConfig) {
        try {
            // Check if this is a FastAPI-MCP server
            const isFastAPIMCP = serverConfig.type === 'fastapi-mcp';

            let client;
            let toolsResult;

            if (isFastAPIMCP) {
                // Use FastAPI-MCP client for FastAPI-based servers
                console.log(`🔧 Using FastAPI-MCP client for ${serverConfig.name}`);
                client = new FastAPIMCPClient(serverConfig.url, serverConfig.apiKey);
                const connected = await client.initialize();

                if (connected) {
                    toolsResult = await client.listTools();
                } else {
                    throw new Error("Failed to initialize FastAPI-MCP client");
                }

            } else {
                // Use standard MCP client for JSON-RPC servers
                console.log(`🔧 Using standard MCP client for ${serverConfig.name}`);
                const transport = new HttpClientTransport(serverConfig.url);
                client = new Client({
                    name: "mcp-client",
                    version: "1.0.0"
                }, {
                    capabilities: {}
                });

                await client.connect(transport);
                toolsResult = await client.listTools();
            }

            this.clients.set(serverConfig.name, { client, config: serverConfig, type: isFastAPIMCP ? 'fastapi-mcp' : 'standard' });

            // First, remove any existing tools from this server to prevent duplicates during re-connection
            this.allTools = this.allTools.filter(tool => tool.serverName !== serverConfig.name);

            // List available tools from this server
            if (toolsResult.tools) {
                this.allTools.push(...toolsResult.tools.map(tool => ({
                    ...tool,
                    serverName: serverConfig.name
                })));
                console.log(`📋 Server ${serverConfig.name}: ${toolsResult.tools.length} tools`);
            }
        } catch (error) {
            console.error(`❌ Failed to connect to ${serverConfig.name}:`, error);
            throw error;
        }
    }

    async processUserQuery(userMessage, uploadedFiles = []) {
        console.log(`\n💬 Processing user query: "${userMessage}"`);
        if (uploadedFiles && uploadedFiles.length > 0) {
            console.log(`📎 With ${uploadedFiles.length} uploaded files`);
        }

        // Create a smart system prompt that allows natural conversation and intelligent tool usage
        const systemPrompt = this.createIntelligentSystemPrompt(uploadedFiles);

        const messages = [
            {
                role: "system",
                content: systemPrompt
            },
            {
                role: "user",
                content: userMessage
            }
        ];

        return await this.chatLoop(messages);
    }

    createIntelligentSystemPrompt(uploadedFiles = []) {
        const availableTools = this.allTools.length > 0
            ? `\nAvailable tools:\n${this.allTools.map(tool => `- ${tool.name}: ${tool.description}`).join('\n')}`
            : '\nNo tools are currently available.';

        const filePrompt = uploadedFiles.length > 0
            ? `\nUploaded files:\n${uploadedFiles.map(file => `- ${file.name} (${file.type || 'unknown type'}) - ${file.path}`).join('\n')}\n\nNote: When tools need file paths, use the paths above.`
            : '';

        return `You are an intelligent AI assistant with access to MCP (Model Context Protocol) tools. You can:

1. **Chat naturally** - Answer questions, have conversations, provide help and information
2. **Use tools when appropriate** - Only call tools when the user specifically requests an action that requires them

${availableTools}
${filePrompt}

**Important guidelines:**
- Have natural conversations like ChatGPT or Claude
- Use tools flexiblywhen the user explicitly asks for something that requires them
- For simple greetings, questions, or general chat, just respond normally without calling any tools
- When you do use tools, explain what you're doing and why
- If no tools are available, let the user know and still be helpful with conversation

**Example interactions:**
- User: "Hello" → Just greet them naturally, no tools needed
- User: "How are you?" → Chat response, no tools needed  
- User: "What can you do?" → Explain your capabilities and available tools
- User: "Generate a document" → Use appropriate tool if available
- User: "Create a renovation report" → Use document generation tool

Be conversational, helpful, and intelligent about when to use tools.`;
    }

    async chatLoop(messages, maxIterations = 5) {
        let iteration = 0;

        while (iteration < maxIterations) {
            iteration++;
            console.log(`\n🔄 Chat iteration ${iteration}`);

            // Prepare tools for OpenRouter format (only if tools are available)
            const formattedTools = this.allTools.length > 0
                ? GeminiLLM.formatToolsForOpenRouter(this.allTools)
                : null;

            // Send to LLM - with or without tools depending on availability
            const response = await this.llm.sendToLLM(messages, formattedTools);

            if (!response.choices || response.choices.length === 0) {
                throw new Error("No response from LLM");
            }

            const choice = response.choices[0];
            const message = choice.message;

            // Add assistant message to conversation
            messages.push(message);

            // Check if LLM wants to use tools (and tools are available)
            if (message.tool_calls && message.tool_calls.length > 0) {

                if (this.allTools.length === 0) {
                    // LLM tried to use tools but none are available
                    console.log(`⚠️ LLM attempted tool use but no tools available`);
                    messages.push({
                        role: "system",
                        content: "No tools are currently available. Please respond with a helpful message explaining this to the user."
                    });
                    continue;
                }

                console.log(`🔧 LLM wants to use ${message.tool_calls.length} tool(s)`);

                // Execute each tool call
                for (const toolCall of message.tool_calls) {
                    const toolResult = await this.executeToolCall(toolCall);

                    // Add tool result to conversation
                    messages.push({
                        role: "tool",
                        tool_call_id: toolCall.id,
                        content: JSON.stringify(toolResult)
                    });
                }

                // Continue the loop to let LLM process tool results
                continue;
            }

            // No tool calls - return final response
            console.log(`✅ Final response received`);
            return {
                response: message.content,
                totalIterations: iteration,
                conversation: messages,
                toolsUsed: this.allTools.length > 0 ? 'available' : 'none'
            };
        }

        console.log(`⚠️ Reached maximum iterations (${maxIterations})`);
        return {
            response: "I've reached the maximum conversation limit. Please start a new conversation.",
            totalIterations: iteration,
            conversation: messages,
            toolsUsed: this.allTools.length > 0 ? 'available' : 'none'
        };
    }

    async executeToolCall(toolCall) {
        const toolName = toolCall.function.name;
        const toolArgs = JSON.parse(toolCall.function.arguments);

        console.log(`🔧 Executing tool: ${toolName}`);
        console.log(`📝 Arguments:`, toolArgs);

        // Find which server has this tool
        const tool = this.allTools.find(t => t.name === toolName);
        if (!tool) {
            const errorMsg = `Tool '${toolName}' not found`;
            console.error(`❌ ${errorMsg}`);
            return { error: errorMsg };
        }

        const serverInfo = this.clients.get(tool.serverName);
        if (!serverInfo) {
            const errorMsg = `Server '${tool.serverName}' not connected`;
            console.error(`❌ ${errorMsg}`);
            return { error: errorMsg };
        }

        try {
            // Process file paths in tool arguments
            const processedArgs = await this.processFileArguments(toolArgs);

            // Call the tool via MCP (different methods for different client types)
            let result;

            if (serverInfo.type === 'fastapi-mcp') {
                // FastAPI-MCP client
                result = await serverInfo.client.callTool({
                    name: toolName,
                    arguments: processedArgs
                });
            } else {
                // Standard MCP client
                result = await serverInfo.client.callTool({
                    name: toolName,
                    arguments: processedArgs
                });
            }

            console.log(`✅ Tool result:`, result);
            return result;
        } catch (error) {
            console.error(`❌ Tool execution failed:`, error);
            return { error: error.message };
        }
    }



    getPublicFileUrl(fileName) {
        // Try to determine the public base URL
        // Support multiple deployment scenarios
        let baseUrl = process.env.PUBLIC_BASE_URL;

        if (!baseUrl) {
            // Auto-detect based on common deployment platforms
            if (process.env.HEROKU_APP_NAME) {
                baseUrl = `https://${process.env.HEROKU_APP_NAME}.herokuapp.com`;
            } else if (process.env.VERCEL_URL) {
                baseUrl = `https://${process.env.VERCEL_URL}`;
            } else if (process.env.RAILWAY_PUBLIC_DOMAIN) {
                baseUrl = `https://${process.env.RAILWAY_PUBLIC_DOMAIN}`;
            } else {
                // Development fallback
                baseUrl = 'http://localhost:3000';
            }
        }

        return `${baseUrl}/uploads/${fileName}`;
    }

    getProjectRoot() {
        // Get the directory where this script is located
        return __dirname;
    }

    disconnectFromServer(serverName) {
        if (this.clients.has(serverName)) {
            this.clients.delete(serverName);
            this.allTools = this.allTools.filter(tool => tool.serverName !== serverName);
            console.log(`🔌 Disconnected from server: ${serverName}`);
        } else {
            console.warn(`⚠️  Attempted to disconnect from a non-connected server: ${serverName}`);
        }
    }

    async close() {
        console.log("🔄 Shutting down MCP Client...");

        for (const [serverName, serverInfo] of this.clients) {
            try {
                await serverInfo.client.close();
                console.log(`✅ Disconnected from ${serverName}`);
            } catch (error) {
                console.error(`❌ Error disconnecting from ${serverName}:`, error);
            }
        }

        this.clients.clear();
        this.allTools = [];
        console.log("👋 MCP Client shut down complete");
    }
} 
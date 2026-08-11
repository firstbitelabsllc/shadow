import { McpServer } from "@modelcontextprotocol/server";
import { createMcpHandler } from "agents/mcp/server";
import { BRIEF_CONTRACT, GOAL_CONTRACT, LOCAL_BOUNDARY } from "./contracts";

const TOOL_ANNOTATIONS = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: false
} as const;

export const TOOL_NAMES = [
  "get_shadow_brief_contract",
  "get_shadow_goal_contract"
] as const;

function textResult(text: string) {
  return { content: [{ type: "text" as const, text }] };
}

export function createServer() {
  const server = new McpServer({
    name: "Shadow Coach",
    version: "1.0.0"
  });

  server.registerTool(
    TOOL_NAMES[0],
    {
      title: "Get the Shadow chief-of-staff brief contract",
      description:
        "Use before writing a portfolio or project brief. Returns Shadow's reader-first structure, reasoning standard, evidence boundaries, and plain-language rules. It supplies no project facts and performs no action.",
      annotations: TOOL_ANNOTATIONS
    },
    async () => textResult(BRIEF_CONTRACT)
  );

  server.registerTool(
    TOOL_NAMES[1],
    {
      title: "Get the Shadow goal contract",
      description:
        "Use before shaping a durable goal. Returns Shadow's compact Outcome, Resume, and Proof contract plus its authority boundaries. It supplies no project facts and performs no action.",
      annotations: TOOL_ANNOTATIONS
    },
    async () => textResult(GOAL_CONTRACT)
  );

  return server;
}

const mcpHandler = createMcpHandler(createServer);

export default {
  fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/") {
      return Response.json({
        name: "Shadow Coach",
        mode: "read-only",
        mcp: "/mcp",
        tools: TOOL_NAMES,
        boundary: LOCAL_BOUNDARY
      });
    }
    if (url.pathname === "/mcp") {
      return mcpHandler(request, env, ctx);
    }
    return new Response("Not found", { status: 404 });
  }
} satisfies ExportedHandler;

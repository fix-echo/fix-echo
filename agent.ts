import {
  createSdkMcpServer,
  query,
  tool,
  type AgentDefinition,
  type HookCallback,
  type PreToolUseHookInput,
} from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";
const reviewSchema = {
  type: "object",
  properties: {
    issues: {
      type: "array",
      items: {
        type: "object",
        properties: {
          severity: {
            type: "string",
            enum: ["low", "medium", "high", "critical"],
          },
          category: {
            type: "string",
            enum: ["bug", "security", "performance", "style"],
          },
          file: { type: "string" },
          line: { type: "number" },
          description: { type: "string" },
          suggestion: { type: "string" },
        },
        required: ["severity", "category", "file", "description"],
      },
    },
    summary: { type: "string" },
    overallScore: { type: "number" },
  },
  required: ["issues", "summary", "overallScore"],
};

// 自定义工具
const customServer = createSdkMcpServer({
  name: "code-metries",
  version: "1.0.0",
  tools: [
    tool(
      "analyze_complexity",
      "计算文件的圈复杂度",
      {
        filePath: z.string().describe("要分析的文件路径"),
      },
      async (args) => {
        // 这里是你的复杂度分析逻辑
        const complexity = Math.floor(Math.random() * 20) + 1; // 占位符
        return {
          content: [
            {
              type: "text",
              text: `文件 ${args.filePath} 的圈复杂度为: ${complexity}`,
            },
          ],
        };
      }
    ),
  ],
});

// use streaming input for MCP servers
async function* generateMessages() {
  yield {
    type: "user" as const,
    message: {
      role: "user" as const,
      content: "Analyze the complexity of main.ts",
    },
  };
}

// 自定义钩子函数，用于记录工具使用情况
const auditLogger: HookCallback = async (input, toolUseId, { signal }) => {
  if (input.hook_event_name === "PreToolUse") {
    const preInput = input as PreToolUseHookInput;
    console.log(`[AUDIT] ${new Date().toISOString()} - ${preInput.tool_name}`);
  }
  return {};
};

// 自定义钩子函数，用于阻止危险命令
const blockDangerousCommands: HookCallback = async (
  input,
  toolUseId,
  { signal }
) => {
  if (input.hook_event_name === "PreToolUse") {
    const preInput = input as PreToolUseHookInput;
    if (preInput.tool_name === "Bash") {
      const command = (preInput.tool_input as any).command || "";
      if (command.includes("rm -rf") || command.includes("sudo")) {
        return {
          hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: "Dangerous command blocked",
          },
        };
      }
    }
  }
  return {};
};

async function reviewCode(directory: string) {
  let sessionId: string | undefined;
  console.log(`\n 🔍 Starting code review for: ${directory}`);

  for await (const message of query({
    prompt: `请对 ${directory} 进行全面的代码审查。
对于安全问题请使用 security-reviewer, 对测试覆盖率请使用 test-analyzer。`,
    options: {
      allowedTools: ["Read", "Glob", "Grep", "Task"],
      permissionMode: "bypassPermissions",
      maxTurns: 250,
      outputFormat: {
        type: "json_schema",
        schema: reviewSchema,
      },
      //   精细控制
      canUseTool: async (toolName, input) => {
        // Allow all read operations
        if (["Read", "Glob", "Grep", "Task"].includes(toolName)) {
          return { behavior: "allow", updatedInput: input };
        }

        // Block writes to certain files
        if (
          toolName === "Write" &&
          (input as { file_path?: string }).file_path?.includes(".env")
        ) {
          return { behavior: "deny", message: "Cannot modify .env files" };
        }

        // Allow everything else
        return { behavior: "allow", updatedInput: input };
      },
      agents: {
        "security-reviewer": {
          description: "安全漏洞检测专家",
          prompt: `你是一名安全专家。请重点关注以下内容：
- SQL 注入、XSS、CSRF 等安全漏洞
- 暴露的凭据和密钥
- 不安全的数据处理
- 认证与授权相关的问题`,
          tools: ["Read", "Grep", "Glob"],
          model: "sonnet",
        } as AgentDefinition,

        "test-analyzer": {
          description: "测试覆盖率与质量分析专家",
          prompt: `你是一名测试专家。请分析以下内容：
- 测试覆盖率缺口
- 缺失的边界用例
- 测试的质量与可靠性
- 对新增测试用例的建议`,
          tools: ["Read", "Grep", "Glob"],
          model: "haiku", // 使用更快的模型用于简单分析
        } as AgentDefinition,
      },
      hooks: {
        PreToolUse: [
          { hooks: [auditLogger] },
          { matcher: "Bash", hooks: [blockDangerousCommands] },
        ],
      },
    },
  })) {
    switch (message.type) {
      case "system":
        if (message.subtype === "init") {
          sessionId = message.session_id;
          console.log("Session ID:", sessionId);
          console.log("Available tools:", message.tools);
        }
        break;
      case "assistant":
        for (const block of message.message.content) {
          if ("text" in block) {
            console.log(block.text);
          } else if ("name" in block && block.name === "Task") {
            console.log(
              `\n🤖 正在委托给: ${(block.input as any).subagent_type}`
            );
          }
        }
        break;
      case "result":
        if (message.subtype === "success") {
          const review = message.structured_output as {
            issues: Array<{
              severity: string;
              category: string;
              file: string;
              line?: number;
              description: string;
              suggestion?: string;
            }>;
            summary: string;
            overallScore: number;
          };

          console.log(`\n📊 Code Review Results\n`);
          console.log(`Score: ${review.overallScore}/100`);
          console.log(`Summary: ${review.summary}\n`);

          for (const issue of review.issues) {
            const icon =
              issue.severity === "critical"
                ? "🔴"
                : issue.severity === "high"
                ? "🟠"
                : issue.severity === "medium"
                ? "🟡"
                : "🟢";
            console.log(
              `${icon} [${issue.category.toUpperCase()}] ${issue.file}${
                issue.line ? `:${issue.line}` : ""
              }`
            );
            console.log(`   ${issue.description}`);
            if (issue.suggestion) {
              console.log(`   💡 ${issue.suggestion}`);
            }
            console.log(
              `\n✅ Review complete! Cost: $${message.total_cost_usd.toFixed(
                4
              )}`
            );
          }
        } else {
          console.log(`\n❌ Review failed: ${message.subtype}`);
        }
    }
  }

  if (sessionId) {
    for await (const message of query({
      prompt: "现在展示如何修复最严重的漏洞",
      options: {
        resume: sessionId, // Continue the conversation
        allowedTools: ["Read", "Glob", "Grep"],
        maxTurns: 250,
      },
    })) {
      switch (message.type) {
        case "system":
          if (message.subtype === "init") {
            sessionId = message.session_id;
            console.log("Session ID:", sessionId);
            console.log("Available tools:", message.tools);
          }
          break;
        case "assistant":
          for (const block of message.message.content) {
            if ("text" in block) {
              console.log(block.text);
            }
          }
          break;
        case "result":
          if (message.subtype === "success") {
            console.log("Total cost:", message.total_cost_usd);
            console.log("Token usage:", message.usage);

            // Per-model breakdown (useful with subagents)
            for (const [model, usage] of Object.entries(message.modelUsage)) {
              console.log(`${model}: $${usage.costUSD.toFixed(4)}`);
            }
          } else {
            console.log("修复失败", message.subtype);
          }
          break;
      }
    }
  }
}

// async function codeMetrics() {
//   for await (const message of query({
//     prompt: generateMessages(),
//     options: {
//       model: "opus",
//       mcpServers: {
//         "code-metrics": customServer,
//       },
//       allowedTools: ["Read", "mcp__code-metrics__analyze_complexity"],
//       maxTurns: 250,
//     },
//   })) {
//   }
// }
async function main() {
  reviewCode(".");
}

main();

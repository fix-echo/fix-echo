import { query } from "@anthropic-ai/claude-agent-sdk";

async function main() {
  for await (const message of query({
    prompt: "这个项目是干什么的？",
    options: {
      allowedTools: ["Glob", "Read"],
      maxTurns: 250,
    },
  })) {
    switch (message.type) {
      case "system":
        if (message.subtype === "init") {
          console.log("Session ID:", message.session_id);
          console.log("Available tools:", message.tools);
        }
        break;
      case "assistant":
        for (const block of message.message.content) {
          if ("text" in block) {
            console.log("Claude:", block.text);
          } else if ("name" in block) {
            console.log("Tool:", block.name);
          }
        }
        break;
      case "result":
        console.log("Status:", message.subtype);
        console.log("Cost:", message.total_cost_usd);
        break;
    }
  }
}

main();

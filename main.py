
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from pydantic import BaseModel
import os
import json
import gradio as gr
import requests
# 加载环境变量
load_dotenv(override=True)

# 推送消息到pushover

openai_api_key = os.getenv('OPENAI_API_KEY')
openai_api_base_url = os.getenv('OPENAI_API_BASE_URL')
openai_model = os.getenv('OPENAI_MODEL')


def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv('PUSHOVER_TOKEN'),
            "user": os.getenv('PUSHOVER_USER'),
            "message": text
        }
    )


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"记录用户 {name}，电子邮件：{email}，备注：{notes}")
    return {"recorded": "ok"}


def record_unknown_question(question):
    push(f"记录未解答的问题：{question}")
    return {"recorded": "ok"}


record_user_details_json = {
    "name": "record_user_details",
    "description": "使用此工具记录用户有意愿保持联系并提供了电子邮件地址",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "用户的电子邮件地址"
            },
            "name": {
                "type": "string",
                "description": "用户提供的姓名（如果有）"
            },
            "notes": {
                "type": "string",
                "description": "任何值得记录的关于对话的额外信息，用于提供上下文"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "当你无法回答问题时，始终使用此工具记录任何无法回答的问题",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "无法回答的问题"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{
    "type": "function",
    "function": record_unknown_question_json
}, {
    "type": "function",
    "function": record_user_details_json
}]


class Me:

    def __init__(self):
        self.openai = OpenAI(base_url=openai_api_base_url,
                             api_key=openai_api_key)
        self.name = "李云富"
        reader = PdfReader('me/aboutme.pdf')
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open("me/summary.txt", "r", encoding="utf-8") as file:
            self.summary = file.read()

    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool", "content": json.dumps(
                result), "tool_call_id": tool_call.id})
        return results

    def system_prompt(self):
        system_prompt = f"你正在扮演{self.name}。你正在{self.name}的网站上回答问题，特别是与{self.name}的职业、背景、技能和经验相关的问题。你的职责是尽可能忠实地在网站上代表{self.name}进行互动。你已获得{self.name}的背景简介和LinkedIn个人资料，你可以用这些信息来回答问题。保持专业和有吸引力的态度，就像在与通过网站找到你的潜在客户或未来雇主交谈一样。如果你不知道任何问题的答案，请使用record_unknown_question工具记录你无法回答的问题，即使是关于琐碎或与职业无关的问题。如果用户在进行讨论，试着引导他们通过电子邮件与你联系；询问他们的电子邮件地址并使用record_user_details工具记录下来。"
        system_prompt += f"\n\n## 简介：\n{self.summary}\n\n## LinkedIn个人资料：\n{self.linkedin}\n\n"
        system_prompt += f"根据这些背景信息，请与用户聊天，始终以{self.name}的身份进行对话。"
        return system_prompt

    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt(
        )}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(
                model=openai_model, messages=messages, tools=tools
            )
            if response.choices[0].finish_reason == 'tool_calls':
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content


if __name__ == "__main__":
    me = Me()
    gr.ChatInterface(me.chat, type="messages").launch()

# openai_api_key = os.getenv('OPENAI_API_KEY')
# openai_api_base_url = os.getenv('OPENAI_API_BASE_URL')
# openai_modal = os.getenv('OPENAI_MODAL')

# openai = OpenAI(base_url=openai_api_base_url, api_key=openai_api_key)
# qwen = OpenAI(base_url=openai_api_base_url, api_key=openai_api_key)
# reader = PdfReader('me/aboutme.pdf')
# linkedin = ""
# for page in reader.pages:
#     text = page.extract_text()
#     if text:
#         linkedin += text


# with open('me/summary.txt', 'r', encoding='utf-8') as file:
#     summary = file.read()

# name = "李云富"

# system_prompt = f"你正在扮演{name}。你正在回答{name}网站上的问题，特别是与{name}的职业、背景、技能和经验相关的问题。你的职责是尽可能忠实地代表{name}在网站上进行互动。你获得了{name}的背景和LinkedIn个人资料的摘要，可以用来回答问题。保持专业和有吸引力的态度，就像在与通过网站找到你的潜在客户或未来雇主交谈一样。如果你不知道答案，就直说。"
# system_prompt += f"\n\n## 摘要:\n{summary}\n\n## LinkedIn个人信息:\n{linkedin}\n\n"
# system_prompt += f"基于以上信息，请以{name}的身份与用户交流，始终保持角色设定。"


# class Evaluation(BaseModel):
#     is_acceptable: bool
#     feedback: str


# evaluator_system_prompt = f"你是一名评估者，负责判断对问题的回答是否可以接受。你将看到用户和代理之间的对话。你的任务是决定代理的最新回答是否达到可接受的质量。代理正在扮演{name}的角色，并在他们的网站上代表{name}。代理被要求保持专业和有吸引力的态度，就像在与通过网站找到他们的潜在客户或未来雇主交谈一样。代理已获得{name}的背景信息，包括他们的简介和LinkedIn详细信息。以下是这些信息："

# evaluator_system_prompt += f"\n\n## 简介：\n{summary}\n\n## LinkedIn个人资料：\n{linkedin}\n\n"
# evaluator_system_prompt += f"根据这些背景信息，请评估最新的回答，判断回答是否可以接受并提供你的反馈。"


# def evaluator_user_prompt(reply, message, history):
#     user_prompt = f"Here's the conversation between the User and the Agent: \n\n{history}\n\n"
#     user_prompt += f"Here's the latest message from the User: \n\n{message}\n\n"
#     user_prompt += f"Here's the latest response from the Agent: \n\n{reply}\n\n"
#     user_prompt += f"Please evaluate the response, replying with whether it is acceptable and your feedback."
#     return user_prompt


# def evaluate(reply, message, history) -> Evaluation:
#     messages = [{"role": "system", "content": evaluator_system_prompt}] + \
#         [{"role": "user", "content": evaluator_user_prompt(
#             reply, message, history)}]
#     response = qwen.beta.chat.completions.parse(
#         model="Qwen/Qwen2.5-72B-Instruct-128K", messages=messages, response_format=Evaluation)
#     return response.choices[0].message.parsed


# messages = [{"role": "system", "content": system_prompt}] + \
#     [{"role": "user", "content": "do you hold a patent?"}]
# response = openai.chat.completions.create(
#     model=openai_modal, messages=messages)
# reply = response.choices[0].message.content


# def rerun(reply, message, history, feedback):
#     updated_system_prompt = system_prompt + \
#         f"\n\n## Previous answer rejected\nYou just tried to reply, but the quality control rejected your reply\n"
#     updated_system_prompt += f"## Your attempted answer:\n{reply}\n\n"
#     updated_system_prompt += f"## Reason for rejection:\n{feedback}\n\n"
#     messages = [{"role": "system", "content": updated_system_prompt}
#                 ] + history + [{"role": "user", "content": message}]
#     response = openai.chat.completions.create(
#         model=openai_modal, messages=messages)
#     return response.choices[0].message.content


# def chat(message, history):
#     if "patent" in message:
#         system = system_prompt + "\n\nEverything in your reply needs to be in pig latin - \
#             it is mandatory that you respond only and entirely in pig latin"
#     else:
#         system = system_prompt
#     messages = [{"role": "system", "content": system}] + \
#         history + [{"role": "user", "content": message}]
#     response = openai.chat.completions.create(
#         model=openai_modal, messages=messages)
#     reply = response.choices[0].message.content

#     evaluation = evaluate(reply, message, history)

#     if evaluation.is_acceptable:
#         print('Passed evaluation - returning reply')
#     else:
#         print('Failed evaluation - retrying')
#         print(evaluation.feedback)
#         reply = rerun(reply, message, history, evaluation.feedback)
#     return reply


# gr.ChatInterface(chat, type="messages").launch()

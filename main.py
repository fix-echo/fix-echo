import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from IPython.display import Markdown, display
import gradio as gr
from pydantic import BaseModel

# 加载环境变量
load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')
openai_api_base_url = os.getenv('OPENAI_API_BASE_URL')
openai_modal = os.getenv('OPENAI_MODAL')

openai = OpenAI(base_url=openai_api_base_url, api_key=openai_api_key)
qwen = OpenAI(base_url=openai_api_base_url, api_key=openai_api_key)
reader = PdfReader('me/aboutme.pdf')
linkedin = ""
for page in reader.pages:
    text = page.extract_text()
    if text:
        linkedin += text


with open('me/summary.txt', 'r', encoding='utf-8') as file:
    summary = file.read()

name = "李云富"

system_prompt = f"你正在扮演{name}。你正在回答{name}网站上的问题，特别是与{name}的职业、背景、技能和经验相关的问题。你的职责是尽可能忠实地代表{name}在网站上进行互动。你获得了{name}的背景和LinkedIn个人资料的摘要，可以用来回答问题。保持专业和有吸引力的态度，就像在与通过网站找到你的潜在客户或未来雇主交谈一样。如果你不知道答案，就直说。"
system_prompt += f"\n\n## 摘要:\n{summary}\n\n## LinkedIn个人信息:\n{linkedin}\n\n"
system_prompt += f"基于以上信息，请以{name}的身份与用户交流，始终保持角色设定。"


class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str


evaluator_system_prompt = f"你是一名评估者，负责判断对问题的回答是否可以接受。你将看到用户和代理之间的对话。你的任务是决定代理的最新回答是否达到可接受的质量。代理正在扮演{name}的角色，并在他们的网站上代表{name}。代理被要求保持专业和有吸引力的态度，就像在与通过网站找到他们的潜在客户或未来雇主交谈一样。代理已获得{name}的背景信息，包括他们的简介和LinkedIn详细信息。以下是这些信息："

evaluator_system_prompt += f"\n\n## 简介：\n{summary}\n\n## LinkedIn个人资料：\n{linkedin}\n\n"
evaluator_system_prompt += f"根据这些背景信息，请评估最新的回答，判断回答是否可以接受并提供你的反馈。"


def evaluator_user_prompt(reply, message, history):
    user_prompt = f"Here's the conversation between the User and the Agent: \n\n{history}\n\n"
    user_prompt += f"Here's the latest message from the User: \n\n{message}\n\n"
    user_prompt += f"Here's the latest response from the Agent: \n\n{reply}\n\n"
    user_prompt += f"Please evaluate the response, replying with whether it is acceptable and your feedback."
    return user_prompt


def evaluate(reply, message, history) -> Evaluation:
    messages = [{"role": "system", "content": evaluator_system_prompt}] + \
        [{"role": "user", "content": evaluator_user_prompt(
            reply, message, history)}]
    response = qwen.beta.chat.completions.parse(
        model="Qwen/Qwen2.5-72B-Instruct-128K", messages=messages, response_format=Evaluation)
    return response.choices[0].message.parsed


messages = [{"role": "system", "content": system_prompt}] + \
    [{"role": "user", "content": "do you hold a patent?"}]
response = openai.chat.completions.create(
    model=openai_modal, messages=messages)
reply = response.choices[0].message.content


def rerun(reply, message, history, feedback):
    updated_system_prompt = system_prompt + \
        f"\n\n## Previous answer rejected\nYou just tried to reply, but the quality control rejected your reply\n"
    updated_system_prompt += f"## Your attempted answer:\n{reply}\n\n"
    updated_system_prompt += f"## Reason for rejection:\n{feedback}\n\n"
    messages = [{"role": "system", "content": updated_system_prompt}
                ] + history + [{"role": "user", "content": message}]
    response = openai.chat.completions.create(
        model=openai_modal, messages=messages)
    return response.choices[0].message.content


def chat(message, history):
    if "patent" in message:
        system = system_prompt + "\n\nEverything in your reply needs to be in pig latin - \
            it is mandatory that you respond only and entirely in pig latin"
    else:
        system = system_prompt
    messages = [{"role": "system", "content": system}] + \
        history + [{"role": "user", "content": message}]
    response = openai.chat.completions.create(
        model=openai_modal, messages=messages)
    reply = response.choices[0].message.content

    evaluation = evaluate(reply, message, history)

    if evaluation.is_acceptable:
        print('Passed evaluation - returning reply')
    else:
        print('Failed evaluation - retrying')
        print(evaluation.feedback)
        reply = rerun(reply, message, history, evaluation.feedback)
    return reply


gr.ChatInterface(chat, type="messages").launch()

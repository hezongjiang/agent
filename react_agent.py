import inspect
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from agent import CHAT_COMPLETIONS_API_KEY, CHAT_COMPLETIONS_URL
from tools import read_file, run_terminal_command, write_to_file

DEFAULT_MODEL = "deepseek-chat"


class DeepSeekClient:
    """封装最薄的一层 DeepSeek Chat Completions API 调用。"""
    def __init__(self, model: str):
        self.model = model
        self.api_key = CHAT_COMPLETIONS_API_KEY

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """请求 DeepSeek，并返回 choices[0].message。"""
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        print("\n正在请求 DeepSeek 模型...")
        response = requests.post(
            CHAT_COMPLETIONS_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            json=body,
            timeout=600,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"DeepSeek HTTP 请求失败：{response.status_code} {response.text}") from exc

        try:
            payload = response.json()
            return payload["choices"][0]["message"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"DeepSeek 返回结构不符合预期：{response.text}") from exc


class ReactAgent:
    """使用 DeepSeek 原生 tool_calls 机制实现的最小 Agent 示例。"""

    def __init__(self, tools: List[Callable], model: DeepSeekClient, project_directory: str):
        self.tools = {tool.__name__: tool for tool in tools}
        self.model = model
        self.project_directory = os.path.abspath(project_directory)

    def run(self, user_input: str) -> str:
        """启动一轮对话，直到模型给出最终自然语言回答。"""
        messages = [
            {"role": "system", "content": self.build_system_prompt()},
            {"role": "user", "content": user_input},
        ]

        while True:
            message = self.model.chat(messages, tools=self.build_tool_schemas())
            tool_calls = message.get("tool_calls") or []
            content = message.get("content") or ""

            # 没有工具调用时，说明模型已经决定直接回答用户。
            if not tool_calls:
                return content.strip()

            # 有工具调用时，必须先保存 assistant 原始消息，再追加每个工具的执行结果。
            messages.append(message)
            for tool_call in tool_calls:
                tool_name, arguments = self.parse_tool_call(tool_call)
                print(f"\n模型请求调用工具：{tool_name}({arguments})")

                observation = self.execute_tool(tool_name, arguments)
                print(f"工具返回结果：{observation}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": observation,
                })

    def build_system_prompt(self) -> str:
        """构造尽量简单的系统提示，重点让模型知道工具边界和工作目录。"""
        return (
            "你是一个智能助手，能够使用工具完成任务。\n"
            "当你需要读取文件、写入文件或执行终端命令时，请使用 API 提供的工具调用机制。\n"
            "不要在普通文本里伪造工具调用结果。\n"
            f"所有文件操作都应限制在这个目录内：{self.project_directory}\n"
            "如果不需要工具，直接用自然语言回答用户。"
        )

    def build_tool_schemas(self) -> List[Dict[str, Any]]:
        """把普通 Python 函数转换成 function tool schema。"""
        schemas = []
        for tool in self.tools.values():
            signature = inspect.signature(tool)
            properties = {}
            required = []

            for param_name, param in signature.parameters.items():
                properties[param_name] = {
                    "type": "string",
                    "description": f"{param_name} 参数",
                }
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.__name__,
                    "description": inspect.getdoc(tool) or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return schemas

    def parse_tool_call(self, tool_call: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """解析模型返回的 tool_call，得到要执行的函数名和参数字典。"""
        try:
            function_call = tool_call["function"]
            tool_name = function_call["name"]
            arguments = json.loads(function_call.get("arguments") or "{}")
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"无法解析 tool_call：{tool_call}") from exc

        if tool_name not in self.tools:
            raise RuntimeError(f"模型请求了未注册的工具：{tool_name}")
        if not isinstance(arguments, dict):
            raise RuntimeError(f"tool_call arguments 必须是 JSON 对象：{tool_call}")

        return tool_name, arguments

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """执行本地工具函数，并把异常也转成文本返回给模型。"""
        if tool_name == "run_terminal_command":
            should_continue = input("模型想执行终端命令，是否允许？（Y/N）：")
            if should_continue.lower() != "y":
                return "用户拒绝执行终端命令。"
        try:
            result = self.tools[tool_name](**arguments)
        except Exception as exc:
            return f"工具执行失败：{exc}"

        return str(result)


if __name__ == "__main__":
    project_dir = os.path.abspath("snack")
    model_name = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)

    model = DeepSeekClient(model_name)
    agent = ReactAgent(
        tools=[read_file, write_to_file, run_terminal_command],
        model=model,
        project_directory=project_dir,
    )

    task = "使用html、js、css写一个贪吃蛇小游戏"
    final_answer = agent.run(task)
    print(f"\n最终回答：{final_answer}")

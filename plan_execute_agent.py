import json
import os
from typing import List, Tuple

from react_agent import DeepSeekClient, ReactAgent
from tools import read_file, run_terminal_command, write_to_file


DEFAULT_MODEL = "deepseek-chat"


class PlannerAgent:
    """负责把用户任务拆成少量可执行步骤。"""

    def __init__(self, client: DeepSeekClient):
        self.client = client

    def make_plan(self, task: str) -> List[str]:
        """生成初始计划，返回字符串步骤列表。"""
        prompt = f"""
请把用户任务拆成 3 到 6 个可以逐步执行的步骤。
只输出 JSON，不要输出额外内容。

输出格式：
{{
  "steps": ["步骤1", "步骤2"]
}}

用户任务：{task}
"""
        print("\n正在生成计划...")
        message = self.client.chat([{"role": "user", "content": prompt}])
        data = json.loads(message.get("content") or "{}")
        steps = data.get("steps")
        if not isinstance(steps, list) or not all(isinstance(step, str) and step.strip() for step in steps):
            raise RuntimeError(f"计划格式不正确：{data}")
        return [step.strip() for step in steps]


class PlanAndExecuteAgent:
    """把 Planner 和 Executor 串起来，形成最小 Plan and Execute Agent。"""

    def __init__(self, planner: PlannerAgent, executor: ReactAgent, client: DeepSeekClient):
        self.planner = planner
        self.executor = executor
        self.client = client

    def run(self, task: str) -> str:
        """先规划，再按步骤执行，最后汇总为最终答案。"""
        steps = self.planner.make_plan(task)
        print("\n计划如下：")
        for index, step in enumerate(steps, start=1):
            print(f"{index}. {step}")

        results: List[Tuple[str, str]] = []
        for index, step in enumerate(steps, start=1):
            print(f"\n开始执行第 {index} 步：{step}")
            result = self.executor.run(self.build_step_input(task, step, results))
            print(f"第 {index} 步结果：{result}")
            results.append((step, result))

        return self.summarize(task, results)

    def build_step_input(self, task: str, step: str, previous_results: List[Tuple[str, str]]) -> str:
        """把原始任务、当前步骤和历史结果整理成 SimpleToolAgent 的用户输入。"""
        if previous_results:
            history = "\n".join(
                f"- 已完成步骤：{done_step}\n  结果：{result}" for done_step, result in previous_results
            )
        else:
            history = "暂无"

        return (
            f"原始任务：{task}\n\n"
            f"当前步骤：{step}\n\n"
            f"之前步骤结果：\n{history}\n\n"
            "请只完成当前步骤，并在步骤完成后简短说明结果。"
        )

    def summarize(self, task: str, results: List[Tuple[str, str]]) -> str:
        """根据每一步执行结果，生成面向用户的最终回答。"""
        result_text = "\n".join(
            f"{index}. 步骤：{step}\n   结果：{result}" for index, (step, result) in enumerate(results, start=1)
        )
        prompt = (
            "你是 Plan and Execute Agent 的总结器。\n"
            "请根据执行记录给出最终答案，语言简洁。\n\n"
            f"用户原始任务：{task}\n\n"
            f"执行记录：\n{result_text}"
        )
        message = self.client.chat([{"role": "user", "content": prompt}])
        return (message.get("content") or "").strip()


if __name__ == "__main__":
    project_dir = os.path.abspath("snack")
    model_name = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    model = DeepSeekClient(model_name)

    planner = PlannerAgent(model)
    executor = ReactAgent(
        tools=[read_file, write_to_file, run_terminal_command],
        model=model,
        project_directory=project_dir,
    )
    agent = PlanAndExecuteAgent(planner, executor, model)

    task = "使用 html、css、js 写一个简单的贪吃蛇小游戏，文件放在 snack 目录中。"
    final_answer = agent.run(task)
    print(f"\n最终回答：{final_answer}")

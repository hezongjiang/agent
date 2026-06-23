import json
import os
from typing import List, Tuple, Any

from constants import DEFAULT_MODEL
from react_agent import DeepSeekClient, ReactAgent
from tools import read_file, run_terminal_command_with_confirm, write_to_file


class PlannerAgent:
    """负责把用户任务拆成多个可执行步骤。"""

    def __init__(self, client: DeepSeekClient):
        self.client = client

    def make_plan(self, task: str) -> List[str]:
        """生成初始计划，返回字符串步骤列表。"""
        prompt = f"""
你负责规划规划，负责把用户任务拆成可逐步执行的步骤。只输出 JSON，不要输出额外内容。
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


class StepEvaluator:
    """评估单步执行结果，判断是否通过，并给出反馈。"""

    def __init__(self, client):
        self.client = client

    def evaluate(self, task: str, step: str, result: str) -> dict[str, Any]:
        """
        返回示例：
        {
            "passed": True,
            "feedback": ""
        }
        """
        prompt = f"""
你负责任务执行评估。请根据原始任务、当前步骤和该步骤的执行结果，判断该步骤是否已成功完成。
输出 JSON，不要输出额外内容：
{{
  "passed": true/false,
  "feedback": "如果未通过，说明缺失什么或哪里不对；如果通过，填空字符串"
}}
原始任务：{task}
当前步骤：{step}
执行结果：{result}
"""
        message = self.client.chat([{"role": "user", "content": prompt}])
        try:
            data = json.loads(message.get("content") or "{}")
        except json.JSONDecodeError:
            data = {"passed": False, "feedback": "评估器返回格式错误"}
        return data


# ---------- 总结器 ----------
class FinalSummarizer:
    """根据所有步骤结果生成面向用户的最终回答。"""

    def __init__(self, client):
        self.client = client

    def summarize(self, task: str, results: List[Tuple[str, str]]) -> str:
        result_text = "\n".join(f"{i}. 步骤：{step}\n   结果：{result}" for i, (step, result) in enumerate(results, 1))
        prompt = (
            "你负责智能总结，根据执行记录给出最终结果。\n"
            f"用户原始任务：{task}\n"
            f"执行记录：\n{result_text}"
        )
        message = self.client.chat([{"role": "user", "content": prompt}])
        return (message.get("content") or "").strip()


# ---------- 编排器 ----------
class EvaluationOrchestrator:
    """评估型 Agent：每步执行后评估，不通过则重试，最后总结。"""

    def __init__(
        self,
        planner: PlannerAgent,
        executor: ReactAgent,                # ReactAgent
        evaluator: StepEvaluator,
        summarizer: FinalSummarizer,
        max_retries_per_step: int = 3,
    ):
        self.planner = planner
        self.executor = executor
        self.evaluator = evaluator
        self.summarizer = summarizer
        self.max_retries = max_retries_per_step

    def run(self, task: str) -> str:
        # 1. 制定计划
        steps = self.planner.make_plan(task)
        print("\n计划如下：")
        for i, step in enumerate(steps, 1):
            print(f"{i}. {step}")

        final_results: List[Tuple[str, str]] = []

        # 2. 逐步执行并评估
        for idx, step in enumerate(steps, 1):
            print(f"\n--- 开始执行第 {idx} 步：{step} ---")
            passed = False
            feedback = ""
            step_result = ""

            for attempt in range(1, self.max_retries + 1):
                # 构造输入（历史结果 + 上次反馈）
                step_input = self._build_step_input(task, step, final_results, feedback)
                step_result = self.executor.run(step_input)
                print(f"第 {attempt} 次尝试结果：{step_result}")

                evaluation = self.evaluator.evaluate(task, step, step_result)
                if evaluation.get("passed"):
                    passed = True
                    break
                else:
                    feedback = evaluation.get("feedback", "步骤未完成，请改进")
                    print(f"评估未通过，反馈：{feedback}")

            if not passed:
                print(f"警告：步骤 {idx} 在 {self.max_retries} 次重试后仍未通过，使用最后的结果继续。")

            final_results.append((step, step_result))

        # 3. 总结最终答案
        return self.summarizer.summarize(task, final_results)

    def _build_step_input(self, task: str, step: str,
                         previous_results: List[Tuple[str, str]],
                         feedback: str) -> str:
        if previous_results:
            history = "\n".join(f"- 已完成步骤：{done_step}\n  结果：{result}" for done_step, result in previous_results)
        else:
            history = "暂无"

        feedback_part = f"\n上一次尝试的反馈：{feedback}" if feedback else ""
        return (
            f"原始任务：{task}\n\n"
            f"当前步骤：{step}\n\n"
            f"之前步骤结果：\n{history}\n{feedback_part}\n\n"
            "请只完成当前步骤，并在步骤完成后简短说明结果。"
        )


if __name__ == "__main__":
    project_dir = os.path.abspath("task")
    # 大模型
    model_name = DEFAULT_MODEL
    model = DeepSeekClient(model_name)
    # 计划
    planner = PlannerAgent(model)
    # 执行
    executor = ReactAgent(
        tools=[read_file, write_to_file, run_terminal_command_with_confirm],
        model=model,
        project_directory=project_dir,
    )
    # 评估
    evaluator = StepEvaluator(model)
    # 总结
    summarizer = FinalSummarizer(model)
    # 调度
    agent = EvaluationOrchestrator(
        planner=planner,
        executor=executor,
        evaluator=evaluator,
        summarizer=summarizer,
        max_retries_per_step=3,
    )

    task = f"使用 html、css、js 写一个简单的贪吃蛇小游戏，文件放在 {project_dir} 目录中。"
    final_answer = agent.run(task)
    print(f"\n最终回答：{final_answer}")

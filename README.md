Agent 是一个随着大模型热潮兴起的重要概念。虽然Agent这个词现在被频繁提及，但它究竟是什么、如何运作，很多人其实并不清楚。

## 1、什么是 Agent

当前的大模型（如GPT-4o、DeepSeek等），虽具备强大的问答能力和逻辑推理能力，但存在一个明显局限：无法感知或改变外界环境。若让 GPT 帮你编写贪吃蛇游戏，它能生成完整代码，但代码写入文件、运行程序等操作，仍需人工完成——这就是大模型无法改变外界环境的体现。再比如，已有部分贪吃蛇代码，希望模型基于现有代码优化功能，就必须手动将代码复制给GPT，它无法主动获取这些外部信息，这则是大模型无法感知外界环境的表现。

要解决这一问题，只需为大模型配备对应的工具，比如读写文件、查看文件列表、运行终端命令等工具。这些工具就像是大模型的“感官”和“四肢”，有了它们，大模型就能自主查询已有文件、写入代码、运行程序，整个过程无需人工干预，实现完全自动化。将一个大模型与若干工具组合，打造出能感知、改变外界环境的智能程序，就是Agent。

![](https://upload-images.jianshu.io/upload_images/2708793-56d7b1d3e9959c89.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)

## 2、ReAct 模式的运行流程

Agent 的运行模式有多种，其中最知名、应用最广泛的是 ReAct（Reasoning and Acting，即“思考与行动”） 模式，是学习 Agent 绕不开的核心模式。该模式于 2022 年10月在  [ReAct: Synergizing Reasoning and Acting in Language Models](https://links.jianshu.com/go?to=https%3A%2F%2Farxiv.org%2Fabs%2F2210.03629) 论文提出，尽管至今已 4 年，但其提出的运行逻辑仍被广泛应用，堪称目前最主流的 Agent 运行模式。

ReAct 模式的运行流程清晰可循：
1. 首先用户提交任务，Agent 先进行思考 Thought，思考后判断是否需要调用工具；
2. 若需要，便调用合适的工具，如读写文件、查询信息等，这一步称为行动 Action；
3. 行动完成后，Agent 会查看工具的执行结果，如文件写入是否成功、查询到的内容是什么，这一步称为观察 Observation；
4. 观察结束后，Agent 再次思考，判断是否需要继续调用工具，若需要则重复“行动-观察-思考”的循环，直至认为无需再调用工具、可直接给出结论，此时输出最终答案 Final Answer，整个流程结束。

因此，ReAct 模式的核心步骤可总结为：Thought 思考、Action 行动、Observation 观察、Final Answer 最终答案，这几个关键步骤后续会频繁用到。

![](https://upload-images.jianshu.io/upload_images/2708793-6a885406c1288997.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)


## 3、ReAct 模式的实现原理

了解 ReAct 的流程后，核心问题是：这种“思考-行动-观察”的逻辑的如何实现？为何模型拿到任务后会先思考再行动，而非直接行动？核心奥秘集中在“系统提示词”上。

系统提示词是与用户问题一同发送给模型的指令，它规定了模型的角色、运行规则、环境信息等。举个简单例子：若在系统提示词中明确“回答必须包含两个XML标签，<question>存放用户问题，<answer>存放回答”，将该提示词与用户问题一同发给大模型，模型就会严格遵循这一规范输出结果。

若要让模型按照 ReAct 模式运行，系统提示词会更复杂，通常包含五个核心部分：职责描述、示例、可用工具、注意事项、环境信息。明确要求模型：解决任务时需将其分解为多个步骤，每个步骤先通过 Thought 思考要做什么，再通过 Action 调用工具，工具执行结果会以 Observation 返回，持续这一循环，直至拥有足够信息输出Final Answer。

简单来说，系统提示词就相当于给模型设定了一个“剧本”，模型会严格按照剧本逐步执行，这就是 ReAct 模式能够落地的核心原因。

## 4、动手实现一个 ReAct Agent

系统提示词是 ReAct 模式运行的关键，在此基础上搭配配套代码，就能搭建出一个可实际使用的 ReAct Agent。我们以“用HTML、CSS、JS实现贪吃蛇游戏”为任务，拆解Agent的实现过程。

首先看代码入口：tools 是可用工具列表，此处我们配置了三个核心工具，分别用于读取文件、写入文件、运行终端命令，本质上都是可直接调用的实用函数。


代码的核心是 ReAct Agent 类，构造该类时需传入三个参数：工具列表、所用模型、项目目录。构造完成后，获取 Agent 实例，提示用户输入任务，再将任务传入 Agent 的 run 函数——该函数是启动 Agent 的核心，前文提到的 Thought、Action、Observation、Final Answer，均在该函数内部依次处理，最终会输出 Final Answer 并显示在屏幕上。


重点解析run函数：该函数接收用户任务作为参数，内部先构建message列表，包含系统提示词和用户问题两部分。系统提示词通过render_system_prompt函数渲染，该函数会读取提示词模板，替换模板中的占位符（如工具列表、当前目录文件列表等），生成最终的系统提示词。

拼接完message列表后，调用call_model函数调用大模型，获取模型返回结果，提取其中的Thought并打印；随后判断Thought之后是否为Final Answer：若是，则返回Final Answer，函数执行结束；若不是，则解析出Action中的函数名和参数列表。需要注意的是，若Action调用的是运行终端命令的工具，会提示用户确认是否执行（因终端命令存在安全风险，编程类Agent通常会增加这一校验步骤）。

工具执行完成后，将执行结果存入Observation，并添加到message列表中。由于整个流程处于while循环中，会再次回到循环开头，将更新后的message列表传入call_model函数，让模型根据Observation判断下一步操作。这一循环会持续进行，直至模型返回Final Answer——这正是ReAct模式的核心逻辑。

## 5、ReAct 运行时序图

为彻底理解 ReAct Agent 的运行逻辑，我们通过时序图梳理各角色的交互过程。时序图中包含两个核心角色：用户和 Agent；其中 Agent 又分为三个部分：模型、工具（函数）、Agent 主程序。Agent主程序是串联整个流程的核心逻辑，负责在合适的时机调用模型和工具，可理解为前文代码中的 run 函数。

![](https://upload-images.jianshu.io/upload_images/2708793-fe480855ef7e58de.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)


完整交互流程如下：
1. 用户提交任务后，任务首先传递给Agent主程序；
2. Agent主程序调用模型，模型返回Thought和Action；
3. Agent主程序将Thought和Action展示给用户，再调用Action指定的工具；
4. 工具执行完成后返回结果，Agent主程序将结果展示给用户，并将该结果作为Observation加入历史消息列表；
5. 随后重复“调用模型-处理Thought和Action-执行工具-记录Observation”的循环，直至模型判断任务已完成、无需再调用工具，此时返回Thought和Final Answer；
6. Agent主程序将Thought和Final Answer展示给用户，整个流程结束。

![](https://upload-images.jianshu.io/upload_images/2708793-5eed812038f51127.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)


## 6、Plan-And-Execute 模式介绍

ReAct 模式是目前最常见、应用最广泛的 Agent 构建模式，但并非唯一方案。除 ReAct 外，还有许多“先规划、再执行”的 Agent 运行模式，其回答时会先构建待办列表，后续执行均遵循该列表；Claude Code中也经常出现“先创建To-Do列表、再逐步执行”的逻辑。

我们通过时序图梳理Plan-And-Execute模式的运行流程，首先明确该模式中Agent的组成模块：Plan模型（负责生成初始执行计划）、Replan模型（负责根据执行结果动态调整计划）、执行Agent（负责执行计划中的每一步）、Agent主程序（串联整个流程）。需要说明的是，Plan模型和Replan模型可选用同一个大模型，也可分开使用；执行Agent可采用前文讲解的ReAct模式（内置对应工具，如网络搜索工具），也可采用其他运行模式，Plan-And-Execute模式仅要求执行Agent能完成指定步骤，不限制其内部实现。

![](https://upload-images.jianshu.io/upload_images/2708793-6c9403fc31621aba.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)


以“查询今年澳网男子冠军的家乡”为例，完整运行流程如下：用户将问题提交给Agent主程序；Agent主程序将问题发送给Plan模型，生成初始执行计划（示例：1. 查询当前日期；2. 根据当前日期查询对应年份的澳网男子冠军姓名；3. 根据冠军姓名查询其家乡）；Agent主程序将初始计划传递给执行Agent，执行Agent完成第一步（查询当前日期）并返回结果；Agent主程序将用户问题、初始计划、执行记录（第一步结果）发送给Replan模型，Replan模型生成新的执行计划（删除已完成的“查询当前日期”步骤，将“查询对应年份冠军姓名”优化为“查询具体年份（如2025年）澳网男子冠军姓名”）；随后重复“执行Agent执行计划第一步- Replan模型生成新计划”的循环，直至所有步骤执行完毕。

具体循环过程可分为三轮：第一轮，执行“查询当前日期”，Replan模型生成优化后的计划；第二轮，执行“查询具体年份澳网男子冠军姓名”，Replan模型生成仅包含“查询冠军家乡”的计划；第三轮，执行“查询冠军家乡”，Replan模型判断所有步骤已完成，不再生成新计划，而是返回最终答案；Agent主程序将最终答案转发给用户，流程结束。

需注意，Replan模型的返回结果有两种可能：若仍有步骤未执行，返回新的执行计划；若所有步骤已完成、用户问题可解答，返回最终答案——这是Plan-And-Execute模式的核心特点，也是其灵活性的体现。至此，相信大家已清晰掌握Plan-And-Execute模式的运行逻辑。

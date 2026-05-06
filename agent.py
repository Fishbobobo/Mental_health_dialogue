"""
Agent Orchestrator — 替代 main.py 的状态机主循环。

使用 DashScope (Qwen, OpenAI-compatible API) 作为底层 LLM，
通过 tool call 驱动对话流程，让 LLM 自主决策下一个动作。
"""

from __future__ import annotations
import json
import threading
import time

from openai import OpenAI

from memory import load_user_memory, save_user_memory, memory_to_context
from tools import TOOLS
from tools.tool_handler import handle_tool_call

from sql_tool import (
    get_history_chat,
    filter_info,
    get_api,
    get_history_summary,
    update_history_summary,
    update_info,
)
from pool_config import Config

# ── API 客户端 ──────────────────────────────────────────────────────────

def _build_client(api_key: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


# ── 工具描述（动态注入 system prompt，保持同步） ───────────────────────

TOOLS_DESCRIPTION = """
### 回复工具（用于生成实际回复）
- **generate_chat_reply**：主要回复工具。生成符合当前对话阶段的回复。几乎所有的用户对话都应该使用这个工具
- **generate_symptom_reply**：当需要询问某个具体的 PHQ-9/GAD-7 症状问题时使用
- **generate_empathetic_reply**：当用户表达了中重度的情绪困扰时，生成共情探索性回复（不直接给建议）
- **generate_topic_reply**：围绕六大主题（家庭/学业/社交/学校/网络/自身）展开讨论时使用
- **generate_end_reply**：在适当的时机结束当前对话时使用

### 评估工具（后台用于追踪数据）
- **assess_symptom**：评估用户对某个 PHQ-9/GAD-7 问题的回答严重程度
- **select_next_symptom**：选择下一个症状问题
- **recognize_intent**：判断用户意图
- **search_topic**：判断用户话题是否匹配预定义主题
- **judge_topic**：评估用户在某话题上的困扰程度

### 记忆工具
- **read_user_memory**：查看用户完整状态
- **write_user_memory**：更新用户状态字段
- **update_conversation_summary**：更新对话摘要
"""

# ── System Prompt ───────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """你是盼达，一只温暖的心理陪伴熊猫，专为中小学生提供心理支持。

## 当前用户状态
{memory_context}

## 核心咨询原则（必须严格遵守）

### 原则一：少说多听
- 每轮回复**不超过 2 句话**，总字数控制在 **80 字以内**
- 多使用简短回应引导用户继续说："嗯""然后呢""能再多说说吗"
- 一句话表达共情/理解，第二句话提问引导
- 宁短勿长，你越少说，用户说得越多
- 如果用户的回答已经很长了，你的回复可以只回应一句"我明白了，然后呢？"或点头式回应

### 原则二：不是每次都要提问
- **如果不需要提问，就用陈述句**：共情、总结、点头式回应都是很好的回复
- 例如："嗯，我明白了" "听起来真的不容易" "你真的很努力了" —— 这些不需要问号
- **如果提问，只能问 1 个开放式问题**，且必须以问号（？）结尾
- 开放式问题示例："你觉得是什么让你有这种想法？" "你想要的理想状态是什么样的？"
- 封闭式问题示例："你是不是很难过？" "这件事让你很困扰吗？"——不要用

### 原则三：不直接给建议，引导探索
- **绝对不直接说"你应该…""我建议你…""你可以试试…"**——这不专业
- 通过提问引导用户自己找到答案："你觉得怎么做会让你感觉好一些？"
- 用户的感受应该是"我自己想通的"，而不是"盼达告诉我的"
- 只有当用户已经自己提出解决方案后，你才给予肯定和鼓励
- 如果想提供新的视角，用温和面质的方式："你刚才说…，但我观察到…，你觉得这之间有关系吗？"

### 原则四：避免重复句式
- **不要连续多轮用同样的句式开头**。如果你的回复总是"这件事…""听起来…""我感受到…"，用户会觉得很生硬
- 变化你的开头方式，善用不同句式：
  - 轻声回应："嗯…" "这样啊"
  - 重复关键词："考不好…"（接用户的词）
  - 直接说出感受："我感受到你…"
  - 简短肯定："你说得对" "确实不容易"
  - 比喻式表达："压力像背着一块大石头"
  - 直接总结："所以你最担心的其实是…"
- 每轮回复前，看看上一轮自己是怎样开头的，**至少换一种开头方式**
- 好的回复像真正的人在说话——有变化、有节奏、不机械

## 对话四阶段引导

### 阶段一：开场共情
- 目标：让用户感受到被接纳，愿意开口
- 引导用户描述**具体事件**和**内心感受**
- 不要急于进入问诊或症状评估
- 使用"听起来你…""我感受到你…"句式
- 如果用户是新用户或刚登录：先温暖问候，问"今天感觉怎么样？"

### 阶段二：深入探索
- 目标：帮助用户理清"发生了什么→我有什么感受→我为什么会有这种感受"
- 在用户表达情绪后引导深入
- 如果用户出现**抵触情绪**（如"不想说了""没什么"）：
  不说："没关系，不想说就不说。我就在这里陪着你，你想说的时候随时告诉我"
- 穿插轻松的**俏皮话**或回答用户的**百科问题**（对方是小学生）

### 阶段三：认知重构
- 目标：提供新视角，帮助用户重新看待问题
- 使用**温和面质**："你刚才说…，但我观察到…，你觉得这两者有关系吗？"
- 引导用户思考解决方案："如果有一个办法能让情况好一点点，你觉得会是什么？"
- 不要直接说"你应该换个角度看"——而是让用户自己发现

### 阶段四：结束总结
- 目标：在用户已经找到解决方案或情绪明显好转后总结
- 总结**用户自己发现**的解决方案，强化"是你自己想通的"的感受
- "今天我们的对话让我看到你很善于思考"
- **不是每轮都需要结束**——只有在合适的时机才结束
- 结束前检查一下所有需要评估的症状是否已经完成

## 穿插要求
- 整个过程中适时穿插轻松话题和俏皮话
- 如果用户问百科问题（如"为什么天是蓝的"），认真用简单的话回答
- 可以使用合适的 emoji 让对话更温暖
- 大约每 5 轮做一次简短的中期总结

## 可用工具
{TOOLS_DESCRIPTION}

## 重要规则
- 使用评估工具获取客观数据，但**不要在对话一开始就直接跳入问诊**
- 当检测到自杀风险时（Q9 ≥ 1），立即给予危机支持
- **必须使用一个 reply 工具生成最终回复**，不要直接输出文本
- 最常用的是 generate_chat_reply——它适用于绝大多数对话场景
"""


# ── 异步摘要 ────────────────────────────────────────────────────────────


def _async_update_summary(user_id: str, dialogue_history: list, api_key: str):
    """异步更新对话摘要。"""
    try:
        new_conn = Config.PYMYSQL_POOL.connection()
        new_cursor = new_conn.cursor()
        try:
            summary_before = get_history_summary(new_cursor, user_id)
            from generate_summary import summary
            new_summary = summary(summary_before, dialogue_history, api_key)
            if new_summary:
                update_history_summary(new_cursor, user_id, new_summary)
        finally:
            new_cursor.close()
            new_conn.close()
    except Exception as e:
        print(f"异步摘要生成错误: {e}", flush=True)


# ── 主 Agent 循环 ───────────────────────────────────────────────────────


def run_agent_turn(cursor, user_name: str) -> str:
    """
    执行一轮 agent 对话，返回 assistant 回复。

    替换 main.py 中的 dialogue_flow()。
    用户消息已由 app.py 存入数据库后再调用此函数。
    """
    start_time = time.time()
    print("Agent 开始处理对话...", flush=True)

    try:
        # 1. 加载 memory
        memory = load_user_memory(cursor, user_name)
        memory["turn_count"] += 1

        # 2. 获取对话历史（已包含用户最新消息）
        db_start = time.time()
        raw_dialogue = get_history_chat(cursor, user_name)
        # 截断至最近 20 轮
        raw_dialogue = raw_dialogue[-20:] if len(raw_dialogue) > 20 else raw_dialogue
        # 保留原始 OpenAI 消息格式用于 LLM
        messages = _to_openai_messages(raw_dialogue)
        # filter_info 格式用于传递给 tool handler（各模块期望的格式）
        filtered_dialogue = filter_info(raw_dialogue)
        api_key = get_api(cursor, user_name)
        summary_text = get_history_summary(cursor, user_name) or ""
        print(f"数据加载耗时: {time.time() - db_start:.2f}秒", flush=True)

        # 3. 注入 memory + tools 到 system prompt
        memory_context = memory_to_context(memory)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            memory_context=memory_context,
            TOOLS_DESCRIPTION=TOOLS_DESCRIPTION.strip(),
        )

        # 4. 构建 client
        client = _build_client(api_key)

        # 5. Agentic Loop
        final_reply = ""
        max_iterations = 8  # 防止无限循环
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            print(f"Agent Loop 迭代 #{iteration}", flush=True)

            response = client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "system", "content": system_prompt}] + messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1024,
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            # 纯文本回复 → 结束 loop
            if finish_reason == "stop":
                final_reply = choice.message.content or ""
                print(f"Agent 生成最终回复，共 {iteration} 轮迭代", flush=True)
                break

            # Tool call → 执行并继续
            if finish_reason == "tool_calls":
                tool_calls = choice.message.tool_calls
                assistant_msg = {"role": "assistant", "content": choice.message.content or "", "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in tool_calls
                ]}
                messages.append(assistant_msg)

                for tc in tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    print(f"  调用工具: {tool_name}, 参数: {tool_args}", flush=True)

                    # 为多数工具注入 recent_dialogue（filter_info 格式）
                    if "recent_dialogue" in _get_expected_params(tool_name):
                        tool_args.setdefault("recent_dialogue", json.dumps(filtered_dialogue, ensure_ascii=False))
                    if "summary" in _get_expected_params(tool_name):
                        tool_args.setdefault("summary", summary_text)
                    if "summary_before" in _get_expected_params(tool_name):
                        tool_args.setdefault("summary_before", summary_text)

                    result_text, memory = handle_tool_call(
                        tool_name, tool_args, memory, api_key, cursor
                    )
                    print(f"  工具结果: {result_text[:100]}", flush=True)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    })

                continue

            # 其他 finish_reason（如 length），直接退出
            print(f"Agent Loop 意外结束, finish_reason={finish_reason}", flush=True)
            if choice.message.content:
                final_reply = choice.message.content
            break

        if not final_reply:
            final_reply = "嗯，我明白了。你还有什么想和我聊聊的吗？"

        # 6. 保存 memory 到 MySQL
        save_user_memory(cursor, user_name, memory)

        # 7. 异步触发摘要（每 5 轮）
        if memory["turn_count"] % 5 == 0:
            threading.Thread(
                target=_async_update_summary,
                args=(user_name, filtered_dialogue, api_key),
                daemon=True,
            ).start()

        print(f"Agent 总耗时: {time.time() - start_time:.2f}秒", flush=True)
        return final_reply

    except Exception as e:
        print(f"Agent 处理出错: {e}, 耗时: {time.time() - start_time:.2f}秒", flush=True)
        raise


# ── 辅助函数 ─────────────────────────────────────────────────────────────


def _to_openai_messages(raw_dialogue: list[dict]) -> list[dict]:
    """
    将 SQL 中的 dialogue 格式转为 OpenAI messages 格式。

    SQL 格式：[{"role": "user", "content": "...", "type": "...", ...}, ...]
    → [{role: "user", content: "..."}, {role: "assistant", content: "..."}]
    """
    messages = []
    for item in raw_dialogue:
        role = item.get("role", "user")
        content = item.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    return messages


# 工具名称 → 所需参数名的映射（供自动注入用）
_EXPECTED_PARAMS: dict[str, set[str]] | None = None


def _get_expected_params(tool_name: str) -> set[str]:
    global _EXPECTED_PARAMS
    if _EXPECTED_PARAMS is None:
        _EXPECTED_PARAMS = {}
        from tools import TOOLS
        for t in TOOLS:
            func = t.get("function", t)
            name = func.get("name", "")
            props = func.get("parameters", {}).get("properties", {})
            _EXPECTED_PARAMS[name] = set(props.keys())
    return _EXPECTED_PARAMS.get(tool_name, set())

"""
Tool 执行分发：将 LLM 调用的 tool 请求分发给现有的独立模块。
"""

from __future__ import annotations
from typing import Any
import json

from memory import PHQ9_KEYS, GAD7_KEYS, memory_to_context

# 复用现有模块
from symptom_judge import symptom_judge
from symptom_select import symptom_select
from intent_recognize import intent_judge
from topic_search import topic_search
from topic_judge import topic_judge
from symptom_reply import symptom_ask_reply
from empathetic_reply import empathetic_reply
from chat_reply import chat_reply
from topic_reply import topic_reply
from end_reply import end_reply
from generate_summary import summary as generate_summary_fn


def handle_tool_call(
    tool_name: str,
    tool_args: dict[str, Any],
    memory: dict[str, Any],
    api_key: str,
    cursor=None,
) -> tuple[str, dict[str, Any]]:
    """
    执行 tool，返回 (结果文本, 更新后的 memory)。

    Parameters
    ----------
    tool_name : str
        工具名称（如 'assess_symptom'）
    tool_args : dict
        工具参数
    memory : dict
        当前 UserMemory
    api_key : str
        当前用户的 API key
    cursor :
        数据库 cursor（部分 tool 需要回写）

    Returns
    -------
    tuple[str, dict]
        (结果文本, 更新后的 memory)
    """

    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return f"未知工具: {tool_name}", memory

    return handler(tool_args, memory, api_key, cursor)


# ── 各 handler 实现 ─────────────────────────────────────────────────────


def _assess_symptom(args, memory, api_key, cursor):
    q_index = args["question_index"]
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)

    score = symptom_judge(q_index, dialogue_list, api_key)

    # 更新 memory
    if 1 <= q_index <= 9:
        key = f"Q{q_index}"
        memory["phq9_scores"][key] = score
        if q_index == 9 and score >= 1:
            memory["suicide_risk"] = True
    elif 10 <= q_index <= 13:
        key = f"Q{q_index}"
        memory["gad7_scores"][key] = score

    severity = { -1: "无法判断", 0: "无症状", 1: "轻度", 2: "中度", 3: "重度" }
    return f"问题 {q_index} 评估结果: {severity.get(score, str(score))}", memory


def _select_next_symptom(args, memory, api_key, cursor):
    if cursor is None:
        return "需要数据库连接才能获取未评估症状", memory

    from sql_tool import phq_gad_unfill_slot
    question_list = phq_gad_unfill_slot(cursor, memory["user_id"])

    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)

    chosen = symptom_select(dialogue_list, question_list, api_key)
    memory["current_question"] = chosen

    return f"选择的下一个症状问题编号: {chosen}", memory


def _recognize_intent(args, memory, api_key, cursor):
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)

    intent = intent_judge(dialogue_list, api_key)

    # 所有问题已评估完且用户无话题 → intent 3
    if intent == 0:
        from sql_tool import phq_num, gad_num
        if cursor:
            if phq_num(cursor, memory["user_id"]) == 0 and gad_num(cursor, memory["user_id"]) == 0:
                intent = 3

    intent_map = {0: "接受症状评估/无新话题", 1: "有想聊的话题/表达了情绪", 3: "无话题且所有症状已评估完"}
    return f"意图识别结果: {intent} ({intent_map.get(intent, '未知')})", memory


def _search_topic(args, memory, api_key, cursor):
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)

    topic_index, flag = topic_search(dialogue_list, api_key)

    result = f"话题匹配: {'是' if flag else '否'}"
    if flag:
        topic_names = ["家庭因素", "学业压力", "社交压力", "学校环境", "网络暴力", "自身因素"]
        result += f", 匹配话题: {topic_names[topic_index] if topic_index is not None else '未知'}"
        memory["current_topic"] = topic_index

    return result, memory


def _judge_topic(args, memory, api_key, cursor):
    topic_index = args["topic_index"]
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)

    judge = topic_judge(topic_index, dialogue_list, api_key)

    # 更新 memory
    key = f"t{topic_index + 1}"
    if key in memory["topic_scores"]:
        memory["topic_scores"][key] = judge

    result_map = { -1: "无法判断", 0: "无困扰", 1: "存在困扰" }
    return f"话题 {topic_index} 评估结果: {result_map.get(judge, str(judge))}", memory


def _generate_symptom_reply(args, memory, api_key, cursor):
    q_index = args["question_index"]
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)
    summary = args.get("summary", memory.get("summary", ""))

    reply = symptom_ask_reply(q_index, dialogue_list, summary, api_key)
    memory["current_question"] = q_index
    memory["phase"] = "assessment"

    return reply or "请问你能详细说说最近的情况吗？", memory


def _generate_empathetic_reply(args, memory, api_key, cursor):
    q_index = args["question_index"]
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)
    summary = args.get("summary", memory.get("summary", ""))

    reply = empathetic_reply(q_index, dialogue_list, summary, api_key)
    memory["phase"] = "free_chat"

    return reply or "我理解你的感受，这些情绪都是正常的。", memory


def _generate_topic_reply(args, memory, api_key, cursor):
    topic_index = args["topic_index"]
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)
    summary = args.get("summary", memory.get("summary", ""))

    reply = topic_reply(topic_index, dialogue_list, summary, api_key)
    memory["current_topic"] = topic_index
    memory["phase"] = "topic_discussion"

    return reply or f"我们来聊聊这个话题吧。", memory


def _generate_chat_reply(args, memory, api_key, cursor):
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)
    summary = args.get("summary", memory.get("summary", ""))

    reply = chat_reply(dialogue_list, summary, api_key)
    memory["phase"] = "free_chat"

    return reply or "嗯，我明白了，你继续说。", memory


def _generate_end_reply(args, memory, api_key, cursor):
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)

    reply = end_reply(dialogue_list, api_key)
    memory["phase"] = "ending"

    return reply or "今天的聊天就到这里吧，好好休息哦~", memory


def _read_user_memory(args, memory, api_key, cursor):
    return memory_to_context(memory), memory


def _write_user_memory(args, memory, api_key, cursor):
    updates = args.get("updates", {})
    for k, v in updates.items():
        if k in memory:
            memory[k] = v
    return f"memory 已更新: {json.dumps(updates, ensure_ascii=False)}", memory


def _update_conversation_summary(args, memory, api_key, cursor):
    dialogue_text = args.get("recent_dialogue", "")
    dialogue_list = _parse_dialogue_text(dialogue_text)
    summary_before = args.get("summary_before", memory.get("summary", ""))

    new_summary = generate_summary_fn(summary_before, dialogue_list, api_key)
    if new_summary:
        memory["summary"] = new_summary

    return f"对话摘要已更新", memory


# ── Handler 注册表 ──────────────────────────────────────────────────────

_TOOL_HANDLERS = {
    "assess_symptom": _assess_symptom,
    "select_next_symptom": _select_next_symptom,
    "recognize_intent": _recognize_intent,
    "search_topic": _search_topic,
    "judge_topic": _judge_topic,
    "generate_symptom_reply": _generate_symptom_reply,
    "generate_empathetic_reply": _generate_empathetic_reply,
    "generate_topic_reply": _generate_topic_reply,
    "generate_chat_reply": _generate_chat_reply,
    "generate_end_reply": _generate_end_reply,
    "read_user_memory": _read_user_memory,
    "write_user_memory": _write_user_memory,
    "update_conversation_summary": _update_conversation_summary,
}


# ── 工具函数 ─────────────────────────────────────────────────────────────


def _parse_dialogue_text(text: str) -> list[dict]:
    """
    将文本形式的对话历史解析为原有模块需要的 list[dict] 格式。
    支持 JSON 格式和简单的 role:content 文本格式。
    """
    text = text.strip()
    if not text:
        return []

    # 尝试 JSON 解析
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 回退：按行解析 "user: xxx" / "assistant: xxx"
    result = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        for role in ("user", "assistant"):
            prefix = f"{role}:"
            if line.startswith(prefix):
                result.append({role: line[len(prefix):].strip()})
                break
    return result

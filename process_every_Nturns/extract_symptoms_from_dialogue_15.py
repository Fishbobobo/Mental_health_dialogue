import ast

from public_tool import get_response_openai3
from generate_summary import generate_user_summary


def _extract_user_messages(dialogue_history):
    user_messages = []
    for item in dialogue_history:
        if isinstance(item, dict):
            if "user" in item:
                user_messages.append(item["user"])
            elif item.get("role") == "user" and item.get("content"):
                user_messages.append(item["content"])
    return user_messages


def _normalize_dialogue(dialogue_history):
    normalized = []
    for item in dialogue_history:
        if not isinstance(item, dict):
            continue
        if "user" in item or "assistant" in item:
            normalized.append(item)
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content:
            normalized.append({role: content})
    return normalized


def extract_symptoms_from_dialogue(dialogue_history, summary_before, api_key):
    normalized_dialogue = _normalize_dialogue(dialogue_history)
    user_messages = _extract_user_messages(normalized_dialogue)
    summary_text = generate_user_summary(summary_before, user_messages, api_key)

    instruction = """你是一名资深心理咨询师，请从以下用户信息中判断用户是否涉及到GAD-7和PHQ-9量表中的某些问题。你的任务如下：
        1. 判断用户描述是否与以下任一量表题目相关（无需涵盖全部，仅提及的即可）。
        2. 若有关，请严格按以下格式输出，不要有任何多余信息：
        PHQ-9量表题目：
            1.做事情时提不起劲或没有兴趣
            2.感到沮丧、郁闷或绝望
            3.入睡困难、睡不安稳或睡得太多
            4.感到疲倦或没有活力
            5.食欲不振或吃太多
            6.觉得自己很差，或让自己或家人失望
            7.难以集中注意力，例如看报纸或看电视时
            8.动作或说话速度缓慢到别人已经注意到；或相反，表现得坐立不安或烦躁
            9.有不如死掉或用某种方式伤害自己的念头
        GAD-7量表题目：
            10.感觉紧张，焦虑或急切
            11.不能停止或无法控制对很多事情担心
            12.变得容易烦恼或易被激怒
            13.感到好像有什么可怕的事会发生

        3. 若用户描述与以上任一量表的数个题目有关，请严格按以下格式输出，不要有任何多余信息：

        输出格式：
        [
         (序号, "症状描述")
        ]

        注意：
        - 序号范围只能是 1~13；
        - 如果没有关联项，请返回一个空列表；
        - 症状描述应为简洁明确的句子；
        - 不要额外输出任何注释或说明，仅返回标准 Python 列表。
    """
    prompt = f"""
        用户总结：{summary_text}
        用户消息：{user_messages}
        对话历史：{normalized_dialogue}
    """
    result = get_response_openai3(instruction, prompt, api_key)
    if not result:
        return []

    try:
        extracted = ast.literal_eval(result)
    except (ValueError, SyntaxError):
        return []

    if not isinstance(extracted, list):
        return []

    normalized = []
    for item in extracted:
        if (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and isinstance(item[0], int)
            and isinstance(item[1], str)
            and 1 <= item[0] <= 13
        ):
            normalized.append((item[0], item[1]))
    return normalized

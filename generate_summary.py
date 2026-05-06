from public_tool import get_response_openai3


def summary(summary_before, dialogue_history, api_key):
    # print("here")
    user_messages = filter_dialogue(dialogue_history)
    user_summary = generate_summary(summary_before, user_messages, api_key)
    return user_summary


def filter_dialogue(dialogue_history):
    user_messages = [item["user"] for item in dialogue_history if "user" in item]
    return user_messages


def generate_summary(summary_before, user_messages, api_key):
    user_summary = generate_user_summary(summary_before, user_messages, api_key)
    return user_summary


def instruction_and_prompt_intent_judge(user_summary_before, user_messages):
    instruction = """你是一名心理咨询师，请根据提供的用户历史消息总结和用户消息列表，分析并总结以下内容：

1. 主要主题（如学习压力、情绪表达等）
2. 高频关键词或情绪倾向（如负面情绪、简短回应等）
3. 用户潜在需求（如寻求支持、表达疲惫等）
4. 记录用户的日常习惯

要求：
1. 语言简洁，逻辑清晰
2. 忽略问候类消息（如‘你好’），专注问题表达
3. 去除重复信息
4. 字数严格控制在<三百字>以内

    """

    prompt = f"""
用户历史消息总结：{user_summary_before}
用户消息列表：{user_messages}
"""

    return instruction, prompt


def generate_user_summary(user_summary_before, user_messages, api_key):
    instruction, prompt = instruction_and_prompt_intent_judge(
        user_summary_before, user_messages
    )
    summary = get_response_openai3(instruction, prompt, api_key)
    print(summary)

    return summary

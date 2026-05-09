from public_tool import get_response_openai3
from generate_summary import generate_user_summary
from sql_tool import update_summary_phased_all


def _extract_user_messages(dialogue_history):
    user_messages = []
    for item in dialogue_history:
        if isinstance(item, dict):
            if "user" in item:
                user_messages.append(item["user"])
            elif item.get("role") == "user" and item.get("content"):
                user_messages.append(item["content"])
    return user_messages


def process_dialogue_and_update_db(dialogue_history, summary_before, api_key, user_id, cursor):
    recent_dialogue = dialogue_history[-20:]
    user_messages = _extract_user_messages(recent_dialogue)
    summary_text = generate_user_summary(summary_before, user_messages, api_key)

    keyword_instruction = """
        你是一位心理咨询师，请从以下对话中提取 1 到 5 个最能反映用户心理状态的关键词。
        关键词之间使用分号分隔，只返回关键词文本。
    """
    keyword_prompt = f"用户内容总结：{summary_text}\n用户发言：{user_messages}"
    keyword_list = (get_response_openai3(keyword_instruction, keyword_prompt, api_key) or "").strip()

    issues_instruction = """
        你是一位心理咨询师，请基于以下对话历史识别用户可能存在的主要心理问题。
        返回 1 到 5 条陈述句，每条以序号开头、分号结尾，总字数不超过 100 字。
    """
    issues_prompt = f"用户内容总结：{summary_text}\n用户发言：{user_messages}"
    issues_list = (get_response_openai3(issues_instruction, issues_prompt, api_key) or "").strip()

    advice_instruction = """
        你是一位心理咨询师，请根据以下用户对话生成最多 4 条简单明了的心理建议。
        每条建议以序号开头、分号结尾，总字数不超过 100 字。
    """
    advice_prompt = f"用户内容总结：{summary_text}\n识别出的心理问题：{issues_list}"
    suggestion_text = (get_response_openai3(advice_instruction, advice_prompt, api_key) or "").strip()

    update_summary_phased_all(
        cursor,
        user_id=user_id,
        summary_text=summary_text,
        keyword_list=keyword_list,
        problem_list=issues_list,
        suggestion_text=suggestion_text,
    )

from public_tool import get_response_openai3


def instruction_and_prompt_end_chat(dialogue_history):
    instruction = f"""你是一位关心中学生的学习聊天助手，任务是与学生进行对话，顺着学生的最后一句话进行自然回应。
你的目标是不再提出新问题，也不要引入新的话题，只需要对学生的话作出简短且认真的回应。
请注意：你的回复应当自然流畅，不要突然结束对话，而是通过鼓励、总结或情感反馈来回应学生的最后一句话，让对方感到你在认真聆听。
回复控制在一百字内，保持简洁明了，但也不要太短，注意逻辑流程，适合中学生理解。仅生成语言回复：请确保生成的内容完全是对话文本，不包含任何动作或行为描述。"""

    prompt = f"""
========== 
对话历史： 
{dialogue_history} 
========== 
请根据对话历史的最后一句生成一个简洁的回应。
避免引入新话题或提出新的问题，只需顺着学生的话回应，并确保对话自然流畅，逐步引导结束。
=========="""
    return instruction, prompt

def end_reply(dialogue_history, key):
    instruction, prompt = instruction_and_prompt_end_chat(dialogue_history)
    response_chat = get_response_openai3(instruction, prompt, key)
    # 返回该话题的对话回复
    return response_chat

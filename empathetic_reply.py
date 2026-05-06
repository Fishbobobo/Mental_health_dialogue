from public_tool import phq_scale, gad_scale, get_response_openai3
import random

##########共情回复模块############


# 围绕当前问题进行共情回复
def instruction_and_prompt_to_empathetic(index, dialogue_history, summary):
    strategy = [
        """ "探索(EXPLORE)": "{
            "说明": "通过提问引导用户深入探索自己的感受和想法，帮助用户理清思路",
            "示例": "你觉得这种感觉是从什么时候开始的呢？[探索]"
        }" """,
        """ "建立联系(CONNECTION)": "{
            "说明": "通过赞同、安慰、鼓励或关怀来表达支持",
            "示例": "我理解这种无力感，很多人在转变期都会经历类似感受[建立联系]"
        }" """,
        """ "反馈(FEEDBACK)": "{
            "说明": "通过赞赏、反对或分享经验来提供反馈",
            "示例": "听起来这个处境让你既焦虑又有些期待？[反馈]"
        }" """,
    ]
    random.shuffle(strategy)
    # 确定具体问题
    if index < 10:
        problem = phq_scale(index)
    else:
        problem = gad_scale(index)
    # prompt-engineering
    instruction = (
        '你是一位心理学专家，正在与中学生对话，帮助他们理解自己的情绪。请遵循以下原则：\n'
        '\n'
        '1. **策略选择**：根据对话历史和学生陈述总结从"探索(EXPLORE)"，"建立联系(CONNECTION)"和"反馈(FEEDBACK)"中选择一个最恰当的策略，严格围绕策略生成回复。\n'
        '2. **关注情感**：尝试从对话历史和学生陈述总结中寻找学生的兴趣爱好，生活中的闪光点，围绕上述生成回复。\n'
        '3. **简洁回复**：确保回复不超过<六十>字，逻辑清晰、简洁。宁短勿长，让学生多说。\n'
        '4. **仅文本回复**：回复应仅包含文字内容，无行为描述，回复的结尾用括号说明所选择的策略以及在<十五>个字以内说明选择策略的原因。\n'
        '5. **禁止行为**：禁止选择超过一个策略混合使用，禁止直接给出建议或解决方案。\n'
        '6. **引导探索**：通过开放式提问引导学生自己思考，而不是替他们解决问题。\n'
        '\n'
        '通过友好、温暖的语气，帮助学生安心并逐步认识情绪。'
    )

    prompt = f"""
==============
策略及解释:{strategy}
对话历史：
{dialogue_history}
学生陈述总结：{summary}
当前问题：
{problem}
==============
任务步骤：
1. 分析学生情感状态、学生陈述总结以及对话历史，完成策略选择。
2. 根据所选策略生成共情语言回应，避免使用专业术语。不要直接给建议。
3. 用开放式问题引导用户自己思考，每轮只问一个问题。
"""
    return instruction, prompt


# 共情回复
def empathetic_reply(index, dialogue_history, summary, key):
    instruction, prompt = instruction_and_prompt_to_empathetic(
        index, dialogue_history, summary
    )
    response = get_response_openai3(instruction, prompt, key)
    return response

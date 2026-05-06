from public_tool import get_response_openai3

#######话题回复模块###########


# 六个主题选择
def topics_scale(index):
    # 主题解释待考量
    list_topics = [
        "家庭因素：关注学生的家庭教育方式,家庭关系,与父母的沟通情况以及父母教育水平等方面",
        "学业压力：关注学习负担,考试焦虑,家长和教师的期望,同伴竞争,学习的时间管理等方面",
        "社交压力：关注同伴关系,社交技能,人际冲突,社交孤立等方面",
        "学校环境：关注校园安全,师生关系,课外活动,设施条件,学校文化和心理支持服务等方面",
        "网络暴力：关注网络欺凌,自身心理影响,应对策略以及家长学校校沟通等方面",
        "自身因素：关注自我认知,情绪管理,学习态度,心理健康,生活习惯和自我效能感等方面",
    ]
    return list_topics[index]


def topic_scale(index):
    list_topic = [
        "家庭因素",
        "学业压力",
        "社交压力",
        "学校环境",
        "网络暴力",
        "自身因素",
    ]
    return list_topic[index]


def instruction_and_prompt_to_topic(index, dialogue_history, summary):
    last_reply = dialogue_history[-1]["user"]
    topic = topic_scale(index)
    topics = topics_scale(index)

    instruction = f"""
你是一个关注中国初高中学生学习的聊天助手，与你的学生进行友好对话。你的任务是围绕主题“{topic}”展开对话，特别是“{topics}”。

指导原则：
1. **自然过渡**：确保话题衔接顺畅，避免突兀转变。
2. **主动引导**：从学生的最后回复中寻找线索，引导他们讨论相关话题。
3. **提供新见解**：避免重复，提供有价值的新信息。
4. **简洁明了**：回复控制在<八十>字以内，保持逻辑清晰。
5. **话题转折**：若需要切换话题，简要总结并自然过渡。
6. **纯文本回复**：仅生成对话文本，不包括动作或行为描述。

保持友好、开放的语气，让学生感到轻松愉快。

"""

    prompt = f"""==========
对话历史：
{dialogue_history}
学生陈述总结：
{summary}
==========
根据对话历史和学生陈述总结，构思一个自然的回复，确保流畅衔接，避免重复，并保持内容简洁明了。
==========

"""

    return instruction, prompt


def topic_reply(index, dialogue_history, summary, key):
    instruction, prompt = instruction_and_prompt_to_topic(
        index, dialogue_history, summary
    )
    response = get_response_openai3(instruction, prompt, key)
    return response



from public_tool import get_response_openai3, get_topic_score

#########话题诊断模块##########
list_topic = [
        "家庭因素", "学业压力", "社交压力", "学校环境", "网络暴力", "自身因素"
    ]

list_topics = [
        "家庭因素：关注学生的家庭教育方式,家庭关系,与父母的沟通情况以及父母教育水平等方面",
        "学业压力：关注学习负担,考试焦虑,家长和教师的期望,同伴竞争,学习的时间管理等方面",
        "社交压力：关注同伴关系,社交技能,人际冲突,社交孤立等方面",
        "学校环境：关注校园安全,师生关系,课外活动,设施条件,学校文化和心理支持服务等方面",
        "网络暴力：关注网络欺凌,自身心理影响,应对策略以及家长学校校沟通等方面",
        "自身因素：关注自我认知,情绪管理,学习态度,心理健康,生活习惯和自我效能感等方面"
    ]

# 对主题是否满足的判断
def instruction_and_prompt_topic_judge(topic_index, dialogue_history):
    topic = list_topic[topic_index]
    topic_problem = list_topics[topic_index]
    instruction = f"""
你是一个关注中国中小学生心理健康的心理医生，正在与学生对话。
请根据“对话历史”判断学生在“{topic}”方面的情况，并生成评价。
评价应严格按照给定标准进行，不包含额外信息。

评价标准：
- “无法判断”：无法判断
- “没有”：在该方面无困扰或影响
- “有”：在该方面存在困扰或影响

"""
    prompt = f"""
==========
对话历史：
{dialogue_history}

{topic} 具体描述：
{topic_problem}

判断标准：
- 无法判断
- 没有
- 有
==========
请根据上述信息，生成针对“{topic}”的评价，严格遵循判断标准。
"""
    return instruction, prompt

# 话题诊断
def topic_judge(topic_index, dialogue_history, key):
    instruction, prompt = instruction_and_prompt_topic_judge(topic_index, dialogue_history)
    # print(instruction, prompt)

    response_judge = get_response_openai3(instruction, prompt, key)
    # print("openai返回主题判断结果：", response_judge)
    # 结果映射
    judge = get_topic_score(response_judge)
    return judge

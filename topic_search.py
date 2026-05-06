from public_tool import get_response_openai3

#######话题检索模块#########

list_topics = [
        "家庭因素：关注学生的家庭教育方式,家庭关系,与父母的沟通情况以及父母教育水平等方面",
        "学业压力：关注学习负担,考试焦虑,家长和教师的期望,同伴竞争,学习的时间管理等方面",
        "社交压力：关注同伴关系,社交技能,人际冲突,社交孤立等方面",
        "学校环境：关注校园安全,师生关系,课外活动,设施条件,学校文化和心理支持服务等方面",
        "网络暴力：关注网络欺凌,自身心理影响,应对策略以及家长学校校沟通等方面",
        "自身因素：关注自我认知,情绪管理,学习态度,心理健康,生活习惯和自我效能感等方面"
    ]

def get_search_result(string):
    if "无" in string:
        return None, False
    return string, True

def get_topic_index(string):
    if "家庭因素" in string:
        return 0
    if "学业压力" in string:
        return 1
    if "社交压力" in string:
        return 2
    if "学校环境" in string:
        return 3
    if "网络暴力" in string:
        return 4
    if "自身因素" in string:
        return 5
    return None
    

def instruction_and_prompt_topic_search(dialogue_history):
    # 只保留两轮对话
    dialogue_history = dialogue_history[-4:] if len(dialogue_history) > 4 else dialogue_history


    instruction = f"""你是一位关注中国中小学生心理健康的心理医生，正在与中小学生进行对话。
请根据“对话历史”，判断对话是否与以下主题相关：{list_topics}
如果相关，请返回相关的主题名称；
如果不相关，请返回“无”。"""

    prompt = f"""==========
“对话历史”如下：
{dialogue_history}
只能输出主题之一（家庭因素，学业压力，社交压力，学校环境，网络暴力，自身因素）或“无”。
=========="""
    return instruction, prompt


def topic_search(dialogue_history, key):
    instrcution, prompt = instruction_and_prompt_topic_search(dialogue_history)
    judge = get_response_openai3(instrcution, prompt, key)
    # print("话题检索模块：", judge)
    topic, flag = get_search_result(judge)
    # print(topic)
    if flag == True:
        topic = get_topic_index(topic)
    return topic, flag


from public_tool import get_response_openai3, get_score, phq_scale, gad_scale
##############症状抽取模块################
def instruction_and_prompt_depression_or_anxiety_judge(index, dialogue_history):
    # 诊断只看最后两句话来判断
    last_two_entries = dialogue_history[-2:]
    # 确定具体问题
    if index<10:
        problem = phq_scale(index)
        topic = "PHQ-9"
    else:
        problem = gad_scale(index)
        topic = "GAD-7"
    

    instruction = f"""
你是一个专注于中国中小学生心理健康的学习心理医生，负责评估学生在{topic}量表中的症状程度。
请根据对话历史，选择以下五个选项中的一个评估结果：‘无法判断’、‘没有’、‘轻度’、‘中度’、‘重度’。

评估标准：
1. **根据频率判断**：若对话中提到症状的频率或时间（如“偶尔”、“经常”），根据此判断症状的严重程度。
2. **症状持续性**：如果症状持续一段时间，即使未提及频率，也应选择适当的严重程度。
3. **信息不足时选择“无法判断”**：若没有足够信息判断症状的程度，选择“无法判断”。
4. **仅选择一个选项**：只返回五个选项之一，不要添加额外解释或信息。

"""

    prompt = f"""
==========
对话历史：
{last_two_entries}

相关问题：
{problem}

请根据以下评估标准，选择最符合的症状严重程度：
- **无法判断**：若未提及时间或频率，或信息不足以判断，选择“无法判断”。
- **没有**：若明确表示无症状，选择“没有”。
- **轻度**：若症状偶尔出现，如“偶尔”、“有时候”。
- **中度**：若症状频繁出现，如“经常”、“总是”。
- **重度**：若症状几乎每天出现，如“几乎每天”或“每天”。

选择评估结果（‘无法判断’、‘没有’、‘轻度’、‘中度’、‘重度’之一）：
==========
"""

    return instruction, prompt



# ---------大模型——诊断症状抽取----------
def llm_judge(index, dialogue_history, key):
    instruction, prompt = instruction_and_prompt_depression_or_anxiety_judge(index, dialogue_history)
    response_judge = get_response_openai3(instruction, prompt, key)
    # print("LLM症状抽取结果：", response_judge)
    # 结果映射
    judge = get_score(response_judge)
    return judge


# -------规则——诊断症状抽取------------
# 频率词程度分类建立
frequency_0 = ["从不", "没有", "正常", "很好", "不太", "几乎不", "很少见", "不曾", "从来没有", "没发生过"]
frequency_1 = ["偶尔", "有点", "有时", "很少", "一两次", "一阵子", "有一点", "偶然"]
frequency_2 = ["总是", "经常", "很多", "时常", "时不时", "频繁", "屡次", "隔三差五", "常常", "常有", "大多数"]
frequency_3 = ["每天", "一直都", "一直存在", "时时刻刻", "无时无刻不", "全天", "反复", "从早到晚", "每分每秒"]

# 基于规则的频率词匹配算法——作为大模型的备用算法
def rule_judge(dialogue_history):
    last_reply = dialogue_history[-1]['user']
    for word_0 in frequency_0:
        if word_0 in last_reply:
            rule_judge = 0
            return rule_judge
    for word_1 in frequency_1:
        if word_1 in last_reply:
            rule_judge = 1
            return rule_judge
    for word_2 in frequency_2:
        if word_2 in last_reply:
            rule_judge = 2
            return rule_judge
    for word_3 in frequency_3:
        if word_3 in last_reply:
            rule_judge = 3
            return rule_judge
    return -1


#######症状抽取#########
def symptom_judge(index, dialogue_history, key):
    # 先进行大模型诊断
    judge = llm_judge(index, dialogue_history, key)
    # 无法判断——进行规则判断
    if judge == -1:
        # print("进行规则判断")
        judge = rule_judge(dialogue_history)
        # 大模型和规则都没有判断，那就认为没有问题，避免重复多次询问影响体验感
        if judge == -1:
            judge = 0

    return judge


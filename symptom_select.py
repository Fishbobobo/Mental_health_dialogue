from public_tool import get_response_openai3
import random

###########症状选择模块##############
# 选择更符合当前对话流程的问题，能够更显自然

def instruction_and_prompt_to_select_symptom(dialogue_history, q_list):
    instruction = f"""
你是对话助手，任务是根据最近几轮对话，选择最符合用户当前情绪或问题的待诊断问题。

步骤：
1. **分析对话历史**：理解用户的情感和主要问题。
2. **选择相关问题**：从待诊断问题池中选择最相关的选项，仅返回问题的标号。
3. **仅返回标号**：只返回数字标号（如“3”），不包含额外内容。

待诊断问题池如下：{q_list}

"""
    prompt = f"""
==========
对话历史：
{dialogue_history}

待诊断问题池：
{q_list}

根据对话历史，选择最符合用户当前情绪或问题的待诊断问题。只需返回问题前的标号，例如，若选择的是“3. 入睡困难, 总是醒着, 或睡得太多嗜睡”，请仅返回“3”。
==========
"""

    return instruction, prompt


def phq_question(index):
    index = index - 1
    list_phq = ["1.做什么事都没兴趣, 沒意思", 
                "2.感到心情低落, 抑郁, 沒希望", 
                "3.入睡困难,总是醒着, 或睡得太多嗜睡",
                "4.常感到很疲倦,沒劲",
                "5.口味不好,或吃的太多", 
                "6.自己对自己不满, 觉得自己是个失败者,或让家人丟脸了",
                "7.无法集中精力,即便是读报纸或看电视时,记忆力下降",
                "8.行动或说话缓慢到引起人们的注意,或刚好相反, 坐臥不安,烦躁易怒易怒,到处走动",
                "9.有不如一死了之的念头, 或想怎样伤害自己一下"]
    return list_phq[index]

def gad_question(index):
    index = index - 10
    list_gad = ["10.感觉紧张，焦虑或急切", 
                "11.不能停止或无法控制对很多事情担心", 
                "12.变得容易烦恼或易被激怒", 
                "13.感到好像有什么可怕的事会发生"]
    return list_gad[index]

# 返回一个具体的问题
def question(index):
    if index<10:
        return phq_question(index)
    else:
        return gad_question(index)


# 将选择转变为具体问题号
def to_int(result):
    if '1' in result:
        return 1
    if '2' in result:
        return 2
    if '3' in result:
        return 3
    if '4' in result:
        return 4
    if '5' in result:
        return 5
    if '6' in result:
        return 6
    if '7' in result:
        return 7
    if '8' in result:
        return 8
    if '9' in result:
        return 9
    if '10' in result:
        return 10
    if '11' in result:
        return 11
    if '12' in result:
        return 12
    if '13' in result:
        return 13
    
    

def symptom_select(dialogue_history, question_list, key):
    q_list = []
    for x in question_list:
        q_list.append(question(x))
    
    instruction, prompt = instruction_and_prompt_to_select_symptom(dialogue_history, q_list)
    # print("症状选择提示:", instruction, prompt, flush=True)
    result = get_response_openai3(instruction, prompt, key)
    # print("症状问题检索模块", result)
    try:
        result = int(result)
    except ValueError:
        result = to_int(result)
    print("大模型选出的诊断问题:", result, flush=True)

    # 有可能选到待诊断池中没有的问题，就随机产生一个
    if result not in question_list:
        result= random.choice(question_list)
        print("随机选择的问题：", result)
    return result
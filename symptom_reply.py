from public_tool import get_response_openai3, phq_scale, gad_scale

#########症状询问模块###########


# 查找对话历史中的最后一个 assistant 回复
def find_last_assistant_reply(dialogue_history):
    # 从后往前遍历对话历史
    for message in reversed(dialogue_history):
        if "assistant" in message:
            return message["assistant"]  # 返回最后一个 assistant 回复
    return None  # 如果没有找到 assistant 的回复，则返回 None


def instruction_and_prompt_symptom(index, dialogue_history, summary):
    flow_strategy = [
        """ "评论后转移(Comment then Shift)": "{
            "说明": "先对对方的上一个回答进行简短的评论，表示理解或认同，然后自然地过渡到下一个话题。",
            "示例": "我明白你最近压力很大，这确实很不容易。对了，说到压力，你最近有没有因为工作或学习而失眠呢？【评论后转移】"
        }" """,
        """ "过渡(Bridging)": "{
            "说明": "使用对方上一个回答中的关键词或概念作为桥梁，引入下一个话题，确保对话连贯。",
            "示例": "你提到最近情绪很低落，这种低落的情绪有没有影响到你的日常生活，比如饮食或者社交呢？【过渡】"
        }" """,
    ]
    question_strategy = [
        """ "加载问题(Loading Question)": "{
            "说明": "利用假设或提示引导询问者找到相关症状。",
            "示例": "很多人都觉得未来充满希望，你是不是也有这样的感觉呢？【加载问题】"
        }" """,
        """ "提名技巧(Nominative Technique)": "{
            "说明": "先提及他人的经历，再询问对方的看法或感受，降低直接提问的敏感性。",
            "示例": "有些人在面对压力时会觉得很无助，你有没有过类似的感觉呢？【提名技巧】"
        }" """,
        """ "宽恕问题(Forgiving Question)": "{
            "说明": "使用开放性问题，以尊重和非评判性的语言提问，营造安全的交流环境。",
            "示例": "你能和我说说最近让你感到烦恼的事情吗？【宽恕问题】"
        }" """,
        """ "澄清(Clarification)": "{
            "说明": "对对方之前提到的内容进行澄清，鼓励对方提供更多细节，同时避免误解。",
            "示例": "你刚才提到感觉很累，能和我说说具体是什么让你觉得累吗？【澄清】"
        }" """,
    ]
    # 确定具体问题
    if index < 10:
        problem = phq_scale(index)
    else:
        problem = gad_scale(index)

    last_assistant_reply = find_last_assistant_reply(dialogue_history)

    # prompt-engineering
    instruction = f"""
你是一位心理学家，与一位中学生对话。任务是根据“对话历史”，“学生陈述总结”来引导学生讨论问题：“{problem}”。请遵循以下原则：

1. **选择话题转换策略**：首先，需要根据对话历史和学生陈述总结，从”评论和话题转化“ 和 ”衔接“中选择一个最恰当的策略，按照策略要求自然引入“{problem}”。
2. **平滑过渡**：根据学生历史回复顺势引入话题，避免突然的转变。
3. **共情回应**：回应学生情绪，让他们感到被理解，但<避免过度>情感化。
========
4. **避免重复**：
1) 若问题<对话历史>已提到，不重复，进行拓展或补充; 
2) 生成的回复应该与之前的任何回复避免重复，尤其是在表达和措辞上。避免与自己的前一个回复{last_assistant_reply}在句式或词汇上相似。
3) 避免重复使用类似的<开头句式>，如“好的，我明白了”，“你提到”等，**不应该使用之前使用过的开头方式**。
========
5. **选择提问策略**：提问时根据对话历史和学生陈述总结从”加载问题“，”提名技巧“，”宽容提问“ 和 ”澄清“中选择一个最恰当的策略，按照策略要求进行提问。
6. **敏感话题**：在询问例如有关 “自杀”，“自残” 等敏感话题时需要利用所选择的提问策略来避免生硬直接地提问，要采用更为委婉、间接且富有同理心的方式引入相关讨论。
7. **简洁提问**：提问时使用简洁的语言，确保不超过<八十>字。
8. **随机询问持续时间**: 结合对话历史，尽量随机的询问问题持续的时间，控制总的问题讨论中，询问持续时间和不询问持续时间达到平衡。
9. **避免提出多个问题**：一次对话中不可以提出两个及以上的问题，尽量**使用单个问题**。
10. **回复要求**：回复的结尾用括号说明所选择的话题转换策略和提问策略，以及在<十五>个字以内说明选择策略的原因。

确保回应贴合学生情感，促进开放交流。
"""

    prompt = f"""
==========  
话题转换策略及策略要求：{flow_strategy}
提问策略及策略要求：{question_strategy}
对话历史：  
{dialogue_history}  
学生陈述总结：{summary}

当前潜在问题：  
{problem}  

推理过程：
1. 分析学生情感和语气，理解其可能的问题。
2. 选择话题转换策略，严格按照策略要求自然地引入问题，避免突兀的转变。
3. 避免重复：避免和对话历史中之前的回复,特别是最后一个回复“{last_assistant_reply}”在措辞、句式、语气上过度相似。生成一个新颖而自然的回复。
4. 根据学生情感调整回应，避免过度情感化。
5. 选择提问策略，严格按照策略要求提出简洁的问题，<随机>询问问题持续的时间,你需要自行判断这轮回是否询问持续时间。

最终生成回复的要求：  
引导学生讨论当前问题，确保对话自然流畅。  

输出：<最终回复>
==========  
"""
    return instruction, prompt




# 症状询问为目的的回复
def symptom_ask_reply(index, dialogue_history, summary, key):
    instruction, prompt = instruction_and_prompt_symptom(
        index, dialogue_history, summary
    )
    # print(instruction, prompt, flush=True)
    response = get_response_openai3(instruction, prompt, key)
    return response



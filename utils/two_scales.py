PHQ9_QUESTIONS = [
    "1.做事情时提不起劲或没有兴趣",
    "2.感到沮丧、郁闷或绝望",
    "3.入睡困难、睡不安稳或睡得太多",
    "4.感到疲倦或没有活力",
    "5.食欲不振或吃太多",
    "6.觉得自己很差，或让自己或家人失望",
    "7.难以集中注意力，例如看报纸或看电视时",
    "8.动作或说话速度缓慢到别人已经注意到；或相反，表现得坐立不安或烦躁",
    "9.有不如死掉或用某种方式伤害自己的念头",
]

GAD7_QUESTIONS = [
    "1.感到紧张、焦虑或急切",
    "2.无法停止或控制担忧",
    "3.对各样事情担忧过多",
    "4.很难放松下来",
]


def get_phq9_level(score):
    if score >= 20:
        return "重度焦虑与抑郁"
    if score >= 15:
        return "中重度焦虑与抑郁"
    if score >= 10:
        return "中度焦虑与抑郁"
    if score >= 5:
        return "轻度心理困扰"
    return "心理状态良好"


def get_gad7_level(score):
    if score >= 15:
        return "重度焦虑与抑郁"
    if score >= 10:
        return "中度焦虑与抑郁"
    if score >= 5:
        return "轻度心理困扰"
    return "心理状态良好"

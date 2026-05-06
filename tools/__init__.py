"""
Tool 定义列表（OpenAI-compatible function calling format）。
供 Agent Loop 注入 LLM。
"""

ASSESSMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "assess_symptom",
            "description": "评估用户对某个 PHQ-9 或 GAD-7 症状问题的回答严重程度。PHQ-9 编号 1-9，GAD-7 编号 10-13。返回分数：-1=无法判断, 0=无症状, 1=轻度, 2=中度, 3=重度",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_index": {
                        "type": "integer",
                        "description": "症状问题编号: 1-9 为 PHQ-9, 10-13 为 GAD-7"
                    },
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容（含 role 标记）"
                    }
                },
                "required": ["question_index", "recent_dialogue"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_next_symptom",
            "description": "根据当前对话和已评估情况，选择下一个最合适的症状问题编号",
            "parameters": {
                "type": "object",
                "properties": {
                    "assessed_questions": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "已评估过的问题编号列表"
                    },
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    }
                },
                "required": ["assessed_questions", "recent_dialogue"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recognize_intent",
            "description": "判断用户当前意图：1=用户有想聊的话题或表达了情绪, 0=用户愿意接受症状评估/无新话题",
            "parameters": {
                "type": "object",
                "properties": {
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    }
                },
                "required": ["recent_dialogue"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_topic",
            "description": "判断用户当前讨论的话题是否匹配预定义的六大话题（家庭因素、学业压力、社交压力、学校环境、网络暴力、自身因素）",
            "parameters": {
                "type": "object",
                "properties": {
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    }
                },
                "required": ["recent_dialogue"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "judge_topic",
            "description": "对已讨论的预定义话题进行评估，判断学生在该话题上是否存在困扰。返回：-1=无法判断, 0=无困扰, 1=存在困扰",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_index": {
                        "type": "integer",
                        "description": "话题编号 0-5: 0=家庭因素, 1=学业压力, 2=社交压力, 3=学校环境, 4=网络暴力, 5=自身因素"
                    },
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    }
                },
                "required": ["topic_index", "recent_dialogue"]
            }
        }
    },
]

REPLY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_chat_reply",
            "description": "【主要回复工具】生成符合当前咨询阶段的回复。适用于绝大多数场景：开场共情、深入探索、认知重构、自由聊天、回答百科问题、轻松俏皮话等。使用此工具时系统会自动根据对话历史和摘要生成符合咨询原则的回复",
            "parameters": {
                "type": "object",
                "properties": {
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    },
                    "summary": {
                        "type": "string",
                        "description": "学生对话摘要"
                    }
                },
                "required": ["recent_dialogue", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_symptom_reply",
            "description": "【特定场景】当对话已经进入评估阶段，需要询问某个具体 PHQ-9/GAD-7 症状问题时使用。不要作为默认回复工具",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_index": {
                        "type": "integer",
                        "description": "症状问题编号 1-13"
                    },
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    },
                    "summary": {
                        "type": "string",
                        "description": "学生对话摘要"
                    }
                },
                "required": ["question_index", "recent_dialogue", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_empathetic_reply",
            "description": "【深度共情】当用户表达了中重度情绪困扰时使用。引导用户深入探索自己的感受，而不是直接给建议或解决方案",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_index": {
                        "type": "integer",
                        "description": "被评估为中重度的症状问题编号"
                    },
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    },
                    "summary": {
                        "type": "string",
                        "description": "学生对话摘要"
                    }
                },
                "required": ["question_index", "recent_dialogue", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_topic_reply",
            "description": "【特定场景】当需要围绕六大主题（家庭/学业/社交/学校/网络/自身因素）展开讨论时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_index": {
                        "type": "integer",
                        "description": "话题编号 0-5: 0=家庭, 1=学业, 2=社交, 3=学校, 4=网络, 5=自身"
                    },
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    },
                    "summary": {
                        "type": "string",
                        "description": "学生对话摘要"
                    }
                },
                "required": ["topic_index", "recent_dialogue", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_end_reply",
        "description": "【结束对话】在用户已经找到解决方案或情绪明显好转后，生成总结性结束语。总结用户自己的发现，强化成就感。不再提新问题或新话题",
            "parameters": {
                "type": "object",
                "properties": {
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    }
                },
                "required": ["recent_dialogue"]
            }
        }
    },
]

MEMORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_user_memory",
            "description": "读取用户的当前状态信息，包括症状评估进度、评分、当前阶段等",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_user_memory",
            "description": "更新用户记忆中的字段。可更新: phase（当前阶段）, current_question（当前症状编号）, current_topic（当前话题编号）, suicide_risk（自杀风险标记）",
            "parameters": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "object",
                        "description": "要更新的字段字典, 如 {\"phase\": \"assessment\", \"current_question\": 3}"
                    }
                },
                "required": ["updates"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_conversation_summary",
            "description": "更新对话摘要（每 5 轮调用一次）。用当前对话内容更新学生陈述总结",
            "parameters": {
                "type": "object",
                "properties": {
                    "recent_dialogue": {
                        "type": "string",
                        "description": "最近几轮对话内容"
                    },
                    "summary_before": {
                        "type": "string",
                        "description": "旧的对话摘要"
                    }
                },
                "required": ["recent_dialogue", "summary_before"]
            }
        }
    },
]

# 所有 tools 合并列表
TOOLS = ASSESSMENT_TOOLS + REPLY_TOOLS + MEMORY_TOOLS

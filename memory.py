"""
UserMemory 层：从 MySQL 多表聚合/写入用户状态，并序列化为 LLM context。
"""

from __future__ import annotations
from typing import Any

# ── Schema ──────────────────────────────────────────────────────────────

PHQ9_KEYS = [f"Q{i}" for i in range(1, 10)]  # Q1..Q9
GAD7_KEYS = [f"Q{i}" for i in range(10, 14)]  # Q10..Q13
TOPIC_KEYS = [f"t{i}" for i in range(1, 7)]  # t1..t6

PHQ9_DB_FIELDS = ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9"]
GAD7_DB_FIELDS = ["q1", "q2", "q3", "q4"]
TOPIC_DB_FIELDS = ["t1", "t2", "t3", "t4", "t5", "t6"]


def empty_memory(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "turn_count": 0,
        "phq9_scores": {k: -1 for k in PHQ9_KEYS},
        "gad7_scores": {k: -1 for k in GAD7_KEYS},
        "topic_scores": {k: -1 for k in TOPIC_KEYS},
        "phase": "assessment",
        "current_question": None,
        "current_topic": None,
        "summary": "",
        "suicide_risk": False,
    }


# ── Read ────────────────────────────────────────────────────────────────


def load_user_memory(cursor, user_id: str) -> dict[str, Any]:
    """从 MySQL 多表聚合 UserMemory。"""
    memory = empty_memory(user_id)

    # 1. student_info
    cursor.execute(
        "SELECT status, topic, cur_selected_slot FROM student_info WHERE id = %s",
        (user_id,),
    )
    row = cursor.fetchone()
    if row:
        phase = _status_to_phase(row.get("status", 2))
        memory["phase"] = phase
        memory["current_topic"] = row.get("topic")
        memory["current_question"] = row.get("cur_selected_slot")

    # 2. PHQ-9
    cursor.execute("SELECT * FROM `PHQ-9` WHERE id = %s", (user_id,))
    phq_row = cursor.fetchone()
    if phq_row:
        for mem_key, db_key in zip(PHQ9_KEYS, PHQ9_DB_FIELDS):
            val = phq_row.get(db_key)
            memory["phq9_scores"][mem_key] = val if val is not None else -1

    # 3. GAD-7
    cursor.execute("SELECT * FROM `GAD-7` WHERE id = %s", (user_id,))
    gad_row = cursor.fetchone()
    if gad_row:
        for mem_key, db_key in zip(GAD7_KEYS, GAD7_DB_FIELDS):
            val = gad_row.get(db_key)
            memory["gad7_scores"][mem_key] = val if val is not None else -1

    # 4. topic
    cursor.execute("SELECT * FROM topic WHERE id = %s", (user_id,))
    topic_row = cursor.fetchone()
    if topic_row:
        for mem_key, db_key in zip(TOPIC_KEYS, TOPIC_DB_FIELDS):
            val = topic_row.get(db_key)
            memory["topic_scores"][mem_key] = val if val is not None else -1

    # 5. instant_info → summary & turn_count
    cursor.execute("SELECT summary, `turn` FROM instant_info WHERE id = %s", (user_id,))
    summ_row = cursor.fetchone()
    if summ_row:
        if summ_row.get("summary"):
            memory["summary"] = summ_row["summary"]
        if summ_row.get("turn") is not None:
            # 从 SQL 中的 turn 反推 turn_count（30 - remaining = used）
            from pool_config import Config
            memory["turn_count"] = Config.MAXTURN - summ_row["turn"]

    # 6. suicide risk (Q9 >= 1)
    if memory["phq9_scores"].get("Q9", -1) >= 1:
        memory["suicide_risk"] = True

    return memory


# ── Write ───────────────────────────────────────────────────────────────


def save_user_memory(cursor, user_id: str, memory: dict[str, Any]) -> None:
    """将 UserMemory 写回 MySQL 各表。"""
    # 1. student_info
    phase = memory.get("phase", "assessment")
    status = _phase_to_status(phase)
    cursor.execute(
        "UPDATE student_info SET status = %s, topic = %s, cur_selected_slot = %s WHERE id = %s",
        (
            status,
            memory.get("current_topic"),
            memory.get("current_question"),
            user_id,
        ),
    )

    # 2. PHQ-9
    phq_updates = {}
    for mem_key, db_key in zip(PHQ9_KEYS, PHQ9_DB_FIELDS):
        val = memory["phq9_scores"].get(mem_key, -1)
        if val != -1:
            phq_updates[db_key] = val
    if phq_updates:
        set_clause = ", ".join(f"{k} = %s" for k in phq_updates)
        vals = list(phq_updates.values()) + [user_id]
        cursor.execute(
            f"UPDATE `PHQ-9` SET {set_clause} WHERE id = %s", vals
        )

    # 3. GAD-7
    gad_updates = {}
    for mem_key, db_key in zip(GAD7_KEYS, GAD7_DB_FIELDS):
        val = memory["gad7_scores"].get(mem_key, -1)
        if val != -1:
            gad_updates[db_key] = val
    if gad_updates:
        set_clause = ", ".join(f"{k} = %s" for k in gad_updates)
        vals = list(gad_updates.values()) + [user_id]
        cursor.execute(f"UPDATE `GAD-7` SET {set_clause} WHERE id = %s", vals)

    # 4. topic
    topic_updates = {}
    for mem_key, db_key in zip(TOPIC_KEYS, TOPIC_DB_FIELDS):
        val = memory["topic_scores"].get(mem_key, -1)
        if val != -1:
            topic_updates[db_key] = val
    if topic_updates:
        set_clause = ", ".join(f"{k} = %s" for k in topic_updates)
        vals = list(topic_updates.values()) + [user_id]
        cursor.execute(f"UPDATE topic SET {set_clause} WHERE id = %s", vals)

    cursor.connection.commit()


# ── Serialize ───────────────────────────────────────────────────────────


def memory_to_context(memory: dict[str, Any]) -> str:
    """序列化为 LLM 可理解的文本。"""
    lines = [
        f"用户ID: {memory['user_id']}",
        f"对话轮次: {memory['turn_count']}",
        f"当前阶段: {memory['phase']}",
    ]

    # PHQ-9 评分
    assessed_phq = {k: v for k, v in memory["phq9_scores"].items() if v >= 0}
    if assessed_phq:
        lines.append("PHQ-9 评估结果: " + ", ".join(f"{k}={v}" for k, v in assessed_phq.items()))
    else:
        lines.append("PHQ-9 症状: 尚未评估")

    # GAD-7 评分
    assessed_gad = {k: v for k, v in memory["gad7_scores"].items() if v >= 0}
    if assessed_gad:
        lines.append("GAD-7 评估结果: " + ", ".join(f"{k}={v}" for k, v in assessed_gad.items()))
    else:
        lines.append("GAD-7 症状: 尚未评估")

    # Topic 评分
    assessed_topic = {k: v for k, v in memory["topic_scores"].items() if v >= 0}
    if assessed_topic:
        lines.append("话题评估: " + ", ".join(f"{k}={v}" for k, v in assessed_topic.items()))

    if memory["current_question"] is not None:
        lines.append(f"当前正在询问的症状编号: {memory['current_question']}")
    if memory["current_topic"] is not None:
        lines.append(f"当前讨论的话题编号: {memory['current_topic']}")

    if memory["summary"]:
        lines.append(f"对话摘要: {memory['summary']}")

    if memory["suicide_risk"]:
        lines.append("[风险警告] 检测到自杀风险，请优先提供危机支持")

    return "\n".join(lines)


# ── 内部辅助 ────────────────────────────────────────────────────────────

PHASE_MAP = {1: "assessment", 2: "free_chat", 3: "topic_discussion"}
STATUS_MAP = {"assessment": 1, "free_chat": 2, "topic_discussion": 3, "ending": 4}


def _status_to_phase(status: int | None) -> str:
    return PHASE_MAP.get(status, "free_chat")


def _phase_to_status(phase: str) -> int:
    return STATUS_MAP.get(phase, 2)

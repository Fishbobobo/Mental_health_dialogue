"""
多轮 E2E 测试脚本 — 验证修复效果。
启动 Flask → 重置用户 → 发送 5 轮对话 → 检查回复质量。
"""
import pymysql
import requests
import json
import time
import subprocess
import signal
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── 配置 ──────────────────────────────────────────────────────────────
USER_ID = "test_user_001"
API_URL = "http://127.0.0.1:8080/textchat"
CHECK_PATTERNS = ["这件事", "这件事…", "这件事让我", "这件事最"]
FLASK_PORT = 8080

# ── 测试消息（模拟一个中学生 × 考试焦虑） ───────────────────────────
MESSAGES = [
    "你好盼达，我最近考试没考好，心情很差",
    "我爸妈对我期望很高，我怕他们失望",
    "我觉得做什么都没用，就是很烦",
    "我觉得自己让父母失望了，很对不起他们",
    "我也不知道该怎么办，有时候觉得压力很大",
]

# ── 数据库重置 ──────────────────────────────────────────────────────
def reset_user():
    conn = pymysql.connect(host="127.0.0.1", user="root", password="", database="data1")
    cursor = conn.cursor()

    # 清空对话记录
    cursor.execute("UPDATE instant_info SET dialogue='[]', turn=0, filter_dialogue='', summary='' WHERE id=%s", (USER_ID,))

    # 重置 PHQ-9 GAD-7 topic 分数
    for i in range(1, 10):
        cursor.execute(f"UPDATE `PHQ-9` SET q{i}=-1 WHERE id=%s", (USER_ID,))
    for i in range(1, 5):
        cursor.execute(f"UPDATE `GAD-7` SET q{i}=-1 WHERE id=%s", (USER_ID,))
    for i in range(1, 7):
        cursor.execute(f"UPDATE topic SET t{i}=-1 WHERE id=%s", (USER_ID,))

    # 重置 student_info status=2 (free_chat)
    cursor.execute("UPDATE student_info SET status=2 WHERE id=%s", (USER_ID,))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[RESET] 用户 {USER_ID} 已重置")

# ── 启动 Flask ───────────────────────────────────────────────────────
def start_flask():
    # Run with FLASK_ENV=production to avoid reloader
    # Clear pycache before starting to ensure fresh bytecode
    import shutil
    for d in ["__pycache__", "tools/__pycache__"]:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), d)
        if os.path.exists(p):
            shutil.rmtree(p)
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "FLASK_ENV": "production"},
    )
    # 等待 Flask 启动
    for _ in range(30):
        try:
            r = requests.get("http://127.0.0.1:8080/", timeout=2)
            if r.status_code == 200:
                print("[FLASK] Flask 已启动")
                return proc
        except:
            pass
        time.sleep(1)
    print("[ERROR] Flask 启动超时")
    proc.kill()
    return None

# ── 发送消息 ─────────────────────────────────────────────────────────
def send_message(text, user_id):
    try:
        r = requests.post(API_URL, json={"text": text, "user_name": user_id}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", "")
        else:
            return f"[ERROR] HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return f"[ERROR] {e}"

# ── 检查回复质量 ─────────────────────────────────────────────────────
def check_reply(reply, turn):
    issues = []

    # 检查长度
    length = len(reply)
    if length > 80:
        issues.append(f"过长 ({length}字)")
    elif length <= 3:
        issues.append(f"过短 ({length}字)")

    # 检查违禁句式
    for pattern in CHECK_PATTERNS:
        if pattern in reply:
            issues.append(f"包含违禁句式「{pattern}」")

    # 检查是否全是提问
    question_count = reply.count("？") + reply.count("?")
    if question_count >= 2:
        issues.append(f"问了 {question_count} 个问题")

    # 检查封闭式问题
    closed_patterns = ["是不是", "有没有", "对不对", "能不能", "会不会"]
    for cp in closed_patterns:
        if cp in reply:
            issues.append(f"含封闭式问题「{cp}」")

    # 检查是否直接给建议
    advice_patterns = ["你应该", "我建议你", "你可以试试", "你最好"]
    for ap in advice_patterns:
        if ap in reply:
            issues.append(f"含直接建议「{ap}」")

    status = "⚠" if issues else "✅"
    detail = f" [{'; '.join(issues)}]" if issues else ""
    print(f"  第{turn}轮回复 ({length}字): \"{reply}\" {status}{detail}")

    return len(issues) == 0

# ── 主流程 ───────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  E2E 多轮对话测试 — 验证回复质量")
    print("=" * 60)

    # 1. 重置用户
    reset_user()

    # 2. 启动 Flask
    print("\n--- 启动 Flask ---")
    flask_proc = start_flask()
    if not flask_proc:
        return False

    try:
        # 3. 发送多轮对话
        print("\n--- 多轮对话 ---")
        all_ok = True
        for i, msg in enumerate(MESSAGES):
            print(f"  用户: {msg}")
            reply = send_message(msg, USER_ID)
            ok = check_reply(reply, i + 1)
            if not ok:
                all_ok = False
            time.sleep(1)  # 避免请求过快

        # 4. 总结
        print(f"\n--- 结果 ---")
        if all_ok:
            print("  ✅ 所有轮次回复质量达标")
        else:
            print("  ⚠  存在需要优化的回复")

        return all_ok

    finally:
        # Kill parent and any orphan children
        import subprocess as _sp
        _sp.run(["pkill", "-f", "python.*app.py"], capture_output=True)
        try:
            flask_proc.wait(timeout=3)
        except:
            flask_proc.kill()
        print("[FLASK] Flask 已关闭")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

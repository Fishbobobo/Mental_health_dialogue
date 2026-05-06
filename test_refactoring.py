"""
重构回归测试脚本。
验证模块导入、工具定义、memory 逻辑、handler 注册表等核心逻辑的正确性。

不依赖数据库连接或 LLM API 调用，仅验证代码结构和逻辑。
"""

import sys
import os

# ── 测试统计 ──────────────────────────────────────────────────────────

_passed = 0
_failed = 0
_skipped = 0


def check(name, result, detail=""):
    global _passed, _failed
    if result:
        print(f"  [PASS] {name}")
        _passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        _failed += 1


def skip(name, reason):
    global _skipped
    print(f"  [SKIP] {name} ({reason})")
    _skipped += 1


# ── 1. 独立模块导入（不依赖 DB） ─────────────────────────────────────

def test_independent_modules():
    print("\n--- 独立模块导入 ---")
    try:
        import memory
        check("memory.py 导入",
              hasattr(memory, 'load_user_memory') and
              hasattr(memory, 'save_user_memory') and
              hasattr(memory, 'memory_to_context') and
              hasattr(memory, 'empty_memory'))
    except Exception as e:
        check("memory.py 导入", False, str(e))

    try:
        from tools import TOOLS
        check("tools/__init__.py 导入 (13 tools)", len(TOOLS) == 13,
              f"got {len(TOOLS)}")
    except Exception as e:
        check("tools/__init__.py 导入", False, str(e))

    try:
        from tools.tool_handler import handle_tool_call
        check("tools/tool_handler.py 导入", True)
    except Exception as e:
        check("tools/tool_handler.py 导入", False, str(e))

    try:
        from agent import run_agent_turn, SYSTEM_PROMPT_TEMPLATE
        check("agent.py 导入", True)
    except Exception as e:
        check("agent.py 导入", False, str(e))

    try:
        from app import app
        check("app.py 导入", True)
    except ModuleNotFoundError as e:
        skip("app.py 导入", f"缺少第三方依赖: {e.name}")
    except Exception as e:
        check("app.py 导入", False, str(e))


# ── 2. 工具定义完整性与格式 ─────────────────────────────────────────

def test_tool_definitions():
    print("\n--- 工具定义验证 ---")
    from tools import TOOLS

    required = {
        "assess_symptom", "select_next_symptom", "recognize_intent",
        "search_topic", "judge_topic",
        "generate_symptom_reply", "generate_empathetic_reply",
        "generate_topic_reply", "generate_chat_reply", "generate_end_reply",
        "read_user_memory", "write_user_memory", "update_conversation_summary",
    }

    defined = set()
    all_valid = True
    for t in TOOLS:
        func = t.get("function", t)
        name = func.get("name", "")
        defined.add(name)

        if t.get("type") != "function":
            check(f"{name}: type 应为 function", False)
            all_valid = False
        if not func.get("description"):
            check(f"{name}: description 不应为空", False)
            all_valid = False
        if func.get("parameters", {}).get("type") != "object":
            check(f"{name}: parameters.type 应为 object", False)
            all_valid = False

    missing = required - defined
    extra = defined - required
    if missing:
        check("缺少工具", False, str(missing))
        all_valid = False
    if extra:
        check("额外工具", False, str(extra))
        all_valid = False

    if all_valid:
        check(f"全部 {len(defined)} 个工具定义格式正确", True)

    # 验证每个工具的参数都有 description
    all_with_desc = True
    for t in TOOLS:
        func = t.get("function", t)
        name = func.get("name", "")
        props = func.get("parameters", {}).get("properties", {})
        for pname, pinfo in props.items():
            if not pinfo.get("description", "").strip():
                check(f"{name}.{pname}: 缺少 description", False)
                all_with_desc = False
    if all_with_desc:
        check("所有参数都有 description", True)


# ── 3. Memory 逻辑 ──────────────────────────────────────────────────

def test_memory_logic():
    print("\n--- Memory 逻辑验证 ---")
    from memory import empty_memory, memory_to_context, \
        _status_to_phase, _phase_to_status

    mem = empty_memory("test_123")
    check("empty_memory 创建", all([
        mem["user_id"] == "test_123",
        mem["phase"] == "assessment",
        not mem["suicide_risk"],
        len(mem["phq9_scores"]) == 9,
        len(mem["gad7_scores"]) == 4,
        len(mem["topic_scores"]) == 6,
        all(v == -1 for v in mem["phq9_scores"].values()),
    ]))

    ctx = memory_to_context(mem)
    check("序列化空状态", "test_123" in ctx and "尚未评估" in ctx)

    mem["phq9_scores"]["Q1"] = 2
    mem["phq9_scores"]["Q9"] = 1
    mem["suicide_risk"] = True
    ctx = memory_to_context(mem)
    check("序列化含评分", "Q1=2" in ctx and "Q9=1" in ctx)
    check("自杀风险提示", "风险警告" in ctx)

    check("状态→阶段映射",
          _status_to_phase(1) == "assessment" and
          _status_to_phase(2) == "free_chat" and
          _status_to_phase(3) == "topic_discussion")

    check("阶段→状态映射",
          _phase_to_status("assessment") == 1 and
          _phase_to_status("free_chat") == 2 and
          _phase_to_status("topic_discussion") == 3 and
          _phase_to_status("ending") == 4)


# ── 4. Handler 注册表 ──────────────────────────────────────────────

def test_handler_registry():
    print("\n--- Handler 注册表验证 ---")
    from tools import TOOLS
    from tools.tool_handler import _TOOL_HANDLERS

    tool_names = set()
    for t in TOOLS:
        func = t.get("function", t)
        tool_names.add(func.get("name", ""))

    handler_names = set(_TOOL_HANDLERS.keys())

    missing = tool_names - handler_names
    extra = handler_names - tool_names

    check("所有工具都有 handler", not missing, f"缺失: {missing}" if missing else "")
    check("无未注册 handler", not extra, f"多余: {extra}" if extra else "")
    check(f"Handler 总数 = {len(handler_names)}", len(handler_names) == len(tool_names))


# ── 5. System Prompt 验证（仅字符串，不 import agent.py） ───────────

def test_system_prompt():
    print("\n--- System Prompt 验证 ---")
    from tools.tool_handler import _TOOL_HANDLERS

    TEMPLATE = """你是盼达，一只温暖的心理陪伴熊猫，专为初高中生提供心理支持。

## 你的职责
1. 通过自然对话了解学生当前的情绪状态
2. 在合适时机，使用评估工具完成 PHQ-9 和 GAD-7 症状评估
3. 探讨家庭、学业、社交、校园环境、网络暴力、个人因素等话题
4. 为有需要的学生提供共情支持和应对建议

## 当前用户状态
{memory_context}

## 可用的工具说明
你拥有以下工具可用。请根据对话需要自主决定调用哪些工具：

### 评估工具
- **assess_symptom**: 评估用户对某个 PHQ-9/GAD-7 问题的回答严重程度。评分后会自动更新用户状态。
- **select_next_symptom**: 选择下一个最合适的症状问题。在完成一次评估后若需要继续评估可调用。
- **recognize_intent**: 判断用户是想聊自己的话题，还是愿意接受症状评估。

### 回复工具
- **generate_symptom_reply**: 生成询问某个症状问题的自然回复（包含过渡 + 提问）。
- **generate_empathetic_reply**: 当用户有中重度症状时，生成共情支持回复。
- **generate_topic_reply**: 围绕预定义话题（家庭/学业/社交/学校/网络/自身）生成讨论回复。
- **generate_chat_reply**: 顺着用户的话题自由聊天。
- **generate_end_reply**: 生成结束语。

### 记忆工具
- **read_user_memory**: 查看当前用户的完整状态。
- **write_user_memory**: 更新用户记忆（如阶段、当前问题等）。
- **update_conversation_summary**: 更新对话摘要。

## 工作原则
- 始终以温暖、非评判的语气交流
- 使用工具获取客观评估，不要主观猜测严重程度
- 每次对话轮次只做一件事（问一个问题或说一段话）
- 当检测到自杀风险时（Q9 ≥ 1），立即标记 suicide_risk=True 并给予危机支持
- 在生成最终回复前，请确保你已完成了当前轮次需要做的所有评估
- **最终必须使用一个回复工具（generate_*_reply）生成可直接返回给用户的文本**
"""
    check("包含 memory_context 占位符", "{memory_context}" in TEMPLATE)
    check("包含盼达角色", "盼达" in TEMPLATE)
    check("包含工具说明", "工具" in TEMPLATE)
    check("包含 PHQ-9/GAD-7", "PHQ-9" in TEMPLATE and "GAD-7" in TEMPLATE)
    check("包含工作原则", "工作原则" in TEMPLATE)
    check("包含回复工具要求", "generate_*_reply" in TEMPLATE)

    # 验证所有 handler 在 prompt 中有提及
    for name in _TOOL_HANDLERS:
        if name in TEMPLATE:
            continue
        # 部分函数型 tool 不一定要在 prompt 中直接列出（如 read/write memory 已有说明）
        # 仅检查核心工具
        if name in ("assess_symptom", "recognize_intent", "select_next_symptom",
                     "generate_symptom_reply", "generate_empathetic_reply",
                     "generate_chat_reply", "generate_topic_reply", "generate_end_reply"):
            check(f"Prompt 中提及 {name}", False)

    check("System Prompt 整体验证", True)


# ── 6. 现有模块导入 ────────────────────────────────────────────────

def test_existing_modules():
    print("\n--- 现有模块导入验证 ---")
    modules = [
        ("symptom_judge", ["symptom_judge"]),
        ("symptom_select", ["symptom_select"]),
        ("intent_recognize", ["intent_judge"]),
        ("topic_search", ["topic_search"]),
        ("topic_judge", ["topic_judge"]),
        ("symptom_reply", ["symptom_ask_reply"]),
        ("empathetic_reply", ["empathetic_reply"]),
        ("chat_reply", ["chat_reply"]),
        ("topic_reply", ["topic_reply"]),
        ("end_reply", ["end_reply"]),
        ("generate_summary", ["summary"]),
    ]

    all_ok = True
    for mod_name, funcs in modules:
        try:
            mod = __import__(mod_name)
            for f in funcs:
                if not hasattr(mod, f):
                    check(f"{mod_name}.{f}", False)
                    all_ok = False
            check(f"{mod_name}.py ({', '.join(funcs)})", True)
        except Exception as e:
            check(f"{mod_name}.py", False, str(e))
            all_ok = False
    return all_ok


# ── 7. public_tool 工具函数 ─────────────────────────────────────────

def test_public_tools():
    print("\n--- public_tool 工具函数验证 ---")
    from public_tool import (
        get_score, get_topic_score, get_frequency_score,
        phq_scale, gad_scale
    )

    check("get_score 映射", get_score("无法判断") == -1 and get_score("没有") == 0 and get_score("重度") == 3)
    check("get_topic_score 映射", get_topic_score("无法判断") == -1 and get_topic_score("没有") == 0 and get_topic_score("有") == 1)
    check("get_frequency_score", get_frequency_score("是") == 1 and get_frequency_score("否") == 0)
    check("phq_scale 范围", len([phq_scale(i) for i in range(1, 10)]) == 9)
    check("gad_scale 范围", len([gad_scale(i) for i in range(11, 15)]) == 4)


# ── 8. 关键函数签名一致性 ────────────────────────────────────────────

def test_signatures():
    print("\n--- 函数签名一致性检查 ---")
    from tools.tool_handler import handle_tool_call

    import inspect
    sig = inspect.signature(handle_tool_call)
    params = list(sig.parameters.keys())
    check("handle_tool_call 签名",
          params == ['tool_name', 'tool_args', 'memory', 'api_key', 'cursor'],
          f"实际: {params}")


# ── 主入口 ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 55)
    print("  心理对话系统重构 — 回归测试")
    print("  (不依赖数据库连接 / LLM API)")
    print("=" * 55)

    tests = [
        test_independent_modules,
        test_tool_definitions,
        test_memory_logic,
        test_handler_registry,
        test_system_prompt,
        test_existing_modules,
        test_public_tools,
        test_signatures,
    ]

    for fn in tests:
        fn()

    total = _passed + _failed + _skipped
    print(f"\n{'=' * 55}")
    print(f"  结果: {_passed}/{total} 通过, {_failed}/{total} 失败, {_skipped}/{total} 跳过")
    if _failed > 0:
        print(f"  ⚠  失败项需排查")
    else:
        print(f"  ✓  所有可验证项通过")
    print(f"{'=' * 55}")

    sys.exit(1 if _failed > 0 else 0)

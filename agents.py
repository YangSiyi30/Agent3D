import re
import json
from openai import OpenAI
import colorama
from colorama import Fore, Style
from prompts import PLANNER_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT, FIXER_SYSTEM_PROMPT
from code_generator import generate_from_llm_output, generate_bpy_code
from deterministic_fixer import deterministic_fix, validate_spec
from spatial_planner import generate_spec_from_request

colorama.init(autoreset=True)

client = OpenAI(
    base_url='http://127.0.0.1:11434/v1',
    api_key='ollama_local'
)

MODEL_CONFIG = {
    "planner": "qwen2.5-coder:7b",
    "coder": "qwen2.5-coder:7b",
    "fixer": "qwen2.5-coder:7b",
}


def _get_available_models():
    try:
        req = __import__('urllib').request.Request('http://127.0.0.1:11434/api/tags')
        with __import__('urllib').request.urlopen(req, timeout=3) as resp:
            data = json.loads(__import__('json').loads(resp.read()))
            return {m['name'] for m in data.get('models', [])}
    except Exception:
        return set()


_available = _get_available_models()
if _available:
    planner_candidates = ["qwen2.5-coder:7b", "deepseek-coder-v2", "qwen2.5:7b"]
    for candidate in planner_candidates:
        if candidate in _available:
            MODEL_CONFIG["planner"] = candidate
            print(Fore.GREEN + f"[Model] Planner 使用 '{candidate}'")
            break
    print(Fore.GREEN + f"[Model] Coder/Fixer 使用 '{MODEL_CONFIG['coder']}'")


def call_llm(system_prompt, user_message, temperature=0.1, agent_type="coder"):
    model = MODEL_CONFIG.get(agent_type, MODEL_CONFIG["coder"])
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content


def extract_code(text):
    """从 LLM 输出提取 Python 代码"""
    matches = re.findall(r"```python\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if matches:
        return "\n\n".join(m.strip() for m in matches if m.strip())
    matches = re.findall(r"```\s*(.*?)```", text, re.DOTALL)
    if matches:
        return "\n\n".join(m.strip() for m in matches if m.strip() and 'import' in m.lower())
    import_match = re.search(r"(import bpy.*)", text, re.DOTALL)
    if import_match:
        return import_match.group(1).strip()
    return text.strip()


def run_planner(user_request):
    """Planner Agent: 将用户需求转为结构化规格"""
    print(Fore.CYAN + "\n[Planner Agent] 正在分析任务并生成空间布局规格...")
    plan = call_llm(PLANNER_SYSTEM_PROMPT, user_request, temperature=0.3, agent_type="planner")
    print(Fore.CYAN + f"[Planner 输出]:\n{plan[:800]}")
    return plan


def _infer_object_type(obj):
    """为对象推断类型（如果缺失或无效），并补充默认尺寸"""
    from object_types import lookup_object, get_default_dims, get_type_info
    # 只在 type 缺失或不是注册表中有效类型时推断
    current_type = obj.get("type", "")
    if not current_type or current_type == "object":
        t = lookup_object(obj["name"].lower())
        if t:
            obj["type"] = t
    elif not get_type_info(current_type):
        # LLM 输出了无效类型（如 "furniture"），从名称推断
        t = lookup_object(obj["name"].lower())
        if t:
            obj["type"] = t

    # 如果尺寸是默认值，补充注册表中的默认尺寸
    if obj.get("dimensions") == [2.0, 2.0, 2.0]:
        t = lookup_object(obj["name"].lower())
        if t:
            default_dims = get_default_dims(t)
            if default_dims:
                obj["dimensions"] = list(default_dims)


def _apply_deterministic_positioning(spec, user_request):
    """
    核心函数：用确定性逻辑（spatial_planner.compute_positions）
    覆盖 LLM 生成的坐标，确保布局正确。
    同时用确定性规划器补充 LLM 遗漏的物体。
    这是「LLM主导理解，数学逻辑保底」的关键。
    """
    if not spec or "objects" not in spec or not spec["objects"]:
        return spec

    # 1. 为所有对象推断类型
    for obj in spec["objects"]:
        _infer_object_type(obj)

    # 2. 用确定性规划器补充 LLM 遗漏的物体（按类型数量比较）
    from spatial_planner import generate_spec_from_request
    try:
        ideal_spec = generate_spec_from_request(user_request)
        if ideal_spec and ideal_spec.get("objects"):
            from collections import Counter
            def _get_canonical_type(obj):
                """通过名称获取规范的物体类型（比 LLM 输出的 type 字段更可靠）。"""
                from object_types import lookup_object
                t = lookup_object(obj["name"].lower())
                if t:
                    return t
                return obj.get("type", "") or ""

            # 统计 LLM 已输出的每种类型数量（使用规范类型）
            llm_type_counts = Counter()
            for o in spec["objects"]:
                t = _get_canonical_type(o)
                if t:
                    llm_type_counts[t] += 1

            # 统计确定性规划期望的每种类型数量（使用规范类型）
            ideal_type_counts = Counter()
            for o in ideal_spec["objects"]:
                t = _get_canonical_type(o)
                if t:
                    ideal_type_counts[t] += 1

            for ideal_obj in ideal_spec["objects"]:
                t = _get_canonical_type(ideal_obj)
                if not t:
                    continue
                from object_types import get_category
                cat = get_category(t)
                if cat not in ('platform', 'satellite'):
                    continue
                # 如果 LLM 输出数量 < 规划器期望数量，补充缺失的
                if llm_type_counts.get(t, 0) < ideal_type_counts.get(t, 0):
                    spec["objects"].append(ideal_obj)
                    llm_type_counts[t] += 1
                    print(Fore.CYAN + f"[定位补充] 确定性规划器补充了 '{ideal_obj['name']}' (type={t})")
    except Exception as e:
        print(Fore.RED + f"[定位补充] 失败: {e}")

    # 3. 关键修复：用确定性规划器的正确尺寸覆盖 LLM 的尺寸，
    #    防止 LLM 输出的错误尺寸（如床深度用默认值 1.6 代替用户指定的 2.2）
    #    导致 compute_positions 算出的布局产生重叠
    if ideal_spec and ideal_spec.get("objects"):
        ideal_dims_by_type = {}
        for ideal_obj in ideal_spec["objects"]:
            t = ideal_obj.get("type", "")
            if t and t not in ideal_dims_by_type:
                ideal_dims_by_type[t] = list(ideal_obj["dimensions"])
        for obj in spec["objects"]:
            t = obj.get("type", "")
            if t in ideal_dims_by_type:
                obj["dimensions"] = list(ideal_dims_by_type[t])

    # 5. 使用确定性逻辑计算正确坐标
    from spatial_planner import compute_positions
    objects = compute_positions(spec["objects"], user_request)

    # 6. 验证并返回
    from deterministic_fixer import validate_spec
    spec["objects"] = objects
    spec = validate_spec(spec)
    return spec


def run_coder(plan, user_request=""):
    """
    Coder Agent:
    1. LLM 理解场景 → 输出结构化规格（含物体类型、尺寸、关系）
    2. 确定性逻辑 compute_positions 计算精确坐标（替代 LLM 猜测的坐标）
    3. 生成 bpy 代码
    """
    print(Fore.MAGENTA + "\n[Coder Agent] 正在根据规划生成对象规格...")

    user_msg = (
        f"Here is the plan:\n{plan}\n\n"
        "Output a JSON specification with EXACT dimensions for each object.\n"
        'Use this format: ```json\n{"objects": [{"name": "...", '
        '"type": "table/chair/sofa/...", "dimensions": [w,d,h], '
        '"location": [x,y,z], "color": [r,g,b], "material_name": "..."}]}\n```'
    )

    llm_output = call_llm(CODER_SYSTEM_PROMPT, user_msg, temperature=0.05, agent_type="coder")

    # ============ 路径1: 从 LLM 输出提取规格 + 确定性定位 ============
    code, spec = generate_from_llm_output(llm_output)
    if code and spec:
        # 用确定性逻辑计算正确坐标（覆盖 LLM 猜测的坐标）
        spec = _apply_deterministic_positioning(spec, user_request)
        code = generate_bpy_code(spec)
        print(Fore.MAGENTA + f"[Coder] LLM 规划 + 确定性定位成功 ({len(spec['objects'])} 个对象)")
        return code

    # ============ 路径2: 从 Planner 回退提取规格 + 确定性定位 ============
    print(Fore.YELLOW + "[Coder] 从 Planner 回退提取规格...")
    code, spec = generate_from_llm_output(plan)
    if code and spec:
        spec = _apply_deterministic_positioning(spec, user_request)
        code = generate_bpy_code(spec)
        print(Fore.MAGENTA + f"[Coder] Planner 回退 + 确定性定位成功 ({len(spec['objects'])} 个对象)")
        return code

    # ============ 路径3: 确定性规划器从 user_request 保底 ============
    print(Fore.YELLOW + "[Coder] LLM 输出解析失败，使用确定性规划器从用户请求生成...")
    try:
        from spatial_planner import generate_spec_from_request
        spec = generate_spec_from_request(user_request)
        if spec and spec.get("objects") and len(spec["objects"]) > 0:
            code = generate_bpy_code(spec)
            print(Fore.MAGENTA + f"[Coder] 确定性规划器成功 ({len(spec['objects'])} 个对象)")
            return code
    except Exception as e:
        print(Fore.RED + f"[Coder] 确定性规划器失败: {e}")

    # ============ 路径4: LLM 直接生成代码（最终回退） ============
    print(Fore.YELLOW + "[Coder] 最终回退：尝试直接生成 bpy 代码...")
    code_response = call_llm(CODER_SYSTEM_PROMPT,
                             f"Here is the plan:\n{plan}\n\nWrite the complete Blender Python script.",
                             temperature=0.0, agent_type="coder")
    extracted = extract_code(code_response)
    if extracted and "import bpy" in extracted:
        print(Fore.MAGENTA + f"[Coder] 直接代码生成成功 ({len(extracted)} 字符)")
        return extracted

    print(Fore.RED + "[Coder] 所有生成方式失败！")
    return "import bpy\n# Error: code generation failed"


def run_fixer(previous_code, error_message, user_request=""):
    """
    Fixer: 优先使用确定性布局重算，失败时回退到 LLM。
    核心思路：通过 deterministic_fix 用 compute_positions 重新计算全局布局，
    而非逐点修补个别坐标。
    """
    print(Fore.RED + "\n[Fixer] 分析物理错误并计算修正坐标...")

    # 1. 优先：确定性修正（含全局布局重算）
    spec = deterministic_fix(previous_code, error_message, user_request)
    if spec and spec.get("objects"):
        spec = validate_spec(spec)
        code = generate_bpy_code(spec)
        print(Fore.MAGENTA + f"[Fixer] 确定性修正成功 ({len(spec['objects'])} 个对象)")
        return code

    # 2. 回退：LLM JSON 修正（让 LLM 重新理解场景，但坐标仍由确定性逻辑计算）
    print(Fore.YELLOW + "[Fixer] 确定性修正失败，回退到 LLM 修正...")
    user_prompt = (
        "=== PHYSICS ERROR REPORT ===\n"
        f"{error_message}\n\n"
        "Output a corrected JSON spec with object types and dimensions.\n"
        "The system will compute correct coordinates automatically.\n"
        'Format: ```json\n{"objects": [{"name": "...", '
        '"type": "table/chair/sofa/...", "dimensions": [w,d,h], '
        '"location": [x,y,z], "color": [r,g,b], "material_name": "..."}]}\n```'
    )
    llm_output = call_llm(FIXER_SYSTEM_PROMPT, user_prompt, temperature=0.1, agent_type="fixer")
    code, spec = generate_from_llm_output(llm_output)
    if code and spec:
        # LLM 理解场景结构，但坐标由确定性逻辑重新计算
        spec = _apply_deterministic_positioning(spec, user_request)
        code = generate_bpy_code(spec)
        print(Fore.MAGENTA + f"[Fixer] LLM 理解 + 确定性定位成功 ({len(spec['objects'])} 个对象)")
        return code

    # 3. 最终回退：LLM 直接修改代码
    print(Fore.YELLOW + "[Fixer] 回退：LLM 直接修改代码...")
    code = _fallback_fix(previous_code, error_message)
    if code:
        print(Fore.MAGENTA + "[Fixer] LLM 代码修正完成")
        return code

    print(Fore.RED + "[Fixer] 所有修正方式失败，返回原代码")
    return previous_code


def _fallback_fix(previous_code, error_message):
    """回退修正：让 LLM 直接修改 Python 代码"""
    user_prompt = (
        f"=== PREVIOUS CODE ===\n{previous_code}\n\n"
        f"=== ERROR REPORT ===\n{error_message}\n\n"
        "Fix the code. Use obj.dimensions = (w, d, h) for exact sizes. "
        "Output complete Python script in ```python ``` block."
    )
    llm_output = call_llm(FIXER_SYSTEM_PROMPT, user_prompt, temperature=0.1, agent_type="fixer")
    extracted = extract_code(llm_output)
    if extracted and "import bpy" in extracted:
        return extracted
    return None

"""
确定性纠错模块：从物理错误报告中解析坐标和重叠信息，
直接计算修正后的坐标，不依赖 LLM。
"""
import re
import math
import json


# 预定义正确的对象尺寸（用于修复默认立方体 2x2x2 的问题）
DEFAULT_DIMENSIONS = {
    "table": [1.2, 0.8, 0.75],
    "desk": [1.2, 0.6, 0.75],
    "chair": [0.4, 0.4, 0.9],
    "seat": [0.4, 0.4, 0.9],
    "stool": [0.3, 0.3, 0.7],
    "sofa": [2.0, 0.8, 0.8],
    "couch": [2.0, 0.8, 0.8],
    "bed": [2.0, 1.5, 0.6],
    "bookshelf": [0.8, 0.3, 1.8],
    "shelf": [0.8, 0.3, 1.8],
    "cabinet": [0.8, 0.4, 1.6],
    "lamp": [0.2, 0.2, 1.5],
    "rug": [1.5, 2.0, 0.05],
    "plant": [0.3, 0.3, 1.0],
    "vase": [0.15, 0.15, 0.3],
    "tv": [1.0, 0.1, 0.6],
    "monitor": [0.6, 0.05, 0.4],
}


def parse_error_report(error_message):
    """
    从物理错误报告文本中解析出结构化的错误信息。
    返回: {"intersections": [...], "undergrounds": [...], "too_close": [...], "floating": [...]}
    """
    result = {
        "intersections": [],
        "undergrounds": [],
        "too_close": [],
        "floating": [],
    }

    for line in error_message.split('\n'):
        line = line.strip().lstrip('- ')

        if line.startswith('INTERSECTION:'):
            # 解析: 'ObjA'[center=(x,y,z) size=(w,d,h)] OVERLAPS 'ObjB'[...] | Overlap: X=. Y=. Z=. | Separation: AXIS | direction
            match = re.search(
                r"INTERSECTION:\s*'([^']+)'\[center=\(([^)]+)\)\s*size=\(([^)]+)\)\]\s*"
                r"OVERLAPS\s*'([^']+)'\[center=\(([^)]+)\)\s*size=\(([^)]+)\)\]\s*"
                r"\|\s*Overlap:\s*X=([\d.]+)m\s*Y=([\d.]+)m\s*Z=([\d.]+)m\s*"
                r"\|\s*Separation:\s*(\w+)\s*axis\s*\|\s*(.+)",
                line
            )
            if match:
                result["intersections"].append({
                    "obj_a": match.group(1),
                    "center_a": [float(x) for x in match.group(2).split(',')],
                    "size_a": [float(x) for x in match.group(3).split(',')],
                    "obj_b": match.group(4),
                    "center_b": [float(x) for x in match.group(5).split(',')],
                    "size_b": [float(x) for x in match.group(6).split(',')],
                    "overlap_x": float(match.group(7)),
                    "overlap_y": float(match.group(8)),
                    "overlap_z": float(match.group(9)),
                    "sep_axis": match.group(10),
                    "direction": match.group(11),
                })

        elif line.startswith('UNDERGROUND:'):
            match = re.search(
                r"UNDERGROUND:\s*'([^']+)'.*?Center Z=([\d.]+)m,\s*height=([\d.]+)m.*?FIX:.*?location\.z\s*=\s*([\d.]+)",
                line
            )
            if match:
                result["undergrounds"].append({
                    "obj_name": match.group(1),
                    "center_z": float(match.group(2)),
                    "height": float(match.group(3)),
                    "fix_z": float(match.group(4)),
                })

        elif line.startswith('TOO_CLOSE:'):
            match = re.search(
                r"TOO_CLOSE:\s*'([^']+)'\s+too close to\s+'([^']+)'\.\s*"
                r"Distance=([\d.]+)m,\s*min=([\d.]+)m\.\s*"
                r"Move away by\s*([\d.]+)m",
                line
            )
            if match:
                result["too_close"].append({
                    "sat_name": match.group(1),
                    "plat_name": match.group(2),
                    "distance": float(match.group(3)),
                    "min_distance": float(match.group(4)),
                    "fix_by": float(match.group(5)),
                })

        elif line.startswith('FLOATING:'):
            match = re.search(
                r"FLOATING:\s*'([^']+)'.*?Center Z=([\d.]+)m,\s*height=([\d.]+)m.*?FIX:.*?location\.z\s*=\s*([\d.]+)",
                line
            )
            if match:
                result["floating"].append({
                    "obj_name": match.group(1),
                    "center_z": float(match.group(2)),
                    "height": float(match.group(3)),
                    "fix_z": float(match.group(4)),
                })

    return result


def validate_spec(spec):
    """
    验证并修正规格中的明显空间错误。
    在代码生成前调用，确保初始布局合理。
    """
    if not spec or "objects" not in spec:
        return spec

    objects = spec["objects"]
    _validate_and_correct_layout(objects)
    return spec


def _validate_and_correct_layout(objects):
    """修正明显的空间布局错误（使用 object_types 注册表进行类型识别）。"""
    from object_types import PLATFORM_TYPES, SATELLITE_TYPES, lookup_object, get_default_dims

    # 1. 修复默认尺寸
    for obj in objects:
        dims = obj.get("dimensions", [2.0, 2.0, 2.0])
        if dims == [2.0, 2.0, 2.0]:
            type_key = lookup_object(obj["name"].lower())
            if type_key:
                obj["dimensions"] = get_default_dims(type_key)

    # 2. 识别平台和附属物体（优先使用 type，回退到名称匹配）
    platforms = [o for o in objects
                 if o.get("type", "") in PLATFORM_TYPES
                 or any(kw in o["name"].lower() for kw in PLATFORM_TYPES)]
    satellites = [o for o in objects
                  if o.get("type", "") in SATELLITE_TYPES
                  or any(kw in o["name"].lower() for kw in SATELLITE_TYPES)]

    # 按尺寸排序平台，保证主平台选择与 compute_positions 一致
    platforms.sort(key=lambda p: -(p['dimensions'][0] * p['dimensions'][1]))
    main_platform = platforms[0] if platforms else None
    if not main_platform:
        for obj in objects:
            dims = obj.get("dimensions", [1, 1, 1])
            obj["location"] = obj.get("location", [0, 0, 0])
            obj["location"][2] = dims[2] / 2
        return

    # 3. 确保主平台在地面上
    p_dims = main_platform["dimensions"]
    main_platform["location"] = main_platform.get("location", [0, 0, 0])
    main_platform["location"][2] = p_dims[2] / 2

    # 4. 修正附属物体位置（仅修正明显错误的位置，不覆盖已正确放置的）
    if satellites:
        p_loc = main_platform["location"]
        p_dims = main_platform["dimensions"]
        gap = 0.25
        margin = 0.1

        for sat in satellites:
            s_dims = sat["dimensions"]
            s_loc = sat.get("location", [0, 0, 0])
            min_y = p_dims[1] / 2 + s_dims[1] / 2 + 0.15

            # 仅修正 Y 方向明显偏离的卫星（距离太近表示位置未正确设置）
            if abs(s_loc[1] - p_loc[1]) < min_y:
                # 位置明显不对，使用 4 面分布逻辑重新计算
                # 此处只做保守修正：确保 Z 在地面，Y 方向有合理间距
                s_loc[2] = s_dims[2] / 2

    # 5. 其他非附属物体：排成一排
    others = [o for o in objects if o not in platforms and o not in satellites]
    y_offset = main_platform["location"][1] + main_platform["dimensions"][1] + 0.5
    for i, obj in enumerate(others):
        dims = obj.get("dimensions", [1, 1, 1])
        loc = obj.get("location", [0, 0, 0])
        loc[0] = 0
        loc[1] = y_offset + i * 1.0
        loc[2] = dims[2] / 2


def deterministic_fix(previous_code, error_message, user_request=""):
    """
    根据物理错误报告，使用确定性逻辑重新计算全局布局。

    核心步骤：
    1. 从代码中提取所有物体的类型和尺寸
    2. 用 spatial_planner.compute_positions 重新计算所有坐标
    3. 再用 _apply_fixes 对特定错误做精确修补
    完全不需要 LLM。
    """
    errors = parse_error_report(error_message)

    # 从原代码中提取对象信息
    objects = _extract_objects_from_code(previous_code)

    if not objects:
        return None

    # 补充：用确定性规划器补充代码中可能遗漏的物体（同 agents.py 逻辑）
    if user_request:
        try:
            from spatial_planner import generate_spec_from_request
            from object_types import lookup_object, get_category
            ideal_spec = generate_spec_from_request(user_request)
            if ideal_spec and ideal_spec.get("objects"):
                def _get_canonical_type(obj):
                    t = lookup_object(obj["name"].lower())
                    if t:
                        return t
                    return obj.get("type", "") or ""

                cur_type_counts = Counter()
                for o in objects:
                    t = _get_canonical_type(o)
                    if t:
                        cur_type_counts[t] += 1
                ideal_type_counts = Counter()
                for o in ideal_spec["objects"]:
                    t = _get_canonical_type(o)
                    if t:
                        ideal_type_counts[t] += 1
                for ideal_obj in ideal_spec["objects"]:
                    t = _get_canonical_type(ideal_obj)
                    if not t:
                        continue
                    cat = get_category(t)
                    if cat not in ('platform', 'satellite'):
                        continue
                    if cur_type_counts.get(t, 0) < ideal_type_counts.get(t, 0):
                        objects.append({
                            "name": ideal_obj["name"],
                            "type": t,
                            "dimensions": list(ideal_obj["dimensions"]),
                            "color": list(ideal_obj.get("color", [0.5, 0.5, 0.5])),
                            "material_name": ideal_obj.get("material_name", "Material"),
                        })
                        cur_type_counts[t] += 1
        except Exception:
            pass

    # ============ 关键改进：全局布局重算 ============
    # 使用 spatial_planner 的确定性定位逻辑重新计算所有坐标
    # 而不是逐点修补个别坐标
    from spatial_planner import compute_positions
    try:
        # 确保所有对象有正确的 type 字段（推断或修正无效类型）
        from object_types import lookup_object, get_type_info
        for obj in objects:
            obj_type = obj.get("type", "")
            if not obj_type or obj_type in ("object", "") or not get_type_info(obj_type):
                t = lookup_object(obj["name"].lower())
                if t:
                    obj["type"] = t

        # 关键修复：用确定性规划器的正确尺寸覆盖提取的尺寸，
        # 防止 LLM 输出的错误尺寸（如床深度用默认值 1.6 代替用户指定的 2.2）
        # 导致 compute_positions 算出的布局产生重叠
        if user_request:
            try:
                from spatial_planner import generate_spec_from_request
                ideal_spec = generate_spec_from_request(user_request)
                if ideal_spec and ideal_spec.get("objects"):
                    # 构建 type→正确尺寸 映射（按类型匹配，不受 LLM 命名差异影响）
                    ideal_dims_by_type = {}
                    for ideal_obj in ideal_spec["objects"]:
                        t = ideal_obj.get("type", "")
                        if t:
                            # 同类型的尺寸应该相同，用第一个遇到的即可
                            if t not in ideal_dims_by_type:
                                ideal_dims_by_type[t] = list(ideal_obj["dimensions"])
                    # 用理想尺寸覆盖提取对象的尺寸
                    for obj in objects:
                        t = obj.get("type", "")
                        if t in ideal_dims_by_type:
                            obj["dimensions"] = list(ideal_dims_by_type[t])
            except Exception:
                pass

        objects = compute_positions(objects, user_request)
    except Exception as e:
        # 如果 compute_positions 失败，回退到原逻辑
        pass

    # 应用错误报告中的特定修正（作为第二道防线）
    objects = _apply_fixes(objects, errors)

    return {"objects": objects}


def _extract_objects_from_code(code):
    """从 bpy 代码中提取逻辑对象（支持复合物体如桌子=桌面+4腿）。

    优先解析 generate_bpy_code 生成的 section header 注释:
        # === ObjectName: WxDxHm at (x, y, z) ===
    回退时解析单个 primitive_cube_add 调用。
    """
    objects = []
    seen_names = set()

    # 1. 解析材质定义：提取颜色映射
    mat_colors = {}
    mat_pattern = re.compile(
        r"mat_(\w+)\.node_tree\.nodes\['Principled BSDF'\]\.inputs\['Base Color'\]"
        r"\.default_value\s*=\s*\(([\d.]+),\s*([\d.]+),\s*([\d.]+)",
    )
    for m in mat_pattern.finditer(code):
        mat_colors[m.group(1)] = [float(m.group(2)), float(m.group(3)), float(m.group(4))]

    # 2. 主路径：解析 section header 获取逻辑对象
    # 格式: # === Name: WxDxHm at (x, y, z) ===
    section_pattern = re.compile(
        r'#\s*===\s*(\w+):\s*([\d.]+)x([\d.]+)x([\d.]+)m\s*'
        r'at\s*\((-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)\)\s*==='
    )
    for m in section_pattern.finditer(code):
        name = m.group(1)
        if name in seen_names:
            continue
        seen_names.add(name)

        dims = [float(m.group(2)), float(m.group(3)), float(m.group(4))]
        loc = [float(m.group(5)), float(m.group(6)), float(m.group(7))]

        # 推测类型（使用注册表）
        from object_types import lookup_object
        obj_type = lookup_object(name.lower()) or "object"

        # 提取材质和颜色：扫描该 section 内的 primitive blocks
        section_start = m.start()
        next_section = re.search(r'#\s*===', code[section_start + 1:])
        section_end = section_start + 1 + next_section.start() if next_section else len(code)
        section_code = code[section_start:section_end]

        mat_match = re.search(r"obj\.data\.materials\.append\(mat_(\w+)\)", section_code)
        mat_name = mat_match.group(1).capitalize() if mat_match else "Material"
        color = mat_colors.get(mat_match.group(1) if mat_match else "", [0.5, 0.5, 0.5])

        objects.append({
            "name": name,
            "dimensions": dims,
            "location": loc,
            "color": color,
            "material_name": mat_name,
            "type": obj_type,
        })

    # 3. 回退：没有 section headers 时解析单个 primitive_cube_add
    if not objects:
        for block in re.split(r'(?=bpy\.ops\.mesh\.primitive_cube_add)', code):
            loc_match = re.search(r'location=\((-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)\)', block)
            name_match = re.search(r"obj\.name\s*=\s*['\"](\w+)['\"]", block)
            if not loc_match or not name_match:
                continue

            name = name_match.group(1)
            # 跳过复合物体的零件（所有已知部件后缀）
            PART_SUFFIXES = [
                '_top', '_seat', '_backrest', '_mattress', '_headboard',
                '_armrest_L', '_armrest_R', '_side_L', '_side_R',
                '_tank', '_bowl', '_tub', '_counter', '_cabinet',
                '_back', '_shelf',
            ]
            is_part = any(
                name.endswith(s) for s in PART_SUFFIXES
            ) or re.search(r'_(?:leg|shelf)_\d+$', name)
            if is_part:
                continue

            loc = [float(loc_match.group(1)), float(loc_match.group(2)), float(loc_match.group(3))]

            dim_match = re.search(r'obj\.dimensions\s*=\s*\(([\d.]+),\s*([\d.]+),\s*([\d.]+)\)', block)
            if dim_match:
                dims = [float(dim_match.group(1)), float(dim_match.group(2)), float(dim_match.group(3))]
            else:
                # 回退：解析 obj.scale（scale = dimensions/2，因为默认立方体为 2x2x2）
                scale_match = re.search(r'obj\.scale\s*=\s*\(([\d.]+),\s*([\d.]+),\s*([\d.]+)\)', block)
                if scale_match:
                    dims = [float(scale_match.group(1)) * 2,
                            float(scale_match.group(2)) * 2,
                            float(scale_match.group(3)) * 2]
                else:
                    dims = [2.0, 2.0, 2.0]

            # 提取材质名，再通过材质映射表获取颜色（而不是在块内扫描 default_value）
            mat_match = re.search(r'mat_(\w+)', block)
            mat_key = mat_match.group(1).lower() if mat_match else ""
            mat_name = mat_match.group(1).capitalize() if mat_match else "Material"
            color = mat_colors.get(mat_key, [0.5, 0.5, 0.5])

            objects.append({
                "name": name,
                "dimensions": dims,
                "location": loc,
                "color": color,
                "material_name": mat_name,
                "type": "object",
            })

    return objects


def _apply_fixes(objects, errors):
    """对对象列表应用所有错误修正"""
    from object_types import lookup_object, get_default_dims

    def _fix_dimensions(obj):
        """如果对象的尺寸是默认立方体 (2,2,2)，从对象名称推断正确尺寸"""
        dims = obj.get("dimensions", [2.0, 2.0, 2.0])
        if dims == [2.0, 2.0, 2.0]:
            type_key = lookup_object(obj["name"].lower())
            if type_key:
                obj["dimensions"] = get_default_dims(type_key)

    def _calculate_chair_position(table, chair, direction="front"):
        """计算椅子相对于桌子的正确位置"""
        t_loc = table["location"]
        t_dims = table["dimensions"]
        c_dims = chair["dimensions"]
        gap = 0.25

        # 椅子在桌子前方 (负Y) 或 后方 (正Y)
        y_sign = -1 if direction == "front" else 1
        y = t_loc[1] + y_sign * (t_dims[1] / 2 + c_dims[1] / 2 + gap)

        return [
            t_loc[0],  # X: 与桌子中心对齐
            y,
            c_dims[2] / 2  # Z: 在地面上
        ]

    obj_map = {o["name"]: o for o in objects}

    # 首先修复所有默认尺寸的对象
    for obj in objects:
        _fix_dimensions(obj)

    # 识别桌子和椅子
    table_obj = None
    chair_objs = []
    for obj in objects:
        name_lower = obj["name"].lower()
        if "table" in name_lower:
            table_obj = obj
        elif "chair" in name_lower:
            chair_objs.append(obj)

    # 如果椅子位置明显错误（在X轴偏移而非Y轴），重新计算正确位置
    if table_obj and chair_objs:
        t_y = table_obj["location"][1]
        for i, chair in enumerate(chair_objs):
            c_y = chair["location"][1]
            c_x = chair["location"][0]
            # 如果椅子X偏移较大而Y偏移较小，说明模型混淆了轴
            if abs(c_x) > 0.1 and abs(c_y - t_y) < 0.3:
                direction = "front" if i == 0 else "back"
                chair["location"] = _calculate_chair_position(table_obj, chair, direction)

    # 1. 处理 UNDERGROUND: 直接应用建议的 Z 值
    for err in errors["undergrounds"]:
        name = err["obj_name"]
        if name in obj_map:
            obj_map[name]["location"][2] = err["fix_z"]
            _fix_dimensions(obj_map[name])

    # 2. 处理 INTERSECTION: 计算并应用分离
    for err in errors["intersections"]:
        name_a = err["obj_a"]
        name_b = err["obj_b"]
        sep_axis = err["sep_axis"]
        axis_idx = {"X": 0, "Y": 1, "Z": 2}[sep_axis]

        # 确定哪个对象更小（应该移动）
        size_a = err["size_a"][axis_idx] * err["size_a"][(axis_idx + 1) % 3]
        size_b = err["size_b"][axis_idx] * err["size_b"][(axis_idx + 1) % 3]

        # 解析建议的分离距离
        sep_match = re.search(r"by\s+([\d.]+)m", err["direction"])
        if sep_match:
            sep_amount = float(sep_match.group(1))
        else:
            sep_amount = err[f"overlap_{sep_axis.lower()}"] + 0.1

        # 移动较小的对象
        if size_a <= size_b and name_a in obj_map:
            move_obj = name_a
        elif name_b in obj_map:
            move_obj = name_b
        else:
            continue

        # 确定移动方向
        if f"'{move_obj}' -{sep_axis}" in err["direction"]:
            obj_map[move_obj]["location"][axis_idx] -= sep_amount
        elif f"'{move_obj}' +{sep_axis}" in err["direction"]:
            obj_map[move_obj]["location"][axis_idx] += sep_amount
        else:
            # 回退：根据中心位置判断
            if move_obj == name_a:
                if err["center_a"][axis_idx] > err["center_b"][axis_idx]:
                    obj_map[move_obj]["location"][axis_idx] += sep_amount
                else:
                    obj_map[move_obj]["location"][axis_idx] -= sep_amount
            else:
                if err["center_b"][axis_idx] > err["center_a"][axis_idx]:
                    obj_map[move_obj]["location"][axis_idx] += sep_amount
                else:
                    obj_map[move_obj]["location"][axis_idx] -= sep_amount

        # 确保移动对象有正确的 dimensions
        if move_obj in obj_map:
            _fix_dimensions(obj_map[move_obj])

    # 3. 处理 TOO_CLOSE: 沿径向（卫星→平台方向的反向）推开卫星
    for err in errors["too_close"]:
        name = err["sat_name"]
        if name in obj_map:
            sat = obj_map[name]
            plat = obj_map.get(err["plat_name"])
            if plat:
                # 沿 (sat_xy - plat_xy) 方向推开，确保径向远离
                dx = sat["location"][0] - plat["location"][0]
                dy = sat["location"][1] - plat["location"][1]
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > 0.001:
                    sat["location"][0] += (dx / dist) * err["fix_by"]
                    sat["location"][1] += (dy / dist) * err["fix_by"]
                else:
                    # 重合时退回到 Y 方向推开
                    sat["location"][1] += err["fix_by"]
            # 确保 Z 在地面上
            dims = sat["dimensions"]
            sat["location"][2] = dims[2] / 2

    # 4. 处理 FLOATING: 设置 Z = height/2
    for err in errors["floating"]:
        name = err["obj_name"]
        if name in obj_map:
            obj_map[name]["location"][2] = err["fix_z"]
            obj_map[name]["dimensions"][2] = err["height"]

    # 最终验证：确保所有对象都在地面上
    for obj in objects:
        obj["location"][2] = max(obj["location"][2], obj["dimensions"][2] / 2)

    return list(obj_map.values())

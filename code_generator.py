"""
确定性代码生成器：根据结构化规格生成正确的 Blender Python 代码。
支持复合物体（桌子=桌面+4腿, 椅子=座面+靠背+4腿, 沙发, 床, 书架），
以及基本几何体（立方体, 球体, 圆柱体）。
"""
import json
import re
from object_types import get_geometry, get_builder


def _create_material(name, color):
    """生成一个 Principled BSDF 材质的 Python 代码"""
    r, g, b = color[0], color[1], color[2]
    return [
        f"mat_{name.lower()} = bpy.data.materials.new(name='{name}')",
        f"mat_{name.lower()}.use_nodes = True",
        f"mat_{name.lower()}.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = ({r}, {g}, {b}, 1.0)",
        f"mat_{name.lower()}.diffuse_color = ({r}, {g}, {b}, 1.0)", 
    ]


def _cube_block(name, loc, scale, mat_name, rotation_z=None):
    """生成一个立方体的 Python 代码块"""
    lines = [
        f"# {name}",
        f"bpy.ops.mesh.primitive_cube_add(location=({loc[0]:.3f}, {loc[1]:.3f}, {loc[2]:.3f}))",
        f"obj = bpy.context.active_object",
        f"obj.name = '{name}'",
        f"obj.scale = ({scale[0]:.4f}, {scale[1]:.4f}, {scale[2]:.4f})",
    ]
    if rotation_z is not None and abs(rotation_z) > 0.001:
        lines.append(f"obj.rotation_euler = (0, 0, {rotation_z:.4f})")
    lines += [
        f"obj.data.materials.append(mat_{mat_name.lower()})",
        "",
    ]
    return lines


def _sphere_block(name, loc, radius, mat_name, rotation_z=None):
    """生成一个 UV 球体的 Python 代码块"""
    lines = [
        f"# {name} (sphere)",
        f"bpy.ops.mesh.primitive_uv_sphere_add(radius={radius:.4f}, location=({loc[0]:.3f}, {loc[1]:.3f}, {loc[2]:.3f}))",
        f"obj = bpy.context.active_object",
        f"obj.name = '{name}'",
    ]
    if rotation_z is not None and abs(rotation_z) > 0.001:
        lines.append(f"obj.rotation_euler = (0, 0, {rotation_z:.4f})")
    lines += [
        f"obj.data.materials.append(mat_{mat_name.lower()})",
        "",
    ]
    return lines


def _cylinder_block(name, loc, radius, depth, mat_name, rotation_z=None):
    """生成一个圆柱体的 Python 代码块 (depth 沿 Z 轴)"""
    lines = [
        f"# {name} (cylinder)",
        f"bpy.ops.mesh.primitive_cylinder_add(radius={radius:.4f}, depth={depth:.4f}, location=({loc[0]:.3f}, {loc[1]:.3f}, {loc[2]:.3f}))",
        f"obj = bpy.context.active_object",
        f"obj.name = '{name}'",
    ]
    if rotation_z is not None and abs(rotation_z) > 0.001:
        lines.append(f"obj.rotation_euler = (0, 0, {rotation_z:.4f})")
    lines += [
        f"obj.data.materials.append(mat_{mat_name.lower()})",
        "",
    ]
    return lines


def _rot_xy(cx, cy, px, py, rot_z):
    """将点 (px,py) 绕中心 (cx,cy) 旋转 rot_z 弧度。"""
    import math
    dx, dy = px - cx, py - cy
    c, s = math.cos(rot_z), math.sin(rot_z)
    return cx + dx*c - dy*s, cy + dx*s + dy*c


def _join_parts_start():
    """记录当前场景中已有的物体，用于后续识别新创建的部件。"""
    return ["__before_parts = set(bpy.context.scene.objects.keys())"]


def _join_parts_end(name):
    """将自 _join_parts_start 以来创建的所有新物体合并为一个网格对象。"""
    return [
        f"# Join {name} composite parts into single object",
        f"__new_parts = [o for o in bpy.context.scene.objects if o.name not in __before_parts]",
        f"if len(__new_parts) > 1:",
        f"    bpy.ops.object.select_all(action='DESELECT')",
        f"    for __p in __new_parts: __p.select_set(True)",
        f"    bpy.context.view_layer.objects.active = __new_parts[0]",
        f"    bpy.ops.object.join()",
        f"    bpy.context.active_object.name = '{name}'",
        "",
    ]


def _make_block(name, loc, scale, mat_name, rotation_z=None):
    """生成一个立方体代码块（自动传递旋转参数）。"""
    return _cube_block(name, loc, scale, mat_name, rotation_z)


def _table_parts(name, dims, loc, mat_name, rotation_z=None):
    """
    桌子的复合几何体：桌面 + 4条腿
    命名规则: {name}_top, {name}_leg_1, ... (便于物理检测时归组)
    部件尺寸根据总尺寸自适应缩放。
    """
    b = lambda n, l, s: _cube_block(n, l, s, mat_name, rotation_z)
    w, d, h = dims
    cx, cy, cz = loc

    top_thickness = max(0.02, min(0.06, h * 0.06))
    leg_size = max(0.04, min(0.08, min(w, d) * 0.08))
    leg_height = h - top_thickness
    inset = leg_size * 1.5

    parts = []

    top_z = cz + h / 2 - top_thickness / 2
    parts += _cube_block(
        f"{name}_top",
        [cx, cy, top_z],
        [w / 2, d / 2, top_thickness / 2],
        mat_name
    )

    leg_z = leg_height / 2
    leg_locs = [
        [cx - w / 2 + inset, cy - d / 2 + inset, leg_z],
        [cx + w / 2 - inset, cy - d / 2 + inset, leg_z],
        [cx - w / 2 + inset, cy + d / 2 - inset, leg_z],
        [cx + w / 2 - inset, cy + d / 2 - inset, leg_z],
    ]
    for i, ll in enumerate(leg_locs):
        parts += _cube_block(
            f"{name}_leg_{i + 1}",
            ll,
            [leg_size / 2, leg_size / 2, leg_height / 2],
            mat_name
        )

    return parts


def _chair_parts(name, dims, loc, mat_name, rotation_z=None):
    """
    椅子的复合几何体：座面 + 靠背 + 4条腿
    命名规则: {name}_seat, {name}_backrest, {name}_leg_1, ...
    部件尺寸根据总尺寸自适应缩放。
    """
    w, d, h = dims
    cx, cy, cz = loc

    seat_thickness = max(0.02, min(0.05, h * 0.05))
    seat_height = max(0.35, min(0.55, h * 0.5))
    leg_thickness = max(0.03, min(0.05, min(w, d) * 0.1))
    backrest_thickness = max(0.02, min(0.05, d * 0.1))
    backrest_height = h - seat_thickness

    parts = []

    seat_z = seat_height + seat_thickness / 2
    seat_xy = [cx, cy]

    backrest_y = cy + d / 2 - backrest_thickness / 2
    backrest_z = seat_height + backrest_height / 2
    backrest_xy = [cx, backrest_y]

    leg_h = seat_height
    leg_z = leg_h / 2
    inset = 0.05
    leg_xy_list = [
        [cx - w / 2 + inset, cy - d / 2 + inset],
        [cx + w / 2 - inset, cy - d / 2 + inset],
        [cx - w / 2 + inset, cy + d / 2 - inset],
        [cx + w / 2 - inset, cy + d / 2 - inset],
    ]

    # 旋转所有部件位置；±90°时交换非对称部件的XY比例
    swap_xy = rotation_z and abs(abs(rotation_z) - 1.5708) < 0.01
    if rotation_z:
        seat_xy[0], seat_xy[1] = _rot_xy(cx, cy, seat_xy[0], seat_xy[1], rotation_z)
        backrest_xy[0], backrest_xy[1] = _rot_xy(cx, cy, backrest_xy[0], backrest_xy[1], rotation_z)
        leg_xy_list = [[_rot_xy(cx, cy, ll[0], ll[1], rotation_z)[0],
                        _rot_xy(cx, cy, ll[0], ll[1], rotation_z)[1],
                        ll[2] if len(ll) > 2 else leg_z] for ll in leg_xy_list]

    # 座面比例对称，不受旋转影响
    parts += _cube_block(f"{name}_seat",
        [seat_xy[0], seat_xy[1], seat_z],
        [w / 2, d / 2, seat_thickness / 2], mat_name)

    # 靠背：±90°时交换X/Y比例（靠背从宽X薄Y变为薄X宽Y）
    br_sx = backrest_thickness / 2 if swap_xy else w / 2
    br_sy = w / 2 if swap_xy else backrest_thickness / 2
    parts += _cube_block(f"{name}_backrest",
        [backrest_xy[0], backrest_xy[1], backrest_z],
        [br_sx, br_sy, backrest_height / 2], mat_name)

    for i, ll in enumerate(leg_xy_list):
        parts += _cube_block(f"{name}_leg_{i + 1}",
            [ll[0], ll[1], leg_z],
            [leg_thickness / 2, leg_thickness / 2, leg_h / 2], mat_name)

    return parts


def _sofa_parts(name, dims, loc, mat_name, rotation_z=None):
    """
    沙发的复合几何体：座面 + 2扶手 + 靠背 + 2前腿
    命名规则: {name}_seat, {name}_armrest_L/R, {name}_backrest, {name}_leg_1/2
    """
    w, d, h = dims
    cx, cy, cz = loc

    seat_h = h * 0.5
    armrest_w = max(0.08, w * 0.06)
    armrest_h = h * 0.4
    backrest_thick = max(0.08, d * 0.12)
    backrest_h = h * 0.55
    leg_h = max(0.1, h * 0.15)
    leg_size = max(0.05, min(w, d) * 0.06)

    parts = []

    # 座面
    seat_z = cz - h / 2 + leg_h + seat_h / 2
    parts += _cube_block(
        f"{name}_seat",
        [cx, cy, seat_z],
        [w / 2, d / 2, seat_h / 2],
        mat_name
                )

    # 左扶手
    armrest_z = seat_z + seat_h / 2 + armrest_h / 2
    armrest_x = cx - w / 2 + armrest_w / 2
    parts += _cube_block(
        f"{name}_armrest_L",
        [armrest_x, cy, armrest_z],
        [armrest_w / 2, d / 2, armrest_h / 2],
        mat_name
                )

    # 右扶手
    parts += _cube_block(
        f"{name}_armrest_R",
        [cx + w / 2 - armrest_w / 2, cy, armrest_z],
        [armrest_w / 2, d / 2, armrest_h / 2],
        mat_name
                )

    # 靠背
    backrest_y = cy + d / 2 - backrest_thick / 2
    backrest_z = seat_z + seat_h / 2 + backrest_h / 2
    parts += _cube_block(
        f"{name}_backrest",
        [cx, backrest_y, backrest_z],
        [w / 2, backrest_thick / 2, backrest_h / 2],
        mat_name
                )

    # 前腿
    leg_z = leg_h / 2
    leg_inset = leg_size
    parts += _cube_block(
        f"{name}_leg_1",
        [cx - w / 2 + leg_inset, cy - d / 2 + leg_inset, leg_z],
        [leg_size / 2, leg_size / 2, leg_h / 2],
        mat_name
                )

    parts += _cube_block(
        f"{name}_leg_2",
        [cx + w / 2 - leg_inset, cy - d / 2 + leg_inset, leg_z],
        [leg_size / 2, leg_size / 2, leg_h / 2],
        mat_name
                )

    return parts


def _bed_parts(name, dims, loc, mat_name, rotation_z=None):
    """
    床的复合几何体：床垫 + 床头板 + 4短腿
    命名规则: {name}_mattress, {name}_headboard, {name}_leg_1-4
    """
    w, d, h = dims
    cx, cy, cz = loc

    mattress_h = h * 0.45
    headboard_w = max(0.04, d * 0.06)
    headboard_h = h * 0.6
    leg_h = max(0.15, h * 0.22)
    leg_size = max(0.06, min(w, d) * 0.07)

    parts = []

    # 床垫
    mattress_z = cz - h / 2 + leg_h + mattress_h / 2
    parts += _cube_block(
        f"{name}_mattress",
        [cx, cy, mattress_z],
        [w / 2, d / 2, mattress_h / 2],
        mat_name
                )

    # 床头板（在 +Y 端）
    headboard_y = cy + d / 2 - headboard_w / 2
    headboard_z = cz - h / 2 + leg_h + headboard_h / 2
    parts += _cube_block(
        f"{name}_headboard",
        [cx, headboard_y, headboard_z],
        [w / 2, headboard_w / 2, headboard_h / 2],
        mat_name
                )

    # 4条腿
    leg_z = leg_h / 2
    leg_inset = leg_size * 1.5
    leg_locs = [
        [cx - w / 2 + leg_inset, cy - d / 2 + leg_inset, leg_z],
        [cx + w / 2 - leg_inset, cy - d / 2 + leg_inset, leg_z],
        [cx - w / 2 + leg_inset, cy + d / 2 - leg_inset, leg_z],
        [cx + w / 2 - leg_inset, cy + d / 2 - leg_inset, leg_z],
    ]
    for i, ll in enumerate(leg_locs):
        parts += _cube_block(
            f"{name}_leg_{i + 1}",
            ll,
            [leg_size / 2, leg_size / 2, leg_h / 2],
            mat_name
                )

    return parts


def _bookshelf_parts(name, dims, loc, mat_name, rotation_z=None):
    """
    书架的复合几何体：2侧板 + 背板 + 4层板
    命名规则: {name}_side_L/R, {name}_back, {name}_shelf_1-4
    """
    w, d, h = dims
    cx, cy, cz = loc

    side_thick = max(0.02, w * 0.04)
    back_thick = max(0.01, d * 0.05)
    shelf_thick = max(0.02, h * 0.015)
    interior_w = w - 2 * side_thick

    parts = []

    # 左侧板
    side_x = cx - w / 2 + side_thick / 2
    parts += _cube_block(
        f"{name}_side_L",
        [side_x, cy, cz],
        [side_thick / 2, d / 2, h / 2],
        mat_name
                )

    # 右侧板
    parts += _cube_block(
        f"{name}_side_R",
        [cx + w / 2 - side_thick / 2, cy, cz],
        [side_thick / 2, d / 2, h / 2],
        mat_name
                )

    # 背板
    back_y = cy + d / 2 - back_thick / 2
    parts += _cube_block(
        f"{name}_back",
        [cx, back_y, cz],
        [w / 2, back_thick / 2, h / 2],
        mat_name
                )

    # 4层隔板
    num_shelves = 4
    interior_h = h - shelf_thick * (num_shelves + 1)
    shelf_spacing = interior_h / (num_shelves + 1)
    for i in range(num_shelves):
        shelf_z = cz - h / 2 + shelf_thick / 2 + (i + 1) * (shelf_spacing + shelf_thick) - shelf_spacing
        # 实际位置
        base_z = cz - h / 2 + shelf_thick / 2
        shelf_z = base_z + (i + 1) * (h - shelf_thick) / (num_shelves + 1)
        parts += _cube_block(
            f"{name}_shelf_{i + 1}",
            [cx, cy, shelf_z],
            [interior_w / 2, d / 2, shelf_thick / 2],
            mat_name
                )

    return parts


def _toilet_parts(name, dims, loc, mat_name, rotation_z=None):
    """
    马桶的复合几何体：水箱(后排上部) + 座体(前排下部)
    命名规则: {name}_tank, {name}_bowl
    """
    w, d, h = dims
    cx, cy, cz = loc

    # 水箱占后部 35% 深度，占上部 60% 高度
    tank_d = d * 0.3
    tank_h = h * 0.55
    tank_w = w * 0.6
    tank_y = cy + d / 2 - tank_d / 2
    tank_z = cz - h / 2 + tank_h / 2 + h * 0.1

    # 座体占前部 70% 深度，占下部 40% 高度
    bowl_d = d * 0.65
    bowl_h = h * 0.4
    bowl_w = w * 0.8
    bowl_y = cy - d / 2 + bowl_d / 2
    bowl_z = cz - h / 2 + bowl_h / 2

    parts = []
    parts += _cube_block(f"{name}_tank", [cx, tank_y, tank_z],
                         [tank_w / 2, tank_d / 2, tank_h / 2], mat_name)
    parts += _cube_block(f"{name}_bowl", [cx, bowl_y, bowl_z],
                         [bowl_w / 2, bowl_d / 2, bowl_h / 2], mat_name)
    return parts


def _bathtub_parts(name, dims, loc, mat_name, rotation_z=None):
    """
    浴缸的复合几何体：缸体(主体) + 底部支撑脚
    命名规则: {name}_tub, {name}_leg_1-4
    """
    w, d, h = dims
    cx, cy, cz = loc

    tub_w = w * 0.95
    tub_d = d * 0.9
    tub_h = h * 0.55
    tub_z = cz - h / 2 + tub_h / 2 + h * 0.1

    leg_h = h * 0.15
    leg_s = min(w, d) * 0.06

    parts = []
    parts += _cube_block(f"{name}_tub", [cx, cy, tub_z],
                         [tub_w / 2, tub_d / 2, tub_h / 2], mat_name)

    leg_z = leg_h / 2
    leg_inset = leg_s * 2
    leg_locs = [
        [cx - tub_w / 2 + leg_inset, cy - tub_d / 2 + leg_inset, leg_z],
        [cx + tub_w / 2 - leg_inset, cy - tub_d / 2 + leg_inset, leg_z],
        [cx - tub_w / 2 + leg_inset, cy + tub_d / 2 - leg_inset, leg_z],
        [cx + tub_w / 2 - leg_inset, cy + tub_d / 2 - leg_inset, leg_z],
    ]
    for i, ll in enumerate(leg_locs):
        parts += _cube_block(f"{name}_leg_{i + 1}", ll,
                             [leg_s / 2, leg_s / 2, leg_h / 2], mat_name)
    return parts


def _sink_parts(name, dims, loc, mat_name, rotation_z=None):
    """
    水槽的复合几何体：台面(上部宽扁) + 柜体(下部)
    命名规则: {name}_counter, {name}_cabinet
    """
    w, d, h = dims
    cx, cy, cz = loc

    counter_h = h * 0.12
    cabinet_h = h * 0.8
    cabinet_z = cz - h / 2 + cabinet_h / 2
    counter_z = cz - h / 2 + cabinet_h + counter_h / 2

    parts = []
    parts += _cube_block(f"{name}_cabinet", [cx, cy, cabinet_z],
                         [w / 2 * 0.9, d / 2 * 0.9, cabinet_h / 2], mat_name)
    parts += _cube_block(f"{name}_counter", [cx, cy, counter_z],
                         [w / 2, d / 2, counter_h / 2], mat_name)
    return parts


# 物体类型到生成函数的映射（key 必须与 object_types.py 中的 builder 字段一致）
BUILDER_FUNCTIONS = {
    "table": _table_parts,
    "chair": _chair_parts,
    "sofa": _sofa_parts,
    "bed": _bed_parts,
    "bookshelf": _bookshelf_parts,
    "toilet": _toilet_parts,
    "bathtub": _bathtub_parts,
    "sink": _sink_parts,
}


def generate_bpy_code(spec):
    """
    从结构化规格生成带复合几何体的 bpy 代码。
    """
    lines = [
        "import bpy",
        "",
        "# Clear scene",
        "bpy.ops.object.select_all(action='SELECT')",
        "bpy.ops.object.delete(use_global=False)",
        "",
    ]

    # 收集所有材质
    materials = {}
    for obj in spec.get("objects", []):
        mat = obj.get("material_name", "Material")
        col = tuple(obj.get("color", [0.5, 0.5, 0.5]))
        if (mat, col) not in materials:
            materials[(mat, col)] = (mat, list(col))

    # 生成材质
    if materials:
        lines.append("# Materials")
        for (mat_name, color) in materials.values():
            lines += _create_material(mat_name, color)
        lines.append("")

    # 生成物体（根据几何类型分发）
    lines.append("# Objects")
    for obj in spec.get("objects", []):
        name = obj["name"]
        dims = obj["dimensions"]
        loc = obj["location"]
        mat_name = obj.get("material_name", "Material")
        obj_type = obj.get("type", "object")
        rot_z = obj.get("rotation_z", None)

        lines.append(f"# === {name}: {dims[0]}x{dims[1]}x{dims[2]}m at ({loc[0]:.3f}, {loc[1]:.3f}, {loc[2]:.3f}) ===")

        geom = get_geometry(obj_type)
        builder_key = get_builder(obj_type)

        if geom == 'composite' and builder_key and builder_key in BUILDER_FUNCTIONS:
            builder = BUILDER_FUNCTIONS[builder_key]
            lines += _join_parts_start()
            lines += builder(name, dims, loc, mat_name, rot_z)
            lines += _join_parts_end(name)
        elif geom == 'sphere':
            radius = max(dims) / 2
            sphere_z = radius
            lines += _sphere_block(name, [loc[0], loc[1], sphere_z], radius, mat_name, rot_z)
        elif geom == 'cylinder':
            radius = max(dims[0], dims[1]) / 2
            height = dims[2]
            cyl_z = height / 2
            lines += _cylinder_block(name, [loc[0], loc[1], cyl_z], radius, height, mat_name, rot_z)
        else:
            sx, sy, sz = dims[0] / 2, dims[1] / 2, dims[2] / 2
            lines += _cube_block(name, loc, [sx, sy, sz], mat_name, rot_z)

    # ====== 相机与灯光设置 ======
    lines.append("# --- Setup Camera and Lighting ---")
    # 1. 设置渲染引擎
    lines.append("for _eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES'):")
    lines.append("    try:")
    lines.append("        bpy.context.scene.render.engine = _eng")
    lines.append("        break")
    lines.append("    except (ValueError, TypeError):")
    lines.append("        continue")

    # 2. 添加柔和的太阳光
    lines.append("bpy.ops.object.light_add(type='SUN', location=(5, -5, 8))")
    lines.append("bpy.context.active_object.data.energy = 3.0")
    lines.append("bpy.context.active_object.rotation_euler = (0.78, 0, 0.78)  # 倾斜45度照射")

    # 3. 添加入口相机（放在右前方的斜上角）
    lines.append("bpy.ops.object.camera_add(location=(5.0, -6.0, 4.0))")
    lines.append("cam = bpy.context.active_object")
    lines.append("cam.rotation_euler = (1.1, 0, 0.6)  # 大约对准中心")
    lines.append("bpy.context.scene.camera = cam")
    # ============================
    
    return "\n".join(lines)


def extract_spec_from_text(text):
    """从 LLM 输出中提取结构化规格（保留兼容性）"""
    # JSON block
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            spec = json.loads(json_match.group(1))
            if "objects" in spec:
                return spec
        except json.JSONDecodeError:
            pass

    try:
        spec = json.loads(text)
        if "objects" in spec:
            return spec
    except json.JSONDecodeError:
        pass

    # 结构化文本回退
    objects = []
    for match in re.finditer(
        r"(\w+)\s*(?:dimensions|size)\s*[=:(]\s*\(?([\d.]+)\s*[,x]\s*([\d.]+)\s*[,x]\s*([\d.]+)\)?\s*[,.]\s*(?:location|at)\s*[=:(]\s*\(?(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\)?",
        text
    ):
        name = match.group(1)
        if name.lower() not in ('the', 'a', 'an', 'type', 'reason', 'plan', 'check'):
            objects.append({
                "name": name,
                "dimensions": [float(match.group(2)), float(match.group(3)), float(match.group(4))],
                "location": [float(match.group(5)), float(match.group(6)), float(match.group(7))],
                "color": [0.5, 0.5, 0.5],
                "material_name": "Material",
                "type": name.lower(),
            })

    if objects:
        return {"objects": objects}

    # 用户请求回退
    user_objects = []
    for match in re.finditer(
        r"([A-Z][a-zA-Z]+)\s*(?::|,)?\s*(?:Type:?\s*\w+\s*(?:with|,)\s*)?(?:dimensions|scale|size)\s*[=:(]\s*\(?([\d.]+)\s*[,x]\s*([\d.]+)\s*[,x]\s*([\d.]+)\)?"
        r".*?(?:Location|location|at)\s*[=:(]\s*\(?(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\)?"
        r".*?(?:color|RGB)\s*[=:(]\s*\(?([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\)?",
        text, re.DOTALL
    ):
        name = match.group(1)
        if name.lower() not in ('type', 'material', 'object', 'the', 'create', 'use', 'ensure', 'important'):
            dims = [float(match.group(2)), float(match.group(3)), float(match.group(4))]
            loc = [float(match.group(5)), float(match.group(6)), float(match.group(7))]
            try:
                color = [float(match.group(8)), float(match.group(9)), float(match.group(10))]
            except (IndexError, TypeError):
                color = [0.5, 0.5, 0.5]
            user_objects.append({
                "name": name, "dimensions": dims, "location": loc,
                "color": color, "material_name": name + "_mat", "type": name.lower(),
            })

    if user_objects:
        return {"objects": user_objects}
    return None


def generate_from_llm_output(llm_text):
    spec = extract_spec_from_text(llm_text)
    if spec and spec.get("objects"):
        code = generate_bpy_code(spec)
        return code, spec
    return None, None

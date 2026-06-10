import os
import subprocess
import colorama
from colorama import Fore
from object_types import PLATFORM_TYPES, SATELLITE_TYPES

colorama.init(autoreset=True)

# 增强版物理检测脚本：纯 Python 实现（无 mathutils 依赖）
# 支持复合物体归组检测（桌子=桌面+4腿 归为一组）
PHYSICS_VERIFIER_CODE = """
import bpy
import math

def mat_mul_vec(matrix, vec):
    '''4x4 matrix @ (x,y,z,1) -> (wx,wy,wz) — 纯 Python，替代 mathutils.Vector'''
    x, y, z = vec[0], vec[1], vec[2]
    wx = matrix[0][0]*x + matrix[0][1]*y + matrix[0][2]*z + matrix[0][3]
    wy = matrix[1][0]*x + matrix[1][1]*y + matrix[1][2]*z + matrix[1][3]
    wz = matrix[2][0]*x + matrix[2][1]*y + matrix[2][2]*z + matrix[2][3]
    return (wx, wy, wz)

def get_world_aabb(obj):
    '''计算物体在世界坐标系下的 AABB，纯 Python'''
    mw = obj.matrix_world
    corners = [mat_mul_vec(mw, c) for c in obj.bound_box]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    zs = [c[2] for c in corners]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

def get_center_from_aabb(aabb):
    return ((aabb[0]+aabb[1])/2, (aabb[2]+aabb[3])/2, (aabb[4]+aabb[5])/2)

def get_size_from_aabb(aabb):
    return (aabb[1]-aabb[0], aabb[3]-aabb[2], aabb[5]-aabb[4])

def combined_aabb(aabbs):
    '''合并多个 AABB 为一个总的 '''
    if not aabbs:
        return (0,0,0,0,0,0)
    return (
        min(a[0] for a in aabbs), max(a[1] for a in aabbs),
        min(a[2] for a in aabbs), max(a[3] for a in aabbs),
        min(a[4] for a in aabbs), max(a[5] for a in aabbs),
    )

def group_meshes(meshes):
    '''将网格按逻辑物体归组。命名规则: {ObjectName}_{partName}[_{N}] -> 归为 ObjectName'''
    BODY_PARTS = ['leg', 'top', 'seat', 'backrest', 'tabletop', 'mattress', 'headboard', 'armrest', 'shelf', 'side', 'back', 'cushion', 'tank', 'bowl', 'tub', 'counter', 'cabinet']
    groups = {}
    ungrouped = []

    for obj in meshes:
        name = obj.name
        base = None
        for part in BODY_PARTS:
            idx = name.find('_' + part)
            if idx != -1:
                base = name[:idx]
                break

        if base:
            if base not in groups:
                groups[base] = []
            groups[base].append(obj)
        else:
            ungrouped.append(obj)

    # 转换为 (group_name, combined_aabb, list_of_objects)
    result = []
    for base_name, objs in groups.items():
        aabbs = [get_world_aabb(o) for o in objs]
        result.append((base_name, combined_aabb(aabbs), objs))
    for obj in ungrouped:
        result.append((obj.name, get_world_aabb(obj), [obj]))

    return result


def check_physics():
    print("\\n===PHYSICS_CHECK_START===")
    bpy.context.view_layer.update()

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        print("PHYSICS_OK")
        print("===PHYSICS_CHECK_END===\\n")
        bpy.ops.wm.save_as_mainfile(filepath="outputs/final_scene.blend")
        return

    errors = []
    warnings = []
    tol = 0.03

    # 按逻辑物体归组
    groups = group_meshes(meshes)

    # 识别平台和附属物体
    platform_keywords = ['table', 'desk', 'sofa', 'couch', 'bed', 'bookshelf', 'cabinet', 'rug', 'counter', 'dresser']
    satellite_keywords = ['chair', 'seat', 'stool', 'armchair', 'bench', 'ottoman', 'nightstand', 'lamp', 'plant', 'vase']
    plat_groups = [g for g in groups if any(kw in g[0].lower() for kw in platform_keywords)]
    sat_groups = [g for g in groups if any(kw in g[0].lower() for kw in satellite_keywords)]

    # 1. 穿模检测（组级别）
    for i in range(len(groups)):
        for j in range(i+1, len(groups)):
            g_name_a, aabb_a, objs_a = groups[i]
            g_name_b, aabb_b, objs_b = groups[j]

            # 同一组的部件跳过
            if g_name_a == g_name_b:
                continue

            overlap_x = min(aabb_a[1], aabb_b[1]) - max(aabb_a[0], aabb_b[0])
            overlap_y = min(aabb_a[3], aabb_b[3]) - max(aabb_a[2], aabb_b[2])
            overlap_z = min(aabb_a[5], aabb_b[5]) - max(aabb_a[4], aabb_b[4])

            if overlap_x > tol and overlap_y > tol and overlap_z > tol:
                min_overlap = min(overlap_x, overlap_y, overlap_z)
                sep_axis = ["X", "Y", "Z"][[overlap_x, overlap_y, overlap_z].index(min_overlap)]

                ca = get_center_from_aabb(aabb_a)
                cb = get_center_from_aabb(aabb_b)
                sa = get_size_from_aabb(aabb_a)
                sb = get_size_from_aabb(aabb_b)

                sep_dist = min_overlap + 0.05
                if ca[["X","Y","Z"].index(sep_axis)] < cb[["X","Y","Z"].index(sep_axis)]:
                    direction = f"Move '{g_name_a}' -{sep_axis} by {sep_dist:.3f}m, or '{g_name_b}' +{sep_axis} by {sep_dist:.3f}m"
                else:
                    direction = f"Move '{g_name_a}' +{sep_axis} by {sep_dist:.3f}m, or '{g_name_b}' -{sep_axis} by {sep_dist:.3f}m"

                errors.append(
                    f"INTERSECTION: '{g_name_a}'[center=({ca[0]:.3f},{ca[1]:.3f},{ca[2]:.3f}) "
                    f"size=({sa[0]:.3f},{sa[1]:.3f},{sa[2]:.3f})] "
                    f"OVERLAPS '{g_name_b}'[center=({cb[0]:.3f},{cb[1]:.3f},{cb[2]:.3f}) "
                    f"size=({sb[0]:.3f},{sb[1]:.3f},{sb[2]:.3f})] "
                    f"| Overlap: X={overlap_x:.3f}m Y={overlap_y:.3f}m Z={overlap_z:.3f}m "
                    f"| Separation: {sep_axis} axis | {direction}"
                )

    # 2. 地面检测（组级别）
    for g_name, aabb, objs in groups:
        min_z = aabb[4]
        center = get_center_from_aabb(aabb)
        size = get_size_from_aabb(aabb)

        if min_z < -tol:
            required_z = center[2] + abs(min_z)
            errors.append(
                f"UNDERGROUND: '{g_name}' bottom at Z={min_z:.3f}m (below ground). "
                f"Center Z={center[2]:.3f}m, height={size[2]:.3f}m. "
                f"FIX: set '{g_name}'.location.z = {required_z:.3f}"
            )
        elif min_z > 0.15:
            warnings.append(
                f"FLOATING: '{g_name}' bottom at Z={min_z:.3f}m (above ground). "
                f"Center Z={center[2]:.3f}m, height={size[2]:.3f}m. "
                f"FIX: set '{g_name}'.location.z = {size[2]/2:.3f}"
            )

    # 3. 空间关系检测（附属 vs 平台）
    if plat_groups and sat_groups:
        for sat_name, sat_aabb, sat_objs in sat_groups:
            s_center = get_center_from_aabb(sat_aabb)
            s_size = get_size_from_aabb(sat_aabb)

            min_dist = float('inf')
            nearest_plat = None
            for plat_name, plat_aabb, plat_objs in plat_groups:
                p_center = get_center_from_aabb(plat_aabb)
                dist = math.sqrt((s_center[0]-p_center[0])**2 + (s_center[1]-p_center[1])**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_plat = (plat_name, plat_aabb)

            if nearest_plat:
                p_name, p_aabb = nearest_plat
                p_size = get_size_from_aabb(p_aabb)
                p_half_y = p_size[1] / 2
                s_half_y = s_size[1] / 2
                min_ok = p_half_y + s_half_y + 0.15
                max_ok = p_half_y + s_half_y + 3.0

                if min_dist < min_ok:
                    errors.append(
                        f"TOO_CLOSE: '{sat_name}' too close to '{p_name}'. "
                        f"Distance={min_dist:.3f}m, min={min_ok:.3f}m. "
                        f"Move away by {(min_ok - min_dist + 0.1):.3f}m"
                    )
                elif min_dist > max_ok:
                    warnings.append(
                        f"TOO_FAR: '{sat_name}' far from '{p_name}'. "
                        f"Distance={min_dist:.3f}m, max={max_ok:.3f}m."
                    )

    # 4. 输出
    if not errors and not warnings:
        print("PHYSICS_OK")
    else:
        for err in errors:
            print("PHYSICS_ERROR:", err)
        for warn in warnings:
            print("PHYSICS_WARNING:", warn)
    print("===PHYSICS_CHECK_END===\\n")

    bpy.ops.wm.save_as_mainfile(filepath="outputs/final_scene.blend")

    # 若验证没有报错，渲染一张 PNG 图片（渲染是可选功能，失败不影响物理验证通过）
    if not errors and not warnings:
        try:
            bpy.context.scene.render.filepath = "//render_preview.png"
            bpy.context.scene.render.resolution_x = 1920
            bpy.context.scene.render.resolution_y = 1080
            bpy.ops.render.render(write_still=True)
        except Exception:
            pass  
    
check_physics()
"""


def execute_and_verify(bpy_code):
    """在后台运行 Blender 并执行代码，返回物理检测结果"""
    os.makedirs("outputs", exist_ok=True)
    script_path = "outputs/temp_execution.py"

    full_code = bpy_code + "\n" + PHYSICS_VERIFIER_CODE

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(full_code)

    print(Fore.YELLOW + "[Environment] Starting Blender background verification...")

    try:
        blender_path = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
        result = subprocess.run(
            [blender_path, "-b", "--python", script_path],
            capture_output=True, text=True, encoding='utf-8'
        )
    except FileNotFoundError:
        return False, "Error: Blender not found."

    output = result.stdout + "\n" + result.stderr

    if any(kw in output for kw in ["Traceback", "SyntaxError", "TypeError", "ValueError", "AttributeError"]):
        return False, f"Code Error:\n{output[-1200:]}"

    if "===PHYSICS_CHECK_START===" in output:
        check = output.split("===PHYSICS_CHECK_START===")[1].split("===PHYSICS_CHECK_END===")[0]
        if "PHYSICS_OK" in check:
            return True, "Success! No physics errors."
        else:
            errs = [l.replace("PHYSICS_ERROR: ", "") for l in check.split('\n') if "PHYSICS_ERROR:" in l]
            wrns = [l.replace("PHYSICS_WARNING: ", "") for l in check.split('\n') if "PHYSICS_WARNING:" in l]
            fb = ""
            if errs:
                fb += "=== ERRORS ===\n" + "\n".join(f"- {e}" for e in errs)
            if wrns:
                fb += "\n\n=== WARNINGS ===\n" + "\n".join(f"- {w}" for w in wrns)
            return False, fb

    return False, f"Unknown Error. Blender output:\n{output[-1200:]}"

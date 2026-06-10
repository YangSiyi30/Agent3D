import colorama
from colorama import Fore
from blender_env import execute_and_verify
from agents import run_fixer

colorama.init(autoreset=True)

# 故意写一段穿模的代码，完美还原大模型的幻觉错误
BAD_CODE = """
import bpy

# 1. 彻底清空默认场景（删掉那个碍事的默认 Cube！）
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 2. 材质设置（加入 diffuse_color 让你在灰模下也能看到颜色）
mat_wood = bpy.data.materials.new(name='Wood')
mat_wood.use_nodes = True
mat_wood.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.6, 0.3, 0.1, 1.0)
mat_wood.diffuse_color = (0.6, 0.3, 0.1, 1.0) # 木头色

mat_metal = bpy.data.materials.new(name='Metal')
mat_metal.use_nodes = True
mat_metal.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.2, 0.4, 0.8, 1.0)
mat_metal.diffuse_color = (0.2, 0.4, 0.8, 1.0) # 蓝色椅子，对比更明显

# 3. 创建桌子
bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.375))
obj = bpy.context.active_object
obj.name = 'TableTop'
obj.scale = (0.6, 0.4, 0.375)
obj.data.materials.append(mat_wood)

# 4. 创建椅子（故意放在 X=0.4，让它有一半狠狠地卡在桌子内部，穿模效果拉满！）
bpy.ops.mesh.primitive_cube_add(location=(0.4, 0.0, 0.45))
obj = bpy.context.active_object
obj.name = 'ChairA'
obj.scale = (0.2, 0.2, 0.45)
obj.data.materials.append(mat_metal)
"""

def main():
    print(Fore.YELLOW + "1. 正在运行穿模的初始场景...")
    success, feedback_msg = execute_and_verify(BAD_CODE)
    
    import os
    import shutil
    if os.path.exists("outputs/final_scene.blend"):
        shutil.copy("outputs/final_scene.blend", "outputs/bad_scene.blend")
        print(Fore.RED + "=> 错误场景已保存为 outputs/bad_scene.blend")
        
    print(Fore.RED + f"\n[环境报错信息]:\n{feedback_msg}\n")
    
    print(Fore.CYAN + "2. 调用 Fixer Agent 进行修复...")
    # 传入报错信息，让 Fixer 修复
    fixed_code = run_fixer(BAD_CODE, feedback_msg, user_request="a table and a chair")
    
    print(Fore.YELLOW + "3. 正在验证修复后的场景...")
    success_fix, feedback_msg_fix = execute_and_verify(fixed_code)
    
    if success_fix:
        if os.path.exists("outputs/final_scene.blend"):
            shutil.copy("outputs/final_scene.blend", "outputs/good_scene.blend")
        print(Fore.GREEN + "=> 修复成功！修复后的场景已保存为 outputs/good_scene.blend")

if __name__ == "__main__":
    main()
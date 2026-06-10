"""
Agent3D: 基于多智能体协作与几何物理反馈的 Blender 程序化场景生成系统

=== 支持的物体类型 ===

平台型 (platform) - 其他物体可围绕其排列:
  table/桌子, sofa/沙发, bed/床, bookshelf/书架, cabinet/柜子, counter/台面, dresser/抽屉柜, rug/地毯

附属型 (satellite) - 围绕平台排列:
  chair/椅子, stool/凳子, armchair/扶手椅, bench/长凳, ottoman/脚凳,
  nightstand/床头柜, lamp/灯, plant/植物, vase/花瓶

独立型 (standalone) - 独立放置:
  家电: tv/电视, fridge/冰箱, oven/烤箱, washer/洗衣机, microwave/微波炉
  卫浴: toilet/马桶, bathtub/浴缸, sink/水槽
  装饰: mirror/镜子, clock/钟, picture/画, trash_can/垃圾桶, cushion/靠垫
  几何体: ball/球(sphere), bottle/瓶子(cylinder), bowl/碗, cup/杯子, box/盒子, book/书

=== 几何类型 ===
  composite : 多部件组合 (table=桌面+4腿, chair=座面+靠背+4腿, sofa/沙发, bed/床, bookshelf/书架)
  cuboid    : 简单立方体 (cabinet, tv, box, book...)
  cylinder  : 圆柱体 (bottle, cup, lamp, vase, trash_can...)
  sphere    : 球体 (ball)

=== 示例场景 ===
  1. 餐厅: "a table 1.2m wide 0.8m deep 0.75m tall with four chairs 0.4m wide 0.4m deep 0.9m tall"
  2. 客厅: "a sofa 2m wide 0.85m deep 0.85m tall with a coffee table and two armchairs"
  3. 卧室: "a bed 2m wide 1.6m deep 0.6m tall with two nightstands"
  4. 多椅: "a table 2.4m wide 1.6m deep 0.75m tall with five chairs. Place two chairs in front and three behind."
  5. 几何体: "a ball 0.3m in diameter and a box 0.5m wide 0.4m deep 0.3m tall"
  6. 中文: "一张桌子宽1.2米深0.8米高0.75米 四把椅子 两把在前面 两把在后面"
  7. 无尺寸: "a table with four chairs and a lamp"
  8. 卫浴: "a toilet and a bathtub and a sink"

=== 已知限制 ===
  - 每面能放置的椅子数量受桌面宽度限制 (宽1.2m最多2把/面, 宽2.4m最多4把/面)
  - 中文长文本(>3字)的物体名称可能无法正确识别
  - "long" 不是有效维度关键词, 请用 "deep" 或 "深"
  - 同一类型的多个平台 (如 "两个桌子") 暂不支持

详细文档见 USAGE.md
"""

import colorama
from colorama import Fore, Style
from agents import run_planner, run_coder, run_fixer
from blender_env import execute_and_verify
from spatial_planner import generate_spec_from_request
from deterministic_fixer import validate_spec
from code_generator import generate_bpy_code

colorama.init(autoreset=True)


def main():
    print(Fore.GREEN + "=" * 50)
    print(Fore.GREEN + " Agent3D: Multi-Agent 3D Scene Generation System")
    print(Fore.GREEN + "=" * 50)

    # 修改下面的 user_request 来测试不同场景
    # 示例场景见本文件头部注释或 USAGE.md
    user_request = (
        "a sofa with two chairs in front facing the sofa."
    )
    # 更多测试场景:
    # 1) 混合朝向 (含 typo): "a sofa with two chairs, one chair in front faing away, one chair behind facing the sofa"
    # 2) 混合朝向 (中文): "一张沙发配两把椅子 前面一把背对着沙发 后面一把正对着沙发"
    # 3) 同向: "a sofa with two chairs in front facing the sofa"
    # 4) 同向背离: "a sofa with two chairs behind facing away"
    # 5) 四面分布混合朝向: "a table 2.0m wide 1.2m deep with four chairs. one in front facing away, one behind facing away, one on the left facing the table, one on the right facing the table"
    # 6) 原复杂场景 (含卫浴+typo): "a toilet and a bathtub and a sink and a sofa 2.5m wide 1.8m deep 1m tall and a table and two chairs, one chair in the front of the sofa and faing away the sofa, one chair behind the sofa facing the sofa"
    print(Fore.YELLOW + f"User Prompt: '{user_request}'\n")

    # 使用 LLM Planner + Coder
    print(Fore.CYAN + "[System] 启动大模型 Planner Agent 进行场景解析与规划...")
    plan = run_planner(user_request)

    # 生成 JSON 规范并转为代码（LLM 主导场景理解，确定性逻辑保底坐标计算）
    current_code = run_coder(plan, user_request)

    # 迭代验证和修正
    MAX_ITERATIONS = 6

    for i in range(MAX_ITERATIONS):
        print(Fore.CYAN + f"\n--- [Iteration {i + 1}/{MAX_ITERATIONS}] ---")

        success, feedback_msg = execute_and_verify(current_code)

        if success:
            print(Fore.GREEN + "\n[Success] Physics verification passed!")
            print(Fore.GREEN + "Final scene saved to outputs/final_scene.blend")
            break
        else:
            print(Fore.RED + f"[Failed] Physics issues detected:\n{feedback_msg}")
            if i < MAX_ITERATIONS - 1:
                # 大模型分析错误，确定性逻辑重新计算全局布局
                current_code = run_fixer(current_code, feedback_msg, user_request)
            else:
                print(Fore.RED + "\n[Terminated] Max iterations reached.")


if __name__ == "__main__":
    main()

"""
物理验证模块 — 重新导出 blender_env 中的验证功能。
实际的物理检测代码位于 blender_env.py (PHYSICS_VERIFIER_CODE)。
"""
from blender_env import execute_and_verify

__all__ = ["execute_and_verify"]

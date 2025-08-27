#!/usr/bin/env python3
"""
截图路径调试脚本
用于实时调试截图路径问题
"""

import os
from pathlib import Path

def debug_screenshot_paths(task_id: str):
    """调试截图路径"""
    print(f"调试任务 {task_id} 的截图路径...")
    
    # 检查可能的截图目录
    possible_dirs = [
        Path("screenshots") / task_id,
        Path("app/screenshots") / task_id,
        Path("./screenshots") / task_id,
        Path(os.getcwd()) / "screenshots" / task_id
    ]
    
    for i, dir_path in enumerate(possible_dirs, 1):
        print(f"{i}. 检查目录: {dir_path}")
        print(f"   绝对路径: {dir_path.resolve()}")
        print(f"   存在: {dir_path.exists()}")
        
        if dir_path.exists():
            files = list(dir_path.glob("*.png"))
            print(f"   PNG文件: {len(files)}")
            for file in files[:3]:  # 显示前3个文件
                print(f"      - {file.name} ({file.stat().st_size} bytes)")
        print()

if __name__ == "__main__":
    # 使用实际的任务ID
    debug_screenshot_paths("f4e0ea3d-d2a6-4af0-85e1-6b2af552a0bb")

#!/usr/bin/env python3
"""
截图去重脚本

解决每个域名有多个重复截图的问题，每个域名只保留一个最新的截图文件。
"""

import os
from pathlib import Path
from datetime import datetime
import shutil


def deduplicate_screenshots(task_id: str):
    """为指定任务去重截图文件"""
    print(f"🔄 开始为任务 {task_id} 去重截图文件")
    
    screenshot_dir = Path("storage/screenshots") / task_id
    
    if not screenshot_dir.exists():
        print(f"❌ 截图目录不存在: {screenshot_dir}")
        return
    
    # 收集所有截图文件
    files = list(screenshot_dir.glob("*.png"))
    print(f"📊 找到 {len(files)} 个截图文件")
    
    if not files:
        print("❌ 没有找到任何截图文件")
        return
    
    # 按域名分组
    domain_groups = {}
    for file in files:
        # 从文件名提取域名（去除时间戳）
        name_parts = file.stem.split("_")
        if len(name_parts) >= 2:
            # 处理包含 _error 后缀的情况
            if name_parts[-1] == "error":
                domain = "_".join(name_parts[:-2])  # 去除时间戳和error
                timestamp = name_parts[-2]
                file_type = "error"
            else:
                domain = "_".join(name_parts[:-1])  # 去除时间戳
                timestamp = name_parts[-1]
                file_type = "normal"
            
            if domain not in domain_groups:
                domain_groups[domain] = []
            domain_groups[domain].append({
                'file': file,
                'timestamp': timestamp,
                'type': file_type,
                'size': file.stat().st_size,
                'mtime': file.stat().st_mtime
            })
    
    print(f"📈 发现 {len(domain_groups)} 个不同的域名")
    
    # 每个域名只保留最新的截图
    kept_files = []
    removed_files = []
    
    for domain, files_list in domain_groups.items():
        print(f"\n🔍 处理域名: {domain}")
        print(f"   找到 {len(files_list)} 个文件")
        
        if len(files_list) > 1:
            print("   🔄 存在重复截图，开始去重...")
            
            # 优先保留正常文件（非error），然后按修改时间排序
            normal_files = [f for f in files_list if f['type'] == 'normal']
            error_files = [f for f in files_list if f['type'] == 'error']
            
            # 选择要保留的文件
            if normal_files:
                # 如果有正常文件，选择最新的正常文件
                normal_files.sort(key=lambda f: f['mtime'], reverse=True)
                keep_file = normal_files[0]
                remove_files = normal_files[1:] + error_files
            else:
                # 如果只有错误文件，选择最新的错误文件
                error_files.sort(key=lambda f: f['mtime'], reverse=True)
                keep_file = error_files[0]
                remove_files = error_files[1:]
            
            kept_files.append(keep_file)
            
            # 删除多余的文件
            for remove_file in remove_files:
                print(f"   ❌ 删除重复截图: {remove_file['file'].name}")
                try:
                    remove_file['file'].unlink()
                    removed_files.append(remove_file)
                except Exception as e:
                    print(f"   ⚠️  删除文件失败: {e}")
            
            print(f"   ✅ 保留文件: {keep_file['file'].name} ({keep_file['size']} 字节)")
        else:
            kept_files.append(files_list[0])
            print(f"   ✅ 无重复，保留: {files_list[0]['file'].name}")
    
    print(f"\n🎉 去重完成!")
    print(f"   📊 保留文件: {len(kept_files)} 个")
    print(f"   🗑️  删除文件: {len(removed_files)} 个")
    print(f"   💾 节省空间: {sum(f['size'] for f in removed_files) / 1024 / 1024:.2f} MB")
    
    # 显示保留的文件列表
    print(f"\n📋 保留的文件列表:")
    for item in kept_files:
        print(f"   ✅ {item['file'].name} ({item['size']} 字节)")
    
    return len(kept_files), len(removed_files)


def main():
    """主函数"""
    print("🚀 截图去重工具")
    print("=" * 50)
    
    # 使用最新任务ID
    task_id = "f4e0ea3d-d2a6-4af0-85e1-6b2af552a0bb"
    
    print(f"🎯 目标任务ID: {task_id}")
    
    # 执行去重
    try:
        kept_count, removed_count = deduplicate_screenshots(task_id)
        
        print("\n" + "=" * 50)
        print("✅ 去重操作完成!")
        print(f"📊 统计结果:")
        print(f"   - 保留文件: {kept_count} 个")
        print(f"   - 删除文件: {removed_count} 个")
        
        if removed_count > 0:
            print(f"\n💡 建议:")
            print(f"   - 重复截图问题已解决")
            print(f"   - 每个域名现在只有一个截图文件")
            print(f"   - 可以重新运行AI分析任务")
        else:
            print(f"\n💭 注意:")
            print(f"   - 没有发现重复截图")
            print(f"   - 所有文件都已是最优状态")
    
    except Exception as e:
        print(f"❌ 去重操作失败: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
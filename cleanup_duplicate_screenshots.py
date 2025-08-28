#!/usr/bin/env python3
"""
清理重复截图脚本
用于清理现有任务中的重复截图文件，每个域名只保留一张最新的截图
"""

import os
import sys
import time
import shutil
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

def analyze_screenshot_directory(screenshot_dir: Path) -> Dict[str, List[Path]]:
    """分析截图目录，按域名分组"""
    domain_files = defaultdict(list)
    
    if not screenshot_dir.exists():
        print(f"截图目录不存在: {screenshot_dir}")
        return domain_files
    
    print(f"分析截图目录: {screenshot_dir}")
    
    # 遍历所有PNG文件
    for png_file in screenshot_dir.glob("*.png"):
        # 提取域名（去掉时间戳和后缀）
        filename = png_file.stem
        
        # 处理不同的文件名格式
        # 格式1: domain_timestamp.png
        # 格式2: domain_timestamp_error.png
        if '_error' in filename:
            # 错误截图，提取域名
            domain = filename.replace('_error', '').rsplit('_', 1)[0]
            domain = domain.replace('_', '.')
        else:
            # 正常截图，提取域名
            parts = filename.split('_')
            if len(parts) >= 2 and parts[-1].isdigit():
                # 有时间戳
                domain = '_'.join(parts[:-1]).replace('_', '.')
            else:
                # 没有时间戳
                domain = filename.replace('_', '.')
        
        domain_files[domain].append(png_file)
    
    return domain_files

def get_file_info(file_path: Path) -> Tuple[int, int]:
    """获取文件信息：修改时间和文件大小"""
    stat = file_path.stat()
    return int(stat.st_mtime), stat.st_size

def select_best_screenshot(files: List[Path]) -> Path:
    """选择最佳的截图文件（最新且非错误文件）"""
    
    # 分离错误文件和正常文件
    normal_files = [f for f in files if '_error' not in f.name]
    error_files = [f for f in files if '_error' in f.name]
    
    # 优先选择正常文件
    if normal_files:
        # 选择最新的正常文件
        return max(normal_files, key=lambda f: get_file_info(f)[0])
    elif error_files:
        # 如果只有错误文件，选择最新的错误文件
        return max(error_files, key=lambda f: get_file_info(f)[0])
    else:
        # 理论上不会到这里
        return files[0]

def cleanup_duplicate_screenshots(task_id: str, dry_run: bool = True) -> Dict[str, any]:
    """清理指定任务的重复截图"""
    
    screenshot_dir = Path("storage/screenshots") / task_id
    
    if not screenshot_dir.exists():
        print(f"任务 {task_id} 的截图目录不存在")
        return {"error": "screenshot directory not found"}
    
    # 分析文件
    domain_files = analyze_screenshot_directory(screenshot_dir)
    
    total_files = sum(len(files) for files in domain_files.values())
    duplicate_count = 0
    kept_count = 0
    removed_files = []
    kept_files = []
    total_size_removed = 0
    
    print(f"\n=== 清理任务 {task_id} 的重复截图 ===")
    print(f"总域名数: {len(domain_files)}")
    print(f"总文件数: {total_files}")
    print(f"执行模式: {'试运行' if dry_run else '实际删除'}")
    
    for domain, files in domain_files.items():
        if len(files) <= 1:
            # 没有重复文件
            kept_count += len(files)
            kept_files.extend([str(f) for f in files])
            continue
        
        # 有重复文件，选择最佳的一个
        best_file = select_best_screenshot(files)
        files_to_remove = [f for f in files if f != best_file]
        
        print(f"\n域名: {domain}")
        print(f"  总文件: {len(files)}")
        print(f"  保留: {best_file.name} ({get_file_info(best_file)[1]} bytes)")
        
        kept_count += 1
        kept_files.append(str(best_file))
        
        for file_to_remove in files_to_remove:
            file_size = get_file_info(file_to_remove)[1]
            total_size_removed += file_size
            duplicate_count += 1
            removed_files.append(str(file_to_remove))
            
            print(f"  删除: {file_to_remove.name} ({file_size} bytes)")
            
            if not dry_run:
                try:
                    file_to_remove.unlink()
                    print(f"    ✓ 已删除")
                except Exception as e:
                    print(f"    ✗ 删除失败: {e}")
    
    # 统计结果
    result = {
        "task_id": task_id,
        "total_domains": len(domain_files),
        "total_files_before": total_files,
        "files_kept": kept_count,
        "files_removed": duplicate_count,
        "size_saved_mb": round(total_size_removed / 1024 / 1024, 2),
        "dry_run": dry_run,
        "removed_files": removed_files,
        "kept_files": kept_files
    }
    
    print(f"\n=== 清理结果 ===")
    print(f"保留文件: {kept_count}")
    print(f"删除文件: {duplicate_count}")
    print(f"节省空间: {result['size_saved_mb']} MB")
    
    return result

def cleanup_all_tasks(dry_run: bool = True) -> List[Dict[str, any]]:
    """清理所有任务的重复截图"""
    
    storage_dir = Path("storage/screenshots")
    
    if not storage_dir.exists():
        print("截图存储目录不存在")
        return []
    
    # 查找所有任务目录
    task_dirs = [d for d in storage_dir.iterdir() if d.is_dir()]
    
    print(f"找到 {len(task_dirs)} 个任务目录")
    
    results = []
    for task_dir in task_dirs:
        task_id = task_dir.name
        try:
            result = cleanup_duplicate_screenshots(task_id, dry_run)
            results.append(result)
        except Exception as e:
            print(f"清理任务 {task_id} 失败: {e}")
            results.append({
                "task_id": task_id,
                "error": str(e)
            })
    
    return results

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="清理重复截图脚本")
    parser.add_argument("--task-id", help="指定要清理的任务ID")
    parser.add_argument("--all", action="store_true", help="清理所有任务")
    parser.add_argument("--execute", action="store_true", help="实际执行删除（默认为试运行）")
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if args.task_id:
        # 清理指定任务
        result = cleanup_duplicate_screenshots(args.task_id, dry_run)
        if not result.get("error"):
            print("\n任务完成！")
            if dry_run:
                print("这是试运行，如需实际删除文件，请添加 --execute 参数")
    elif args.all:
        # 清理所有任务
        results = cleanup_all_tasks(dry_run)
        
        # 汇总统计
        total_saved_mb = sum(r.get("size_saved_mb", 0) for r in results if not r.get("error"))
        total_removed = sum(r.get("files_removed", 0) for r in results if not r.get("error"))
        
        print(f"\n=== 总体统计 ===")
        print(f"处理任务数: {len(results)}")
        print(f"总删除文件: {total_removed}")
        print(f"总节省空间: {total_saved_mb} MB")
        
        if dry_run:
            print("\n这是试运行，如需实际删除文件，请添加 --execute 参数")
    else:
        print("请指定 --task-id <任务ID> 或 --all")
        parser.print_help()

if __name__ == "__main__":
    main()

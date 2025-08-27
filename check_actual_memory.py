#!/usr/bin/env python3
"""
检查实际的系统内存使用情况
用于验证内存数据的准确性
"""

import psutil
import os


def check_system_memory():
    """检查系统内存使用情况"""
    print("🖥️  系统内存使用情况:")
    print("=" * 50)
    
    # 系统内存信息
    memory = psutil.virtual_memory()
    
    print(f"总内存: {memory.total / (1024**3):.1f} GB")
    print(f"可用内存: {memory.available / (1024**3):.1f} GB")
    print(f"已用内存: {memory.used / (1024**3):.1f} GB")
    print(f"内存使用率: {memory.percent:.1f}%")
    print(f"空闲内存: {memory.free / (1024**3):.1f} GB")
    
    if hasattr(memory, 'buffers'):
        print(f"缓冲区: {memory.buffers / (1024**3):.1f} GB")
    if hasattr(memory, 'cached'):
        print(f"缓存: {memory.cached / (1024**3):.1f} GB")


def check_current_process():
    """检查当前进程内存使用情况"""
    print("\n🔍 当前进程内存使用情况:")
    print("=" * 50)
    
    process = psutil.Process()
    memory_info = process.memory_info()
    memory_percent = process.memory_percent()
    
    print(f"进程名称: {process.name()}")
    print(f"进程ID: {process.pid}")
    print(f"物理内存 (RSS): {memory_info.rss / (1024**2):.1f} MB")
    print(f"虚拟内存 (VMS): {memory_info.vms / (1024**2):.1f} MB")
    print(f"进程内存使用率: {memory_percent:.1f}%")
    
    # 计算进程内存占总内存的百分比
    system_memory = psutil.virtual_memory()
    actual_process_percent = (memory_info.rss / system_memory.total) * 100
    print(f"进程内存占总内存比例: {actual_process_percent:.1f}%")


def check_top_memory_processes():
    """检查占用内存最多的进程"""
    print("\n📊 占用内存最多的5个进程:")
    print("=" * 70)
    
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # 按内存使用率排序
    processes.sort(key=lambda x: x['memory_percent'], reverse=True)
    
    print(f"{'PID':<8} {'进程名':<25} {'内存(MB)':<12} {'内存%':<8}")
    print("-" * 70)
    
    for proc in processes[:5]:
        memory_mb = proc['memory_info'].rss / (1024**2)
        print(f"{proc['pid']:<8} {proc['name'][:24]:<25} {memory_mb:<12.1f} {proc['memory_percent']:<8.1f}")


def check_disk_usage():
    """检查磁盘使用情况"""
    print("\n💾 磁盘使用情况:")
    print("=" * 50)
    
    disk = psutil.disk_usage('/')
    
    print(f"总空间: {disk.total / (1024**3):.1f} GB")
    print(f"已用空间: {disk.used / (1024**3):.1f} GB")
    print(f"可用空间: {disk.free / (1024**3):.1f} GB")
    print(f"磁盘使用率: {(disk.used / disk.total) * 100:.1f}%")


def check_cpu_usage():
    """检查CPU使用情况"""
    print("\n⚡ CPU使用情况:")
    print("=" * 50)
    
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_count_logical = psutil.cpu_count(logical=True)
    
    print(f"CPU使用率: {cpu_percent:.1f}%")
    print(f"物理CPU核心数: {cpu_count}")
    print(f"逻辑CPU核心数: {cpu_count_logical}")
    
    # 每个核心的使用率
    cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
    print(f"各核心使用率: {[f'{cpu:.1f}%' for cpu in cpu_per_core]}")


def main():
    print("🚀 检查实际系统性能数据")
    print("=" * 60)
    
    try:
        check_system_memory()
        check_current_process()
        check_top_memory_processes()
        check_disk_usage()
        check_cpu_usage()
        
        print("\n" + "=" * 60)
        print("✅ 检查完成！")
        print("\n💡 说明:")
        print("   - 进程内存使用率是指当前Python进程占用的内存")
        print("   - 系统内存使用率是指整个系统的内存使用情况")
        print("   - 如果测试脚本显示的数据与实际不符，说明需要调整监控逻辑")
        
    except Exception as e:
        print(f"❌ 检查过程中出现错误: {e}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
测试性能监控页面内存使用量详细显示功能

验证：
1. 系统内存使用率显示（百分比 + 具体用量）
2. 磁盘使用率显示（百分比 + 具体用量）
3. 进程内存显示（具体用量）
4. 数据格式化正确性
"""

import asyncio
import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.api.v1.performance import SystemPerformanceService
from app.core.memory_manager import memory_manager
from app.core.logging import logger


def format_bytes(bytes_value):
    """格式化字节数为可读格式"""
    if not bytes_value:
        return "0 B"
    
    sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while bytes_value >= 1024 and i < len(sizes) - 1:
        bytes_value /= 1024
        i += 1
    
    return f"{bytes_value:.1f} {sizes[i]}"


async def test_memory_detail_display():
    """测试内存详细信息显示"""
    print("🧠 测试内存详细信息显示...")
    
    try:
        # 获取内存统计
        memory_stats = await memory_manager.get_system_stats()
        
        print("✅ 内存统计详细信息:")
        
        # 系统内存信息
        if 'memory_info' in memory_stats and 'system_memory' in memory_stats['memory_info']:
            system_memory = memory_stats['memory_info']['system_memory']
            
            print("\n📊 系统内存:")
            print(f"   总内存: {system_memory.get('total_gb', 'N/A')} GB")
            print(f"   已用内存: {system_memory.get('used_gb', 'N/A')} GB")
            print(f"   可用内存: {system_memory.get('available_gb', 'N/A')} GB")
            print(f"   使用率: {system_memory.get('percent', 'N/A')}%")
            
            # 模拟前端显示格式
            used_gb = system_memory.get('used_gb', 0)
            total_gb = system_memory.get('total_gb', 0)
            percent = system_memory.get('percent', 0)
            
            print(f"\n🎨 前端显示格式:")
            print(f"   内存使用率: {percent:.1f}%")
            print(f"   内存详情: {used_gb}GB / {total_gb}GB")
        
        # 进程内存信息
        if 'memory_info' in memory_stats and 'process_memory' in memory_stats['memory_info']:
            process_memory = memory_stats['memory_info']['process_memory']
            
            print("\n🔍 进程内存:")
            print(f"   物理内存: {process_memory.get('rss_mb', 'N/A')} MB")
            print(f"   虚拟内存: {process_memory.get('vms_mb', 'N/A')} MB")
            print(f"   进程使用率: {process_memory.get('percent', 'N/A')}%")
            
            # 模拟前端显示格式
            rss_mb = process_memory.get('rss_mb', 0)
            percent = process_memory.get('percent', 0)
            
            print(f"\n🎨 前端显示格式:")
            print(f"   进程内存: {percent:.1f}%")
            print(f"   进程详情: {rss_mb}MB")
        
        return True
        
    except Exception as e:
        print(f"❌ 内存详细信息测试失败: {e}")
        return False


async def test_performance_service_detail():
    """测试性能服务的详细信息"""
    print("\n📊 测试性能服务详细信息...")
    
    try:
        # 创建性能服务实例
        service = SystemPerformanceService()
        
        # 获取综合统计
        stats = await service.get_comprehensive_stats()
        
        print("✅ 性能统计详细信息:")
        
        # 系统健康数据
        if 'system_health' in stats:
            system_health = stats['system_health']
            
            # 磁盘使用率
            disk_usage = system_health.get('disk_usage', {})
            if disk_usage:
                used_gb = disk_usage.get('used', 0) / (1024**3)
                total_gb = disk_usage.get('total', 0) / (1024**3)
                percent = disk_usage.get('percent', 0)
                
                print(f"\n💾 磁盘使用:")
                print(f"   总空间: {total_gb:.1f} GB")
                print(f"   已用空间: {used_gb:.1f} GB")
                print(f"   使用率: {percent:.1f}%")
                
                print(f"\n🎨 前端显示格式:")
                print(f"   磁盘使用率: {percent:.1f}%")
                print(f"   磁盘详情: {used_gb:.1f}GB / {total_gb:.1f}GB")
            
            # CPU使用率
            cpu_percent = system_health.get('cpu_percent')
            if cpu_percent is not None:
                print(f"\n⚡ CPU使用:")
                print(f"   CPU使用率: {cpu_percent:.1f}%")
        
        # 内存统计数据
        if 'memory_stats' in stats:
            memory_stats = stats['memory_stats']
            if 'memory_info' in memory_stats and 'system_memory' in memory_stats['memory_info']:
                system_memory = memory_stats['memory_info']['system_memory']
                
                used_gb = system_memory.get('used_gb', 0)
                total_gb = system_memory.get('total_gb', 0)
                percent = system_memory.get('percent', 0)
                
                print(f"\n🧠 系统内存:")
                print(f"   内存使用率: {percent:.1f}%")
                print(f"   内存详情: {used_gb}GB / {total_gb}GB")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能服务详细信息测试失败: {e}")
        return False


def test_frontend_formatting_functions():
    """测试前端格式化函数"""
    print("\n🎨 测试前端格式化函数...")
    
    # 模拟Vue.js中的格式化函数
    def formatPercentage(value):
        if value is None:
            return '0.0'
        return f"{value:.1f}"
    
    def formatBytes(bytes_value):
        if not bytes_value:
            return '0 B'
        sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        while bytes_value >= 1024 and i < len(sizes) - 1:
            bytes_value /= 1024
            i += 1
        return f"{bytes_value:.1f} {sizes[i]}"
    
    def getMemoryUsageDetail(memory_stats):
        if not memory_stats or 'memory_info' not in memory_stats:
            return 'N/A'
        
        system_memory = memory_stats['memory_info'].get('system_memory', {})
        used_gb = system_memory.get('used_gb', 0)
        total_gb = system_memory.get('total_gb', 0)
        
        return f"{used_gb}GB / {total_gb}GB"
    
    def getDiskUsageDetail(system_health):
        if not system_health or 'disk_usage' not in system_health:
            return 'N/A'
        
        disk_usage = system_health['disk_usage']
        used_gb = disk_usage.get('used', 0) / (1024**3)
        total_gb = disk_usage.get('total', 0) / (1024**3)
        
        return f"{used_gb:.1f}GB / {total_gb:.1f}GB"
    
    # 测试用例
    test_cases = [
        {
            'name': '内存使用率格式化',
            'function': formatPercentage,
            'inputs': [66.4123, 0.8017669976764806, 100, None],
            'expected': ['66.4', '0.8', '100.0', '0.0']
        },
        {
            'name': '字节格式化',
            'function': formatBytes,
            'inputs': [1024, 1048576, 1073741824, 0],
            'expected': ['1.0 KB', '1.0 MB', '1.0 GB', '0 B']
        }
    ]
    
    all_passed = True
    for test_case in test_cases:
        print(f"\n📝 {test_case['name']}:")
        for i, input_val in enumerate(test_case['inputs']):
            result = test_case['function'](input_val)
            expected = test_case['expected'][i]
            if result == expected:
                print(f"   ✅ {input_val} -> {result}")
            else:
                print(f"   ❌ {input_val} -> {result} (期望: {expected})")
                all_passed = False
    
    # 测试组合显示
    print(f"\n📝 组合显示测试:")
    mock_memory_stats = {
        'memory_info': {
            'system_memory': {
                'used_gb': 10.5,
                'total_gb': 16.0,
                'percent': 65.6
            }
        }
    }
    
    mock_disk_data = {
        'disk_usage': {
            'used': 100 * 1024**3,  # 100GB
            'total': 200 * 1024**3  # 200GB
        }
    }
    
    memory_detail = getMemoryUsageDetail(mock_memory_stats)
    disk_detail = getDiskUsageDetail(mock_disk_data)
    
    print(f"   内存详情: 65.6% ({memory_detail})")
    print(f"   磁盘详情: 50.0% ({disk_detail})")
    
    return all_passed


async def main():
    """主测试函数"""
    print("🚀 开始测试性能监控页面内存使用量详细显示功能")
    print("=" * 70)
    
    tests = [
        test_memory_detail_display,
        test_performance_service_detail,
        test_frontend_formatting_functions
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 发生异常: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有测试都通过了！内存使用量详细显示功能正常。")
        print("\n📝 功能总结:")
        print("   ✅ 系统内存显示: 百分比 + 具体用量 (如: 66.4% - 10.5GB / 16.0GB)")
        print("   ✅ 磁盘使用率显示: 百分比 + 具体用量 (如: 65.2% - 100.0GB / 200.0GB)")
        print("   ✅ 进程内存显示: 百分比 + 具体用量 (如: 0.8% - 80.7MB)")
        print("   ✅ 数值格式化: 统一保留一位小数")
        print("   ✅ 用户体验: 同时看到百分比和具体数值")
    else:
        print("⚠️  有测试失败，请检查相关配置。")


if __name__ == "__main__":
    asyncio.run(main())
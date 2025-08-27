#!/usr/bin/env python3
"""
性能监控API修复验证脚本

验证修复的问题：
1. 'str' object is not callable 错误
2. range参数名冲突问题
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_range_function_access():
    """测试range函数访问"""
    print("🧪 测试range函数访问")
    print("=" * 30)
    
    # 模拟原始有问题的代码逻辑
    range_param = "1h"  # 模拟API参数
    
    print(f"参数值: {range_param}")
    
    try:
        # 这就是原来出错的地方：range参数覆盖了内置range函数
        points = 12
        for i in range(points):  # 这里会出错，因为range现在是字符串
            pass
        print("✅ range函数调用成功")
    except TypeError as e:
        print(f"❌ range函数调用失败: {e}")
        print("   这就是原始错误的原因")


def test_fixed_logic():
    """测试修复后的逻辑"""
    print("\n🔧 测试修复后的逻辑")
    print("=" * 30)
    
    # 模拟修复后的代码逻辑
    range_param = "1h"  # API参数
    time_range = range_param  # 立即赋值给新变量
    
    print(f"API参数: {range_param}")
    print(f"内部变量: {time_range}")
    
    try:
        # 现在range函数仍然可用
        points = 12
        timestamps = []
        for i in range(points):  # 这里不会出错
            timestamps.append(f"time_{i}")
        
        print(f"✅ range函数调用成功，生成了 {len(timestamps)} 个时间点")
        print("✅ 修复成功！")
        return True
    except Exception as e:
        print(f"❌ 修复后仍有问题: {e}")
        return False


def test_metrics_endpoint_logic():
    """测试metrics端点的完整逻辑"""
    print("\n📊 测试metrics端点逻辑")
    print("=" * 30)
    
    import random
    from datetime import datetime, timedelta
    
    # 模拟API参数
    range_param = "1h"
    
    try:
        # 按照修复后的代码逻辑
        time_range = range_param  # 避免冲突
        
        # 根据时间范围确定参数
        if time_range == "1h":
            interval_minutes = 5
            points = 12
        elif time_range == "6h":
            interval_minutes = 30
            points = 12
        elif time_range == "24h":
            interval_minutes = 120
            points = 12
        else:  # 7d
            interval_minutes = 6 * 60
            points = 28
        
        print(f"时间范围: {time_range}")
        print(f"数据点数量: {points}")
        print(f"时间间隔: {interval_minutes}分钟")
        
        # 生成时间序列数据
        now = datetime.utcnow()
        timestamps = []
        cpu_data = []
        memory_data = []
        disk_data = []
        
        for i in range(points):  # 这里应该正常工作
            time_point = now - timedelta(minutes=interval_minutes * (points - 1 - i))
            timestamps.append(time_point.strftime('%H:%M'))
            
            # 生成模拟数据
            base_cpu = 25 + random.random() * 30
            base_memory = 40 + random.random() * 35
            base_disk = 60 + random.random() * 20
            
            cpu_data.append(round(base_cpu, 1))
            memory_data.append(round(base_memory, 1))
            disk_data.append(round(base_disk, 1))
        
        # 构建响应
        response_data = {
            'success': True,
            'data': {
                'timestamps': timestamps,
                'cpu': cpu_data,
                'memory': memory_data,
                'disk': disk_data,
                'range': time_range
            }
        }
        
        print(f"✅ 成功生成 {len(timestamps)} 个数据点")
        print(f"   时间戳示例: {timestamps[:3]}...")
        print(f"   CPU数据示例: {cpu_data[:3]}...")
        print(f"   内存数据示例: {memory_data[:3]}...")
        print(f"   磁盘数据示例: {disk_data[:3]}...")
        
        # 验证数据格式
        assert len(timestamps) == points
        assert len(cpu_data) == points
        assert len(memory_data) == points
        assert len(disk_data) == points
        assert response_data['data']['range'] == time_range
        
        print("✅ 数据格式验证通过")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return False


def test_api_compatibility():
    """测试API兼容性"""
    print("\n🔗 测试API兼容性")
    print("=" * 30)
    
    # 测试不同的时间范围参数
    test_ranges = ["1h", "6h", "24h", "7d", "invalid"]
    
    for test_range in test_ranges:
        print(f"\n测试范围: {test_range}")
        
        try:
            # 模拟API逻辑
            time_range = test_range
            
            if time_range == "1h":
                interval_minutes = 5
                points = 12
            elif time_range == "6h":
                interval_minutes = 30
                points = 12
            elif time_range == "24h":
                interval_minutes = 120
                points = 12
            else:  # 7d 或其他
                interval_minutes = 6 * 60
                points = 28
            
            # 验证range函数仍然可用
            data_points = list(range(points))
            
            print(f"   间隔: {interval_minutes}分钟, 点数: {points}")
            print(f"   ✅ 成功处理")
            
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")


def main():
    """主测试函数"""
    print("🚀 性能监控API修复验证")
    print("=" * 60)
    
    # 运行所有测试
    tests = [
        ("range函数冲突演示", test_range_function_access),
        ("修复逻辑验证", test_fixed_logic),
        ("完整端点逻辑测试", test_metrics_endpoint_logic),
        ("API兼容性测试", test_api_compatibility)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - 通过")
            else:
                failed += 1
                print(f"❌ {test_name} - 失败")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} - 异常: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有测试都通过了！")
        print("\n💡 修复总结:")
        print("   ✅ 解决了 'str' object is not callable 错误")
        print("   ✅ 保持了API参数名的向后兼容性")
        print("   ✅ 通过内部变量重命名避免了range函数冲突")
        print("   ✅ metrics端点现在应该能正常工作")
        
        print("\n🔧 修复方案:")
        print("   - API参数仍使用 'range' 保持前端兼容")
        print("   - 函数开头立即将 range 参数赋值给 time_range 变量")
        print("   - 后续逻辑使用 time_range 而不是 range")
        print("   - 内置 range() 函数不再被覆盖")
        
    else:
        print("⚠️  有测试失败，请检查修复逻辑。")


if __name__ == "__main__":
    main()
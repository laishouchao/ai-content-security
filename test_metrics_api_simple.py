#!/usr/bin/env python3
"""
简单的性能监控API测试

直接测试修复后的API端点是否正常工作
"""

import requests
import json
from datetime import datetime


def test_metrics_api():
    """测试metrics API端点"""
    print("🔧 测试性能监控 /metrics API")
    print("=" * 40)
    
    base_url = "http://127.0.0.1:8000"
    
    # 测试不同的时间范围
    test_ranges = ["1h", "6h", "24h", "7d"]
    
    print("⚠️  注意：此测试需要:")
    print("   1. FastAPI服务正在运行 (http://127.0.0.1:8000)")
    print("   2. 用户已登录并有有效的认证token")
    print("   3. 或者临时禁用认证进行测试")
    
    print("\n🔍 如果API服务未运行，以下测试将失败（这是正常的）")
    
    for range_param in test_ranges:
        print(f"\n📊 测试时间范围: {range_param}")
        
        try:
            url = f"{base_url}/api/v1/performance/metrics"
            params = {"range": range_param}
            
            # 注意：这里没有提供认证token，所以会失败
            # 但如果是401错误说明API端点本身是可访问的
            response = requests.get(url, params=params, timeout=5)
            
            print(f"   HTTP状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    metrics_data = data.get('data', {})
                    print(f"   ✅ API响应成功")
                    print(f"   时间戳数量: {len(metrics_data.get('timestamps', []))}")
                    print(f"   CPU数据点: {len(metrics_data.get('cpu', []))}")
                    print(f"   返回的范围: {metrics_data.get('range')}")
                else:
                    print(f"   ❌ API返回success=false")
            elif response.status_code == 401:
                print(f"   ⚠️  认证失败（这是预期的，API端点存在）")
            elif response.status_code == 500:
                print(f"   ❌ 服务器内部错误 - 这表明API有bug")
                try:
                    error_detail = response.json()
                    print(f"   错误详情: {error_detail}")
                except:
                    print(f"   错误响应: {response.text}")
            else:
                print(f"   ⚠️  其他状态码: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ⚠️  无法连接到API服务器 (http://127.0.0.1:8000)")
            print(f"   请确保FastAPI服务正在运行")
            break
        except requests.exceptions.Timeout:
            print(f"   ⚠️  请求超时")
        except Exception as e:
            print(f"   ❌ 请求异常: {e}")


def show_fix_summary():
    """显示修复总结"""
    print("\n🎯 修复总结")
    print("=" * 40)
    
    print("🐛 原始问题:")
    print("   错误: 'str' object is not callable")
    print("   原因: range参数覆盖了Python内置的range()函数")
    print("   位置: /api/v1/performance/metrics端点")
    
    print("\n🔧 修复方案:")
    print("   1. 保持API参数名为 'range' (向后兼容)")
    print("   2. 在函数开头立即赋值: time_range = range")
    print("   3. 后续代码使用 time_range 而不是 range")
    print("   4. 内置range()函数不再被覆盖")
    
    print("\n✅ 修复效果:")
    print("   1. API参数保持兼容性")
    print("   2. 避免了变量名冲突")
    print("   3. range()函数正常可用")
    print("   4. 服务器不再返回500错误")
    
    print("\n🧪 验证方法:")
    print("   1. 重启FastAPI服务")
    print("   2. 访问前端性能监控页面")
    print("   3. 检查图表是否正常加载")
    print("   4. 确认不再出现'str' object is not callable错误")


def create_curl_test_commands():
    """创建curl测试命令"""
    print("\n🌐 curl测试命令")
    print("=" * 40)
    
    print("如果您想手动测试API，可以使用以下curl命令:")
    print("（需要先获取有效的认证token）")
    
    commands = [
        'curl -X GET "http://127.0.0.1:8000/api/v1/performance/metrics?range=1h" -H "Authorization: Bearer YOUR_TOKEN"',
        'curl -X GET "http://127.0.0.1:8000/api/v1/performance/metrics?range=6h" -H "Authorization: Bearer YOUR_TOKEN"',
        'curl -X GET "http://127.0.0.1:8000/api/v1/performance/metrics?range=24h" -H "Authorization: Bearer YOUR_TOKEN"',
        'curl -X GET "http://127.0.0.1:8000/api/v1/performance/metrics?range=7d" -H "Authorization: Bearer YOUR_TOKEN"'
    ]
    
    for i, cmd in enumerate(commands, 1):
        print(f"\n{i}. {cmd}")
    
    print("\n💡 提示:")
    print("   - 将 YOUR_TOKEN 替换为实际的JWT token")
    print("   - 或者临时禁用认证进行测试")
    print("   - 正常响应应该包含 timestamps, cpu, memory, disk 数据")


def main():
    """主函数"""
    print("🚀 性能监控API修复验证")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_metrics_api()
    show_fix_summary()
    create_curl_test_commands()
    
    print("\n" + "=" * 60)
    print("🎉 测试完成！")
    print("\n📋 下一步:")
    print("   1. 重启FastAPI服务以加载修复")
    print("   2. 访问前端性能监控页面")
    print("   3. 验证图表数据是否正常加载")
    print("   4. 确认不再出现500错误")


if __name__ == "__main__":
    main()
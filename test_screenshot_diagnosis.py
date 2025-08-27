#!/usr/bin/env python3
"""
截图功能诊断和修复脚本

分析问题：
1. 从日志看，虽然内容抓取成功，但AI分析时所有域名都显示"没有有效的截图文件"
2. 可能原因：截图文件路径存储不正确，或文件未正确生成

功能：
1. 测试截图服务功能
2. 检查截图文件路径生成
3. 验证AI分析阶段的截图文件查找逻辑
4. 提供修复建议
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.engines.content_capture import ScreenshotService, ContentCaptureEngine
from app.core.config import settings


async def test_screenshot_service():
    """测试截图服务基本功能"""
    print("📸 测试截图服务基本功能...")
    
    # 创建测试任务ID
    test_task_id = f"test_{int(datetime.now().timestamp())}"
    
    try:
        # 测试截图服务
        async with ScreenshotService(test_task_id) as screenshot_service:
            
            # 测试URL列表
            test_urls = [
                "https://www.example.com",
                "https://www.google.com",
                "https://httpbin.org/html"
            ]
            
            print(f"   测试任务ID: {test_task_id}")
            print(f"   截图保存目录: {screenshot_service.screenshot_dir}")
            print(f"   目录是否存在: {screenshot_service.screenshot_dir.exists()}")
            
            results = []
            for url in test_urls:
                print(f"   正在截图: {url}")
                try:
                    screenshot_path, html_content = await screenshot_service.capture_screenshot(url)
                    
                    # 检查文件是否真实存在
                    file_exists = os.path.exists(screenshot_path)
                    file_size = os.path.getsize(screenshot_path) if file_exists else 0
                    
                    result = {
                        'url': url,
                        'screenshot_path': screenshot_path,
                        'file_exists': file_exists,
                        'file_size': file_size,
                        'html_length': len(html_content) if html_content else 0
                    }
                    results.append(result)
                    
                    print(f"     ✅ 截图路径: {screenshot_path}")
                    print(f"     ✅ 文件存在: {file_exists}")
                    print(f"     ✅ 文件大小: {file_size} bytes")
                    print(f"     ✅ HTML长度: {len(html_content) if html_content else 0}")
                    
                except Exception as e:
                    print(f"     ❌ 截图失败: {e}")
                    results.append({
                        'url': url,
                        'error': str(e)
                    })
            
            return results
            
    except Exception as e:
        print(f"❌ 截图服务测试失败: {e}")
        return []


async def test_content_capture_engine():
    """测试内容抓取引擎"""
    print("\n🏭 测试内容抓取引擎...")
    
    test_task_id = f"test_{int(datetime.now().timestamp())}"
    test_user_id = "test_user"
    
    try:
        capture_engine = ContentCaptureEngine(test_task_id, test_user_id)
        
        # 测试域名和URL
        test_domain = "example.com"
        test_urls = [
            "https://example.com",
            "http://example.com"
        ]
        
        config = {
            'capture_screenshots': True,
            'max_captures_per_domain': 10
        }
        
        print(f"   测试域名: {test_domain}")
        print(f"   测试URL: {test_urls}")
        
        # 执行内容抓取
        results = await capture_engine.capture_domain_content(
            test_domain, test_urls, config
        )
        
        print(f"   抓取结果数量: {len(results)}")
        
        for i, result in enumerate(results):
            print(f"   结果 {i+1}:")
            print(f"     URL: {result.url}")
            print(f"     截图路径: {result.screenshot_path}")
            print(f"     文件存在: {os.path.exists(result.screenshot_path) if result.screenshot_path else False}")
            print(f"     错误信息: {result.error_message}")
            print(f"     状态码: {result.status_code}")
        
        return results
        
    except Exception as e:
        print(f"❌ 内容抓取引擎测试失败: {e}")
        return []


def analyze_screenshot_path_logic():
    """分析截图路径生成逻辑"""
    print("\n🔍 分析截图路径生成逻辑...")
    
    # 模拟真实任务的截图路径生成
    task_id = "f4e0ea3d-d2a6-4af0-85e1-6b2af552a0bb"  # 从日志中的真实任务ID
    
    # 方法1: ScreenshotService的路径生成
    screenshot_dir_1 = Path(settings.SCREENSHOT_PATH) / task_id
    print(f"   ScreenshotService路径: {screenshot_dir_1}")
    print(f"   路径存在: {screenshot_dir_1.exists()}")
    
    # 方法2: 可能的旧版本路径生成
    screenshot_dir_2 = Path("screenshots") / task_id
    print(f"   相对路径方式: {screenshot_dir_2}")
    print(f"   路径存在: {screenshot_dir_2.exists()}")
    
    # 检查设置中的截图路径配置
    print(f"   配置中的截图路径: {settings.SCREENSHOT_PATH}")
    
    # 列出可能的截图文件
    for path in [screenshot_dir_1, screenshot_dir_2]:
        if path.exists():
            print(f"   {path} 目录内容:")
            try:
                files = list(path.glob("*.png"))
                for file in files[:5]:  # 只显示前5个文件
                    print(f"     - {file.name} ({file.stat().st_size} bytes)")
                if len(files) > 5:
                    print(f"     ... 还有 {len(files) - 5} 个文件")
            except Exception as e:
                print(f"     无法列出文件: {e}")


def check_ai_analysis_screenshot_logic():
    """检查AI分析阶段的截图文件查找逻辑"""
    print("\n🤖 检查AI分析阶段的截图文件查找逻辑...")
    
    # 模拟AI分析阶段的逻辑
    print("   AI分析期望的截图查找逻辑:")
    print("   1. 从content_results中获取screenshot_path")
    print("   2. 使用Path(screenshot_path).exists()检查文件存在")
    print("   3. 如果不存在，跳过AI分析")
    
    # 问题分析
    print("\n   可能的问题原因:")
    print("   1. content_results中的screenshot_path为空或None")
    print("   2. screenshot_path是相对路径，但检查时使用绝对路径")
    print("   3. 截图文件生成失败但路径仍被保存")
    print("   4. 路径字符串格式问题（反斜杠vs正斜杠）")
    
    print("\n   推荐的修复方案:")
    print("   1. 在AI分析前验证截图文件确实存在")
    print("   2. 统一截图路径格式（绝对路径）")
    print("   3. 添加更详细的日志记录截图路径")
    print("   4. 在content_capture阶段验证截图文件生成成功")


async def test_real_subdomain_screenshot():
    """测试真实子域名截图功能"""
    print("\n🏠 测试真实子域名截图功能...")
    
    # 使用一些真实的、可访问的子域名进行测试
    test_subdomains = [
        "www.example.com",
        "docs.github.com", 
        "api.github.com"
    ]
    
    test_task_id = f"subdomain_test_{int(datetime.now().timestamp())}"
    test_user_id = "test_user"
    
    try:
        capture_engine = ContentCaptureEngine(test_task_id, test_user_id)
        
        config = {
            'capture_screenshots': True,
            'max_captures_per_domain': 5
        }
        
        all_results = []
        
        for subdomain in test_subdomains:
            print(f"   测试子域名: {subdomain}")
            
            urls_to_capture = [
                f"https://{subdomain}",
                f"http://{subdomain}"
            ]
            
            try:
                results = await capture_engine.capture_domain_content(
                    subdomain, urls_to_capture, config
                )
                
                for result in results:
                    print(f"     URL: {result.url}")
                    print(f"     截图路径: {result.screenshot_path}")
                    
                    if result.screenshot_path:
                        file_exists = os.path.exists(result.screenshot_path)
                        file_size = os.path.getsize(result.screenshot_path) if file_exists else 0
                        print(f"     文件存在: {file_exists}")
                        print(f"     文件大小: {file_size} bytes")
                        
                        # 这里模拟AI分析阶段的检查逻辑
                        ai_check_result = Path(result.screenshot_path).exists()
                        print(f"     AI分析检查: {ai_check_result}")
                    else:
                        print(f"     ❌ 截图路径为空")
                    
                    if result.error_message:
                        print(f"     错误: {result.error_message}")
                
                all_results.extend(results)
                
            except Exception as e:
                print(f"     ❌ 抓取失败: {e}")
        
        return all_results
        
    except Exception as e:
        print(f"❌ 子域名截图测试失败: {e}")
        return []


def provide_fix_recommendations():
    """提供修复建议"""
    print("\n💡 修复建议:")
    print("=" * 60)
    
    print("1. 截图路径标准化:")
    print("   - 统一使用绝对路径存储截图文件路径")
    print("   - 确保所有截图路径都以正斜杠分隔")
    print("   - 在保存路径前验证文件确实存在")
    
    print("\n2. AI分析阶段改进:")
    print("   - 在准备AI分析时，添加更详细的截图路径检查日志")
    print("   - 对于找不到截图的情况，记录具体的路径信息")
    print("   - 考虑支持多种路径格式的检查")
    
    print("\n3. 内容抓取阶段改进:")
    print("   - 在截图完成后立即验证文件是否成功生成")
    print("   - 如果截图失败，不要保存空的screenshot_path")
    print("   - 添加截图失败重试机制")
    
    print("\n4. 调试改进:")
    print("   - 在AI分析阶段输出更详细的截图路径信息")
    print("   - 记录每个域名的截图文件查找过程")
    print("   - 统计成功/失败的截图数量")
    
    print("\n5. 子域名AI分析确保:")
    print("   - 验证子域名截图抓取是否正确执行")
    print("   - 确认子域名记录正确添加到AI分析队列")
    print("   - 检查子域名和第三方域名的统计是否正确")


async def main():
    """主测试函数"""
    print("🚀 开始截图功能诊断")
    print("=" * 60)
    
    # 基础配置检查
    print(f"截图配置路径: {settings.SCREENSHOT_PATH}")
    print(f"浏览器无头模式: {settings.PLAYWRIGHT_HEADLESS}")
    print(f"截图超时设置: {settings.PLAYWRIGHT_TIMEOUT}")
    print()
    
    # 运行所有测试
    try:
        # 测试1: 基础截图服务
        screenshot_results = await test_screenshot_service()
        
        # 测试2: 内容抓取引擎
        capture_results = await test_content_capture_engine()
        
        # 测试3: 分析路径逻辑
        analyze_screenshot_path_logic()
        
        # 测试4: AI分析逻辑检查
        check_ai_analysis_screenshot_logic()
        
        # 测试5: 真实子域名测试
        subdomain_results = await test_real_subdomain_screenshot()
        
        # 提供修复建议
        provide_fix_recommendations()
        
        print("\n" + "=" * 60)
        print("📊 诊断结果总结:")
        
        successful_screenshots = len([r for r in screenshot_results if 'error' not in r and r.get('file_exists')])
        total_screenshots = len(screenshot_results)
        
        print(f"   基础截图成功率: {successful_screenshots}/{total_screenshots}")
        
        if capture_results:
            successful_captures = len([r for r in capture_results if r.screenshot_path and os.path.exists(r.screenshot_path)])
            print(f"   内容抓取截图成功: {successful_captures}/{len(capture_results)}")
        
        if subdomain_results:
            successful_subdomains = len([r for r in subdomain_results if r.screenshot_path and os.path.exists(r.screenshot_path)])
            print(f"   子域名截图成功: {successful_subdomains}/{len(subdomain_results)}")
        
        print("\n🎯 关键发现:")
        print("   如果截图功能本身正常工作，但AI分析时找不到文件，")
        print("   问题很可能在于路径存储或查找逻辑不一致。")
        print("   建议检查content_results中保存的screenshot_path格式。")
        
    except Exception as e:
        print(f"❌ 诊断过程中出现异常: {e}")


if __name__ == "__main__":
    asyncio.run(main())
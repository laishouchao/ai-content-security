#!/usr/bin/env python3
"""
测试优化的截图服务和AI分析输出管理器
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from app.engines.optimized_screenshot_service import OptimizedScreenshotService, DomainScreenshotResult
from app.engines.ai_analysis_output_manager import AIAnalysisOutputManager


async def test_optimized_screenshot_service():
    """测试优化的截图服务"""
    print("=== 测试优化的截图服务 ===")
    
    task_id = "test_task_" + str(int(asyncio.get_event_loop().time()))
    
    # 测试域名列表
    test_domains = [
        "www.baidu.com",
        "www.github.com", 
        "www.stackoverflow.com"
    ]
    
    try:
        async with OptimizedScreenshotService(task_id, "test_user") as screenshot_service:
            # 测试配置
            config = {
                'skip_existing': False,  # 强制重新截图
                'timeout': 30000
            }
            
            print(f"开始测试 {len(test_domains)} 个域名的截图...")
            
            # 执行优化截图
            results = await screenshot_service.capture_domains_optimized(test_domains, config)
            
            print(f"\n截图结果:")
            success_count = 0
            for result in results:
                status = "✓" if result.success else "✗"
                print(f"{status} {result.domain}: {result.error_message if not result.success else f'截图大小: {result.file_size} bytes'}")
                if result.success:
                    success_count += 1
                    print(f"   截图路径: {result.screenshot_path}")
                    print(f"   源码路径: {result.source_code_path}")
                    print(f"   页面标题: {result.page_title}")
                    print(f"   内容哈希: {result.content_hash}")
            
            print(f"\n成功率: {success_count}/{len(test_domains)} ({success_count/len(test_domains)*100:.1f}%)")
            
            # 获取统计信息
            stats = screenshot_service.get_statistics()
            print(f"\n服务统计:")
            print(f"- 截图文件数: {stats.get('screenshot_count', 0)}")
            print(f"- 源码文件数: {stats.get('source_code_count', 0)}")
            print(f"- 临时文件数: {stats.get('temp_file_count', 0)}")
            print(f"- 截图总大小: {stats.get('total_screenshot_size_mb', 0)} MB")
            print(f"- 源码总大小: {stats.get('total_source_size_mb', 0)} MB")
            
            # 测试获取分析数据
            print(f"\n测试获取分析数据:")
            for domain in test_domains[:2]:  # 只测试前两个
                analysis_data = await screenshot_service.get_domain_analysis_data(domain)
                if analysis_data:
                    print(f"✓ {domain}: 找到分析数据")
                    print(f"   - 截图路径: {analysis_data.get('screenshot_path', 'N/A')}")
                    print(f"   - 源码路径: {analysis_data.get('source_code_path', 'N/A')}")
                    print(f"   - 页面标题: {analysis_data.get('page_title', 'N/A')}")
                else:
                    print(f"✗ {domain}: 未找到分析数据")
            
            return True
            
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_ai_analysis_output_manager():
    """测试AI分析输出管理器"""
    print("\n=== 测试AI分析输出管理器 ===")
    
    task_id = "test_task_" + str(int(asyncio.get_event_loop().time()))
    
    try:
        output_manager = AIAnalysisOutputManager(task_id, "test_user")
        
        # 测试数据
        test_domain = "example.com"
        screenshot_path = "test_screenshot.png" 
        source_code_path = "test_source.html"
        
        # 创建模拟的截图和源码文件
        test_screenshot_data = b"fake_png_data"
        test_source_code = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>测试页面</title>
            <meta name="description" content="这是一个测试页面">
        </head>
        <body>
            <h1>测试内容</h1>
            <p>这是测试文本内容</p>
        </body>
        </html>
        """
        
        # 创建临时文件
        temp_screenshot = Path("temp_test_screenshot.png")
        temp_source = Path("temp_test_source.html")
        
        with open(temp_screenshot, 'wb') as f:
            f.write(test_screenshot_data)
        
        with open(temp_source, 'w', encoding='utf-8') as f:
            f.write(test_source_code)
        
        try:
            print("测试准备分析输入文件...")
            
            # 准备分析输入
            input_file_path = await output_manager.prepare_analysis_input(
                test_domain,
                str(temp_screenshot),
                str(temp_source),
                {"additional_info": "test_data"}
            )
            
            print(f"✓ 输入文件创建成功: {input_file_path}")
            
            # 验证输入文件内容
            input_data = output_manager.load_input_data(input_file_path)
            if input_data:
                print("✓ 输入文件内容验证成功")
                print(f"   - 域名: {input_data.get('domain')}")
                print(f"   - 页面标题: {input_data.get('page_title')}")
                print(f"   - 页面描述: {input_data.get('page_description')}")
                print(f"   - 源码长度: {input_data.get('source_code_length', 0)}")
                print(f"   - 截图大小: {input_data.get('screenshot_size', 0)}")
            else:
                print("✗ 输入文件内容验证失败")
                return False
            
            print("\n测试保存分析输出文件...")
            
            # 模拟AI分析结果
            mock_analysis_result = {
                "has_violation": False,
                "violation_types": [],
                "confidence_score": 0.85,
                "risk_level": "low",
                "title": "测试网站",
                "description": "这是一个测试网站，没有发现安全问题"
            }
            
            mock_ai_response = '{"success": true, "analysis": "mock_response"}'
            
            # 保存分析输出
            output_file_path = await output_manager.save_analysis_output(
                test_domain,
                mock_analysis_result,
                mock_ai_response,
                input_file_path
            )
            
            print(f"✓ 输出文件创建成功: {output_file_path}")
            
            # 测试加载最新分析结果
            latest_result = output_manager.load_latest_analysis_result(test_domain)
            if latest_result:
                print("✓ 最新分析结果加载成功")
                print(f"   - 有违规: {latest_result.get('processing_info', {}).get('has_violation', False)}")
                print(f"   - 置信度: {latest_result.get('processing_info', {}).get('confidence_score', 0)}")
                print(f"   - 风险等级: {latest_result.get('processing_info', {}).get('risk_level', 'unknown')}")
            else:
                print("✗ 最新分析结果加载失败")
                return False
            
            # 获取分析摘要
            summary = output_manager.get_analysis_summary()
            print(f"\n分析摘要:")
            print(f"- 输入文件数: {summary.get('total_input_files', 0)}")
            print(f"- 输出文件数: {summary.get('total_output_files', 0)}")
            print(f"- 总分析数: {summary.get('total_analyzed', 0)}")
            print(f"- 违规数量: {summary.get('violation_count', 0)}")
            print(f"- 违规率: {summary.get('violation_rate', 0)}%")
            
            return True
            
        finally:
            # 清理临时文件
            for temp_file in [temp_screenshot, temp_source]:
                if temp_file.exists():
                    temp_file.unlink()
    
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integration():
    """测试整合功能"""
    print("\n=== 测试整合功能 ===")
    
    task_id = "integration_test_" + str(int(asyncio.get_event_loop().time()))
    
    try:
        # 测试域名
        test_domain = "httpbin.org"  # 一个稳定的测试API网站
        
        print(f"测试域名: {test_domain}")
        
        # 1. 截图服务
        async with OptimizedScreenshotService(task_id, "test_user") as screenshot_service:
            config = {'skip_existing': False}
            
            print("步骤1: 执行截图...")
            results = await screenshot_service.capture_domains_optimized([test_domain], config)
            
            if not results or not results[0].success:
                print("✗ 截图失败")
                return False
            
            result = results[0]
            print(f"✓ 截图成功: {result.screenshot_path}")
            
            # 2. AI分析输出管理
            output_manager = AIAnalysisOutputManager(task_id, "test_user")
            
            print("步骤2: 准备AI分析输入...")
            input_file_path = await output_manager.prepare_analysis_input(
                test_domain,
                result.screenshot_path,
                result.source_code_path
            )
            print(f"✓ AI输入文件: {input_file_path}")
            
            # 3. 模拟AI分析
            print("步骤3: 模拟AI分析...")
            mock_result = {
                "has_violation": False,
                "violation_types": [],
                "confidence_score": 0.9,
                "risk_level": "low",
                "title": "测试网站安全检查",
                "description": "网站内容正常，未发现安全问题"
            }
            
            output_file_path = await output_manager.save_analysis_output(
                test_domain,
                mock_result,
                '{"mock": "ai_response"}',
                input_file_path
            )
            print(f"✓ AI输出文件: {output_file_path}")
            
            # 4. 验证完整流程
            analysis_data = await screenshot_service.get_domain_analysis_data(test_domain)
            if analysis_data:
                print("✓ 完整流程验证成功")
                print(f"   - 截图文件: {Path(analysis_data['screenshot_path']).exists()}")
                print(f"   - 源码文件: {Path(analysis_data['source_code_path']).exists() if analysis_data.get('source_code_path') else False}")
                print(f"   - 临时文件: {Path(analysis_data['temp_analysis_path']).exists() if analysis_data.get('temp_analysis_path') else False}")
            else:
                print("✗ 完整流程验证失败")
                return False
            
            return True
    
    except Exception as e:
        print(f"整合测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("🚀 开始测试优化的截图和AI分析系统")
    print("=" * 60)
    
    # 运行测试
    tests = [
        ("优化截图服务", test_optimized_screenshot_service),
        ("AI分析输出管理器", test_ai_analysis_output_manager),
        ("整合功能", test_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 运行测试: {test_name}")
            success = await test_func()
            results.append((test_name, success))
            status = "✅ 通过" if success else "❌ 失败"
            print(f"测试结果: {status}")
        except Exception as e:
            print(f"❌ 测试 {test_name} 出现异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结:")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n总体结果: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 所有测试通过！优化方案工作正常。")
    else:
        print("⚠️  部分测试失败，需要检查相关功能。")


if __name__ == "__main__":
    asyncio.run(main())
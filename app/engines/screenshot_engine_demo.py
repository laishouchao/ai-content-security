"""
截图引擎测试和使用示例
展示如何使用截图引擎进行网页截图

包含：
1. 基本截图功能测试
2. 批量截图测试
3. 配置选项演示
4. 错误处理测试
"""

import asyncio
import os
import time
from typing import List, Dict, Any

from app.engines.screenshot_engine import (
    UniversalScreenshotEngine, 
    ScreenshotConfig, 
    ScreenshotResult,
    BatchScreenshotResult
)


class ScreenshotEngineDemo:
    """截图引擎演示类"""
    
    def __init__(self):
        self.task_id = "demo_task"
        self.user_id = "demo_user"
        self.engine = UniversalScreenshotEngine(self.task_id, self.user_id)
        
        # 测试URL列表
        self.test_urls = [
            "https://httpbin.org/html",
            "https://example.com",
            "https://httpbin.org/json",
            "https://httpbin.org/status/200"
        ]
    
    async def test_basic_screenshot(self):
        """测试基本截图功能"""
        print("=== 测试基本截图功能 ===")
        
        # 创建配置
        config = ScreenshotConfig(
            width=1280,
            height=800,
            full_page=False,
            quality=95,
            timeout=30,
            wait_time=2.0
        )
        
        # 初始化引擎
        await self.engine.initialize(config)
        
        # 单个截图测试
        test_url = "https://example.com"
        print(f"截图URL: {test_url}")
        
        start_time = time.time()
        result = await self.engine.capture_screenshot(
            test_url, 
            config, 
            "demo_screenshot.png"
        )
        
        duration = time.time() - start_time
        
        if result.success:
            print(f"✅ 截图成功!")
            print(f"   文件路径: {result.screenshot_path}")
            print(f"   文件大小: {result.file_size} bytes")
            print(f"   响应时间: {result.response_time:.2f} 秒")
            print(f"   页面标题: {result.page_title}")
            print(f"   最终URL: {result.page_url}")
            print(f"   状态码: {result.status_code}")
        else:
            print(f"❌ 截图失败: {result.error_message}")
        
        print(f"总耗时: {duration:.2f} 秒\\n")
        return result
    
    async def test_batch_screenshot(self):
        """测试批量截图功能"""
        print("=== 测试批量截图功能 ===")
        
        # 创建配置
        config = ScreenshotConfig(
            width=1920,
            height=1080,
            full_page=True,
            quality=85,
            timeout=20,
            wait_time=1.0,
            retry_count=2
        )
        
        # 创建输出目录
        output_dir = "demo_screenshots"
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"批量截图 {len(self.test_urls)} 个URL")
        print(f"输出目录: {output_dir}")
        
        start_time = time.time()
        batch_result = await self.engine.batch_screenshot(
            self.test_urls,
            config,
            output_dir,
            max_concurrent=3
        )
        
        duration = time.time() - start_time
        
        print(f"\\n批量截图结果:")
        print(f"   总URL数: {batch_result.total_urls}")
        print(f"   成功截图: {batch_result.successful_screenshots}")
        print(f"   失败截图: {batch_result.failed_screenshots}")
        print(f"   总耗时: {batch_result.total_duration:.2f} 秒")
        print(f"   平均响应时间: {batch_result.average_response_time:.2f} 秒")
        
        if batch_result.error_summary:
            print(f"   错误统计: {batch_result.error_summary}")
        
        # 显示详细结果
        print(f"\\n详细结果:")
        for i, result in enumerate(batch_result.results, 1):
            status = "✅" if result.success else "❌"
            print(f"   {i}. {status} {result.url}")
            if result.success:
                print(f"      文件: {result.screenshot_path}")
                print(f"      大小: {result.file_size} bytes")
            else:
                print(f"      错误: {result.error_message}")
        
        print(f"\\n总耗时: {duration:.2f} 秒\\n")
        return batch_result
    
    async def test_different_configs(self):
        """测试不同配置选项"""
        print("=== 测试不同配置选项 ===")
        
        test_url = "https://httpbin.org/html"
        configs = [
            {
                'name': '标准配置',
                'config': ScreenshotConfig(width=1280, height=800, full_page=False)
            },
            {
                'name': '全屏截图',
                'config': ScreenshotConfig(width=1920, height=1080, full_page=True)
            },
            {
                'name': '移动端视图',
                'config': ScreenshotConfig(width=375, height=667, full_page=False)
            },
            {
                'name': '高质量JPEG',
                'config': ScreenshotConfig(
                    width=1280, height=800, 
                    format='jpeg', quality=100
                )
            }
        ]
        
        for i, config_test in enumerate(configs, 1):
            print(f"测试配置 {i}: {config_test['name']}")
            
            filename = f"demo_config_{i}.{config_test['config'].format}"
            result = await self.engine.capture_screenshot(
                test_url,
                config_test['config'],
                filename
            )
            
            if result.success:
                print(f"   ✅ 成功 - 文件: {filename}, 大小: {result.file_size} bytes")
            else:
                print(f"   ❌ 失败 - {result.error_message}")
        
        print()
    
    async def test_error_handling(self):
        """测试错误处理"""
        print("=== 测试错误处理 ===")
        
        config = ScreenshotConfig(timeout=5, retry_count=2)
        
        # 测试无效URL
        invalid_urls = [
            "https://nonexistent-domain-12345.com",
            "http://localhost:99999",
            "https://httpbin.org/status/404",
            "https://httpbin.org/delay/10"  # 超时测试
        ]
        
        for url in invalid_urls:
            print(f"测试URL: {url}")
            result = await self.engine.capture_screenshot(url, config)
            
            if result.success:
                print(f"   ✅ 意外成功")
            else:
                print(f"   ❌ 预期失败: {result.error_message}")
                print(f"   重试次数: {result.retry_count}")
        
        print()
    
    async def performance_benchmark(self):
        """性能基准测试"""
        print("=== 性能基准测试 ===")
        
        config = ScreenshotConfig(
            width=1280,
            height=800,
            timeout=15,
            wait_time=1.0
        )
        
        # 准备测试数据
        benchmark_urls = [
            "https://httpbin.org/html",
            "https://example.com",
            "https://httpbin.org/json"
        ] * 3  # 重复3次进行9个截图
        
        print(f"基准测试: {len(benchmark_urls)} 个截图")
        
        # 顺序执行测试
        print("\\n顺序执行:")
        start_time = time.time()
        sequential_results = []
        for url in benchmark_urls:
            result = await self.engine.capture_screenshot(url, config)
            sequential_results.append(result)
        sequential_time = time.time() - start_time
        sequential_success = len([r for r in sequential_results if r.success])
        
        print(f"   耗时: {sequential_time:.2f} 秒")
        print(f"   成功: {sequential_success}/{len(benchmark_urls)}")
        print(f"   平均: {sequential_time/len(benchmark_urls):.2f} 秒/截图")
        
        # 并发执行测试
        print("\\n并发执行 (3个并发):")
        start_time = time.time()
        batch_result = await self.engine.batch_screenshot(
            benchmark_urls,
            config,
            "benchmark_screenshots",
            max_concurrent=3
        )
        concurrent_time = time.time() - start_time
        
        print(f"   耗时: {concurrent_time:.2f} 秒")
        print(f"   成功: {batch_result.successful_screenshots}/{batch_result.total_urls}")
        print(f"   平均: {concurrent_time/len(benchmark_urls):.2f} 秒/截图")
        print(f"   提速: {sequential_time/concurrent_time:.2f}x")
        
        print()
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 截图引擎演示开始\\n")
        
        # 显示引擎信息
        engine_info = self.engine.get_engine_info()
        print(f"引擎信息: {engine_info}\\n")
        
        try:
            # 运行各项测试
            await self.test_basic_screenshot()
            await self.test_batch_screenshot()
            await self.test_different_configs()
            await self.test_error_handling()
            await self.performance_benchmark()
            
            print("✅ 所有测试完成!")
            
        except Exception as e:
            print(f"❌ 测试过程中出现异常: {e}")
        
        finally:
            # 清理资源
            await self.engine.cleanup()
            print("🧹 资源清理完成")


async def main():
    """主函数"""
    demo = ScreenshotEngineDemo()
    await demo.run_all_tests()


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())
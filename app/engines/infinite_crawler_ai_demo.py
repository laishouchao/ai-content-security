"""
无限迭代爬虫AI分析演示
展示如何使用AI分析引擎进行域名内容分析

功能演示：
1. AI分析引擎配置和初始化
2. 单个域名内容分析
3. 批量域名分析
4. 结果处理和统计
"""

import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.engines.infinite_crawler_ai_engine import (
    InfiniteCrawlerAIEngine,
    AIAnalysisConfig,
    DomainAnalysisRequest,
    AIAnalysisResult,
    create_ai_analysis_config_from_env,
    create_domain_analysis_request
)
from app.core.logging import TaskLogger


class InfiniteCrawlerAIDemo:
    """无限迭代爬虫AI分析演示类"""
    
    def __init__(self):
        self.task_id = "ai_demo_task"
        self.user_id = "demo_user"
        self.logger = TaskLogger(self.task_id, self.user_id)
        self.ai_engine: Optional[InfiniteCrawlerAIEngine] = None
    
    async def demo_ai_config_setup(self):
        """演示AI配置设置"""
        print("=== AI配置设置演示 ===")
        
        # 方法1: 从环境变量创建配置
        config = await create_ai_analysis_config_from_env()
        if config:
            print("✅ 从环境变量成功创建AI配置")
            print(f"   模型: {config.model}")
            print(f"   最大token: {config.max_tokens}")
            print(f"   温度: {config.temperature}")
            print(f"   并发限制: {config.max_concurrent}")
            return config
        
        # 方法2: 手动创建配置（示例）
        print("⚠️ 环境变量配置不可用，使用示例配置")
        config = AIAnalysisConfig(
            api_key="your-openai-api-key-here",
            base_url="https://api.openai.com/v1",
            model="gpt-4-vision-preview",
            max_tokens=1500,
            temperature=0.3,
            timeout=60,
            max_retries=3,
            max_concurrent=5
        )
        
        print("📝 请设置以下环境变量来使用真实的AI功能:")
        print("   OPENAI_API_KEY=your_api_key")
        print("   OPENAI_MODEL=gpt-4-vision-preview")
        print("   OPENAI_BASE_URL=https://api.openai.com/v1")
        
        return config
    
    async def demo_single_domain_analysis(self):
        """演示单个域名分析"""
        print("\\n=== 单个域名分析演示 ===")
        
        # 创建测试域名分析请求
        request = create_domain_analysis_request(
            domain="cdn.example.com",
            page_title="Example CDN Service",
            page_content="This is a content delivery network service providing fast content distribution globally. Our CDN ensures low latency and high availability for your web assets.",
            source_urls=["https://main.example.com", "https://www.example.com"],
        )
        
        print(f"分析域名: {request.domain}")
        print(f"页面标题: {request.page_title}")
        print(f"来源URL: {request.source_urls}")
        
        if not self.ai_engine:
            print("❌ AI引擎未初始化，跳过实际分析")
            return self._create_mock_analysis_result(request.domain)
        
        try:
            # 执行AI分析
            results = await self.ai_engine.analyze_domains_batch([request])
            if results:
                result = results[0]
                self._display_analysis_result(result)
                return result
            else:
                print("❌ AI分析返回空结果")
                return None
        except Exception as e:
            print(f"❌ AI分析失败: {e}")
            return None
    
    async def demo_batch_domain_analysis(self):
        """演示批量域名分析"""
        print("\\n=== 批量域名分析演示 ===")
        
        # 创建多个测试域名分析请求
        test_domains = [
            {
                "domain": "analytics.google.com",
                "title": "Google Analytics",
                "content": "Google Analytics helps you understand your customers across devices and platforms.",
                "source_urls": ["https://example.com"]
            },
            {
                "domain": "connect.facebook.net", 
                "title": "Facebook Connect",
                "content": "Facebook Connect allows users to connect their Facebook identity with your website.",
                "source_urls": ["https://example.com"]
            },
            {
                "domain": "js.stripe.com",
                "title": "Stripe JavaScript Library",
                "content": "Stripe.js is a JavaScript library for building payment flows.",
                "source_urls": ["https://example.com/checkout"]
            },
            {
                "domain": "suspicious-ads.example",
                "title": "Suspicious Ad Network",
                "content": "Click here for amazing deals! Free money! Adult content! Gambling opportunities!",
                "source_urls": ["https://example.com"]
            }
        ]
        
        # 创建分析请求
        requests = []
        for domain_data in test_domains:
            request = create_domain_analysis_request(
                domain=domain_data["domain"],
                page_title=domain_data["title"],
                page_content=domain_data["content"],
                source_urls=domain_data["source_urls"]
            )
            requests.append(request)
        
        print(f"准备分析 {len(requests)} 个域名:")
        for req in requests:
            print(f"  - {req.domain}")
        
        if not self.ai_engine:
            print("❌ AI引擎未初始化，生成模拟结果")
            results = [self._create_mock_analysis_result(req.domain) for req in requests]
        else:
            try:
                # 执行批量AI分析
                results = await self.ai_engine.analyze_domains_batch(requests)
            except Exception as e:
                print(f"❌ 批量AI分析失败: {e}")
                results = []
        
        # 显示结果
        print(f"\\n批量分析完成，共 {len(results)} 个结果:")
        for result in results:
            self._display_analysis_result(result, brief=True)
        
        return results
    
    async def demo_ai_statistics(self):
        """演示AI分析统计信息"""
        print("\\n=== AI分析统计信息演示 ===")
        
        if not self.ai_engine:
            print("❌ AI引擎未初始化，显示模拟统计")
            stats = {
                'total_requests': 4,
                'successful_requests': 4,
                'failed_requests': 0,
                'cache_hits': 0,
                'cache_misses': 4,
                'api_calls_made': 4,
                'tokens_used': 6000,
                'average_processing_time': 2.5,
                'success_rate': 1.0,
                'cache_hit_rate': 0.0
            }
        else:
            stats = self.ai_engine.get_analysis_statistics()
        
        print("📊 AI分析统计信息:")
        print(f"   总请求数: {stats.get('total_requests', 0)}")
        print(f"   成功请求: {stats.get('successful_requests', 0)}")
        print(f"   失败请求: {stats.get('failed_requests', 0)}")
        print(f"   成功率: {stats.get('success_rate', 0):.2%}")
        print(f"   缓存命中率: {stats.get('cache_hit_rate', 0):.2%}")
        print(f"   API调用次数: {stats.get('api_calls_made', 0)}")
        print(f"   使用Token数: {stats.get('tokens_used', 0)}")
        print(f"   平均处理时间: {stats.get('average_processing_time', 0):.2f}秒")
        
        return stats
    
    def _create_mock_analysis_result(self, domain: str) -> AIAnalysisResult:
        """创建模拟的AI分析结果"""
        # 简单的域名分类逻辑
        if "google" in domain or "analytics" in domain:
            category = "analytics"
            risk = "low"
        elif "facebook" in domain or "social" in domain:
            category = "social"
            risk = "medium"
        elif "stripe" in domain or "payment" in domain:
            category = "payment"
            risk = "low"
        elif "suspicious" in domain or "ads" in domain:
            category = "advertising"
            risk = "high"
        else:
            category = "unknown"
            risk = "medium"
        
        return AIAnalysisResult(
            domain=domain,
            analysis_success=True,
            analysis_timestamp=datetime.utcnow(),
            processing_time=2.0,
            domain_category=category,
            risk_level=risk,
            confidence_score=0.85,
            content_type="service",
            has_violations=risk in ["high", "critical"],
            violation_types=["suspicious_content"] if risk == "high" else [],
            violation_details="检测到可疑广告内容" if risk == "high" else "",
            ai_raw_response='{"domain_category": "' + category + '", "risk_level": "' + risk + '"}',
            analysis_prompt_used="模拟分析提示词"
        )
    
    def _display_analysis_result(self, result: AIAnalysisResult, brief: bool = False):
        """显示AI分析结果"""
        status = "✅" if result.analysis_success else "❌"
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🟠",
            "critical": "🔴"
        }.get(result.risk_level, "⚪")
        
        if brief:
            print(f"  {status} {result.domain} - {risk_emoji} {result.risk_level} - {result.domain_category}")
            if result.has_violations:
                print(f"    ⚠️ 违规: {', '.join(result.violation_types)}")
        else:
            print(f"\\n{status} 域名分析结果: {result.domain}")
            print(f"   分析状态: {'成功' if result.analysis_success else '失败'}")
            print(f"   域名分类: {result.domain_category}")
            print(f"   风险等级: {risk_emoji} {result.risk_level}")
            print(f"   置信度: {result.confidence_score:.2f}")
            print(f"   内容类型: {result.content_type}")
            print(f"   处理时间: {result.processing_time:.2f}秒")
            
            if result.has_violations:
                print(f"   ⚠️ 发现违规:")
                print(f"     类型: {', '.join(result.violation_types)}")
                print(f"     详情: {result.violation_details}")
            
            if result.error_message:
                print(f"   ❌ 错误信息: {result.error_message}")
    
    async def run_full_demo(self):
        """运行完整演示"""
        print("🚀 无限迭代爬虫AI分析引擎演示")
        print("=" * 50)
        
        try:
            # 1. 配置设置
            config = await self.demo_ai_config_setup()
            
            # 2. 初始化AI引擎（如果配置有效）
            if config and config.api_key != "your-openai-api-key-here":
                try:
                    self.ai_engine = InfiniteCrawlerAIEngine(
                        self.task_id, 
                        self.user_id, 
                        config
                    )
                    await self.ai_engine.initialize()
                    print("✅ AI引擎初始化成功")
                except Exception as e:
                    print(f"⚠️ AI引擎初始化失败: {e}")
                    self.ai_engine = None
            
            # 3. 单个域名分析
            await self.demo_single_domain_analysis()
            
            # 4. 批量域名分析
            await self.demo_batch_domain_analysis()
            
            # 5. 统计信息
            await self.demo_ai_statistics()
            
            print("\\n✅ 演示完成!")
            
        except Exception as e:
            print(f"❌ 演示过程中出现异常: {e}")
        
        finally:
            # 清理资源
            if self.ai_engine:
                await self.ai_engine.cleanup()
                print("🧹 AI引擎资源清理完成")


async def main():
    """主函数"""
    demo = InfiniteCrawlerAIDemo()
    await demo.run_full_demo()


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())
"""
高级AI提示词系统演示
展示如何使用高级提示词系统进行专业的AI分析

功能演示：
1. 不同分析类型的提示词生成
2. 提示词优化和性能监控
3. 缓存机制和性能统计
4. 上下文感知的提示词构建
"""

import asyncio
import time
from typing import List, Dict, Any

from app.engines.advanced_prompt_system import (
    EnhancedPromptManager,
    AnalysisType,
    PromptContext,
    create_prompt_context
)


class AdvancedPromptDemo:
    """高级提示词系统演示类"""
    
    def __init__(self):
        self.task_id = "prompt_demo_task"
        self.user_id = "demo_user"
        self.prompt_manager = EnhancedPromptManager(self.task_id, self.user_id)
    
    def create_test_contexts(self) -> List[PromptContext]:
        """创建测试上下文"""
        return [
            create_prompt_context(
                domain="cdn.cloudflare.com",
                page_title="Cloudflare CDN Service",
                page_content="Cloudflare provides a global content delivery network that accelerates and secures websites. Our CDN ensures fast load times and protection against DDoS attacks.",
                source_urls=["https://example.com"],
                discovery_method="dns_query"
            ),
            create_prompt_context(
                domain="analytics.google.com", 
                page_title="Google Analytics",
                page_content="Google Analytics helps you understand your customers across devices and platforms. Track user behavior, measure conversion rates, and optimize your marketing.",
                source_urls=["https://example.com/analytics"],
                discovery_method="content_extraction"
            ),
            create_prompt_context(
                domain="suspicious-ads.example",
                page_title="Amazing Deals - Click Now!",
                page_content="Free money! Adult content! Gambling opportunities! Click here for amazing deals that seem too good to be true. Limited time offer!",
                source_urls=["https://example.com"],
                discovery_method="link_crawling"
            ),
            create_prompt_context(
                domain="payment.stripe.com",
                page_title="Stripe Payment Processing",
                page_content="Stripe is a payment infrastructure for the internet. Accept payments online and in person. Built for developers, trusted by businesses worldwide.",
                source_urls=["https://example.com/checkout"],
                discovery_method="third_party_integration"
            )
        ]
    
    async def demo_different_analysis_types(self):
        """演示不同分析类型的提示词生成"""
        print("=== 不同分析类型演示 ===")
        
        test_context = create_prompt_context(
            domain="social.example.com",
            page_title="Social Media Platform",
            page_content="Connect with friends and share your life moments. Join millions of users worldwide in our social community.",
            source_urls=["https://main.example.com"],
            discovery_method="subdomain_discovery"
        )
        
        analysis_types = [
            (AnalysisType.DOMAIN_CLASSIFICATION, "域名分类分析"),
            (AnalysisType.SECURITY_ASSESSMENT, "安全风险评估"),
            (AnalysisType.CONTENT_ANALYSIS, "内容分析"),
            (AnalysisType.COMPREHENSIVE, "综合分析")
        ]
        
        for analysis_type, description in analysis_types:
            print(f"\\n--- {description} ---")
            
            prompt_result = await self.prompt_manager.generate_analysis_prompt(
                test_context,
                analysis_type
            )
            
            print(f"模板使用: {prompt_result.template_used}")
            print(f"估算Token数: {prompt_result.estimated_tokens}")
            print(f"系统提示词长度: {len(prompt_result.system_prompt)} 字符")
            print(f"用户提示词长度: {len(prompt_result.user_prompt)} 字符")
            
            # 显示系统提示词的前100个字符
            system_preview = prompt_result.system_prompt[:100] + "..." if len(prompt_result.system_prompt) > 100 else prompt_result.system_prompt
            print(f"系统提示词预览: {system_preview}")
    
    async def demo_context_variations(self):
        """演示不同上下文的提示词变化"""
        print("\\n=== 上下文变化演示 ===")
        
        base_domain = "api.example.com"
        
        contexts = [
            {
                "name": "基础信息",
                "context": create_prompt_context(
                    domain=base_domain,
                    discovery_method="dns_query"
                )
            },
            {
                "name": "包含页面信息",
                "context": create_prompt_context(
                    domain=base_domain,
                    page_title="API Service",
                    page_content="RESTful API for developers",
                    discovery_method="dns_query"
                )
            },
            {
                "name": "包含内容和截图",
                "context": create_prompt_context(
                    domain=base_domain,
                    page_title="API Service",
                    page_content="Our API provides endpoints for user management, data processing, and analytics. Rate limits apply.",
                    screenshot_path="/fake/path/screenshot.png",
                    source_urls=["https://docs.example.com"],
                    discovery_method="api_documentation"
                )
            }
        ]
        
        for context_info in contexts:
            print(f"\\n--- {context_info['name']} ---")
            
            prompt_result = await self.prompt_manager.generate_analysis_prompt(
                context_info['context'],
                AnalysisType.COMPREHENSIVE
            )
            
            print(f"提示词总长度: {len(prompt_result.user_prompt)} 字符")
            print(f"估算Token数: {prompt_result.estimated_tokens}")
            
            # 显示用户提示词的关键部分
            lines = prompt_result.user_prompt.split('\\n')
            relevant_lines = [line for line in lines if line.strip() and not line.startswith('{')][:5]
            print("关键信息:")
            for line in relevant_lines:
                print(f"  {line.strip()}")
    
    async def demo_performance_and_caching(self):
        """演示性能监控和缓存功能"""
        print("\\n=== 性能和缓存演示 ===")
        
        test_contexts = self.create_test_contexts()
        
        # 第一轮：生成提示词（无缓存）
        print("第一轮生成（无缓存）:")
        first_round_times = []
        
        for i, context in enumerate(test_contexts):
            start_time = time.time()
            
            prompt_result = await self.prompt_manager.generate_analysis_prompt(
                context,
                AnalysisType.COMPREHENSIVE
            )
            
            generation_time = time.time() - start_time
            first_round_times.append(generation_time)
            
            print(f"  域名 {i+1}: {generation_time*1000:.2f}ms")
        
        # 获取性能指标
        metrics = self.prompt_manager.get_performance_metrics()
        print(f"\\n第一轮统计:")
        print(f"  总提示词数: {metrics['total_prompts']}")
        print(f"  缓存命中率: {metrics['cache_hit_rate']:.2%}")
        print(f"  平均生成时间: {metrics['average_generation_time']*1000:.2f}ms")
        
        # 第二轮：相同上下文（测试缓存）
        print("\\n第二轮生成（测试缓存）:")
        second_round_times = []
        
        for i, context in enumerate(test_contexts):
            start_time = time.time()
            
            prompt_result = await self.prompt_manager.generate_analysis_prompt(
                context,
                AnalysisType.COMPREHENSIVE
            )
            
            generation_time = time.time() - start_time
            second_round_times.append(generation_time)
            
            print(f"  域名 {i+1}: {generation_time*1000:.2f}ms")
        
        # 最终性能指标
        final_metrics = self.prompt_manager.get_performance_metrics()
        print(f"\\n最终统计:")
        print(f"  总提示词数: {final_metrics['total_prompts']}")
        print(f"  缓存命中率: {final_metrics['cache_hit_rate']:.2%}")
        print(f"  平均生成时间: {final_metrics['average_generation_time']*1000:.2f}ms")
        print(f"  性能评分: {final_metrics['performance_score']:.1f}/100")
        
        # 计算性能提升
        avg_first = sum(first_round_times) / len(first_round_times)
        avg_second = sum(second_round_times) / len(second_round_times)
        improvement = (avg_first - avg_second) / avg_first * 100
        
        print(f"\\n性能提升:")
        print(f"  第一轮平均: {avg_first*1000:.2f}ms")
        print(f"  第二轮平均: {avg_second*1000:.2f}ms")
        print(f"  提升幅度: {improvement:.1f}%")
    
    async def demo_custom_instructions(self):
        """演示自定义指令功能"""
        print("\\n=== 自定义指令演示 ===")
        
        test_context = create_prompt_context(
            domain="ecommerce.example.com",
            page_title="Online Shopping Platform",
            page_content="Buy and sell products online. Secure payments, fast shipping, customer reviews.",
            source_urls=["https://example.com"],
            discovery_method="business_analysis"
        )
        
        custom_instructions = [
            None,
            "重点关注数据隐私和用户信息保护",
            "从电商合规角度进行分析，特别关注支付安全",
            "分析该平台的商业模式和盈利方式"
        ]
        
        for i, instruction in enumerate(custom_instructions):
            print(f"\\n--- 指令 {i+1}: {instruction or '无自定义指令'} ---")
            
            prompt_result = await self.prompt_manager.generate_analysis_prompt(
                test_context,
                AnalysisType.COMPREHENSIVE,
                instruction
            )
            
            print(f"提示词长度: {len(prompt_result.user_prompt)} 字符")
            
            # 查找自定义指令在提示词中的体现
            if instruction and instruction in prompt_result.user_prompt:
                print("✅ 自定义指令已成功集成到提示词中")
            elif instruction:
                print("⚠️ 自定义指令未明确出现在提示词中")
            else:
                print("📝 使用默认分析指导")
    
    async def demo_prompt_optimization(self):
        """演示提示词优化功能"""
        print("\\n=== 提示词优化演示 ===")
        
        # 创建一个内容很长的上下文来触发优化
        long_content = "这是一个很长的页面内容。" * 200  # 创建长内容
        
        test_context = create_prompt_context(
            domain="content-heavy.example.com",
            page_title="Content Heavy Website with Very Long Title That Contains Lots of Information",
            page_content=long_content,
            source_urls=[f"https://example.com/page{i}" for i in range(10)],  # 多个源URL
            discovery_method="comprehensive_crawling"
        )
        
        print("原始上下文信息:")
        print(f"  页面标题长度: {len(test_context.page_title or '')} 字符")
        print(f"  页面内容长度: {len(test_context.content_snippet or '')} 字符")
        print(f"  源URL数量: {len(test_context.source_urls)}")
        
        prompt_result = await self.prompt_manager.generate_analysis_prompt(
            test_context,
            AnalysisType.COMPREHENSIVE
        )
        
        print(f"\\n优化后的提示词:")
        print(f"  总长度: {len(prompt_result.user_prompt)} 字符")
        print(f"  估算Token数: {prompt_result.estimated_tokens}")
        
        # 检查优化效果
        optimized_content = prompt_result.user_prompt
        if "..." in optimized_content:
            print("✅ 检测到内容截断优化")
        
        if len(test_context.source_urls) > 3 and optimized_content.count("https://") < len(test_context.source_urls):
            print("✅ 检测到URL列表优化")
    
    async def run_full_demo(self):
        """运行完整演示"""
        print("🚀 高级AI提示词系统演示")
        print("=" * 50)
        
        try:
            # 1. 不同分析类型演示
            await self.demo_different_analysis_types()
            
            # 2. 上下文变化演示
            await self.demo_context_variations()
            
            # 3. 性能和缓存演示
            await self.demo_performance_and_caching()
            
            # 4. 自定义指令演示
            await self.demo_custom_instructions()
            
            # 5. 提示词优化演示
            await self.demo_prompt_optimization()
            
            print("\\n✅ 演示完成!")
            
        except Exception as e:
            print(f"❌ 演示过程中出现异常: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """主函数"""
    demo = AdvancedPromptDemo()
    await demo.run_full_demo()


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())
#!/usr/bin/env python3
"""
性能优化验证测试脚本

测试并行执行器与传统执行器的性能对比
验证智能AI预筛选的效果
"""

import asyncio
import time
import json
from typing import Dict, Any, List
from datetime import datetime
import uuid

from app.engines.parallel_scan_executor import ParallelScanExecutor
from app.engines.scan_executor import ScanTaskExecutor
from app.core.logging import TaskLogger


# 测试域名列表
TEST_DOMAINS = [
    'example.com',
    'httpbin.org',
    'jsonplaceholder.typicode.com'
]

# 测试配置
TEST_CONFIGS = {
    'traditional': {
        'use_parallel_executor': False,
        'smart_prefilter_enabled': False,
        'dns_concurrency': 50,
        'max_subdomains': 50,
        'max_crawl_depth': 2,
        'max_pages_per_domain': 100,
        'request_delay': 1000,
        'timeout': 30
    },
    'parallel_basic': {
        'use_parallel_executor': True,
        'smart_prefilter_enabled': False,
        'dns_concurrency': 100,
        'max_subdomains': 50,
        'max_crawl_depth': 2,
        'max_pages_per_domain': 100,
        'request_delay': 500,
        'timeout': 30
    },
    'parallel_optimized': {
        'use_parallel_executor': True,
        'smart_prefilter_enabled': True,
        'dns_concurrency': 100,
        'ai_skip_threshold': 0.3,
        'max_subdomains': 50,
        'max_crawl_depth': 2,
        'max_pages_per_domain': 100,
        'request_delay': 500,
        'timeout': 30,
        'multi_viewport_capture': False,
        'enable_aggressive_caching': True
    },
    'high_performance': {
        'use_parallel_executor': True,
        'smart_prefilter_enabled': True,
        'dns_concurrency': 150,
        'ai_skip_threshold': 0.2,
        'max_subdomains': 100,
        'max_crawl_depth': 3,
        'max_pages_per_domain': 200,
        'request_delay': 200,
        'timeout': 30,
        'multi_viewport_capture': True,
        'enable_aggressive_caching': True
    }
}


class PerformanceTester:
    """性能测试器"""
    
    def __init__(self):
        self.results = {}
        self.test_start_time = None
        self.test_end_time = None
    
    async def run_performance_tests(self) -> Dict[str, Any]:
        """运行性能测试套件"""
        print("🚀 开始性能优化验证测试")
        self.test_start_time = time.time()
        
        # 测试所有配置
        for config_name, config in TEST_CONFIGS.items():
            print(f"\n📊 测试配置: {config_name}")
            config_results = []
            
            for domain in TEST_DOMAINS:
                print(f"   测试域名: {domain}")
                
                try:
                    result = await self._test_single_domain(domain, config, config_name)
                    config_results.append(result)
                    print(f"   ✅ 完成 - 耗时: {result['execution_time']:.2f}s")
                    
                except Exception as e:
                    print(f"   ❌ 失败: {e}")
                    config_results.append({
                        'domain': domain,
                        'error': str(e),
                        'execution_time': 0
                    })
            
            self.results[config_name] = config_results
        
        self.test_end_time = time.time()
        
        # 生成报告
        report = self._generate_performance_report()
        
        # 保存报告
        await self._save_test_report(report)
        
        return report
    
    async def _test_single_domain(self, domain: str, config: Dict[str, Any], config_name: str) -> Dict[str, Any]:
        """测试单个域名"""
        task_id = str(uuid.uuid4())
        user_id = "test_user"
        
        start_time = time.time()
        
        # 选择执行器
        if config.get('use_parallel_executor', False):
            executor = ParallelScanExecutor(task_id, user_id)
            result = await executor.execute_scan(domain, config)
            
            # 提取性能指标
            results_data = result.get('results', {})
            ai_calls_made = 0
            ai_calls_skipped = 0
            
            # 从事件中统计AI调用
            events = result.get('events', [])
            for event in events:
                if event.get('event_type') == 'ai_analysis_skipped':
                    ai_calls_skipped += 1
                elif event.get('event_type') == 'domain_analyzed':
                    ai_calls_made += 1
            
        else:
            # 传统执行器（简化测试）
            executor = ScanTaskExecutor(task_id, user_id)
            result = await executor.execute_scan(domain, config)
            
            results_data = {
                'subdomains': getattr(result, 'subdomains', []),
                'third_party_domains': getattr(result, 'third_party_domains', []),
                'statistics': getattr(result, 'statistics', {})
            }
            ai_calls_made = results_data['statistics'].get('ai_analysis_completed', 0)
            ai_calls_skipped = 0
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 返回性能指标
        return {
            'domain': domain,
            'config_name': config_name,
            'execution_time': execution_time,
            'subdomains_found': len(results_data.get('subdomains', [])),
            'third_party_domains': len(results_data.get('third_party_domains', [])),
            'ai_calls_made': ai_calls_made,
            'ai_calls_skipped': ai_calls_skipped,
            'ai_skip_rate': (ai_calls_skipped / (ai_calls_made + ai_calls_skipped) * 100) if (ai_calls_made + ai_calls_skipped) > 0 else 0,
            'executor_type': 'parallel' if config.get('use_parallel_executor') else 'traditional',
            'smart_prefilter_enabled': config.get('smart_prefilter_enabled', False)
        }
    
    def _generate_performance_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        report = {
            'test_summary': {
                'start_time': datetime.fromtimestamp(self.test_start_time or time.time()).isoformat(),
                'end_time': datetime.fromtimestamp(self.test_end_time or time.time()).isoformat(),
                'total_duration': (self.test_end_time or 0) - (self.test_start_time or 0),
                'configs_tested': len(TEST_CONFIGS),
                'domains_tested': len(TEST_DOMAINS)
            },
            'detailed_results': self.results,
            'performance_comparison': self._calculate_performance_comparison(),
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _calculate_performance_comparison(self) -> Dict[str, Any]:
        """计算性能对比"""
        comparison = {}
        
        # 计算每个配置的平均性能
        for config_name, results in self.results.items():
            if not results:
                continue
            
            valid_results = [r for r in results if 'error' not in r]
            if not valid_results:
                continue
            
            avg_execution_time = sum(r['execution_time'] for r in valid_results) / len(valid_results)
            total_subdomains = sum(r['subdomains_found'] for r in valid_results)
            total_ai_calls = sum(r['ai_calls_made'] for r in valid_results)
            total_ai_skipped = sum(r['ai_calls_skipped'] for r in valid_results)
            
            comparison[config_name] = {
                'avg_execution_time': avg_execution_time,
                'total_subdomains': total_subdomains,
                'total_ai_calls': total_ai_calls,
                'total_ai_skipped': total_ai_skipped,
                'ai_skip_rate': (total_ai_skipped / (total_ai_calls + total_ai_skipped) * 100) if (total_ai_calls + total_ai_skipped) > 0 else 0,
                'efficiency_score': total_subdomains / avg_execution_time if avg_execution_time > 0 else 0
            }
        
        # 计算性能提升倍数
        if 'traditional' in comparison and 'parallel_optimized' in comparison:
            traditional_time = comparison['traditional']['avg_execution_time']
            optimized_time = comparison['parallel_optimized']['avg_execution_time']
            
            if optimized_time > 0:
                speedup = traditional_time / optimized_time
                comparison['performance_improvement'] = {
                    'speedup_factor': speedup,
                    'time_reduction_percentage': ((traditional_time - optimized_time) / traditional_time) * 100,
                    'ai_cost_reduction': comparison['parallel_optimized']['ai_skip_rate']
                }
        
        return comparison
    
    def _generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        comparison = self._calculate_performance_comparison()
        
        if 'performance_improvement' in comparison:
            improvement = comparison['performance_improvement']
            
            if improvement['speedup_factor'] > 2:
                recommendations.append(f"🚀 并行执行器显著提升性能 {improvement['speedup_factor']:.1f}x，强烈推荐启用")
            
            if improvement['ai_cost_reduction'] > 50:
                recommendations.append(f"💰 智能AI预筛选节省 {improvement['ai_cost_reduction']:.1f}% 成本，建议启用")
        
        # 根据测试结果生成具体建议
        if 'high_performance' in comparison:
            hp_score = comparison['high_performance']['efficiency_score']
            recommendations.append(f"⚡ 高性能配置效率评分: {hp_score:.2f}，适合大规模扫描")
        
        recommendations.extend([
            "📊 建议根据具体业务需求选择配置预设",
            "🔧 可根据服务器性能调整DNS并发数",
            "🎯 定期监控AI跳过率以平衡成本和准确性"
        ])
        
        return recommendations
    
    async def _save_test_report(self, report: Dict[str, Any]):
        """保存测试报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"performance_test_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"\n📋 测试报告已保存: {filename}")
            
            # 打印摘要
            self._print_test_summary(report)
            
        except Exception as e:
            print(f"❌ 保存报告失败: {e}")
    
    def _print_test_summary(self, report: Dict[str, Any]):
        """打印测试摘要"""
        print("\n" + "="*60)
        print("🎯 性能优化测试摘要")
        print("="*60)
        
        summary = report['test_summary']
        print(f"📅 测试时间: {summary['start_time']} ~ {summary['end_time']}")
        print(f"⏱️  总耗时: {summary['total_duration']:.2f}秒")
        print(f"🧪 测试配置: {summary['configs_tested']}个")
        print(f"🌐 测试域名: {summary['domains_tested']}个")
        
        comparison = report['performance_comparison']
        
        if 'performance_improvement' in comparison:
            improvement = comparison['performance_improvement']
            print(f"\n📈 性能提升:")
            print(f"   🚀 速度提升: {improvement['speedup_factor']:.1f}x")
            print(f"   ⏱️  时间减少: {improvement['time_reduction_percentage']:.1f}%")
            print(f"   💰 AI成本节省: {improvement['ai_cost_reduction']:.1f}%")
        
        print(f"\n💡 优化建议:")
        for rec in report['recommendations']:
            print(f"   {rec}")
        
        print("\n" + "="*60)


async def main():
    """主函数"""
    tester = PerformanceTester()
    
    try:
        report = await tester.run_performance_tests()
        print("\n✅ 性能测试完成!")
        return report
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
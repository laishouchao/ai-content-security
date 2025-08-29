#!/usr/bin/env python3
"""
测试循环域名发现引擎
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app.engines.domain_discovery_engine import ContinuousDomainDiscoveryEngine


async def test_continuous_discovery():
    """测试循环域名发现"""
    print("🧪 测试循环域名发现引擎")
    print("=" * 60)
    
    # 创建引擎实例
    engine = ContinuousDomainDiscoveryEngine(
        task_id="test_task_001",
        user_id="test_user",
        target_domain="sdyu.edu.cn"
    )
    
    # 配置
    config = {
        'max_discovery_rounds': 3,  # 限制测试轮次
        'max_pages_per_domain': 5,  # 限制每个域名的页面数
        'request_delay': 1000       # 请求间隔
    }
    
    print(f"📋 测试目标域名: {engine.target_domain}")
    print(f"🔧 测试配置: {config}")
    print()
    
    try:
        # 执行循环发现
        print("🚀 开始循环域名发现...")
        start_time = datetime.now()
        
        result = await engine.start_continuous_discovery(config)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("✅ 循环发现完成！")
        print(f"⏱️  总用时: {duration:.2f} 秒")
        print()
        
        # 打印结果
        print("📊 发现统计:")
        print(f"   - 总轮次: {result.get('total_rounds', 0)}")
        print(f"   - 发现域名总数: {result.get('total_domains', 0)}")
        print(f"   - 目标主域名: {result.get('target_main_count', 0)}")
        print(f"   - 目标子域名: {result.get('target_subdomain_count', 0)}")
        print(f"   - 第三方域名: {result.get('third_party_count', 0)}")
        print(f"   - 未知域名: {result.get('unknown_count', 0)}")
        print(f"   - 爬取页面总数: {result.get('total_pages_crawled', 0)}")
        print()
        
        # 打印轮次详情
        discovery_rounds = result.get('discovery_rounds', [])
        if discovery_rounds:
            print("🔄 轮次详情:")
            for round_info in discovery_rounds:
                print(f"   第{round_info['round']}轮: 爬取{round_info['domains_crawled']}个域名, "
                      f"发现{round_info['new_domains_found']}个新域名, "
                      f"爬取{round_info['pages_crawled']}个页面, "
                      f"用时{round_info['duration_seconds']:.1f}秒")
        
        print()
        print("🎉 测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_domain_classification():
    """测试域名分类逻辑"""
    print("\n🧪 测试域名分类逻辑")
    print("=" * 60)
    
    engine = ContinuousDomainDiscoveryEngine(
        task_id="test_task_002",
        user_id="test_user",
        target_domain="sdyu.edu.cn"
    )
    
    test_domains = [
        "sdyu.edu.cn",          # 目标主域名
        "www.sdyu.edu.cn",      # 目标子域名
        "bgs.sdyu.edu.cn",      # 目标子域名
        "webvpn.sdyu.edu.cn",   # 目标子域名
        "mail.sdyu.edu.cn",     # 目标子域名
        "www.coremail.cn",      # 第三方域名
        "google.com",           # 第三方域名
        "baidu.com",            # 第三方域名
    ]
    
    print("域名分类测试:")
    for domain in test_domains:
        category = engine._classify_domain(domain)
        print(f"   {domain:<25} -> {category}")
    
    print()


if __name__ == "__main__":
    asyncio.run(test_domain_classification())
    # asyncio.run(test_continuous_discovery())  # 注释掉完整测试，避免实际爬取
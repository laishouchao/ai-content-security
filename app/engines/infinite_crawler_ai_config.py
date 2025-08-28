"""
无限迭代爬虫AI分析配置示例
展示如何配置和使用AI分析功能

配置说明：
1. AI分析引擎配置
2. 爬虫任务配置
3. 第三方域名分析配置
4. 性能优化配置
"""

import os
from typing import Dict, Any
from app.engines.infinite_crawler_ai_engine import AIAnalysisConfig


# ===== AI分析配置 =====
def create_ai_analysis_config() -> AIAnalysisConfig:
    """创建AI分析配置"""
    return AIAnalysisConfig(
        # OpenAI API配置
        api_key=os.getenv('OPENAI_API_KEY', 'your-openai-api-key'),
        base_url=os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
        model=os.getenv('OPENAI_MODEL', 'gpt-4-vision-preview'),
        
        # 模型参数
        max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', '1500')),
        temperature=float(os.getenv('OPENAI_TEMPERATURE', '0.3')),
        timeout=int(os.getenv('OPENAI_TIMEOUT', '60')),
        max_retries=int(os.getenv('OPENAI_MAX_RETRIES', '3')),
        
        # 并发控制
        max_concurrent=int(os.getenv('AI_MAX_CONCURRENT', '5')),
        
        # 功能开关
        enable_screenshot_analysis=True,
        enable_content_analysis=True,
        enable_risk_assessment=True,
        enable_caching=True
    )


# ===== 爬虫任务配置 =====
def create_infinite_crawler_config() -> Dict[str, Any]:
    """创建无限迭代爬虫配置"""
    return {
        # ===== 基础配置 =====
        'task_name': 'infinite_domain_discovery',
        'target_domain': 'example.com',  # 目标域名
        
        # ===== 迭代控制配置 =====
        'max_iterations': 50,              # 最大迭代次数
        'max_domains_per_iteration': 200,  # 每次迭代处理的最大域名数
        'max_total_domains': 10000,        # 全局最大域名数限制
        
        # ===== 并发控制配置 =====
        'max_concurrent': 20,              # 最大并发数
        'max_concurrent_ai_calls': 5,      # AI分析最大并发数
        'timeout_per_page': 30,            # 每个页面超时时间
        'request_delay_range': [1.0, 3.0], # 请求延迟范围
        
        # ===== 子域名发现配置 =====
        'subdomain_discovery': {
            'enable_dns_query': True,
            'enable_certificate_transparency': True,
            'enable_search_engines': True,
            'enable_brute_force': True,
            'max_subdomains_per_method': 1000,
            'dns_timeout': 10,
            'brute_force_wordlist_size': 1000
        },
        
        # ===== 内容爬取配置 =====
        'content_crawling': {
            'max_pages_per_domain': 50,
            'enable_javascript': False,
            'follow_redirects': True,
            'max_redirect_count': 5,
            'content_size_limit': 1048576,  # 1MB
            'allowed_content_types': [
                'text/html',
                'application/xhtml+xml'
            ]
        },
        
        # ===== 截图配置 =====
        'screenshot': {
            'enable_screenshot': True,
            'screenshot_width': 1280,
            'screenshot_height': 720,
            'screenshot_quality': 85,
            'full_page_screenshot': False,
            'screenshot_timeout': 25
        },
        
        # ===== AI分析配置 =====
        'ai_analysis_enabled': True,        # 启用AI分析
        'content_capture_enabled': True,    # 启用内容抓取
        'ai_batch_size': 10,               # AI分析批次大小
        'ai_analysis_cache_ttl': 86400,    # AI分析结果缓存时间(秒)
        
        # ===== 第三方域名分析配置 =====
        'third_party_analysis': {
            'enable_risk_assessment': True,
            'enable_content_classification': True,
            'enable_violation_detection': True,
            'risk_threshold': 'medium',      # low, medium, high, critical
            'analyze_unknown_domains': True,
            'skip_common_services': False,   # 是否跳过常见服务(CDN等)
        },
        
        # ===== 性能优化配置 =====
        'performance': {
            'enable_adaptive_delay': True,
            'enable_queue_optimization': True,
            'enable_memory_monitoring': True,
            'memory_limit_mb': 2048,
            'cpu_limit_percent': 80,
            'disk_space_limit_gb': 10
        },
        
        # ===== 输出配置 =====
        'output': {
            'save_detailed_results': True,
            'save_statistics': True,
            'save_crawling_logs': True,
            'export_format': 'json',         # json, csv, txt
            'output_directory': 'results',
            'compress_output': True
        },
        
        # ===== 错误处理配置 =====
        'error_handling': {
            'max_retries': 3,
            'retry_delay': 2.0,
            'ignore_ssl_errors': True,
            'continue_on_error': True,
            'error_threshold': 0.5          # 错误率阈值
        }
    }


# ===== 高级配置 =====
def create_advanced_ai_config() -> Dict[str, Any]:
    """创建高级AI分析配置"""
    return {
        # ===== AI提示词配置 =====
        'ai_prompts': {
            'system_prompt_override': None,  # 自定义系统提示词
            'analysis_focus': [
                'security_risks',
                'content_classification',
                'business_purpose',
                'data_collection_practices'
            ],
            'language_preference': 'zh-CN',  # 分析结果语言
            'detail_level': 'comprehensive'  # basic, standard, comprehensive
        },
        
        # ===== 风险评估配置 =====
        'risk_assessment': {
            'enable_content_analysis': True,
            'enable_domain_reputation': True,
            'enable_ssl_analysis': True,
            'enable_behavioral_analysis': True,
            'risk_scoring_weights': {
                'content_risk': 0.4,
                'reputation_risk': 0.3,
                'technical_risk': 0.2,
                'behavioral_risk': 0.1
            }
        },
        
        # ===== 分类配置 =====
        'classification': {
            'enable_business_classification': True,
            'enable_technical_classification': True,
            'enable_geographic_classification': True,
            'classification_confidence_threshold': 0.7,
            'unknown_classification_handling': 'analyze'  # skip, analyze, flag
        },
        
        # ===== 监控和告警配置 =====
        'monitoring': {
            'enable_real_time_alerts': True,
            'alert_on_high_risk_domains': True,
            'alert_on_violations': True,
            'alert_on_api_errors': True,
            'notification_channels': ['email', 'webhook'],
            'alert_thresholds': {
                'high_risk_count': 10,
                'violation_rate': 0.1,
                'api_error_rate': 0.2
            }
        }
    }


# ===== 环境变量配置示例 =====
def setup_environment_variables():
    """设置环境变量的示例"""
    env_vars = {
        # OpenAI配置
        'OPENAI_API_KEY': 'your-openai-api-key-here',
        'OPENAI_BASE_URL': 'https://api.openai.com/v1',
        'OPENAI_MODEL': 'gpt-4-vision-preview',
        'OPENAI_MAX_TOKENS': '1500',
        'OPENAI_TEMPERATURE': '0.3',
        'OPENAI_TIMEOUT': '60',
        'OPENAI_MAX_RETRIES': '3',
        
        # AI分析配置
        'AI_MAX_CONCURRENT': '5',
        'AI_BATCH_SIZE': '10',
        'AI_CACHE_TTL': '86400',
        
        # 爬虫配置
        'CRAWLER_MAX_CONCURRENT': '20',
        'CRAWLER_TIMEOUT': '30',
        'CRAWLER_MAX_PAGES': '50',
        
        # 性能配置
        'MEMORY_LIMIT_MB': '2048',
        'CPU_LIMIT_PERCENT': '80',
        'DISK_SPACE_LIMIT_GB': '10'
    }
    
    print("请设置以下环境变量:")
    for key, value in env_vars.items():
        print(f"export {key}={value}")
    
    return env_vars


# ===== 使用示例 =====
async def example_usage():
    """使用示例"""
    from app.engines.infinite_crawler_engine import InfiniteCrawlerEngine
    
    # 1. 创建配置
    ai_config = create_ai_analysis_config()
    crawler_config = create_infinite_crawler_config()
    
    # 2. 创建爬虫引擎
    engine = InfiniteCrawlerEngine(
        task_id="example_task",
        user_id="example_user", 
        target_domain="example.com"
    )
    
    # 3. 配置AI分析
    engine.configure_ai_analysis(ai_config)
    
    # 4. 启动爬取
    try:
        result = await engine.start_infinite_crawling(crawler_config)
        print(f"爬取完成: 发现 {result['domain_statistics']['total_domains']} 个域名")
        
        # 5. 显示AI分析结果
        if 'ai_analysis_metrics' in result:
            ai_metrics = result['ai_analysis_metrics']
            print(f"AI分析: 成功 {ai_metrics.get('successful_ai_requests', 0)} 个")
            print(f"发现违规: {result.get('total_violations', 0)} 个")
        
    except Exception as e:
        print(f"爬取失败: {e}")
    
    finally:
        # 6. 清理资源
        await engine.cleanup()


if __name__ == "__main__":
    # 显示配置信息
    print("=== 无限迭代爬虫AI分析配置示例 ===")
    
    # 显示环境变量设置
    setup_environment_variables()
    
    # 显示配置结构
    print("\\n=== 配置结构 ===")
    config = create_infinite_crawler_config()
    import json
    print(json.dumps(config, indent=2, ensure_ascii=False))
"""
第三方域名访问管理器
管理和优化第三方域名的访问、内容抓取和分析流程

核心功能：
1. 智能第三方域名访问策略
2. 批量内容抓取和截图
3. 访问频率控制和反检测
4. 内容质量评估和过滤
5. 异常处理和重试机制
6. 数据完整性保证

确保对第三方域名进行全面而安全的访问和分析
"""

import asyncio
import time
import hashlib
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from urllib.parse import urlparse
import json
import random

from app.core.logging import TaskLogger
from app.engines.third_party_domain_analyzer import ThirdPartyDomainAnalyzer, ThirdPartyDomainResult
from app.engines.screenshot_engine import UniversalScreenshotEngine, ScreenshotConfig


@dataclass
class AccessPolicy:
    """访问策略配置"""
    max_concurrent_access: int = 10  # 最大并发访问数
    request_delay_range: Tuple[float, float] = (1.0, 3.0)  # 请求延迟范围
    timeout_per_domain: int = 30  # 每个域名超时时间
    max_retries: int = 2  # 最大重试次数
    enable_screenshot: bool = True  # 是否启用截图
    enable_content_analysis: bool = True  # 是否启用内容分析
    content_size_limit: int = 1024 * 1024  # 内容大小限制(1MB)
    respect_robots_txt: bool = False  # 是否遵守robots.txt
    user_agent_rotation: bool = True  # 是否轮换User-Agent


@dataclass
class AccessResult:
    """域名访问结果"""
    domain: str
    access_time: datetime
    success: bool
    response_time: float = 0.0
    error_message: Optional[str] = None
    content_captured: bool = False
    screenshot_captured: bool = False
    content_hash: Optional[str] = None
    risk_assessment: Optional[str] = None
    
    # 详细信息
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    content_length: int = 0
    server_info: Optional[str] = None
    final_url: Optional[str] = None
    
    # 分析结果
    analysis_result: Optional[ThirdPartyDomainResult] = None


class ThirdPartyAccessManager:
    """第三方域名访问管理器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 核心组件
        self.domain_analyzer = ThirdPartyDomainAnalyzer(task_id, user_id)
        self.screenshot_engine = UniversalScreenshotEngine(task_id, user_id)
        
        # 访问策略
        self.access_policy = AccessPolicy()
        
        # 访问状态管理
        self.access_queue: deque = deque()
        self.processing_domains: Set[str] = set()
        self.completed_domains: Dict[str, AccessResult] = {}
        self.failed_domains: Dict[str, AccessResult] = {}
        
        # 访问统计
        self.total_accessed = 0
        self.total_successful = 0
        self.total_failed = 0
        self.total_screenshots = 0
        self.total_content_captured = 0
        
        # 频率控制
        self.last_access_time = 0.0
        self.access_intervals: List[float] = []
        
        # User-Agent池
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15'
        ]
        self.current_user_agent_index = 0
        
        # 截图配置
        self.screenshot_config = ScreenshotConfig(
            width=1280,
            height=720,
            full_page=False,
            quality=85,
            timeout=25,
            wait_time=2.0,
            retry_count=2
        )
        
        self._engine_initialized = False
    
    def configure_access_policy(self, policy_config: Dict[str, Any]):
        """配置访问策略"""
        if 'max_concurrent_access' in policy_config:
            self.access_policy.max_concurrent_access = policy_config['max_concurrent_access']
        if 'request_delay_range' in policy_config:
            self.access_policy.request_delay_range = tuple(policy_config['request_delay_range'])
        if 'timeout_per_domain' in policy_config:
            self.access_policy.timeout_per_domain = policy_config['timeout_per_domain']
        if 'enable_screenshot' in policy_config:
            self.access_policy.enable_screenshot = policy_config['enable_screenshot']
        if 'enable_content_analysis' in policy_config:
            self.access_policy.enable_content_analysis = policy_config['enable_content_analysis']
        
        self.logger.info(f"访问策略已更新: {self.access_policy}")
    
    async def _ensure_engines_initialized(self):
        """确保引擎已初始化"""
        if not self._engine_initialized:
            try:
                await self.screenshot_engine.initialize(self.screenshot_config)
                self._engine_initialized = True
                self.logger.info("第三方访问管理器引擎初始化完成")
            except Exception as e:
                self.logger.warning(f"引擎初始化失败: {e}")
    
    def add_domains_to_queue(self, domains: List[Dict[str, Any]]):
        """添加域名到访问队列"""
        added_count = 0
        for domain_info in domains:
            domain = domain_info.get('domain', '').strip().lower()
            if domain and domain not in self.processing_domains and domain not in self.completed_domains:
                self.access_queue.append(domain_info)
                added_count += 1
        
        self.logger.info(f"添加 {added_count} 个域名到访问队列，队列总数: {len(self.access_queue)}")
    
    async def process_access_queue(self) -> Dict[str, Any]:
        """处理访问队列"""
        if not self.access_queue:
            self.logger.info("访问队列为空")
            return self._generate_access_summary()
        
        self.logger.info(f"开始处理访问队列: {len(self.access_queue)} 个域名")
        start_time = time.time()
        
        # 确保引擎已初始化
        await self._ensure_engines_initialized()
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.access_policy.max_concurrent_access)
        
        # 并发处理队列中的域名
        tasks = []
        while self.access_queue:
            domain_info = self.access_queue.popleft()
            task = self._process_single_domain(domain_info, semaphore)
            tasks.append(task)
        
        # 执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for result in results:
            if isinstance(result, AccessResult):
                if result.success:
                    self.completed_domains[result.domain] = result
                    self.total_successful += 1
                else:
                    self.failed_domains[result.domain] = result
                    self.total_failed += 1
                self.total_accessed += 1
            elif isinstance(result, Exception):
                self.logger.error(f"域名处理异常: {result}")
                self.total_failed += 1
        
        processing_time = time.time() - start_time
        self.logger.info(f"访问队列处理完成: 成功 {self.total_successful}, 失败 {self.total_failed}, 耗时 {processing_time:.2f}秒")
        
        return self._generate_access_summary()
    
    async def _process_single_domain(
        self, 
        domain_info: Dict[str, Any], 
        semaphore: asyncio.Semaphore
    ) -> AccessResult:
        """处理单个域名"""
        async with semaphore:
            domain = domain_info.get('domain', '')
            source_urls = domain_info.get('source_urls', [])
            
            self.processing_domains.add(domain)
            start_time = time.time()
            
            try:
                # 频率控制
                await self._apply_rate_limiting()
                
                # 使用域名分析器进行分析
                self.logger.debug(f"开始分析第三方域名: {domain}")
                
                analysis_result = await self.domain_analyzer.analyze_domain(domain, source_urls)
                
                # 创建访问结果
                access_result = AccessResult(
                    domain=domain,
                    access_time=datetime.utcnow(),
                    success=analysis_result.is_accessible,
                    response_time=time.time() - start_time,
                    analysis_result=analysis_result
                )
                
                if analysis_result.is_accessible:
                    # 填充成功访问的详细信息
                    access_result.status_code = analysis_result.response_code
                    access_result.final_url = analysis_result.final_url
                    access_result.server_info = analysis_result.server_info
                    access_result.content_captured = bool(analysis_result.page_content)
                    access_result.screenshot_captured = bool(analysis_result.screenshot_path)
                    access_result.risk_assessment = analysis_result.risk_level
                    
                    if analysis_result.page_content:
                        access_result.content_hash = hashlib.md5(
                            analysis_result.page_content.encode('utf-8')
                        ).hexdigest()
                        access_result.content_length = len(analysis_result.page_content)
                    
                    # 更新统计
                    if access_result.content_captured:
                        self.total_content_captured += 1
                    if access_result.screenshot_captured:
                        self.total_screenshots += 1
                    
                    self.logger.debug(f"域名 {domain} 访问成功: 状态码 {access_result.status_code}")
                else:
                    access_result.error_message = analysis_result.error_message or '域名无法访问'
                    self.logger.debug(f"域名 {domain} 访问失败: {access_result.error_message}")
                
                return access_result
                
            except Exception as e:
                self.logger.warning(f"域名 {domain} 处理异常: {e}")
                return AccessResult(
                    domain=domain,
                    access_time=datetime.utcnow(),
                    success=False,
                    response_time=time.time() - start_time,
                    error_message=str(e)
                )
            
            finally:
                self.processing_domains.discard(domain)
    
    async def _apply_rate_limiting(self):
        """应用频率限制"""
        current_time = time.time()
        
        # 计算延迟时间
        min_delay, max_delay = self.access_policy.request_delay_range
        delay = random.uniform(min_delay, max_delay)
        
        # 如果距离上次访问时间太短，则等待
        if self.last_access_time > 0:
            elapsed = current_time - self.last_access_time
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
        
        self.last_access_time = time.time()
        
        # 记录访问间隔用于分析
        if len(self.access_intervals) >= 100:
            self.access_intervals.pop(0)
        self.access_intervals.append(delay)
    
    def _get_next_user_agent(self) -> str:
        """获取下一个User-Agent"""
        if self.access_policy.user_agent_rotation:
            user_agent = self.user_agents[self.current_user_agent_index]
            self.current_user_agent_index = (self.current_user_agent_index + 1) % len(self.user_agents)
            return user_agent
        else:
            return self.user_agents[0]
    
    def _generate_access_summary(self) -> Dict[str, Any]:
        """生成访问摘要"""
        total_domains = self.total_accessed
        success_rate = self.total_successful / max(total_domains, 1)
        
        # 计算平均响应时间
        all_results = list(self.completed_domains.values()) + list(self.failed_domains.values())
        avg_response_time = sum(r.response_time for r in all_results) / max(len(all_results), 1)
        
        # 统计风险等级
        risk_distribution = defaultdict(int)
        for result in self.completed_domains.values():
            if result.risk_assessment:
                risk_distribution[result.risk_assessment] += 1
            else:
                risk_distribution['unknown'] += 1
        
        # 统计内容类型
        content_types = defaultdict(int)
        for result in self.completed_domains.values():
            if result.analysis_result and result.analysis_result.domain_type:
                content_types[result.analysis_result.domain_type] += 1
            else:
                content_types['unknown'] += 1
        
        summary = {
            'task_id': self.task_id,
            'processing_summary': {
                'total_domains': total_domains,
                'successful_accesses': self.total_successful,
                'failed_accesses': self.total_failed,
                'success_rate': success_rate,
                'content_captured_count': self.total_content_captured,
                'screenshots_captured': self.total_screenshots
            },
            'performance_metrics': {
                'average_response_time': avg_response_time,
                'average_access_interval': sum(self.access_intervals) / max(len(self.access_intervals), 1),
                'total_processing_time': sum(r.response_time for r in all_results)
            },
            'risk_distribution': dict(risk_distribution),
            'content_type_distribution': dict(content_types),
            'detailed_results': {
                'successful_domains': [
                    {
                        'domain': result.domain,
                        'response_time': result.response_time,
                        'status_code': result.status_code,
                        'risk_level': result.risk_assessment,
                        'content_captured': result.content_captured,
                        'screenshot_captured': result.screenshot_captured,
                        'content_hash': result.content_hash
                    }
                    for result in self.completed_domains.values()
                ],
                'failed_domains': [
                    {
                        'domain': result.domain,
                        'error_message': result.error_message,
                        'response_time': result.response_time
                    }
                    for result in self.failed_domains.values()
                ]
            },
            'access_policy': {
                'max_concurrent_access': self.access_policy.max_concurrent_access,
                'request_delay_range': self.access_policy.request_delay_range,
                'enable_screenshot': self.access_policy.enable_screenshot,
                'enable_content_analysis': self.access_policy.enable_content_analysis
            }
        }
        
        return summary
    
    async def get_high_risk_domains(self) -> List[Dict[str, Any]]:
        """获取高风险域名列表"""
        high_risk_domains = []
        
        for result in self.completed_domains.values():
            if (result.analysis_result and 
                result.analysis_result.risk_level in ['high', 'critical']):
                
                high_risk_info = {
                    'domain': result.domain,
                    'risk_level': result.analysis_result.risk_level,
                    'domain_type': result.analysis_result.domain_type,
                    'confidence_score': result.analysis_result.confidence_score,
                    'description': result.analysis_result.description,
                    'tags': result.analysis_result.tags,
                    'screenshot_path': result.analysis_result.screenshot_path,
                    'access_time': result.access_time.isoformat(),
                    'source_urls': result.analysis_result.source_urls
                }
                high_risk_domains.append(high_risk_info)
        
        # 按风险等级和置信度排序
        high_risk_domains.sort(
            key=lambda x: (
                0 if x['risk_level'] == 'critical' else 1,
                -x.get('confidence_score', 0)
            )
        )
        
        return high_risk_domains
    
    async def export_results(self, output_file: str):
        """导出处理结果"""
        try:
            summary = self._generate_access_summary()
            
            # 添加高风险域名详情
            summary['high_risk_domains'] = await self.get_high_risk_domains()
            
            # 导出到文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"第三方域名访问结果已导出到: {output_file}")
            
        except Exception as e:
            self.logger.error(f"导出结果失败: {e}")
    
    async def cleanup(self):
        """清理资源"""
        try:
            await self.domain_analyzer.cleanup()
            await self.screenshot_engine.cleanup()
            self.logger.info("第三方域名访问管理器资源清理完成")
        except Exception as e:
            self.logger.warning(f"清理第三方域名访问管理器资源失败: {e}")
    
    def get_processing_status(self) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            'queue_size': len(self.access_queue),
            'processing_count': len(self.processing_domains),
            'completed_count': len(self.completed_domains),
            'failed_count': len(self.failed_domains),
            'total_accessed': self.total_accessed,
            'success_rate': self.total_successful / max(self.total_accessed, 1),
            'engines_initialized': self._engine_initialized
        }
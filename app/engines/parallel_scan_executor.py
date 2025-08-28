import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from app.core.logging import TaskLogger
from app.engines.subdomain_discovery import SubdomainDiscoveryEngine, SubdomainResult
from app.engines.link_crawler import LinkCrawlerEngine, CrawlResult
from app.engines.third_party_identifier import ThirdPartyIdentifierEngine, ThirdPartyDomainResult
from app.engines.content_capture import ContentCaptureEngine, ContentResult
from app.engines.ai_analysis import AIAnalysisEngine
from app.models.task import ViolationRecord


class PipelineStage(Enum):
    """流水线阶段"""
    DISCOVERY = "discovery"
    CRAWLING = "crawling"
    ANALYSIS = "analysis"


@dataclass
class ScanEvent:
    """扫描事件"""
    timestamp: float
    stage: PipelineStage
    event_type: str
    data: Dict[str, Any]
    task_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'stage': self.stage.value,
            'event_type': self.event_type,
            'data': self.data,
            'task_id': self.task_id
        }


class EventStore:
    """事件存储器"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.events: List[ScanEvent] = []
        self.subscribers = []
    
    async def emit(self, stage: PipelineStage, event_type: str, data: Dict[str, Any]):
        """发射事件"""
        event = ScanEvent(
            timestamp=time.time(),
            stage=stage,
            event_type=event_type,
            data=data,
            task_id=self.task_id
        )
        
        self.events.append(event)
        
        # 通知所有订阅者
        for subscriber in self.subscribers:
            try:
                await subscriber(event)
            except Exception as e:
                print(f"Event subscriber error: {e}")
    
    def subscribe(self, callback):
        """订阅事件"""
        self.subscribers.append(callback)
    
    def get_events(self) -> List[Dict[str, Any]]:
        """获取所有事件"""
        return [event.to_dict() for event in self.events]


class PipelineQueue:
    """轨间通信队列"""
    
    def __init__(self, maxsize: int = 1000):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.processed_count = 0
        self.error_count = 0
    
    async def put(self, item: Any):
        """放入队列"""
        await self.queue.put(item)
    
    async def get(self) -> Any:
        """从队列获取"""
        item = await self.queue.get()
        self.processed_count += 1
        return item
    
    def qsize(self) -> int:
        """队列大小"""
        return self.queue.qsize()
    
    def task_done(self):
        """标记任务完成"""
        self.queue.task_done()


class ParallelScanExecutor:
    """并行扫描执行器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 事件存储
        self.event_store = EventStore(task_id)
        
        # 引擎实例
        self.subdomain_engine = SubdomainDiscoveryEngine(task_id, user_id)
        self.crawler_engine = LinkCrawlerEngine(task_id, user_id)
        self.identifier_engine = ThirdPartyIdentifierEngine(task_id, user_id)
        self.capture_engine = ContentCaptureEngine(task_id, user_id)
        self.ai_engine = None  # 延迟初始化
        
        # 轨间队列
        self.discovery_to_crawl = PipelineQueue(maxsize=2000)
        self.crawl_to_analysis = PipelineQueue(maxsize=2000)
        
        # 执行状态
        self.is_running = False
        self.is_cancelled = False
        self.start_time = None
        self.end_time = None
        
        # 结果收集
        self.results = {
            'subdomains': [],
            'crawl_results': [],
            'third_party_domains': [],
            'content_results': [],
            'violation_records': [],
            'statistics': {}
        }
    
    async def execute_scan(self, target_domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """执行并行扫描"""
        self.is_running = True
        self.is_cancelled = False
        self.start_time = time.time()
        
        try:
            await self.event_store.emit(
                PipelineStage.DISCOVERY, 
                'scan_started', 
                {'target_domain': target_domain, 'config': config}
            )
            
            # 启动三轨并行流水线
            discovery_task = asyncio.create_task(
                self._discovery_pipeline(target_domain, config)
            )
            crawl_task = asyncio.create_task(
                self._crawling_pipeline(config)
            )
            analysis_task = asyncio.create_task(
                self._analysis_pipeline(config)
            )
            
            # 等待所有轨完成
            await asyncio.gather(
                discovery_task, 
                crawl_task, 
                analysis_task,
                return_exceptions=True
            )
            
            # 计算最终统计
            await self._calculate_final_statistics()
            
            await self.event_store.emit(
                PipelineStage.ANALYSIS,
                'scan_completed',
                {'duration': time.time() - self.start_time}
            )
            
            return self._build_scan_result()
            
        except Exception as e:
            self.logger.error(f"并行扫描执行失败: {e}")
            await self.event_store.emit(
                PipelineStage.ANALYSIS,
                'scan_failed',
                {'error': str(e)}
            )
            raise
        finally:
            self.is_running = False
            self.end_time = time.time()
    
    async def _discovery_pipeline(self, target_domain: str, config: Dict[str, Any]):
        """发现轨流水线"""
        try:
            await self.event_store.emit(
                PipelineStage.DISCOVERY,
                'stage_started',
                {'stage': 'subdomain_discovery'}
            )
            
            # 并行执行所有子域名发现方法
            discovery_tasks = []
            
            # DNS爆破（高并发）
            if config.get('subdomain_discovery_enabled', True):
                discovery_tasks.append(
                    self._enhanced_dns_discovery(target_domain, config)
                )
            
            # 证书透明日志（多源）
            if config.get('certificate_discovery_enabled', True):
                discovery_tasks.append(
                    self._enhanced_certificate_discovery(target_domain, config)
                )
            
            # 被动DNS
            if config.get('passive_dns_enabled', True):
                discovery_tasks.append(
                    self._passive_dns_discovery(target_domain, config)
                )
            
            # 并行执行所有发现任务
            discovery_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
            
            # 合并去重结果
            all_subdomains = set()
            for result in discovery_results:
                if isinstance(result, list):
                    all_subdomains.update(result)
                elif isinstance(result, Exception):
                    self.logger.warning(f"子域名发现异常: {result}")
            
            self.results['subdomains'] = list(all_subdomains)
            
            await self.event_store.emit(
                PipelineStage.DISCOVERY,
                'subdomains_discovered',
                {
                    'count': len(all_subdomains),
                    'domains': [sub.subdomain for sub in all_subdomains][:10]  # 前10个
                }
            )
            
            # 将可访问的子域名发送到爬取轨
            accessible_subdomains = [sub for sub in all_subdomains if sub.is_accessible]
            for subdomain in accessible_subdomains:
                await self.discovery_to_crawl.put(subdomain)
            
            # 发送完成信号
            await self.discovery_to_crawl.put(None)
            
        except Exception as e:
            self.logger.error(f"发现轨执行失败: {e}")
            await self.event_store.emit(
                PipelineStage.DISCOVERY,
                'stage_failed',
                {'error': str(e)}
            )
    
    async def _crawling_pipeline(self, config: Dict[str, Any]):
        """爬取轨流水线"""
        try:
            await self.event_store.emit(
                PipelineStage.CRAWLING,
                'stage_started',
                {'stage': 'link_crawling'}
            )
            
            crawl_count = 0
            while True:
                if self.is_cancelled:
                    break
                
                # 从发现轨接收子域名
                subdomain = await self.discovery_to_crawl.get()
                
                if subdomain is None:  # 完成信号
                    break
                
                try:
                    # 爬取单个子域名
                    crawl_results = await self._enhanced_crawl_subdomain(subdomain, config)
                    self.results['crawl_results'].extend(crawl_results)
                    
                    # 发送到分析轨
                    for crawl_result in crawl_results:
                        await self.crawl_to_analysis.put(crawl_result)
                    
                    crawl_count += 1
                    
                    await self.event_store.emit(
                        PipelineStage.CRAWLING,
                        'subdomain_crawled',
                        {
                            'subdomain': subdomain.subdomain,
                            'pages': len(crawl_results),
                            'total_crawled': crawl_count
                        }
                    )
                    
                except Exception as e:
                    self.logger.warning(f"爬取子域名失败 {subdomain.subdomain}: {e}")
                
                finally:
                    self.discovery_to_crawl.task_done()
            
            # 发送完成信号
            await self.crawl_to_analysis.put(None)
            
            await self.event_store.emit(
                PipelineStage.CRAWLING,
                'stage_completed',
                {'total_crawled': crawl_count}
            )
            
        except Exception as e:
            self.logger.error(f"爬取轨执行失败: {e}")
            await self.event_store.emit(
                PipelineStage.CRAWLING,
                'stage_failed',
                {'error': str(e)}
            )
    
    async def _analysis_pipeline(self, config: Dict[str, Any]):
        """分析轨流水线"""
        try:
            await self.event_store.emit(
                PipelineStage.ANALYSIS,
                'stage_started',
                {'stage': 'ai_analysis'}
            )
            
            analysis_count = 0
            ai_call_count = 0
            ai_skip_count = 0
            
            while True:
                if self.is_cancelled:
                    break
                
                # 从爬取轨接收爬取结果
                crawl_result = await self.crawl_to_analysis.get()
                
                if crawl_result is None:  # 完成信号
                    break
                
                try:
                    # 第三方域名识别
                    third_party_domains = await self.identifier_engine.identify_third_party_domains(
                        [crawl_result], config
                    )
                    self.results['third_party_domains'].extend(third_party_domains)
                    
                    # 内容抓取
                    content_results = await self.capture_engine.capture_domain_content(
                        crawl_result.domain, [crawl_result.url], config
                    )
                    self.results['content_results'].extend(content_results)
                    
                    # 智能AI分析（预筛选）
                    for content_result in content_results:
                        should_analyze, reason = await self._should_analyze_with_ai(content_result)
                        
                        if should_analyze:
                            ai_call_count += 1
                            violations = await self._perform_ai_analysis(content_result, config)
                            self.results['violation_records'].extend(violations)
                        else:
                            ai_skip_count += 1
                            await self.event_store.emit(
                                PipelineStage.ANALYSIS,
                                'ai_analysis_skipped',
                                {'reason': reason, 'url': content_result.url}
                            )
                    
                    analysis_count += 1
                    
                    await self.event_store.emit(
                        PipelineStage.ANALYSIS,
                        'domain_analyzed',
                        {
                            'domain': crawl_result.domain,
                            'third_party_count': len(third_party_domains),
                            'content_count': len(content_results),
                            'total_analyzed': analysis_count
                        }
                    )
                    
                except Exception as e:
                    self.logger.warning(f"分析域名失败 {crawl_result.domain}: {e}")
                
                finally:
                    self.crawl_to_analysis.task_done()
            
            await self.event_store.emit(
                PipelineStage.ANALYSIS,
                'stage_completed',
                {
                    'total_analyzed': analysis_count,
                    'ai_calls': ai_call_count,
                    'ai_skips': ai_skip_count,
                    'ai_efficiency': f"{(ai_skip_count / (ai_call_count + ai_skip_count) * 100):.1f}%" if (ai_call_count + ai_skip_count) > 0 else "0%"
                }
            )
            
        except Exception as e:
            self.logger.error(f"分析轨执行失败: {e}")
            await self.event_store.emit(
                PipelineStage.ANALYSIS,
                'stage_failed',
                {'error': str(e)}
            )
    
    async def _enhanced_dns_discovery(self, domain: str, config: Dict[str, Any]) -> List[SubdomainResult]:
        """增强的DNS发现"""
        concurrency = config.get('dns_concurrency', 100)  # 提高并发度
        timeout = config.get('dns_timeout', 3)  # 降低超时时间
        
        return await self.subdomain_engine.discover_dns_with_concurrency(
            domain, concurrency, timeout
        )
    
    async def _enhanced_certificate_discovery(self, domain: str, config: Dict[str, Any]) -> List[SubdomainResult]:
        """增强的证书透明日志发现"""
        # 多源并发查询
        sources = ['crt.sh', 'censys', 'facebook_ct']
        
        return await self.subdomain_engine.discover_certificate_multi_source(
            domain, sources
        )
    
    async def _passive_dns_discovery(self, domain: str, config: Dict[str, Any]) -> List[SubdomainResult]:
        """被动DNS发现"""
        # 从第三方数据源查询
        return await self.subdomain_engine.discover_passive_dns(domain)
    
    async def _enhanced_crawl_subdomain(self, subdomain: SubdomainResult, config: Dict[str, Any]) -> List[CrawlResult]:
        """增强的子域名爬取"""
        max_pages = config.get('max_pages_per_subdomain', 20)
        
        return await self.crawler_engine.crawl_subdomain_enhanced(
            subdomain.subdomain, max_pages
        )
    
    async def _should_analyze_with_ai(self, content_result: ContentResult) -> Tuple[bool, str]:
        """判断是否需要AI分析（预筛选）"""
        # 快速预筛选规则
        if not content_result.screenshot_path:
            return False, "no_screenshot"
        
        # 检查文件大小
        try:
            import os
            file_size = os.path.getsize(content_result.screenshot_path)
            if file_size < 1024:  # 小于1KB，可能是空截图
                return False, "screenshot_too_small"
        except:
            return False, "screenshot_file_error"
        
        # 检查URL模式
        suspicious_patterns = [
            'login', 'admin', 'auth', 'api', 'upload', 'download',
            'casino', 'porn', 'adult', 'gambling', 'phishing'
        ]
        
        url_lower = content_result.url.lower()
        for pattern in suspicious_patterns:
            if pattern in url_lower:
                return True, f"suspicious_pattern_{pattern}"
        
        # 检查状态码
        if hasattr(content_result, 'status_code') and content_result.status_code >= 400:
            return False, "error_status_code"
        
        # 默认：随机采样策略（降低AI调用）
        import random
        sample_rate = 0.3  # 30%采样率
        if random.random() < sample_rate:
            return True, "random_sample"
        else:
            return False, "random_skip"
    
    async def _perform_ai_analysis(self, content_result: ContentResult, config: Dict[str, Any]) -> List[ViolationRecord]:
        """执行AI分析"""
        if not self.ai_engine:
            from app.models.user import UserAIConfig
            from app.core.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                ai_config = await db.get(UserAIConfig, self.user_id)
                if ai_config:
                    from app.engines.ai_analysis import AIAnalysisEngine
                    self.ai_engine = AIAnalysisEngine(self.task_id, self.user_id)
        
        if self.ai_engine:
            return await self.ai_engine.analyze_single_content(content_result)
        else:
            return []
    
    async def _calculate_final_statistics(self):
        """计算最终统计信息"""
        self.results['statistics'] = {
            'total_subdomains': len(self.results['subdomains']),
            'accessible_subdomains': len([s for s in self.results['subdomains'] if s.is_accessible]),
            'total_pages_crawled': len(self.results['crawl_results']),
            'total_third_party_domains': len(self.results['third_party_domains']),
            'total_violations': len(self.results['violation_records']),
            'execution_duration': int(time.time() - self.start_time) if self.start_time else 0,
            'pipeline_efficiency': {
                'discovery_queue_max': self.discovery_to_crawl.processed_count,
                'crawl_queue_max': self.crawl_to_analysis.processed_count,
            }
        }
    
    def _build_scan_result(self) -> Dict[str, Any]:
        """构建扫描结果"""
        return {
            'task_id': self.task_id,
            'status': 'completed' if not self.is_cancelled else 'cancelled',
            'start_time': self.start_time,
            'end_time': self.end_time,
            'events': self.event_store.get_events(),
            'results': self.results
        }
    
    async def cancel_scan(self):
        """取消扫描"""
        self.is_cancelled = True
        await self.event_store.emit(
            PipelineStage.ANALYSIS,
            'scan_cancelled',
            {'reason': 'user_request'}
        )
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            'is_running': self.is_running,
            'is_cancelled': self.is_cancelled,
            'task_id': self.task_id,
            'queue_status': {
                'discovery_to_crawl': self.discovery_to_crawl.qsize(),
                'crawl_to_analysis': self.crawl_to_analysis.qsize()
            },
            'events_count': len(self.event_store.events)
        }
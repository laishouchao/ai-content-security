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
            'domain_records': [],
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
            
            # 转换为列表以便后续处理
            subdomain_list = list(all_subdomains)
            
            # 🔧 关键修复：添加可访问性验证
            if subdomain_list and config.get('verify_accessibility', True):
                self.logger.info(f"开始验证 {len(subdomain_list)} 个子域名的可访问性...")
                
                # 使用子域名发现引擎的可访问性验证方法
                verified_subdomains = await self.subdomain_engine._verify_accessibility(subdomain_list)
                self.results['subdomains'] = verified_subdomains
                
                # 统计可访问的子域名
                accessible_count = sum(1 for sub in verified_subdomains if sub.is_accessible)
                self.logger.info(f"可访问性验证完成: {accessible_count}/{len(verified_subdomains)} 个子域名可访问")
            else:
                # 如果跳过验证，直接使用发现结果
                self.results['subdomains'] = subdomain_list
                self.logger.warning("跳过可访问性验证")
            
            await self.event_store.emit(
                PipelineStage.DISCOVERY,
                'subdomains_discovered',
                {
                    'count': len(self.results['subdomains']),
                    'domains': [sub.subdomain for sub in self.results['subdomains']][:10]  # 前10个
                }
            )
            
            # 将可访问的子域名发送到爬取轨
            accessible_subdomains = [sub for sub in self.results['subdomains'] if sub.is_accessible]
            self.logger.info(f"发送 {len(accessible_subdomains)} 个可访问子域名到爬取轨")
            
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
            
            # 检查AI分析是否启用
            ai_analysis_enabled = config.get('ai_analysis_enabled', True)
            self.logger.info(f"AI分析配置: ai_analysis_enabled={ai_analysis_enabled}")
            
            if not ai_analysis_enabled:
                self.logger.warning("⚠️ AI分析已被禁用，跳过分析阶段")
                await self.event_store.emit(
                    PipelineStage.ANALYSIS,
                    'ai_analysis_disabled',
                    {'reason': 'ai_analysis_disabled_in_config'}
                )
                return
            
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
                    self.logger.info(f"🔍 开始分析域名: {crawl_result.domain}")
                    
                    # 第三方域名识别
                    domain_records = await self.identifier_engine.identify_domain_records(
                        crawl_result.domain, [crawl_result], config
                    )
                    self.results['domain_records'].extend(domain_records)
                    self.logger.info(f"识别到 {len(domain_records)} 个第三方域名")
                    
                    # 内容抓取
                    content_results = await self.capture_engine.capture_domain_content(
                        crawl_result.domain, [crawl_result.url], config
                    )
                    self.results['content_results'].extend(content_results)
                    self.logger.info(f"抓取到 {len(content_results)} 个内容结果")
                    
                    # AI分析
                    for i, content_result in enumerate(content_results):
                        self.logger.info(f"🤖 正在处理内容 ({i+1}/{len(content_results)}): {content_result.url}")
                        
                        # 详细检查内容结果
                        self.logger.debug(f"内容结果详情: screenshot_path={getattr(content_result, 'screenshot_path', None)}, "
                                         f"status_code={getattr(content_result, 'status_code', None)}")
                        
                        should_analyze, reason = await self._should_analyze_with_ai(content_result)
                        self.logger.info(f"分析检查结果: should_analyze={should_analyze}, reason={reason}")
                        
                        if should_analyze:
                            ai_call_count += 1
                            self.logger.info(f"✅ 执行AI分析 (#{ai_call_count}): {content_result.url}")
                            
                            try:
                                violations = await self._perform_ai_analysis(content_result, config)
                                self.results['violation_records'].extend(violations)
                                self.logger.info(f"🚨 AI分析完成，发现 {len(violations)} 个违规")
                            except Exception as ai_error:
                                self.logger.error(f"❌ AI分析失败: {ai_error}")
                                await self.event_store.emit(
                                    PipelineStage.ANALYSIS,
                                    'ai_analysis_error',
                                    {'url': content_result.url, 'error': str(ai_error)}
                                )
                        else:
                            ai_skip_count += 1
                            self.logger.info(f"⏭️ 跳过AI分析 (#{ai_skip_count}): {reason} - {content_result.url}")
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
                            'third_party_count': len(domain_records),
                            'content_count': len(content_results),
                            'total_analyzed': analysis_count
                        }
                    )
                    
                except Exception as e:
                    self.logger.warning(f"分析域名失败 {crawl_result.domain}: {e}")
                
                finally:
                    self.crawl_to_analysis.task_done()
            
            # 计算AI效率统计
            ai_efficiency = 0
            if (ai_call_count + ai_skip_count) > 0:
                ai_efficiency = (ai_skip_count / (ai_call_count + ai_skip_count) * 100)
            
            self.logger.info(f"🏁 分析阶段完成统计:")
            self.logger.info(f"  - 总分析域名: {analysis_count}")
            self.logger.info(f"  - AI调用次数: {ai_call_count}")
            self.logger.info(f"  - AI跳过次数: {ai_skip_count}")
            self.logger.info(f"  - AI效率: {ai_efficiency:.1f}%")
            
            await self.event_store.emit(
                PipelineStage.ANALYSIS,
                'stage_completed',
                {
                    'total_analyzed': analysis_count,
                    'ai_calls': ai_call_count,
                    'ai_skips': ai_skip_count,
                    'ai_efficiency': f"{ai_efficiency:.1f}%"
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
        
        # 构建起始URL列表
        start_urls = [
            f"https://{subdomain.subdomain}",
            f"http://{subdomain.subdomain}"
        ]
        
        # 使用实际存在的crawl_domain方法
        crawl_config = config.copy()
        crawl_config['max_pages_per_domain'] = max_pages
        
        return await self.crawler_engine.crawl_domain(
            subdomain.subdomain, start_urls, crawl_config
        )
    
    async def _should_analyze_with_ai(self, content_result: ContentResult) -> Tuple[bool, str]:
        """判断是否需要AI分析"""
        self.logger.debug(f"🔍 开始分析检查: {content_result.url}")
        
        # 根据AI分析配置规则，确保100%的AI分析覆盖率
        # 不跳过任何内容，即使没有截图也要进行AI分析
        
        # 检查截图文件（仅用于日志记录）
        if not content_result.screenshot_path:
            self.logger.info(f"⚠️ 没有截图路径，但仍然进行AI分析: {content_result.url}")
        else:
            self.logger.debug(f"🖼️ 截图路径: {content_result.screenshot_path}")
            
            # 检查文件大小（仅用于日志记录）
            try:
                import os
                if not os.path.exists(content_result.screenshot_path):
                    self.logger.info(f"⚠️ 截图文件不存在，但仍然进行AI分析: {content_result.screenshot_path}")
                else:
                    file_size = os.path.getsize(content_result.screenshot_path)
                    self.logger.debug(f"📄 截图文件大小: {file_size} bytes")
                    
                    if file_size < 1024:  # 小于1KB
                        self.logger.info(f"⚠️ 截图文件较小，但仍然进行AI分析: {file_size} bytes")
            except Exception as e:
                self.logger.info(f"⚠️ 检查截图文件出错，但仍然进行AI分析: {e}")
        
        # 检查状态码（仅用于日志记录）
        if hasattr(content_result, 'status_code') and content_result.status_code is not None and content_result.status_code >= 400:
            self.logger.info(f"⚠️ 错误状态码，但仍然进行AI分析: {content_result.status_code}")
        
        # 根据AI分析配置规则，对所有内容进行AI分析，不跳过任何内容
        self.logger.info(f"✅ 对所有内容进行AI分析（100%覆盖率）: {content_result.url}")
        return True, "analyze_all_content"
    
    async def _perform_ai_analysis(self, content_result: ContentResult, config: Dict[str, Any]) -> List[ViolationRecord]:
        """执行AI分析"""
        self.logger.info(f"🤖 开始执行AI分析: {content_result.url}")
        
        # 检查AI引擎是否已初始化
        if not self.ai_engine:
            self.logger.info("🔧 正在初始化AI引擎...")
            
            from app.models.user import UserAIConfig
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import select
            from app.core.security import data_encryption
            
            try:
                async with AsyncSessionLocal() as db:
                    # 使用正确的查询方式：根据user_id查询，而不是使用主键
                    stmt = select(UserAIConfig).where(UserAIConfig.user_id == self.user_id)
                    result = await db.execute(stmt)
                    ai_config = result.scalar_one_or_none()
                    
                    if not ai_config:
                        self.logger.error(f"❌ 用户AI配置不存在: user_id={self.user_id}")
                        return []
                    
                    # 解密API密钥
                    if ai_config.openai_api_key is not None:
                        try:
                            decrypted_api_key = data_encryption.decrypt_data(str(ai_config.openai_api_key))
                            # 使用setattr来避免SQLAlchemy Column类型检查问题
                            setattr(ai_config, 'openai_api_key', decrypted_api_key)
                        except Exception as e:
                            self.logger.warning(f"解密API密钥失败: {e}")
                            # 使用setattr来避免SQLAlchemy Column类型检查问题
                            setattr(ai_config, 'openai_api_key', None)
                    
                    self.logger.debug(f"🔑 获取到AI配置: model={ai_config.model_name}, "
                                     f"has_api_key={bool(ai_config.openai_api_key)}, "
                                     f"has_valid_config={ai_config.has_valid_config}")
                    
                    if not ai_config.has_valid_config:
                        self.logger.error(f"❌ 用户AI配置无效: user_id={self.user_id}")
                        return []
                    
                    from app.engines.ai_analysis import AIAnalysisEngine
                    self.ai_engine = AIAnalysisEngine(self.task_id, ai_config)
                    self.logger.info("✅ AI引擎初始化成功")
                    
            except Exception as e:
                self.logger.error(f"❌ AI引擎初始化失败: {e}")
                return []
        
        if self.ai_engine:
            try:
                # 由于AIAnalysisEngine.analyze_domains需要ThirdPartyDomain对象列表
                # 我们需要创建一个临时的域名对象来进行分析
                from app.models.domain import DomainRecord
                from urllib.parse import urlparse
                
                # 从content_result.url解析域名
                parsed_url = urlparse(content_result.url)
                domain_name = parsed_url.netloc
                
                self.logger.debug(f"🌍 解析域名: {domain_name} from {content_result.url}")
                
                # 创建临时的ThirdPartyDomain对象
                temp_domain = DomainRecord(
                    task_id=self.task_id,
                    domain=domain_name,
                    found_on_url=content_result.url,
                    screenshot_path=content_result.screenshot_path,
                    page_title=getattr(content_result, 'page_title', ''),
                    page_description=getattr(content_result, 'page_description', ''),
                    domain_type='unknown',
                    is_analyzed=False
                )
                
                self.logger.info(f"📦 创建临时域名对象: {domain_name}")
                
                # 调用analyze_domains方法
                self.logger.info(f"🚀 开始调用AI分析接口...")
                violations = await self.ai_engine.analyze_domains([temp_domain])
                
                self.logger.info(f"✅ AI分析完成，返回 {len(violations)} 个违规记录")
                
                # 记录违规详情
                for i, violation in enumerate(violations):
                    self.logger.info(f"🚨 违规#{i+1}: {violation.violation_type} - "
                                   f"置信度:{violation.confidence_score:.2f} - "
                                   f"风险等级:{violation.risk_level}")
                
                return violations
                
            except Exception as e:
                self.logger.error(f"❌ AI分析执行失败: {e}")
                import traceback
                self.logger.error(f"错误堆栈: {traceback.format_exc()}")
                return []
        else:
            self.logger.error("❌ AI引擎不可用")
            return []
    
    async def _calculate_final_statistics(self):
        """计算最终统计信息"""
        self.results['statistics'] = {
            'total_subdomains': len(self.results['subdomains']),
            'accessible_subdomains': len([s for s in self.results['subdomains'] if s.is_accessible]),
            'total_pages_crawled': len(self.results['crawl_results']),
            'total_domain_records': len(self.results['domain_records']),
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
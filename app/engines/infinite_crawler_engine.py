"""
无限迭代爬虫引擎
实现无层级限制的全面域名发现和内容抓取

设计思路：
1. 保留并优化多种子域名发现方式
2. 实现全局域名池管理，避免重复处理
3. 无限迭代直至没有新域名发现
4. 对所有发现的域名（包括第三方）进行深度分析
5. 集成AI分析和内容评估

核心流程：
初始域名 -> 子域名发现 -> URL抓取 -> 域名提取 -> 新域名入池 -> 重复迭代 -> AI分析
"""

import asyncio
import aiohttp
import time
import hashlib
from typing import Dict, List, Set, Any, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict, deque
from urllib.parse import urlparse, urljoin
import re
import json
from pathlib import Path

from app.core.logging import TaskLogger
from app.core.config import settings
from app.engines.subdomain_discovery import DNSQueryMethod, CertificateTransparencyMethod, BruteForceMethod, SubdomainResult
from app.engines.enhanced_subdomain_discovery_v2 import EnhancedSubdomainDiscoveryEngine
from app.engines.enhanced_domain_extractor import EnhancedDomainExtractor
from app.engines.smart_link_crawler import SmartLinkCrawler
from app.engines.infinite_iteration_controller import InfiniteIterationController, IterationPhase
from app.engines.third_party_access_manager import ThirdPartyAccessManager
from app.engines.third_party_domain_analyzer import ThirdPartyDomainAnalyzer, ThirdPartyDomainResult
from app.engines.ai_analysis import AIAnalysisEngine


@dataclass
class DomainInfo:
    """域名信息"""
    domain: str
    domain_type: str  # 'target_subdomain', 'third_party'
    discovered_at: datetime
    discovery_method: str
    source_urls: List[str] = field(default_factory=list)
    
    # 处理状态
    subdomain_discovered: bool = False  # 是否已进行子域名发现
    content_crawled: bool = False      # 是否已进行内容爬取
    ai_analyzed: bool = False          # 是否已进行AI分析
    
    # 分析结果
    is_accessible: bool = False
    page_count: int = 0
    found_links: List[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    risk_level: str = 'unknown'
    

@dataclass
class IterationResult:
    """迭代结果"""
    iteration_number: int
    new_domains_found: int
    total_domains: int
    processed_domains: int
    ai_violations_found: int
    duration_seconds: float
    

class InfiniteCrawlerEngine:
    """无限迭代爬虫引擎"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain.lower().strip()
        self.logger = TaskLogger(task_id, user_id)
        
        # 全局域名池
        self.all_domains: Dict[str, DomainInfo] = {}
        
        # 工作队列
        self.subdomain_discovery_queue: deque = deque()  # 待进行子域名发现的域名
        self.content_crawl_queue: deque = deque()        # 待进行内容爬取的域名  
        self.ai_analysis_queue: deque = deque()          # 待进行AI分析的域名
        
        # 引擎组件
        self.enhanced_subdomain_engine = EnhancedSubdomainDiscoveryEngine(task_id, user_id)
        self.domain_extractor = EnhancedDomainExtractor(task_id, user_id, target_domain)
        self.smart_crawler = SmartLinkCrawler(task_id, user_id, target_domain)
        self.third_party_access_manager = ThirdPartyAccessManager(task_id, user_id)
        self.domain_analyzer = ThirdPartyDomainAnalyzer(task_id, user_id)
        self.ai_engine: Optional[AIAnalysisEngine] = None
        
        # 无限迭代控制器
        self.iteration_controller = InfiniteIterationController(task_id, user_id, target_domain)
        
        # 传统方法作为备用
        self.dns_method = DNSQueryMethod()
        self.ct_method = CertificateTransparencyMethod()
        self.brute_method = BruteForceMethod()
        
        # 统计信息
        self.iteration_results: List[IterationResult] = []
        self.total_violations_found = 0
        
        # 配置参数
        self.max_domains_per_iteration = 200  # 每次迭代处理的最大域名数
        self.max_total_domains = 10000        # 全局最大域名数限制
        self.concurrent_crawlers = 20         # 并发爬虫数量
        
    async def start_infinite_crawling(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        启动无限迭代爬取
        
        Args:
            config: 爬取配置参数
            
        Returns:
            爬取结果统计
        """
        start_time = time.time()
        self.logger.info(f"开始无限迭代爬取: {self.target_domain}")
        
        try:
            # 配置迭代控制器
            self.iteration_controller.configure_stopping_conditions(config)
            
            # 阶段1: 初始化目标域名
            self.iteration_controller.update_phase(IterationPhase.INITIALIZING)
            await self._initialize_target_domain()
            
            # 阶段2: 真正的无限迭代发现循环
            iteration_count = 0
            while True:
                iteration_count += 1
                
                # 开始新迭代
                iteration_metrics = self.iteration_controller.start_iteration(iteration_count)
                
                self.logger.info(f"=== 开始第 {iteration_count} 次迭代 ===")
                
                # 执行单次迭代
                new_domains_count = await self._execute_enhanced_iteration(config)
                
                # 记录队列状态
                queue_status = {
                    'subdomain_discovery': len(self.subdomain_discovery_queue),
                    'content_crawl': len(self.content_crawl_queue),
                    'ai_analysis': len(self.ai_analysis_queue)
                }
                self.iteration_controller.record_queue_status(queue_status)
                
                # 结束迭代并判断是否继续
                should_continue = self.iteration_controller.end_iteration(
                    new_domains_count, 
                    len(self.all_domains)
                )
                
                # 获取自适应参数
                adaptive_params = self.iteration_controller.get_adaptive_parameters()
                self.max_domains_per_iteration = adaptive_params['batch_size']
                self.concurrent_crawlers = adaptive_params['concurrent_limit']
                
                # 应用自适应延迟
                await asyncio.sleep(adaptive_params['delay'])
                
                # 检查是否应该停止
                if not should_continue:
                    self.logger.info(f"迭代控制器决定停止迭代")
                    break
            
            # 阶段3: 增强的第三方域名分析
            self.iteration_controller.update_phase(IterationPhase.AI_ANALYSIS)
            await self._enhanced_third_party_analysis(config)
            
            # 阶段4: 生成最终结果
            self.iteration_controller.update_phase(IterationPhase.COMPLETED)
            total_duration = time.time() - start_time
            final_result = await self._generate_enhanced_final_result(total_duration)
            
            # 保存迭代报告
            try:
                report_file = f"iteration_report_{self.target_domain}_{int(time.time())}.json"
                self.iteration_controller.save_iteration_report(report_file)
            except Exception as e:
                self.logger.warning(f"保存迭代报告失败: {e}")
            
            self.logger.info(f"无限迭代爬取完成: 共 {iteration_count} 次迭代，发现 {len(self.all_domains)} 个域名，耗时 {total_duration:.2f} 秒")
            
            return final_result
            
        except Exception as e:
            self.iteration_controller.update_phase(IterationPhase.ERROR)
            self.iteration_controller.record_error(type(e).__name__, str(e))
            self.logger.error(f"无限迭代爬取异常: {e}")
            raise e
        finally:
            # 清理资源
            try:
                self.iteration_controller.cleanup()
                await self.third_party_access_manager.cleanup()
                await self.domain_analyzer.cleanup()
            except Exception as cleanup_error:
                self.logger.warning(f"资源清理警告: {cleanup_error}")
    
    async def _initialize_target_domain(self):
        """初始化目标域名"""
        self.logger.info(f"初始化目标域名: {self.target_domain}")
        
        # 添加主域名到全局池
        main_domain_info = DomainInfo(
            domain=self.target_domain,
            domain_type='target_subdomain',
            discovered_at=datetime.utcnow(),
            discovery_method='initial_target'
        )
        self.all_domains[self.target_domain] = main_domain_info
        
        # 添加到子域名发现队列
        self.subdomain_discovery_queue.append(self.target_domain)
    
    async def _execute_enhanced_iteration(self, config: Dict[str, Any]) -> int:
        """执行增强的单次迭代，返回新发现的域名数量"""
        initial_domain_count = len(self.all_domains)
        
        try:
            # 步骤1: 子域名发现阶段
            self.iteration_controller.update_phase(IterationPhase.SUBDOMAIN_DISCOVERY)
            subdomain_results = await self._enhanced_subdomain_discovery_phase(config)
            self.iteration_controller.record_discovery(subdomain_results)
            
            # 步骤2: 内容爬取阶段  
            self.iteration_controller.update_phase(IterationPhase.CONTENT_CRAWLING)
            crawl_results = await self._enhanced_content_crawling_phase(config)
            pages_crawled, links_extracted = crawl_results
            self.iteration_controller.record_discovery(0, pages_crawled, links_extracted)
            
            # 步骤3: 域名提取和队列更新阶段
            self.iteration_controller.update_phase(IterationPhase.DOMAIN_EXTRACTION)
            extraction_results = await self._enhanced_domain_extraction_phase()
            self.iteration_controller.record_discovery(extraction_results)
            
        except Exception as e:
            self.iteration_controller.record_error(type(e).__name__, str(e))
            self.logger.error(f"迭代执行异常: {e}")
        
        # 计算新发现的域名数量
        new_domain_count = len(self.all_domains) - initial_domain_count
        return new_domain_count
    
    async def _enhanced_subdomain_discovery_phase(self, config: Dict[str, Any]) -> int:
        """增强的子域名发现阶段"""
        if not self.subdomain_discovery_queue:
            return 0
            
        self.logger.info(f"增强子域名发现阶段: 队列中有 {len(self.subdomain_discovery_queue)} 个域名")
        
        # 获取自适应参数
        adaptive_params = self.iteration_controller.get_adaptive_parameters()
        batch_size = min(adaptive_params['batch_size'], len(self.subdomain_discovery_queue))
        
        # 批量处理队列中的域名
        batch_domains = []
        for _ in range(batch_size):
            if self.subdomain_discovery_queue:
                domain = self.subdomain_discovery_queue.popleft()
                batch_domains.append(domain)
        
        # 并发执行子域名发现
        discovery_tasks = []
        for domain in batch_domains:
            if domain in self.all_domains and not self.all_domains[domain].subdomain_discovered:
                discovery_tasks.append(self._discover_subdomains_for_domain(domain))
        
        discovered_count = 0
        if discovery_tasks:
            discovery_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
            
            # 处理发现结果
            for i, result in enumerate(discovery_results):
                domain = batch_domains[i]
                if isinstance(result, Exception):
                    self.iteration_controller.record_error(type(result).__name__, str(result))
                    self.logger.warning(f"域名 {domain} 子域名发现失败: {result}")
                else:
                    # 标记已完成子域名发现
                    if domain in self.all_domains:
                        self.all_domains[domain].subdomain_discovered = True
                        
                    # 处理新发现的子域名
                    if isinstance(result, list):  # 确保是列表
                        discovered_count += len(result)
                        for subdomain_result in result:
                            await self._add_domain_to_pool(
                                subdomain_result.subdomain,
                                'target_subdomain',
                                subdomain_result.method if hasattr(subdomain_result, 'method') else 'subdomain_discovery',
                                [f"subdomain_of_{domain}"]
                            )
        
        self.logger.info(f"子域名发现阶段完成: 新发现 {discovered_count} 个子域名")
        return discovered_count
    
    async def _enhanced_content_crawling_phase(self, config: Dict[str, Any]) -> Tuple[int, int]:
        """增强的内容爬取阶段，返回(页面数, 链接数)"""
        if not self.content_crawl_queue:
            return 0, 0
            
        self.logger.info(f"增强内容爬取阶段: 队列中有 {len(self.content_crawl_queue)} 个域名")
        
        # 获取自适应参数
        adaptive_params = self.iteration_controller.get_adaptive_parameters()
        batch_size = min(adaptive_params['batch_size'], len(self.content_crawl_queue))
        
        # 批量处理队列中的域名
        batch_domains = []
        for _ in range(batch_size):
            if self.content_crawl_queue:
                domain = self.content_crawl_queue.popleft()
                batch_domains.append(domain)
        
        # 并发执行内容爬取
        crawl_tasks = []
        for domain in batch_domains:
            if domain in self.all_domains and not self.all_domains[domain].content_crawled:
                # 动态配置爬取参数
                enhanced_config = config.copy()
                enhanced_config.update({
                    'max_concurrent': adaptive_params['concurrent_limit'],
                    'max_pages_per_domain': min(config.get('max_pages_per_domain', 50), 100)
                })
                crawl_tasks.append(self._crawl_domain_content(domain, enhanced_config))
        
        total_pages = 0
        total_links = 0
        
        if crawl_tasks:
            crawl_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
            
            # 处理爬取结果
            for i, result in enumerate(crawl_results):
                domain = batch_domains[i]
                if isinstance(result, Exception):
                    self.iteration_controller.record_error(type(result).__name__, str(result))
                    self.logger.warning(f"域名 {domain} 内容爬取失败: {result}")
                else:
                    # 标记已完成内容爬取
                    if domain in self.all_domains:
                        self.all_domains[domain].content_crawled = True
                        if isinstance(result, list) and result:  # 确保是列表
                            self.all_domains[domain].is_accessible = True
                            self.all_domains[domain].page_count = len(result)
                            total_pages += len(result)
                            
                            # 提取所有链接
                            all_links = []
                            for crawl_result in result:
                                if hasattr(crawl_result, 'found_links'):
                                    all_links.extend(crawl_result.found_links)
                            
                            self.all_domains[domain].found_links = all_links
                            total_links += len(all_links)
        
        self.logger.info(f"内容爬取阶段完成: 爬取 {total_pages} 个页面，发现 {total_links} 个链接")
        return total_pages, total_links
    
    async def _enhanced_domain_extraction_phase(self) -> int:
        """增强的域名提取和队列更新阶段，返回新发现的域名数量"""
        self.logger.info("增强域名提取阶段: 从已爬取内容中提取新域名")
        
        # 从所有已爬取的链接中提取域名
        all_found_links = []
        for domain_info in self.all_domains.values():
            if domain_info.content_crawled and domain_info.found_links:
                all_found_links.extend(domain_info.found_links)
        
        if not all_found_links:
            return 0
        
        self.logger.debug(f"开始从 {len(all_found_links)} 个链接中提取域名")
        
        # 提取域名
        initial_domain_count = len(self.all_domains)
        extracted_domains = await self._extract_domains_from_links(all_found_links)
        
        # 添加新域名到池中
        for domain, domain_type, source_urls in extracted_domains:
            await self._add_domain_to_pool(domain, domain_type, 'enhanced_link_extraction', source_urls)
        
        new_domains_count = len(self.all_domains) - initial_domain_count
        self.logger.info(f"域名提取阶段完成: 新发现 {new_domains_count} 个域名")
        
        return new_domains_count
    
    async def _subdomain_discovery_phase(self, config: Dict[str, Any]):
        """子域名发现阶段"""
        if not self.subdomain_discovery_queue:
            return
            
        self.logger.info(f"子域名发现阶段: 队列中有 {len(self.subdomain_discovery_queue)} 个域名")
        
        # 批量处理队列中的域名
        batch_size = min(self.max_domains_per_iteration, len(self.subdomain_discovery_queue))
        batch_domains = []
        
        for _ in range(batch_size):
            if self.subdomain_discovery_queue:
                domain = self.subdomain_discovery_queue.popleft()
                batch_domains.append(domain)
        
        # 并发执行子域名发现
        discovery_tasks = []
        for domain in batch_domains:
            if domain in self.all_domains and not self.all_domains[domain].subdomain_discovered:
                discovery_tasks.append(self._discover_subdomains_for_domain(domain))
        
        if discovery_tasks:
            discovery_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
            
            # 处理发现结果
            for i, result in enumerate(discovery_results):
                domain = batch_domains[i]
                if isinstance(result, Exception):
                    self.logger.warning(f"域名 {domain} 子域名发现失败: {result}")
                else:
                    # 标记已完成子域名发现
                    if domain in self.all_domains:
                        self.all_domains[domain].subdomain_discovered = True
                        
                    # 处理新发现的子域名
                    if isinstance(result, list):  # 确保是列表
                        for subdomain_result in result:
                            await self._add_domain_to_pool(
                                subdomain_result.subdomain,
                                'target_subdomain',
                                subdomain_result.method if hasattr(subdomain_result, 'method') else 'subdomain_discovery',
                                [f"subdomain_of_{domain}"]
                            )
    
    async def _content_crawling_phase(self, config: Dict[str, Any]):
        """内容爬取阶段"""
        if not self.content_crawl_queue:
            return
            
        self.logger.info(f"内容爬取阶段: 队列中有 {len(self.content_crawl_queue)} 个域名")
        
        # 批量处理队列中的域名
        batch_size = min(self.max_domains_per_iteration, len(self.content_crawl_queue))
        batch_domains = []
        
        for _ in range(batch_size):
            if self.content_crawl_queue:
                domain = self.content_crawl_queue.popleft()
                batch_domains.append(domain)
        
        # 并发执行内容爬取
        crawl_tasks = []
        for domain in batch_domains:
            if domain in self.all_domains and not self.all_domains[domain].content_crawled:
                crawl_tasks.append(self._crawl_domain_content(domain, config))
        
        if crawl_tasks:
            crawl_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
            
            # 处理爬取结果
            for i, result in enumerate(crawl_results):
                domain = batch_domains[i]
                if isinstance(result, Exception):
                    self.logger.warning(f"域名 {domain} 内容爬取失败: {result}")
                else:
                    # 标记已完成内容爬取
                    if domain in self.all_domains:
                        self.all_domains[domain].content_crawled = True
                        if isinstance(result, list) and result:  # 确保是列表
                            self.all_domains[domain].is_accessible = True
                            self.all_domains[domain].page_count = len(result)
                            # 提取所有链接
                            all_links = []
                            for crawl_result in result:
                                if hasattr(crawl_result, 'found_links'):
                                    all_links.extend(crawl_result.found_links)
                            self.all_domains[domain].found_links = all_links
    
    async def _domain_extraction_phase(self):
        """域名提取和队列更新阶段"""
        self.logger.info("域名提取阶段: 从已爬取内容中提取新域名")
        
        # 从所有已爬取的链接中提取域名
        all_found_links = []
        for domain_info in self.all_domains.values():
            if domain_info.content_crawled and domain_info.found_links:
                all_found_links.extend(domain_info.found_links)
        
        # 提取域名
        extracted_domains = await self._extract_domains_from_links(all_found_links)
        
        # 添加新域名到池中
        for domain, domain_type, source_urls in extracted_domains:
            await self._add_domain_to_pool(domain, domain_type, 'link_extraction', source_urls)
    
    async def _discover_subdomains_for_domain(self, domain: str) -> List[SubdomainResult]:
        """为指定域名发现子域名"""
        try:
            self.logger.debug(f"开始增强子域名发现: {domain}")
            
            # 使用增强的子域名发现引擎
            config = {
                'search_engine_enabled': True,
                'api_query_enabled': True,
                'passive_dns_enabled': False,
                'verify_accessibility': True,
                'max_subdomains': 500
            }
            
            enhanced_results = await self.enhanced_subdomain_engine.discover_all_enhanced(domain, config)
            
            # 转换为标准格式
            standard_results = []
            for result in enhanced_results:
                # 转换为SubdomainResult格式
                subdomain_result = SubdomainResult(
                    subdomain=result.subdomain,
                    method=result.discovery_method
                )
                # 手动设置其他属性
                subdomain_result.ip_addresses = result.ip_addresses
                subdomain_result.is_accessible = result.is_accessible
                subdomain_result.response_code = result.response_code
                subdomain_result.response_time = result.response_time
                standard_results.append(subdomain_result)
            
            self.logger.debug(f"域名 {domain} 增强子域名发现完成: {len(standard_results)} 个结果")
            return standard_results
            
        except Exception as e:
            self.logger.error(f"域名 {domain} 增强子域名发现异常: {e}")
            # 回退到传统方法
            return await self._fallback_subdomain_discovery(domain)
    
    async def _crawl_domain_content(self, domain: str, config: Dict[str, Any]) -> List[Any]:
        """爬取域名内容"""
        try:
            self.logger.debug(f"开始智能内容爬取: {domain}")
            
            # 配置智能爬取参数
            crawl_config = {
                'max_pages_per_domain': config.get('max_pages_per_domain', 50),
                'max_concurrent': config.get('max_concurrent', 10),
                'timeout_per_page': config.get('timeout_per_page', 30)
            }
            
            # 执行智能爬取
            crawling_result = await self.smart_crawler.crawl_domain(domain, config=crawl_config)
            
            # 转换结果格式以兼容现有代码
            converted_results = []
            for page in crawling_result.pages:
                # 创建兼容的结果对象
                crawl_result = type('CrawlResult', (), {
                    'url': page.url,
                    'status_code': page.status_code,
                    'title': page.title,
                    'found_links': page.found_links,
                    'found_domains': page.found_domains,
                    'content_length': page.content_length,
                    'response_time': page.response_time,
                    'error_message': page.error_message
                })()
                converted_results.append(crawl_result)
            
            self.logger.debug(f"域名 {domain} 智能内容爬取完成: {len(converted_results)} 个页面")
            return converted_results
            
        except Exception as e:
            self.logger.error(f"域名 {domain} 智能内容爬取异常: {e}")
            return []
    
    async def _extract_domains_from_links(self, links: List[str]) -> List[Tuple[str, str, List[str]]]:
        """从链接中提取域名"""
        try:
            # 使用增强的域名提取器进行批量提取
            self.logger.debug(f"开始从 {len(links)} 个链接中提取域名")
            
            # 构建虚拟HTML用于提取
            virtual_html = '<html><body>'
            for link in links[:1000]:  # 限制处理数量避免过大
                virtual_html += f'<a href="{link}">{link}</a>\n'
            virtual_html += '</body></html>'
            
            # 使用域名提取器分析
            extraction_result = await self.domain_extractor.extract_from_html('virtual://links', virtual_html)
            
            # 转换结果格式
            extracted_domains = []
            for domain_info in extraction_result.extracted_domains:
                domain_type = domain_info.domain_type
                if domain_type == 'target_subdomain':
                    final_type = 'target_subdomain'
                else:
                    final_type = 'third_party'
                
                extracted_domains.append((
                    domain_info.domain,
                    final_type,
                    domain_info.source_links[:10]  # 限制源链接数量
                ))
            
            self.logger.debug(f"域名提取完成: 发现 {len(extracted_domains)} 个域名")
            return extracted_domains
            
        except Exception as e:
            self.logger.warning(f"增强域名提取失败，使用传统方法: {e}")
            return await self._fallback_extract_domains_from_links(links)
    
    async def _add_domain_to_pool(self, domain: str, domain_type: str, discovery_method: str, source_urls: List[str]):
        """添加域名到全局池"""
        if domain in self.all_domains:
            # 域名已存在，更新源URL
            self.all_domains[domain].source_urls.extend(source_urls)
            return
        
        if len(self.all_domains) >= self.max_total_domains:
            self.logger.warning(f"已达到最大域名数量限制: {self.max_total_domains}")
            return
        
        # 添加新域名
        domain_info = DomainInfo(
            domain=domain,
            domain_type=domain_type,
            discovered_at=datetime.utcnow(),
            discovery_method=discovery_method,
            source_urls=source_urls
        )
        
        self.all_domains[domain] = domain_info
        
        # 添加到相应队列
        if domain_type == 'target_subdomain' or domain_type == 'third_party':
            # 所有域名都需要进行子域名发现
            self.subdomain_discovery_queue.append(domain)
            # 所有域名都需要进行内容爬取
            self.content_crawl_queue.append(domain)
            # 第三方域名和可疑域名需要AI分析
            if domain_type == 'third_party':
                self.ai_analysis_queue.append(domain)
        
        self.logger.debug(f"新域名入池: {domain} ({domain_type})")
    
    async def _enhanced_third_party_analysis(self, config: Dict[str, Any]):
        """增强的第三方域名分析阶段"""
        # 收集所有第三方域名
        third_party_domains = []
        for domain, domain_info in self.all_domains.items():
            if (domain_info.domain_type == 'third_party' and 
                not domain_info.ai_analyzed):
                third_party_domains.append({
                    'domain': domain,
                    'source_urls': domain_info.source_urls,
                    'discovery_method': domain_info.discovery_method
                })
        
        if not third_party_domains:
            self.logger.info("无第三方域名需要分析")
            return
        
        self.logger.info(f"开始增强第三方域名分析: {len(third_party_domains)} 个域名")
        
        # 配置访问策略
        access_policy = {
            'max_concurrent_access': min(config.get('max_concurrent_ai_calls', 5), 10),
            'request_delay_range': (1.0, 2.0),
            'timeout_per_domain': config.get('timeout_per_page', 30),
            'enable_screenshot': config.get('content_capture_enabled', True),
            'enable_content_analysis': config.get('ai_analysis_enabled', True)
        }
        
        self.third_party_access_manager.configure_access_policy(access_policy)
        
        # 添加域名到访问队列
        self.third_party_access_manager.add_domains_to_queue(third_party_domains)
        
        # 处理访问队列
        access_summary = await self.third_party_access_manager.process_access_queue()
        
        # 更新域名信息
        for domain in third_party_domains:
            domain_name = domain['domain']
            if domain_name in self.all_domains:
                domain_info = self.all_domains[domain_name]
                domain_info.ai_analyzed = True
                
                # 更新访问结果
                if domain_name in self.third_party_access_manager.completed_domains:
                    access_result = self.third_party_access_manager.completed_domains[domain_name]
                    domain_info.is_accessible = access_result.success
                    domain_info.screenshot_path = access_result.analysis_result.screenshot_path if access_result.analysis_result else None
                    domain_info.risk_level = access_result.risk_assessment or 'low'
                    
                    # 统计高风险域名
                    if domain_info.risk_level in ['high', 'critical']:
                        self.total_violations_found += 1
        
        # 记录统计信息
        self.logger.info(f"第三方域名分析完成: "
                        f"成功 {access_summary['processing_summary']['successful_accesses']}, "
                        f"失败 {access_summary['processing_summary']['failed_accesses']}, "
                        f"截图 {access_summary['processing_summary']['screenshots_captured']}, "
                        f"高风险 {self.total_violations_found}")
    
    async def _should_stop_iteration(self, new_domains_count: int, iteration_count: int) -> bool:
        """判断是否应该停止迭代"""
        # 停止条件1: 没有新域名发现
        if new_domains_count == 0:
            self.logger.info("停止迭代: 没有新域名发现")
            return True
        
        # 停止条件2: 达到最大迭代次数
        max_iterations = 50  # 最大迭代次数
        if iteration_count >= max_iterations:
            self.logger.info(f"停止迭代: 达到最大迭代次数 {max_iterations}")
            return True
        
        # 停止条件3: 达到最大域名数量
        if len(self.all_domains) >= self.max_total_domains:
            self.logger.info(f"停止迭代: 达到最大域名数量 {self.max_total_domains}")
            return True
        
        # 停止条件4: 队列为空
        if (not self.subdomain_discovery_queue and 
            not self.content_crawl_queue and 
            not self.ai_analysis_queue):
            self.logger.info("停止迭代: 所有队列为空")
            return True
        
        return False
    
    async def _generate_final_result(self, total_duration: float) -> Dict[str, Any]:
        """生成最终结果"""
        # 统计各类域名
        target_subdomains = [d for d in self.all_domains.values() if d.domain_type == 'target_subdomain']
        third_party_domains = [d for d in self.all_domains.values() if d.domain_type == 'third_party']
        
        accessible_domains = [d for d in self.all_domains.values() if d.is_accessible]
        high_risk_domains = [d for d in self.all_domains.values() if d.risk_level in ['high', 'critical']]
        
        # 计算总页面数
        total_pages = sum(d.page_count for d in self.all_domains.values())
        
        result = {
            'task_id': self.task_id,
            'target_domain': self.target_domain,
            'total_duration': total_duration,
            'iterations_completed': len(self.iteration_results),
            
            # 域名统计
            'domain_statistics': {
                'total_domains': len(self.all_domains),
                'target_subdomains': len(target_subdomains),
                'third_party_domains': len(third_party_domains),
                'accessible_domains': len(accessible_domains),
                'high_risk_domains': len(high_risk_domains),
                'total_pages_crawled': total_pages
            },
            
            # 发现方法统计
            'discovery_methods': self._get_discovery_method_stats(),
            
            # 迭代详情
            'iteration_results': [
                {
                    'iteration': r.iteration_number,
                    'new_domains': r.new_domains_found,
                    'total_domains': r.total_domains,
                    'duration': r.duration_seconds
                }
                for r in self.iteration_results
            ],
            
            # 域名列表
            'discovered_domains': [
                {
                    'domain': d.domain,
                    'type': d.domain_type,
                    'discovery_method': d.discovery_method,
                    'is_accessible': d.is_accessible,
                    'risk_level': d.risk_level,
                    'page_count': d.page_count,
                    'ai_analyzed': d.ai_analyzed
                }
                for d in self.all_domains.values()
            ]
        }
        
    async def _generate_enhanced_final_result(self, total_duration: float) -> Dict[str, Any]:
        """生成增强的最终结果"""
        # 获取基本结果
        base_result = await self._generate_final_result(total_duration)
        
        # 添加迭代控制器的统计信息
        iteration_summary = self.iteration_controller.get_iteration_summary()
        
        # 增强结果
        enhanced_result = {
            **base_result,
            'infinite_iteration_metrics': iteration_summary,
            'adaptive_optimization': {
                'final_batch_size': self.max_domains_per_iteration,
                'final_concurrent_limit': self.concurrent_crawlers,
                'total_optimizations': len(self.iteration_controller.performance_history)
            },
            'quality_metrics': {
                'discovery_efficiency': iteration_summary.get('average_discovery_rate', 0),
                'error_rate': iteration_summary.get('total_errors', 0) / max(iteration_summary.get('total_iterations', 1), 1),
                'resource_utilization': {
                    'peak_memory_mb': iteration_summary.get('performance_metrics', {}).get('peak_memory_usage_mb', 0),
                    'avg_cpu_percent': iteration_summary.get('performance_metrics', {}).get('average_cpu_usage_percent', 0)
                }
            }
        }
        
        return enhanced_result
    
    def _get_discovery_method_stats(self) -> Dict[str, int]:
        """获取发现方法统计"""
        method_stats = defaultdict(int)
        for domain_info in self.all_domains.values():
            method_stats[domain_info.discovery_method] += 1
        return dict(method_stats)
    
    def _is_valid_domain(self, domain: str) -> bool:
        """验证域名是否有效"""
        if not domain or len(domain) > 253:
            return False
        
        # 基本域名格式验证
        domain_pattern = re.compile(
            r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        )
        
        return bool(domain_pattern.match(domain))
    
    def _is_target_subdomain(self, domain: str) -> bool:
        """判断是否为目标域名的子域名"""
        if domain == self.target_domain:
            return True
        return domain.endswith(f'.{self.target_domain}')
    
    def get_domain_pool_status(self) -> Dict[str, Any]:
        """获取域名池状态"""
        return {
            'total_domains': len(self.all_domains),
            'subdomain_discovery_queue': len(self.subdomain_discovery_queue),
            'content_crawl_queue': len(self.content_crawl_queue),
            'ai_analysis_queue': len(self.ai_analysis_queue),
            'processed_domains': {
                'subdomain_discovered': len([d for d in self.all_domains.values() if d.subdomain_discovered]),
                'content_crawled': len([d for d in self.all_domains.values() if d.content_crawled]),
                'ai_analyzed': len([d for d in self.all_domains.values() if d.ai_analyzed])
            }
        }
    
    async def _fallback_subdomain_discovery(self, domain: str) -> List[SubdomainResult]:
        """备用的传统子域名发现方法"""
        try:
            self.logger.debug(f"使用传统子域名发现方法: {domain}")
            
            all_results = []
            
            # 方法1: DNS查询
            try:
                dns_results = await self.dns_method.discover(domain, self.logger)
                all_results.extend(dns_results)
            except Exception as e:
                self.logger.warning(f"DNS查询失败 {domain}: {e}")
            
            # 方法2: 证书透明度查询
            try:
                ct_results = await self.ct_method.discover(domain, self.logger)
                all_results.extend(ct_results)
            except Exception as e:
                self.logger.warning(f"证书透明度查询失败 {domain}: {e}")
            
            # 方法3: 字典爆破（仅对目标域名）
            if domain == self.target_domain or domain.endswith(f'.{self.target_domain}'):
                try:
                    brute_results = await self.brute_method.discover(domain, self.logger, max_subdomains=100)
                    all_results.extend(brute_results)
                except Exception as e:
                    self.logger.warning(f"字典爆破失败 {domain}: {e}")
            
            self.logger.debug(f"传统子域名发现完成 {domain}: {len(all_results)} 个结果")
            return all_results
            
        except Exception as e:
            self.logger.error(f"传统子域名发现失败 {domain}: {e}")
            return []
    
    async def _fallback_extract_domains_from_links(self, links: List[str]) -> List[Tuple[str, str, List[str]]]:
        """备用的传统域名提取方法"""
        domain_sources = defaultdict(list)
        
        for link in links:
            try:
                parsed = urlparse(link)
                if parsed.netloc:
                    domain = parsed.netloc.lower()
                    # 清理端口号
                    if ':' in domain:
                        domain = domain.split(':')[0]
                    
                    if self._is_valid_domain(domain):
                        domain_sources[domain].append(link)
            except Exception:
                continue
        
        # 分类域名并返回
        extracted_domains = []
        for domain, source_links in domain_sources.items():
            if self._is_target_subdomain(domain):
                domain_type = 'target_subdomain'
            else:
                domain_type = 'third_party'
            
            extracted_domains.append((domain, domain_type, source_links[:10]))  # 限制源链接数量
        
        return extracted_domains
    
    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """获取增强的统计信息"""
        base_stats = self.get_domain_pool_status()
        
        # 添加新的统计信息
        try:
            extraction_stats = self.domain_extractor.get_extraction_statistics()
            crawling_stats = self.smart_crawler.get_crawling_statistics()
        except Exception as e:
            self.logger.warning(f"获取统计信息失败: {e}")
            extraction_stats = {}
            crawling_stats = {}
        
        enhanced_stats = {
            **base_stats,
            'extraction_statistics': extraction_stats,
            'crawling_statistics': crawling_stats,
            'iteration_count': len(self.iteration_results),
            'total_violations': self.total_violations_found,
            'performance_metrics': {
                'avg_iteration_duration': sum(r.duration_seconds for r in self.iteration_results) / max(len(self.iteration_results), 1),
                'domains_per_iteration': sum(r.new_domains_found for r in self.iteration_results) / max(len(self.iteration_results), 1)
            }
        }
        
        return enhanced_stats
    
    def save_crawling_results(self, output_dir: str = 'crawling_results'):
        """保存爬取结果到文件"""
        try:
            import os
            from datetime import datetime
            
            # 创建输出目录
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存域名列表
            domains_file = os.path.join(output_dir, f'domains_{self.target_domain}_{timestamp}.txt')
            with open(domains_file, 'w', encoding='utf-8') as f:
                f.write(f"# 无限迭代爬虫结果 - {self.target_domain}\n")
                f.write(f"# 生成时间: {datetime.now()}\n")
                f.write(f"# 总域名数: {len(self.all_domains)}\n\n")
                
                for domain, info in self.all_domains.items():
                    f.write(f"{domain} [{info.domain_type}] - {info.discovery_method}\n")
            
            # 保存统计信息
            stats_file = os.path.join(output_dir, f'statistics_{self.target_domain}_{timestamp}.json')
            import json
            with open(stats_file, 'w', encoding='utf-8') as f:
                stats = self.get_enhanced_statistics()
                json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
            
            # 让智能爬虫保存详细结果
            try:
                crawler_results_file = os.path.join(output_dir, f'crawler_results_{self.target_domain}_{timestamp}.txt')
                self.smart_crawler.save_results_to_file(crawler_results_file)
            except Exception as e:
                self.logger.warning(f"保存爬虫详细结果失败: {e}")
            
            self.logger.info(f"爬取结果已保存到: {output_dir}")
            
        except Exception as e:
            self.logger.error(f"保存爬取结果失败: {e}")
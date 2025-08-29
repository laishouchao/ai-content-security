import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.core.logging import TaskLogger
from app.core.config import settings
from app.engines.subdomain_discovery import SubdomainDiscoveryEngine, SubdomainResult
from app.engines.link_crawler import LinkCrawlerEngine, CrawlResult
from app.engines.domain_discovery_engine import ContinuousDomainDiscoveryEngine  # 新的循环发现引擎
from app.engines.third_party_identifier import ThirdPartyIdentifierEngine, ThirdPartyDomainResult
from app.engines.content_capture import ContentCaptureEngine, ContentResult
from app.engines.ai_analysis import AIAnalysisEngine, AIAnalysisResult
from app.engines.optimized_screenshot_service import OptimizedScreenshotService
from app.websocket.handlers import task_monitor


class ScanExecutionResult:
    """扫描执行结果"""
    
    def __init__(self):
        self.task_id = ""
        self.target_domain = ""
        self.status = "pending"
        self.progress = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        # 执行结果
        self.subdomains: List[SubdomainResult] = []
        self.crawl_results: List[CrawlResult] = []
        self.domain_records: List[ThirdPartyDomainResult] = []
        self.content_results: List[ContentResult] = []
        self.violation_records = []
        
        # 添加全量链接存储
        self.all_crawled_links: List[str] = []  # 全量存储爬取到的链接
        
        # 统计信息
        self.statistics: Dict[str, Any] = {
            'total_subdomains': 0,
            'accessible_subdomains': 0,
            'total_pages_crawled': 0,
            'total_links_found': 0,
            'total_resources_found': 0,
            'total_domain_records': 0,
            'high_risk_domains': 0,
            'total_screenshots': 0,
            'total_violations': 0,
            'ai_analysis_completed': 0,
            'execution_duration': 0
        }
        
        # 错误信息
        self.errors = []
        self.warnings = []


class ScanTaskExecutor:
    """扫描任务执行器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 初始化引擎
        self.subdomain_engine = SubdomainDiscoveryEngine(task_id, user_id)
        self.crawler_engine = LinkCrawlerEngine(task_id, user_id)
        self.domain_discovery_engine = ContinuousDomainDiscoveryEngine(task_id, user_id, "")  # 目标域名在execute_scan中设置
        self.identifier_engine = ThirdPartyIdentifierEngine(task_id, user_id)
        self.capture_engine = ContentCaptureEngine(task_id, user_id)
        self.ai_engine = None  # 将在需要时初始化
        self.domain_classifier = None  # 将在需要时初始化
        
        # 执行状态
        self.is_running = False
        self.is_cancelled = False
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self.progress_callback = callback
    
    async def execute_scan(
        self, 
        target_domain: str, 
        config: Dict[str, Any]
    ) -> ScanExecutionResult:
        """执行完整的域名扫描"""
        self.is_running = True
        self.is_cancelled = False
        
        result = ScanExecutionResult()
        result.task_id = self.task_id
        result.target_domain = target_domain
        result.start_time = datetime.utcnow()
        result.status = "running"
        
        try:
            self.logger.info(f"开始执行域名扫描任务: {target_domain}")
            await self._update_progress(result, 0, "初始化扫描任务")
            
            # 初始化域名发现引擎的目标域名
            self.domain_discovery_engine.target_domain = target_domain
            import tldextract
            self.domain_discovery_engine.target_parts = tldextract.extract(target_domain)
            self.domain_discovery_engine.target_registered_domain = self.domain_discovery_engine.target_parts.registered_domain.lower()
            
            # 新的统一流程：循环域名发现和爬取 (0-80%)
            if not self.is_cancelled and config.get('continuous_discovery_enabled', True):
                await self._execute_continuous_domain_discovery(result, config)
                await self._update_progress(result, 80, f"循环域名发现完成: {result.statistics.get('total_domains', 0)} 个域名")
            
            # AI分析 (80-100%)
            if not self.is_cancelled and config.get('ai_analysis_enabled', True):
                await self._execute_ai_analysis(result, config)
                await self._update_progress(result, 100, f"AI分析完成: {len(result.violation_records)} 个违规")
            
            # 计算最终统计
            await self._calculate_final_statistics(result)
            
            if self.is_cancelled:
                result.status = "cancelled"
                self.logger.info("扫描任务已取消")
            else:
                result.status = "completed"
                self.logger.info("扫描任务执行完成")
                
        except Exception as e:
            result.status = "failed"
            result.errors.append(f"执行异常: {str(e)}")
            self.logger.error(f"扫描任务执行失败: {e}")
            
        finally:
            result.end_time = datetime.utcnow()
            if result.start_time:
                duration = (result.end_time - result.start_time).total_seconds()
                result.statistics['execution_duration'] = int(duration)
            
            self.is_running = False
        
        return result
    
    async def _execute_subdomain_discovery(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行子域名发现"""
        try:
            self.logger.info("开始子域名发现阶段")
            
            subdomains = await self.subdomain_engine.discover_all(result.target_domain, config)
            result.subdomains = subdomains
            
            # 更新统计
            result.statistics['total_subdomains'] = len(subdomains)
            result.statistics['accessible_subdomains'] = sum(1 for s in subdomains if s.is_accessible)
            
            self.logger.info(f"子域名发现完成: 总计 {len(subdomains)} 个，可访问 {result.statistics['accessible_subdomains']} 个")
            
            # 立即保存子域名记录到数据库
            if subdomains:
                await self._save_subdomain_results(result)
            
        except Exception as e:
            error_msg = f"子域名发现失败: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
    
    async def _execute_continuous_domain_discovery(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行循环域名发现"""
        try:
            self.logger.info("开始循环域名发现阶段")
            
            # 执行循环发现
            discovery_stats = await self.domain_discovery_engine.start_continuous_discovery(config)
            
            # 更新统计信息
            result.statistics.update({
                'total_domains': discovery_stats.get('total_domains', 0),
                'target_main_count': discovery_stats.get('target_main_count', 0),
                'target_subdomain_count': discovery_stats.get('target_subdomain_count', 0),
                'third_party_count': discovery_stats.get('third_party_count', 0),
                'unknown_count': discovery_stats.get('unknown_count', 0),
                'discovery_rounds': discovery_stats.get('total_rounds', 0),
                'total_pages_crawled': discovery_stats.get('total_pages_crawled', 0)
            })
            
            # 从数据库加载最新的域名数据到结果中（为了兼容性）
            await self._load_domains_from_database(result)
            
            self.logger.info(f"循环域名发现完成: 总计 {discovery_stats.get('total_domains', 0)} 个域名")
            
        except Exception as e:
            error_msg = f"循环域名发现失败: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
    
    async def _load_domains_from_database(self, result: ScanExecutionResult):
        """从数据库加载域名数据（为了兼容性）"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.domain import DomainRecord, DomainCategory
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as db:
                # 查询所有域名记录
                query = select(DomainRecord).where(DomainRecord.task_id == result.task_id)
                domain_result = await db.execute(query)
                domain_records = domain_result.scalars().all()
                
                # 转换为兼容格式（为了保持前端兼容性）
                result.subdomains = []
                result.domain_records = []
                
                for domain_record in domain_records:
                    if domain_record.category in [DomainCategory.TARGET_MAIN, DomainCategory.TARGET_SUBDOMAIN]:
                        # 转换为子域名格式
                        from app.engines.subdomain_discovery import SubdomainResult
                        subdomain_result = SubdomainResult(
                            subdomain=str(domain_record.domain),
                            method=str(domain_record.discovery_method),
                            ip_address=str(domain_record.ip_address) if domain_record.ip_address is not None else None
                        )
                        # 设置其他属性
                        subdomain_result.is_accessible = bool(domain_record.is_accessible)
                        subdomain_result.response_code = int(domain_record.response_code) if domain_record.response_code is not None else None  # type: ignore
                        subdomain_result.response_time = float(domain_record.response_time) if domain_record.response_time is not None else None  # type: ignore
                        result.subdomains.append(subdomain_result)
                    
                    elif str(domain_record.category) == DomainCategory.THIRD_PARTY:
                        # 转换为第三方域名格式
                        from app.engines.third_party_identifier import ThirdPartyDomainResult
                        third_party_result = ThirdPartyDomainResult(
                            domain=str(domain_record.domain),
                            domain_type="third_party",
                            risk_level=str(domain_record.risk_level),
                            found_on_urls=list(domain_record.found_on_urls) if domain_record.found_on_urls is not None else [],  # type: ignore
                            confidence_score=float(domain_record.confidence_score) if domain_record.confidence_score is not None else 0.0,  # type: ignore
                            description=f"从循环发现中识别的第三方域名: {domain_record.domain}",
                            category_tags=["continuous_discovery", "third_party"]
                        )
                        result.domain_records.append(third_party_result)
                
                self.logger.info(f"已加载域名数据: 子域名={len(result.subdomains)}, 第三方域名={len(result.domain_records)}")
                
        except Exception as e:
            self.logger.error(f"加载域名数据失败: {e}")
    
    async def _execute_improved_link_crawling(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行改进的链接爬取"""
        try:
            self.logger.info("开始改进的链接爬取阶段")
            
            # 获取配置
            max_iterations = config.get('max_crawl_iterations', 10)
            max_pages_per_domain = config.get('max_pages_per_domain', 100)
            
            # 准备初始URL（目标域名和已发现的子域名）
            initial_urls = [f"https://{result.target_domain}", f"http://{result.target_domain}"]
            
            # 添加可访问的子域名
            for subdomain in result.subdomains:
                if subdomain.is_accessible:
                    initial_urls.extend([
                        f"https://{subdomain.subdomain}",
                        f"http://{subdomain.subdomain}"
                    ])
            
            # 去重
            all_crawled_urls = set(initial_urls)
            all_found_links = set()
            
            # 迭代爬取
            current_iteration = 0
            urls_to_crawl = set(initial_urls)
            all_crawl_results = []
            
            while current_iteration < max_iterations and urls_to_crawl and len(all_crawl_results) < max_pages_per_domain:
                self.logger.info(f"开始第 {current_iteration + 1} 轮爬取，待处理URL数量: {len(urls_to_crawl)}")
                
                # 当前轮次的URL
                current_urls = list(urls_to_crawl)[:max_pages_per_domain - len(all_crawl_results)]
                urls_to_crawl.clear()
                
                # 执行当前轮次的爬取
                crawl_results = await self.crawler_engine.crawl_domain(
                    result.target_domain, current_urls, config
                )
                
                # 添加到总结果中
                all_crawl_results.extend(crawl_results)
                
                # 从爬取结果中提取新的链接
                for crawl_result in crawl_results:
                    # 提取所有发现的链接
                    all_found_links.update(crawl_result.links)
                    all_found_links.update(crawl_result.resources)
                    all_found_links.update(crawl_result.forms)
                
                # 从所有发现的链接中提取属于目标域名的子域名
                new_subdomains = self._extract_subdomains_from_links(all_found_links, result.target_domain)
                
                # 将新发现的子域名添加到结果中（避免重复）
                existing_subdomains = {s.subdomain for s in result.subdomains}
                for new_sub in new_subdomains:
                    if new_sub not in existing_subdomains:
                        # 创建新的子域名结果
                        sub_result = SubdomainResult(new_sub, "link_crawling")
                        result.subdomains.append(sub_result)
                        existing_subdomains.add(new_sub)
                        
                        # 将新子域名添加到待爬取URL中
                        urls_to_crawl.add(f"https://{new_sub}")
                        urls_to_crawl.add(f"http://{new_sub}")
                
                # 从所有发现的链接中提取新的域名并进行正确分类
                for link in all_found_links:
                    extracted_domain = self._extract_domain_from_url(link)
                    if not extracted_domain:
                        continue
                    
                    # 使用强化的子域名检查逻辑
                    target_domain_lower = result.target_domain.lower()
                    is_target_subdomain = self._is_target_domain_or_subdomain_advanced(extracted_domain, target_domain_lower)
                    
                    if is_target_subdomain:
                        # 这是目标域名或子域名
                        if extracted_domain != target_domain_lower:  # 排除主域名本身
                            existing_subdomains = {s.subdomain for s in result.subdomains}
                            if extracted_domain not in existing_subdomains:
                                # 创建新的子域名结果
                                sub_result = SubdomainResult(extracted_domain, "link_crawling")
                                result.subdomains.append(sub_result)
                                existing_subdomains.add(extracted_domain)
                                
                                # 将新子域名添加到待爬取URL中
                                urls_to_crawl.add(f"https://{extracted_domain}")
                                urls_to_crawl.add(f"http://{extracted_domain}")
                                
                                self.logger.info(f"通过链接爬取发现新子域名: {extracted_domain}")
                                
                                # 立即保存新发现的子域名到数据库
                                await self._save_single_subdomain_result(result.task_id, sub_result)
                        
                        # 将目标域名和子域名的URL添加到待爬取队列中
                        if link not in all_crawled_urls:
                            urls_to_crawl.add(link)
                            all_crawled_urls.add(link)
                        
                        self.logger.debug(f"识别为目标域名或子域名: {extracted_domain}")
                    else:
                        # 再次使用强化逻辑确认这确实是第三方域名
                        if not self._is_target_domain_or_subdomain_advanced(extracted_domain, target_domain_lower):
                            # 这是第三方域名，使用域名分类器进行详细分类
                            if self.domain_classifier is None:
                                # 初始化域名分类器
                                from app.engines.domain_classifier import DomainClassifier
                                self.domain_classifier = DomainClassifier(self.task_id, self.user_id, result.target_domain)
                            
                            # 进行域名分类
                            classification = await self.domain_classifier.classify_domain(extracted_domain)
                            
                            # 只有分类器确认为第三方域名才添加
                            if classification.domain_type.value in ['third_party', 'unknown', 'cdn', 'analytics', 'advertising', 'social', 'api']:
                                existing_third_party = {d.domain for d in result.domain_records}
                                if extracted_domain not in existing_third_party:
                                    # 创建第三方域名结果
                                    from app.engines.third_party_identifier import ThirdPartyDomainResult
                                    third_party_result = ThirdPartyDomainResult(
                                        domain=extracted_domain,
                                        domain_type=classification.domain_type.value,  # 使用分类器的结果
                                        risk_level="low",       # 后续会进行风险评估
                                        found_on_urls=[link],
                                        confidence_score=classification.confidence_score,
                                        description=f"从链接中发现的第三方域名: {extracted_domain} ({classification.domain_type.value})",
                                        category_tags=["discovered_from_crawling", classification.domain_type.value]
                                    )
                                    result.domain_records.append(third_party_result)
                                    
                                    self.logger.debug(f"发现第三方域名: {extracted_domain} (类型: {classification.domain_type.value})")
                            else:
                                self.logger.warning(f"分类器将 {extracted_domain} 识别为 {classification.domain_type.value}，应为子域名但被误分类")
                        else:
                            self.logger.debug(f"二次确认 {extracted_domain} 为目标域名相关，跳过第三方域名处理")
                
                current_iteration += 1
                
                # 防止过快请求
                await asyncio.sleep(0.1)
            
            result.crawl_results = all_crawl_results
            
            # 获取全量链接
            result.all_crawled_links = self.crawler_engine.all_crawled_links
            
            # 更新子域名统计信息（包括新发现的子域名）
            result.statistics['total_subdomains'] = len(result.subdomains)
            result.statistics['accessible_subdomains'] = sum(1 for s in result.subdomains if s.is_accessible)
            
            # 获取爬取统计
            crawl_stats = await self.crawler_engine.get_crawl_statistics()
            result.statistics.update({
                'total_pages_crawled': crawl_stats['total_crawled'],
                'total_links_found': len(all_found_links),
                'total_resources_found': crawl_stats['total_resources']
            })
            
            self.logger.info(f"改进的链接爬取完成: {len(all_crawl_results)} 个页面，迭代 {current_iteration} 次")
            
            # 更新数据库中的子域名统计信息
            if len(result.subdomains) > 0:
                await self._update_subdomain_statistics(result)
            
        except Exception as e:
            error_msg = f"改进的链接爬取失败: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
    
    def _extract_subdomains_from_links(self, links: set[str], target_domain: str) -> set[str]:
        """从链接中提取属于目标域名的子域名"""
        subdomains = set()
        target_domain_lower = target_domain.lower()
        
        for link in links:
            try:
                parsed = urlparse(link)
                if parsed.netloc:
                    domain = parsed.netloc.lower()
                    
                    # 移除端口号
                    if ':' in domain:
                        domain = domain.split(':')[0]
                    
                    # 检查是否为目标域名的子域名
                    if domain != target_domain_lower and domain.endswith(f'.{target_domain_lower}'):
                        subdomains.add(domain)
                        
            except Exception:
                continue
        
        return subdomains
    
    def _is_target_domain_or_subdomain(self, url: str, target_domain: str) -> bool:
        """检查URL是否属于目标域名或其子域名"""
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                domain = parsed.netloc.lower()
                
                # 移除端口号
                if ':' in domain:
                    domain = domain.split(':')[0]
                
                target_domain_lower = target_domain.lower()
                
                # 检查是否为目标域名或其子域名
                return domain == target_domain_lower or domain.endswith(f'.{target_domain_lower}')
                
        except Exception:
            pass
        
        return False
    
    def _is_target_domain_or_subdomain_advanced(self, domain: str, target_domain: str) -> bool:
        """强化的子域名检查方法，使用多种验证逻辑"""
        domain_lower = domain.lower().strip()
        target_domain_lower = target_domain.lower().strip()
        
        try:
            import tldextract
            
            # 完全相同
            if domain_lower == target_domain_lower:
                return True
            
            # 基本的子域名检查
            if domain_lower.endswith(f'.{target_domain_lower}'):
                return True
            
            # 使用tldextract进行精确的域名解析
            domain_extracted = tldextract.extract(domain_lower)
            target_extracted = tldextract.extract(target_domain_lower)
            
            # 检查注册域名是否相同
            domain_registered = domain_extracted.registered_domain.lower()
            target_registered = target_extracted.registered_domain.lower()
            
            if domain_registered != target_registered:
                return False
            
            # 如果注册域名相同，进一步检查子域名关系
            domain_full = f"{domain_extracted.subdomain}.{domain_registered}" if domain_extracted.subdomain else domain_registered
            target_full = f"{target_extracted.subdomain}.{target_registered}" if target_extracted.subdomain else target_registered
            
            # 清理可能的空子域名前缀
            domain_full = domain_full.lstrip('.')
            target_full = target_full.lstrip('.')
            
            # 检查子域名关系
            return (domain_full == target_full or 
                    domain_full.endswith(f'.{target_full}') or 
                    target_full.endswith(f'.{domain_full}'))
                    
        except Exception as e:
            self.logger.debug(f"强化子域名检查失败 {domain}: {e}")
            # 如果解析失败，回退到基本字符串匹配
            return (domain_lower == target_domain_lower or 
                    domain_lower.endswith(f'.{target_domain_lower}'))
    
    async def _execute_third_party_identification(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行第三方域名识别"""
        try:
            self.logger.info("开始第三方域名识别阶段")
            
            # 使用第三方域名识别引擎识别第三方域名
            # 注意：这里现在也包括了直接从链接中发现的第三方域名
            domain_records = await self.identifier_engine.identify_domain_records(
                result.target_domain, result.crawl_results, config
            )
            
            # 合并从链接中直接发现的第三方域名和通过引擎识别的域名
            # 先添加通过引擎识别的域名
            result.domain_records.extend(domain_records)
            
            # 去重处理
            unique_domains = {}
            for domain in result.domain_records:
                if domain.domain not in unique_domains:
                    unique_domains[domain.domain] = domain
                else:
                    # 合并found_on_urls
                    existing_domain = unique_domains[domain.domain]
                    existing_domain.found_on_urls.extend(domain.found_on_urls)
                    # 去重
                    existing_domain.found_on_urls = list(set(existing_domain.found_on_urls))
            
            result.domain_records = list(unique_domains.values())
            
            # 更新统计
            result.statistics['total_domain_records'] = len(result.domain_records)
            result.statistics['high_risk_domains'] = sum(
                1 for d in result.domain_records 
                if d.risk_level in ['high', 'critical']
            )
            
            self.logger.info(f"第三方域名识别完成: {len(result.domain_records)} 个，高风险 {result.statistics['high_risk_domains']} 个")
            
            # 立即保存第三方域名记录到数据库
            if result.domain_records:
                await self._save_domain_records_results(result)
            
        except Exception as e:
            error_msg = f"第三方域名识别失败: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
    
    async def _execute_content_capture(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行内容抓取"""
        try:
            self.logger.info("开始内容抓取阶段")
            
            all_content_results = []
            
            # 1. 首先为子域名的主页抓取内容和截图
            self.logger.info(f"开始抓取 {len(result.subdomains)} 个子域名的主页")
            for subdomain in result.subdomains:
                if self.is_cancelled:
                    break
                
                # 只抓取可访问的子域名
                if subdomain.is_accessible:
                    urls_to_capture = [
                        f"https://{subdomain.subdomain}",
                        f"http://{subdomain.subdomain}"
                    ]
                    
                    # 执行抓取
                    content_results = await self.capture_engine.capture_domain_content(
                        subdomain.subdomain, urls_to_capture, config
                    )
                    
                    all_content_results.extend(content_results)
            
            # 2. 然后为每个第三方域名抓取内容
            self.logger.info(f"开始抓取 {len(result.domain_records)} 个第三方域名")
            for third_party_domain in result.domain_records:
                if self.is_cancelled:
                    break
                
                # 构建要抓取的URL列表
                urls_to_capture = []
                
                # 优先抓取主域名
                urls_to_capture.extend([
                    f"https://{third_party_domain.domain}",
                    f"http://{third_party_domain.domain}"
                ])
                
                # 添加发现的URL（限制数量）
                found_urls = third_party_domain.found_on_urls[:5]  # 最多5个URL
                urls_to_capture.extend(found_urls)
                
                # 去重
                urls_to_capture = list(set(urls_to_capture))
                
                # 执行抓取
                content_results = await self.capture_engine.capture_domain_content(
                    third_party_domain.domain, urls_to_capture, config
                )
                
                all_content_results.extend(content_results)
            
            result.content_results = all_content_results
            
            # 获取抓取统计
            capture_stats = await self.capture_engine.get_capture_statistics()
            result.statistics['total_screenshots'] = capture_stats['total_captured']
            
            self.logger.info(f"内容抓取完成: {len(all_content_results)} 个页面")
            
        except Exception as e:
            error_msg = f"内容抓取失败: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
    
    async def _execute_ai_analysis(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行AI分析"""
        try:
            self.logger.info("开始AI分析阶段")
            
            # 检查是否需要AI分析
            if not config.get('ai_analysis_enabled', True):
                self.logger.info("AI分析已禁用，跳过此阶段")
                return
            
            # 获取用户AI配置
            user_ai_config = await self._get_user_ai_config()
            if not user_ai_config or not user_ai_config.has_valid_config:
                self.logger.warning("用户AI配置无效，跳过AI分析")
                result.warnings.append("用户AI配置无效，跳过AI分析")
                return
            
            # 初始化AI分析引擎
            if not self.ai_engine:
                self.ai_engine = AIAnalysisEngine(self.task_id, user_ai_config)
            
            # 准备需要分析的第三方域名数据
            domains_to_analyze = await self._prepare_domains_for_analysis(result)
            
            if not domains_to_analyze:
                self.logger.info("没有需要进行AI分析的域名")
                return
            
            # 统计子域名和第三方域名数量
            subdomain_count = sum(1 for d in domains_to_analyze if hasattr(d, 'domain_type') and d.domain_type == 'subdomain')
            third_party_count = len(domains_to_analyze) - subdomain_count
            
            self.logger.info(f"开始分析 {len(domains_to_analyze)} 个域名（子域名: {subdomain_count}, 第三方域名: {third_party_count}）")
            
            # 执行AI分析
            violations = await self.ai_engine.analyze_domains(domains_to_analyze)
            result.violation_records = violations
            
            # 更新统计
            result.statistics['total_violations'] = len(violations)
            result.statistics['ai_analysis_completed'] = len([d for d in domains_to_analyze if d.is_analyzed])
            
            # 统计违规分布
            violation_distribution = {}
            for violation in violations:
                risk_level = violation.risk_level
                violation_distribution[risk_level] = violation_distribution.get(risk_level, 0) + 1
            
            result.statistics['violation_distribution'] = violation_distribution
            
            self.logger.info(f"AI分析完成: {len(violations)} 个违规记录")
            
        except Exception as e:
            error_msg = f"AI分析失败: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
    
    async def _get_user_ai_config(self):
        """获取用户AI配置"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.user import UserAIConfig
            from sqlalchemy import select
            from app.core.security import data_encryption
            
            async with AsyncSessionLocal() as db:
                stmt = select(UserAIConfig).where(UserAIConfig.user_id == self.user_id)
                result = await db.execute(stmt)
                config = result.scalar_one_or_none()
                
                # 解密API密钥
                if config and getattr(config, 'openai_api_key', None):
                    try:
                        decrypted_key = data_encryption.decrypt_data(str(config.openai_api_key))
                        setattr(config, 'openai_api_key', decrypted_key)
                    except Exception as e:
                        self.logger.warning(f"解密API密钥失败: {e}")
                        setattr(config, 'openai_api_key', None)
                
                return config
        except Exception as e:
            self.logger.error(f"获取用户AI配置失败: {e}")
            return None
    
    async def _prepare_domains_for_analysis(self, result: ScanExecutionResult):
        """准备需要分析的域名数据（包括子域名和第三方域名）"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.domain import DomainRecord
            from sqlalchemy import select
            from datetime import datetime, timedelta
            
            async with AsyncSessionLocal() as db:
                domains_to_analyze = []
                
                # 1. 处理第三方域名
                stmt = select(DomainRecord).where(
                    DomainRecord.task_id == self.task_id,
                    DomainRecord.is_analyzed == False  # 只分析未分析的
                )
                db_result = await db.execute(stmt)
                domain_records = db_result.scalars().all()
                
                self.logger.info(f"找到 {len(domain_records)} 个未分析的第三方域名")
                
                for domain in domain_records:
                    # 检查是否有缓存的分析结果
                    if domain.cached_analysis_result is not None:
                        try:
                            # 使用缓存结果
                            cached_result = domain.cached_analysis_result
                            self.logger.info(f"使用缓存的AI分析结果: {domain.domain}")
                            
                            # 标记为已分析
                            domain.is_analyzed = True  # type: ignore
                            domain.analyzed_at = datetime.utcnow()  # type: ignore
                            
                        except Exception as e:
                            self.logger.warning(f"使用缓存结果失败: {e}")
                            # 如果缓存结果有问题，仍然需要分析
                            if domain.screenshot_path is not None and Path(str(domain.screenshot_path)).exists():
                                domains_to_analyze.append(domain)
                    else:
                        # 没有缓存结果，需要进行分析
                        if domain.screenshot_path is not None and Path(str(domain.screenshot_path)).exists():
                            domains_to_analyze.append(domain)
                        else:
                            self.logger.warning(f"第三方域名 {domain.domain} 没有有效的截图文件，跳过AI分析")
                
                # 2. 处理子域名（新增功能）
                subdomain_stmt = select(DomainRecord).where(
                    DomainRecord.task_id == self.task_id
                )
                subdomain_result = await db.execute(subdomain_stmt)
                domain_records = subdomain_result.scalars().all()
                
                self.logger.info(f"找到 {len(domain_records)} 个子域名记录")
                
                # 为子域名创建类似第三方域名的结构，以便AI分析
                for subdomain_record in domain_records:
                    # 只分析可访问的子域名
                    if subdomain_record.is_accessible is True:
                        # 查找对应的截图文件
                        screenshot_path = None
                        self.logger.debug(f"查找子域名 {subdomain_record.subdomain} 的截图文件...")
                        
                        for content_result in result.content_results:
                            self.logger.debug(f"检查内容结果: URL={content_result.url}, 截图路径={content_result.screenshot_path}")
                            if str(subdomain_record.subdomain) in content_result.url:
                                screenshot_path = content_result.screenshot_path
                                self.logger.debug(f"找到匹配的截图: {screenshot_path}")
                                break
                        
                        if screenshot_path:
                            # 验证截图文件是否存在
                            screenshot_file_exists = Path(screenshot_path).exists()
                            self.logger.debug(f"子域名 {subdomain_record.subdomain} 截图路径: {screenshot_path}, 文件存在: {screenshot_file_exists}")
                            
                            if screenshot_file_exists:
                                # 创建一个临时的第三方域名对象用于AI分析
                                subdomain_for_analysis = type('SubdomainForAnalysis', (), {
                                    'id': subdomain_record.id,
                                    'domain': subdomain_record.subdomain,
                                    'screenshot_path': screenshot_path,
                                    'page_title': subdomain_record.page_title or f"{subdomain_record.subdomain} - 子域名主页",
                                    'page_description': f"目标域名的子域名: {subdomain_record.subdomain}",
                                    'is_analyzed': False,
                                    'domain_type': 'subdomain',  # 标记为子域名类型
                                    'cached_analysis_result': None
                                })()
                                
                                domains_to_analyze.append(subdomain_for_analysis)
                                self.logger.info(f"子域名 {subdomain_record.subdomain} 已添加到AI分析队列")
                            else:
                                self.logger.warning(f"子域名 {subdomain_record.subdomain} 截图文件不存在: {screenshot_path}")
                        else:
                            self.logger.warning(f"子域名 {subdomain_record.subdomain} 没有找到匹配的截图文件")
                
                await db.commit()
                
                self.logger.info(f"总共准备了 {len(domains_to_analyze)} 个域名进行AI分析（包括第三方域名和子域名）")
                return domains_to_analyze
                
        except Exception as e:
            self.logger.error(f"准备分析域名数据失败: {e}")
            return []
    
    async def _save_analysis_to_cache(self, domain_id: str, analysis_result: Dict[str, Any]):
        """保存AI分析结果到缓存"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.domain import DomainRecord
            from sqlalchemy import update
            
            async with AsyncSessionLocal() as db:
                stmt = update(DomainRecord).where(
                    DomainRecord.id == domain_id
                ).values(
                    cached_analysis_result=analysis_result
                )
                await db.execute(stmt)
                await db.commit()
                
        except Exception as e:
            self.logger.warning(f"保存分析结果到缓存失败: {e}")
    
    async def _calculate_final_statistics(self, result: ScanExecutionResult):
        """计算最终统计信息"""
        try:
            # 计算风险分布
            risk_distribution = {}
            for domain in result.domain_records:
                risk_level = domain.risk_level
                risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1
            
            result.statistics['risk_distribution'] = risk_distribution
            
            # 计算类型分布
            type_distribution = {}
            for domain in result.domain_records:
                domain_type = domain.domain_type
                type_distribution[domain_type] = type_distribution.get(domain_type, 0) + 1
            
            result.statistics['type_distribution'] = type_distribution
            
            # 计算成功率
            if result.statistics['total_pages_crawled'] > 0:
                result.statistics['crawl_success_rate'] = int(
                    result.statistics['total_pages_crawled'] / 
                    (result.statistics['total_pages_crawled'] + len(result.errors)) * 100
                )
            
            self.logger.info("最终统计信息计算完成")
            
        except Exception as e:
            self.logger.warning(f"统计信息计算失败: {e}")
    
    async def _update_progress(self, result: ScanExecutionResult, progress: int, message: str):
        """更新进度"""
        result.progress = progress
        self.logger.info(f"进度更新: {progress}% - {message}")
        
        # 发送WebSocket通知 - 使用新的域名推送系统
        try:
            from app.websocket.domain_websocket import task_notifier
            await task_notifier.notify_task_progress(
                self.task_id, 
                progress, 
                result.status, 
                message
            )
        except Exception as e:
            self.logger.warning(f"发送WebSocket进度通知失败: {e}")
        
        # 同步更新数据库任务进度
        try:
            await self._update_task_progress_in_db(progress, result.status)
        except Exception as e:
            self.logger.warning(f"更新数据库进度失败: {e}")
        
        if self.progress_callback:
            try:
                await self.progress_callback(self.task_id, progress, message)
            except Exception as e:
                self.logger.warning(f"进度回调失败: {e}")
    
    async def _update_task_progress_in_db(self, progress: int, status: str):
        """同步更新数据库中的任务进度"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.task import ScanTask
            from sqlalchemy import update
            
            async with AsyncSessionLocal() as db:
                # 更新任务进度
                update_query = update(ScanTask).where(
                    ScanTask.id == self.task_id
                ).values(
                    progress=progress,
                    status=status,
                    last_updated_at=datetime.utcnow()
                )
                
                await db.execute(update_query)
                await db.commit()
                
        except Exception as e:
            self.logger.error(f"更新数据库任务进度失败: {e}")
    
    async def cancel_scan(self):
        """取消扫描"""
        self.is_cancelled = True
        self.logger.info("收到取消扫描请求")
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前执行状态"""
        return {
            'is_running': self.is_running,
            'is_cancelled': self.is_cancelled,
            'task_id': self.task_id
        }
    
    def _get_current_stage(self, progress: int) -> str:
        """根据进度获取当前阶段"""
        if progress <= 25:
            return "子域名发现"
        elif progress <= 50:
            return "链接爬取"
        elif progress <= 70:
            return "第三方域名识别"
        elif progress <= 85:
            return "内容抓取"
        elif progress <= 100:
            return "AI分析"
        else:
            return "完成"
    
    async def _save_subdomain_results(self, result: ScanExecutionResult):
        """立即保存子域名结果到数据库"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.domain import DomainRecord
            from app.models.task import ScanTask
            from sqlalchemy import update
            
            async with AsyncSessionLocal() as db:
                # 保存子域名记录
                saved_count = 0
                for subdomain in result.subdomains:
                    subdomain_record = DomainRecord(
                        task_id=result.task_id,
                        subdomain=subdomain.subdomain,
                        ip_address=subdomain.ip_address,
                        discovery_method=subdomain.method,
                        is_accessible=subdomain.is_accessible,
                        response_code=subdomain.response_code,
                        response_time=subdomain.response_time,
                        server_header=subdomain.server_header,
                        content_type=getattr(subdomain, 'content_type', None),
                        page_title=getattr(subdomain, 'page_title', None),
                        created_at=subdomain.discovered_at
                    )
                    db.add(subdomain_record)
                    saved_count += 1
                
                # 更新任务统计信息
                stmt = update(ScanTask).where(ScanTask.id == result.task_id).values(
                    total_subdomains=result.statistics['total_subdomains']
                )
                await db.execute(stmt)
                
                await db.commit()
                self.logger.info(f"已保存 {saved_count} 个子域名记录到数据库")
                
        except Exception as e:
            self.logger.error(f"保存子域名结果失败: {e}")
            import traceback
            self.logger.error(f"错误堆栈追踪: {traceback.format_exc()}")
    
    async def _save_single_subdomain_result(self, task_id: str, subdomain: SubdomainResult):
        """保存单个子域名结果到数据库"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.domain import DomainRecord
            
            async with AsyncSessionLocal() as db:
                # 检查是否已存在
                from sqlalchemy import select
                existing_query = select(DomainRecord).where(
                    DomainRecord.task_id == task_id,
                    DomainRecord.subdomain == subdomain.subdomain
                )
                existing_result = await db.execute(existing_query)
                existing_record = existing_result.scalar_one_or_none()
                
                if existing_record:
                    self.logger.debug(f"子域名 {subdomain.subdomain} 已存在，跳过保存")
                    return
                
                # 创建新记录
                subdomain_record = DomainRecord(
                    task_id=task_id,
                    subdomain=subdomain.subdomain,
                    ip_address=subdomain.ip_address,
                    discovery_method=subdomain.method,
                    is_accessible=subdomain.is_accessible,
                    response_code=subdomain.response_code,
                    response_time=subdomain.response_time,
                    server_header=subdomain.server_header,
                    content_type=getattr(subdomain, 'content_type', None),
                    page_title=getattr(subdomain, 'page_title', None),
                    created_at=subdomain.discovered_at
                )
                db.add(subdomain_record)
                await db.commit()
                
                self.logger.info(f"已保存新发现的子域名: {subdomain.subdomain}")
                
        except Exception as e:
            self.logger.error(f"保存单个子域名结果失败: {e}")
    
    async def _update_subdomain_statistics(self, result: ScanExecutionResult):
        """更新数据库中的子域名统计信息"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.task import ScanTask
            from sqlalchemy import update
            
            async with AsyncSessionLocal() as db:
                stmt = update(ScanTask).where(ScanTask.id == result.task_id).values(
                    total_subdomains=result.statistics['total_subdomains']
                )
                await db.execute(stmt)
                await db.commit()
                
                self.logger.info(f"已更新任务统计信息: 子域名总数 = {result.statistics['total_subdomains']}")
                
        except Exception as e:
            self.logger.error(f"更新子域名统计信息失败: {e}")
    
    async def _save_domain_records_results(self, result: ScanExecutionResult):
        """立即保存第三方域名结果到数据库"""
        self.logger.info(f"开始保存 {len(result.domain_records)} 个第三方域名记录")
        
        def truncate_url_list(urls, max_length=200):
            """
            截断URL列表，确保总长度不超过指定长度
            """
            if not urls:
                return ""
            
            # 先限制URL数量
            limited_urls = urls[:3]  # 最多3个URL
            
            # 然后限制每个URL的长度
            truncated_urls = []
            for url in limited_urls:
                if len(url) > 100:
                    # 如果URL太长，截断并添加省略号
                    truncated_urls.append(url[:97] + "...")
                else:
                    truncated_urls.append(url)
            
            # 最后限制整体长度
            result_str = ", ".join(truncated_urls)
            if len(result_str) > max_length:
                result_str = result_str[:max_length-3] + "..."
            
            return result_str

        try:
            from app.core.database import AsyncSessionLocal
            from app.models.domain import DomainRecord
            from app.models.task import ScanTask
            from sqlalchemy import update
            
            async with AsyncSessionLocal() as db:
                saved_count = 0
                # 保存第三方域名记录
                for i, third_party in enumerate(result.domain_records):
                    try:
                        # 在第三方域名识别阶段，content_results可能还不存在
                        screenshot_path = None
                        if hasattr(result, 'content_results') and result.content_results:
                            for content in result.content_results:
                                if third_party.domain in content.url:
                                    screenshot_path = content.screenshot_path
                                    break
                        
                        # 限制found_on_url字段长度
                        found_on_url = truncate_url_list(third_party.found_on_urls, 200)
                        
                        third_party_record = DomainRecord(
                            task_id=result.task_id,
                            domain=third_party.domain,
                            found_on_url=found_on_url,
                            domain_type=third_party.domain_type,
                            risk_level=third_party.risk_level,
                            page_title=f"{third_party.domain} - {third_party.description}"[:500],  # 限制标题长度
                            page_description=third_party.description[:1000] if third_party.description else None,  # 限制描述长度
                            screenshot_path=screenshot_path[:500] if screenshot_path else None,  # 限制路径长度
                            is_analyzed=False,  # 初始时未进行AI分析
                            created_at=third_party.discovered_at
                        )
                        db.add(third_party_record)
                        saved_count += 1
                        
                        if (i + 1) % 50 == 0:  # 每50个记录输出一次进度
                            self.logger.info(f"已处理 {i + 1}/{len(result.domain_records)} 个第三方域名")
                    
                    except Exception as domain_error:
                        self.logger.error(f"保存第三方域名 {third_party.domain} 失败: {domain_error}")
                        continue
                
                # 更新任务统计信息
                self.logger.info(f"更新任务统计信息: total_domain_records = {result.statistics['total_domain_records']}")
                stmt = update(ScanTask).where(ScanTask.id == result.task_id).values(
                    total_domain_records=result.statistics['total_domain_records']
                )
                await db.execute(stmt)
                
                # 同时更新子域名统计信息（如果存在）
                if result.statistics.get('total_subdomains', 0) > 0:
                    stmt_sub = update(ScanTask).where(ScanTask.id == result.task_id).values(
                        total_subdomains=result.statistics['total_subdomains']
                    )
                    await db.execute(stmt_sub)
                
                self.logger.info(f"开始提交数据库事务")
                await db.commit()
                self.logger.info(f"已成功保存 {saved_count} 个第三方域名记录到数据库")
                
        except Exception as e:
            self.logger.error(f"保存第三方域名结果失败: {e}")
            import traceback
            self.logger.error(f"错误堆栈追踪: {traceback.format_exc()}")
    
    def _extract_domain_from_url(self, url: str) -> Optional[str]:
        """从URL中提取域名"""
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                domain = parsed.netloc.lower()
                # 移除端口号
                if ':' in domain:
                    domain = domain.split(':')[0]
                return domain
        except Exception:
            pass
        return None

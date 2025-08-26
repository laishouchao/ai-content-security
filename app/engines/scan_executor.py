import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from app.core.logging import TaskLogger
from app.core.config import settings
from app.engines.subdomain_discovery import SubdomainDiscoveryEngine, SubdomainResult
from app.engines.link_crawler import LinkCrawlerEngine, CrawlResult
from app.engines.third_party_identifier import ThirdPartyIdentifierEngine, ThirdPartyDomainResult
from app.engines.content_capture import ContentCaptureEngine, ContentResult
from app.engines.ai_analysis import AIAnalysisEngine, AIAnalysisResult
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
        self.third_party_domains: List[ThirdPartyDomainResult] = []
        self.content_results: List[ContentResult] = []
        self.violation_records = []
        
        # 统计信息
        self.statistics: Dict[str, Any] = {
            'total_subdomains': 0,
            'accessible_subdomains': 0,
            'total_pages_crawled': 0,
            'total_links_found': 0,
            'total_resources_found': 0,
            'total_third_party_domains': 0,
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
        self.identifier_engine = ThirdPartyIdentifierEngine(task_id, user_id)
        self.capture_engine = ContentCaptureEngine(task_id, user_id)
        self.ai_engine = None  # 将在需要时初始化
        
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
            
            # 阶段1: 子域名发现 (0-25%)
            if not self.is_cancelled and config.get('subdomain_discovery_enabled', True):
                await self._execute_subdomain_discovery(result, config)
                await self._update_progress(result, 25, f"子域名发现完成: {len(result.subdomains)} 个")
            
            # 阶段2: 链接爬取 (25-50%)
            if not self.is_cancelled and config.get('link_crawling_enabled', True):
                await self._execute_link_crawling(result, config)
                await self._update_progress(result, 50, f"链接爬取完成: {len(result.crawl_results)} 个页面")
            
            # 阶段3: 第三方域名识别 (50-70%)
            if not self.is_cancelled and config.get('third_party_identification_enabled', True):
                await self._execute_third_party_identification(result, config)
                await self._update_progress(result, 70, f"第三方域名识别完成: {len(result.third_party_domains)} 个")
            
            # 阶段4: 内容抓取 (70-85%)
            if not self.is_cancelled and config.get('content_capture_enabled', True):
                await self._execute_content_capture(result, config)
                await self._update_progress(result, 85, f"内容抓取完成: {len(result.content_results)} 个")
            
            # 阶段5: AI分析 (85-100%)
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
    
    async def _execute_link_crawling(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行链接爬取"""
        try:
            self.logger.info("开始链接爬取阶段")
            
            # 准备起始URL
            start_urls = [f"https://{result.target_domain}", f"http://{result.target_domain}"]
            
            # 添加可访问的子域名
            for subdomain in result.subdomains:
                if subdomain.is_accessible:
                    start_urls.extend([
                        f"https://{subdomain.subdomain}",
                        f"http://{subdomain.subdomain}"
                    ])
            
            # 去重
            start_urls = list(set(start_urls))
            
            # 执行爬取
            crawl_results = await self.crawler_engine.crawl_domain(
                result.target_domain, start_urls, config
            )
            result.crawl_results = crawl_results
            
            # 获取爬取统计
            crawl_stats = await self.crawler_engine.get_crawl_statistics()
            result.statistics.update({
                'total_pages_crawled': crawl_stats['total_crawled'],
                'total_links_found': crawl_stats['total_links'],
                'total_resources_found': crawl_stats['total_resources']
            })
            
            self.logger.info(f"链接爬取完成: {crawl_stats['total_crawled']} 个页面")
            
        except Exception as e:
            error_msg = f"链接爬取失败: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
    
    async def _execute_third_party_identification(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行第三方域名识别"""
        try:
            self.logger.info("开始第三方域名识别阶段")
            
            third_party_domains = await self.identifier_engine.identify_third_party_domains(
                result.target_domain, result.crawl_results, config
            )
            result.third_party_domains = third_party_domains
            
            # 更新统计
            result.statistics['total_third_party_domains'] = len(third_party_domains)
            result.statistics['high_risk_domains'] = sum(
                1 for d in third_party_domains 
                if d.risk_level in ['high', 'critical']
            )
            
            self.logger.info(f"第三方域名识别完成: {len(third_party_domains)} 个，高风险 {result.statistics['high_risk_domains']} 个")
            
            # 立即保存第三方域名记录到数据库
            if third_party_domains:
                await self._save_third_party_domains_results(result)
            
        except Exception as e:
            error_msg = f"第三方域名识别失败: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
    
    async def _execute_content_capture(self, result: ScanExecutionResult, config: Dict[str, Any]):
        """执行内容抓取"""
        try:
            self.logger.info("开始内容抓取阶段")
            
            # 为每个第三方域名抓取内容
            all_content_results = []
            
            for third_party_domain in result.third_party_domains:
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
            
            self.logger.info(f"开始分析 {len(domains_to_analyze)} 个第三方域名")
            
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
            
            async with AsyncSessionLocal() as db:
                stmt = select(UserAIConfig).where(UserAIConfig.user_id == self.user_id)
                result = await db.execute(stmt)
                return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"获取用户AI配置失败: {e}")
            return None
    
    async def _prepare_domains_for_analysis(self, result: ScanExecutionResult):
        """准备需要分析的域名数据"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.task import ThirdPartyDomain
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as db:
                # 查询当前任务的第三方域名记录
                stmt = select(ThirdPartyDomain).where(
                    ThirdPartyDomain.task_id == self.task_id,
                    ThirdPartyDomain.is_analyzed == False  # 只分析未分析的
                )
                db_result = await db.execute(stmt)
                domains = db_result.scalars().all()
                
                # 过滤有截图文件的域名
                valid_domains = []
                for domain in domains:
                    if domain.screenshot_path is not None and Path(str(domain.screenshot_path)).exists():
                        valid_domains.append(domain)
                    else:
                        self.logger.warning(f"域名 {domain.domain} 没有有效的截图文件，跳过AI分析")
                
                return valid_domains
        except Exception as e:
            self.logger.error(f"准备分析域名数据失败: {e}")
            return []
    
    async def _calculate_final_statistics(self, result: ScanExecutionResult):
        """计算最终统计信息"""
        try:
            # 计算风险分布
            risk_distribution = {}
            for domain in result.third_party_domains:
                risk_level = domain.risk_level
                risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1
            
            result.statistics['risk_distribution'] = risk_distribution
            
            # 计算类型分布
            type_distribution = {}
            for domain in result.third_party_domains:
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
        
        # 发送WebSocket通知
        try:
            stage = self._get_current_stage(progress)
            await task_monitor.notify_task_progress(
                self.task_id, progress, stage, message
            )
        except Exception as e:
            self.logger.warning(f"发送进度通知失败: {e}")
        
        if self.progress_callback:
            try:
                await self.progress_callback(self.task_id, progress, message)
            except Exception as e:
                self.logger.warning(f"进度回调失败: {e}")
    
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
            from app.models.task import SubdomainRecord, ScanTask
            from sqlalchemy import update
            
            async with AsyncSessionLocal() as db:
                # 保存子域名记录
                saved_count = 0
                for subdomain in result.subdomains:
                    subdomain_record = SubdomainRecord(
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
    
    async def _save_third_party_domains_results(self, result: ScanExecutionResult):
        """立即保存第三方域名结果到数据库"""
        self.logger.info(f"开始保存 {len(result.third_party_domains)} 个第三方域名记录")
        
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
            from app.models.task import ThirdPartyDomain, ScanTask
            from sqlalchemy import update
            
            async with AsyncSessionLocal() as db:
                saved_count = 0
                # 保存第三方域名记录
                for i, third_party in enumerate(result.third_party_domains):
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
                        
                        third_party_record = ThirdPartyDomain(
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
                            self.logger.info(f"已处理 {i + 1}/{len(result.third_party_domains)} 个第三方域名")
                    
                    except Exception as domain_error:
                        self.logger.error(f"保存第三方域名 {third_party.domain} 失败: {domain_error}")
                        continue
                
                # 更新任务统计信息
                self.logger.info(f"更新任务统计信息: total_third_party_domains = {result.statistics['total_third_party_domains']}")
                stmt = update(ScanTask).where(ScanTask.id == result.task_id).values(
                    total_third_party_domains=result.statistics['total_third_party_domains']
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
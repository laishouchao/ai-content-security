"""
循环域名发现和爬取引擎
持续从域名库发现新域名，循环爬取直到找不到新域名为止
"""

import asyncio
import time
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field
import tldextract

from app.core.logging import TaskLogger
from app.core.database import AsyncSessionLocal
from app.models.domain import DomainRecord, DomainCategory, DomainStatus, DiscoveryMethod, RiskLevel
from app.engines.link_crawler import LinkCrawlerEngine
from sqlalchemy import select, update, and_, or_, func


@dataclass 
class DiscoveryRound:
    """发现轮次信息"""
    round_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    domains_to_crawl: int = 0
    new_domains_found: int = 0
    pages_crawled: int = 0
    total_links_found: int = 0
    errors: List[str] = field(default_factory=list)
    



class ContinuousDomainDiscoveryEngine:
    """持续域名发现引擎"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain.lower().strip()
        self.logger = TaskLogger(task_id, user_id)
        
        # 爬取引擎
        self.crawler_engine = LinkCrawlerEngine(task_id, user_id)
        
        # 运行状态
        self.is_running = False
        self.is_cancelled = False
        self.current_round = 0
        self.total_domains_discovered = 0
        self.total_pages_crawled = 0
        
        # 发现轮次记录
        self.discovery_rounds: List[DiscoveryRound] = []
        
        # 目标域名的注册域名信息
        self.target_parts = tldextract.extract(self.target_domain)
        self.target_registered_domain = self.target_parts.registered_domain.lower()
        
        # 进度回调函数
        self.progress_callback = None
        
        self.logger.info(f"初始化持续域名发现引擎: 目标域名={self.target_domain}")
    
    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self.progress_callback = callback
    
    async def _notify_progress(self, progress: int, message: str):
        """通知进度更新"""
        if self.progress_callback:
            try:
                await self.progress_callback(progress, message)
            except Exception as e:
                self.logger.warning(f"进度回调失败: {e}")
    
    async def start_continuous_discovery(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """开始持续域名发现"""
        self.logger.info("🚀 开始持续域名发现和爬取...")
        
        self.is_running = True
        self.is_cancelled = False
        
        try:
            # 1. 初始化：将目标域名添加到域名库
            await self._initialize_target_domain()
            await self._notify_progress(8, "目标域名初始化完成")
            
            # 2. 持续循环发现和爬取
            base_progress = 10  # 从10%开始
            max_progress = 75   # 到75%结束，为AI分析预留空间
            
            while not self.is_cancelled:
                discovery_result = await self._execute_discovery_round(config)
                
                # 如果没有发现新域名，结束循环
                if discovery_result['new_domains_found'] == 0:
                    self.logger.info("✅ 未发现新域名，持续发现完成")
                    break
                
                # 根据轮次计算进度
                max_rounds = config.get('max_discovery_rounds', 20)
                progress_increment = (max_progress - base_progress) / max_rounds
                current_progress = min(max_progress, base_progress + (self.current_round * progress_increment))
                await self._notify_progress(int(current_progress), f"第{self.current_round}轮发现完成，新增{discovery_result['new_domains_found']}个域名")
                
                # 检查是否达到最大轮次限制
                if self.current_round >= max_rounds:
                    self.logger.warning(f"⚠️ 达到最大发现轮次限制 ({max_rounds})，停止发现")
                    break
                
                # 短暂休息避免过度请求
                await asyncio.sleep(1)
            
            # 3. 统计最终结果
            final_stats = await self._calculate_final_statistics()
            
            self.logger.info("🎉 持续域名发现完成")
            self.logger.info(f"📊 最终统计: 总轮次={self.current_round}, 发现域名={self.total_domains_discovered}, 爬取页面={self.total_pages_crawled}")
            
            return final_stats
            
        except Exception as e:
            self.logger.error(f"持续域名发现失败: {e}")
            raise
        finally:
            self.is_running = False
    
    async def _initialize_target_domain(self):
        """初始化：将目标域名添加到域名库"""
        try:
            async with AsyncSessionLocal() as db:
                # 检查目标域名是否已存在
                existing_query = select(DomainRecord).where(
                    and_(
                        DomainRecord.task_id == self.task_id,
                        DomainRecord.domain == self.target_domain
                    )
                )
                result = await db.execute(existing_query)
                existing_domain = result.scalar_one_or_none()
                
                if not existing_domain:
                    # 创建目标域名记录
                    target_record = DomainRecord(
                        task_id=self.task_id,
                        domain=self.target_domain,
                        category=DomainCategory.TARGET_MAIN,
                        status=DomainStatus.DISCOVERED,
                        discovery_method=DiscoveryMethod.MANUAL,
                        is_accessible=True,
                        depth_level=0,
                        risk_level=RiskLevel.SAFE,
                        confidence_score=1.0,
                        tags=["target_domain", "initial"],
                        extra_data={"initialization": True}
                    )
                    
                    db.add(target_record)
                    await db.commit()
                    
                    self.logger.info(f"✅ 目标域名已添加到域名库: {self.target_domain}")
                else:
                    self.logger.info(f"ℹ️ 目标域名已存在于域名库: {self.target_domain}")
                    
        except Exception as e:
            self.logger.error(f"初始化目标域名失败: {e}")
            raise
    
    async def _execute_discovery_round(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """执行一轮发现"""
        self.current_round += 1
        round_info = DiscoveryRound(
            round_number=self.current_round,
            start_time=datetime.utcnow()
        )
        
        self.logger.info(f"🔄 开始第 {self.current_round} 轮域名发现...")
        
        try:
            # 1. 从域名库获取需要爬取的域名
            domains_to_crawl = await self._get_domains_to_crawl()
            round_info.domains_to_crawl = len(domains_to_crawl)
            
            if not domains_to_crawl:
                self.logger.info("📋 没有需要爬取的域名")
                round_info.end_time = datetime.utcnow()
                self.discovery_rounds.append(round_info)
                return {'new_domains_found': 0, 'round_info': round_info}
            
            self.logger.info(f"📋 找到 {len(domains_to_crawl)} 个需要爬取的域名")
            
            # 2. 爬取这些域名
            crawl_results = await self._crawl_domains(domains_to_crawl, config)
            round_info.pages_crawled = len(crawl_results)
            
            # 3. 从爬取结果中提取新域名
            new_domains = await self._extract_and_save_new_domains(crawl_results)
            round_info.new_domains_found = len(new_domains)
            round_info.total_links_found = sum(len(result.links) for result in crawl_results)
            
            # 4. 更新已爬取域名的状态
            await self._update_crawled_domains_status(domains_to_crawl)
            
            # 5. 发送实时更新
            await self._send_real_time_update(round_info, new_domains)
            
            round_info.end_time = datetime.utcnow()
            self.discovery_rounds.append(round_info)
            
            self.total_domains_discovered += round_info.new_domains_found
            self.total_pages_crawled += round_info.pages_crawled
            
            self.logger.info(f"✅ 第 {self.current_round} 轮完成: 爬取域名={round_info.domains_to_crawl}, 发现新域名={round_info.new_domains_found}")
            
            return {'new_domains_found': round_info.new_domains_found, 'round_info': round_info}
            
        except Exception as e:
            error_msg = f"第 {self.current_round} 轮发现失败: {e}"
            round_info.errors.append(error_msg)
            round_info.end_time = datetime.utcnow()
            self.discovery_rounds.append(round_info)
            self.logger.error(error_msg)
            raise
    
    async def _get_domains_to_crawl(self) -> List[DomainRecord]:
        """获取需要爬取的域名"""
        try:
            async with AsyncSessionLocal() as db:
                # 查询需要爬取的域名：已发现但未爬取的域名
                query = select(DomainRecord).where(
                    and_(
                        DomainRecord.task_id == self.task_id,
                        DomainRecord.status.in_([DomainStatus.DISCOVERED, DomainStatus.ACCESSIBLE]),
                        DomainRecord.is_accessible == True,
                        # 还没有被爬取过的域名（可以通过额外字段或状态判断）
                        or_(
                            DomainRecord.extra_data == None,
                            ~DomainRecord.extra_data.has_key('crawled'),
                            DomainRecord.extra_data['crawled'].as_boolean() == False
                        )
                    )
                ).limit(20)  # 每轮限制爬取数量
                
                result = await db.execute(query)
                domains = result.scalars().all()
                
                return list(domains)
                
        except Exception as e:
            self.logger.error(f"获取待爬取域名失败: {e}")
            return []
    
    async def _crawl_domains(self, domains: List[DomainRecord], config: Dict[str, Any]) -> List[Any]:
        """爬取指定的域名列表"""
        all_crawl_results = []
        
        for domain_record in domains:
            try:
                # 获取域名字符串
                domain_str = str(domain_record.domain)
                
                # 构建要爬取的URL
                urls_to_crawl = [
                    f"https://{domain_str}",
                    f"http://{domain_str}"
                ]
                
                self.logger.debug(f"🕷️ 开始爬取域名: {domain_str}")
                
                # 执行爬取
                crawl_results = await self.crawler_engine.crawl_domain(
                    domain_str, 
                    urls_to_crawl, 
                    config
                )
                
                all_crawl_results.extend(crawl_results)
                
                self.logger.debug(f"✅ 域名爬取完成: {domain_str}, 页面数={len(crawl_results)}")
                
                # 短暂休息避免过度请求
                await asyncio.sleep(0.2)
                
            except Exception as e:
                domain_str = str(domain_record.domain)
                self.logger.warning(f"爬取域名失败 {domain_str}: {e}")
                continue
        
        return all_crawl_results
    
    async def _extract_and_save_new_domains(self, crawl_results: List[Any]) -> List[str]:
        """从爬取结果中提取并保存新域名"""
        try:
            new_domains = set()
            
            # 从所有爬取结果中提取链接
            for result in crawl_results:
                links = []
                if hasattr(result, 'links'):
                    links.extend(result.links)
                if hasattr(result, 'resources'):
                    links.extend(result.resources)
                if hasattr(result, 'forms'):
                    links.extend(result.forms)
                
                # 从链接中提取域名
                for link in links:
                    domain = self._extract_domain_from_url(link)
                    if domain and self._is_valid_domain(domain):
                        new_domains.add(domain)
            
            # 过滤掉已存在的域名
            existing_domains = await self._get_existing_domains()
            truly_new_domains = new_domains - existing_domains
            
            if truly_new_domains:
                self.logger.info(f"🆕 发现 {len(truly_new_domains)} 个新域名")
                
                # 批量保存新域名到数据库
                await self._save_new_domains_to_db(list(truly_new_domains))
            
            return list(truly_new_domains)
            
        except Exception as e:
            self.logger.error(f"提取和保存新域名失败: {e}")
            return []
    
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
    
    def _is_valid_domain(self, domain: str) -> bool:
        """检查域名是否有效"""
        if not domain or len(domain) < 3:
            return False
        
        # 排除明显的无效域名
        invalid_patterns = [
            'localhost', '127.0.0.1', '0.0.0.0',
            'example.com', 'test.com', 'demo.com'
        ]
        
        if domain in invalid_patterns:
            return False
        
        # 必须包含点号
        if '.' not in domain:
            return False
        
        return True
    
    async def _get_existing_domains(self) -> Set[str]:
        """获取已存在的域名集合"""
        try:
            async with AsyncSessionLocal() as db:
                query = select(DomainRecord.domain).where(
                    DomainRecord.task_id == self.task_id
                )
                result = await db.execute(query)
                domains = result.scalars().all()
                return set(domains)
        except Exception as e:
            self.logger.error(f"获取已存在域名失败: {e}")
            return set()
    
    async def _save_new_domains_to_db(self, domains: List[str]):
        """批量保存新域名到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                domain_records = []
                
                for domain in domains:
                    # 判断域名类型
                    category = self._classify_domain(domain)
                    
                    record = DomainRecord(
                        task_id=self.task_id,
                        domain=domain,
                        category=category,
                        status=DomainStatus.DISCOVERED,
                        discovery_method=DiscoveryMethod.LINK_CRAWLING,
                        is_accessible=True,  # 默认设为可访问，后续验证
                        depth_level=self.current_round,
                        risk_level=RiskLevel.LOW if category != DomainCategory.THIRD_PARTY else RiskLevel.MEDIUM,
                        confidence_score=0.8,
                        tags=["auto_discovered", f"round_{self.current_round}"],
                        extra_data={
                            "discovered_in_round": self.current_round,
                            "crawled": False
                        }
                    )
                    
                    domain_records.append(record)
                
                # 批量添加
                db.add_all(domain_records)
                await db.commit()
                
                self.logger.info(f"✅ 已保存 {len(domain_records)} 个新域名到数据库")
                
        except Exception as e:
            self.logger.error(f"保存新域名到数据库失败: {e}")
            raise
    
    def _classify_domain(self, domain: str) -> str:
        """简单的域名分类"""
        try:
            # 使用tldextract解析域名
            domain_parts = tldextract.extract(domain)
            domain_registered = domain_parts.registered_domain.lower()
            
            # 如果注册域名相同，则是目标相关域名
            if domain_registered == self.target_registered_domain:
                if domain == self.target_domain:
                    return DomainCategory.TARGET_MAIN
                else:
                    return DomainCategory.TARGET_SUBDOMAIN
            else:
                return DomainCategory.THIRD_PARTY
                
        except Exception:
            return DomainCategory.UNKNOWN
    
    async def _update_crawled_domains_status(self, domains: List[DomainRecord]):
        """更新已爬取域名的状态"""
        try:
            async with AsyncSessionLocal() as db:
                for domain_record in domains:
                    # 获取现有的extra_data，确保是字典类型
                    existing_extra_data = domain_record.extra_data if isinstance(domain_record.extra_data, dict) else {}
                    
                    # 更新域名状态为已爬取
                    update_query = update(DomainRecord).where(
                        DomainRecord.id == domain_record.id
                    ).values(
                        status=DomainStatus.ACCESSIBLE,
                        last_accessed_at=datetime.utcnow(),
                        extra_data={
                            **existing_extra_data,
                            "crawled": True,
                            "crawled_at": datetime.utcnow().isoformat(),
                            "crawled_in_round": self.current_round
                        }
                    )
                    
                    await db.execute(update_query)
                
                await db.commit()
                
        except Exception as e:
            self.logger.error(f"更新域名状态失败: {e}")
    
    async def _send_real_time_update(self, round_info: DiscoveryRound, new_domains: List[str]):
        """发送实时更新"""
        try:
            # 使用WebSocket发送实时更新
            from app.websocket.domain_websocket import task_notifier, notify_domain_stats_update
            
            # 发送轮次完成通知
            round_data = {
                "round_number": round_info.round_number,
                "domains_crawled": round_info.domains_to_crawl,
                "new_domains_found": round_info.new_domains_found,
                "pages_crawled": round_info.pages_crawled,
                "total_links_found": round_info.total_links_found,
                "duration_seconds": (round_info.end_time - round_info.start_time).total_seconds() if round_info.end_time else 0,
                "errors": round_info.errors
            }
            
            await task_notifier.notify_continuous_discovery_round(self.task_id, round_data)
            
            # 如果发现了新域名，发送域名发现通知
            if new_domains:
                await task_notifier.notify_domain_discovered(
                    self.task_id, 
                    new_domains, 
                    round_info.round_number
                )
            
            # 更新域名统计数据
            await notify_domain_stats_update(self.task_id)
            
            self.logger.debug(f"📡 发送实时更新: 轮次{round_info.round_number}, 新域名{len(new_domains)}个")
            
        except Exception as e:
            self.logger.warning(f"发送实时更新失败: {e}")
    
    async def _calculate_final_statistics(self) -> Dict[str, Any]:
        """计算最终统计信息"""
        try:
            async with AsyncSessionLocal() as db:
                # 统计各类域名数量
                total_query = select(DomainRecord).where(DomainRecord.task_id == self.task_id)
                result = await db.execute(total_query)
                all_domains = result.scalars().all()
                
                # 使用数据库查询计算各种统计数据
                target_main_query = select(func.count()).where(
                    and_(
                        DomainRecord.task_id == self.task_id,
                        DomainRecord.category == DomainCategory.TARGET_MAIN
                    )
                )
                target_main_result = await db.execute(target_main_query)
                target_main_count = target_main_result.scalar() or 0
                
                target_subdomain_query = select(func.count()).where(
                    and_(
                        DomainRecord.task_id == self.task_id,
                        DomainRecord.category == DomainCategory.TARGET_SUBDOMAIN
                    )
                )
                target_subdomain_result = await db.execute(target_subdomain_query)
                target_subdomain_count = target_subdomain_result.scalar() or 0
                
                third_party_query = select(func.count()).where(
                    and_(
                        DomainRecord.task_id == self.task_id,
                        DomainRecord.category == DomainCategory.THIRD_PARTY
                    )
                )
                third_party_result = await db.execute(third_party_query)
                third_party_count = third_party_result.scalar() or 0
                
                unknown_query = select(func.count()).where(
                    and_(
                        DomainRecord.task_id == self.task_id,
                        DomainRecord.category == DomainCategory.UNKNOWN
                    )
                )
                unknown_result = await db.execute(unknown_query)
                unknown_count = unknown_result.scalar() or 0
                
                stats = {
                    "total_rounds": self.current_round,
                    "total_domains": len(all_domains),
                    "total_pages_crawled": self.total_pages_crawled,
                    "target_main_count": target_main_count,
                    "target_subdomain_count": target_subdomain_count,
                    "third_party_count": third_party_count,
                    "unknown_count": unknown_count,
                    "discovery_rounds": [
                        {
                            "round": r.round_number,
                            "domains_crawled": r.domains_to_crawl,
                            "new_domains_found": r.new_domains_found,
                            "pages_crawled": r.pages_crawled,
                            "duration_seconds": (r.end_time - r.start_time).total_seconds() if r.end_time else 0
                        }
                        for r in self.discovery_rounds
                    ]
                }
                
                return stats
                
        except Exception as e:
            self.logger.error(f"计算最终统计失败: {e}")
            return {"error": str(e)}
    
    async def cancel_discovery(self):
        """取消发现过程"""
        self.is_cancelled = True
        self.logger.info("🛑 收到取消发现请求")
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "is_running": self.is_running,
            "is_cancelled": self.is_cancelled,
            "current_round": self.current_round,
            "total_domains_discovered": self.total_domains_discovered,
            "total_pages_crawled": self.total_pages_crawled,
            "discovery_rounds": len(self.discovery_rounds)
        }
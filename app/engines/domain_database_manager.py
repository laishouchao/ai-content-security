"""
域名数据库管理器
优化数据存储和域名库管理

核心功能：
1. 全局域名池管理
2. 域名去重和验证
3. 批量存储和更新
4. 统计和关联分析
5. 缓存优化
"""

import asyncio
import hashlib
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json

from app.core.logging import TaskLogger
from app.engines.ai_result_processor import ProcessedDomainResult, RiskLevel


@dataclass
class DomainRecord:
    """域名记录"""
    domain: str
    domain_type: str  # 'target_subdomain', 'third_party'
    discovery_method: str
    source_urls: List[str] = field(default_factory=list)
    
    # 状态信息
    first_discovered: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    discovery_count: int = 1
    
    # 分析结果
    is_accessible: bool = False
    risk_level: str = 'unknown'
    has_violations: bool = False
    violation_types: List[str] = field(default_factory=list)
    
    # AI分析信息
    ai_analyzed: bool = False
    analysis_count: int = 0
    last_analysis: Optional[datetime] = None
    confidence_score: float = 0.0
    
    # 处理状态
    screenshot_captured: bool = False
    content_analyzed: bool = False
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainStatistics:
    """域名统计信息"""
    total_domains: int = 0
    target_subdomains: int = 0
    third_party_domains: int = 0
    accessible_domains: int = 0
    analyzed_domains: int = 0
    violation_domains: int = 0
    
    # 风险分布
    risk_distribution: Dict[str, int] = field(default_factory=lambda: {
        'low': 0, 'medium': 0, 'high': 0, 'critical': 0, 'unknown': 0
    })
    
    # 发现方法统计
    discovery_methods: Dict[str, int] = field(default_factory=dict)
    
    # 状态统计
    processing_status: Dict[str, int] = field(default_factory=lambda: {
        'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0
    })


class DomainDeduplicator:
    """域名去重器"""
    
    def __init__(self):
        self.domain_hashes: Set[str] = set()
        self.canonical_domains: Dict[str, str] = {}
    
    def normalize_domain(self, domain: str) -> str:
        """规范化域名格式"""
        # 转小写
        domain = domain.lower().strip()
        
        # 移除协议前缀
        if domain.startswith(('http://', 'https://')):
            domain = domain.split('://', 1)[1]
        
        # 移除路径和查询参数
        if '/' in domain:
            domain = domain.split('/', 1)[0]
        
        # 移除端口号（保留常见端口）
        if ':' in domain and not domain.endswith((':80', ':443')):
            parts = domain.split(':')
            if len(parts) == 2 and parts[1].isdigit():
                port = int(parts[1])
                # 只保留非标准端口
                if port not in (80, 443):
                    domain = parts[0]
                else:
                    domain = parts[0]
        
        return domain
    
    def generate_domain_hash(self, domain: str) -> str:
        """生成域名哈希"""
        normalized = self.normalize_domain(domain)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:16]
    
    def is_duplicate(self, domain: str) -> Tuple[bool, Optional[str]]:
        """检查是否重复域名"""
        normalized = self.normalize_domain(domain)
        domain_hash = self.generate_domain_hash(domain)
        
        if domain_hash in self.domain_hashes:
            # 找到规范域名
            canonical = self.canonical_domains.get(domain_hash, normalized)
            return True, canonical
        
        return False, None
    
    def add_domain(self, domain: str) -> str:
        """添加域名到去重器"""
        normalized = self.normalize_domain(domain)
        domain_hash = self.generate_domain_hash(domain)
        
        self.domain_hashes.add(domain_hash)
        
        # 保存规范域名（选择最短的作为规范形式）
        if domain_hash not in self.canonical_domains:
            self.canonical_domains[domain_hash] = normalized
        else:
            current = self.canonical_domains[domain_hash]
            if len(normalized) < len(current):
                self.canonical_domains[domain_hash] = normalized
        
        return self.canonical_domains[domain_hash]


class DomainCacheManager:
    """域名缓存管理器"""
    
    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self.memory_cache: Dict[str, DomainRecord] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.access_counts: Dict[str, int] = defaultdict(int)
    
    def get_cached_domain(self, domain: str) -> Optional[DomainRecord]:
        """获取缓存的域名记录"""
        if domain in self.memory_cache:
            # 检查是否过期
            if self._is_cache_valid(domain):
                self.access_counts[domain] += 1
                return self.memory_cache[domain]
            else:
                # 清理过期缓存
                self._remove_from_cache(domain)
        
        return None
    
    def cache_domain(self, domain_record: DomainRecord):
        """缓存域名记录"""
        domain = domain_record.domain
        self.memory_cache[domain] = domain_record
        self.cache_timestamps[domain] = datetime.utcnow()
        self.access_counts[domain] = 1
    
    def _is_cache_valid(self, domain: str) -> bool:
        """检查缓存是否有效"""
        if domain not in self.cache_timestamps:
            return False
        
        timestamp = self.cache_timestamps[domain]
        return (datetime.utcnow() - timestamp).seconds < self.cache_ttl
    
    def _remove_from_cache(self, domain: str):
        """从缓存中移除域名"""
        self.memory_cache.pop(domain, None)
        self.cache_timestamps.pop(domain, None)
        self.access_counts.pop(domain, None)
    
    def cleanup_expired_cache(self):
        """清理过期缓存"""
        expired_domains = []
        for domain, timestamp in self.cache_timestamps.items():
            if (datetime.utcnow() - timestamp).seconds >= self.cache_ttl:
                expired_domains.append(domain)
        
        for domain in expired_domains:
            self._remove_from_cache(domain)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            'total_cached': len(self.memory_cache),
            'average_access': sum(self.access_counts.values()) / max(len(self.access_counts), 1),
            'cache_hit_rate': len([d for d in self.memory_cache.keys() if self._is_cache_valid(d)]) / max(len(self.memory_cache), 1)
        }


class DomainDatabaseManager:
    """域名数据库管理器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 组件
        self.deduplicator = DomainDeduplicator()
        self.cache_manager = DomainCacheManager()
        
        # 域名池
        self.domain_pool: Dict[str, DomainRecord] = {}
        self.pending_updates: List[DomainRecord] = []
        
        # 批量操作配置
        self.batch_size = 100
        self.auto_flush_interval = 300  # 5分钟
        self.last_flush_time = datetime.utcnow()
        
        # 统计信息
        self.stats = DomainStatistics()
    
    def add_domain(
        self, 
        domain: str, 
        domain_type: str, 
        discovery_method: str,
        source_urls: List[str] = None
    ) -> Tuple[bool, DomainRecord]:
        """添加域名到池中"""
        source_urls = source_urls or []
        
        # 检查重复
        is_duplicate, canonical_domain = self.deduplicator.is_duplicate(domain)
        
        if is_duplicate and canonical_domain in self.domain_pool:
            # 更新现有记录
            existing_record = self.domain_pool[canonical_domain]
            existing_record.last_seen = datetime.utcnow()
            existing_record.discovery_count += 1
            
            # 合并来源URL
            for url in source_urls:
                if url not in existing_record.source_urls:
                    existing_record.source_urls.append(url)
            
            # 更新发现方法（如果不同）
            if discovery_method not in existing_record.metadata.get('discovery_methods', []):
                if 'discovery_methods' not in existing_record.metadata:
                    existing_record.metadata['discovery_methods'] = []
                existing_record.metadata['discovery_methods'].append(discovery_method)
            
            self.logger.debug(f"更新重复域名: {canonical_domain}")
            return False, existing_record
        
        # 添加新域名
        canonical_domain = self.deduplicator.add_domain(domain)
        
        domain_record = DomainRecord(
            domain=canonical_domain,
            domain_type=domain_type,
            discovery_method=discovery_method,
            source_urls=source_urls.copy(),
            metadata={'discovery_methods': [discovery_method]}
        )
        
        self.domain_pool[canonical_domain] = domain_record
        self.pending_updates.append(domain_record)
        
        # 更新统计
        self._update_statistics(domain_record, is_new=True)
        
        # 缓存新记录
        self.cache_manager.cache_domain(domain_record)
        
        self.logger.debug(f"添加新域名: {canonical_domain} ({domain_type})")
        
        # 检查是否需要批量刷新
        if len(self.pending_updates) >= self.batch_size:
            asyncio.create_task(self.flush_pending_updates())
        
        return True, domain_record
    
    def get_domain(self, domain: str) -> Optional[DomainRecord]:
        """获取域名记录"""
        # 先检查缓存
        cached = self.cache_manager.get_cached_domain(domain)
        if cached:
            return cached
        
        # 检查内存池
        canonical_domain = self.deduplicator.normalize_domain(domain)
        if canonical_domain in self.domain_pool:
            record = self.domain_pool[canonical_domain]
            self.cache_manager.cache_domain(record)
            return record
        
        return None
    
    def update_domain_analysis(
        self, 
        domain: str, 
        processed_result: ProcessedDomainResult
    ):
        """更新域名分析结果"""
        record = self.get_domain(domain)
        if not record:
            self.logger.warning(f"未找到域名记录: {domain}")
            return
        
        # 更新分析结果
        record.ai_analyzed = True
        record.analysis_count += 1
        record.last_analysis = datetime.utcnow()
        record.risk_level = processed_result.risk_level.value
        record.has_violations = processed_result.has_violations
        record.violation_types = processed_result.violation_types.copy()
        record.confidence_score = processed_result.confidence_score
        
        # 更新元数据
        record.metadata.update({
            'violation_severity': processed_result.violation_severity,
            'security_score': processed_result.security_score,
            'trustworthiness': processed_result.trustworthiness,
            'recommended_action': processed_result.recommended_action
        })
        
        # 标记需要更新
        if record not in self.pending_updates:
            self.pending_updates.append(record)
        
        # 更新统计
        self._update_statistics(record, is_new=False)
        
        self.logger.debug(f"更新域名分析结果: {domain} - 风险{record.risk_level}")
    
    def batch_update_domains(self, updates: List[Tuple[str, Dict[str, Any]]]):
        """批量更新域名"""
        for domain, update_data in updates:
            record = self.get_domain(domain)
            if record:
                # 更新字段
                for key, value in update_data.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                
                # 标记需要更新
                if record not in self.pending_updates:
                    self.pending_updates.append(record)
        
        self.logger.info(f"批量更新 {len(updates)} 个域名")
    
    async def flush_pending_updates(self):
        """刷新待更新的记录到数据库"""
        if not self.pending_updates:
            return
        
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.task import SubdomainRecord, ThirdPartyDomain
            from sqlalchemy import select, update
            from sqlalchemy.dialects.postgresql import insert
            
            async with AsyncSessionLocal() as db:
                subdomain_updates = []
                third_party_updates = []
                
                for record in self.pending_updates:
                    update_data = {
                        'is_accessible': record.is_accessible,
                        'risk_level': record.risk_level,
                        'is_analyzed': record.ai_analyzed,
                        'confidence_score': record.confidence_score,
                        'last_analyzed': record.last_analysis,
                        'metadata': record.metadata
                    }
                    
                    if record.domain_type == 'target_subdomain':
                        subdomain_updates.append((record.domain, update_data))
                    else:
                        third_party_updates.append((record.domain, update_data))
                
                # 批量更新子域名
                if subdomain_updates:
                    for domain, data in subdomain_updates:
                        stmt = update(SubdomainRecord).where(
                            SubdomainRecord.task_id == self.task_id,
                            SubdomainRecord.subdomain == domain
                        ).values(**data)
                        await db.execute(stmt)
                
                # 批量更新第三方域名
                if third_party_updates:
                    for domain, data in third_party_updates:
                        stmt = update(ThirdPartyDomain).where(
                            ThirdPartyDomain.task_id == self.task_id,
                            ThirdPartyDomain.domain == domain
                        ).values(**data)
                        await db.execute(stmt)
                
                await db.commit()
                
                self.logger.info(f"成功刷新 {len(self.pending_updates)} 个域名记录到数据库")
                self.pending_updates.clear()
                self.last_flush_time = datetime.utcnow()
                
        except Exception as e:
            self.logger.error(f"刷新域名记录到数据库失败: {e}")
    
    def _update_statistics(self, record: DomainRecord, is_new: bool):
        """更新统计信息"""
        if is_new:
            self.stats.total_domains += 1
            if record.domain_type == 'target_subdomain':
                self.stats.target_subdomains += 1
            else:
                self.stats.third_party_domains += 1
            
            # 更新发现方法统计
            method = record.discovery_method
            self.stats.discovery_methods[method] = self.stats.discovery_methods.get(method, 0) + 1
        
        # 更新状态统计
        if record.is_accessible:
            self.stats.accessible_domains += 1
        
        if record.ai_analyzed:
            self.stats.analyzed_domains += 1
        
        if record.has_violations:
            self.stats.violation_domains += 1
        
        # 更新风险分布
        risk_level = record.risk_level
        if risk_level in self.stats.risk_distribution:
            self.stats.risk_distribution[risk_level] += 1
    
    def get_statistics(self) -> DomainStatistics:
        """获取统计信息"""
        return self.stats
    
    def get_domain_list(
        self, 
        domain_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        has_violations: Optional[bool] = None
    ) -> List[DomainRecord]:
        """获取域名列表"""
        domains = list(self.domain_pool.values())
        
        # 应用过滤条件
        if domain_type:
            domains = [d for d in domains if d.domain_type == domain_type]
        
        if risk_level:
            domains = [d for d in domains if d.risk_level == risk_level]
        
        if has_violations is not None:
            domains = [d for d in domains if d.has_violations == has_violations]
        
        return domains
    
    def export_domain_data(self) -> Dict[str, Any]:
        """导出域名数据"""
        return {
            'task_id': self.task_id,
            'export_time': datetime.utcnow().isoformat(),
            'statistics': {
                'total_domains': self.stats.total_domains,
                'target_subdomains': self.stats.target_subdomains,
                'third_party_domains': self.stats.third_party_domains,
                'risk_distribution': self.stats.risk_distribution,
                'discovery_methods': self.stats.discovery_methods
            },
            'domains': [
                {
                    'domain': record.domain,
                    'type': record.domain_type,
                    'discovery_method': record.discovery_method,
                    'risk_level': record.risk_level,
                    'has_violations': record.has_violations,
                    'violation_types': record.violation_types,
                    'first_discovered': record.first_discovered.isoformat(),
                    'last_seen': record.last_seen.isoformat(),
                    'discovery_count': record.discovery_count
                }
                for record in self.domain_pool.values()
            ]
        }
    
    async def cleanup(self):
        """清理资源"""
        # 刷新剩余更新
        await self.flush_pending_updates()
        
        # 清理缓存
        self.cache_manager.cleanup_expired_cache()
        
        self.logger.info("域名数据库管理器清理完成")


# 便捷函数
def create_domain_database_manager(task_id: str, user_id: str) -> DomainDatabaseManager:
    """创建域名数据库管理器的便捷函数"""
    return DomainDatabaseManager(task_id, user_id)
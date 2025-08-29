"""
域名数据库管理器
优化域名存储、去重、统计、关联功能

核心功能：
1. 域名去重和规范化
2. 高效的域名索引和查询
3. 域名统计和分析
4. 关联关系管理
5. 批量操作支持
6. 数据备份和恢复
"""

import asyncio
import hashlib
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from urllib.parse import urlparse
import json
import sqlite3
import aiosqlite

from app.core.logging import TaskLogger
from app.engines.domain_classifier import DomainClassification, DomainType, DomainPriority


@dataclass
class DomainRecord:
    """域名记录"""
    domain: str
    normalized_domain: str
    domain_hash: str
    
    # 基本信息
    first_discovered: datetime
    last_updated: datetime
    discovery_count: int = 1
    
    # 分类信息
    domain_type: Optional[str] = None
    priority: int = 3
    confidence_score: float = 0.0
    
    # 来源信息
    discovery_methods: List[str] = field(default_factory=list)
    source_domains: List[str] = field(default_factory=list)
    source_urls: List[str] = field(default_factory=list)
    
    # 分析结果
    is_accessible: bool = False
    content_analyzed: bool = False
    ai_analyzed: bool = False
    risk_level: str = "unknown"
    risk_score: float = 0.0
    
    # 违规信息
    has_violations: bool = False
    violation_types: List[str] = field(default_factory=list)
    violation_details: Optional[str] = None
    
    # 统计信息
    page_count: int = 0
    link_count: int = 0
    screenshot_path: Optional[str] = None


class DomainDatabaseManager:
    """域名数据库管理器"""
    
    def __init__(self, task_id: str, user_id: str, db_path: Optional[str] = None):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 数据库路径
        self.db_path = db_path or f"domain_db_{task_id}.sqlite"
        
        # 内存索引
        self.domain_index: Dict[str, DomainRecord] = {}
        self.hash_index: Dict[str, str] = {}  # hash -> domain
        self.type_index: Dict[str, Set[str]] = defaultdict(set)
        
        # 统计信息
        self.stats = {
            'total_domains': 0,
            'new_domains_today': 0,
            'analyzed_domains': 0,
            'violation_domains': 0,
            'high_risk_domains': 0
        }
        
        self._initialized = False
    
    async def initialize(self):
        """初始化数据库"""
        if self._initialized:
            return
        
        try:
            await self._create_database_schema()
            await self._load_existing_domains()
            await self._update_statistics()
            self._initialized = True
            self.logger.info(f"域名数据库初始化完成: {self.stats['total_domains']} 个域名")
        except Exception as e:
            self.logger.error(f"域名数据库初始化失败: {e}")
            raise
    
    async def _create_database_schema(self):
        """创建数据库模式"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript('''
                CREATE TABLE IF NOT EXISTS domains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT UNIQUE NOT NULL,
                    normalized_domain TEXT NOT NULL,
                    domain_hash TEXT UNIQUE NOT NULL,
                    first_discovered TIMESTAMP NOT NULL,
                    last_updated TIMESTAMP NOT NULL,
                    discovery_count INTEGER DEFAULT 1,
                    domain_type TEXT,
                    priority INTEGER DEFAULT 3,
                    confidence_score REAL DEFAULT 0.0,
                    discovery_methods TEXT,
                    source_domains TEXT,
                    source_urls TEXT,
                    is_accessible BOOLEAN DEFAULT FALSE,
                    content_analyzed BOOLEAN DEFAULT FALSE,
                    ai_analyzed BOOLEAN DEFAULT FALSE,
                    risk_level TEXT DEFAULT 'unknown',
                    risk_score REAL DEFAULT 0.0,
                    has_violations BOOLEAN DEFAULT FALSE,
                    violation_types TEXT,
                    violation_details TEXT,
                    page_count INTEGER DEFAULT 0,
                    link_count INTEGER DEFAULT 0,
                    screenshot_path TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_domain ON domains(domain);
                CREATE INDEX IF NOT EXISTS idx_domain_hash ON domains(domain_hash);
                CREATE INDEX IF NOT EXISTS idx_domain_type ON domains(domain_type);
                CREATE INDEX IF NOT EXISTS idx_risk_level ON domains(risk_level);
                CREATE INDEX IF NOT EXISTS idx_has_violations ON domains(has_violations);
                CREATE INDEX IF NOT EXISTS idx_last_updated ON domains(last_updated);
                
                CREATE TABLE IF NOT EXISTS domain_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_domain TEXT NOT NULL,
                    child_domain TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(parent_domain, child_domain, relation_type)
                );
                
                CREATE INDEX IF NOT EXISTS idx_parent_domain ON domain_relations(parent_domain);
                CREATE INDEX IF NOT EXISTS idx_child_domain ON domain_relations(child_domain);
            ''')
            await db.commit()
    
    async def add_domain(
        self, 
        domain: str,
        discovery_method: str,
        source_domain: Optional[str] = None,
        source_url: Optional[str] = None,
        classification: Optional[DomainClassification] = None
    ) -> bool:
        """添加域名到数据库"""
        try:
            normalized = self._normalize_domain(domain)
            if not normalized:
                return False
            
            domain_hash = self._calculate_domain_hash(normalized)
            
            # 检查是否已存在
            if domain_hash in self.hash_index:
                existing_domain = self.hash_index[domain_hash]
                await self._update_existing_domain(
                    existing_domain, discovery_method, source_domain, source_url
                )
                return False  # 不是新域名
            
            # 创建新域名记录
            record = DomainRecord(
                domain=domain,
                normalized_domain=normalized,
                domain_hash=domain_hash,
                first_discovered=datetime.now(),
                last_updated=datetime.now(),
                discovery_methods=[discovery_method],
                source_domains=[source_domain] if source_domain else [],
                source_urls=[source_url] if source_url else []
            )
            
            # 应用分类信息
            if classification:
                record.domain_type = classification.domain_type.value
                record.priority = classification.priority.value
                record.confidence_score = classification.confidence_score
            
            # 保存到数据库
            await self._save_domain_record(record)
            
            # 更新索引
            self._update_indexes(record)
            
            self.logger.debug(f"新域名已添加: {domain}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加域名失败 {domain}: {e}")
            return False
    
    async def get_domain(self, domain: str) -> Optional[DomainRecord]:
        """获取域名记录"""
        normalized = self._normalize_domain(domain)
        if not normalized:
            return None
        
        return self.domain_index.get(normalized)
    
    async def update_domain_analysis(
        self,
        domain: str,
        analysis_data: Dict[str, Any]
    ) -> bool:
        """更新域名分析结果"""
        try:
            record = await self.get_domain(domain)
            if not record:
                return False
            
            # 更新分析结果
            if 'is_accessible' in analysis_data:
                record.is_accessible = analysis_data['is_accessible']
            if 'content_analyzed' in analysis_data:
                record.content_analyzed = analysis_data['content_analyzed']
            if 'ai_analyzed' in analysis_data:
                record.ai_analyzed = analysis_data['ai_analyzed']
            if 'risk_level' in analysis_data:
                record.risk_level = analysis_data['risk_level']
            if 'risk_score' in analysis_data:
                record.risk_score = analysis_data['risk_score']
            if 'has_violations' in analysis_data:
                record.has_violations = analysis_data['has_violations']
            if 'violation_types' in analysis_data:
                record.violation_types = analysis_data['violation_types']
            if 'page_count' in analysis_data:
                record.page_count = analysis_data['page_count']
            if 'screenshot_path' in analysis_data:
                record.screenshot_path = analysis_data['screenshot_path']
            
            record.last_updated = datetime.now()
            
            # 保存到数据库
            await self._save_domain_record(record, update=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"更新域名分析失败 {domain}: {e}")
            return False
    
    async def get_domains_by_type(self, domain_type: str) -> List[DomainRecord]:
        """根据类型获取域名列表"""
        domains = self.type_index.get(domain_type, set())
        return [self.domain_index[d] for d in domains if d in self.domain_index]
    
    async def get_high_risk_domains(self, min_risk_score: float = 0.7) -> List[DomainRecord]:
        """获取高风险域名列表"""
        return [
            record for record in self.domain_index.values()
            if record.risk_score >= min_risk_score
        ]
    
    async def get_violation_domains(self) -> List[DomainRecord]:
        """获取违规域名列表"""
        return [
            record for record in self.domain_index.values()
            if record.has_violations
        ]
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        await self._update_statistics()
        
        # 详细统计
        type_stats = Counter()
        risk_stats = Counter()
        priority_stats = Counter()
        
        for record in self.domain_index.values():
            if record.domain_type:
                type_stats[record.domain_type] += 1
            risk_stats[record.risk_level] += 1
            priority_stats[record.priority] += 1
        
        return {
            'basic_stats': self.stats,
            'type_distribution': dict(type_stats),
            'risk_distribution': dict(risk_stats),
            'priority_distribution': dict(priority_stats),
            'recent_discoveries': await self._get_recent_discoveries()
        }
    
    def _normalize_domain(self, domain: str) -> Optional[str]:
        """规范化域名"""
        try:
            domain = domain.lower().strip()
            if domain.startswith(('http://', 'https://')):
                domain = urlparse(domain).netloc
            
            if ':' in domain:
                domain = domain.split(':')[0]
            
            if not domain or '.' not in domain:
                return None
            
            return domain
        except Exception:
            return None
    
    def _calculate_domain_hash(self, domain: str) -> str:
        """计算域名哈希"""
        return hashlib.md5(domain.encode('utf-8')).hexdigest()
    
    def _update_indexes(self, record: DomainRecord):
        """更新内存索引"""
        self.domain_index[record.normalized_domain] = record
        self.hash_index[record.domain_hash] = record.normalized_domain
        
        if record.domain_type:
            self.type_index[record.domain_type].add(record.normalized_domain)
    
    async def _save_domain_record(self, record: DomainRecord, update: bool = False):
        """保存域名记录到数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            if update:
                await db.execute('''
                    UPDATE domains SET
                        last_updated = ?, discovery_count = ?,
                        domain_type = ?, priority = ?, confidence_score = ?,
                        discovery_methods = ?, source_domains = ?, source_urls = ?,
                        is_accessible = ?, content_analyzed = ?, ai_analyzed = ?,
                        risk_level = ?, risk_score = ?, has_violations = ?,
                        violation_types = ?, violation_details = ?,
                        page_count = ?, link_count = ?, screenshot_path = ?
                    WHERE domain_hash = ?
                ''', (
                    record.last_updated, record.discovery_count,
                    record.domain_type, record.priority, record.confidence_score,
                    json.dumps(record.discovery_methods),
                    json.dumps(record.source_domains),
                    json.dumps(record.source_urls),
                    record.is_accessible, record.content_analyzed, record.ai_analyzed,
                    record.risk_level, record.risk_score, record.has_violations,
                    json.dumps(record.violation_types), record.violation_details,
                    record.page_count, record.link_count, record.screenshot_path,
                    record.domain_hash
                ))
            else:
                await db.execute('''
                    INSERT INTO domains (
                        domain, normalized_domain, domain_hash,
                        first_discovered, last_updated, discovery_count,
                        domain_type, priority, confidence_score,
                        discovery_methods, source_domains, source_urls,
                        is_accessible, content_analyzed, ai_analyzed,
                        risk_level, risk_score, has_violations,
                        violation_types, page_count, screenshot_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.domain, record.normalized_domain, record.domain_hash,
                    record.first_discovered, record.last_updated, record.discovery_count,
                    record.domain_type, record.priority, record.confidence_score,
                    json.dumps(record.discovery_methods),
                    json.dumps(record.source_domains),
                    json.dumps(record.source_urls),
                    record.is_accessible, record.content_analyzed, record.ai_analyzed,
                    record.risk_level, record.risk_score, record.has_violations,
                    json.dumps(record.violation_types),
                    record.page_count, record.screenshot_path
                ))
            await db.commit()
    
    async def _load_existing_domains(self):
        """加载现有域名"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM domains') as cursor:
                async for row in cursor:
                    record = self._row_to_record(row)
                    self._update_indexes(record)
    
    def _row_to_record(self, row) -> DomainRecord:
        """数据库行转换为记录对象"""
        return DomainRecord(
            domain=row[1],
            normalized_domain=row[2],
            domain_hash=row[3],
            first_discovered=datetime.fromisoformat(row[4]),
            last_updated=datetime.fromisoformat(row[5]),
            discovery_count=row[6],
            domain_type=row[7],
            priority=row[8],
            confidence_score=row[9],
            discovery_methods=json.loads(row[10] or '[]'),
            source_domains=json.loads(row[11] or '[]'),
            source_urls=json.loads(row[12] or '[]'),
            is_accessible=bool(row[13]),
            content_analyzed=bool(row[14]),
            ai_analyzed=bool(row[15]),
            risk_level=row[16],
            risk_score=row[17],
            has_violations=bool(row[18]),
            violation_types=json.loads(row[19] or '[]'),
            violation_details=row[20],
            page_count=row[21],
            link_count=row[22],
            screenshot_path=row[23]
        )
    
    async def _update_existing_domain(
        self,
        domain: str,
        discovery_method: str,
        source_domain: Optional[str],
        source_url: Optional[str]
    ):
        """更新现有域名"""
        record = self.domain_index[domain]
        record.discovery_count += 1
        record.last_updated = datetime.now()
        
        if discovery_method not in record.discovery_methods:
            record.discovery_methods.append(discovery_method)
        
        if source_domain and source_domain not in record.source_domains:
            record.source_domains.append(source_domain)
        
        if source_url and source_url not in record.source_urls:
            record.source_urls.append(source_url)
        
        await self._save_domain_record(record, update=True)
    
    async def _update_statistics(self):
        """更新统计信息"""
        today = datetime.now().date()
        
        self.stats['total_domains'] = len(self.domain_index)
        self.stats['new_domains_today'] = sum(
            1 for record in self.domain_index.values()
            if record.first_discovered.date() == today
        )
        self.stats['analyzed_domains'] = sum(
            1 for record in self.domain_index.values()
            if record.ai_analyzed
        )
        self.stats['violation_domains'] = sum(
            1 for record in self.domain_index.values()
            if record.has_violations
        )
        self.stats['high_risk_domains'] = sum(
            1 for record in self.domain_index.values()
            if record.risk_score >= 0.7
        )
    
    async def _get_recent_discoveries(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取最近发现的域名"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent = [
            {
                'domain': record.domain,
                'discovered': record.first_discovered.isoformat(),
                'type': record.domain_type,
                'risk_level': record.risk_level
            }
            for record in self.domain_index.values()
            if record.first_discovered >= cutoff_date
        ]
        
        return sorted(recent, key=lambda x: x['discovered'], reverse=True)[:50]
    
    async def cleanup(self):
        """清理资源"""
        try:
            self.logger.info("域名数据库管理器清理完成")
        except Exception as e:
            self.logger.warning(f"清理域名数据库管理器失败: {e}")


# 便捷函数
async def create_domain_database_manager(
    task_id: str,
    user_id: str,
    db_path: Optional[str] = None
) -> DomainDatabaseManager:
    """创建并初始化域名数据库管理器"""
    manager = DomainDatabaseManager(task_id, user_id, db_path)
    await manager.initialize()
    return manager
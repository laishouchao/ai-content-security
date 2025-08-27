"""
域名库管理服务
实现白名单/黑名单的CRUD操作和匹配功能
"""

import re
import fnmatch
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update, delete
from sqlalchemy.orm import selectinload
import uuid

from app.models.domain_list import DomainList, DomainListEntry, DomainMatchLog, DomainListType, DomainListScope
from app.models.user import User
from app.core.logging import logger
from app.core.exceptions import ValidationError, NotFoundError


class DomainListService:
    """域名列表服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_domain_list(
        self, 
        user_id: str,
        name: str,
        list_type: str,
        description: Optional[str] = None,
        scope: str = "user",
        is_regex_enabled: bool = False,
        priority: int = 0
    ) -> DomainList:
        """创建域名列表"""
        
        # 验证参数
        if list_type not in [DomainListType.WHITELIST, DomainListType.BLACKLIST]:
            raise ValidationError("无效的列表类型")
        
        if scope not in [DomainListScope.GLOBAL, DomainListScope.USER, DomainListScope.TASK]:
            raise ValidationError("无效的作用域")
        
        # 检查同名列表
        existing_query = select(DomainList).where(
            and_(
                DomainList.name == name,
                DomainList.user_id == user_id,
                DomainList.list_type == list_type
            )
        )
        existing_result = await self.db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise ValidationError("同名列表已存在")
        
        # 创建新列表
        domain_list = DomainList(
            name=name,
            description=description,
            list_type=list_type,
            scope=scope,
            user_id=user_id if scope == DomainListScope.USER else None,
            is_regex_enabled=is_regex_enabled,
            priority=priority,
            created_by=user_id
        )
        
        self.db.add(domain_list)
        await self.db.commit()
        await self.db.refresh(domain_list)
        
        logger.info(f"创建域名列表: {name} (类型: {list_type}, 用户: {user_id})")
        return domain_list
    
    async def get_domain_lists(
        self,
        user_id: str,
        list_type: Optional[str] = None,
        scope: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[DomainList], int]:
        """获取域名列表"""
        
        # 构建查询条件
        conditions = []
        
        # 用户权限过滤
        conditions.append(
            or_(
                DomainList.user_id == user_id,  # 用户自己的列表
                DomainList.scope == DomainListScope.GLOBAL  # 全局列表
            )
        )
        
        if list_type:
            conditions.append(DomainList.list_type == list_type)
        
        if scope:
            conditions.append(DomainList.scope == scope)
        
        if is_active is not None:
            conditions.append(DomainList.is_active == is_active)
        
        # 查询总数
        count_query = select(func.count(DomainList.id)).where(and_(*conditions))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        # 查询列表
        query = select(DomainList).options(
            selectinload(DomainList.domains)
        ).where(
            and_(*conditions)
        ).order_by(
            DomainList.priority.desc(),
            DomainList.created_at.desc()
        ).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        domain_lists = result.scalars().all()
        
        return list(domain_lists), total
    
    async def get_domain_list_by_id(self, list_id: str, user_id: str) -> Optional[DomainList]:
        """根据ID获取域名列表"""
        query = select(DomainList).options(
            selectinload(DomainList.domains)
        ).where(
            and_(
                DomainList.id == list_id,
                or_(
                    DomainList.user_id == user_id,
                    DomainList.scope == DomainListScope.GLOBAL
                )
            )
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def update_domain_list(
        self,
        list_id: str,
        user_id: str,
        **updates
    ) -> DomainList:
        """更新域名列表"""
        
        domain_list = await self.get_domain_list_by_id(list_id, user_id)
        if not domain_list:
            raise NotFoundError("域名列表不存在")
        
        # 检查权限
        if domain_list.user_id != user_id and domain_list.scope != DomainListScope.GLOBAL:
            raise ValidationError("无权限修改此列表")
        
        # 更新字段
        for key, value in updates.items():
            if hasattr(domain_list, key):
                setattr(domain_list, key, value)
        
        domain_list.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(domain_list)
        
        logger.info(f"更新域名列表: {list_id}")
        return domain_list
    
    async def delete_domain_list(self, list_id: str, user_id: str) -> bool:
        """删除域名列表"""
        
        domain_list = await self.get_domain_list_by_id(list_id, user_id)
        if not domain_list:
            raise NotFoundError("域名列表不存在")
        
        # 检查权限
        if domain_list.user_id != user_id:
            raise ValidationError("无权限删除此列表")
        
        await self.db.delete(domain_list)
        await self.db.commit()
        
        logger.info(f"删除域名列表: {list_id}")
        return True
    
    async def add_domain_entry(
        self,
        list_id: str,
        user_id: str,
        domain_pattern: str,
        description: Optional[str] = None,
        is_regex: bool = False,
        is_wildcard: bool = False,
        tags: Optional[List[str]] = None,
        confidence_score: int = 100
    ) -> DomainListEntry:
        """添加域名条目"""
        
        domain_list = await self.get_domain_list_by_id(list_id, user_id)
        if not domain_list:
            raise NotFoundError("域名列表不存在")
        
        # 验证域名模式
        if is_regex:
            try:
                re.compile(domain_pattern)
            except re.error as e:
                raise ValidationError(f"无效的正则表达式: {e}")
        
        # 检查重复
        existing_query = select(DomainListEntry).where(
            and_(
                DomainListEntry.domain_list_id == list_id,
                DomainListEntry.domain_pattern == domain_pattern
            )
        )
        existing_result = await self.db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise ValidationError("域名模式已存在")
        
        # 创建条目
        entry = DomainListEntry(
            domain_list_id=list_id,
            domain_pattern=domain_pattern,
            description=description,
            is_regex=is_regex,
            is_wildcard=is_wildcard,
            tags=tags or [],
            confidence_score=confidence_score,
            created_by=user_id
        )
        
        self.db.add(entry)
        
        # 更新列表统计
        domain_list.domain_count = domain_list.domain_count + 1
        domain_list.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(entry)
        
        logger.info(f"添加域名条目: {domain_pattern} 到列表 {list_id}")
        return entry
    
    async def remove_domain_entry(self, entry_id: str, user_id: str) -> bool:
        """删除域名条目"""
        
        query = select(DomainListEntry).options(
            selectinload(DomainListEntry.domain_list)
        ).where(DomainListEntry.id == entry_id)
        
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise NotFoundError("域名条目不存在")
        
        # 检查权限
        if entry.domain_list.user_id != user_id:
            raise ValidationError("无权限删除此条目")
        
        # 更新列表统计
        entry.domain_list.domain_count = max(0, entry.domain_list.domain_count - 1)
        entry.domain_list.updated_at = datetime.utcnow()
        
        await self.db.delete(entry)
        await self.db.commit()
        
        logger.info(f"删除域名条目: {entry_id}")
        return True
    
    async def batch_add_domains(
        self,
        list_id: str,
        user_id: str,
        domain_patterns: List[str],
        is_regex: bool = False,
        is_wildcard: bool = False
    ) -> Dict[str, Any]:
        """批量添加域名"""
        
        domain_list = await self.get_domain_list_by_id(list_id, user_id)
        if not domain_list:
            raise NotFoundError("域名列表不存在")
        
        # 获取现有条目
        existing_query = select(DomainListEntry.domain_pattern).where(
            DomainListEntry.domain_list_id == list_id
        )
        existing_result = await self.db.execute(existing_query)
        existing_patterns = {row[0] for row in existing_result.all()}
        
        # 过滤重复和无效的域名
        valid_patterns = []
        invalid_patterns = []
        duplicate_patterns = []
        
        for pattern in domain_patterns:
            pattern = pattern.strip()
            if not pattern:
                continue
                
            if pattern in existing_patterns:
                duplicate_patterns.append(pattern)
                continue
            
            # 验证正则表达式
            if is_regex:
                try:
                    re.compile(pattern)
                    valid_patterns.append(pattern)
                except re.error:
                    invalid_patterns.append(pattern)
            else:
                valid_patterns.append(pattern)
        
        # 批量插入
        entries = []
        for pattern in valid_patterns:
            entry = DomainListEntry(
                domain_list_id=list_id,
                domain_pattern=pattern,
                is_regex=is_regex,
                is_wildcard=is_wildcard,
                created_by=user_id
            )
            entries.append(entry)
        
        if entries:
            self.db.add_all(entries)
            
            # 更新列表统计
            domain_list.domain_count = domain_list.domain_count + len(entries)
            domain_list.updated_at = datetime.utcnow()
            
            await self.db.commit()
        
        result = {
            'added_count': len(valid_patterns),
            'duplicate_count': len(duplicate_patterns),
            'invalid_count': len(invalid_patterns),
            'invalid_patterns': invalid_patterns
        }
        
        logger.info(f"批量添加域名到列表 {list_id}: {result}")
        return result


class DomainMatcherService:
    """域名匹配服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache = {}
        self._cache_ttl = 300  # 5分钟缓存
        self._last_cache_update = 0
    
    async def check_domain(self, domain: str, user_id: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """检查域名是否在白名单或黑名单中"""
        
        domain = domain.lower().strip()
        
        # 获取活跃的域名列表
        whitelist_entries = await self._get_active_entries(user_id, DomainListType.WHITELIST)
        blacklist_entries = await self._get_active_entries(user_id, DomainListType.BLACKLIST)
        
        # 检查黑名单（优先级高）
        blacklist_match = self._match_domain_against_entries(domain, blacklist_entries)
        if blacklist_match:
            await self._log_match(domain, blacklist_match, user_id, task_id, "blocked")
            return {
                'is_allowed': False,
                'list_type': 'blacklist',
                'matched_pattern': blacklist_match['pattern'],
                'match_type': blacklist_match['match_type'],
                'confidence': blacklist_match['confidence'],
                'action': 'blocked'
            }
        
        # 检查白名单
        whitelist_match = self._match_domain_against_entries(domain, whitelist_entries)
        if whitelist_match:
            await self._log_match(domain, whitelist_match, user_id, task_id, "allowed")
            return {
                'is_allowed': True,
                'list_type': 'whitelist',
                'matched_pattern': whitelist_match['pattern'],
                'match_type': whitelist_match['match_type'],
                'confidence': whitelist_match['confidence'],
                'action': 'allowed'
            }
        
        # 未匹配任何列表
        return {
            'is_allowed': None,  # 未定义，使用默认策略
            'list_type': None,
            'matched_pattern': None,
            'match_type': None,
            'confidence': 0,
            'action': 'default'
        }
    
    async def batch_check_domains(self, domains: List[str], user_id: str, task_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """批量检查域名"""
        results = {}
        
        # 获取活跃的域名列表（只查询一次）
        whitelist_entries = await self._get_active_entries(user_id, DomainListType.WHITELIST)
        blacklist_entries = await self._get_active_entries(user_id, DomainListType.BLACKLIST)
        
        for domain in domains:
            domain = domain.lower().strip()
            
            # 检查黑名单
            blacklist_match = self._match_domain_against_entries(domain, blacklist_entries)
            if blacklist_match:
                results[domain] = {
                    'is_allowed': False,
                    'list_type': 'blacklist',
                    'matched_pattern': blacklist_match['pattern'],
                    'match_type': blacklist_match['match_type'],
                    'confidence': blacklist_match['confidence'],
                    'action': 'blocked'
                }
                continue
            
            # 检查白名单
            whitelist_match = self._match_domain_against_entries(domain, whitelist_entries)
            if whitelist_match:
                results[domain] = {
                    'is_allowed': True,
                    'list_type': 'whitelist',
                    'matched_pattern': whitelist_match['pattern'],
                    'match_type': whitelist_match['match_type'],
                    'confidence': whitelist_match['confidence'],
                    'action': 'allowed'
                }
                continue
            
            # 未匹配
            results[domain] = {
                'is_allowed': None,
                'list_type': None,
                'matched_pattern': None,
                'match_type': None,
                'confidence': 0,
                'action': 'default'
            }
        
        # 批量记录匹配日志
        await self._batch_log_matches(results, user_id, task_id)
        
        return results
    
    async def _get_active_entries(self, user_id: str, list_type: str) -> List[Dict[str, Any]]:
        """获取活跃的域名列表条目"""
        
        query = select(
            DomainListEntry.domain_pattern,
            DomainListEntry.is_regex,
            DomainListEntry.is_wildcard,
            DomainListEntry.confidence_score,
            DomainListEntry.id,
            DomainList.priority
        ).join(
            DomainList, DomainListEntry.domain_list_id == DomainList.id
        ).where(
            and_(
                DomainList.list_type == list_type,
                DomainList.is_active == True,
                DomainListEntry.is_active == True,
                or_(
                    DomainList.user_id == user_id,
                    DomainList.scope == DomainListScope.GLOBAL
                )
            )
        ).order_by(DomainList.priority.desc())
        
        result = await self.db.execute(query)
        
        entries = []
        for row in result.all():
            entries.append({
                'pattern': row.domain_pattern,
                'is_regex': row.is_regex,
                'is_wildcard': row.is_wildcard,
                'confidence': row.confidence_score,
                'entry_id': row.id,
                'priority': row.priority
            })
        
        return entries
    
    def _match_domain_against_entries(self, domain: str, entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """匹配域名对条目列表"""
        
        for entry in entries:
            pattern = entry['pattern']
            
            # 精确匹配
            if domain == pattern:
                return {
                    'pattern': pattern,
                    'match_type': 'exact',
                    'confidence': entry['confidence'],
                    'entry_id': entry['entry_id']
                }
            
            # 正则表达式匹配
            if entry['is_regex']:
                try:
                    if re.match(pattern, domain):
                        return {
                            'pattern': pattern,
                            'match_type': 'regex',
                            'confidence': entry['confidence'],
                            'entry_id': entry['entry_id']
                        }
                except re.error:
                    continue
            
            # 通配符匹配
            if entry['is_wildcard']:
                if fnmatch.fnmatch(domain, pattern):
                    return {
                        'pattern': pattern,
                        'match_type': 'wildcard',
                        'confidence': entry['confidence'],
                        'entry_id': entry['entry_id']
                    }
            
            # 子域名匹配（如果模式以.开头）
            if pattern.startswith('.') and domain.endswith(pattern):
                return {
                    'pattern': pattern,
                    'match_type': 'subdomain',
                    'confidence': entry['confidence'],
                    'entry_id': entry['entry_id']
                }
        
        return None
    
    async def _log_match(self, domain: str, match_info: Dict[str, Any], user_id: str, task_id: Optional[str], action: str):
        """记录匹配日志"""
        
        # 更新条目统计
        await self.db.execute(
            update(DomainListEntry).where(
                DomainListEntry.id == match_info['entry_id']
            ).values(
                match_count=DomainListEntry.match_count + 1,
                last_matched_at=datetime.utcnow(),
                last_matched_domain=domain
            )
        )
        
        # 记录匹配日志
        log_entry = DomainMatchLog(
            domain=domain,
            matched_pattern=match_info['pattern'],
            list_type='whitelist' if action == 'allowed' else 'blacklist',
            match_type=match_info['match_type'],
            domain_entry_id=match_info['entry_id'],
            task_id=task_id,
            user_id=user_id,
            action_taken=action,
            confidence_score=match_info['confidence']
        )
        
        self.db.add(log_entry)
        await self.db.commit()
    
    async def _batch_log_matches(self, results: Dict[str, Dict[str, Any]], user_id: str, task_id: Optional[str]):
        """批量记录匹配日志"""
        # 这里可以实现批量日志记录以提高性能
        pass
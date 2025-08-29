"""
域名列表服务单元测试
测试域名白名单/黑名单的核心功能
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid

from app.services.domain_list_service import DomainListService, DomainMatcherService
from app.models.domain_list import DomainList, DomainListEntry, DomainListType, DomainListScope
from app.core.exceptions import ValidationError, NotFoundError


class TestDomainListService:
    """域名列表服务测试"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_db):
        """创建服务实例"""
        return DomainListService(mock_db)

    @pytest.fixture
    def mock_user_id(self):
        """模拟用户ID"""
        return str(uuid.uuid4())

    @pytest.fixture
    def sample_domain_list(self, mock_user_id):
        """样例域名列表"""
        return DomainList(
            id=uuid.uuid4(),
            name="测试白名单",
            description="测试用白名单",
            list_type=DomainListType.WHITELIST,
            scope=DomainListScope.USER,
            user_id=mock_user_id,
            is_active=True,
            domain_count=0,
            created_by=mock_user_id
        )

    @pytest.mark.asyncio
    async def test_create_domain_list_success(self, service, mock_db, mock_user_id):
        """测试成功创建域名列表"""
        # 模拟查询不存在同名列表
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        
        # 执行创建
        result = await service.create_domain_list(
            user_id=mock_user_id,
            name="测试白名单",
            list_type=DomainListType.WHITELIST,
            description="测试描述"
        )
        
        # 验证结果
        assert result is not None
        assert result.name == "测试白名单"
        assert result.list_type == DomainListType.WHITELIST
        assert result.user_id == mock_user_id
        
        # 验证数据库操作
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_domain_list_duplicate_name(self, service, mock_db, mock_user_id):
        """测试创建重名域名列表失败"""
        # 模拟查询到同名列表
        mock_db.execute.return_value.scalar_one_or_none.return_value = MagicMock()
        
        # 执行创建并验证异常
        with pytest.raises(ValidationError, match="同名列表已存在"):
            await service.create_domain_list(
                user_id=mock_user_id,
                name="重复名称",
                list_type=DomainListType.WHITELIST
            )

    @pytest.mark.asyncio
    async def test_create_domain_list_invalid_type(self, service, mock_db, mock_user_id):
        """测试创建无效类型域名列表失败"""
        with pytest.raises(ValidationError, match="无效的列表类型"):
            await service.create_domain_list(
                user_id=mock_user_id,
                name="测试列表",
                list_type="invalid_type"
            )

    @pytest.mark.asyncio
    async def test_get_domain_lists_with_filters(self, service, mock_db, mock_user_id):
        """测试带过滤条件获取域名列表"""
        # 模拟查询结果
        mock_lists = [MagicMock() for _ in range(3)]
        mock_db.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=10)),  # 总数查询
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_lists))))  # 列表查询
        ]
        
        # 执行查询
        lists, total = await service.get_domain_lists(
            user_id=mock_user_id,
            list_type=DomainListType.WHITELIST,
            is_active=True,
            skip=0,
            limit=10
        )
        
        # 验证结果
        assert len(lists) == 3
        assert total == 10

    @pytest.mark.asyncio
    async def test_add_domain_entry_success(self, service, mock_db, mock_user_id, sample_domain_list):
        """测试成功添加域名条目"""
        # 模拟获取域名列表
        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=sample_domain_list)),  # 获取列表
            MagicMock(scalar_one_or_none=MagicMock(return_value=None))  # 检查重复
        ]
        
        # 执行添加
        result = await service.add_domain_entry(
            list_id=str(sample_domain_list.id),
            user_id=mock_user_id,
            domain_pattern="example.com",
            description="测试域名"
        )
        
        # 验证结果
        assert result is not None
        assert result.domain_pattern == "example.com"
        assert result.description == "测试域名"
        
        # 验证数据库操作
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_add_domain_entry_invalid_regex(self, service, mock_db, mock_user_id, sample_domain_list):
        """测试添加无效正则表达式域名条目失败"""
        # 模拟获取域名列表
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_domain_list
        
        # 执行添加无效正则表达式
        with pytest.raises(ValidationError, match="无效的正则表达式"):
            await service.add_domain_entry(
                list_id=str(sample_domain_list.id),
                user_id=mock_user_id,
                domain_pattern="[invalid regex",
                is_regex=True
            )

    @pytest.mark.asyncio
    async def test_batch_add_domains_success(self, service, mock_db, mock_user_id, sample_domain_list):
        """测试批量添加域名成功"""
        # 模拟获取域名列表和现有条目
        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=sample_domain_list)),  # 获取列表
            MagicMock(all=MagicMock(return_value=[]))  # 获取现有条目
        ]
        
        # 准备测试数据
        domain_patterns = ["example.com", "test.com", "demo.org"]
        
        # 执行批量添加
        result = await service.batch_add_domains(
            list_id=str(sample_domain_list.id),
            user_id=mock_user_id,
            domain_patterns=domain_patterns
        )
        
        # 验证结果
        assert result["added_count"] == 3
        assert result["duplicate_count"] == 0
        assert result["invalid_count"] == 0
        
        # 验证数据库操作
        mock_db.add_all.assert_called_once()
        mock_db.commit.assert_called_once()


class TestDomainMatcherService:
    """域名匹配服务测试"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def matcher_service(self, mock_db):
        """创建匹配服务实例"""
        return DomainMatcherService(mock_db)

    @pytest.fixture
    def mock_user_id(self):
        """模拟用户ID"""
        return str(uuid.uuid4())

    @pytest.fixture
    def mock_whitelist_entries(self):
        """模拟白名单条目"""
        return [
            {
                'pattern': 'example.com',
                'is_regex': False,
                'is_wildcard': False,
                'confidence': 100,
                'entry_id': str(uuid.uuid4()),
                'priority': 10
            },
            {
                'pattern': '*.test.com',
                'is_regex': False,
                'is_wildcard': True,
                'confidence': 90,
                'entry_id': str(uuid.uuid4()),
                'priority': 5
            },
            {
                'pattern': r'^.*\.google\.com$',
                'is_regex': True,
                'is_wildcard': False,
                'confidence': 95,
                'entry_id': str(uuid.uuid4()),
                'priority': 8
            }
        ]

    @pytest.fixture
    def mock_blacklist_entries(self):
        """模拟黑名单条目"""
        return [
            {
                'pattern': 'malicious.com',
                'is_regex': False,
                'is_wildcard': False,
                'confidence': 100,
                'entry_id': str(uuid.uuid4()),
                'priority': 10
            },
            {
                'pattern': '*.bad.com',
                'is_regex': False,
                'is_wildcard': True,
                'confidence': 95,
                'entry_id': str(uuid.uuid4()),
                'priority': 8
            }
        ]

    def test_match_domain_against_entries_exact_match(self, matcher_service, mock_whitelist_entries):
        """测试精确匹配"""
        domain = "example.com"
        
        result = matcher_service._match_domain_against_entries(domain, mock_whitelist_entries)
        
        assert result is not None
        assert result['pattern'] == 'example.com'
        assert result['match_type'] == 'exact'
        assert result['confidence'] == 100

    def test_match_domain_against_entries_wildcard_match(self, matcher_service, mock_whitelist_entries):
        """测试通配符匹配"""
        domain = "subdomain.test.com"
        
        result = matcher_service._match_domain_against_entries(domain, mock_whitelist_entries)
        
        assert result is not None
        assert result['pattern'] == '*.test.com'
        assert result['match_type'] == 'wildcard'
        assert result['confidence'] == 90

    def test_match_domain_against_entries_regex_match(self, matcher_service, mock_whitelist_entries):
        """测试正则表达式匹配"""
        domain = "mail.google.com"
        
        result = matcher_service._match_domain_against_entries(domain, mock_whitelist_entries)
        
        assert result is not None
        assert result['pattern'] == r'^.*\.google\.com$'
        assert result['match_type'] == 'regex'
        assert result['confidence'] == 95

    def test_match_domain_against_entries_no_match(self, matcher_service, mock_whitelist_entries):
        """测试无匹配情况"""
        domain = "nomatch.org"
        
        result = matcher_service._match_domain_against_entries(domain, mock_whitelist_entries)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_check_domain_blacklist_match(self, matcher_service, mock_db, mock_user_id, mock_blacklist_entries):
        """测试域名黑名单匹配"""
        # 模拟获取条目
        with patch.object(matcher_service, '_get_active_entries') as mock_get_entries:
            mock_get_entries.side_effect = [mock_blacklist_entries, []]  # 黑名单有匹配，白名单为空
            
            # 模拟记录匹配日志
            with patch.object(matcher_service, '_log_match') as mock_log:
                result = await matcher_service.check_domain("malicious.com", mock_user_id)
                
                # 验证结果
                assert result['is_allowed'] is False
                assert result['list_type'] == 'blacklist'
                assert result['matched_pattern'] == 'malicious.com'
                assert result['action'] == 'blocked'
                
                # 验证日志记录
                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_domain_whitelist_match(self, matcher_service, mock_db, mock_user_id, mock_whitelist_entries):
        """测试域名白名单匹配"""
        # 模拟获取条目
        with patch.object(matcher_service, '_get_active_entries') as mock_get_entries:
            mock_get_entries.side_effect = [[], mock_whitelist_entries]  # 黑名单为空，白名单有匹配
            
            # 模拟记录匹配日志
            with patch.object(matcher_service, '_log_match') as mock_log:
                result = await matcher_service.check_domain("example.com", mock_user_id)
                
                # 验证结果
                assert result['is_allowed'] is True
                assert result['list_type'] == 'whitelist'
                assert result['matched_pattern'] == 'example.com'
                assert result['action'] == 'allowed'
                
                # 验证日志记录
                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_domain_no_match(self, matcher_service, mock_db, mock_user_id):
        """测试域名无匹配情况"""
        # 模拟获取条目
        with patch.object(matcher_service, '_get_active_entries') as mock_get_entries:
            mock_get_entries.side_effect = [[], []]  # 黑名单和白名单都为空
            
            result = await matcher_service.check_domain("unknown.com", mock_user_id)
            
            # 验证结果
            assert result['is_allowed'] is None
            assert result['list_type'] is None
            assert result['matched_pattern'] is None
            assert result['action'] == 'default'

    @pytest.mark.asyncio
    async def test_batch_check_domains(self, matcher_service, mock_db, mock_user_id, mock_whitelist_entries, mock_blacklist_entries):
        """测试批量域名检查"""
        domains = ["example.com", "malicious.com", "unknown.org"]
        
        # 模拟获取条目
        with patch.object(matcher_service, '_get_active_entries') as mock_get_entries:
            mock_get_entries.side_effect = [mock_blacklist_entries, mock_whitelist_entries]
            
            # 模拟批量记录日志
            with patch.object(matcher_service, '_batch_log_matches') as mock_batch_log:
                result = await matcher_service.batch_check_domains(domains, mock_user_id)
                
                # 验证结果
                assert len(result) == 3
                assert result["example.com"]["is_allowed"] is True
                assert result["malicious.com"]["is_allowed"] is False
                assert result["unknown.org"]["is_allowed"] is None
                
                # 验证批量日志记录
                mock_batch_log.assert_called_once()


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
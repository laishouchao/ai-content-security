"""
域名白名单/黑名单管理API
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import csv
import io
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import ValidationError, NotFoundError
from app.models.user import User
from app.models.domain_list import DomainListType, DomainListScope
from app.services.domain_list_service import DomainListService, DomainMatcherService
from app.core.logging import logger


router = APIRouter(tags=["域名列表管理"])


# Pydantic模型定义
class DomainListCreateRequest(BaseModel):
    name: str = Field(..., description="列表名称")
    list_type: str = Field(..., description="列表类型：whitelist/blacklist")
    description: Optional[str] = Field(None, description="列表描述")
    scope: str = Field("user", description="作用域：global/user/task")
    is_regex_enabled: bool = Field(False, description="是否启用正则表达式")
    priority: int = Field(0, description="优先级")


class DomainListResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    list_type: str
    scope: str
    is_active: bool
    is_regex_enabled: bool
    priority: int
    domain_count: int
    match_count: int
    last_matched_at: Optional[str]
    created_at: str
    updated_at: str


class DomainEntryCreateRequest(BaseModel):
    domain_pattern: str = Field(..., description="域名模式")
    description: Optional[str] = Field(None, description="条目描述")
    is_regex: bool = Field(False, description="是否为正则表达式")
    is_wildcard: bool = Field(False, description="是否为通配符模式")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    confidence_score: int = Field(100, description="置信度", ge=0, le=100)


class DomainEntryResponse(BaseModel):
    id: str
    domain_pattern: str
    description: Optional[str]
    is_regex: bool
    is_wildcard: bool
    tags: List[str]
    confidence_score: int
    match_count: int
    last_matched_at: Optional[str]
    last_matched_domain: Optional[str]
    is_active: bool
    created_at: str


class BatchAddDomainsRequest(BaseModel):
    domain_patterns: List[str] = Field(..., description="域名模式列表")
    is_regex: bool = Field(False, description="是否为正则表达式")
    is_wildcard: bool = Field(False, description="是否为通配符模式")


class DomainCheckRequest(BaseModel):
    domains: List[str] = Field(..., description="要检查的域名列表")


# API路由实现
@router.post("", response_model=DomainListResponse)
async def create_domain_list(
    request: DomainListCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建域名列表"""
    try:
        service = DomainListService(db)
        domain_list = await service.create_domain_list(
            user_id=str(current_user.id),
            name=request.name,
            list_type=request.list_type,
            description=request.description,
            scope=request.scope,
            is_regex_enabled=request.is_regex_enabled,
            priority=request.priority
        )
        
        return DomainListResponse(
            id=str(domain_list.id),
            name=domain_list.name,  # type: ignore
            description=domain_list.description,  # type: ignore
            list_type=domain_list.list_type,  # type: ignore
            scope=domain_list.scope,  # type: ignore
            is_active=domain_list.is_active,  # type: ignore
            is_regex_enabled=domain_list.is_regex_enabled,  # type: ignore
            priority=domain_list.priority,  # type: ignore
            domain_count=domain_list.domain_count,  # type: ignore
            match_count=domain_list.match_count,  # type: ignore
            last_matched_at=domain_list.last_matched_at.isoformat() if domain_list.last_matched_at is not None else None,  # type: ignore
            created_at=domain_list.created_at.isoformat(),  # type: ignore
            updated_at=domain_list.updated_at.isoformat()  # type: ignore
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"创建域名列表失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建域名列表失败")


@router.get("", response_model=Dict[str, Any])
async def get_domain_lists(
    list_type: Optional[str] = Query(None, description="列表类型过滤"),
    scope: Optional[str] = Query(None, description="作用域过滤"),
    is_active: Optional[bool] = Query(None, description="是否启用过滤"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(50, ge=1, le=200, description="限制数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取域名列表"""
    try:
        service = DomainListService(db)
        domain_lists, total = await service.get_domain_lists(
            user_id=str(current_user.id),
            list_type=list_type,
            scope=scope,
            is_active=is_active,
            skip=skip,
            limit=limit
        )
        
        items = []
        for domain_list in domain_lists:
            items.append(DomainListResponse(
                id=str(domain_list.id),
                name=domain_list.name,  # type: ignore
                description=domain_list.description,  # type: ignore
                list_type=domain_list.list_type,  # type: ignore
                scope=domain_list.scope,  # type: ignore
                is_active=domain_list.is_active,  # type: ignore
                is_regex_enabled=domain_list.is_regex_enabled,  # type: ignore
                priority=domain_list.priority,  # type: ignore
                domain_count=domain_list.domain_count,  # type: ignore
                match_count=domain_list.match_count,  # type: ignore
                last_matched_at=domain_list.last_matched_at.isoformat() if domain_list.last_matched_at is not None else None,  # type: ignore
                created_at=domain_list.created_at.isoformat(),  # type: ignore
                updated_at=domain_list.updated_at.isoformat()  # type: ignore
            ))
        
        return {
            "success": True,
            "data": {
                "items": items,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"获取域名列表失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取域名列表失败")


@router.get("/{list_id}", response_model=Dict[str, Any])
async def get_domain_list(
    list_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取域名列表详情"""
    try:
        service = DomainListService(db)
        domain_list = await service.get_domain_list_by_id(list_id, str(current_user.id))
        
        if not domain_list:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域名列表不存在")
        
        # 构建响应
        list_data = DomainListResponse(
            id=str(domain_list.id),
            name=domain_list.name,  # type: ignore
            description=domain_list.description,  # type: ignore
            list_type=domain_list.list_type,  # type: ignore
            scope=domain_list.scope,  # type: ignore
            is_active=domain_list.is_active,  # type: ignore
            is_regex_enabled=domain_list.is_regex_enabled,  # type: ignore
            priority=domain_list.priority,  # type: ignore
            domain_count=domain_list.domain_count,  # type: ignore
            match_count=domain_list.match_count,  # type: ignore
            last_matched_at=domain_list.last_matched_at.isoformat() if domain_list.last_matched_at is not None else None,  # type: ignore
            created_at=domain_list.created_at.isoformat(),  # type: ignore
            updated_at=domain_list.updated_at.isoformat()  # type: ignore
        )
        
        # 包含域名条目
        entries = []
        for entry in domain_list.domains:
            entries.append(DomainEntryResponse(
                id=str(entry.id),
                domain_pattern=entry.domain_pattern,  # type: ignore
                description=entry.description,  # type: ignore
                is_regex=entry.is_regex,  # type: ignore
                is_wildcard=entry.is_wildcard,  # type: ignore
                tags=entry.tags or [],  # type: ignore
                confidence_score=entry.confidence_score,  # type: ignore
                match_count=entry.match_count,  # type: ignore
                last_matched_at=entry.last_matched_at.isoformat() if entry.last_matched_at is not None else None,  # type: ignore
                last_matched_domain=entry.last_matched_domain,  # type: ignore
                is_active=entry.is_active,  # type: ignore
                created_at=entry.created_at.isoformat()  # type: ignore
            ))
        
        return {
            "success": True,
            "data": {
                "list": list_data,
                "entries": entries
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取域名列表详情失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取域名列表详情失败")


@router.put("/{list_id}", response_model=DomainListResponse)
async def update_domain_list(
    list_id: str,
    request: DomainListCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新域名列表"""
    try:
        service = DomainListService(db)
        domain_list = await service.update_domain_list(
            list_id=list_id,
            user_id=str(current_user.id),
            name=request.name,
            description=request.description,
            is_regex_enabled=request.is_regex_enabled,
            priority=request.priority
        )
        
        return DomainListResponse(
            id=str(domain_list.id),
            name=domain_list.name,  # type: ignore
            description=domain_list.description,  # type: ignore
            list_type=domain_list.list_type,  # type: ignore
            scope=domain_list.scope,  # type: ignore
            is_active=domain_list.is_active,  # type: ignore
            is_regex_enabled=domain_list.is_regex_enabled,  # type: ignore
            priority=domain_list.priority,  # type: ignore
            domain_count=domain_list.domain_count,  # type: ignore
            match_count=domain_list.match_count,  # type: ignore
            last_matched_at=domain_list.last_matched_at.isoformat() if domain_list.last_matched_at is not None else None,  # type: ignore
            created_at=domain_list.created_at.isoformat(),  # type: ignore
            updated_at=domain_list.updated_at.isoformat()  # type: ignore
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"更新域名列表失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新域名列表失败")


@router.delete("/{list_id}")
async def delete_domain_list(
    list_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除域名列表"""
    try:
        service = DomainListService(db)
        await service.delete_domain_list(list_id, str(current_user.id))
        
        return {"success": True, "message": "域名列表删除成功"}
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"删除域名列表失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除域名列表失败")


@router.post("/{list_id}/entries", response_model=DomainEntryResponse)
async def add_domain_entry(
    list_id: str,
    request: DomainEntryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """添加域名条目"""
    try:
        service = DomainListService(db)
        entry = await service.add_domain_entry(
            list_id=list_id,
            user_id=str(current_user.id),
            domain_pattern=request.domain_pattern,
            description=request.description,
            is_regex=request.is_regex,
            is_wildcard=request.is_wildcard,
            tags=request.tags,
            confidence_score=request.confidence_score
        )
        
        return DomainEntryResponse(
            id=str(entry.id),
            domain_pattern=entry.domain_pattern,  # type: ignore
            description=entry.description,  # type: ignore
            is_regex=entry.is_regex,  # type: ignore
            is_wildcard=entry.is_wildcard,  # type: ignore
            tags=entry.tags or [],  # type: ignore
            confidence_score=entry.confidence_score,  # type: ignore
            match_count=entry.match_count,  # type: ignore
            last_matched_at=entry.last_matched_at.isoformat() if entry.last_matched_at is not None else None,  # type: ignore
            last_matched_domain=entry.last_matched_domain,  # type: ignore
            is_active=entry.is_active,  # type: ignore
            created_at=entry.created_at.isoformat()  # type: ignore
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"添加域名条目失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="添加域名条目失败")


@router.delete("/entries/{entry_id}")
async def remove_domain_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除域名条目"""
    try:
        service = DomainListService(db)
        await service.remove_domain_entry(entry_id, str(current_user.id))
        
        return {"success": True, "message": "域名条目删除成功"}
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"删除域名条目失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除域名条目失败")


@router.post("/{list_id}/batch-add", response_model=Dict[str, Any])
async def batch_add_domains(
    list_id: str,
    request: BatchAddDomainsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量添加域名"""
    try:
        service = DomainListService(db)
        result = await service.batch_add_domains(
            list_id=list_id,
            user_id=str(current_user.id),
            domain_patterns=request.domain_patterns,
            is_regex=request.is_regex,
            is_wildcard=request.is_wildcard
        )
        
        return {"success": True, "data": result}
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"批量添加域名失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="批量添加域名失败")


@router.post("/{list_id}/import-csv")
async def import_domains_from_csv(
    list_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """从CSV文件导入域名"""
    try:
        if not file.filename or not file.filename.endswith('.csv'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只支持CSV文件")
        
        # 读取CSV内容
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # 解析CSV
        csv_reader = csv.reader(io.StringIO(csv_content))
        domain_patterns = []
        
        for row in csv_reader:
            if row and row[0].strip():  # 跳过空行
                domain_patterns.append(row[0].strip())
        
        # 批量添加
        service = DomainListService(db)
        result = await service.batch_add_domains(
            list_id=list_id,
            user_id=str(current_user.id),
            domain_patterns=domain_patterns
        )
        
        return {"success": True, "data": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV导入失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="CSV导入失败")


@router.post("/check", response_model=Dict[str, Any])
async def check_domains(
    request: DomainCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """检查域名是否在白名单或黑名单中"""
    try:
        matcher = DomainMatcherService(db)
        results = await matcher.batch_check_domains(
            domains=request.domains,
            user_id=str(current_user.id)
        )
        
        return {"success": True, "data": results}
        
    except Exception as e:
        logger.error(f"域名检查失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="域名检查失败")
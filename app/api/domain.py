"""
域名管理API接口
支持统一的域名记录管理
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db
from app.core.dependencies import get_current_user
from app.models.domain import DomainRecord, DomainCategory, DomainStatus, RiskLevel
from app.models.user import User
from app.schemas.domain import (
    DomainRecordCreateSchema,
    DomainRecordUpdateSchema, 
    DomainRecordResponseSchema,
    DomainListResponseSchema,
    DomainStatsSchema,
    DomainFilterSchema,
    TaskDomainSummarySchema
)
from app.schemas.base import ResponseSchema


router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("/task/{task_id}/scan-domains", response_model=ResponseSchema[DomainListResponseSchema])
async def get_task_scan_domains(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    filters: DomainFilterSchema = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务的需要扫描的域名列表"""
    try:
        # 构建查询条件
        query = select(DomainRecord).where(
            and_(
                DomainRecord.task_id == task_id,
                or_(
                    DomainRecord.category == DomainCategory.TARGET_MAIN,
                    DomainRecord.category == DomainCategory.TARGET_SUBDOMAIN
                )
            )
        )
        
        # 应用过滤器
        if filters.status:
            query = query.where(DomainRecord.status == filters.status)
        if filters.category:
            query = query.where(DomainRecord.category == filters.category)
        if filters.is_accessible is not None:
            query = query.where(DomainRecord.is_accessible == filters.is_accessible)
        if filters.domain_search:
            query = query.where(DomainRecord.domain.contains(filters.domain_search))
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 获取分页数据
        query = query.order_by(DomainRecord.first_discovered_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # 转换为响应模式
        domain_list = []
        for domain in domains:
            domain_dict = domain.to_dict()
            domain_list.append(DomainRecordResponseSchema(**domain_dict))
        
        response_data = DomainListResponseSchema(
            items=domain_list,
            total=total,
            skip=skip,
            limit=limit
        )
        
        return ResponseSchema(success=True, data=response_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取扫描域名失败: {str(e)}")


@router.get("/task/{task_id}/all-domains", response_model=ResponseSchema[DomainListResponseSchema])
async def get_task_all_domains(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    filters: DomainFilterSchema = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务检测到的所有域名列表"""
    try:
        # 构建查询条件
        query = select(DomainRecord).where(DomainRecord.task_id == task_id)
        
        # 应用过滤器
        if filters.category:
            query = query.where(DomainRecord.category == filters.category)
        if filters.status:
            query = query.where(DomainRecord.status == filters.status)
        if filters.risk_level:
            query = query.where(DomainRecord.risk_level == filters.risk_level)
        if filters.is_accessible is not None:
            query = query.where(DomainRecord.is_accessible == filters.is_accessible)
        if filters.is_analyzed is not None:
            query = query.where(DomainRecord.is_analyzed == filters.is_analyzed)
        if filters.domain_search:
            query = query.where(DomainRecord.domain.contains(filters.domain_search))
        if filters.parent_domain:
            query = query.where(DomainRecord.parent_domain == filters.parent_domain)
        if filters.tags:
            for tag in filters.tags:
                query = query.where(DomainRecord.tags.contains([tag]))
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 获取分页数据
        query = query.order_by(DomainRecord.first_discovered_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # 转换为响应模式
        domain_list = []
        for domain in domains:
            domain_dict = domain.to_dict()
            domain_list.append(DomainRecordResponseSchema(**domain_dict))
        
        response_data = DomainListResponseSchema(
            items=domain_list,
            total=total,
            skip=skip,
            limit=limit
        )
        
        return ResponseSchema(success=True, data=response_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取所有域名失败: {str(e)}")


@router.get("/task/{task_id}/stats", response_model=ResponseSchema[DomainStatsSchema])
async def get_task_domain_stats(
    task_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务的域名统计信息"""
    try:
        # 获取所有域名
        query = select(DomainRecord).where(DomainRecord.task_id == task_id)
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # 计算统计信息 - 使用数据库查询避免类型错误
        total_domains = len(domains)
        
        # 使用数据库聚合查询计算各种统计信息
        target_domains_query = select(func.count()).where(
            and_(
                DomainRecord.task_id == task_id,
                DomainRecord.category == DomainCategory.TARGET_MAIN
            )
        )
        target_domains_result = await db.execute(target_domains_query)
        target_domains = target_domains_result.scalar() or 0
        
        subdomain_query = select(func.count()).where(
            and_(
                DomainRecord.task_id == task_id,
                DomainRecord.category == DomainCategory.TARGET_SUBDOMAIN
            )
        )
        subdomain_result = await db.execute(subdomain_query)
        subdomain_count = subdomain_result.scalar() or 0
        
        third_party_query = select(func.count()).where(
            and_(
                DomainRecord.task_id == task_id,
                DomainRecord.category == DomainCategory.THIRD_PARTY
            )
        )
        third_party_result = await db.execute(third_party_query)
        third_party_count = third_party_result.scalar() or 0
        
        accessible_query = select(func.count()).where(
            and_(
                DomainRecord.task_id == task_id,
                DomainRecord.is_accessible == True
            )
        )
        accessible_result = await db.execute(accessible_query)
        accessible_count = accessible_result.scalar() or 0
        
        analyzed_query = select(func.count()).where(
            and_(
                DomainRecord.task_id == task_id,
                DomainRecord.is_analyzed == True
            )
        )
        analyzed_result = await db.execute(analyzed_query)
        analyzed_count = analyzed_result.scalar() or 0
        
        violation_count = 0  # TODO: 从违规记录中计算
        
        # 分类分布
        category_distribution = {}
        for category in DomainCategory:
            cat_query = select(func.count()).where(
                and_(
                    DomainRecord.task_id == task_id,
                    DomainRecord.category == category
                )
            )
            cat_result = await db.execute(cat_query)
            category_distribution[category.value] = cat_result.scalar() or 0
        
        # 状态分布
        status_distribution = {}
        for status in DomainStatus:
            status_query = select(func.count()).where(
                and_(
                    DomainRecord.task_id == task_id,
                    DomainRecord.status == status
                )
            )
            status_result = await db.execute(status_query)
            status_distribution[status.value] = status_result.scalar() or 0
        
        # 风险分布
        risk_distribution = {}
        for risk in RiskLevel:
            risk_query = select(func.count()).where(
                and_(
                    DomainRecord.task_id == task_id,
                    DomainRecord.risk_level == risk
                )
            )
            risk_result = await db.execute(risk_query)
            risk_distribution[risk.value] = risk_result.scalar() or 0
        
        # 发现方法分布
        discovery_method_distribution = {}
        for domain in domains:
            method = domain.discovery_method
            discovery_method_distribution[method] = discovery_method_distribution.get(method, 0) + 1
        
        stats = DomainStatsSchema(
            total_domains=total_domains,
            target_domains=target_domains,
            subdomain_count=subdomain_count,
            third_party_count=third_party_count,
            accessible_count=accessible_count,
            analyzed_count=analyzed_count,
            violation_count=violation_count,
            category_distribution=category_distribution,
            status_distribution=status_distribution,
            risk_distribution=risk_distribution,
            discovery_method_distribution=discovery_method_distribution
        )
        
        return ResponseSchema(success=True, data=stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取域名统计失败: {str(e)}")


@router.get("/task/{task_id}/summary", response_model=ResponseSchema[TaskDomainSummarySchema])
async def get_task_domain_summary(
    task_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务的域名汇总信息"""
    try:
        # 获取任务信息
        from app.models.task import ScanTask
        task_query = select(ScanTask).where(ScanTask.id == task_id)
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取需要扫描的域名
        scan_domains_query = select(DomainRecord).where(
            and_(
                DomainRecord.task_id == task_id,
                or_(
                    DomainRecord.category == DomainCategory.TARGET_MAIN,
                    DomainRecord.category == DomainCategory.TARGET_SUBDOMAIN
                )
            )
        ).order_by(DomainRecord.first_discovered_at.desc()).limit(50)
        
        scan_result = await db.execute(scan_domains_query)
        scan_domains = scan_result.scalars().all()
        
        # 获取所有域名
        all_domains_query = select(DomainRecord).where(
            DomainRecord.task_id == task_id
        ).order_by(DomainRecord.first_discovered_at.desc()).limit(100)
        
        all_result = await db.execute(all_domains_query)
        all_domains = all_result.scalars().all()
        
        # 获取统计信息
        stats_response = await get_task_domain_stats(task_id, db, current_user)
        stats = stats_response.data
        
        # 转换域名数据
        def convert_domain(domain):
            domain_dict = domain.to_dict()
            return DomainRecordResponseSchema(**domain_dict)
        
        # 计算最后更新时间
        all_times = []
        if all_domains:
            all_times.extend([d.last_updated_at for d in all_domains])
        all_times.append(task.created_at)
        if task.last_updated_at:
            all_times.append(task.last_updated_at)
        
        last_updated = max(all_times).isoformat()
        
        summary = TaskDomainSummarySchema(
            task_id=task_id,
            target_domain=str(task.target_domain),
            scan_domains=[convert_domain(d) for d in scan_domains],
            all_domains=[convert_domain(d) for d in all_domains],
            stats=stats,
            last_updated=last_updated
        )
        
        return ResponseSchema(success=True, data=summary)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取域名汇总失败: {str(e)}")


@router.post("/", response_model=ResponseSchema[DomainRecordResponseSchema])
async def create_domain_record(
    domain_data: DomainRecordCreateSchema,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """创建域名记录"""
    try:
        # TODO: 需要在schema中添加task_id字段或修改API路径参数
        # 暂时跳过重复检查
        
        # 创建新的域名记录
        # TODO: 需要从请求中获取 task_id，或修改 API 路径参数
        domain_record = DomainRecord(
            task_id="",  # 需要从请求中获取
            domain=domain_data.domain,
            category=domain_data.category,
            discovery_method=domain_data.discovery_method,
            found_on_urls=domain_data.found_on_urls,
            parent_domain=domain_data.parent_domain,
            depth_level=domain_data.depth_level,
            tags=domain_data.tags,
            extra_data=domain_data.extra_data
        )
        
        db.add(domain_record)
        await db.commit()
        await db.refresh(domain_record)
        
        # 转换为响应模式
        domain_dict = domain_record.to_dict()
        response_data = DomainRecordResponseSchema(**domain_dict)
        
        return ResponseSchema(success=True, data=response_data)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建域名记录失败: {str(e)}")
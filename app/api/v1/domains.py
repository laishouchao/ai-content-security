from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.task import ThirdPartyDomain, ViolationRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/domains", tags=["域名库"])

@router.get("")
async def get_all_domains(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    domain: Optional[str] = Query(None),
    domain_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    has_violations: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """获取所有第三方域名（全局域名库）"""
    try:
        # 构建查询条件
        conditions = []
        
        # 支持域名模糊搜索
        if domain:
            conditions.append(ThirdPartyDomain.domain.ilike(f"%{domain}%"))
        
        # 域名类型筛选
        if domain_type:
            conditions.append(ThirdPartyDomain.domain_type == domain_type)
        
        # 风险等级筛选
        if risk_level:
            conditions.append(ThirdPartyDomain.risk_level == risk_level)
        
        # 违规状态筛选
        if has_violations is not None:
            if has_violations:
                # 有违规记录的域名
                conditions.append(ThirdPartyDomain.violations.any())
            else:
                # 无违规记录的域名
                conditions.append(~ThirdPartyDomain.violations.any())
        
        # 查询总数
        count_query = select(func.count(ThirdPartyDomain.id)).where(
            and_(*conditions)
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询域名列表，包含违规记录
        from sqlalchemy.orm import selectinload
        
        query = select(ThirdPartyDomain).options(
            selectinload(ThirdPartyDomain.violations)
        ).where(
            and_(*conditions)
        ).order_by(ThirdPartyDomain.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # 转换为响应格式
        domain_list = []
        for domain in domains:
            domain_data = {
                "id": domain.id,
                "task_id": domain.task_id,
                "domain": domain.domain,
                "found_on_url": domain.found_on_url,
                "domain_type": domain.domain_type,
                "risk_level": domain.risk_level,
                "page_title": domain.page_title,
                "page_description": domain.page_description,
                "content_hash": domain.content_hash,
                "screenshot_path": domain.screenshot_path,
                "html_content_path": domain.html_content_path,
                "is_analyzed": domain.is_analyzed,
                "analysis_error": domain.analysis_error,
                "created_at": domain.created_at.isoformat() if domain.created_at is not None else None,
                "analyzed_at": domain.analyzed_at.isoformat() if domain.analyzed_at is not None else None,
                # 添加违规记录信息
                "violations": [
                    {
                        "id": violation.id,
                        "task_id": violation.task_id,
                        "domain_id": violation.domain_id,
                        "violation_type": violation.violation_type,
                        "confidence_score": violation.confidence_score,
                        "risk_level": violation.risk_level,
                        "title": violation.title,
                        "description": violation.description,
                        "content_snippet": violation.content_snippet,
                        "ai_analysis_result": violation.ai_analysis_result,
                        "ai_model_used": violation.ai_model_used,
                        "evidence": violation.evidence,
                        "recommendations": violation.recommendations,
                        "detected_at": violation.detected_at.isoformat() if violation.detected_at else None
                    }
                    for violation in domain.violations
                ] if domain.violations else [],
                # 添加计算属性
                "has_violations": len(domain.violations) > 0
            }
            domain_list.append(domain_data)
        
        return {
            "success": True,
            "data": {
                "items": domain_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取域名库数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取域名库数据失败"
        )


@router.get("/{domain_id}")
async def get_domain_detail(
    domain_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """获取域名详情"""
    try:
        # 查询域名详情，包含违规记录
        from sqlalchemy.orm import selectinload
        
        query = select(ThirdPartyDomain).options(
            selectinload(ThirdPartyDomain.violations)
        ).where(
            ThirdPartyDomain.id == domain_id
        )
        
        result = await db.execute(query)
        domain = result.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="域名不存在"
            )
        
        # 转换为响应格式
        domain_data = {
            "id": domain.id,
            "task_id": domain.task_id,
            "domain": domain.domain,
            "found_on_url": domain.found_on_url,
            "domain_type": domain.domain_type,
            "risk_level": domain.risk_level,
            "page_title": domain.page_title,
            "page_description": domain.page_description,
            "content_hash": domain.content_hash,
            "screenshot_path": domain.screenshot_path,
            "html_content_path": domain.html_content_path,
            "is_analyzed": domain.is_analyzed,
            "analysis_error": domain.analysis_error,
            "created_at": domain.created_at.isoformat() if domain.created_at is not None else None,
            "analyzed_at": domain.analyzed_at.isoformat() if domain.analyzed_at is not None else None,
            # 添加违规记录信息
            "violations": [
                {
                    "id": violation.id,
                    "task_id": violation.task_id,
                    "domain_id": violation.domain_id,
                    "violation_type": violation.violation_type,
                    "confidence_score": violation.confidence_score,
                    "risk_level": violation.risk_level,
                    "title": violation.title,
                    "description": violation.description,
                    "content_snippet": violation.content_snippet,
                    "ai_analysis_result": violation.ai_analysis_result,
                    "ai_model_used": violation.ai_model_used,
                    "evidence": violation.evidence,
                    "recommendations": violation.recommendations,
                    "detected_at": violation.detected_at.isoformat() if violation.detected_at else None
                }
                for violation in domain.violations
            ] if domain.violations else [],
            # 添加计算属性
            "has_violations": len(domain.violations) > 0
        }
        
        return {
            "success": True,
            "data": domain_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取域名详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取域名详情失败"
        )


@router.get("/{domain_id}/violations")
async def get_domain_violations(
    domain_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    risk_level: Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """获取域名的违规记录"""
    try:
        # 验证域名存在
        domain_query = select(ThirdPartyDomain).where(
            ThirdPartyDomain.id == domain_id
        )
        domain_result = await db.execute(domain_query)
        domain = domain_result.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="域名不存在"
            )
        
        # 查询总数
        conditions = [ViolationRecord.domain_id == domain_id]
        if risk_level:
            conditions.append(ViolationRecord.risk_level == risk_level)
        if violation_type:
            conditions.append(ViolationRecord.violation_type == violation_type)
        
        count_query = select(func.count(ViolationRecord.id)).where(
            and_(*conditions)
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询违规记录列表
        query = select(ViolationRecord).where(
            and_(*conditions)
        ).order_by(ViolationRecord.detected_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        violations = result.scalars().all()
        
        # 转换为响应格式
        violation_list = []
        for violation in violations:
            violation_data = {
                "id": violation.id,
                "task_id": violation.task_id,
                "domain_id": violation.domain_id,
                "violation_type": violation.violation_type,
                "confidence_score": violation.confidence_score,
                "risk_level": violation.risk_level,
                "title": violation.title,
                "description": violation.description,
                "content_snippet": violation.content_snippet,
                "ai_analysis_result": violation.ai_analysis_result,
                "ai_model_used": violation.ai_model_used,
                "evidence": violation.evidence,
                "recommendations": violation.recommendations,
                "detected_at": violation.detected_at.isoformat() if violation.detected_at is not None else None  # type: ignore
            }
            violation_list.append(violation_data)
        
        return {
            "success": True,
            "data": {
                "items": violation_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取域名违规记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取域名违规记录失败"
        )


@router.get("/stats")
async def get_domain_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """获取域名统计信息"""
    try:
        # 总域名数
        total_query = select(func.count(ThirdPartyDomain.id))
        total_result = await db.execute(total_query)
        total_domains = total_result.scalar() or 0
        
        # 已分析域名数
        analyzed_query = select(func.count(ThirdPartyDomain.id)).where(
            ThirdPartyDomain.is_analyzed == True
        )
        analyzed_result = await db.execute(analyzed_query)
        analyzed_domains = analyzed_result.scalar() or 0
        
        # 未分析域名数
        unanalyzed_domains = total_domains - analyzed_domains
        
        # 有违规记录的域名数
        violation_query = select(func.count(ThirdPartyDomain.id)).where(
            ThirdPartyDomain.violations.any()
        )
        violation_result = await db.execute(violation_query)
        violation_domains = violation_result.scalar() or 0
        
        # 域名类型分布
        type_distribution_query = select(
            ThirdPartyDomain.domain_type,
            func.count(ThirdPartyDomain.id)
        ).group_by(ThirdPartyDomain.domain_type)
        
        type_result = await db.execute(type_distribution_query)
        domain_type_distribution = {
            row[0]: row[1] for row in type_result.fetchall()
        }
        
        # 风险等级分布
        risk_distribution_query = select(
            ThirdPartyDomain.risk_level,
            func.count(ThirdPartyDomain.id)
        ).group_by(ThirdPartyDomain.risk_level)
        
        risk_result = await db.execute(risk_distribution_query)
        risk_level_distribution = {
            row[0]: row[1] for row in risk_result.fetchall()
        }
        
        # 最近添加的域名
        recent_query = select(ThirdPartyDomain).order_by(
            ThirdPartyDomain.created_at.desc()
        ).limit(10)
        
        recent_result = await db.execute(recent_query)
        recent_domains = recent_result.scalars().all()
        
        # 转换最近域名格式
        recent_domain_list = []
        for domain in recent_domains:
            domain_data = {
                "id": domain.id,
                "task_id": domain.task_id,
                "domain": domain.domain,
                "found_on_url": domain.found_on_url,
                "domain_type": domain.domain_type,
                "risk_level": domain.risk_level,
                "page_title": domain.page_title,
                "page_description": domain.page_description,
                "is_analyzed": domain.is_analyzed,
                "created_at": domain.created_at.isoformat() if domain.created_at is not None else None,
                "has_violations": len(domain.violations) > 0
            }
            recent_domain_list.append(domain_data)
        
        return {
            "success": True,
            "data": {
                "total_domains": total_domains,
                "analyzed_domains": analyzed_domains,
                "unanalyzed_domains": unanalyzed_domains,
                "violation_domains": violation_domains,
                "domain_type_distribution": domain_type_distribution,
                "risk_level_distribution": risk_level_distribution,
                "recent_domains": recent_domain_list
            }
        }
        
    except Exception as e:
        logger.error(f"获取域名统计信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取域名统计信息失败"
        )


@router.post("/{domain_id}/reanalyze")
async def reanalyze_domain(
    domain_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """重新分析域名"""
    try:
        # 查询域名
        query = select(ThirdPartyDomain).where(
            ThirdPartyDomain.id == domain_id
        )
        
        result = await db.execute(query)
        domain = result.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="域名不存在"
            )
        
        # 重置分析状态
        domain.is_analyzed = False  # type: ignore
        domain.analysis_error = None  # type: ignore
        domain.analyzed_at = None  # type: ignore
        domain.cached_analysis_result = None  # type: ignore
        
        # 清除相关违规记录
        delete_violations_query = select(ViolationRecord).where(
            ViolationRecord.domain_id == domain_id
        )
        violations_result = await db.execute(delete_violations_query)
        violations = violations_result.scalars().all()
        
        for violation in violations:
            await db.delete(violation)
        
        await db.commit()
        
        # 返回更新后的域名信息
        updated_domain_data = {
            "id": domain.id,
            "task_id": domain.task_id,
            "domain": domain.domain,
            "found_on_url": domain.found_on_url,
            "domain_type": domain.domain_type,
            "risk_level": domain.risk_level,
            "page_title": domain.page_title,
            "page_description": domain.page_description,
            "content_hash": domain.content_hash,
            "screenshot_path": domain.screenshot_path,
            "html_content_path": domain.html_content_path,
            "is_analyzed": domain.is_analyzed,
            "analysis_error": domain.analysis_error,
            "created_at": domain.created_at.isoformat() if domain.created_at is not None else None,
            "analyzed_at": domain.analyzed_at.isoformat() if domain.analyzed_at is not None else None,
            "has_violations": False
        }
        
        return {
            "success": True,
            "data": updated_domain_data,
            "message": "域名已重置，等待重新分析"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新分析域名失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重新分析域名失败"
        )


@router.post("/batch-delete")
async def batch_delete_domains(
    domain_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """批量删除域名"""
    try:
        if not domain_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要删除的域名"
            )
        
        # 查询要删除的域名
        query = select(ThirdPartyDomain).where(
            ThirdPartyDomain.id.in_(domain_ids)
        )
        
        result = await db.execute(query)
        domains = result.scalars().all()
        
        if not domains:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到指定的域名"
            )
        
        # 删除相关违规记录
        for domain in domains:
            # 删除违规记录
            delete_violations_query = select(ViolationRecord).where(
                ViolationRecord.domain_id == domain.id
            )
            violations_result = await db.execute(delete_violations_query)
            violations = violations_result.scalars().all()
            
            for violation in violations:
                await db.delete(violation)
            
            # 删除域名
            await db.delete(domain)
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"成功删除 {len(domains)} 个域名"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量删除域名失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量删除域名失败"
        )


@router.get("/export")
async def export_domains(
    format: str = Query("json", regex="^(json|csv|excel)$"),
    domain: Optional[str] = Query(None),
    domain_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    has_violations: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导出域名数据"""
    try:
        # 构建查询条件
        conditions = []
        
        if domain:
            conditions.append(ThirdPartyDomain.domain.ilike(f"%{domain}%"))
        
        if domain_type:
            conditions.append(ThirdPartyDomain.domain_type == domain_type)
        
        if risk_level:
            conditions.append(ThirdPartyDomain.risk_level == risk_level)
        
        if has_violations is not None:
            if has_violations:
                conditions.append(ThirdPartyDomain.violations.any())
            else:
                conditions.append(~ThirdPartyDomain.violations.any())
        
        # 查询域名数据
        from sqlalchemy.orm import selectinload
        
        query = select(ThirdPartyDomain).options(
            selectinload(ThirdPartyDomain.violations)
        ).where(
            and_(*conditions)
        ).order_by(ThirdPartyDomain.created_at.desc())
        
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # 根据格式导出数据
        if format == "json":
            # 准备JSON数据
            export_data = []
            for domain in domains:
                domain_data = {
                    "id": domain.id,
                    "domain": domain.domain,
                    "domain_type": domain.domain_type,
                    "risk_level": domain.risk_level,
                    "page_title": domain.page_title,
                    "page_description": domain.page_description,
                    "found_on_url": domain.found_on_url,
                    "is_analyzed": domain.is_analyzed,
                    "created_at": domain.created_at.isoformat() if domain.created_at is not None else None,
                    "analyzed_at": domain.analyzed_at.isoformat() if domain.analyzed_at is not None else None,
                    "violation_count": len(domain.violations),
                    "has_violations": len(domain.violations) > 0
                }
                export_data.append(domain_data)
            
            import json
            from fastapi.responses import Response
            
            json_data = json.dumps(export_data, ensure_ascii=False, indent=2)
            return Response(
                content=json_data,
                media_type="application/json",
                headers={
                    "Content-Disposition": "attachment; filename=domains.json"
                }
            )
        
        elif format == "csv":
            # 准备CSV数据
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow([
                "ID", "域名", "域名类型", "风险等级", "页面标题", "页面描述",
                "发现位置", "是否已分析", "创建时间", "分析时间", "违规数量", "是否有违规"
            ])
            
            # 写入数据
            for domain in domains:
                writer.writerow([
                    domain.id,
                    domain.domain,
                    domain.domain_type,
                    domain.risk_level,
                    domain.page_title or "",
                    domain.page_description or "",
                    domain.found_on_url,
                    "是" if domain.is_analyzed is True else "否",
                    domain.created_at.isoformat() if domain.created_at is not None else "",
                    domain.analyzed_at.isoformat() if domain.analyzed_at is not None else "",
                    len(domain.violations),
                    "是" if len(domain.violations) > 0 else "否"
                ])
            
            csv_data = output.getvalue()
            output.close()
            
            from fastapi.responses import Response
            
            return Response(
                content=csv_data,
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=domains.csv"
                }
            )
        
        elif format == "excel":
            # 准备Excel数据
            try:
                import pandas as pd
                from fastapi.responses import Response
                import io
                
                # 准备数据
                data = []
                for domain in domains:
                    data.append({
                        "ID": domain.id,
                        "域名": domain.domain,
                        "域名类型": domain.domain_type,
                        "风险等级": domain.risk_level,
                        "页面标题": domain.page_title or "",
                        "页面描述": domain.page_description or "",
                        "发现位置": domain.found_on_url,
                        "是否已分析": "是" if domain.is_analyzed is True else "否",
                        "创建时间": domain.created_at.isoformat() if domain.created_at is not None else "",
                        "分析时间": domain.analyzed_at.isoformat() if domain.analyzed_at is not None else "",
                        "违规数量": len(domain.violations),
                        "是否有违规": "是" if len(domain.violations) > 0 else "否"
                    })
                
                # 创建DataFrame
                df = pd.DataFrame(data)
                
                # 写入Excel
                output = io.BytesIO()
                writer = pd.ExcelWriter(output, engine='openpyxl')  # type: ignore
                df.to_excel(writer, sheet_name='域名库', index=False)
                writer.close()
                
                excel_data = output.getvalue()
                output.close()
                
                return Response(
                    content=excel_data,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={
                        "Content-Disposition": "attachment; filename=domains.xlsx"
                    }
                )
                
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="缺少pandas库，无法导出Excel格式"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出域名数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出域名数据失败"
        )
#!/usr/bin/env python3
"""
AI分析诊断脚本
用于调试任务 #57e2c8b5-0066-4816-9d79-62ed597b4604 的AI分析问题
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.database import AsyncSessionLocal
from app.models.domain import DomainRecord
from app.models.user import User, UserAIConfig
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def diagnose_ai_analysis():
    """诊断AI分析问题"""
    task_id = "57e2c8b5-0066-4816-9d79-62ed597b4604"
    
    print("🔍 开始诊断AI分析问题...")
    print(f"📋 任务ID: {task_id}")
    print("=" * 80)
    
    async with AsyncSessionLocal() as db:
        # 1. 检查任务信息
        print("1️⃣ 检查任务信息...")
        task_stmt = select(ScanTask).options(
            selectinload(ScanTask.user)
        ).where(ScanTask.id == task_id)
        task_result = await db.execute(task_stmt)
        task = task_result.scalar_one_or_none()
        
        if not task:
            print(f"❌ 任务不存在: {task_id}")
            return
        
        print(f"✅ 任务存在: {task.target_domain}")
        print(f"   状态: {task.status}")
        print(f"   用户: {task.user.username} (ID: {task.user_id})")
        print(f"   配置: {task.config}")
        print()
        
        # 2. 检查任务配置中的AI分析设置
        print("2️⃣ 检查任务配置...")
        config = task.config or {}
        ai_analysis_enabled = config.get('ai_analysis_enabled', True)
        content_capture_enabled = config.get('content_capture_enabled', True)
        
        print(f"   AI分析启用: {ai_analysis_enabled}")
        print(f"   内容抓取启用: {content_capture_enabled}")
        print(f"   使用并行执行器: {config.get('use_parallel_executor', False)}")
        print(f"   智能预筛选: {config.get('smart_prefilter_enabled', False)}")
        print(f"   AI跳过阈值: {config.get('ai_skip_threshold', 'N/A')}")
        print()
        
        # 3. 检查用户AI配置
        print("3️⃣ 检查用户AI配置...")
        ai_config_stmt = select(UserAIConfig).where(UserAIConfig.user_id == task.user_id)
        ai_config_result = await db.execute(ai_config_stmt)
        ai_config = ai_config_result.scalar_one_or_none()
        
        if not ai_config:
            print("❌ 用户没有AI配置")
            print("💡 解决方案: 请前往设置页面配置OpenAI API密钥和模型")
            return
        
        print(f"✅ 用户有AI配置")
        print(f"   模型: {ai_config.model_name}")
        print(f"   基础URL: {ai_config.openai_base_url}")
        print(f"   有API密钥: {bool(ai_config.openai_api_key)}")
        print(f"   配置有效: {ai_config.has_valid_config}")
        
        if not ai_config.has_valid_config:
            print("❌ AI配置无效")
            print("💡 可能原因:")
            print("   - 缺少OpenAI API密钥")
            print("   - 模型名称未设置")
            print("   - 基础URL未设置")
            return
        
        print()
        
        # 4. 检查第三方域名记录
        print("4️⃣ 检查第三方域名记录...")
        domains_stmt = select(DomainRecord).where(
            DomainRecord.task_id == task_id
        ).limit(10)
        domains_result = await db.execute(domains_stmt)
        domains = domains_result.scalars().all()
        
        if not domains:
            print("❌ 没有发现第三方域名记录")
            print("💡 可能原因:")
            print("   - 子域名发现失败")
            print("   - 链接爬取失败")
            print("   - 第三方域名识别失败")
            return
        
        print(f"✅ 发现 {len(domains)} 个第三方域名记录")
        
        analyzed_count = 0
        screenshot_count = 0
        
        for domain in domains:
            print(f"   🌐 {domain.domain}")
            print(f"      已分析: {domain.is_analyzed}")
            print(f"      截图路径: {domain.screenshot_path}")
            print(f"      分析错误: {domain.analysis_error}")
            
            if domain.is_analyzed:
                analyzed_count += 1
            
            if domain.screenshot_path:
                screenshot_count += 1
                # 检查截图文件是否存在
                if os.path.exists(domain.screenshot_path):
                    file_size = os.path.getsize(domain.screenshot_path)
                    print(f"      截图文件: 存在 ({file_size} bytes)")
                else:
                    print(f"      截图文件: 不存在")
            
            print()
        
        print(f"📊 统计:")
        print(f"   总域名数: {len(domains)}")
        print(f"   已分析: {analyzed_count}")
        print(f"   有截图: {screenshot_count}")
        print()
        
        # 5. 检查违规记录
        print("5️⃣ 检查违规记录...")
        violations_stmt = select(ViolationRecord).where(
            ViolationRecord.task_id == task_id
        )
        violations_result = await db.execute(violations_stmt)
        violations = violations_result.scalars().all()
        
        print(f"📋 发现 {len(violations)} 个违规记录")
        
        if violations:
            for violation in violations:
                print(f"   🚨 {violation.violation_type}")
                print(f"      置信度: {violation.confidence_score}")
                print(f"      风险等级: {violation.risk_level}")
                print(f"      AI模型: {violation.ai_model_used}")
                print()
        else:
            print("💡 没有发现违规记录，可能原因:")
            print("   - AI分析未执行")
            print("   - 内容被预筛选跳过")
            print("   - 没有检测到违规内容")
        
        print()
        
        # 6. 诊断建议
        print("6️⃣ 诊断建议...")
        
        issues = []
        solutions = []
        
        if not ai_analysis_enabled:
            issues.append("❌ AI分析被禁用")
            solutions.append("💡 在任务配置中启用AI分析")
        
        if not ai_config or not ai_config.has_valid_config:
            issues.append("❌ AI配置无效")
            solutions.append("💡 配置有效的OpenAI API密钥和模型")
        
        if screenshot_count == 0:
            issues.append("❌ 没有截图文件")
            solutions.append("💡 检查内容抓取配置和网络连接")
        
        if analyzed_count == 0 and ai_analysis_enabled and ai_config and ai_config.has_valid_config:
            issues.append("❌ 有配置但未执行AI分析")
            solutions.append("💡 可能是预筛选跳过率过高，建议调整ai_skip_threshold")
        
        if issues:
            print("🔧 发现的问题:")
            for issue in issues:
                print(f"   {issue}")
            print()
            print("💡 建议的解决方案:")
            for solution in solutions:
                print(f"   {solution}")
        else:
            print("✅ 未发现明显问题")
            print("💡 如果仍然没有AI分析结果，建议:")
            print("   - 检查日志文件中的详细错误信息")
            print("   - 降低ai_skip_threshold值")
            print("   - 检查OpenAI API配额和网络连接")


if __name__ == "__main__":
    asyncio.run(diagnose_ai_analysis())
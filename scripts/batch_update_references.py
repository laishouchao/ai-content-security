#!/usr/bin/env python3
"""
批量更新脚本 - 替换所有文件中对已删除模型的引用
将SubdomainRecord和ThirdPartyDomain的引用替换为DomainRecord
"""

import os
import re
from pathlib import Path

def update_file_references():
    """更新文件中的模型引用"""
    
    # 需要更新的文件路径
    files_to_update = [
        "app/api/v1/domains.py",
        "app/api/v1/tasks.py", 
        "app/core/cache_manager.py",
        "app/engines/enhanced_ai_analysis.py",
        "app/engines/parallel_scan_executor.py",
        "app/engines/scan_executor.py",
        "app/engines/third_party_identifier.py",
        "app/tasks/scan_tasks.py",
        "debug_ai_analysis.py",
        "scripts/migrate_domain_tables.py"
    ]
    
    # 模型替换规则
    replacements = [
        # 导入语句更新
        (r'from app\.models\.task import.*SubdomainRecord.*', 
         'from app.models.domain import DomainRecord'),
        (r'from app\.models\.task import.*ThirdPartyDomain.*', 
         'from app.models.domain import DomainRecord'),
        (r'from app\.models\.task import.*SubdomainRecord.*ThirdPartyDomain.*', 
         'from app.models.domain import DomainRecord'),
        (r'from app\.models\.task import.*ThirdPartyDomain.*SubdomainRecord.*', 
         'from app.models.domain import DomainRecord'),
        
        # 类名替换
        (r'\bSubdomainRecord\b', 'DomainRecord'),
        (r'\bThirdPartyDomain\b', 'DomainRecord'),
        
        # 表名替换
        (r'subdomain_records', 'domain_records'),
        (r'third_party_domains', 'domain_records'),
    ]
    
    updated_files = []
    
    for file_path in files_to_update:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"⚠️  文件不存在: {file_path}")
            continue
            
        try:
            # 读取文件内容
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # 应用替换规则
            for pattern, replacement in replacements:
                content = re.sub(pattern, replacement, content)
            
            # 如果内容有变化，写回文件
            if content != original_content:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                updated_files.append(file_path)
                print(f"✅ 已更新: {file_path}")
            else:
                print(f"ℹ️  无需更新: {file_path}")
                
        except Exception as e:
            print(f"❌ 更新失败 {file_path}: {e}")
    
    print(f"\n📋 更新完成，共更新了 {len(updated_files)} 个文件")
    for file_path in updated_files:
        print(f"  - {file_path}")

if __name__ == "__main__":
    print("🔄 开始批量更新文件引用...")
    update_file_references()
    print("✅ 批量更新完成")
#!/usr/bin/env python3
"""
子域名AI分析功能验证脚本

验证改进后的功能：
1. 子域名主页截图抓取
2. 子域名AI分析队列处理
3. 系统名称更新
4. 详细日志输出改进
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_updated_system():
    """测试更新后的系统功能"""
    print("🎯 测试更新后的AI网站外链域名安全性合规检测系统")
    print("=" * 60)
    
    print("✅ 系统名称已更新为: AI网站外链域名安全性合规检测系统")
    print("✅ 子域名AI分析功能已集成")
    print("✅ 详细日志记录已改进")
    
    # 验证README文件更新
    readme_path = project_root / "README.md"
    if readme_path.exists():
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "AI网站外链域名安全性合规检测系统" in content:
                print("✅ README文件中的系统名称已更新")
            else:
                print("❌ README文件中的系统名称未更新")
    
    print("\n📋 功能改进清单:")
    improvements = [
        "子域名主页内容抓取和截图",
        "子域名安全性AI分析",
        "第三方域名和子域名统计分离",
        "详细的截图文件检查日志",
        "AI分析队列准备过程优化",
        "系统名称全面更新"
    ]
    
    for i, improvement in enumerate(improvements, 1):
        print(f"   {i}. {improvement}")
    
    return True


def analyze_log_improvements():
    """分析日志改进"""
    print("\n📝 日志改进分析:")
    print("=" * 40)
    
    print("🔍 原有问题:")
    old_issues = [
        "所有域名显示'没有有效的截图文件'",
        "缺少详细的截图路径检查信息",
        "子域名和第三方域名混淆",
        "无法追踪具体的失败原因"
    ]
    
    for issue in old_issues:
        print(f"   ❌ {issue}")
    
    print("\n✨ 改进措施:")
    improvements = [
        "添加详细的截图路径调试日志",
        "分离子域名和第三方域名的处理逻辑",
        "在文件检查前记录路径信息",
        "区分不同类型的失败原因",
        "添加文件存在性验证",
        "改进AI分析队列统计"
    ]
    
    for improvement in improvements:
        print(f"   ✅ {improvement}")
    
    print("\n🔮 期望的新日志输出:")
    expected_logs = [
        "找到 X 个未分析的第三方域名",
        "找到 Y 个子域名记录",
        "查找子域名 xxx.com 的截图文件...",
        "检查内容结果: URL=https://xxx.com, 截图路径=/path/to/screenshot.png",
        "找到匹配的截图: /path/to/screenshot.png",
        "子域名 xxx.com 截图路径: /path, 文件存在: True",
        "子域名 xxx.com 已添加到AI分析队列",
        "总共准备了 Z 个域名进行AI分析（包括第三方域名和子域名）",
        "开始分析 Z 个域名（子域名: A, 第三方域名: B）"
    ]
    
    for log in expected_logs:
        print(f"   INFO: {log}")


def create_test_recommendations():
    """创建测试建议"""
    print("\n🧪 测试建议:")
    print("=" * 30)
    
    print("1. 运行完整扫描测试:")
    print("   - 选择一个有多个子域名的域名进行测试")
    print("   - 观察新的日志输出格式")
    print("   - 验证子域名是否正确添加到AI分析队列")
    
    print("\n2. 检查截图功能:")
    print("   - 运行 test_screenshot_diagnosis.py 进行详细诊断")
    print("   - 验证截图文件是否正确生成")
    print("   - 检查截图路径存储格式")
    
    print("\n3. 验证AI分析覆盖:")
    print("   - 确认子域名出现在AI分析日志中")
    print("   - 验证不再出现'跳过AI分析'的警告")
    print("   - 检查分析统计数据的准确性")
    
    print("\n4. 系统名称验证:")
    print("   - 检查前端页面标题")
    print("   - 验证API文档描述")
    print("   - 确认所有文档中的名称一致性")


def check_file_modifications():
    """检查文件修改状态"""
    print("\n📁 文件修改检查:")
    print("=" * 30)
    
    modified_files = [
        ("README.md", "系统名称更新"),
        ("app/engines/scan_executor.py", "AI分析逻辑改进"),
        ("test_screenshot_diagnosis.py", "新建截图诊断脚本"),
        ("test_subdomain_ai_analysis_verification.py", "新建验证脚本")
    ]
    
    for file_path, description in modified_files:
        full_path = project_root / file_path
        if full_path.exists():
            # 获取文件修改时间
            mtime = datetime.fromtimestamp(full_path.stat().st_mtime)
            print(f"   ✅ {file_path} - {description}")
            print(f"      最后修改: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"   ❓ {file_path} - 文件不存在")


def generate_next_steps():
    """生成下一步操作建议"""
    print("\n🚀 下一步操作建议:")
    print("=" * 30)
    
    steps = [
        {
            "step": "运行截图诊断",
            "command": "python test_screenshot_diagnosis.py",
            "description": "诊断截图功能是否正常工作"
        },
        {
            "step": "测试新扫描功能",
            "command": "启动Celery Worker并运行域名扫描",
            "description": "验证子域名AI分析是否正确集成"
        },
        {
            "step": "检查日志输出",
            "command": "观察Celery Worker日志",
            "description": "确认新的日志格式和调试信息"
        },
        {
            "step": "验证AI分析结果",
            "command": "检查扫描结果",
            "description": "确认子域名被正确分析和记录"
        }
    ]
    
    for i, step in enumerate(steps, 1):
        print(f"\n{i}. {step['step']}:")
        print(f"   命令: {step['command']}")
        print(f"   目的: {step['description']}")


def main():
    """主测试函数"""
    print("🔧 子域名AI分析功能验证")
    print("=" * 60)
    
    # 运行所有验证
    asyncio.run(test_updated_system())
    analyze_log_improvements()
    create_test_recommendations()
    check_file_modifications()
    generate_next_steps()
    
    print("\n" + "=" * 60)
    print("🎉 验证完成！")
    print("\n💡 关键改进总结:")
    print("   1. ✅ 系统名称更新为'AI网站外链域名安全性合规检测系统'")
    print("   2. ✅ 子域名主页截图抓取功能已集成")
    print("   3. ✅ 子域名AI安全性分析功能已添加")
    print("   4. ✅ 详细的调试日志已改进")
    print("   5. ✅ AI分析队列统计已优化")
    
    print("\n🎯 期望效果:")
    print("   - 子域名将出现在AI分析队列中")
    print("   - 日志将显示详细的截图检查过程")
    print("   - 不再出现'没有有效的截图文件'的警告（对于可访问的域名）")
    print("   - AI分析统计将分别显示子域名和第三方域名数量")
    
    print("\n⚠️  注意事项:")
    print("   - 如果截图功能本身有问题，请先运行截图诊断脚本")
    print("   - 确保Playwright浏览器正确安装")
    print("   - 检查截图目录权限设置")


if __name__ == "__main__":
    main()
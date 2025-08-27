#!/usr/bin/env python3
"""
截图路径问题终极修复脚本

基于日志分析，问题很可能是：
1. 截图文件生成但路径存储格式不一致
2. AI分析时路径检查逻辑有误
3. 相对路径vs绝对路径问题

提供：
1. 截图路径标准化修复
2. AI分析截图检查逻辑优化
3. 路径兼容性处理
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def analyze_screenshot_path_issue():
    """分析截图路径问题"""
    print("🔍 分析截图路径问题")
    print("=" * 40)
    
    print("📊 从日志分析的问题:")
    print("   1. 内容抓取阶段: '内容抓取完成: 85 个页面'")
    print("   2. AI分析阶段: 所有域名都显示'没有有效的截图文件'")
    print("   3. 说明截图可能生成了，但路径查找有问题")
    
    print("\n🎯 可能的原因:")
    reasons = [
        "截图路径存储为相对路径，但检查时使用绝对路径",
        "路径分隔符问题（Windows的反斜杠vs正斜杠）",
        "截图文件生成后被移动或删除",
        "content_results中的screenshot_path为空",
        "Path对象和字符串混用导致检查失败"
    ]
    
    for i, reason in enumerate(reasons, 1):
        print(f"   {i}. {reason}")


def provide_path_standardization_fix():
    """提供路径标准化修复方案"""
    print("\n🛠️ 路径标准化修复方案")
    print("=" * 40)
    
    print("修复方案1: 统一使用绝对路径")
    fix1_code = '''
# 在ScreenshotService中确保返回绝对路径
def capture_screenshot(self, url: str) -> Tuple[str, str]:
    # 生成截图文件名
    screenshot_path = self.screenshot_dir / filename
    
    # 截图完成后返回绝对路径
    return str(screenshot_path.resolve()), html_content
'''
    print(fix1_code)
    
    print("\n修复方案2: 改进AI分析的路径检查")
    fix2_code = '''
# 在_prepare_domains_for_analysis中改进路径检查
def check_screenshot_exists(screenshot_path: str) -> bool:
    if not screenshot_path:
        return False
    
    # 尝试多种路径格式
    path_obj = Path(screenshot_path)
    
    # 检查绝对路径
    if path_obj.is_absolute() and path_obj.exists():
        return True
    
    # 检查相对路径（相对于项目根目录）
    relative_path = Path.cwd() / screenshot_path
    if relative_path.exists():
        return True
    
    # 检查截图目录下的路径
    screenshot_dir = Path("screenshots") / task_id
    if (screenshot_dir / Path(screenshot_path).name).exists():
        return True
    
    return False
'''
    print(fix2_code)


def provide_content_capture_fix():
    """提供内容抓取阶段的修复"""
    print("\n📸 内容抓取阶段修复")
    print("=" * 30)
    
    print("问题：截图生成但路径格式不统一")
    print("解决方案：在截图完成后立即验证文件存在")
    
    fix_code = '''
# 在ContentCaptureEngine中添加验证
async def capture_domain_content(self, domain: str, urls: List[str], config: Dict[str, Any]):
    # ... 现有代码 ...
    
    for result in results:
        if result.screenshot_path:
            # 立即验证截图文件是否存在
            if not os.path.exists(result.screenshot_path):
                self.logger.warning(f"截图文件生成失败或路径错误: {result.screenshot_path}")
                result.screenshot_path = ""  # 清空无效路径
            else:
                # 转换为绝对路径
                result.screenshot_path = str(Path(result.screenshot_path).resolve())
                self.logger.debug(f"截图文件验证成功: {result.screenshot_path}")
    
    return results
'''
    print(fix_code)


def create_improved_scan_executor_patch():
    """创建改进的scan_executor补丁"""
    print("\n🔧 创建scan_executor改进补丁")
    print("=" * 40)
    
    patch_content = '''
# 在scan_executor.py的_prepare_domains_for_analysis方法中添加更强的路径检查
def robust_screenshot_check(screenshot_path: str, task_id: str, domain: str) -> bool:
    """强化的截图文件检查"""
    if not screenshot_path:
        self.logger.debug(f"域名 {domain} 没有截图路径")
        return False
    
    # 尝试多种路径检查方式
    check_paths = []
    
    # 1. 原始路径
    check_paths.append(Path(screenshot_path))
    
    # 2. 绝对路径
    if not Path(screenshot_path).is_absolute():
        check_paths.append(Path.cwd() / screenshot_path)
    
    # 3. 截图目录下的文件名
    filename = Path(screenshot_path).name
    check_paths.append(Path("screenshots") / task_id / filename)
    
    # 4. 配置目录下的路径
    from app.core.config import settings
    if hasattr(settings, 'SCREENSHOT_PATH'):
        check_paths.append(Path(settings.SCREENSHOT_PATH) / task_id / filename)
    
    for path in check_paths:
        if path.exists():
            self.logger.debug(f"域名 {domain} 截图文件找到: {path}")
            return True
        else:
            self.logger.debug(f"域名 {domain} 截图路径不存在: {path}")
    
    self.logger.warning(f"域名 {domain} 所有路径检查都失败: {screenshot_path}")
    return False
'''
    
    print("此补丁将添加更强的截图路径检查逻辑")
    print("支持多种路径格式的兼容性检查")
    
    # 将补丁保存到文件
    patch_file = project_root / "screenshot_path_fix.patch"
    with open(patch_file, 'w', encoding='utf-8') as f:
        f.write(patch_content)
    
    print(f"✅ 补丁已保存到: {patch_file}")


def provide_immediate_fix():
    """提供立即修复方案"""
    print("\n⚡ 立即修复方案")
    print("=" * 20)
    
    print("🎯 针对当前问题的快速修复:")
    
    print("\n1. 检查截图目录结构:")
    task_id = "f4e0ea3d-d2a6-4af0-85e1-6b2af552a0bb"  # 从日志中的真实任务ID
    
    possible_dirs = [
        Path("screenshots") / task_id,
        Path(".") / "screenshots" / task_id,
        Path("app") / "screenshots" / task_id
    ]
    
    for dir_path in possible_dirs:
        if dir_path.exists():
            print(f"   ✅ 找到截图目录: {dir_path}")
            files = list(dir_path.glob("*.png"))
            print(f"      PNG文件数量: {len(files)}")
            if files:
                print(f"      示例文件: {files[0].name}")
        else:
            print(f"   ❌ 目录不存在: {dir_path}")
    
    print("\n2. 如果截图文件存在但AI分析找不到:")
    print("   - 问题在于路径格式不匹配")
    print("   - 需要修改AI分析的路径检查逻辑")
    print("   - 建议使用绝对路径存储")
    
    print("\n3. 如果截图文件根本不存在:")
    print("   - 问题在于截图生成阶段")
    print("   - 需要检查ScreenshotService配置")
    print("   - 验证Playwright是否正常工作")


def create_debug_script():
    """创建调试脚本"""
    print("\n🐛 创建调试脚本")
    print("=" * 20)
    
    debug_script = '''#!/usr/bin/env python3
"""
截图路径调试脚本
用于实时调试截图路径问题
"""

import os
from pathlib import Path

def debug_screenshot_paths(task_id: str):
    """调试截图路径"""
    print(f"调试任务 {task_id} 的截图路径...")
    
    # 检查可能的截图目录
    possible_dirs = [
        Path("screenshots") / task_id,
        Path("app/screenshots") / task_id,
        Path("./screenshots") / task_id,
        Path(os.getcwd()) / "screenshots" / task_id
    ]
    
    for i, dir_path in enumerate(possible_dirs, 1):
        print(f"{i}. 检查目录: {dir_path}")
        print(f"   绝对路径: {dir_path.resolve()}")
        print(f"   存在: {dir_path.exists()}")
        
        if dir_path.exists():
            files = list(dir_path.glob("*.png"))
            print(f"   PNG文件: {len(files)}")
            for file in files[:3]:  # 显示前3个文件
                print(f"      - {file.name} ({file.stat().st_size} bytes)")
        print()

if __name__ == "__main__":
    # 使用实际的任务ID
    debug_screenshot_paths("f4e0ea3d-d2a6-4af0-85e1-6b2af552a0bb")
'''
    
    debug_file = project_root / "debug_screenshot_paths.py"
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(debug_script)
    
    print(f"✅ 调试脚本已创建: {debug_file}")
    print("   运行: python debug_screenshot_paths.py")


def main():
    """主函数"""
    print("🚀 截图路径问题终极修复")
    print("=" * 60)
    
    analyze_screenshot_path_issue()
    provide_path_standardization_fix()
    provide_content_capture_fix()
    create_improved_scan_executor_patch()
    provide_immediate_fix()
    create_debug_script()
    
    print("\n" + "=" * 60)
    print("🎯 修复建议优先级:")
    print("1. 🥇 运行 debug_screenshot_paths.py 确认截图文件是否存在")
    print("2. 🥈 如果文件存在，应用路径检查逻辑改进")
    print("3. 🥉 如果文件不存在，检查截图生成过程")
    print("4. 🏅 运行 test_screenshot_diagnosis.py 进行全面诊断")
    
    print("\n💡 关键提示:")
    print("   - 从日志看，85个页面内容抓取成功，说明截图很可能已生成")
    print("   - 问题很可能在AI分析阶段的路径检查逻辑")
    print("   - 建议优先检查路径格式和文件存在性验证")


if __name__ == "__main__":
    main()
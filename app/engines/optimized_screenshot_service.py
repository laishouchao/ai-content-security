"""
优化的截图服务
实现每个域名只截图一张，同时获取源码，并为AI分析生成临时输出文件
"""

import asyncio
import aiohttp
import time
import os
import json
import hashlib
from typing import List, Dict, Optional, Any, Tuple, Set
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup, Tag

from app.core.logging import TaskLogger
from app.core.config import settings


@dataclass
class DomainScreenshotResult:
    """域名截图结果"""
    domain: str
    url: str
    screenshot_path: str
    source_code_path: str
    page_title: str
    page_description: str
    text_content: str
    content_hash: str
    file_size: int
    success: bool
    error_message: str = ""
    captured_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.captured_at is None:
            self.captured_at = datetime.utcnow()


class OptimizedScreenshotService:
    """优化的截图服务"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 设置存储路径
        self.screenshot_dir = Path("storage/screenshots") / task_id
        self.source_code_dir = Path("storage/source_code") / task_id
        self.temp_analysis_dir = Path("storage/temp_analysis") / task_id
        
        # 创建目录
        for directory in [self.screenshot_dir, self.source_code_dir, self.temp_analysis_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # 跟踪已处理的域名，避免重复
        self.processed_domains: Set[str] = set()
        
        # 浏览器相关
        self.browser = None
        self.context = None
        self.playwright = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.playwright = await async_playwright().start()
        
        # 启动浏览器
        self.browser = await self.playwright.chromium.launch(
            headless=settings.PLAYWRIGHT_HEADLESS,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080'
            ]
        )
        
        # 创建浏览器上下文
        self.context = await self.browser.new_context(
            viewport={
                'width': settings.SCREENSHOT_VIEWPORT_WIDTH,
                'height': settings.SCREENSHOT_VIEWPORT_HEIGHT
            },
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def capture_domains_optimized(
        self, 
        domains: List[str], 
        config: Dict[str, Any]
    ) -> List[DomainScreenshotResult]:
        """批量优化截图 - 每个域名只截图一张"""
        results = []
        
        # 去重域名
        unique_domains = list(set(domains))
        self.logger.info(f"开始优化截图: {len(unique_domains)} 个唯一域名")
        
        # 限制并发数，避免资源过载
        semaphore = asyncio.Semaphore(2)
        
        async def capture_single_domain(domain: str):
            async with semaphore:
                return await self._capture_single_domain_optimized(domain, config)
        
        # 并发处理
        tasks = [capture_single_domain(domain) for domain in unique_domains]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        valid_results = []
        for result in results:
            if isinstance(result, DomainScreenshotResult):
                valid_results.append(result)
                if result.success:
                    self.processed_domains.add(result.domain)
            elif isinstance(result, Exception):
                self.logger.error(f"域名截图异常: {result}")
        
        self.logger.info(f"优化截图完成: 成功 {len([r for r in valid_results if r.success])}, 失败 {len([r for r in valid_results if not r.success])}")
        
        return valid_results
    
    async def _capture_single_domain_optimized(
        self, 
        domain: str, 
        config: Dict[str, Any]
    ) -> DomainScreenshotResult:
        """单个域名优化截图"""
        
        # 检查是否已处理过
        if domain in self.processed_domains:
            self.logger.debug(f"域名 {domain} 已处理过，跳过")
            return self._create_error_result(domain, "", "域名已处理过")
        
        # 检查是否已存在截图文件
        existing_screenshot = self._find_existing_screenshot(domain)
        if existing_screenshot and config.get('skip_existing', True):
            self.logger.debug(f"域名 {domain} 已存在截图文件: {existing_screenshot}")
            return await self._load_existing_result(domain, existing_screenshot)
        
        # 尝试多个URL
        urls_to_try = [
            f"https://{domain}",
            f"http://{domain}",
            f"https://www.{domain}",
            f"http://www.{domain}"
        ]
        
        for url in urls_to_try:
            try:
                result = await self._capture_url_content(url, domain, config)
                if result.success:
                    self.logger.info(f"域名 {domain} 截图成功: {url}")
                    return result
                else:
                    self.logger.debug(f"URL {url} 截图失败: {result.error_message}")
            except Exception as e:
                self.logger.debug(f"URL {url} 截图异常: {e}")
                continue
        
        # 所有URL都失败，返回错误结果
        return self._create_error_result(domain, urls_to_try[0], "所有URL尝试均失败")
    
    async def _capture_url_content(
        self, 
        url: str, 
        domain: str, 
        config: Dict[str, Any]
    ) -> DomainScreenshotResult:
        """抓取URL内容和截图"""
        page = None
        
        try:
            if self.context is None:
                raise Exception("浏览器上下文未初始化")
            
            page = await self.context.new_page()
            page.set_default_timeout(settings.PLAYWRIGHT_TIMEOUT)
            
            # 访问页面
            response = await page.goto(url, wait_until='networkidle')
            
            if response and response.status >= 400:
                raise Exception(f"页面返回错误状态: {response.status}")
            
            # 等待页面加载完成
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)  # 额外等待时间确保动态内容加载
            
            # 提取页面信息
            page_title = await page.title()
            page_description = await page.evaluate('''
                () => {
                    const meta = document.querySelector('meta[name="description"]');
                    return meta ? meta.getAttribute('content') : '';
                }
            ''')
            
            # 获取页面文本内容
            text_content = await page.evaluate('''
                () => {
                    const text = document.body.innerText || document.body.textContent || '';
                    return text.substring(0, 5000);  // 增加到5000字符
                }
            ''')
            
            # 获取完整HTML源码
            html_content = await page.content()
            
            # 生成文件名
            safe_domain = self._make_safe_filename(domain)
            timestamp = int(time.time())
            
            screenshot_filename = f"{safe_domain}.png"  # 不使用时间戳，避免重复
            source_code_filename = f"{safe_domain}_source.html"
            
            screenshot_path = self.screenshot_dir / screenshot_filename
            source_code_path = self.source_code_dir / source_code_filename
            
            # 截图
            await page.screenshot(
                path=str(screenshot_path),
                full_page=True,
                type='png'
            )
            
            # 保存源码
            with open(source_code_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 计算内容哈希
            content_hash = hashlib.md5(html_content.encode('utf-8')).hexdigest()
            
            # 获取截图文件大小
            file_size = screenshot_path.stat().st_size if screenshot_path.exists() else 0
            
            # 创建AI分析临时文件
            await self._create_analysis_temp_file(domain, {
                'url': url,
                'domain': domain,
                'page_title': page_title,
                'page_description': page_description,
                'text_content': text_content,
                'content_hash': content_hash,
                'screenshot_path': str(screenshot_path),
                'source_code_path': str(source_code_path),
                'captured_at': datetime.utcnow().isoformat()
            })
            
            return DomainScreenshotResult(
                domain=domain,
                url=url,
                screenshot_path=str(screenshot_path),
                source_code_path=str(source_code_path),
                page_title=page_title,
                page_description=str(page_description),
                text_content=text_content,
                content_hash=content_hash,
                file_size=file_size,
                success=True
            )
            
        except Exception as e:
            return self._create_error_result(domain, url, str(e))
        
        finally:
            if page:
                await page.close()
    
    async def _create_analysis_temp_file(self, domain: str, analysis_data: Dict[str, Any]):
        """为AI分析创建临时文件"""
        temp_filename = f"{self._make_safe_filename(domain)}_analysis_input.json"
        temp_path = self.temp_analysis_dir / temp_filename
        
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"创建AI分析临时文件: {temp_path}")
        except Exception as e:
            self.logger.warning(f"创建AI分析临时文件失败: {e}")
    
    def _find_existing_screenshot(self, domain: str) -> Optional[str]:
        """查找域名的现有截图文件"""
        safe_domain = self._make_safe_filename(domain)
        
        # 优先查找不带时间戳的文件
        preferred_path = self.screenshot_dir / f"{safe_domain}.png"
        if preferred_path.exists() and preferred_path.stat().st_size > 100:
            return str(preferred_path)
        
        # 查找带时间戳的文件
        domain_files = list(self.screenshot_dir.glob(f"{safe_domain}_*.png"))
        if domain_files:
            # 返回最新的文件
            latest_file = max(domain_files, key=lambda f: f.stat().st_mtime)
            if latest_file.stat().st_size > 100:
                return str(latest_file)
        
        return None
    
    async def _load_existing_result(self, domain: str, screenshot_path: str) -> DomainScreenshotResult:
        """加载现有的截图结果"""
        try:
            screenshot_file = Path(screenshot_path)
            source_code_path = self.source_code_dir / f"{self._make_safe_filename(domain)}_source.html"
            
            # 读取源码（如果存在）
            text_content = ""
            page_title = domain
            page_description = ""
            content_hash = ""
            
            if source_code_path.exists():
                with open(source_code_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                    content_hash = hashlib.md5(html_content.encode('utf-8')).hexdigest()
                    
                    # 简单提取标题
                    soup = BeautifulSoup(html_content, 'html.parser')
                    if soup.title:
                        page_title = soup.title.get_text()
                    
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc and isinstance(meta_desc, Tag):
                        content = meta_desc.get('content', '')
                        page_description = str(content) if content else ''
                    
                    text_content = soup.get_text()[:5000]
            
            return DomainScreenshotResult(
                domain=domain,
                url=f"https://{domain}",
                screenshot_path=screenshot_path,
                source_code_path=str(source_code_path),
                page_title=page_title,
                page_description=str(page_description),
                text_content=text_content,
                content_hash=content_hash,
                file_size=screenshot_file.stat().st_size,
                success=True
            )
        
        except Exception as e:
            return self._create_error_result(domain, f"https://{domain}", f"加载现有结果失败: {e}")
    
    def _create_error_result(self, domain: str, url: str, error_message: str) -> DomainScreenshotResult:
        """创建错误结果"""
        return DomainScreenshotResult(
            domain=domain,
            url=url,
            screenshot_path="",
            source_code_path="",
            page_title="",
            page_description="",
            text_content="",
            content_hash="",
            file_size=0,
            success=False,
            error_message=error_message
        )
    
    def _make_safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        safe_filename = ''.join(c if c in safe_chars else '_' for c in filename)
        
        if len(safe_filename) > 50:
            safe_filename = safe_filename[:50]
        
        return safe_filename or "unknown"
    
    async def get_domain_analysis_data(self, domain: str) -> Optional[Dict[str, Any]]:
        """获取域名的分析数据（包含截图和源码路径）"""
        safe_domain = self._make_safe_filename(domain)
        
        # 查找截图文件
        screenshot_path = self._find_existing_screenshot(domain)
        if not screenshot_path:
            return None
        
        # 查找源码文件
        source_code_path = self.source_code_dir / f"{safe_domain}_source.html"
        
        # 查找分析临时文件
        temp_analysis_path = self.temp_analysis_dir / f"{safe_domain}_analysis_input.json"
        
        result = {
            'domain': domain,
            'screenshot_path': screenshot_path,
            'source_code_path': str(source_code_path) if source_code_path.exists() else None,
            'temp_analysis_path': str(temp_analysis_path) if temp_analysis_path.exists() else None
        }
        
        # 如果有临时分析文件，读取其中的数据
        if temp_analysis_path.exists():
            try:
                with open(temp_analysis_path, 'r', encoding='utf-8') as f:
                    analysis_data = json.load(f)
                    result.update(analysis_data)
            except Exception as e:
                self.logger.warning(f"读取分析临时文件失败: {e}")
        
        return result
    
    async def cleanup_temp_files(self):
        """清理临时文件"""
        try:
            # 清理分析临时文件
            for temp_file in self.temp_analysis_dir.glob("*.json"):
                temp_file.unlink()
            
            self.logger.info(f"清理临时文件完成: {self.temp_analysis_dir}")
        except Exception as e:
            self.logger.warning(f"清理临时文件失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取截图统计信息"""
        try:
            screenshot_files = list(self.screenshot_dir.glob("*.png"))
            source_code_files = list(self.source_code_dir.glob("*.html"))
            temp_files = list(self.temp_analysis_dir.glob("*.json"))
            
            total_screenshot_size = sum(f.stat().st_size for f in screenshot_files)
            total_source_size = sum(f.stat().st_size for f in source_code_files)
            
            return {
                'screenshot_count': len(screenshot_files),
                'source_code_count': len(source_code_files),
                'temp_file_count': len(temp_files),
                'processed_domains': len(self.processed_domains),
                'total_screenshot_size_mb': round(total_screenshot_size / 1024 / 1024, 2),
                'total_source_size_mb': round(total_source_size / 1024 / 1024, 2)
            }
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}
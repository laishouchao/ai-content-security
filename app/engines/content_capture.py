import asyncio
import aiohttp
import time
import os
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlparse
from datetime import datetime
import hashlib
import base64
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

from app.core.logging import TaskLogger
from app.core.config import settings
from app.engines.optimized_screenshot_service import OptimizedScreenshotService


class ContentResult:
    """内容抓取结果"""
    
    def __init__(self, url: str, domain: str):
        self.url = url
        self.domain = domain
        self.html_content = ""
        self.text_content = ""
        self.page_title = ""
        self.meta_description = ""
        self.screenshot_path = ""
        self.content_hash = ""
        self.file_size = 0
        self.status_code = None  # type: Optional[int]
        self.error_message = ""
        self.captured_at = datetime.utcnow()
        self.capture_duration = 0.0  # type: float
    
    def set_content_hash(self, content: str):
        """设置内容哈希"""
        self.content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()


class ScreenshotService:
    """截图服务"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.screenshot_dir = Path(settings.SCREENSHOT_PATH) / task_id
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        self.browser = None
        self.context = None
    
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
    
    async def capture_screenshot(self, url: str, filename: Optional[str] = None) -> Tuple[str, str]:
        """截取页面截图"""
        if not filename:
            # 生成安全的文件名
            safe_domain = self._make_safe_filename(urlparse(url).netloc)
            timestamp = int(time.time())
            filename = f"{safe_domain}_{timestamp}.png"
        
        screenshot_path = self.screenshot_dir / filename
        
        page = None
        try:
            # 检查context是否已初始化
            if self.context is None:
                raise Exception("浏览器上下文未初始化")
                
            page = await self.context.new_page()
            
            # 设置超时
            page.set_default_timeout(settings.PLAYWRIGHT_TIMEOUT)
            
            # 访问页面
            response = await page.goto(url, wait_until='networkidle')
            
            if response and response.status >= 400:
                raise Exception(f"页面返回错误状态: {response.status}")
            
            # 等待页面加载完成
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)  # 额外等待时间确保动态内容加载
            
            # 截图
            await page.screenshot(
                path=str(screenshot_path),
                full_page=True,
                type='png'
            )
            
            # 获取页面HTML内容
            html_content = await page.content()
            
            return str(screenshot_path), html_content
            
        except Exception as e:
            # 如果截图失败，创建一个错误截图
            error_screenshot = await self._create_error_screenshot(url, str(e))
            return error_screenshot, ""
            
        finally:
            if page:
                await page.close()
    
    async def _create_error_screenshot(self, url: str, error_message: str) -> str:
        """创建错误截图"""
        safe_domain = self._make_safe_filename(urlparse(url).netloc)
        timestamp = int(time.time())
        filename = f"{safe_domain}_{timestamp}_error.png"
        screenshot_path = self.screenshot_dir / filename
        
        try:
            # 检查context是否已初始化
            if self.context is None:
                raise Exception("浏览器上下文未初始化，无法创建错误截图")
                
            page = await self.context.new_page()
            
            # 创建错误页面HTML
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Screenshot Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 50px; background: #f5f5f5; }}
                    .error-container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .error-title {{ color: #d32f2f; font-size: 24px; margin-bottom: 20px; }}
                    .error-url {{ background: #f0f0f0; padding: 10px; border-radius: 5px; word-break: break-all; }}
                    .error-message {{ color: #666; margin-top: 15px; }}
                </style>
            </head>
            <body>
                <div class="error-container">
                    <div class="error-title">页面截图失败</div>
                    <div class="error-url">{url}</div>
                    <div class="error-message">错误信息: {error_message}</div>
                    <div class="error-message">时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                </div>
            </body>
            </html>
            """
            
            await page.set_content(error_html)
            await page.screenshot(path=str(screenshot_path), type='png')
            await page.close()
            
        except Exception:
            pass
        
        return str(screenshot_path)
    
    def _make_safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        # 移除或替换不安全的字符
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        safe_filename = ''.join(c if c in safe_chars else '_' for c in filename)
        
        # 限制长度
        if len(safe_filename) > 50:
            safe_filename = safe_filename[:50]
        
        return safe_filename or "unknown"


class ContentExtractor:
    """内容提取器"""
    
    def __init__(self):
        pass
    
    def extract_text_content(self, html: str) -> Dict[str, str]:
        """从HTML中提取文本内容"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 移除脚本和样式标签
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 提取页面标题
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # 提取meta描述
            meta_description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            # 检查meta_desc是否为Tag类型
            from bs4 import Tag
            if isinstance(meta_desc, Tag):
                content_value = meta_desc.get('content')
                if content_value is not None:
                    # 确保content_value是字符串类型
                    if isinstance(content_value, str):
                        meta_description = content_value.strip()
                    elif isinstance(content_value, list) and len(content_value) > 0:
                        meta_description = content_value[0].strip()
            
            # 提取正文内容
            text_content = soup.get_text()
            
            # 清理文本
            lines = (line.strip() for line in text_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text_content = ' '.join(chunk for chunk in chunks if chunk)
            
            # 限制内容长度
            max_length = 50000  # 50KB文本
            if len(text_content) > max_length:
                text_content = text_content[:max_length] + "... [内容过长已截断]"
            
            return {
                'title': title,
                'meta_description': meta_description,
                'text_content': text_content
            }
            
        except Exception as e:
            return {
                'title': "",
                'meta_description': "",
                'text_content': f"内容提取失败: {str(e)}"
            }


class ContentCaptureEngine:
    """内容抓取引擎"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        self.content_extractor = ContentExtractor()
        self.captured_count = 0
        self.failed_count = 0
    
    async def capture_domain_content(
        self, 
        domain: str, 
        urls: List[str], 
        config: Dict[str, Any]
    ) -> List[ContentResult]:
        """抓取域名内容"""
        start_time = time.time()
        self.logger.info(f"🚀 开始抓取域名内容: {domain}, {len(urls)} 个URL")
        
        results = []
        max_captures = config.get('max_captures_per_domain', 50)
        capture_screenshots = config.get('capture_screenshots', True)
        
        self.logger.info(f"📸 截图配置: capture_screenshots={capture_screenshots}")
        
        # 限制抓取数量
        urls_to_capture = urls[:max_captures]
        self.logger.info(f"📋 准备抓取 {len(urls_to_capture)} 个URL")
        
        # 使用优化的截图服务
        if capture_screenshots:
            try:
                self.logger.info("🔧 初始化优化截图服务...")
                async with OptimizedScreenshotService(self.task_id, self.user_id) as optimized_service:
                    # 提取域名列表，每个域名只截图一张
                    unique_domains = list(set([urlparse(url).netloc for url in urls_to_capture]))
                    self.logger.info(f"🌐 发现 {len(unique_domains)} 个唯一域名: {unique_domains}")
                    
                    # 优化截图
                    self.logger.info("📸 开始批量截图...")
                    screenshot_results = await optimized_service.capture_domains_optimized(
                        unique_domains, config
                    )
                    
                    self.logger.info(f"📊 截图结果: {len(screenshot_results)} 个")
                    
                    # 转换为ContentResult格式
                    for i, screenshot_result in enumerate(screenshot_results):
                        self.logger.debug(f"处理截图结果 {i+1}/{len(screenshot_results)}: {screenshot_result.domain}")
                        
                        if screenshot_result.success:
                            content_result = ContentResult(screenshot_result.url, screenshot_result.domain)
                            content_result.screenshot_path = screenshot_result.screenshot_path
                            content_result.html_content = screenshot_result.text_content  # 使用提取的文本
                            content_result.page_title = screenshot_result.page_title
                            content_result.meta_description = screenshot_result.page_description
                            content_result.text_content = screenshot_result.text_content
                            content_result.set_content_hash(screenshot_result.text_content)
                            content_result.file_size = screenshot_result.file_size
                            content_result.status_code = 200
                            content_result.capture_duration = time.time() - start_time
                            
                            self.logger.info(f"✅ 成功抓取: {screenshot_result.domain} - 截图路径: {screenshot_result.screenshot_path}")
                            results.append(content_result)
                            self.captured_count += 1
                        else:
                            # 为失败的域名创建错误结果
                            content_result = ContentResult(screenshot_result.url, screenshot_result.domain)
                            content_result.error_message = screenshot_result.error_message
                            content_result.status_code = 500
                            
                            self.logger.warning(f"❌ 抓取失败: {screenshot_result.domain} - 错误: {screenshot_result.error_message}")
                            results.append(content_result)
                            self.failed_count += 1
                            
            except Exception as e:
                self.logger.error(f"💥 截图服务异常: {e}")
                import traceback
                self.logger.error(f"错误堆栈: {traceback.format_exc()}")
                
                # 如果截图服务失败，尝试不截图的方式
                self.logger.info("🔄 截图服务失败，尝试不截图的方式...")
                results = await self._capture_without_screenshots(
                    urls_to_capture, domain, config
                )
        else:
            self.logger.info("📝 仅抓取内容，不截图")
            results = await self._capture_without_screenshots(
                urls_to_capture, domain, config
            )
        
        duration = time.time() - start_time
        self.logger.info(f"🏁 域名内容抓取完成: 成功 {self.captured_count}, 失败 {self.failed_count}, 耗时 {duration:.2f} 秒")
        
        # 输出详细的结果统计
        for result in results:
            self.logger.debug(f"结果详情: {result.domain} - 截图路径: {result.screenshot_path} - 状态: {result.status_code}")
        
        return results
    
    async def _capture_with_screenshots(
        self, 
        urls: List[str], 
        domain: str, 
        screenshot_service: ScreenshotService,
        config: Dict[str, Any]
    ) -> List[ContentResult]:
        """使用截图服务抓取内容"""
        results = []
        
        # 限制并发数
        semaphore = asyncio.Semaphore(3)  # 截图比较消耗资源，限制并发数
        
        async def capture_single_url(url: str):
            async with semaphore:
                return await self._capture_single_page_with_screenshot(
                    url, domain, screenshot_service, config
                )
        
        # 批量抓取
        tasks = [capture_single_url(url) for url in urls]
        capture_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for result in capture_results:
            if isinstance(result, ContentResult):
                results.append(result)
                if result.error_message:
                    self.failed_count += 1
                else:
                    self.captured_count += 1
            elif isinstance(result, Exception):
                self.logger.debug(f"内容抓取异常: {result}")
                self.failed_count += 1
        
        return results
    
    async def _capture_without_screenshots(
        self, 
        urls: List[str], 
        domain: str, 
        config: Dict[str, Any]
    ) -> List[ContentResult]:
        """不使用截图服务抓取内容"""
        results = []
        
        # 限制并发数
        semaphore = asyncio.Semaphore(10)
        
        async def capture_single_url(url: str):
            async with semaphore:
                return await self._capture_single_page_without_screenshot(
                    url, domain, config
                )
        
        # 批量抓取
        tasks = [capture_single_url(url) for url in urls]
        capture_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for result in capture_results:
            if isinstance(result, ContentResult):
                results.append(result)
                if result.error_message:
                    self.failed_count += 1
                else:
                    self.captured_count += 1
            elif isinstance(result, Exception):
                self.logger.debug(f"内容抓取异常: {result}")
                self.failed_count += 1
        
        return results
    
    async def _capture_single_page_with_screenshot(
        self, 
        url: str, 
        domain: str, 
        screenshot_service: ScreenshotService,
        config: Dict[str, Any]
    ) -> ContentResult:
        """抓取单个页面（包含截图）"""
        start_time = time.time()
        result = ContentResult(url, domain)
        
        try:
            # 截图并获取HTML内容
            screenshot_path, html_content = await screenshot_service.capture_screenshot(url)
            
            result.screenshot_path = screenshot_path
            result.html_content = html_content
            result.capture_duration = time.time() - start_time
            
            if html_content:
                # 提取文本内容
                extracted = self.content_extractor.extract_text_content(html_content)
                result.page_title = extracted['title']
                result.meta_description = extracted['meta_description']
                result.text_content = extracted['text_content']
                result.set_content_hash(html_content)
                
                # 计算文件大小
                if os.path.exists(screenshot_path):
                    result.file_size = os.path.getsize(screenshot_path)
                
                result.status_code = 200
                self.logger.debug(f"页面内容抓取成功: {url}")
            else:
                result.error_message = "无法获取页面内容"
                result.status_code = 500
                
        except Exception as e:
            result.error_message = f"抓取失败: {str(e)}"
            result.capture_duration = time.time() - start_time
            self.logger.debug(f"页面内容抓取失败: {url} - {e}")
        
        return result
    
    async def _capture_single_page_without_screenshot(
        self, 
        url: str, 
        domain: str, 
        config: Dict[str, Any]
    ) -> ContentResult:
        """抓取单个页面（不包含截图）"""
        start_time = time.time()
        result = ContentResult(url, domain)
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    result.status_code = response.status
                    result.capture_duration = time.time() - start_time
                    
                    if response.status == 200:
                        html_content = await response.text()
                        result.html_content = html_content
                        
                        # 提取文本内容
                        extracted = self.content_extractor.extract_text_content(html_content)
                        result.page_title = extracted['title']
                        result.meta_description = extracted['meta_description']
                        result.text_content = extracted['text_content']
                        result.set_content_hash(html_content)
                        
                        self.logger.debug(f"页面内容抓取成功: {url}")
                    else:
                        result.error_message = f"HTTP错误: {response.status}"
                        
        except asyncio.TimeoutError:
            result.error_message = "请求超时"
            result.capture_duration = time.time() - start_time
        except Exception as e:
            result.error_message = f"抓取失败: {str(e)}"
            result.capture_duration = time.time() - start_time
            self.logger.debug(f"页面内容抓取失败: {url} - {e}")
        
        return result
    
    async def get_capture_statistics(self) -> Dict[str, Any]:
        """获取抓取统计信息"""
        return {
            'total_captured': self.captured_count,
            'total_failed': self.failed_count,
            'success_rate': self.captured_count / (self.captured_count + self.failed_count) if (self.captured_count + self.failed_count) > 0 else 0
        }
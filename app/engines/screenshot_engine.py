"""
网页截图引擎
基于CSDN文章3的Go Chromedp思路，使用Python和Playwright实现

核心功能：
1. 高性能网页截图
2. 支持全屏和视窗截图
3. 智能等待和错误处理
4. 批量截图处理
5. 多浏览器支持
6. 反检测机制

参考CSDN文章3的Go实现，转换为Python版本
"""

import asyncio
import time
import os
import base64
from typing import Dict, List, Set, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import json

from app.core.logging import TaskLogger

# 尝试导入Playwright
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    # 定义占位类型
    class Playwright: pass
    class Browser: pass
    class BrowserContext: pass
    class Page: pass
    async_playwright = None

# 尝试导入Selenium作为备用
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.wait import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None
    ChromeOptions = None
    By = None
    WebDriverWait = None
    EC = None


@dataclass
class ScreenshotConfig:
    """截图配置"""
    width: int = 1280
    height: int = 800
    full_page: bool = False
    quality: int = 95
    format: str = 'png'  # 'png' or 'jpeg'
    timeout: int = 30
    wait_for_load: bool = True
    wait_for_network: bool = True
    wait_time: float = 2.0  # 额外等待时间
    retry_count: int = 3
    enable_javascript: bool = True
    enable_images: bool = True
    user_agent: str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'


@dataclass
class ScreenshotResult:
    """截图结果"""
    url: str
    success: bool
    screenshot_path: Optional[str] = None
    screenshot_data: Optional[bytes] = None
    file_size: int = 0
    response_time: float = 0.0
    page_title: Optional[str] = None
    page_url: Optional[str] = None  # 最终URL（重定向后）
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    captured_at: datetime = field(default_factory=datetime.utcnow)
    viewport_size: Tuple[int, int] = (1280, 800)
    full_page: bool = False


@dataclass
class BatchScreenshotResult:
    """批量截图结果"""
    total_urls: int
    successful_screenshots: int
    failed_screenshots: int
    total_duration: float
    results: List[ScreenshotResult] = field(default_factory=list)
    average_response_time: float = 0.0
    error_summary: Dict[str, int] = field(default_factory=dict)


class PlaywrightScreenshotEngine:
    """基于Playwright的截图引擎"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.contexts: List[BrowserContext] = []
        
        # 黑名单域名，避免截图
        self.blacklist_domains = {
            'edu.cn', 'gov.cn', 'mil.cn',
            'localhost', '127.0.0.1', '0.0.0.0'
        }
    
    async def initialize(self, config: ScreenshotConfig):
        """初始化Playwright"""
        try:
            self.playwright = await async_playwright().start()
            
            # 启动浏览器
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1280,800',
                    '--disable-web-security',
                    '--allow-running-insecure-content',
                    '--ignore-certificate-errors',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            
            self.logger.info("Playwright截图引擎初始化成功")
            
        except Exception as e:
            self.logger.error(f"Playwright初始化失败: {e}")
            raise e
    
    async def create_context(self, config: ScreenshotConfig) -> BrowserContext:
        """创建浏览器上下文"""
        context = await self.browser.new_context(
            viewport={'width': config.width, 'height': config.height},
            user_agent=config.user_agent,
            java_script_enabled=config.enable_javascript,
            ignore_https_errors=True,
            bypass_csp=True
        )
        
        # 设置额外的反检测措施
        await context.add_init_script("""
            // 移除webdriver标识
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // 修改plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // 修改languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en'],
            });
        """)
        
        self.contexts.append(context)
        return context
    
    async def capture_screenshot(
        self, 
        url: str, 
        config: ScreenshotConfig,
        output_path: Optional[str] = None
    ) -> ScreenshotResult:
        """截取单个网页截图"""
        start_time = time.time()
        
        # 检查黑名单
        if self._is_blacklisted(url):
            return ScreenshotResult(
                url=url,
                success=False,
                error_message="域名在黑名单中",
                response_time=time.time() - start_time
            )
        
        context = await self.create_context(config)
        
        try:
            page = await context.new_page()
            
            # 尝试多次截图
            for attempt in range(config.retry_count):
                try:
                    result = await self._capture_single_screenshot(page, url, config, output_path)
                    result.retry_count = attempt
                    return result
                    
                except Exception as e:
                    if attempt == config.retry_count - 1:
                        # 最后一次尝试失败
                        return ScreenshotResult(
                            url=url,
                            success=False,
                            error_message=str(e),
                            response_time=time.time() - start_time,
                            retry_count=attempt + 1
                        )
                    
                    # 等待后重试
                    await asyncio.sleep(2 ** attempt)
                    self.logger.debug(f"截图重试 {attempt + 1}/{config.retry_count}: {url}")
        
        finally:
            await context.close()
            if context in self.contexts:
                self.contexts.remove(context)
        
        # 如果所有尝试都失败，返回错误结果
        return ScreenshotResult(
            url=url,
            success=False,
            error_message="所有截图尝试都失败",
            response_time=time.time() - start_time
        )
    
    async def _capture_single_screenshot(
        self, 
        page: Page, 
        url: str, 
        config: ScreenshotConfig,
        output_path: Optional[str] = None
    ) -> ScreenshotResult:
        """执行单次截图"""
        start_time = time.time()
        
        try:
            # 导航到页面
            response = await page.goto(
                url, 
                wait_until='domcontentloaded',
                timeout=config.timeout * 1000
            )
            
            # 等待页面加载
            if config.wait_for_load:
                await page.wait_for_load_state('domcontentloaded')
                
            if config.wait_for_network:
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except:
                    pass  # 网络空闲等待可能超时，继续执行
            
            # 额外等待时间
            if config.wait_time > 0:
                await asyncio.sleep(config.wait_time)
            
            # 获取页面信息
            page_title = await page.title()
            page_url = page.url
            
            # 执行截图
            screenshot_options = {
                'type': config.format,
                'quality': config.quality if config.format == 'jpeg' else None,
                'full_page': config.full_page
            }
            
            if output_path:
                screenshot_options['path'] = output_path
                screenshot_data = await page.screenshot(**screenshot_options)
            else:
                screenshot_data = await page.screenshot(**screenshot_options)
            
            # 获取文件大小
            file_size = len(screenshot_data) if screenshot_data else 0
            
            # 获取状态码
            status_code = response.status if response else None
            
            return ScreenshotResult(
                url=url,
                success=True,
                screenshot_path=output_path,
                screenshot_data=screenshot_data,
                file_size=file_size,
                response_time=time.time() - start_time,
                page_title=page_title,
                page_url=page_url,
                status_code=status_code,
                viewport_size=(config.width, config.height),
                full_page=config.full_page
            )
            
        except Exception as e:
            return ScreenshotResult(
                url=url,
                success=False,
                error_message=str(e),
                response_time=time.time() - start_time
            )
    
    def _is_blacklisted(self, url: str) -> bool:
        """检查URL是否在黑名单中"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 移除端口号
            if ':' in domain:
                domain = domain.split(':')[0]
            
            # 检查黑名单
            for blacklisted in self.blacklist_domains:
                if blacklisted in domain:
                    return True
            
            return False
            
        except Exception:
            return True  # 无法解析的URL认为是黑名单
    
    async def batch_screenshot(
        self, 
        urls: List[str], 
        config: ScreenshotConfig,
        output_dir: str,
        max_concurrent: int = 5
    ) -> BatchScreenshotResult:
        """批量截图"""
        start_time = time.time()
        self.logger.info(f"开始批量截图: {len(urls)} 个URL")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def screenshot_with_semaphore(url: str) -> ScreenshotResult:
            async with semaphore:
                # 生成输出文件名
                output_filename = self._generate_filename(url, config.format)
                output_path = os.path.join(output_dir, output_filename)
                
                return await self.capture_screenshot(url, config, output_path)
        
        # 并发执行截图
        tasks = [screenshot_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        valid_results = []
        error_summary = {}
        
        for result in results:
            if isinstance(result, ScreenshotResult):
                valid_results.append(result)
                if not result.success and result.error_message:
                    error_type = type(Exception(result.error_message)).__name__
                    error_summary[error_type] = error_summary.get(error_type, 0) + 1
            elif isinstance(result, Exception):
                error_type = type(result).__name__
                error_summary[error_type] = error_summary.get(error_type, 0) + 1
        
        # 统计结果
        successful_count = len([r for r in valid_results if r.success])
        failed_count = len(valid_results) - successful_count
        total_duration = time.time() - start_time
        avg_response_time = sum(r.response_time for r in valid_results) / max(len(valid_results), 1)
        
        batch_result = BatchScreenshotResult(
            total_urls=len(urls),
            successful_screenshots=successful_count,
            failed_screenshots=failed_count,
            total_duration=total_duration,
            results=valid_results,
            average_response_time=avg_response_time,
            error_summary=error_summary
        )
        
        self.logger.info(f"批量截图完成: {successful_count}/{len(urls)} 成功，耗时 {total_duration:.2f} 秒")
        return batch_result
    
    def _generate_filename(self, url: str, format: str) -> str:
        """生成截图文件名"""
        try:
            parsed = urlparse(url)
            
            # 使用域名和路径生成文件名
            filename_parts = []
            if parsed.netloc:
                filename_parts.append(parsed.netloc)
            if parsed.path and parsed.path != '/':
                path_clean = parsed.path.replace('/', '_').replace('\\', '_')
                filename_parts.append(path_clean)
            
            filename = '_'.join(filename_parts)
            
            # 限制长度并添加时间戳
            if len(filename) > 100:
                filename = filename[:100]
            
            timestamp = int(time.time())
            filename = f"{filename}_{timestamp}.{format}"
            
            # 清理无效字符
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                filename = filename.replace(char, '_')
            
            return filename
            
        except Exception:
            # 如果无法解析，使用哈希值
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            timestamp = int(time.time())
            return f"screenshot_{url_hash}_{timestamp}.{format}"
    
    async def cleanup(self):
        """清理资源"""
        # 关闭所有上下文
        for context in self.contexts:
            try:
                await context.close()
            except Exception as e:
                self.logger.warning(f"关闭浏览器上下文失败: {e}")
        
        # 关闭浏览器
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                self.logger.warning(f"关闭浏览器失败: {e}")
        
        # 停止Playwright
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                self.logger.warning(f"停止Playwright失败: {e}")
        
        self.contexts.clear()
        self.logger.info("Playwright截图引擎资源清理完成")


class SeleniumScreenshotEngine:
    """基于Selenium的备用截图引擎"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        self.drivers: List[Any] = []  # 使用Any类型避免类型错误
    
    def create_driver(self, config: ScreenshotConfig) -> Any:
        """创建Chrome驱动"""
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium不可用")
            
        chrome_options = ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument(f'--window-size={config.width},{config.height}')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument(f'--user-agent={config.user_agent}')
        
        # 反检测设置
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.drivers.append(driver)
        return driver
    
    async def capture_screenshot(
        self, 
        url: str, 
        config: ScreenshotConfig,
        output_path: Optional[str] = None
    ) -> ScreenshotResult:
        """使用Selenium截图"""
        start_time = time.time()
        driver = None
        
        try:
            driver = self.create_driver(config)
            
            # 导航到页面
            driver.get(url)
            
            # 等待页面加载
            if config.wait_for_load:
                WebDriverWait(driver, config.timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            
            # 额外等待
            if config.wait_time > 0:
                time.sleep(config.wait_time)
            
            # 获取页面信息
            page_title = driver.title
            page_url = driver.current_url
            
            # 截图
            if output_path:
                driver.save_screenshot(output_path)
                with open(output_path, 'rb') as f:
                    screenshot_data = f.read()
            else:
                screenshot_data = driver.get_screenshot_as_png()
            
            file_size = len(screenshot_data) if screenshot_data else 0
            
            return ScreenshotResult(
                url=url,
                success=True,
                screenshot_path=output_path,
                screenshot_data=screenshot_data,
                file_size=file_size,
                response_time=time.time() - start_time,
                page_title=page_title,
                page_url=page_url,
                viewport_size=(config.width, config.height),
                full_page=config.full_page
            )
            
        except Exception as e:
            return ScreenshotResult(
                url=url,
                success=False,
                error_message=str(e),
                response_time=time.time() - start_time
            )
        
        finally:
            if driver:
                try:
                    driver.quit()
                    if driver in self.drivers:
                        self.drivers.remove(driver)
                except Exception as e:
                    self.logger.warning(f"关闭Selenium驱动失败: {e}")
    
    def cleanup(self):
        """清理Selenium资源"""
        for driver in self.drivers:
            try:
                driver.quit()
            except Exception as e:
                self.logger.warning(f"清理Selenium驱动失败: {e}")
        
        self.drivers.clear()
        self.logger.info("Selenium截图引擎资源清理完成")


class UniversalScreenshotEngine:
    """通用截图引擎，自动选择最佳实现"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 选择最佳引擎
        if PLAYWRIGHT_AVAILABLE:
            self.engine = PlaywrightScreenshotEngine(task_id, user_id)
            self.engine_type = 'playwright'
            self.logger.info("使用Playwright截图引擎")
        elif SELENIUM_AVAILABLE:
            self.engine = SeleniumScreenshotEngine(task_id, user_id)
            self.engine_type = 'selenium'
            self.logger.info("使用Selenium截图引擎")
        else:
            self.engine = None
            self.engine_type = 'none'
            self.logger.error("没有可用的截图引擎")
    
    async def initialize(self, config: ScreenshotConfig):
        """初始化引擎"""
        if self.engine and hasattr(self.engine, 'initialize'):
            await self.engine.initialize(config)
    
    async def capture_screenshot(
        self, 
        url: str, 
        config: ScreenshotConfig,
        output_path: Optional[str] = None
    ) -> ScreenshotResult:
        """截图"""
        if not self.engine:
            return ScreenshotResult(
                url=url,
                success=False,
                error_message="没有可用的截图引擎"
            )
        
        return await self.engine.capture_screenshot(url, config, output_path)
    
    async def batch_screenshot(
        self, 
        urls: List[str], 
        config: ScreenshotConfig,
        output_dir: str,
        max_concurrent: int = 5
    ) -> BatchScreenshotResult:
        """批量截图"""
        if not self.engine:
            return BatchScreenshotResult(
                total_urls=len(urls),
                successful_screenshots=0,
                failed_screenshots=len(urls),
                total_duration=0.0,
                error_summary={"NoEngineAvailable": len(urls)}
            )
        
        if hasattr(self.engine, 'batch_screenshot'):
            return await self.engine.batch_screenshot(urls, config, output_dir, max_concurrent)
        else:
            # 为Selenium引擎实现批量截图
            return await self._fallback_batch_screenshot(urls, config, output_dir, max_concurrent)
    
    async def _fallback_batch_screenshot(
        self, 
        urls: List[str], 
        config: ScreenshotConfig,
        output_dir: str,
        max_concurrent: int
    ) -> BatchScreenshotResult:
        """备用批量截图实现"""
        start_time = time.time()
        os.makedirs(output_dir, exist_ok=True)
        
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def screenshot_with_semaphore(url: str) -> ScreenshotResult:
            async with semaphore:
                output_filename = f"screenshot_{int(time.time())}_{len(results)}.png"
                output_path = os.path.join(output_dir, output_filename)
                return await self.engine.capture_screenshot(url, config, output_path)
        
        tasks = [screenshot_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = [r for r in results if isinstance(r, ScreenshotResult)]
        successful_count = len([r for r in valid_results if r.success])
        
        return BatchScreenshotResult(
            total_urls=len(urls),
            successful_screenshots=successful_count,
            failed_screenshots=len(valid_results) - successful_count,
            total_duration=time.time() - start_time,
            results=valid_results
        )
    
    async def cleanup(self):
        """清理资源"""
        if self.engine:
            if hasattr(self.engine, 'cleanup'):
                if asyncio.iscoroutinefunction(self.engine.cleanup):
                    await self.engine.cleanup()
                else:
                    self.engine.cleanup()
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取引擎信息"""
        return {
            'engine_type': self.engine_type,
            'playwright_available': PLAYWRIGHT_AVAILABLE,
            'selenium_available': SELENIUM_AVAILABLE,
            'engine_ready': self.engine is not None
        }
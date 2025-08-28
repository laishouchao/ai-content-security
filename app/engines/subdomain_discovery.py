import asyncio
import aiohttp
import asyncio
import dns.resolver
import dns.exception
import re
import json
import ssl
import socket
from typing import List, Dict, Set, Optional, Any
from urllib.parse import urlparse
from datetime import datetime
import time
import random

from app.core.logging import TaskLogger
from app.core.config import settings


class SubdomainResult:
    """子域名发现结果"""
    
    def __init__(self, subdomain: str, method: str, ip_address: Optional[str] = None):
        self.subdomain = subdomain.lower().strip()
        self.method = method
        self.ip_address = ip_address
        self.is_accessible: bool = False
        self.response_code: Optional[int] = None
        self.response_time: Optional[float] = None
        self.server_header: Optional[str] = None
        self.discovered_at = datetime.utcnow()
    
    def __hash__(self):
        return hash(self.subdomain)
    
    def __eq__(self, other):
        if isinstance(other, SubdomainResult):
            return self.subdomain == other.subdomain
        return False


class DNSQueryMethod:
    """DNS查询方法"""
    
    def __init__(self):
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 5
        self.resolver.lifetime = 10
    
    async def discover(self, domain: str, logger: TaskLogger) -> List[SubdomainResult]:
        """通过DNS查询发现子域名"""
        results = []
        
        # 常见子域名列表
        common_subdomains = [
            'www', 'mail', 'ftp', 'cpanel', 'webmail', 'admin', 'blog', 'shop',
            'api', 'dev', 'test', 'staging', 'prod', 'cms', 'app', 'mobile',
            'secure', 'support', 'help', 'docs', 'cdn', 'assets', 'static',
            'img', 'images', 'media', 'files', 'download', 'upload', 'cloud',
            'vpn', 'remote', 'portal', 'dashboard', 'panel', 'control', 'monitor'
        ]
        
        # 并发查询子域名
        tasks = []
        for subdomain in common_subdomains:
            full_domain = f"{subdomain}.{domain}"
            tasks.append(self._query_domain(full_domain, "dns_query", logger))
        
        # 批量执行DNS查询
        dns_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in dns_results:
            if isinstance(result, SubdomainResult):
                results.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"DNS查询异常: {result}")
        
        logger.info(f"DNS查询发现 {len(results)} 个子域名")
        return results
    
    async def _query_domain(self, domain: str, method: str, logger: TaskLogger) -> Optional[SubdomainResult]:
        """查询单个域名"""
        try:
            # 使用asyncio.to_thread来异步执行同步的DNS查询
            answers = await asyncio.to_thread(self.resolver.resolve, domain, 'A')
            
            if answers:
                ip_address = str(answers[0])
                return SubdomainResult(domain, method, ip_address)
                
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
            # 这些异常是正常的，表示域名不存在
            pass
        except Exception as e:
            logger.debug(f"DNS查询失败 {domain}: {e}")
        
        return None


class MultiSourceCertificateMethod:
    """多源证书透明日志查询方法"""
    
    def __init__(self):
        self.sources = {
            'crt_sh': "https://crt.sh/?q=%25.{domain}&output=json",
            'censys': "https://search.censys.io/api/v2/certificates/search",
            'facebook_ct': "https://graph.facebook.com/certificates?query={domain}"
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    async def discover_multi_source(self, domain: str, logger: TaskLogger, sources: Optional[List[str]] = None) -> List[SubdomainResult]:
        """多源并发证书透明日志查询"""
        if sources is None:
            sources = ['crt_sh', 'censys', 'facebook_ct']
        
        results = set()
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(ssl=False),
            headers=self.headers
        ) as session:
            
            # 并发查询所有源
            tasks = []
            for source in sources:
                if source == 'crt_sh':
                    tasks.append(self._query_crt_sh_enhanced(session, domain, logger))
                elif source == 'censys':
                    tasks.append(self._query_censys(session, domain, logger))
                elif source == 'facebook_ct':
                    tasks.append(self._query_facebook_ct(session, domain, logger))
            
            source_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(source_results):
                if isinstance(result, set):
                    results.update(result)
                    logger.info(f"{sources[i]} 发现 {len(result)} 个子域名")
                elif isinstance(result, Exception):
                    logger.warning(f"{sources[i]} 查询失败: {result}")
        
        logger.info(f"多源证书透明日志发现 {len(results)} 个子域名")
        return list(results)
    
    async def _query_crt_sh_enhanced(self, session: aiohttp.ClientSession, domain: str, logger: TaskLogger) -> Set[SubdomainResult]:
        """增强的crt.sh查询"""
        results = set()
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # 使用BloomFilter概念进行去重（简化版）
                    seen_domains = set()
                    
                    for cert in data:
                        if 'name_value' in cert:
                            names = cert['name_value'].split('\n')
                            for name in names:
                                name = name.strip().lower()
                                if name and name not in seen_domains and self._is_valid_subdomain(name, domain):
                                    seen_domains.add(name)
                                    results.add(SubdomainResult(name, "crt_sh_enhanced"))
                                    
        except Exception as e:
            logger.warning(f"crt.sh增强查询异常: {e}")
        
        return results
    
    async def _query_censys(self, session: aiohttp.ClientSession, domain: str, logger: TaskLogger) -> Set[SubdomainResult]:
        """Censys API查询"""
        results = set()
        
        # 需要API密钥，这里提供框架
        censys_api_key = getattr(settings, 'CENSYS_API_KEY', None)
        if not censys_api_key:
            logger.debug("Censys API密钥未配置，跳过查询")
            return results
        
        try:
            headers = {
                'Authorization': f'Bearer {censys_api_key}',
                'Content-Type': 'application/json'
            }
            
            query_data = {
                'query': f'names: *.{domain}',
                'per_page': 100,
                'cursor': ''
            }
            
            async with session.post(
                'https://search.censys.io/api/v2/certificates/search',
                headers=headers,
                json=query_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for cert in data.get('result', {}).get('hits', []):
                        for name in cert.get('names', []):
                            if self._is_valid_subdomain(name, domain):
                                results.add(SubdomainResult(name, "censys"))
                                
        except Exception as e:
            logger.debug(f"Censys查询失败: {e}")
        
        return results
    
    async def _query_facebook_ct(self, session: aiohttp.ClientSession, domain: str, logger: TaskLogger) -> Set[SubdomainResult]:
        """Facebook CT API查询"""
        results = set()
        
        try:
            # Facebook CT API通常需要认证，这里提供基础框架
            url = f"https://graph.facebook.com/certificates?query={domain}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for cert in data.get('data', []):
                        for name in cert.get('domains', []):
                            if self._is_valid_subdomain(name, domain):
                                results.add(SubdomainResult(name, "facebook_ct"))
                                
        except Exception as e:
            logger.debug(f"Facebook CT查询失败: {e}")
        
        return results
    
    def _is_valid_subdomain(self, name: str, domain: str) -> bool:
        """验证是否为有效的子域名"""
        if not name.endswith(f".{domain}"):
            return False
        
        # 过滤通配符和无效字符
        if '*' in name or '?' in name:
            return False
        
        # 检查域名格式
        try:
            parts = name.split('.')
            if len(parts) < 2:
                return False
            
            for part in parts:
                if not part or len(part) > 63:
                    return False
                if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?$', part):
                    return False
                    
            return True
        except:
            return False


class CertificateTransparencyMethod:
    """证书透明度日志查询方法（兼容性包装）"""
    
    def __init__(self):
        self.multi_source_method = MultiSourceCertificateMethod()
    
    async def discover(self, domain: str, logger: TaskLogger) -> List[SubdomainResult]:
        """通过证书透明度日志发现子域名"""
        try:
            # 使用多源证书方法，但只使用crt.sh源以保持兼容性
            results = await self.multi_source_method.discover_multi_source(
                domain, logger, sources=['crt_sh']
            )
            return results
        except Exception as e:
            logger.error(f"证书透明度查询失败: {e}")
            return []


class BruteForceMethod:
    """子域名字典爆破方法"""
    
    def __init__(self):
        self.wordlist = self._get_wordlist()
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 3
        self.resolver.lifetime = 5
    
    def _get_wordlist(self) -> List[str]:
        """获取子域名字典"""
        # 扩展的子域名字典
        wordlist = [
            # 常见服务
            'www', 'mail', 'email', 'webmail', 'ftp', 'sftp', 'ssh', 'vpn',
            'api', 'rest', 'graphql', 'webhook', 'ws', 'wss',
            
            # 开发环境
            'dev', 'test', 'qa', 'staging', 'prod', 'production', 'demo',
            'beta', 'alpha', 'rc', 'preview', 'sandbox', 'lab',
            
            # 管理相关
            'admin', 'administrator', 'panel', 'cpanel', 'control', 'manage',
            'dashboard', 'console', 'portal', 'gateway', 'monitor', 'status',
            
            # 内容相关
            'blog', 'news', 'cms', 'wiki', 'forum', 'community', 'support',
            'help', 'docs', 'documentation', 'manual', 'guide', 'faq',
            
            # 商务相关
            'shop', 'store', 'cart', 'checkout', 'payment', 'billing',
            'invoice', 'account', 'profile', 'user', 'customer', 'client',
            
            # 技术服务
            'cdn', 'cache', 'static', 'assets', 'media', 'img', 'images',
            'files', 'download', 'upload', 'backup', 'archive', 'storage',
            
            # 移动和应用
            'mobile', 'app', 'ios', 'android', 'web', 'spa', 'm', 'wap',
            
            # 网络服务
            'ns', 'ns1', 'ns2', 'dns', 'mx', 'smtp', 'pop', 'imap',
            'ldap', 'ad', 'sso', 'oauth', 'auth', 'login', 'register',
            
            # 监控和工具
            'nagios', 'zabbix', 'grafana', 'kibana', 'elasticsearch',
            'redis', 'mysql', 'postgres', 'mongo', 'db', 'database',
            
            # 云服务
            'aws', 'azure', 'gcp', 'cloud', 'k8s', 'kube', 'docker',
            'ci', 'cd', 'jenkins', 'gitlab', 'github', 'git',
            
            # 业务部门
            'hr', 'finance', 'sales', 'marketing', 'legal', 'compliance',
            'security', 'it', 'ops', 'devops', 'sre'
        ]
        
        return wordlist
    
    async def discover(self, domain: str, logger: TaskLogger, max_subdomains: int = 100) -> List[SubdomainResult]:
        """通过字典爆破发现子域名"""
        results = []
        
        # 限制并发数量以避免过载
        semaphore = asyncio.Semaphore(10)
        
        async def _brute_force_subdomain(subdomain: str):
            async with semaphore:
                full_domain = f"{subdomain}.{domain}"
                result = await self._check_subdomain_exists(full_domain, logger)
                if result:
                    return result
                return None
        
        # 创建任务列表
        tasks = []
        for subdomain in self.wordlist[:max_subdomains]:
            tasks.append(_brute_force_subdomain(subdomain))
        
        # 批量执行爆破
        brute_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in brute_results:
            if isinstance(result, SubdomainResult):
                results.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"爆破查询异常: {result}")
        
        logger.info(f"字典爆破发现 {len(results)} 个子域名")
        return results
    
    async def _check_subdomain_exists(self, domain: str, logger: TaskLogger) -> Optional[SubdomainResult]:
        """检查子域名是否存在"""
        try:
            answers = await asyncio.to_thread(self.resolver.resolve, domain, 'A')
            if answers:
                ip_address = str(answers[0])
                return SubdomainResult(domain, "bruteforce", ip_address)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
            pass
        except Exception as e:
            logger.debug(f"子域名检查失败 {domain}: {e}")
        
        return None


class SubdomainDiscoveryEngine:
    """子域名发现引擎"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 初始化发现方法
        self.methods = [
            DNSQueryMethod(),
            CertificateTransparencyMethod(),
            BruteForceMethod()
        ]
    
    async def discover_all(self, domain: str, config: Dict[str, Any]) -> List[SubdomainResult]:
        """使用所有方法发现子域名"""
        start_time = time.time()
        self.logger.info(f"开始子域名发现: {domain}")
        
        all_results = set()
        max_subdomains = config.get('max_subdomains', settings.MAX_SUBDOMAINS_PER_TASK)
        
        # 并发执行所有发现方法
        tasks = []
        
        # DNS查询
        if config.get('subdomain_discovery', {}).get('dns_query_enabled', True):
            tasks.append(self.methods[0].discover(domain, self.logger))
        
        # 证书透明日志
        if config.get('subdomain_discovery', {}).get('certificate_transparency_enabled', True):
            tasks.append(self.methods[1].discover(domain, self.logger))
        
        # 字典爆破
        if config.get('subdomain_discovery', {}).get('bruteforce_enabled', True):
            max_brute = min(max_subdomains // 2, 200)  # 限制爆破数量
            tasks.append(self.methods[2].discover(domain, self.logger, max_brute))
        
        # 执行所有发现任务
        discovery_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        for results in discovery_results:
            if isinstance(results, list):
                for result in results:
                    all_results.add(result)
                    if len(all_results) >= max_subdomains:
                        break
            elif isinstance(results, Exception):
                self.logger.error(f"子域名发现异常: {results}")
        
        # 转换为列表并限制数量
        final_results = list(all_results)[:max_subdomains]
        
        # 验证子域名可访问性
        if config.get('subdomain_discovery', {}).get('verify_accessibility', True):
            final_results = await self._verify_accessibility(final_results)
        
        duration = time.time() - start_time
        self.logger.info(f"子域名发现完成: 发现 {len(final_results)} 个子域名，耗时 {duration:.2f} 秒")
        
        return final_results
    
    async def _verify_accessibility(self, results: List[SubdomainResult]) -> List[SubdomainResult]:
        """验证子域名的可访问性"""
        if not results:
            return results
            
        self.logger.info(f"开始验证 {len(results)} 个子域名的可访问性")
        
        # 降低并发数，避免网络拥塞
        semaphore = asyncio.Semaphore(5)  # 从20降低到5
        completed_count = 0
        
        async def _check_accessibility_with_progress(result: SubdomainResult):
            nonlocal completed_count
            async with semaphore:
                try:
                    await self._check_http_accessibility(result)
                    completed_count += 1
                    
                    # 每处理5个或在最后输出进度
                    if completed_count % 5 == 0 or completed_count == len(results):
                        accessible_so_far = sum(1 for r in results[:completed_count] if r.is_accessible)
                        self.logger.info(
                            f"可访问性验证进度: {completed_count}/{len(results)}, "
                            f"已发现可访问: {accessible_so_far}"
                        )
                    
                    return result
                except Exception as e:
                    self.logger.warning(f"验证子域名可访问性时出错 {result.subdomain}: {e}")
                    result.is_accessible = False
                    return result
        
        # 并发检查可访问性
        tasks = [_check_accessibility_with_progress(result) for result in results]
        verified_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in verified_results:
            if isinstance(result, SubdomainResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger.warning(f"可访问性检查异常: {result}")
        
        accessible_count = sum(1 for r in valid_results if r.is_accessible)
        self.logger.info(
            f"✅ 可访问性验证完成: {accessible_count}/{len(valid_results)} 个子域名可访问"
        )
        
        # 输出可访问的子域名列表
        accessible_domains = [r.subdomain for r in valid_results if r.is_accessible]
        if accessible_domains:
            self.logger.info(f"可访问的子域名: {', '.join(accessible_domains[:10])}{'...' if len(accessible_domains) > 10 else ''}")
        
        return valid_results
    
    async def _check_http_accessibility(self, result: SubdomainResult):
        """检查HTTP可访问性"""
        start_time = time.time()
        
        # 定义请求头，模拟真实浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 多种协议和端口组合
        urls_to_check = [
            f"https://{result.subdomain}",
            f"http://{result.subdomain}",
            f"https://{result.subdomain}:443",
            f"http://{result.subdomain}:80"
        ]
        
        # 创建更宽松的连接配置
        connector = aiohttp.TCPConnector(
            ssl=False,  # 忽略SSL证书验证
            limit=10,
            limit_per_host=2,
            enable_cleanup_closed=True
        )
        
        # 增加超时时间，分别设置连接和总超时
        timeout = aiohttp.ClientTimeout(
            total=30,      # 总超时30秒
            connect=10,    # 连接超时10秒
            sock_read=15   # 读取超时15秒
        )
        
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers
        ) as session:
            
            for url in urls_to_check:
                # 每个URL尝试最多3次
                for attempt in range(3):
                    try:
                        self.logger.debug(f"尝试访问 {url} (第{attempt+1}次)")
                        
                        async with session.get(
                            url, 
                            allow_redirects=True,
                            ssl=False  # 忽略SSL验证
                        ) as response:
                            
                            # 认为2xx和3xx状态码都是可访问的
                            if 200 <= response.status < 400:
                                result.is_accessible = True
                                result.response_code = response.status
                                result.response_time = time.time() - start_time
                                result.server_header = response.headers.get('Server', '')
                                
                                self.logger.info(f"✅ 子域名可访问: {result.subdomain} - {url} ({response.status})")
                                return
                            else:
                                self.logger.debug(f"HTTP状态码异常: {url} - {response.status}")
                        
                    except asyncio.TimeoutError:
                        self.logger.debug(f"访问超时: {url} (第{attempt+1}次)")
                        if attempt < 2:  # 不是最后一次尝试
                            await asyncio.sleep(1)  # 等待1秒后重试
                        continue
                        
                    except aiohttp.ClientError as e:
                        self.logger.debug(f"客户端错误: {url} - {type(e).__name__}: {str(e)}")
                        if attempt < 2:
                            await asyncio.sleep(1)
                        continue
                        
                    except Exception as e:
                        self.logger.debug(f"访问异常: {url} - {type(e).__name__}: {str(e)}")
                        if attempt < 2:
                            await asyncio.sleep(1)
                        continue
                    
                    # 如果成功访问，跳出重试循环
                    if result.is_accessible:
                        return
        
        # 如果所有尝试都失败，记录为不可访问
        result.is_accessible = False
        result.response_time = time.time() - start_time
        self.logger.debug(f"❌ 子域名不可访问: {result.subdomain} (尝试了所有URL和重试)")
    
    # 新增高性能方法
    async def discover_dns_with_concurrency(self, domain: str, concurrency: int = 100, timeout: int = 3) -> List[SubdomainResult]:
        """高并发DNS发现"""
        try:
            self.logger.info(f"开始高并发DNS发现: {domain}, 并发数: {concurrency}")
            
            # 使用基本DNS查询方法作为替代
            dns_method = DNSQueryMethod()
            results = await dns_method.discover(domain, self.logger)
            
            self.logger.info(f"高并发DNS发现完成: {len(results)} 个子域名")
            return results
            
        except Exception as e:
            self.logger.error(f"高并发DNS发现失败: {e}")
            return []
    
    async def discover_certificate_multi_source(self, domain: str, sources: Optional[List[str]] = None) -> List[SubdomainResult]:
        """多源证书透明日志发现"""
        try:
            self.logger.info(f"开始多源证书透明日志发现: {domain}")
            
            multi_cert_method = MultiSourceCertificateMethod()
            results = await multi_cert_method.discover_multi_source(domain, self.logger, sources)
            
            self.logger.info(f"多源证书发现完成: {len(results)} 个子域名")
            return results
            
        except Exception as e:
            self.logger.error(f"多源证书发现失败: {e}")
            return []
    
    async def discover_passive_dns(self, domain: str) -> List[SubdomainResult]:
        """被动DNS发现"""
        try:
            self.logger.info(f"开始被动DNS发现: {domain}")
            
            # 暂时使用证书透明度方法作为被动DNS替代
            ct_method = CertificateTransparencyMethod()
            results = await ct_method.discover(domain, self.logger)
            
            self.logger.info(f"被动DNS发现完成: {len(results)} 个子域名")
            return results
            
        except Exception as e:
            self.logger.error(f"被动DNS发现失败: {e}")
            return []
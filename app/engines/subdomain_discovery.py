import asyncio
import aiohttp
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


class CertificateTransparencyMethod:
    """证书透明日志查询方法"""
    
    def __init__(self):
        self.ct_logs = [
            "https://crt.sh/?q=%25.{domain}&output=json",
            "https://api.certspotter.com/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names"
        ]
    
    async def discover(self, domain: str, logger: TaskLogger) -> List[SubdomainResult]:
        """通过证书透明日志发现子域名"""
        results = set()
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(ssl=False)
        ) as session:
            
            # 查询crt.sh
            try:
                crt_results = await self._query_crt_sh(session, domain, logger)
                results.update(crt_results)
            except Exception as e:
                logger.warning(f"crt.sh查询失败: {e}")
            
            # 查询certspotter（如果有API密钥）
            try:
                certspotter_results = await self._query_certspotter(session, domain, logger)
                results.update(certspotter_results)
            except Exception as e:
                logger.debug(f"certspotter查询失败: {e}")
        
        logger.info(f"证书透明日志发现 {len(results)} 个子域名")
        return list(results)
    
    async def _query_crt_sh(self, session: aiohttp.ClientSession, domain: str, logger: TaskLogger) -> Set[SubdomainResult]:
        """查询crt.sh证书透明日志"""
        results = set()
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for cert in data:
                        if 'name_value' in cert:
                            names = cert['name_value'].split('\n')
                            for name in names:
                                name = name.strip().lower()
                                if name and self._is_valid_subdomain(name, domain):
                                    results.add(SubdomainResult(name, "certificate_transparency"))
                                    
        except Exception as e:
            logger.warning(f"crt.sh查询异常: {e}")
        
        return results
    
    async def _query_certspotter(self, session: aiohttp.ClientSession, domain: str, logger: TaskLogger) -> Set[SubdomainResult]:
        """查询certspotter API"""
        results = set()
        # 这里需要API密钥，暂时跳过
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
        self.logger.info(f"开始验证 {len(results)} 个子域名的可访问性")
        
        # 限制并发数
        semaphore = asyncio.Semaphore(20)
        
        async def _check_accessibility(result: SubdomainResult):
            async with semaphore:
                await self._check_http_accessibility(result)
                return result
        
        # 并发检查可访问性
        tasks = [_check_accessibility(result) for result in results]
        verified_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in verified_results:
            if isinstance(result, SubdomainResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger.debug(f"可访问性检查异常: {result}")
        
        accessible_count = sum(1 for r in valid_results if r.is_accessible)
        self.logger.info(f"可访问性验证完成: {accessible_count}/{len(valid_results)} 个子域名可访问")
        
        return valid_results
    
    async def _check_http_accessibility(self, result: SubdomainResult):
        """检查HTTP可访问性"""
        start_time = time.time()
        
        urls_to_check = [
            f"https://{result.subdomain}",
            f"http://{result.subdomain}"
        ]
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            connector=aiohttp.TCPConnector(ssl=False)
        ) as session:
            
            for url in urls_to_check:
                try:
                    async with session.get(url, allow_redirects=True) as response:
                        result.is_accessible = True
                        result.response_code = response.status
                        result.response_time = time.time() - start_time
                        result.server_header = response.headers.get('Server', '')
                        
                        self.logger.debug(f"子域名可访问: {result.subdomain} ({response.status})")
                        return
                        
                except Exception:
                    continue
        
        # 如果都无法访问，记录为不可访问
        result.is_accessible = False
        result.response_time = time.time() - start_time
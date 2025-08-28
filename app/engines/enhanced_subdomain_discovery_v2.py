"""
增强的子域名发现引擎
整合多种子域名发现方法，支持高并发和智能去重

参考CSDN文章的思路：
1. 保留传统DNS、证书透明度等方法
2. 新增基于搜索引擎、API等方法
3. 实现智能域名验证和过滤
4. 支持多源并发查询
"""

import asyncio
import aiohttp
import dns.resolver
import dns.exception
import re
import json
import ssl
import socket
import hashlib
import time
import random
from typing import List, Dict, Set, Optional, Any, Tuple
from urllib.parse import urlparse, quote
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
import base64

from app.core.logging import TaskLogger
from app.core.config import settings
from app.engines.subdomain_discovery import SubdomainResult


@dataclass
class EnhancedSubdomainResult:
    """增强的子域名发现结果"""
    subdomain: str
    discovery_method: str
    ip_addresses: List[str] = field(default_factory=list)
    is_accessible: bool = False
    response_code: Optional[int] = None
    response_time: Optional[float] = None
    server_header: Optional[str] = None
    ssl_info: Optional[Dict[str, Any]] = None
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    confidence_score: float = 1.0  # 发现可信度评分
    source_details: Dict[str, Any] = field(default_factory=dict)
    

class EnhancedDNSQueryMethod:
    """增强的DNS查询方法"""
    
    def __init__(self):
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 3
        self.resolver.lifetime = 10
        
        # 扩展的子域名字典，基于常见命名模式
        self.common_subdomains = [
            # 基础服务
            'www', 'mail', 'ftp', 'webmail', 'admin', 'root', 'test', 'demo',
            
            # 开发环境
            'dev', 'development', 'staging', 'stage', 'prod', 'production',
            'test', 'testing', 'qa', 'preprod', 'preview', 'beta', 'alpha',
            
            # API和服务
            'api', 'apis', 'rest', 'graphql', 'service', 'services', 'micro',
            'gateway', 'proxy', 'load', 'balancer', 'lb',
            
            # 内容和媒体
            'cdn', 'static', 'assets', 'media', 'img', 'images', 'pics',
            'files', 'uploads', 'downloads', 'resources', 'content',
            
            # 数据库和存储
            'db', 'database', 'mysql', 'postgres', 'redis', 'mongo', 'elastic',
            'search', 'solr', 'cache', 'storage', 'backup',
            
            # 监控和管理
            'monitor', 'monitoring', 'metrics', 'logs', 'grafana', 'kibana',
            'prometheus', 'alerts', 'status', 'health', 'ping',
            
            # 安全和认证
            'auth', 'sso', 'oauth', 'login', 'secure', 'ssl', 'vpn',
            'firewall', 'waf', 'security', 'cert', 'certs',
            
            # 移动和应用
            'mobile', 'app', 'apps', 'android', 'ios', 'wap', 'm',
            'touch', 'responsive',
            
            # 邮件和通信
            'smtp', 'pop', 'imap', 'exchange', 'webmail', 'mx',
            'newsletter', 'support', 'help', 'chat',
            
            # 地域和语言
            'us', 'eu', 'asia', 'china', 'jp', 'uk', 'de', 'fr',
            'en', 'zh', 'cn', 'global', 'local', 'regional',
            
            # 业务功能
            'shop', 'store', 'ecommerce', 'cart', 'checkout', 'payment',
            'blog', 'news', 'forum', 'wiki', 'docs', 'documentation',
            'crm', 'erp', 'hr', 'finance', 'accounting', 'sales',
            
            # 数字和编号
            'v1', 'v2', 'v3', 'v4', 'version1', 'version2',
            'node1', 'node2', 'server1', 'server2', 'web1', 'web2',
            '1', '2', '3', '4', '5', '01', '02', '03',
            
            # 其他常见
            'old', 'new', 'legacy', 'next', 'future', 'temp', 'tmp',
            'backup', 'mirror', 'cdn', 'edge', 'origin', 'main'
        ]
    
    async def discover(self, domain: str, logger: TaskLogger, max_concurrent: int = 100) -> List[EnhancedSubdomainResult]:
        """通过DNS查询发现子域名"""
        start_time = time.time()
        logger.info(f"开始增强DNS查询: {domain}")
        
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # 并发查询子域名
        tasks = []
        for subdomain in self.common_subdomains:
            full_domain = f"{subdomain}.{domain}"
            tasks.append(self._query_domain_enhanced(full_domain, "enhanced_dns", logger, semaphore))
        
        # 批量执行DNS查询
        dns_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in dns_results:
            if isinstance(result, EnhancedSubdomainResult):
                results.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"DNS查询异常: {result}")
        
        duration = time.time() - start_time
        logger.info(f"增强DNS查询完成: 发现 {len(results)} 个子域名，耗时 {duration:.2f} 秒")
        return results
    
    async def _query_domain_enhanced(
        self, 
        domain: str, 
        method: str, 
        logger: TaskLogger, 
        semaphore: asyncio.Semaphore
    ) -> Optional[EnhancedSubdomainResult]:
        """增强的域名查询"""
        async with semaphore:
            try:
                start_time = time.time()
                
                # 使用asyncio.to_thread来异步执行同步的DNS查询
                answers = await asyncio.to_thread(self.resolver.resolve, domain, 'A')
                
                if answers:
                    ip_addresses = [str(answer) for answer in answers]
                    response_time = time.time() - start_time
                    
                    result = EnhancedSubdomainResult(
                        subdomain=domain,
                        discovery_method=method,
                        ip_addresses=ip_addresses,
                        response_time=response_time,
                        confidence_score=0.9,  # DNS查询可信度较高
                        source_details={
                            'resolver_used': str(self.resolver.nameservers),
                            'query_type': 'A'
                        }
                    )
                    
                    return result
                    
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
                # 这些异常是正常的，表示域名不存在
                pass
            except Exception as e:
                logger.debug(f"DNS查询失败 {domain}: {e}")
            
            return None


class SearchEngineSubdomainMethod:
    """搜索引擎子域名发现方法"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 搜索引擎查询模板
        self.search_engines = {
            'google': {
                'url': 'https://www.google.com/search?q=site:{domain}&num=100&start={start}',
                'pattern': r'https?://([^/\s<>"\']+\.{domain})',
                'delay': 2
            },
            'bing': {
                'url': 'https://www.bing.com/search?q=site:{domain}&count=50&first={start}',
                'pattern': r'https?://([^/\s<>"\']+\.{domain})',
                'delay': 1
            },
            'baidu': {
                'url': 'https://www.baidu.com/s?wd=site:{domain}&pn={start}',
                'pattern': r'https?://([^/\s<>"\']+\.{domain})',
                'delay': 1
            }
        }
    
    async def discover(self, domain: str, logger: TaskLogger) -> List[EnhancedSubdomainResult]:
        """通过搜索引擎发现子域名"""
        logger.info(f"开始搜索引擎查询: {domain}")
        
        results = []
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=self.headers
        ) as session:
            
            # 并发查询多个搜索引擎
            tasks = []
            for engine_name, engine_config in self.search_engines.items():
                tasks.append(self._search_engine_query(session, domain, engine_name, engine_config, logger))
            
            search_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 合并结果
            all_subdomains = set()
            for result in search_results:
                if isinstance(result, set):
                    all_subdomains.update(result)
                elif isinstance(result, Exception):
                    logger.warning(f"搜索引擎查询失败: {result}")
            
            # 转换为结果对象
            for subdomain in all_subdomains:
                results.append(EnhancedSubdomainResult(
                    subdomain=subdomain,
                    discovery_method="search_engine",
                    confidence_score=0.7,  # 搜索引擎结果可信度中等
                    source_details={'engines_used': list(self.search_engines.keys())}
                ))
        
        logger.info(f"搜索引擎查询完成: 发现 {len(results)} 个子域名")
        return results
    
    async def _search_engine_query(
        self, 
        session: aiohttp.ClientSession, 
        domain: str, 
        engine_name: str, 
        engine_config: Dict[str, Any], 
        logger: TaskLogger
    ) -> Set[str]:
        """单个搜索引擎查询"""
        subdomains = set()
        
        try:
            # 查询多页结果
            for page in range(3):  # 查询前3页
                start = page * 10 if engine_name == 'google' else page * 50
                url = engine_config['url'].format(domain=domain, start=start)
                
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        # 提取子域名
                        pattern = engine_config['pattern'].format(domain=re.escape(domain))
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        
                        for match in matches:
                            subdomain = match.lower().strip()
                            if self._is_valid_subdomain(subdomain, domain):
                                subdomains.add(subdomain)
                
                # 延迟避免被封
                await asyncio.sleep(engine_config['delay'])
                
        except Exception as e:
            logger.warning(f"{engine_name} 搜索引擎查询失败: {e}")
        
        return subdomains
    
    def _is_valid_subdomain(self, subdomain: str, target_domain: str) -> bool:
        """验证子域名是否有效"""
        if not subdomain or subdomain == target_domain:
            return False
        
        # 检查是否是目标域名的子域名
        if not subdomain.endswith(f'.{target_domain}'):
            return False
        
        # 检查域名格式
        domain_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$')
        return bool(domain_pattern.match(subdomain))


class APIBasedSubdomainMethod:
    """基于API的子域名发现方法"""
    
    def __init__(self):
        self.api_sources = {
            'virustotal': {
                'url': 'https://www.virustotal.com/vtapi/v2/domain/report',
                'params': {'apikey': 'your_api_key', 'domain': '{domain}'},
                'requires_key': True
            },
            'securitytrails': {
                'url': 'https://api.securitytrails.com/v1/domain/{domain}/subdomains',
                'headers': {'APIKEY': 'your_api_key'},
                'requires_key': True
            },
            'crtsh': {
                'url': 'https://crt.sh/?q=%.{domain}&output=json',
                'requires_key': False
            },
            'hackertarget': {
                'url': 'https://api.hackertarget.com/hostsearch/?q={domain}',
                'requires_key': False
            }
        }
        
        # 从设置中获取API密钥
        self.api_keys = {
            'virustotal': getattr(settings, 'VIRUSTOTAL_API_KEY', None),
            'securitytrails': getattr(settings, 'SECURITYTRAILS_API_KEY', None)
        }
    
    async def discover(self, domain: str, logger: TaskLogger) -> List[EnhancedSubdomainResult]:
        """通过API发现子域名"""
        logger.info(f"开始API查询: {domain}")
        
        results = []
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            
            # 并发查询所有可用的API
            tasks = []
            for source_name, source_config in self.api_sources.items():
                if source_config.get('requires_key') and not self.api_keys.get(source_name):
                    logger.debug(f"跳过 {source_name}: 缺少API密钥")
                    continue
                
                tasks.append(self._api_query(session, domain, source_name, source_config, logger))
            
            api_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 合并结果
            all_subdomains = set()
            for result in api_results:
                if isinstance(result, set):
                    all_subdomains.update(result)
                elif isinstance(result, Exception):
                    logger.warning(f"API查询失败: {result}")
            
            # 转换为结果对象
            for subdomain in all_subdomains:
                results.append(EnhancedSubdomainResult(
                    subdomain=subdomain,
                    discovery_method="api_query",
                    confidence_score=0.85,  # API查询可信度较高
                    source_details={'apis_used': list(self.api_sources.keys())}
                ))
        
        logger.info(f"API查询完成: 发现 {len(results)} 个子域名")
        return results
    
    async def _api_query(
        self, 
        session: aiohttp.ClientSession, 
        domain: str, 
        source_name: str, 
        source_config: Dict[str, Any], 
        logger: TaskLogger
    ) -> Set[str]:
        """单个API查询"""
        subdomains = set()
        
        try:
            url = source_config['url'].format(domain=domain)
            headers = {}
            params = {}
            
            # 设置API密钥
            if source_name in self.api_keys and self.api_keys[source_name]:
                if 'headers' in source_config:
                    headers.update(source_config['headers'])
                    headers['APIKEY'] = self.api_keys[source_name]
                elif 'params' in source_config:
                    params.update(source_config['params'])
                    params['apikey'] = self.api_keys[source_name]
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    if source_name == 'crtsh':
                        # 处理crt.sh JSON响应
                        data = await response.json()
                        for cert in data:
                            if 'name_value' in cert:
                                names = cert['name_value'].split('\n')
                                for name in names:
                                    name = name.strip().lower()
                                    if name and self._is_valid_subdomain(name, domain):
                                        subdomains.add(name)
                    
                    elif source_name == 'hackertarget':
                        # 处理hackertarget文本响应
                        text = await response.text()
                        lines = text.split('\n')
                        for line in lines:
                            if ',' in line:
                                subdomain = line.split(',')[0].strip().lower()
                                if self._is_valid_subdomain(subdomain, domain):
                                    subdomains.add(subdomain)
                    
                    elif source_name in ['virustotal', 'securitytrails']:
                        # 处理JSON响应
                        data = await response.json()
                        if source_name == 'virustotal' and 'subdomains' in data:
                            for sub in data['subdomains']:
                                full_domain = f"{sub}.{domain}"
                                if self._is_valid_subdomain(full_domain, domain):
                                    subdomains.add(full_domain)
                        elif source_name == 'securitytrails' and 'subdomains' in data:
                            for sub in data['subdomains']:
                                full_domain = f"{sub}.{domain}"
                                if self._is_valid_subdomain(full_domain, domain):
                                    subdomains.add(full_domain)
                
        except Exception as e:
            logger.warning(f"{source_name} API查询失败: {e}")
        
        return subdomains
    
    def _is_valid_subdomain(self, subdomain: str, target_domain: str) -> bool:
        """验证子域名是否有效"""
        if not subdomain or subdomain == target_domain:
            return False
        
        # 检查是否是目标域名的子域名
        if not subdomain.endswith(f'.{target_domain}') and subdomain != target_domain:
            return False
        
        # 检查域名格式
        domain_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$')
        return bool(domain_pattern.match(subdomain))


class PassiveDNSMethod:
    """被动DNS查询方法"""
    
    def __init__(self):
        self.passive_dns_sources = {
            'dnsdb': {
                'url': 'https://api.dnsdb.info/lookup/rrset/name/*.{domain}',
                'headers': {'X-API-Key': 'your_api_key'},
                'requires_key': True
            },
            'passivetotal': {
                'url': 'https://api.passivetotal.org/v2/dns/passive',
                'auth': ('username', 'api_key'),
                'requires_key': True
            }
        }
    
    async def discover(self, domain: str, logger: TaskLogger) -> List[EnhancedSubdomainResult]:
        """通过被动DNS发现子域名"""
        logger.info(f"开始被动DNS查询: {domain}")
        
        # 由于被动DNS服务通常需要付费API，这里先返回空结果
        # 实际实现时需要配置相应的API密钥
        results = []
        
        logger.info(f"被动DNS查询完成: 发现 {len(results)} 个子域名")
        return results


class EnhancedSubdomainDiscoveryEngine:
    """增强的子域名发现引擎"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 初始化发现方法
        self.methods = {
            'enhanced_dns': EnhancedDNSQueryMethod(),
            'search_engine': SearchEngineSubdomainMethod(),
            'api_based': APIBasedSubdomainMethod(),
            'passive_dns': PassiveDNSMethod()
        }
        
        # 结果去重和验证
        self.discovered_subdomains: Set[str] = set()
        self.validation_cache: Dict[str, bool] = {}
    
    async def discover_all_enhanced(
        self, 
        domain: str, 
        config: Dict[str, Any]
    ) -> List[EnhancedSubdomainResult]:
        """使用所有增强方法发现子域名"""
        start_time = time.time()
        self.logger.info(f"开始增强子域名发现: {domain}")
        
        all_results = []
        max_subdomains = config.get('max_subdomains', 2000)  # 提高默认限制
        
        # 并发执行所有发现方法
        discovery_tasks = []
        
        # DNS查询 - 始终启用
        discovery_tasks.append(self.methods['enhanced_dns'].discover(domain, self.logger))
        
        # 搜索引擎查询
        if config.get('search_engine_enabled', True):
            discovery_tasks.append(self.methods['search_engine'].discover(domain, self.logger))
        
        # API查询
        if config.get('api_query_enabled', True):
            discovery_tasks.append(self.methods['api_based'].discover(domain, self.logger))
        
        # 被动DNS查询
        if config.get('passive_dns_enabled', False):
            discovery_tasks.append(self.methods['passive_dns'].discover(domain, self.logger))
        
        # 执行所有发现任务
        discovery_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
        
        # 合并和去重结果
        subdomain_map = {}
        for method_results in discovery_results:
            if isinstance(method_results, list):
                for result in method_results:
                    if result.subdomain not in subdomain_map:
                        subdomain_map[result.subdomain] = result
                    else:
                        # 合并多个方法的发现结果
                        existing = subdomain_map[result.subdomain]
                        existing.discovery_method += f", {result.discovery_method}"
                        existing.confidence_score = max(existing.confidence_score, result.confidence_score)
                        existing.source_details.update(result.source_details)
            elif isinstance(method_results, Exception):
                self.logger.error(f"子域名发现方法异常: {method_results}")
        
        all_results = list(subdomain_map.values())
        
        # 限制结果数量
        if len(all_results) > max_subdomains:
            # 按可信度排序，保留最可信的结果
            all_results.sort(key=lambda x: x.confidence_score, reverse=True)
            all_results = all_results[:max_subdomains]
        
        # 验证子域名可访问性
        if config.get('verify_accessibility', True):
            all_results = await self._verify_accessibility_enhanced(all_results)
        
        duration = time.time() - start_time
        self.logger.info(f"增强子域名发现完成: 发现 {len(all_results)} 个子域名，耗时 {duration:.2f} 秒")
        
        return all_results
    
    async def _verify_accessibility_enhanced(
        self, 
        results: List[EnhancedSubdomainResult]
    ) -> List[EnhancedSubdomainResult]:
        """增强的可访问性验证"""
        self.logger.info(f"开始验证 {len(results)} 个子域名的可访问性")
        
        # 并发验证
        semaphore = asyncio.Semaphore(50)  # 控制并发数
        verification_tasks = []
        
        for result in results:
            verification_tasks.append(
                self._verify_single_subdomain(result, semaphore)
            )
        
        verified_results = await asyncio.gather(*verification_tasks, return_exceptions=True)
        
        # 过滤有效结果
        valid_results = []
        for result in verified_results:
            if isinstance(result, EnhancedSubdomainResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger.debug(f"子域名验证异常: {result}")
        
        accessible_count = sum(1 for r in valid_results if r.is_accessible)
        self.logger.info(f"可访问性验证完成: {accessible_count}/{len(valid_results)} 个子域名可访问")
        
        return valid_results
    
    async def _verify_single_subdomain(
        self, 
        result: EnhancedSubdomainResult, 
        semaphore: asyncio.Semaphore
    ) -> EnhancedSubdomainResult:
        """验证单个子域名的可访问性"""
        async with semaphore:
            start_time = time.time()
            
            # 如果已在缓存中，直接返回
            cache_key = f"{result.subdomain}_accessibility"
            if cache_key in self.validation_cache:
                result.is_accessible = self.validation_cache[cache_key]
                return result
            
            try:
                # 测试HTTPS和HTTP
                test_urls = [
                    f"https://{result.subdomain}",
                    f"http://{result.subdomain}"
                ]
                
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10),
                    connector=aiohttp.TCPConnector(ssl=False)
                ) as session:
                    
                    for url in test_urls:
                        try:
                            async with session.head(url) as response:
                                result.is_accessible = True
                                result.response_code = response.status
                                result.response_time = time.time() - start_time
                                result.server_header = response.headers.get('Server')
                                
                                # 缓存结果
                                self.validation_cache[cache_key] = True
                                return result
                                
                        except Exception:
                            continue
                
                # 所有测试都失败
                result.is_accessible = False
                self.validation_cache[cache_key] = False
                
            except Exception as e:
                self.logger.debug(f"验证子域名 {result.subdomain} 失败: {e}")
                result.is_accessible = False
                self.validation_cache[cache_key] = False
            
            return result
    
    def get_discovery_statistics(self) -> Dict[str, Any]:
        """获取发现统计信息"""
        method_stats = defaultdict(int)
        confidence_stats = defaultdict(int)
        
        # 这里可以添加统计逻辑
        
        return {
            'discovery_methods': dict(method_stats),
            'confidence_distribution': dict(confidence_stats),
            'total_cache_entries': len(self.validation_cache)
        }
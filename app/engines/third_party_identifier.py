import re
import json
import asyncio
from typing import List, Dict, Set, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass
from datetime import datetime
import tldextract

from app.core.logging import TaskLogger
from app.models.task import DomainType, RiskLevel


@dataclass
class ThirdPartyDomainResult:
    """第三方域名识别结果"""
    domain: str
    domain_type: str
    risk_level: str
    found_on_urls: List[str]
    confidence_score: float
    description: str
    category_tags: List[str]
    
    def __post_init__(self):
        self.discovered_at = datetime.utcnow()


class DomainClassifier:
    """域名分类器"""
    
    def __init__(self):
        self.domain_patterns = self._load_domain_patterns()
        self.risk_indicators = self._load_risk_indicators()
    
    def _load_domain_patterns(self) -> Dict[str, Dict[str, Any]]:
        """加载域名模式库"""
        return {
            # CDN服务提供商
            'cdn': {
                'patterns': [
                    r'.*\.cloudfront\.net',
                    r'.*\.fastly\.com',
                    r'.*\.cloudflare\.com',
                    r'.*\.jsdelivr\.net',
                    r'.*\.unpkg\.com',
                    r'.*\.cdnjs\.cloudflare\.com',
                    r'.*\.bootstrapcdn\.com',
                    r'.*\.maxcdn\.com',
                    r'.*\.keycdn\.com',
                    r'.*\.stackpath\.bootstrapcdn\.com'
                ],
                'keywords': ['cdn', 'cache', 'static', 'assets'],
                'risk_level': 'low',
                'description': 'Content Delivery Network'
            },
            
            # 分析和统计服务
            'analytics': {
                'patterns': [
                    r'.*\.google-analytics\.com',
                    r'.*\.googletagmanager\.com',
                    r'.*\.googlesyndication\.com',
                    r'.*\.doubleclick\.net',
                    r'.*\.facebook\.com/tr',
                    r'.*\.facebook\.net',
                    r'.*\.baidu\.com',
                    r'.*\.umeng\.com',
                    r'.*\.cnzz\.com',
                    r'.*\.51\.la',
                    r'.*analytics.*',
                    r'.*\.mixpanel\.com',
                    r'.*\.hotjar\.com',
                    r'.*\.segment\.com'
                ],
                'keywords': ['analytics', 'tracking', 'stats', 'monitor'],
                'risk_level': 'medium',
                'description': 'Analytics and Tracking Service'
            },
            
            # 广告服务
            'advertising': {
                'patterns': [
                    r'.*\.googlesyndication\.com',
                    r'.*\.googleadservices\.com',
                    r'.*\.doubleclick\.net',
                    r'.*\.adsystem\.com',
                    r'.*\.amazon-adsystem\.com',
                    r'.*\.facebook\.com/tr',
                    r'.*\.bing\.com/ads',
                    r'.*\.ads\.yahoo\.com',
                    r'.*\.adsense\.com',
                    r'.*\.adnxs\.com',
                    r'.*\.advertising\.com',
                    r'.*\.adsrvr\.org'
                ],
                'keywords': ['ads', 'advertising', 'sponsor', 'promotion'],
                'risk_level': 'medium',
                'description': 'Advertising Network'
            },
            
            # 社交媒体
            'social': {
                'patterns': [
                    r'.*\.facebook\.com',
                    r'.*\.twitter\.com',
                    r'.*\.linkedin\.com',
                    r'.*\.youtube\.com',
                    r'.*\.instagram\.com',
                    r'.*\.tiktok\.com',
                    r'.*\.weibo\.com',
                    r'.*\.qq\.com',
                    r'.*\.wechat\.com',
                    r'.*\.pinterest\.com',
                    r'.*\.snapchat\.com'
                ],
                'keywords': ['social', 'share', 'like', 'follow'],
                'risk_level': 'low',
                'description': 'Social Media Platform'
            },
            
            # API和微服务
            'api': {
                'patterns': [
                    r'api\..*',
                    r'.*\.api\..*',
                    r'rest\..*',
                    r'graphql\..*',
                    r'.*\.amazonaws\.com',
                    r'.*\.azurewebsites\.net',
                    r'.*\.herokuapp\.com',
                    r'.*\.vercel\.app',
                    r'.*\.netlify\.app'
                ],
                'keywords': ['api', 'rest', 'graphql', 'service', 'micro'],
                'risk_level': 'low',
                'description': 'API or Microservice'
            },
            
            # 支付服务
            'payment': {
                'patterns': [
                    r'.*\.paypal\.com',
                    r'.*\.stripe\.com',
                    r'.*\.alipay\.com',
                    r'.*\.wepay\.com',
                    r'.*\.square\.com',
                    r'.*\.braintree\.com',
                    r'.*\.authorize\.net',
                    r'.*\.worldpay\.com'
                ],
                'keywords': ['pay', 'payment', 'checkout', 'billing'],
                'risk_level': 'high',
                'description': 'Payment Service Provider'
            },
            
            # 安全服务
            'security': {
                'patterns': [
                    r'.*\.recaptcha\.net',
                    r'.*\.hcaptcha\.com',
                    r'.*\.cloudflare\.com',
                    r'.*\.akamai\.com',
                    r'.*\.imperva\.com',
                    r'.*\.sucuri\.net'
                ],
                'keywords': ['captcha', 'security', 'protect', 'firewall'],
                'risk_level': 'low',
                'description': 'Security Service'
            },
            
            # 地图和位置服务
            'maps': {
                'patterns': [
                    r'.*\.googleapis\.com/maps',
                    r'maps\.google\.com',
                    r'.*\.mapbox\.com',
                    r'.*\.openstreetmap\.org',
                    r'.*\.here\.com',
                    r'.*\.baidu\.com/maps'
                ],
                'keywords': ['map', 'geo', 'location', 'place'],
                'risk_level': 'low',
                'description': 'Map and Location Service'
            }
        }
    
    def _load_risk_indicators(self) -> Dict[str, List[str]]:
        """加载风险指标"""
        return {
            'high_risk_keywords': [
                'malware', 'virus', 'phishing', 'spam', 'scam', 'fraud',
                'adult', 'porn', 'gambling', 'casino', 'bet', 'drug',
                'hack', 'crack', 'pirate', 'illegal', 'torrent'
            ],
            'suspicious_tlds': [
                '.tk', '.ml', '.ga', '.cf', '.gq', '.top', '.click',
                '.download', '.loan', '.win', '.faith', '.science'
            ],
            'suspicious_patterns': [
                r'.*-.*-.*-.*',  # 多个连字符
                r'.*\d{4,}.*',   # 长数字序列
                r'.{20,}',       # 超长域名
                r'.*[0-9]+[a-z]+[0-9]+.*'  # 数字字母混合
            ]
        }
    
    def classify_domain(self, domain: str, context: Dict[str, Any] = None) -> Tuple[str, str, float]:
        """对域名进行分类"""
        domain_lower = domain.lower()
        
        # 检查已知模式
        for category, config in self.domain_patterns.items():
            # 检查正则表达式模式
            for pattern in config['patterns']:
                if re.match(pattern, domain_lower):
                    return category, config['risk_level'], 0.9
            
            # 检查关键词
            for keyword in config['keywords']:
                if keyword in domain_lower:
                    return category, config['risk_level'], 0.7
        
        # 计算风险评分
        risk_level, risk_score = self._assess_risk(domain_lower)
        
        return 'unknown', risk_level, risk_score
    
    def _assess_risk(self, domain: str) -> Tuple[str, float]:
        """评估域名风险"""
        risk_score = 0.0
        
        # 检查高风险关键词
        for keyword in self.risk_indicators['high_risk_keywords']:
            if keyword in domain:
                risk_score += 0.3
        
        # 检查可疑TLD
        try:
            extracted = tldextract.extract(domain)
            if extracted.suffix in self.risk_indicators['suspicious_tlds']:
                risk_score += 0.2
        except:
            pass
        
        # 检查可疑模式
        for pattern in self.risk_indicators['suspicious_patterns']:
            if re.match(pattern, domain):
                risk_score += 0.1
        
        # 域名长度风险
        if len(domain) > 50:
            risk_score += 0.1
        
        # 确定风险等级
        if risk_score >= 0.7:
            return 'critical', risk_score
        elif risk_score >= 0.5:
            return 'high', risk_score
        elif risk_score >= 0.3:
            return 'medium', risk_score
        else:
            return 'low', risk_score


class ThirdPartyIdentifierEngine:
    """第三方域名识别引擎"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        self.classifier = DomainClassifier()
        self.identified_domains = {}
        
    async def identify_third_party_domains(
        self, 
        target_domain: str, 
        crawl_results: List[Any],
        config: Dict[str, Any]
    ) -> List[ThirdPartyDomainResult]:
        """识别第三方域名"""
        self.logger.info(f"开始识别第三方域名，目标域名: {target_domain}")
        
        # 提取所有发现的域名
        all_domains = self._extract_domains_from_results(crawl_results)
        
        # 过滤第三方域名
        third_party_domains = self._filter_third_party_domains(target_domain, all_domains)
        
        # 分类和风险评估
        results = []
        for domain_info in third_party_domains:
            domain = domain_info['domain']
            found_urls = domain_info['found_on_urls']
            
            # 检查缓存库
            cached_result = await self._check_domain_cache(domain)
            if cached_result:
                # 使用缓存库结果
                result = ThirdPartyDomainResult(
                    domain=domain,
                    domain_type=cached_result.domain_type,
                    risk_level=cached_result.risk_level,
                    found_on_urls=found_urls,
                    confidence_score=0.95,  # 缓存库结果置信度更高
                    description=f"使用缓存库分析结果 - {cached_result.page_description or cached_result.domain_type}",
                    category_tags=[cached_result.domain_type, "cached", "from_cache_library"]
                )
                self.logger.info(f"使用缓存库结果: {domain}")
            else:
                # 分类域名
                domain_type, risk_level, confidence = self.classifier.classify_domain(
                    domain, {'found_urls': found_urls}
                )
                
                # 生成描述和标签
                description = self._generate_description(domain, domain_type, risk_level)
                tags = self._generate_tags(domain, domain_type, found_urls)
                
                result = ThirdPartyDomainResult(
                    domain=domain,
                    domain_type=domain_type,
                    risk_level=risk_level,
                    found_on_urls=found_urls,
                    confidence_score=confidence,
                    description=description,
                    category_tags=tags
                )
                
                # 保存到缓存库
                await self._save_to_domain_cache(domain, result)
            
            results.append(result)
        
        # 按风险等级排序
        results.sort(key=lambda x: self._get_risk_priority(x.risk_level), reverse=True)
        
        self.logger.info(f"第三方域名识别完成: 识别到 {len(results)} 个第三方域名")
        
        return results
    
    def _extract_domains_from_results(self, crawl_results: List[Any]) -> Dict[str, List[str]]:
        """从爬取结果中提取所有域名"""
        domain_urls = {}
        
        for result in crawl_results:
            if hasattr(result, 'links'):
                self._extract_domains_from_urls(result.links, result.url, domain_urls)
            
            if hasattr(result, 'resources'):
                self._extract_domains_from_urls(result.resources, result.url, domain_urls)
            
            if hasattr(result, 'forms'):
                self._extract_domains_from_urls(result.forms, result.url, domain_urls)
        
        return domain_urls
    
    def _extract_domains_from_urls(self, urls: List[str], source_url: str, domain_urls: Dict[str, List[str]]):
        """从URL列表中提取域名"""
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    domain = parsed.netloc.lower()
                    
                    # 移除端口号
                    if ':' in domain:
                        domain = domain.split(':')[0]
                    
                    # 移除www前缀
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    
                    if domain not in domain_urls:
                        domain_urls[domain] = []
                    
                    if source_url not in domain_urls[domain]:
                        domain_urls[domain].append(source_url)
                        
            except Exception as e:
                self.logger.debug(f"URL解析失败: {url} - {e}")
    
    def _filter_third_party_domains(self, target_domain: str, all_domains: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """过滤出第三方域名"""
        target_domain_lower = target_domain.lower()
        third_party_domains = []
        
        for domain, found_urls in all_domains.items():
            # 排除目标域名及其子域名
            if not self._is_same_or_subdomain(domain, target_domain_lower):
                # 排除本地和内网地址
                if not self._is_local_domain(domain):
                    third_party_domains.append({
                        'domain': domain,
                        'found_on_urls': found_urls
                    })
        
        return third_party_domains
    
    def _is_same_or_subdomain(self, domain: str, target_domain: str) -> bool:
        """检查是否为相同域名或子域名"""
        domain_lower = domain.lower()
        target_lower = target_domain.lower()
        
        return (domain_lower == target_lower or 
                domain_lower.endswith(f'.{target_lower}') or
                target_lower.endswith(f'.{domain_lower}'))
    
    def _is_local_domain(self, domain: str) -> bool:
        """检查是否为本地或内网域名"""
        local_patterns = [
            r'^localhost$',
            r'^127\.0\.0\.1$',
            r'^192\.168\.\d+\.\d+$',
            r'^10\.\d+\.\d+\.\d+$',
            r'^172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+$',
            r'^.*\.local$',
            r'^.*\.internal$',
            r'^.*\.intranet$'
        ]
        
        for pattern in local_patterns:
            if re.match(pattern, domain, re.IGNORECASE):
                return True
        
        return False
    
    def _generate_description(self, domain: str, domain_type: str, risk_level: str) -> str:
        """生成域名描述"""
        type_descriptions = {
            'cdn': f"CDN服务提供商 - {domain}",
            'analytics': f"分析统计服务 - {domain}",
            'advertising': f"广告网络服务 - {domain}",
            'social': f"社交媒体平台 - {domain}",
            'api': f"API服务接口 - {domain}",
            'payment': f"支付服务提供商 - {domain}",
            'security': f"安全防护服务 - {domain}",
            'maps': f"地图位置服务 - {domain}",
            'unknown': f"未知类型第三方服务 - {domain}"
        }
        
        base_description = type_descriptions.get(domain_type, f"第三方服务 - {domain}")
        
        if risk_level in ['high', 'critical']:
            base_description += " (需要重点关注)"
        elif risk_level == 'medium':
            base_description += " (建议审查)"
        
        return base_description
    
    def _generate_tags(self, domain: str, domain_type: str, found_urls: List[str]) -> List[str]:
        """生成域名标签"""
        tags = [domain_type]
        
        # 基于域名特征添加标签
        if 'google' in domain:
            tags.append('google-service')
        elif 'facebook' in domain or 'fb' in domain:
            tags.append('facebook-service')
        elif 'amazon' in domain:
            tags.append('amazon-service')
        elif 'microsoft' in domain:
            tags.append('microsoft-service')
        
        # 基于URL数量添加标签
        if len(found_urls) > 10:
            tags.append('high-usage')
        elif len(found_urls) > 5:
            tags.append('medium-usage')
        else:
            tags.append('low-usage')
        
        # 基于协议添加标签
        https_count = sum(1 for url in found_urls if url.startswith('https://'))
        if https_count == len(found_urls):
            tags.append('secure-only')
        elif https_count > 0:
            tags.append('mixed-protocol')
        else:
            tags.append('insecure-only')
        
        return list(set(tags))
    
    def _get_risk_priority(self, risk_level: str) -> int:
        """获取风险等级优先级"""
        priority_map = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1,
            'unknown': 0
        }
        return priority_map.get(risk_level, 0)
    
    async def _check_domain_cache(self, domain: str) -> Optional[Any]:
        """检查第三方域名缓存库"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.third_party_cache import ThirdPartyDomainCache
            from sqlalchemy import select
            from datetime import datetime, timedelta
            
            async with AsyncSessionLocal() as db:
                # 查找缓存的域名信息
                stmt = select(ThirdPartyDomainCache).where(
                    ThirdPartyDomainCache.domain == domain
                )
                
                result = await db.execute(stmt)
                cached_domain = result.scalar_one_or_none()
                
                if cached_domain:
                    # 检查是否在7天内更新过
                    seven_days_ago = datetime.utcnow() - timedelta(days=7)
                    if cached_domain.last_identified_at >= seven_days_ago:
                        self.logger.debug(f"找到缓存库中的域名信息: {domain}")
                        return cached_domain
                    else:
                        self.logger.debug(f"缓存库中的域名信息已过期: {domain}")
                
        except Exception as e:
            self.logger.warning(f"检查域名缓存库失败: {e}")
        
        return None
    
    async def _save_to_domain_cache(self, domain: str, result: ThirdPartyDomainResult):
        """保存域名信息到缓存库"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.third_party_cache import ThirdPartyDomainCache
            from sqlalchemy import select, update
            from datetime import datetime
            
            async with AsyncSessionLocal() as db:
                # 检查是否已存在
                stmt = select(ThirdPartyDomainCache).where(
                    ThirdPartyDomainCache.domain == domain
                )
                
                db_result = await db.execute(stmt)
                existing_cache = db_result.scalar_one_or_none()
                
                if existing_cache:
                    # 更新现有记录
                    update_stmt = update(ThirdPartyDomainCache).where(
                        ThirdPartyDomainCache.id == existing_cache.id
                    ).values(
                        domain_type=result.domain_type,
                        risk_level=result.risk_level,
                        page_title=result.description[:500] if result.description else None,
                        page_description=result.description[:1000] if result.description else None,
                        identification_count=existing_cache.identification_count + 1,
                        last_identified_at=datetime.utcnow()
                    )
                    await db.execute(update_stmt)
                else:
                    # 创建新记录
                    cache_record = ThirdPartyDomainCache(
                        domain=domain,
                        domain_type=result.domain_type,
                        risk_level=result.risk_level,
                        page_title=result.description[:500] if result.description else None,
                        page_description=result.description[:1000] if result.description else None,
                        identification_count=1,
                        first_identified_at=datetime.utcnow(),
                        last_identified_at=datetime.utcnow()
                    )
                    db.add(cache_record)
                
                await db.commit()
                
        except Exception as e:
            self.logger.warning(f"保存域名到缓存库失败: {e}")
    
    async def get_identification_statistics(self) -> Dict[str, Any]:
        """获取识别统计信息"""
        return {
            'total_identified': len(self.identified_domains),
            'risk_distribution': self._calculate_risk_distribution(),
            'type_distribution': self._calculate_type_distribution()
        }
    
    def _calculate_risk_distribution(self) -> Dict[str, int]:
        """计算风险分布"""
        distribution = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        for domain_info in self.identified_domains.values():
            risk_level = domain_info.get('risk_level', 'low')
            if risk_level in distribution:
                distribution[risk_level] += 1
        
        return distribution
    
    def _calculate_type_distribution(self) -> Dict[str, int]:
        """计算类型分布"""
        distribution = {}
        
        for domain_info in self.identified_domains.values():
            domain_type = domain_info.get('type', 'unknown')
            distribution[domain_type] = distribution.get(domain_type, 0) + 1
        
        return distribution
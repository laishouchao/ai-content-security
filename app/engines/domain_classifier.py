"""
域名分类器
智能分析和分类发现的域名，区分目标子域名、第三方域名、内部链接等

核心功能：
1. 域名类型自动识别和分类
2. 目标子域名检测和验证
3. 第三方域名识别和风险评估
4. 内部链接和外部链接区分
5. 域名相似度和关联性分析
6. CDN和服务域名识别
7. 恶意域名特征检测
8. 域名优先级评分系统
"""

import re
import tldextract
import asyncio
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from urllib.parse import urlparse
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import ipaddress
from collections import defaultdict, Counter

from app.core.logging import TaskLogger


class DomainType(Enum):
    """域名类型枚举"""
    TARGET_SUBDOMAIN = "target_subdomain"      # 目标子域名
    TARGET_MAIN = "target_main"                # 目标主域名
    THIRD_PARTY = "third_party"                # 第三方域名
    INTERNAL_LINK = "internal_link"            # 内部链接
    CDN_SERVICE = "cdn_service"                # CDN服务域名
    SOCIAL_MEDIA = "social_media"              # 社交媒体域名
    ADVERTISING = "advertising"                # 广告域名
    ANALYTICS = "analytics"                    # 分析统计域名
    SUSPICIOUS = "suspicious"                  # 可疑域名
    BLOCKED = "blocked"                        # 被阻止域名
    UNKNOWN = "unknown"                        # 未知类型


class DomainPriority(Enum):
    """域名优先级"""
    CRITICAL = 5     # 关键 - 目标域名必须爬取
    HIGH = 4         # 高 - 子域名和重要第三方
    MEDIUM = 3       # 中等 - 一般第三方域名
    LOW = 2          # 低 - CDN、广告等
    IGNORE = 1       # 忽略 - 不需要爬取


@dataclass
class DomainClassification:
    """域名分类结果"""
    domain: str
    normalized_domain: str
    domain_type: DomainType
    priority: DomainPriority
    
    # 分析详情
    is_target_related: bool = False
    is_subdomain: bool = False
    is_ip_address: bool = False
    similarity_score: float = 0.0
    
    # 特征标签
    features: Set[str] = field(default_factory=set)
    risk_indicators: List[str] = field(default_factory=list)
    
    # 元数据
    tld_info: Optional[Dict[str, str]] = None
    classification_reasons: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    
    # 统计信息
    discovery_count: int = 1
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """后处理初始化"""
        if not self.tld_info:
            self.tld_info = self._extract_tld_info()
    
    def _extract_tld_info(self) -> Dict[str, str]:
        """提取TLD信息"""
        try:
            extracted = tldextract.extract(self.domain)
            return {
                'subdomain': extracted.subdomain,
                'domain': extracted.domain,
                'suffix': extracted.suffix,
                'registered_domain': extracted.registered_domain
            }
        except Exception:
            return {}


class DomainClassifier:
    """域名分类器"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain.lower()
        self.logger = TaskLogger(task_id, user_id)
        
        # 提取目标域名信息
        self.target_tld = tldextract.extract(self.target_domain)
        self.target_registered_domain = self.target_tld.registered_domain.lower()
        
        # 域名分类缓存
        self.classification_cache: Dict[str, DomainClassification] = {}
        
        # 初始化分类规则
        self._init_classification_rules()
    
    def _init_classification_rules(self):
        """初始化分类规则"""
        # CDN服务域名
        self.cdn_patterns = [
            r'.*\.cloudflare\.com$',
            r'.*\.cloudfront\.net$',
            r'.*\.fastly\.com$',
            r'.*\.akamai\.net$',
            r'.*\.amazonaws\.com$',
            r'.*\.azure\.com$',
            r'.*\.googleusercontent\.com$',
            r'.*\.jsdelivr\.net$',
            r'.*\.unpkg\.com$',
        ]
        
        # 社交媒体域名
        self.social_media_patterns = [
            r'.*\.facebook\.com$',
            r'.*\.twitter\.com$',
            r'.*\.instagram\.com$',
            r'.*\.linkedin\.com$',
            r'.*\.youtube\.com$',
            r'.*\.tiktok\.com$',
            r'.*\.weibo\.com$',
            r'.*\.qq\.com$',
            r'.*\.wechat\.com$',
        ]
        
        # 广告域名
        self.advertising_patterns = [
            r'^.*doubleclick\.net$',
            r'^.*googlesyndication\.com$',
            r'^.*googleadservices\.com$',
            r'^.*\.ads\..*$',
            r'^ads\..*$',
            r'^.*tracking.*\..*$',
        ]
        
        # 分析统计域名
        self.analytics_patterns = [
            r'^.*google-analytics\.com$',
            r'^.*googletagmanager\.com$',
            r'^.*hotjar\.com$',
            r'^.*segment\.com$',
            r'^.*mixpanel\.com$',
            r'^stats\..*$',
            r'^analytics\..*$',
        ]
        
        # 可疑域名特征
        self.suspicious_patterns = [
            r'.*\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}.*',  # IP地址形式
            r'.*[a-f0-9]{32,}.*',                      # 长哈希字符串
            r'.*\.tk$', r'.*\.ml$', r'.*\.ga$',        # 免费域名后缀
            r'.*porn.*', r'.*adult.*', r'.*xxx.*',     # 成人内容关键词
            r'.*casino.*', r'.*bet.*', r'.*gambling.*', # 赌博关键词
            r'.*drug.*', r'.*pharma.*',                 # 药物关键词
        ]
        
        # 编译正则表达式
        self.cdn_regexes = [re.compile(p, re.IGNORECASE) for p in self.cdn_patterns]
        self.social_regexes = [re.compile(p, re.IGNORECASE) for p in self.social_media_patterns]
        self.ad_regexes = [re.compile(p, re.IGNORECASE) for p in self.advertising_patterns]
        self.analytics_regexes = [re.compile(p, re.IGNORECASE) for p in self.analytics_patterns]
        self.suspicious_regexes = [re.compile(p, re.IGNORECASE) for p in self.suspicious_patterns]
    
    async def classify_domain(
        self, 
        domain: str, 
        source_url: Optional[str] = None,
        discovery_method: Optional[str] = None
    ) -> DomainClassification:
        """分类单个域名"""
        try:
            normalized_domain = self._normalize_domain(domain)
            if not normalized_domain:
                return self._create_unknown_classification(domain)
            
            # 检查缓存
            if normalized_domain in self.classification_cache:
                cached = self.classification_cache[normalized_domain]
                cached.discovery_count += 1
                cached.last_seen = datetime.now()
                return cached
            
            # 执行分类
            classification = await self._perform_classification(normalized_domain, source_url, discovery_method)
            
            # 缓存结果
            self.classification_cache[normalized_domain] = classification
            
            self.logger.debug(f"域名分类完成: {domain} -> {classification.domain_type.value} (优先级: {classification.priority.value})")
            return classification
            
        except Exception as e:
            self.logger.error(f"域名分类失败 {domain}: {e}")
            return self._create_unknown_classification(domain)
    
    async def classify_domains_batch(
        self, 
        domains: List[str], 
        max_concurrent: int = 50
    ) -> List[DomainClassification]:
        """批量分类域名"""
        self.logger.info(f"开始批量域名分类: {len(domains)} 个域名")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def classify_with_semaphore(domain: str) -> DomainClassification:
            async with semaphore:
                return await self.classify_domain(domain)
        
        tasks = [classify_with_semaphore(domain) for domain in domains]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        classifications = []
        for i, result in enumerate(results):
            if isinstance(result, DomainClassification):
                classifications.append(result)
            else:
                self.logger.warning(f"域名 {domains[i]} 分类失败: {result}")
                classifications.append(self._create_unknown_classification(domains[i]))
        
        self.logger.info(f"批量域名分类完成: {len(classifications)} 个结果")
        return classifications
    
    async def _perform_classification(
        self, 
        domain: str, 
        source_url: Optional[str] = None,
        discovery_method: Optional[str] = None
    ) -> DomainClassification:
        """执行域名分类逻辑"""
        classification = DomainClassification(
            domain=domain,
            normalized_domain=domain,
            domain_type=DomainType.UNKNOWN,  # 初始化为未知类型
            priority=DomainPriority.LOW      # 初始化为低优先级
        )
        
        # 1. 基础检查
        self._check_basic_features(classification)
        
        # 2. 目标域名相关性检查
        self._check_target_relationship(classification)
        
        # 3. 特殊服务域名检查
        self._check_service_domains(classification)
        
        # 4. 风险指标检查
        self._check_risk_indicators(classification)
        
        # 5. 计算相似度得分
        classification.similarity_score = self._calculate_similarity(domain)
        
        # 6. 最终分类决策
        self._make_final_classification(classification)
        
        # 7. 计算置信度
        classification.confidence_score = self._calculate_confidence(classification)
        
        return classification
    
    def _check_basic_features(self, classification: DomainClassification):
        """检查基础特征"""
        domain = classification.domain
        
        # 检查是否为IP地址
        try:
            ipaddress.ip_address(domain)
            classification.is_ip_address = True
            classification.features.add('ip_address')
        except ValueError:
            pass
        
        # 检查域名长度
        if len(domain) > 50:
            classification.features.add('long_domain')
        
        # 检查数字比例
        digit_count = sum(c.isdigit() for c in domain)
        if digit_count / len(domain) > 0.3:
            classification.features.add('high_digit_ratio')
        
        # 检查连字符
        if domain.count('-') > 3:
            classification.features.add('many_hyphens')
        
        # 检查子域名层级
        subdomain_levels = domain.count('.')
        if subdomain_levels > 3:
            classification.features.add('deep_subdomain')
    
    def _check_target_relationship(self, classification: DomainClassification):
        """检查与目标域名的关系（强化版本）"""
        domain = classification.domain
        
        try:
            # 完全匹配目标域名
            if domain == self.target_domain:
                classification.domain_type = DomainType.TARGET_MAIN
                classification.is_target_related = True
                classification.priority = DomainPriority.CRITICAL
                classification.classification_reasons.append("完全匹配目标域名")
                return
            
            # 目标域名的子域名（基本检查）
            if domain.endswith('.' + self.target_domain):
                classification.domain_type = DomainType.TARGET_SUBDOMAIN
                classification.is_target_related = True
                classification.is_subdomain = True
                classification.priority = DomainPriority.CRITICAL
                classification.classification_reasons.append("目标域名的子域名")
                classification.features.add('target_subdomain')
                return
            
            # 使用tldextract进行精确的域名解析
            extracted = tldextract.extract(domain)
            domain_registered = extracted.registered_domain.lower()
            
            # 相同注册域名
            if domain_registered == self.target_registered_domain:
                # 如果有子域名，则是目标域名的子域名
                if extracted.subdomain:
                    classification.domain_type = DomainType.TARGET_SUBDOMAIN
                    classification.is_target_related = True
                    classification.is_subdomain = True
                    classification.priority = DomainPriority.CRITICAL
                    classification.classification_reasons.append("目标域名的子域名（精确解析）")
                    classification.features.add('target_subdomain')
                else:
                    # 没有子域名，是主域名
                    classification.domain_type = DomainType.TARGET_MAIN
                    classification.is_target_related = True
                    classification.priority = DomainPriority.CRITICAL
                    classification.classification_reasons.append("目标域名本身（精确解析）")
                
                classification.features.add('same_registered_domain')
                return
            
            # 如果没有匹配，记录调试信息
            self.logger.debug(f"域名 {domain} 与目标域名 {self.target_domain} 不相关")
            self.logger.debug(f"  - 域名注册域: {domain_registered}")
            self.logger.debug(f"  - 目标注册域: {self.target_registered_domain}")
        
        except Exception as e:
            self.logger.debug(f"目标关系检查失败 {domain}: {e}")
    
    def _check_service_domains(self, classification: DomainClassification):
        """检查特殊服务域名"""
        domain = classification.domain
        
        # CDN服务
        if any(regex.match(domain) for regex in self.cdn_regexes):
            classification.domain_type = DomainType.CDN_SERVICE
            classification.priority = DomainPriority.LOW
            classification.features.add('cdn_service')
            classification.classification_reasons.append("CDN服务域名")
            return
        
        # 社交媒体
        if any(regex.match(domain) for regex in self.social_regexes):
            classification.domain_type = DomainType.SOCIAL_MEDIA
            classification.priority = DomainPriority.LOW
            classification.features.add('social_media')
            classification.classification_reasons.append("社交媒体域名")
            return
        
        # 广告域名
        if any(regex.match(domain) for regex in self.ad_regexes):
            classification.domain_type = DomainType.ADVERTISING
            classification.priority = DomainPriority.IGNORE
            classification.features.add('advertising')
            classification.classification_reasons.append("广告域名")
            return
        
        # 分析统计
        if any(regex.match(domain) for regex in self.analytics_regexes):
            classification.domain_type = DomainType.ANALYTICS
            classification.priority = DomainPriority.IGNORE
            classification.features.add('analytics')
            classification.classification_reasons.append("分析统计域名")
            return
    
    def _check_risk_indicators(self, classification: DomainClassification):
        """检查风险指标"""
        domain = classification.domain
        
        # 可疑模式检查
        for regex in self.suspicious_regexes:
            if regex.match(domain):
                classification.risk_indicators.append("匹配可疑模式")
                classification.features.add('suspicious_pattern')
        
        # 免费域名检查
        free_tlds = ['.tk', '.ml', '.ga', '.cf', '.gq']
        if any(domain.endswith(tld) for tld in free_tlds):
            classification.risk_indicators.append("使用免费域名后缀")
            classification.features.add('free_tld')
        
        # 新gTLD检查
        new_gtlds = ['.top', '.club', '.online', '.site', '.website', '.space']
        if any(domain.endswith(tld) for tld in new_gtlds):
            classification.features.add('new_gtld')
        
        # 如果有风险指标，标记为可疑
        if classification.risk_indicators:
            if classification.domain_type == DomainType.UNKNOWN:
                classification.domain_type = DomainType.SUSPICIOUS
                classification.priority = DomainPriority.MEDIUM
                classification.classification_reasons.append("存在风险指标")
    
    def _calculate_similarity(self, domain: str) -> float:
        """计算与目标域名的相似度"""
        try:
            # 简单的字符串相似度计算
            target = self.target_domain
            
            # Levenshtein距离相似度
            def levenshtein_similarity(s1: str, s2: str) -> float:
                if len(s1) < len(s2):
                    return levenshtein_similarity(s2, s1)
                
                if len(s2) == 0:
                    return 0.0
                
                previous_row = list(range(len(s2) + 1))
                for i, c1 in enumerate(s1):
                    current_row = [i + 1]
                    for j, c2 in enumerate(s2):
                        insertions = previous_row[j + 1] + 1
                        deletions = current_row[j] + 1
                        substitutions = previous_row[j] + (c1 != c2)
                        current_row.append(min(insertions, deletions, substitutions))
                    previous_row = current_row
                
                return 1.0 - previous_row[-1] / len(s1)
            
            return levenshtein_similarity(domain, target)
            
        except Exception:
            return 0.0
    
    def _make_final_classification(self, classification: DomainClassification):
        """最终分类决策"""
        # 如果已经分类，不再修改
        if classification.domain_type != DomainType.UNKNOWN:
            return
        
        # 基于特征进行分类
        if classification.is_target_related:
            classification.domain_type = DomainType.TARGET_SUBDOMAIN
            classification.priority = DomainPriority.HIGH
            classification.classification_reasons.append("与目标域名相关")
        
        elif classification.similarity_score > 0.8:
            classification.domain_type = DomainType.TARGET_SUBDOMAIN
            classification.priority = DomainPriority.HIGH
            classification.classification_reasons.append("高相似度域名")
        
        elif 'suspicious_pattern' in classification.features:
            classification.domain_type = DomainType.SUSPICIOUS
            classification.priority = DomainPriority.MEDIUM
            classification.classification_reasons.append("可疑特征")
        
        else:
            classification.domain_type = DomainType.THIRD_PARTY
            classification.priority = DomainPriority.MEDIUM
            classification.classification_reasons.append("第三方域名")
    
    def _calculate_confidence(self, classification: DomainClassification) -> float:
        """计算分类置信度"""
        confidence = 0.5  # 基础置信度
        
        # 根据分类依据调整置信度
        if classification.is_target_related:
            confidence += 0.3
        
        if classification.similarity_score > 0.7:
            confidence += 0.2
        
        if len(classification.features) > 0:
            confidence += 0.1
        
        if len(classification.classification_reasons) > 1:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _normalize_domain(self, domain: str) -> Optional[str]:
        """规范化域名"""
        try:
            domain = domain.lower().strip()
            
            # 移除协议前缀
            if domain.startswith(('http://', 'https://')):
                domain = urlparse(f"http://{domain}").netloc
            
            # 移除端口号
            if ':' in domain and not domain.count(':') > 1:  # 不是IPv6
                domain = domain.split(':')[0]
            
            # 移除路径
            if '/' in domain:
                domain = domain.split('/')[0]
            
            # 基本验证
            if not domain or '.' not in domain:
                return None
            
            return domain
            
        except Exception:
            return None
    
    def _create_unknown_classification(self, domain: str) -> DomainClassification:
        """创建未知类型分类"""
        return DomainClassification(
            domain=domain,
            normalized_domain=domain,
            domain_type=DomainType.UNKNOWN,
            priority=DomainPriority.LOW,
            classification_reasons=["分类失败"],
            confidence_score=0.1
        )
    
    def get_classification_statistics(self) -> Dict[str, Any]:
        """获取分类统计信息"""
        if not self.classification_cache:
            return {}
        
        classifications = list(self.classification_cache.values())
        
        # 按类型统计
        type_counts = Counter(c.domain_type.value for c in classifications)
        
        # 按优先级统计
        priority_counts = Counter(c.priority.value for c in classifications)
        
        # 特征统计
        all_features = []
        for c in classifications:
            all_features.extend(c.features)
        feature_counts = Counter(all_features)
        
        return {
            'total_domains': len(classifications),
            'type_distribution': dict(type_counts),
            'priority_distribution': dict(priority_counts),
            'feature_distribution': dict(feature_counts.most_common(10)),
            'target_related_count': sum(1 for c in classifications if c.is_target_related),
            'high_priority_count': sum(1 for c in classifications if c.priority.value >= 4),
            'average_confidence': sum(c.confidence_score for c in classifications) / len(classifications)
        }
    
    def get_prioritized_domains(
        self, 
        min_priority: DomainPriority = DomainPriority.LOW,
        domain_types: Optional[List[DomainType]] = None,
        limit: Optional[int] = None
    ) -> List[DomainClassification]:
        """获取按优先级排序的域名"""
        classifications = list(self.classification_cache.values())
        
        # 过滤条件
        filtered = []
        for c in classifications:
            if c.priority.value < min_priority.value:
                continue
            
            if domain_types and c.domain_type not in domain_types:
                continue
            
            filtered.append(c)
        
        # 按优先级和置信度排序
        filtered.sort(key=lambda x: (x.priority.value, x.confidence_score), reverse=True)
        
        if limit:
            filtered = filtered[:limit]
        
        return filtered


# 便捷函数
async def classify_domain(
    domain: str,
    target_domain: str,
    task_id: str = "default",
    user_id: str = "default"
) -> DomainClassification:
    """便捷的域名分类函数"""
    classifier = DomainClassifier(task_id, user_id, target_domain)
    return await classifier.classify_domain(domain)


def get_target_subdomains(classifications: List[DomainClassification]) -> List[str]:
    """从分类结果中获取目标子域名"""
    return [
        c.domain for c in classifications 
        if c.domain_type in [DomainType.TARGET_MAIN, DomainType.TARGET_SUBDOMAIN]
    ]


def get_high_priority_domains(classifications: List[DomainClassification]) -> List[str]:
    """从分类结果中获取高优先级域名"""
    return [
        c.domain for c in classifications 
        if c.priority.value >= DomainPriority.HIGH.value
    ]
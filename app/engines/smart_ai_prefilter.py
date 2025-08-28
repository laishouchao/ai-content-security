import os
import re
import time
import hashlib
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from PIL import Image
import imagehash
import io

from app.core.logging import TaskLogger
from app.engines.content_capture import ContentResult
from app.models.task import ViolationRecord, RiskLevel


class ImageAnalyzer:
    """图像快速分析器"""
    
    def __init__(self):
        self.suspicious_colors = [
            (255, 192, 203),  # 粉色
            (255, 20, 147),   # 深粉色
            (255, 105, 180),  # 热粉色
            (139, 69, 19),    # 棕色（可能的皮肤色）
        ]
    
    def analyze_image_features(self, image_path: str) -> Dict[str, Any]:
        """分析图像特征"""
        try:
            with Image.open(image_path) as img:
                # 基本信息
                width, height = img.size
                file_size = os.path.getsize(image_path)
                
                # 转换为RGB模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 颜色分析
                colors = img.getcolors(maxcolors=256*256*256)
                if colors:
                    dominant_color = max(colors, key=lambda x: x[0])[1]
                    color_diversity = len(colors)
                else:
                    dominant_color = (0, 0, 0)
                    color_diversity = 0
                
                # 计算图像熵（复杂度）
                entropy = self._calculate_image_entropy(img)
                
                # 检测可疑颜色占比
                suspicious_ratio = self._calculate_suspicious_color_ratio(img)
                
                return {
                    'width': width,
                    'height': height,
                    'file_size': file_size,
                    'dominant_color': dominant_color,
                    'color_diversity': color_diversity,
                    'entropy': entropy,
                    'suspicious_color_ratio': suspicious_ratio,
                    'aspect_ratio': width / height if height > 0 else 0
                }
                
        except Exception as e:
            return {
                'error': str(e),
                'width': 0,
                'height': 0,
                'file_size': 0,
                'entropy': 0,
                'suspicious_color_ratio': 0
            }
    
    def _calculate_image_entropy(self, img: Image.Image) -> float:
        """计算图像熵"""
        try:
            # 转换为灰度图
            gray = img.convert('L')
            # 获取像素值分布
            histogram = gray.histogram()
            # 计算概率分布
            total_pixels = img.width * img.height
            probabilities = [h / total_pixels for h in histogram if h > 0]
            # 计算熵
            import math
            entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)
            return entropy
        except:
            return 0.0
    
    def _calculate_suspicious_color_ratio(self, img: Image.Image) -> float:
        """计算可疑颜色占比"""
        try:
            # 降采样以提高速度
            img_small = img.resize((100, 100))
            pixels = list(img_small.getdata())
            
            suspicious_count = 0
            total_count = len(pixels)
            
            for pixel in pixels:
                r, g, b = pixel[:3]  # 确保RGB值
                for sus_r, sus_g, sus_b in self.suspicious_colors:
                    # 颜色相似度检测
                    if abs(r - sus_r) < 30 and abs(g - sus_g) < 30 and abs(b - sus_b) < 30:
                        suspicious_count += 1
                        break
            
            return suspicious_count / total_count if total_count > 0 else 0.0
            
        except:
            return 0.0


class URLAnalyzer:
    """URL快速分析器"""
    
    def __init__(self):
        # 高风险关键词
        self.high_risk_keywords = [
            'porn', 'sex', 'adult', 'nude', 'naked', 'xxx', 'nsfw',
            'gambling', 'casino', 'bet', 'poker', 'lottery',
            'phishing', 'scam', 'fraud', 'fake', 'hack', 'crack',
            'malware', 'virus', 'trojan', 'spam',
            'drug', 'pharmacy', 'pills', 'medicine',
            'loan', 'credit', 'debt', 'money', 'finance',
            'download', 'torrent', 'pirate', 'warez'
        ]
        
        # 中等风险关键词
        self.medium_risk_keywords = [
            'login', 'admin', 'auth', 'register', 'signup',
            'api', 'webhook', 'callback', 'redirect',
            'upload', 'file', 'image', 'photo',
            'search', 'query', 'submit', 'form',
            'user', 'profile', 'account', 'settings'
        ]
        
        # 可疑TLD
        self.suspicious_tlds = [
            '.tk', '.ml', '.ga', '.cf', '.gq',  # 免费域名
            '.cc', '.tv', '.me', '.to',         # 常被滥用
            '.click', '.download', '.racing',   # 可疑后缀
        ]
        
        # 可疑模式
        self.suspicious_patterns = [
            r'[0-9]{4,}',           # 大量连续数字
            r'[a-z]-[a-z]-[a-z]',   # 短横线分隔单词
            r'^[a-z]{20,}',         # 超长域名
            r'[0-9]+[a-z]+[0-9]+',  # 数字字母混合
            r'(.)\\1{3,}',           # 连续重复字符
        ]
    
    def analyze_url_risk(self, url: str) -> Dict[str, Any]:
        """分析URL风险"""
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            query = parsed.query.lower()
            full_url = url.lower()
            
            # 关键词检测
            high_risk_score = self._check_keywords(full_url, self.high_risk_keywords)
            medium_risk_score = self._check_keywords(full_url, self.medium_risk_keywords)
            
            # TLD检测
            tld_risk = any(domain.endswith(tld) for tld in self.suspicious_tlds)
            
            # 模式检测
            pattern_risk = self._check_patterns(domain)
            
            # 路径深度
            path_depth = len([p for p in path.split('/') if p])
            
            # 查询参数数量
            query_params = len(query.split('&')) if query else 0
            
            # 域名长度
            domain_length = len(domain)
            
            # 计算综合风险分数
            risk_score = (
                high_risk_score * 0.4 +
                medium_risk_score * 0.2 +
                (1.0 if tld_risk else 0.0) * 0.2 +
                pattern_risk * 0.1 +
                min(path_depth / 10, 1.0) * 0.05 +
                min(query_params / 20, 1.0) * 0.05
            )
            
            return {
                'risk_score': min(risk_score, 1.0),
                'high_risk_keywords': high_risk_score,
                'medium_risk_keywords': medium_risk_score,
                'suspicious_tld': tld_risk,
                'pattern_risk': pattern_risk,
                'domain_length': domain_length,
                'path_depth': path_depth,
                'query_params': query_params,
                'needs_ai_analysis': risk_score > 0.3
            }
            
        except Exception as e:
            return {
                'risk_score': 0.5,  # 解析失败，中等风险
                'error': str(e),
                'needs_ai_analysis': True
            }
    
    def _check_keywords(self, text: str, keywords: List[str]) -> float:
        """检查关键词匹配"""
        matches = 0
        for keyword in keywords:
            if keyword in text:
                matches += 1
        
        return min(matches / len(keywords), 1.0) if keywords else 0.0
    
    def _check_patterns(self, domain: str) -> float:
        """检查可疑模式"""
        matches = 0
        for pattern in self.suspicious_patterns:
            if re.search(pattern, domain):
                matches += 1
        
        return min(matches / len(self.suspicious_patterns), 1.0) if self.suspicious_patterns else 0.0


class ContentAnalyzer:
    """内容快速分析器"""
    
    def __init__(self):
        self.suspicious_titles = [
            'error', '404', '403', '500', 'not found',
            'access denied', 'forbidden', 'unauthorized',
            'coming soon', 'under construction', 'maintenance',
            'login required', 'sign in', 'authentication'
        ]
    
    def analyze_content_features(self, content_result: ContentResult) -> Dict[str, Any]:
        """分析内容特征"""
        features = {
            'has_title': False,
            'title_suspicious': False,
            'content_length': 0,
            'has_forms': False,
            'has_scripts': False,
            'has_iframes': False,
            'response_time': getattr(content_result, 'response_time', 0),
            'status_code': getattr(content_result, 'status_code', 200)
        }
        
        # 标题分析
        if hasattr(content_result, 'page_title') and content_result.page_title:
            features['has_title'] = True
            title_lower = content_result.page_title.lower()
            features['title_suspicious'] = any(
                sus in title_lower for sus in self.suspicious_titles
            )
        
        # 内容长度
        if hasattr(content_result, 'content_length'):
            features['content_length'] = content_result.content_length
        
        # HTML特征检测（如果有HTML内容）
        if hasattr(content_result, 'html_content') and content_result.html_content:
            html = content_result.html_content.lower()
            features['has_forms'] = '<form' in html
            features['has_scripts'] = '<script' in html
            features['has_iframes'] = '<iframe' in html
        
        return features


class SmartAIPrefilter:
    """智能AI预筛选器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        self.image_analyzer = ImageAnalyzer()
        self.url_analyzer = URLAnalyzer()
        self.content_analyzer = ContentAnalyzer()
        
        # 缓存机制
        self.analysis_cache = {}  # phash -> result
        self.cache_hits = 0
        self.cache_misses = 0
        
        # 统计信息
        self.total_processed = 0
        self.ai_calls_made = 0
        self.ai_calls_skipped = 0
    
    async def should_analyze_with_ai(self, content_result: ContentResult) -> Tuple[bool, str, Dict[str, Any]]:
        """
        判断是否需要AI分析
        返回: (是否需要AI分析, 原因, 详细分析结果)
        """
        self.total_processed += 1
        
        try:
            # 基础检查
            if not content_result.screenshot_path or not os.path.exists(content_result.screenshot_path):
                self.ai_calls_skipped += 1
                return False, "no_screenshot", {}
            
            # 文件大小检查
            file_size = os.path.getsize(content_result.screenshot_path)
            if file_size < 1024:  # 小于1KB
                self.ai_calls_skipped += 1
                return False, "screenshot_too_small", {'file_size': file_size}
            
            # 计算perceptual hash用于去重
            phash = await self._calculate_perceptual_hash(content_result.screenshot_path)
            if phash in self.analysis_cache:
                self.cache_hits += 1
                cached_result = self.analysis_cache[phash]
                return cached_result['needs_ai'], f"cache_hit_{cached_result['reason']}", cached_result
            
            self.cache_misses += 1
            
            # 图像特征分析
            image_features = self.image_analyzer.analyze_image_features(content_result.screenshot_path)
            
            # URL风险分析
            url_features = self.url_analyzer.analyze_url_risk(content_result.url)
            
            # 内容特征分析
            content_features = self.content_analyzer.analyze_content_features(content_result)
            
            # 综合决策
            decision_result = self._make_analysis_decision(
                image_features, url_features, content_features
            )
            
            # 缓存结果
            cache_entry = {
                'needs_ai': decision_result['needs_ai'],
                'reason': decision_result['reason'],
                'image_features': image_features,
                'url_features': url_features,
                'content_features': content_features,
                'decision_score': decision_result['decision_score']
            }
            self.analysis_cache[phash] = cache_entry
            
            if decision_result['needs_ai']:
                self.ai_calls_made += 1
            else:
                self.ai_calls_skipped += 1
            
            return decision_result['needs_ai'], decision_result['reason'], cache_entry
            
        except Exception as e:
            self.logger.warning(f"预筛选分析失败: {e}")
            # 出错时保守处理，进行AI分析
            self.ai_calls_made += 1
            return True, f"prefilter_error_{str(e)}", {}
    
    async def _calculate_perceptual_hash(self, image_path: str) -> str:
        """计算感知哈希"""
        try:
            with Image.open(image_path) as img:
                # 使用imagehash库计算perceptual hash
                phash = imagehash.phash(img)
                return str(phash)
        except Exception:
            # 如果计算失败，使用文件MD5作为备选
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()[:16]
    
    def _make_analysis_decision(
        self, 
        image_features: Dict[str, Any], 
        url_features: Dict[str, Any], 
        content_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """综合决策是否需要AI分析"""
        
        # 强制AI分析的条件
        force_ai_conditions = [
            # URL高风险
            url_features.get('risk_score', 0) > 0.6,
            # 图像可疑颜色占比高
            image_features.get('suspicious_color_ratio', 0) > 0.15,
            # 高风险关键词
            url_features.get('high_risk_keywords', 0) > 0.3,
            # 状态码异常
            content_features.get('status_code', 200) >= 400,
        ]
        
        # 跳过AI分析的条件
        skip_ai_conditions = [
            # 图像太简单（低熵值）
            image_features.get('entropy', 0) < 2.0,
            # 文件太小
            image_features.get('file_size', 0) < 5120,  # 5KB
            # 标题明显无害
            content_features.get('title_suspicious', False) is False and content_features.get('has_title', False),
            # 响应时间过长（可能是超时页面）
            content_features.get('response_time', 0) > 30,
        ]
        
        # 计算决策分数
        force_score = sum(1 for condition in force_ai_conditions if condition)
        skip_score = sum(1 for condition in skip_ai_conditions if condition)
        
        # URL风险分数权重
        url_risk_weight = url_features.get('risk_score', 0) * 2
        
        # 图像复杂度权重
        image_complexity = min(image_features.get('entropy', 0) / 8.0, 1.0)
        
        # 最终决策分数
        decision_score = (
            force_score * 0.4 +
            url_risk_weight * 0.3 +
            image_complexity * 0.2 -
            skip_score * 0.1
        )
        
        # 决策阈值
        threshold = 0.5
        needs_ai = decision_score > threshold
        
        # 生成决策原因
        if needs_ai:
            reasons = []
            if force_score > 0:
                reasons.append(f"force_conditions_{force_score}")
            if url_risk_weight > 0.3:
                reasons.append(f"high_url_risk_{url_risk_weight:.2f}")
            if image_complexity > 0.5:
                reasons.append(f"complex_image_{image_complexity:.2f}")
            reason = "_".join(reasons) if reasons else "threshold_exceeded"
        else:
            reasons = []
            if skip_score > 0:
                reasons.append(f"skip_conditions_{skip_score}")
            if decision_score <= threshold:
                reasons.append(f"low_score_{decision_score:.2f}")
            reason = "_".join(reasons) if reasons else "below_threshold"
        
        return {
            'needs_ai': needs_ai,
            'reason': reason,
            'decision_score': decision_score,
            'force_score': force_score,
            'skip_score': skip_score,
            'url_risk_weight': url_risk_weight,
            'image_complexity': image_complexity
        }
    
    def get_efficiency_stats(self) -> Dict[str, Any]:
        """获取效率统计"""
        return {
            'total_processed': self.total_processed,
            'ai_calls_made': self.ai_calls_made,
            'ai_calls_skipped': self.ai_calls_skipped,
            'ai_skip_rate': f"{(self.ai_calls_skipped / self.total_processed * 100):.1f}%" if self.total_processed > 0 else "0%",
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': f"{(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%" if (self.cache_hits + self.cache_misses) > 0 else "0%",
            'cost_reduction': f"{(self.ai_calls_skipped / self.total_processed * 100):.1f}%" if self.total_processed > 0 else "0%"
        }
    
    async def clear_cache(self):
        """清理缓存"""
        self.analysis_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.logger.info("AI预筛选缓存已清理")
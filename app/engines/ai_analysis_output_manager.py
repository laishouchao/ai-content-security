"""
AI分析输出管理器
管理AI分析过程中的输入输出临时文件
"""

import json
import time
import base64
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from app.core.logging import TaskLogger


class AIAnalysisOutputManager:
    """AI分析输出管理器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 设置输出目录
        self.output_dir = Path("storage/ai_analysis_output") / task_id
        self.input_dir = Path("storage/temp_analysis") / task_id
        
        # 创建目录
        for directory in [self.output_dir, self.input_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def prepare_analysis_input(
        self, 
        domain: str, 
        screenshot_path: str, 
        source_code_path: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """准备AI分析输入文件"""
        
        safe_domain = self._make_safe_filename(domain)
        input_filename = f"{safe_domain}_input_{int(time.time())}.json"
        input_file_path = self.input_dir / input_filename
        
        try:
            # 准备基础数据
            input_data = {
                'domain': domain,
                'screenshot_path': screenshot_path,
                'source_code_path': source_code_path,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'task_id': self.task_id
            }
            
            # 读取截图并转换为Base64
            if Path(screenshot_path).exists():
                with open(screenshot_path, 'rb') as f:
                    screenshot_base64 = base64.b64encode(f.read()).decode('utf-8')
                    input_data['screenshot_base64'] = screenshot_base64
                    input_data['screenshot_size'] = str(len(screenshot_base64))
            else:
                input_data['screenshot_base64'] = ""
                input_data['screenshot_error'] = f"截图文件不存在: {screenshot_path}"
            
            # 读取源码
            if Path(source_code_path).exists():
                with open(source_code_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                    input_data['source_code'] = source_code[:10000]  # 限制长度
                    input_data['source_code_length'] = str(len(source_code))
                    
                    # 提取关键信息
                    input_data.update(self._extract_source_code_info(source_code))
            else:
                input_data['source_code'] = ""
                input_data['source_code_error'] = f"源码文件不存在: {source_code_path}"
            
            # 添加额外数据
            if additional_data:
                input_data.update(additional_data)
            
            # 保存输入文件
            with open(input_file_path, 'w', encoding='utf-8') as f:
                json.dump(input_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"准备AI分析输入文件: {input_file_path}")
            return str(input_file_path)
            
        except Exception as e:
            self.logger.error(f"准备AI分析输入文件失败: {e}")
            raise
    
    async def save_analysis_output(
        self, 
        domain: str, 
        analysis_result: Dict[str, Any],
        ai_raw_response: str,
        input_file_path: str
    ) -> str:
        """保存AI分析输出文件"""
        
        safe_domain = self._make_safe_filename(domain)
        output_filename = f"{safe_domain}_output_{int(time.time())}.json"
        output_file_path = self.output_dir / output_filename
        
        try:
            output_data = {
                'domain': domain,
                'analysis_result': analysis_result,
                'ai_raw_response': ai_raw_response,
                'input_file_path': input_file_path,
                'analysis_completed_at': datetime.utcnow().isoformat(),
                'task_id': self.task_id,
                'processing_info': {
                    'has_violation': analysis_result.get('has_violation', False),
                    'confidence_score': analysis_result.get('confidence_score', 0.0),
                    'risk_level': analysis_result.get('risk_level', 'unknown'),
                    'violation_types': analysis_result.get('violation_types', [])
                }
            }
            
            # 保存输出文件
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"保存AI分析输出文件: {output_file_path}")
            return str(output_file_path)
            
        except Exception as e:
            self.logger.error(f"保存AI分析输出文件失败: {e}")
            raise
    
    def _extract_source_code_info(self, source_code: str) -> Dict[str, Any]:
        """从源码中提取关键信息"""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(source_code, 'html.parser')
            
            # 提取页面标题
            title = soup.find('title')
            page_title = title.get_text().strip() if title else ""
            
            # 提取meta描述
            meta_description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                try:
                    # 使用getattr安全访问属性
                    attrs = getattr(meta_desc, 'attrs', {})
                    meta_description = str(attrs.get('content', '')).strip()
                except (AttributeError, KeyError, TypeError):
                    meta_description = ""
            
            # 提取关键词
            keywords = []
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords:
                try:
                    # 使用getattr安全访问属性
                    attrs = getattr(meta_keywords, 'attrs', {})
                    content = str(attrs.get('content', ''))
                    if content:
                        keywords = [k.strip() for k in content.split(',')]
                except (AttributeError, KeyError, TypeError):
                    keywords = []
            
            # 提取页面文本内容
            text_content = soup.get_text()
            clean_text = ' '.join(text_content.split())[:3000]  # 清理空白并限制长度
            
            # 统计信息
            stats = {
                'total_links': str(len(soup.find_all('a'))),
                'total_images': str(len(soup.find_all('img'))),
                'total_scripts': str(len(soup.find_all('script'))),
                'total_forms': str(len(soup.find_all('form'))),
                'has_css': len(soup.find_all('link', rel='stylesheet')) > 0 or len(soup.find_all('style')) > 0
            }
            
            return {
                'page_title': page_title,
                'page_description': meta_description,
                'keywords': keywords,
                'text_content': clean_text,
                'page_stats': stats
            }
            
        except Exception as e:
            self.logger.warning(f"提取源码信息失败: {e}")
            return {
                'page_title': "",
                'page_description': "",
                'keywords': [],
                'text_content': "",
                'page_stats': {}
            }
    
    def get_domain_input_files(self, domain: str) -> List[str]:
        """获取域名的所有输入文件"""
        safe_domain = self._make_safe_filename(domain)
        pattern = f"{safe_domain}_input_*.json"
        
        input_files = list(self.input_dir.glob(pattern))
        return [str(f) for f in sorted(input_files, key=lambda x: x.stat().st_mtime, reverse=True)]
    
    def get_domain_output_files(self, domain: str) -> List[str]:
        """获取域名的所有输出文件"""
        safe_domain = self._make_safe_filename(domain)
        pattern = f"{safe_domain}_output_*.json"
        
        output_files = list(self.output_dir.glob(pattern))
        return [str(f) for f in sorted(output_files, key=lambda x: x.stat().st_mtime, reverse=True)]
    
    def load_latest_analysis_result(self, domain: str) -> Optional[Dict[str, Any]]:
        """加载域名的最新分析结果"""
        output_files = self.get_domain_output_files(domain)
        
        if not output_files:
            return None
        
        try:
            with open(output_files[0], 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载分析结果失败: {e}")
            return None
    
    def load_input_data(self, input_file_path: str) -> Optional[Dict[str, Any]]:
        """加载输入数据"""
        try:
            with open(input_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载输入数据失败: {e}")
            return None
    
    async def cleanup_old_files(self, keep_days: int = 7):
        """清理旧文件"""
        cutoff_time = time.time() - (keep_days * 24 * 3600)
        
        cleaned_count = 0
        
        # 清理输入文件
        for file_path in self.input_dir.glob("*.json"):
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                cleaned_count += 1
        
        # 清理输出文件
        for file_path in self.output_dir.glob("*.json"):
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.logger.info(f"清理了 {cleaned_count} 个旧文件")
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """获取分析摘要"""
        try:
            input_files = list(self.input_dir.glob("*.json"))
            output_files = list(self.output_dir.glob("*.json"))
            
            # 统计违规情况
            violation_count = 0
            total_analyzed = 0
            
            for output_file in output_files:
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        total_analyzed += 1
                        if data.get('processing_info', {}).get('has_violation', False):
                            violation_count += 1
                except:
                    continue
            
            return {
                'total_input_files': len(input_files),
                'total_output_files': len(output_files),
                'total_analyzed': total_analyzed,
                'violation_count': violation_count,
                'violation_rate': round(violation_count / total_analyzed * 100, 2) if total_analyzed > 0 else 0,
                'input_dir_size_mb': self._get_directory_size(self.input_dir),
                'output_dir_size_mb': self._get_directory_size(self.output_dir)
            }
            
        except Exception as e:
            self.logger.error(f"获取分析摘要失败: {e}")
            return {}
    
    def _get_directory_size(self, directory: Path) -> float:
        """获取目录大小(MB)"""
        try:
            total_size = sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())
            return round(total_size / 1024 / 1024, 2)
        except:
            return 0.0
    
    def _make_safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        safe_filename = ''.join(c if c in safe_chars else '_' for c in filename)
        
        if len(safe_filename) > 50:
            safe_filename = safe_filename[:50]
        
        return safe_filename or "unknown"
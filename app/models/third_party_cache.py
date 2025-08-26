from sqlalchemy import Column, String, DateTime, Boolean, Integer, Float, Text, JSON
from datetime import datetime
import uuid

from app.core.database import Base


class ThirdPartyDomainCache(Base):
    """第三方域名缓存库模型"""
    __tablename__ = "third_party_domain_cache"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 域名信息
    domain = Column(String(255), nullable=False, index=True, unique=True)
    domain_type = Column(String(50), nullable=False)
    
    # 风险信息
    risk_level = Column(String(20), nullable=False)
    
    # 内容信息
    page_title = Column(String(500), nullable=True)
    page_description = Column(Text, nullable=True)
    
    # AI分析结果缓存
    cached_analysis_result = Column(JSON, nullable=True)
    
    # 统计信息
    identification_count = Column(Integer, default=1, nullable=False)  # 识别次数
    last_analysis_result = Column(JSON, nullable=True)  # 最后一次分析结果
    
    # 时间戳
    first_identified_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 首次识别时间
    last_identified_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 最后识别时间
    last_analyzed_at = Column(DateTime, nullable=True)  # 最后分析时间
    
    def __repr__(self):
        return f"<ThirdPartyDomainCache(id={self.id}, domain={self.domain}, type={self.domain_type})>"
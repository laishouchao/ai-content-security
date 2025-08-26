<template>
  <div class="domain-detail">
    <div class="page-header">
      <el-button @click="$router.back()" type="text">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <h2>域名详情 - {{ domain.domain }}</h2>
      <div class="header-actions">
        <el-button @click="reanalyzeDomain" :loading="reanalyzing">
          重新分析
        </el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <!-- 域名基本信息 -->
      <el-col :span="24">
        <el-card v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>基本信息</span>
              <div class="header-actions">
                <el-tag :type="getRiskType(domain.risk_level)" size="small">
                  {{ getRiskText(domain.risk_level) }}风险
                </el-tag>
                <el-tag type="info" size="small">
                  {{ getDomainTypeText(domain.domain_type) }}
                </el-tag>
              </div>
            </div>
          </template>
          
          <el-descriptions :column="3" border>
            <el-descriptions-item label="域名">
              <span class="domain-name">{{ domain.domain }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="域名类型">
              {{ getDomainTypeText(domain.domain_type) }}
            </el-descriptions-item>
            <el-descriptions-item label="风险等级">
              <el-tag :type="getRiskType(domain.risk_level)" size="small">
                {{ getRiskText(domain.risk_level) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="识别时间">
              {{ domain.created_at ? formatTime(domain.created_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="分析时间">
              {{ domain.analyzed_at ? formatTime(domain.analyzed_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="分析状态">
              <el-tag :type="domain.is_analyzed ? 'success' : 'info'" size="small">
                {{ domain.is_analyzed ? '已分析' : '未分析' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="所属任务">
              <el-button type="text" @click="goToTask">
                {{ domain.task_id }}
              </el-button>
            </el-descriptions-item>
            <el-descriptions-item label="发现位置">
              <span class="found-url">{{ domain.found_on_url }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="违规状态">
              <el-tag :type="domain.has_violations ? 'danger' : 'success'" size="small">
                {{ domain.has_violations ? '有违规' : '无违规' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 页面信息 -->
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>页面信息</span>
          </template>
          
          <div class="page-info">
            <h4>页面标题</h4>
            <p>{{ domain.page_title || '无标题' }}</p>
            
            <h4>页面描述</h4>
            <p>{{ domain.page_description || '无描述' }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 违规记录 -->
    <el-row style="margin-top: 20px;" v-if="domain.has_violations && domain.violations && domain.violations.length > 0">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>违规记录 ({{ domain.violations.length }})</span>
          </template>
          
          <div class="violations-list">
            <div 
              v-for="violation in domain.violations" 
              :key="violation.id"
              class="violation-item"
            >
              <div class="violation-header">
                <span class="violation-title">{{ violation.title }}</span>
                <el-tag :type="getRiskType(violation.risk_level)" size="small">
                  {{ getRiskText(violation.risk_level) }}风险
                </el-tag>
              </div>
              
              <p class="violation-desc">{{ violation.description }}</p>
              
              <div class="violation-details">
                <el-row :gutter="20">
                  <el-col :span="8">
                    <div class="detail-item">
                      <span class="label">违规类型:</span>
                      <span>{{ getViolationTypeText(violation.violation_type) }}</span>
                    </div>
                  </el-col>
                  <el-col :span="8">
                    <div class="detail-item">
                      <span class="label">置信度:</span>
                      <span>{{ Math.round(violation.confidence_score * 100) }}%</span>
                    </div>
                  </el-col>
                  <el-col :span="8">
                    <div class="detail-item">
                      <span class="label">检测时间:</span>
                      <span>{{ formatTime(violation.detected_at) }}</span>
                    </div>
                  </el-col>
                </el-row>
              </div>
              
              <div class="violation-content" v-if="violation.content_snippet">
                <h4>内容片段</h4>
                <pre class="content-snippet">{{ violation.content_snippet }}</pre>
              </div>
              
              <div class="violation-evidence" v-if="violation.evidence && violation.evidence.length > 0">
                <h4>证据</h4>
                <ul>
                  <li v-for="(evidence, index) in violation.evidence" :key="index">
                    {{ evidence }}
                  </li>
                </ul>
              </div>
              
              <div class="violation-recommendations" v-if="violation.recommendations && violation.recommendations.length > 0">
                <h4>建议</h4>
                <ul>
                  <li v-for="(recommendation, index) in violation.recommendations" :key="index">
                    {{ recommendation }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- AI分析结果 -->
    <el-row style="margin-top: 20px;" v-if="domain.is_analyzed">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>AI分析结果</span>
          </template>
          
          <div class="ai-analysis-result">
            <el-alert
              v-if="domain.analysis_error"
              :title="domain.analysis_error"
              type="error"
              show-icon
            />
            
            <div v-else>
              <p>该域名已完成AI分析，分析结果已保存。</p>
              <div v-if="domain.violations && domain.violations.length > 0" class="analysis-summary">
                <h4>分析摘要</h4>
                <p>检测到 {{ domain.violations.length }} 个违规项，建议立即处理。</p>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { domainAPI } from '@/api'
import type { ThirdPartyDomain } from '@/types/api'
import { formatTime } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const domainId = route.params.id

// 响应式状态
const loading = ref(false)
const reanalyzing = ref(false)
const domain = ref<ThirdPartyDomain>({} as ThirdPartyDomain)

// 方法
const getDomainTypeText = (type: string) => {
  const typeMap: Record<string, string> = {
    cdn: 'CDN',
    analytics: '分析服务',
    advertising: '广告服务',
    social: '社交媒体',
    api: 'API服务',
    payment: '支付服务',
    security: '安全服务',
    maps: '地图服务',
    unknown: '未知类型'
  }
  return typeMap[type] || type
}

const getRiskType = (risk: string): 'info' | 'success' | 'warning' | 'danger' => {
  const riskMap: Record<string, 'info' | 'success' | 'warning' | 'danger'> = {
    low: 'success',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return riskMap[risk] || 'info'
}

const getRiskText = (risk: string) => {
  const riskMap: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '严重风险'
  }
  return riskMap[risk] || risk
}

const getViolationTypeText = (type: string) => {
  const typeMap: Record<string, string> = {
    'nsfw': '色情内容',
    'violence': '暴力内容',
    'gambling': '赌博内容',
    'scam': '诈骗信息',
    'malware': '恶意软件',
    'hate_speech': '仇恨言论',
    'copyright': '侵权内容',
    'other': '其他违规'
  }
  return typeMap[type] || type
}

const fetchDomainDetail = async () => {
  try {
    loading.value = true
    
    const response = await domainAPI.getDomain(domainId as string)
    
    if (response.data.success) {
      domain.value = response.data.data as ThirdPartyDomain
      
      // 添加违规状态计算属性
      domain.value.has_violations = domain.value.violations && domain.value.violations.length > 0
    }
  } catch (error) {
    console.error('获取域名详情失败:', error)
    ElMessage.error('获取域名详情失败')
  } finally {
    loading.value = false
  }
}

const reanalyzeDomain = async () => {
  try {
    reanalyzing.value = true
    
    await ElMessageBox.confirm(
      '确定要重新分析此域名吗？这将清除现有的分析结果并重新进行AI分析。',
      '确认重新分析',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const response = await domainAPI.reanalyzeDomain(domainId as string)
    
    if (response.data.success) {
      ElMessage.success('域名已重置，等待重新分析')
      fetchDomainDetail()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('重新分析域名失败:', error)
      ElMessage.error('重新分析域名失败')
    }
  } finally {
    reanalyzing.value = false
  }
}

const goToTask = () => {
  router.push(`/tasks/${domain.value.task_id}`)
}

// 生命周期
onMounted(() => {
  if (domainId) {
    fetchDomainDetail()
  }
})
</script>

<style scoped>
.domain-detail {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  gap: 12px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  flex: 1;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.domain-name {
  font-weight: 500;
  color: #409eff;
  font-size: 16px;
}

.found-url {
  color: #666;
  font-size: 14px;
}

.page-info h4 {
  margin: 16px 0 8px 0;
  font-size: 16px;
  color: #333;
}

.page-info p {
  margin: 0;
  color: #666;
  line-height: 1.5;
}

.violations-list {
  max-height: 600px;
  overflow-y: auto;
}

.violation-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 16px;
  margin-bottom: 16px;
}

.violation-item:last-child {
  margin-bottom: 0;
}

.violation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.violation-title {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.violation-desc {
  margin: 0 0 16px 0;
  color: #666;
  line-height: 1.5;
}

.violation-details {
  margin-bottom: 16px;
}

.detail-item {
  display: flex;
  gap: 8px;
}

.detail-item .label {
  font-weight: 500;
  color: #333;
}

.violation-content h4,
.violation-evidence h4,
.violation-recommendations h4 {
  margin: 16px 0 8px 0;
  font-size: 14px;
  color: #333;
}

.content-snippet {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.4;
}

.violation-evidence ul,
.violation-recommendations ul {
  margin: 0;
  padding-left: 20px;
}

.violation-evidence li,
.violation-recommendations li {
  margin-bottom: 4px;
  color: #666;
}

.ai-analysis-result {
  min-height: 100px;
}

.analysis-summary {
  margin-top: 16px;
  padding: 12px;
  background: #fef0f0;
  border-radius: 4px;
  border: 1px solid #fde2e2;
}

.analysis-summary h4 {
  margin: 0 0 8px 0;
  color: #333;
}

.analysis-summary p {
  margin: 0;
  color: #666;
}
</style>
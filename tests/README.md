# 测试目录结构说明

本目录包含项目的所有测试相关文件，按功能分类组织。

## 目录结构

```
tests/
├── README.md                      # 本文档
├── test_api.py                    # API接口测试
├── test_database_optimizer.py     # 数据库优化器测试
├── test_domain_list_service.py    # 域名列表服务测试
├── test_integration.py            # 集成测试
├── test_integration_new.py        # 新集成测试
├── test_performance.py            # 性能测试
├── test_task_api.py               # 任务API测试
├── debug/                         # 调试相关脚本
│   └── debug_ai_analysis.py       # AI分析诊断脚本
├── manual/                        # 手动测试脚本
│   └── test_discovery_engine.py   # 域名发现引擎测试
└── tools/                         # 开发工具脚本
    ├── cache_manager_cli.py        # 缓存管理命令行工具
    ├── cleanup_duplicate_screenshots.py  # 重复截图清理工具
    ├── db_manager.py               # 数据库管理工具
    └── start_all_services.py       # 服务启动工具
```

## 测试类型

### 单元测试 (Unit Tests)
- `test_api.py` - API接口单元测试
- `test_database_optimizer.py` - 数据库优化器单元测试
- `test_domain_list_service.py` - 域名列表服务单元测试
- `test_task_api.py` - 任务API单元测试

### 集成测试 (Integration Tests)
- `test_integration.py` - 完整的集成测试
- `test_integration_new.py` - 新版集成测试

### 性能测试 (Performance Tests)
- `test_performance.py` - 系统性能测试

### 手动测试 (Manual Tests)
- `manual/test_discovery_engine.py` - 域名发现引擎手动测试

### 调试工具 (Debug Tools)
- `debug/debug_ai_analysis.py` - AI分析问题诊断工具

### 开发工具 (Development Tools)
- `tools/cache_manager_cli.py` - 缓存管理命令行工具
- `tools/cleanup_duplicate_screenshots.py` - 重复截图清理工具
- `tools/db_manager.py` - 数据库管理工具
- `tools/start_all_services.py` - 一键启动所有服务

## 运行测试

### 运行单元测试
```bash
# 运行所有单元测试
python -m pytest tests/test_*.py

# 运行特定测试
python -m pytest tests/test_api.py
```

### 运行集成测试
```bash
# 运行集成测试
python -m pytest tests/test_integration.py
```

### 运行性能测试
```bash
# 运行性能测试
python -m pytest tests/test_performance.py
```

### 运行手动测试
```bash
# 域名发现引擎测试
python tests/manual/test_discovery_engine.py
```

### 使用调试工具
```bash
# AI分析诊断
python tests/debug/debug_ai_analysis.py
```

### 使用开发工具
```bash
# 缓存管理
python tests/tools/cache_manager_cli.py --help

# 数据库管理
python tests/tools/db_manager.py --help

# 启动所有服务
python tests/tools/start_all_services.py

# 清理重复截图
python tests/tools/cleanup_duplicate_screenshots.py --help
```

## 注意事项

1. **环境配置**: 运行测试前请确保已正确配置环境变量和数据库连接
2. **依赖关系**: 某些测试可能需要运行的Redis和PostgreSQL服务
3. **测试数据**: 集成测试会创建测试数据，请使用测试数据库
4. **路径问题**: 所有脚本已正确配置项目根目录路径，可以从任意位置运行

## 贡献指南

添加新测试时，请遵循以下规则：

1. **单元测试**: 直接放在 `tests/` 根目录，命名为 `test_*.py`
2. **手动测试**: 放在 `tests/manual/` 目录
3. **调试工具**: 放在 `tests/debug/` 目录
4. **开发工具**: 放在 `tests/tools/` 目录
5. **更新文档**: 添加新文件后请更新此README文档
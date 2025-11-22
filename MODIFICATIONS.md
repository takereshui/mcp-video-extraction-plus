# MCP Video Extraction - 语音识别服务集成修改说明

## 概述

本次修改将项目的语音识别服务从仅支持 **Whisper（本地模型）** 扩展为支持三种方式：

1. **Whisper** - OpenAI 的本地语音识别模型（原有）
2. **JianYing (CapCut)** - 字节跳动简影/CapCut 的在线语音识别服务
3. **Bcut (B站剪辑)** - 哔哩哔哩剪辑的在线语音识别服务

## 新增文件

### 核心 ASR 模块

| 文件 | 说明 |
|------|------|
| `src/mcp_video_service/services/asr_data.py` | ASR 数据结构定义（ASRDataSeg、ASRData） |
| `src/mcp_video_service/services/status.py` | ASR 任务状态枚举 |
| `src/mcp_video_service/services/base_asr.py` | 基础 ASR 抽象类，所有 ASR 实现的父类 |
| `src/mcp_video_service/services/jianying_asr.py` | 简影（CapCut）语音识别实现 |
| `src/mcp_video_service/services/bcut_asr.py` | B站剪辑（Bcut）语音识别实现 |
| `src/mcp_video_service/services/__init__.py` | Services 包初始化文件 |

## 修改的文件

### 1. `src/mcp_video_service/services/video_service.py`

**主要改动：**

- 添加 ASR 提供者配置支持（`asr_provider`）
- 修改 `__init__` 方法，支持从配置文件读取 ASR 提供者选择
- 新增 `_create_asr_instance()` 方法，根据配置创建对应的 ASR 实例
- 修改 `extract_text()` 方法，支持多种 ASR 提供者
  - 如果选择 Whisper，使用本地模型
  - 如果选择 JianYing 或 Bcut，调用在线 API
- 添加导入语句，支持相对导入和绝对导入兼容

**配置参数：**

```python
self.config = {
    'asr': {
        'provider': 'whisper',  # 可选: whisper, jianying, bcut
        'use_cache': False,
        'need_word_time_stamp': False,
    },
    'jianying': {
        'start_time': 0,
        'end_time': 6000,
    },
    # ... 其他配置
}
```

### 2. `config.yaml`

**新增配置项：**

```yaml
# ASR（自动语音识别）提供者配置
asr:
  provider: "whisper"  # 可选: whisper, jianying, bcut
  use_cache: false
  need_word_time_stamp: false

# JianYing (CapCut) 语音识别配置
jianying:
  start_time: 0      # 音频开始时间（毫秒）
  end_time: 6000     # 音频结束时间（毫秒）

# Bcut (B站剪辑) 语音识别配置
# 暂无特殊配置，使用默认值
```

## 使用方式

### 1. 使用 Whisper（本地模型，默认）

```python
from mcp_video_service.services.video_service import VideoService

service = VideoService(config_path='config.yaml')
# config.yaml 中设置: asr.provider = "whisper"

text = await service.extract_text('audio.mp3')
```

### 2. 使用 JianYing（在线服务）

```python
# 修改 config.yaml
# asr:
#   provider: "jianying"
#   use_cache: false
#   need_word_time_stamp: false
# jianying:
#   start_time: 0
#   end_time: 6000

service = VideoService(config_path='config.yaml')
text = await service.extract_text('audio.mp3')
```

### 3. 使用 Bcut（在线服务）

```python
# 修改 config.yaml
# asr:
#   provider: "bcut"
#   use_cache: true
#   need_word_time_stamp: false

service = VideoService(config_path='config.yaml')
text = await service.extract_text('audio.mp3')
```

### 4. 通过环境变量配置

```bash
# 使用 JianYing
export ASR_PROVIDER=jianying
export ASR_USE_CACHE=false
export JIANYING_START_TIME=0
export JIANYING_END_TIME=6000

# 使用 Bcut
export ASR_PROVIDER=bcut
export ASR_USE_CACHE=true
```

## 架构设计

### 类继承关系

```
BaseASR (抽象基类)
├── JianYingASR
├── BcutASR
└── VideoService (使用 Whisper 时直接调用 whisper.load_model)
```

### BaseASR 的主要特性

- **统一接口**：所有 ASR 实现都继承自 `BaseASR`
- **缓存支持**：通过 CRC32 校验和生成缓存键
- **速率限制**：内置速率限制机制，防止 API 过载
- **进度回调**：支持异步进度回调函数
- **错误处理**：统一的错误处理和日志记录

## 数据结构

### ASRDataSeg（分段数据）

```python
@dataclass
class ASRDataSeg:
    text: str          # 分段文本
    start_time: float  # 开始时间（毫秒）
    end_time: float    # 结束时间（毫秒）
```

### ASRData（完整数据）

```python
@dataclass
class ASRData:
    text: str                    # 完整文本
    segments: List[ASRDataSeg]   # 分段列表
```

## 状态管理

ASR 任务的状态通过 `ASRStatus` 枚举管理：

| 状态 | 进度 | 说明 |
|------|------|------|
| UPLOADING | 20 | 上传中 |
| SUBMITTING | 40 | 提交中 |
| QUERYING_RESULT | 60 | 查询结果中 |
| CREATING_TASK | 40 | 创建任务中 |
| TRANSCRIBING | 60 | 转录中 |
| COMPLETED | 100 | 已完成 |

## 导入兼容性

所有新增的 ASR 模块都支持**相对导入**和**绝对导入**的双重兼容：

```python
# 相对导入（在包内使用）
from .asr_data import ASRDataSeg
from .base_asr import BaseASR

# 绝对导入（直接加载模块时使用）
from asr_data import ASRDataSeg
from base_asr import BaseASR
```

这确保了模块在不同的导入场景下都能正常工作。

## 依赖项

### 新增依赖

- `requests` - 用于 HTTP 请求（JianYing 和 Bcut API）

### 现有依赖

- `yt-dlp` - 视频下载
- `whisper` - 本地语音识别（仅在使用 Whisper 时需要）
- `pyyaml` - 配置文件解析

## 环境变量支持

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `ASR_PROVIDER` | ASR 提供者 | whisper |
| `ASR_USE_CACHE` | 是否使用缓存 | false |
| `ASR_WORD_TIME_STAMP` | 是否需要词级时间戳 | false |
| `JIANYING_START_TIME` | JianYing 音频开始时间 | 0 |
| `JIANYING_END_TIME` | JianYing 音频结束时间 | 6000 |
| `WHISPER_MODEL` | Whisper 模型大小 | base |
| `WHISPER_LANGUAGE` | Whisper 语言 | auto |

## 向后兼容性

本次修改完全向后兼容：

- 默认 ASR 提供者为 `whisper`，保持原有行为
- 原有的 `extract_text()` 接口保持不变
- 所有新增功能都是可选的

## 测试验证

所有新增模块已通过以下验证：

- ✓ Python 语法检查
- ✓ 模块导入测试
- ✓ 类继承关系验证
- ✓ 配置文件解析测试

## 后续扩展

该架构支持轻松添加新的 ASR 提供者：

1. 创建新类继承 `BaseASR`
2. 实现 `_run()` 和 `_make_segments()` 方法
3. 在 `VideoService._create_asr_instance()` 中添加条件分支
4. 在 `config.yaml` 中添加相应配置项

## 许可证

保持原项目许可证不变。

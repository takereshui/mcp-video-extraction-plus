# MCP Video Extraction Server - AI Agent Guide

## Project Overview

MCP Video Extraction is a Model Context Protocol (MCP) server that provides text extraction capabilities from various video platforms and audio files. The project supports multiple ASR (Automatic Speech Recognition) providers including Whisper (local), JianYing (CapCut), and Bcut (Bilibili), enabling high-quality speech recognition from platforms like YouTube, Bilibili, TikTok, Instagram, Twitter/X, Facebook, Vimeo, and more.

## Technology Stack

- **Language**: Python 3.10+
- **Core Framework**: Model Context Protocol (MCP) Python SDK
- **Build System**: Hatchling (PEP 517)
- **Package Manager**: uv (recommended)
- **Key Dependencies**:
  - `openai-whisper` - Local speech recognition
  - `yt-dlp` - Video/audio downloading
  - `mcp[cli]` - MCP server implementation
  - `pydantic` - Data validation
  - `pyyaml` - Configuration management

## Project Structure

```
src/mcp_video_service/
├── __init__.py              # Main entry point with MCP tools
├── __main__.py              # CLI entry point
└── services/                # Core service implementations
    ├── __init__.py
    ├── asr_data.py          # ASR data structures (ASRData, ASRDataSeg)
    ├── base_asr.py          # Abstract base class for ASR providers
    ├── bcut_asr.py          # Bilibili Bcut ASR implementation
    ├── jianying_asr.py      # JianYing/CapCut ASR implementation
    ├── status.py            # ASR task status enums
    └── video_service.py     # Main video service orchestrator
```

## Core Architecture

### MCP Server Implementation
The server exposes four main tools through the MCP protocol:
1. `video_download` - Download videos from supported platforms
2. `audio_download` - Extract audio from videos
3. `audio_extract` - Extract text from audio/video files
4. `process_video` - Complete pipeline: download + transcribe

### ASR Provider Architecture
- **BaseASR**: Abstract base class providing unified interface, caching, rate limiting
- **Whisper**: Local model implementation (default)
- **JianYingASR**: ByteDance CapCut online service integration
- **BcutASR**: Bilibili Bcut online service integration

### Configuration System
Flexible configuration through:
- `config.yaml` file (primary)
- Environment variables (override)
- Runtime parameters

## Build and Test Commands

### Development Setup
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install FFmpeg (required dependency)
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg
# Windows: choco install ffmpeg
```

### Running the Server
```bash
# Using uvx (recommended)
uvx mcp-video-extraction

# Or install and run
uv pip install mcp-video-extraction
mcp-video-extraction
```

### Development Scripts
```bash
# Development script (scripts/dev.sh)
./scripts/dev.sh
```

## Configuration

### Primary Configuration (config.yaml)
```yaml
asr:
  provider: "whisper"  # Options: whisper, jianying, bcut
  use_cache: false
  need_word_time_stamp: false

whisper:
  model: "base"  # Options: tiny, base, small, medium, large
  language: "auto"

jianying:
  start_time: 0
  end_time: 6000

youtube:
  download:
    audio_format: "mp3"
    audio_quality: "192"

storage:
  temp_dir: "/tmp/mcp-video"
```

### Environment Variables
- `ASR_PROVIDER` - Override ASR provider selection
- `ASR_USE_CACHE` - Enable/disable caching
- `WHISPER_MODEL` - Whisper model size
- `WHISPER_LANGUAGE` - Language setting
- `TEMP_DIR` - Temporary storage location

## Code Style Guidelines

### Import Patterns
All service modules support both relative and absolute imports for compatibility:
```python
try:
    from .base_asr import BaseASR
    from .asr_data import ASRData
except ImportError:
    from base_asr import BaseASR
    from asr_data import ASRData
```

### Error Handling
- Use specific exception types with descriptive messages
- Log errors with appropriate context
- Clean up resources in finally blocks

### Async Patterns
- All download operations are async with 5-minute timeout
- Use `asyncio.wait_for()` for timeout handling
- Implement proper cleanup of temporary files

## Testing Strategy

### Current Validation
- ✓ Python syntax validation
- ✓ Module import testing
- ✓ Class inheritance verification
- ✓ Configuration file parsing

### Manual Testing
```python
# Test Whisper (default)
service = VideoService()
text = await service.extract_text('audio.mp3')

# Test JianYing
# Set ASR_PROVIDER=jianying in config or environment
service = VideoService()
text = await service.extract_text('audio.mp3')

# Test Bcut
# Set ASR_PROVIDER=bcut in config or environment
service = VideoService()
text = await service.extract_text('audio.mp3')
```

## Deployment Process

### MCP Client Integration
Add to Claude/Cursor settings:
```json
"mcpServers": {
  "video-extraction": {
    "command": "uvx",
    "args": ["mcp-video-extraction"]
  }
}
```

### System Requirements
- **Minimum**: 8GB RAM, FFmpeg installed
- **Recommended**: NVIDIA GPU + CUDA for Whisper acceleration
- **Storage**: Sufficient space for model download (~1GB) and temp files

### Performance Optimization
1. **GPU Acceleration**: Install CUDA and cuDNN for faster Whisper processing
2. **Model Selection**: Choose appropriate Whisper model (tiny/base/small/medium/large)
3. **Storage**: Use SSD for temporary file operations
4. **Network**: Stable connection for video downloads

## Security Considerations

### File Handling
- Unique filename generation using UUID to prevent conflicts
- Automatic cleanup of temporary files after processing
- Restricted to configured temp directory

### Network Security
- SSL certificate verification disabled for yt-dlp (configurable)
- Rate limiting for ASR API calls
- Timeout controls for all network operations

### Data Protection
- Local Whisper processing keeps data private
- Online ASR services (JianYing/Bcut) require file upload
- No persistent storage of processed content

## Development Notes

### Adding New ASR Providers
1. Create new class inheriting from `BaseASR`
2. Implement `_run()` and `_make_segments()` methods
3. Add provider selection in `VideoService._create_asr_instance()`
4. Update configuration schema in `config.yaml`
5. Add environment variable support

### Extending Video Platforms
The project uses yt-dlp which supports 1000+ sites. No code changes needed for new platforms - they're automatically supported through yt-dlp updates.

### Debugging Tips
- Enable debug logging: Set logging level to DEBUG
- Check temp directory for failed downloads
- Monitor network requests for ASR API issues
- Verify FFmpeg installation for audio processing

## Common Issues and Solutions

### First Run Issues
- **Whisper Model Download**: ~1GB download on first use, may take 10+ minutes
- **FFmpeg Missing**: Install system FFmpeg package
- **Permission Errors**: Ensure write access to temp directory

### Performance Issues
- **Slow Processing**: Use smaller Whisper model or GPU acceleration
- **Memory Usage**: Monitor RAM usage with large models
- **Network Timeouts**: Adjust timeout settings in configuration

### Integration Issues
- **MCP Client Connection**: Verify uvx installation and PATH
- **Audio Format Issues**: Check FFmpeg codec support
- **Platform Support**: Verify yt-dlp supports target platform
import os
import tempfile
import yt_dlp
import logging
import uuid
from typing import Optional, Literal
import yaml

try:
    from .base_asr import BaseASR
    from .jianying_asr import JianYingASR
    from .bcut_asr import BcutASR
except ImportError:
    from base_asr import BaseASR
    from jianying_asr import JianYingASR
    from bcut_asr import BcutASR

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('video_service')

class VideoLogger:
    """自定义的 yt-dlp 日志处理器"""
    def debug(self, msg):
        # 兼容 youtube-dl，debug 和 info 都会传递到这里
        # 可以通过 '[debug] ' 前缀区分
        if msg.startswith('[debug] '):
            return
        # 非调试信息传递给 info 处理
        self.info(msg)

    def info(self, msg):
        # 不输出普通信息
        pass

    def warning(self, msg):
        # 不输出警告信息
        pass

    def error(self, msg):
        # 只输出错误信息到我们的日志系统
        logger.error(msg)

def download_hook(d):
    """下载进度回调函数"""
    if d['status'] == 'finished':
        logger.info('下载完成，开始后处理...')

class VideoService:
    """视频服务，负责下载视频的音频部分并进行文字转换处理"""    
      
    def _generate_unique_filename(self, ext: str) -> str:
        """生成唯一的文件名
        
        Args:
            ext: 文件扩展名（不包含点号）
            
        Returns:
            str: 生成的唯一文件名（格式：uuid.扩展名）
        """
        return f"{uuid.uuid4()}.{ext}"
    
          
   
        
    def __init__(self, config_path: str='config.yaml'):
        # 尝试从YAML文件加载配置，如果失败则使用默认值
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                file_config = yaml.safe_load(file) or {}
        except (FileNotFoundError, yaml.YAMLError):
            file_config = {}
            logger.info(f"配置文件 {config_path} 不存在或解析失败，使用默认配置")
            
        # 获取配置值的辅助函数
        def get_config_value(keys, default):
            """从嵌套字典中安全获取值"""
            value = file_config
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            return value
        
            
        # 从环境变量读取配置，如果没有则从文件配置读取，最后使用默认值        
        self.config = {
            'asr': {
                'provider': os.getenv('ASR_PROVIDER') or get_config_value(['asr', 'provider'], 'whisper'),
                'use_cache': os.getenv('ASR_USE_CACHE', 'false').lower() == 'true' or get_config_value(['asr', 'use_cache'], False),
                'need_word_time_stamp': os.getenv('ASR_WORD_TIME_STAMP', 'false').lower() == 'true' or get_config_value(['asr', 'need_word_time_stamp'], False),
            },
            'whisper': {
                'model': os.getenv('WHISPER_MODEL') or get_config_value(['whisper', 'model'], 'base'),
                'language': os.getenv('WHISPER_LANGUAGE') or get_config_value(['whisper', 'language'], 'auto')
            },
            'jianying': {
                'start_time': float(os.getenv('JIANYING_START_TIME', '0') or get_config_value(['jianying', 'start_time'], 0)),
                'end_time': float(os.getenv('JIANYING_END_TIME', '6000') or get_config_value(['jianying', 'end_time'], 6000)),
            },
            'youtube': {
                'download': {
                    # 'format': os.getenv('YOUTUBE_FORMAT') or get_config_value(['youtube', 'download', 'format'], 'bestaudio'),
                    'audio_format': os.getenv('AUDIO_FORMAT') or get_config_value(['youtube', 'download', 'audio_format'], 'mp3'),
                    'audio_quality': os.getenv('AUDIO_QUALITY') or get_config_value(['youtube', 'download', 'audio_quality'], '192')
                }
            },
            'storage': {
                'temp_dir': os.getenv('TEMP_DIR') or get_config_value(['storage', 'temp_dir'], '/tmp/mcp-video')
            }
        }
        
        # 初始化 ASR 提供者
        self.asr_provider = self.config['asr']['provider'].lower()
        
        # 如果使用 Whisper，则加载模型
        if self.asr_provider == 'whisper':
            import whisper
            logger.info("初始化 Whisper 模型...")
            self.whisper_model = whisper.load_model(self.config['whisper']['model'])
        else:
            self.whisper_model = None
        
        # 通用下载选项
        self.common_opts = {
            'logger': VideoLogger(),  # 使用自定义日志处理器
            'progress_hooks': [download_hook],  # 使用下载进度回调
            'retries': int(os.getenv('DOWNLOAD_RETRIES', '3')),  # 重试次数
            'fragment_retries': int(os.getenv('FRAGMENT_RETRIES', '5')),  # 分片下载重试次数
            'socket_timeout': int(os.getenv('SOCKET_TIMEOUT', '60')),  # 网络超时时间（秒）
            'nocheckcertificate': True,  # 忽略 SSL 证书验证
            'ignoreerrors': True,  # 忽略可恢复的错误
            'no_warnings': True,  # 减少输出
        }
        
        # 音频下载配置
        self.audio_opts = {
            **self.common_opts,
            'format': 'bestaudio',  # 优先最佳音频，如果没有则选择最佳视频
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.config['youtube']['download']['audio_format'],
                'preferredquality': self.config['youtube']['download']['audio_quality'],
            }],
            'outtmpl': os.path.join(self.config['storage']['temp_dir'], '%(id)s.%(ext)s'),  # 直接下载到目标目录
        }
        
        # 视频下载配置
        self.video_opts = {
            **self.common_opts,
            'format': 'bestvideo+bestaudio/best',  # 优先选择最佳视频+音频，如果没有则选择最佳
            'outtmpl': os.path.join(self.config['storage']['temp_dir'], '%(id)s.%(ext)s'),  # 直接下载到目标目录
        }

        # 确保临时目录存在
        os.makedirs(self.config['storage']['temp_dir'], exist_ok=True)

    async def download(self, url: str, opts: dict) -> Optional[str]:
        import asyncio
        
        def _download_sync():
            """同步下载函数，在线程池中执行"""
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    logger.info(f"开始下载: {url}")
                    # 获取视频信息
                    info = ydl.extract_info(url, download=True)
                    
                    if info is None:
                        raise Exception("无法获取视频信息，可能是格式不支持或网络问题")
                    
                    # 获取下载后的文件路径
                    temp_path = ydl.prepare_filename(info)                
                    logger.debug(f"temp_path: {temp_path}")
                    
                    # 检查是否为音频下载（有后处理器）
                    if 'postprocessors' in opts and any(pp.get('key') == 'FFmpegExtractAudio' for pp in opts['postprocessors']):
                        # 音频下载：后处理后的文件路径
                        audio_ext = opts['postprocessors'][0]['preferredcodec']
                        final_path = os.path.splitext(temp_path)[0] + '.' + audio_ext
                        logger.debug(f"期望的音频文件路径: {final_path}")
                        
                        # 检查多种可能的文件路径
                        possible_paths = [
                            final_path,  # 标准路径
                            temp_path,   # 原始下载路径（如果后处理失败）
                        ]
                        
                        actual_file = None
                        for path in possible_paths:
                            logger.debug(f"检查文件: {path}")
                            if os.path.exists(path):
                                actual_file = path
                                break
                        
                        if actual_file:
                            # 使用唯一文件名重命名
                            new_filename = self._generate_unique_filename(audio_ext)
                            new_path = os.path.join(self.config['storage']['temp_dir'], new_filename)
                            os.rename(actual_file, new_path)
                            logger.info(f"音频下载完成: {new_path}")
                            return new_path
                        else:
                            # 列出目录中的所有文件进行调试
                            dir_path = os.path.dirname(temp_path) if os.path.dirname(temp_path) else '.'
                            files = os.listdir(dir_path)
                            logger.error(f"音频文件不存在。目录 {dir_path} 中的文件: {files}")
                            return None
                    else:
                        # 视频下载：直接使用下载的文件
                        file_ext = os.path.splitext(temp_path)[1][1:]  # 获取扩展名（不含点号）                
                        new_filename = self._generate_unique_filename(file_ext)                
                        new_path = os.path.join(self.config['storage']['temp_dir'], new_filename)
                        logger.debug(f"new_path: {new_path}")
                        
                        # 重命名文件
                        if os.path.exists(temp_path):
                            os.rename(temp_path, new_path)
                            logger.info(f"视频下载完成: {new_path}")
                            return new_path
                        else:
                            logger.error(f"视频文件不存在: {temp_path}")
                            return None
            except Exception as e:
                logger.error(f"下载失败: {str(e)}")
                raise Exception(f"下载视频失败: {str(e)}")
        
        try:
            # 在线程池中执行下载，避免阻塞事件循环，设置超时
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _download_sync),
                timeout=300  # 5分钟超时
            )
            return result
        except asyncio.TimeoutError:
            raise Exception("下载超时（5分钟），请尝试较短的视频或检查网络连接")
        except Exception as e:
            raise Exception(f"下载视频失败: {str(e)}")

    async def download_video(self, url: str) -> Optional[str]:            
        """
        从各种视频平台下载完整视频。支持的平台包括但不限于：
        - YouTube
        - Bilibili
        - TikTok
        - Instagram
        - Twitter/X
        - Facebook
        - Vimeo
        - Dailymotion
        
        完整的支持平台列表请参考：
        https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md
        
        Args:
            url: 视频平台的URL
            
        Returns:
            str: 下载的视频文件路径
            
        Raises:
            Exception: 当下载失败时抛出异常
        """
        return await self.download(url, self.video_opts)
        
    async def download_audio(self, url: str) -> Optional[str]:
        """
        从各种视频平台下载音频。支持的平台包括但不限于：
        - YouTube
        - Bilibili
        - TikTok
        - Instagram
        - Twitter/X
        - Facebook
        - Vimeo
        - Dailymotion
        - SoundCloud
        
        完整的支持平台列表请参考：
        https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md
        
        Args:
            url: 视频平台的URL
            
        Returns:
            str: 下载的音频文件路径(MP3格式)
            
        Raises:
            Exception: 当下载失败时抛出异常
        """
        return await self.download(url, self.audio_opts)
    
    def _create_asr_instance(self, audio_path: str) -> BaseASR:
        """创建 ASR 实例
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            BaseASR: ASR 实例
            
        Raises:
            ValueError: 当 ASR 提供者不支持时
        """
        if self.asr_provider == 'whisper':
            # Whisper 本地模型不需要创建实例，直接使用
            return None
        elif self.asr_provider == 'jianying':
            return JianYingASR(
                audio_path,
                use_cache=self.config['asr']['use_cache'],
                need_word_time_stamp=self.config['asr']['need_word_time_stamp'],
                start_time=self.config['jianying']['start_time'],
                end_time=self.config['jianying']['end_time'],
            )
        elif self.asr_provider == 'bcut':
            return BcutASR(
                audio_path,
                use_cache=self.config['asr']['use_cache'],
                need_word_time_stamp=self.config['asr']['need_word_time_stamp'],
            )
        else:
            raise ValueError(f"不支持的 ASR 提供者: {self.asr_provider}")
                   
    async def extract_text(self, audio_path: str) -> str:
        """
        从音频文件中提取文字
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            str: 提取的文字内容
            
        Raises:
            Exception: 当文件不存在或处理失败时
        """
        try:
            if not os.path.exists(audio_path):
                raise Exception(f"音频文件不存在: {audio_path}")

            if self.asr_provider == 'whisper':
                # 使用 Whisper 本地模型
                logger.info(f"使用 Whisper 模型进行语音识别: {audio_path}")
                result = self.whisper_model.transcribe(
                    audio_path,
                    language=None if self.config['whisper']['language'] == 'auto' else self.config['whisper']['language']
                )
                return result["text"]
            else:
                # 使用在线 ASR 服务
                logger.info(f"使用 {self.asr_provider} 进行语音识别: {audio_path}")
                asr_instance = self._create_asr_instance(audio_path)
                asr_data = asr_instance.run()
                return asr_data.text

        except Exception as e:
            raise Exception(f"文字提取失败: {str(e)}")

    async def cleanup(self, audio_path: str):
        """清理临时音频文件"""
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as e:
            logger.error(f"清理音频文件失败: {str(e)}")

    async def process_video(self, url: str) -> str:
        """
        处理视频：下载音频并提取文字
        
        Args:
            url: 视频 URL
            
        Returns:
            str: 提取的文字内容
            
        Raises:
            Exception: 当处理失败时
        """
        try:
            # 下载音频
            audio_path = await self.download_audio(url)
            if not audio_path:
                raise Exception("音频下载失败")
            
            logger.debug(f"音频文件路径: {audio_path}")

            try:
                # 提取文字
                return await self.extract_text(audio_path)
            finally:
                # 清理临时文件
                await self.cleanup(audio_path)

        except Exception as e:
            raise Exception(f"视频处理失败: {str(e)}")

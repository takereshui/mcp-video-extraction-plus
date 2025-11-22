import hashlib
import logging
import os
import time
import binascii
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Union

try:
    from .asr_data import ASRData, ASRDataSeg
except ImportError:
    from asr_data import ASRData, ASRDataSeg

logger = logging.getLogger(__name__)


class BaseASR(ABC):
    """基础 ASR 类，所有 ASR 实现都应继承此类"""

    # 速率限制配置
    RATE_LIMIT_CALLS = 10  # 每个时间窗口的最大调用次数
    RATE_LIMIT_PERIOD = 60  # 时间窗口（秒）

    def __init__(self, audio_path: Union[str, bytes], use_cache: bool = False):
        """
        初始化 ASR 实例

        Args:
            audio_path: 音频文件路径或音频二进制数据
            use_cache: 是否使用缓存
        """
        self.audio_path = audio_path
        self.use_cache = use_cache
        self.file_binary = self._load_audio_file()
        self.crc32_hex = self._calculate_crc32()
        self._last_call_time = 0
        self._call_count = 0

    def _load_audio_file(self) -> bytes:
        """加载音频文件"""
        if isinstance(self.audio_path, bytes):
            return self.audio_path
        elif isinstance(self.audio_path, str):
            if not os.path.exists(self.audio_path):
                raise FileNotFoundError(f"音频文件不存在: {self.audio_path}")
            with open(self.audio_path, "rb") as f:
                return f.read()
        else:
            raise TypeError("audio_path 必须是文件路径或二进制数据")

    def _calculate_crc32(self) -> str:
        """计算文件的 CRC32 校验和"""
        # 使用binascii计算CRC32，确保与AWS S3兼容
        crc32_value = binascii.crc32(self.file_binary) & 0xFFFFFFFF
        return f"{crc32_value:08x}"

    @staticmethod
    def _crc32_table():
        """生成 CRC32 查找表"""
        table = []
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
            table.append(crc)
        return table

    _crc32_table = _crc32_table()

    def _check_rate_limit(self):
        """检查速率限制"""
        current_time = time.time()
        if current_time - self._last_call_time > self.RATE_LIMIT_PERIOD:
            self._last_call_time = current_time
            self._call_count = 0

        if self._call_count >= self.RATE_LIMIT_CALLS:
            sleep_time = self.RATE_LIMIT_PERIOD - (current_time - self._last_call_time)
            if sleep_time > 0:
                logger.warning(f"触发速率限制，等待 {sleep_time:.1f} 秒")
                time.sleep(sleep_time)
                self._last_call_time = time.time()
                self._call_count = 0

        self._call_count += 1

    def run(
        self, callback: Optional[Callable[[int, str], None]] = None, **kwargs: Any
    ) -> ASRData:
        """
        运行 ASR 任务

        Args:
            callback: 进度回调函数，接收 (progress: int, message: str)
            **kwargs: 其他参数

        Returns:
            ASRData: 识别结果
        """
        resp_data = self._run(callback, **kwargs)
        segments = self._make_segments(resp_data)
        text = "\n".join([seg.text for seg in segments])
        return ASRData(text=text, segments=segments)

    @abstractmethod
    def _run(
        self, callback: Optional[Callable[[int, str], None]] = None, **kwargs: Any
    ) -> dict:
        """
        执行 ASR 任务的具体实现

        Args:
            callback: 进度回调函数
            **kwargs: 其他参数

        Returns:
            dict: API 返回的原始数据
        """
        pass

    @abstractmethod
    def _make_segments(self, resp_data: dict) -> List[ASRDataSeg]:
        """
        从 API 响应中提取分段数据

        Args:
            resp_data: API 返回的原始数据

        Returns:
            List[ASRDataSeg]: 分段列表
        """
        pass

    def _get_key(self) -> str:
        """获取缓存键"""
        return f"{self.__class__.__name__}-{self.crc32_hex}"

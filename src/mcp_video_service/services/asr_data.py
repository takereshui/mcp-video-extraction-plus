from dataclasses import dataclass
from typing import List


@dataclass
class ASRDataSeg:
    """ASR 数据段"""
    text: str
    start_time: float
    end_time: float


@dataclass
class ASRData:
    """ASR 数据"""
    text: str
    segments: List[ASRDataSeg]

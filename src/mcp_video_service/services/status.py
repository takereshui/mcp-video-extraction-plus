from enum import Enum


class ASRStatus(Enum):
    """ASR 任务状态"""
    UPLOADING = (20, "上传中")
    SUBMITTING = (40, "提交中")
    QUERYING_RESULT = (60, "查询结果中")
    CREATING_TASK = (40, "创建任务中")
    TRANSCRIBING = (60, "转录中")
    COMPLETED = (100, "已完成")

    def __init__(self, progress: int, message: str):
        self.progress = progress
        self.message = message

    def callback_tuple(self):
        """返回回调函数所需的元组"""
        return (self.progress, self.message)

    def with_progress(self, progress: int):
        """返回指定进度的元组"""
        return (progress, self.message)

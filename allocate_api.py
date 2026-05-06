import random
import os


def _load_api_keys():
    keys = os.environ.get("DASHSCOPE_API_KEYS", "")
    return [key.strip() for key in keys.split(",") if key.strip()]


api_key = _load_api_keys()

class APIKeyManager:
    def __init__(self):
        # 存储所有的 API 密钥
        self.api_keys = api_key
        # 记录每个 API 密钥的使用次数
        self.usage_count = {key: 0 for key in self.api_keys}
    
    def get_api_key(self):
        if not self.api_keys:
            raise RuntimeError("DASHSCOPE_API_KEYS is not configured")
        # 找到使用次数最少的密钥
        min_key = min(self.usage_count, key=self.usage_count.get)
        # 增加该密钥的使用次数
        self.usage_count[min_key] += 1
        return min_key


# 实例化类-整个应用周期中运行
api_key_manager = APIKeyManager()


# 为用户分配api
def choice_api():
    return api_key_manager.get_api_key()

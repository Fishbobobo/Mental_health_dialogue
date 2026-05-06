from aip import AipSpeech
from error import SpeechError
import os


# ######################语音识别###################
# 百度语音识别的AIP参数
BAIDU_APP_ID = os.environ.get("BAIDU_APP_ID", "")
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY", "")

client = AipSpeech(BAIDU_APP_ID, BAIDU_API_KEY, BAIDU_SECRET_KEY) # 初始化AipSpeech客户端（百度语音识别的客户端类，用于与百度语音服务进行交互）

# 语音识别函数------需要加异常处理
def speechrecognize(file):
    try:
        data = open(file, 'rb').read() # 打开音频文件并读取为二进制文件
        # print(data)
        # print("读取文件")
        # 文件 文件格式 采样频率 PID语音种类
        result = client.asr(data, 'wav', 16000, {"dev_id": 1537}) # 执行语音识别，指定音频文件格式为'wav'，音频的采样率为16000HZ，1537为设备ID
        # print(result)
        # 返回示例
        # {"corpus_no":"6433214037620997779","err_msg":"success.","err_no":0,"result":["北京科技馆，"],"sn":"371191073711497849365"}
        return result["result"][0] # result是一个字典，key是"result"，value是识别出来的文本，即result["result"]，是个只有一项的列表，用[0]把列表转为字符串。
    except Exception as e:
        raise SpeechError("语音识别出错")
    
def main():
    speechrecognize("C:/Users/15270/Desktop/7_20240913000456_tmp_735eafd820dad033076d4ec6cb0dd3e8.wav")

# 添加入口点
if __name__ == "__main__":
    main()



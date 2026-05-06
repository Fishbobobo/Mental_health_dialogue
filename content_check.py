import requests
import json
import http.client
import ssl
import certifi

class TextContentCheck:
    def __init__(self, appid, secret, jscode):
        self.appid = appid
        self.secret = secret
        self.jscode = jscode
        self.access_token = self.get_access_token()
        print("打印jscode", jscode)
        self.openid = self.get_openid()
        print("打印openid", self.openid)

    def get_access_token(self):
        """获取微信小程序的 access_token"""
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.appid}&secret={self.secret}"
        response = requests.get(url)
        data = response.json()
        if 'access_token' in data:
            return data['access_token']
        else:
            raise Exception(f"Error getting access token: {data}")
        
    def get_openid(self):
        """通过 jscode 获取用户的 openid"""
        url = f"https://api.weixin.qq.com/sns/jscode2session?appid={self.appid}&secret={self.secret}&js_code={self.jscode}&grant_type=authorization_code"
        response = requests.get(url)
        data = response.json()
        if 'openid' in data:
            return data['openid']
        else:
            raise Exception(f"Error getting openid: {data}")

    def msg_sec_check(self, content):
        # """进行文本安全检测"""
        # 确保内容是字符串并进行 UTF-8 编码
        # content = content.encode('utf-8')
        # print(type(content))
        params = {
            "openid": self.openid,  # 用户的唯一标识符，可以根据需要选择是否提供
            "scene": 3, # 场景为社交日志场景枚举值（0 资料；1 评论；2 论坛；3 社交日志）
            "version": 2, # 微信API版本号
            "content": content #用户输入的文本内容，用于安全检测
        }
        # 将参数params字典转换为JSON字符串，并设置ensure_ascii=False以确保非ASCII字符（如中文）能够正确输出
        # 并编码为UTF-8的字节数据，作为HTTP请求的正文部分发送给微信API。
        json_data = json.dumps(params, ensure_ascii=False).encode('utf-8')

        # 创建 HTTPS 连接，使用 certifi 提供的证书验证
        context = ssl.create_default_context(cafile=certifi.where())

        # 发送请求
        conn = http.client.HTTPSConnection("api.weixin.qq.com", context=context)
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Content-Length': str(len(json_data))
        }
        url = f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={self.access_token}"

        conn.request("POST", url, body=json_data, headers=headers)

        # 获取响应
        response = conn.getresponse()
        response_data = response.read().decode('utf-8')  # 解码为 UTF-8 字符串
        conn.close()

        # 解析响应
        json_object = json.loads(response_data)
        result = json_object.get("result", {})
        suggest = result.get("suggest")
        label = result.get("label")

        print("suggest", suggest)
        print(json.dumps(json_object, ensure_ascii=False))  # 输出完整响应

        # 检查 label 值，label 为 100 认为内容安全
        return label == 100

        # url = f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={self.access_token}"
        # response = requests.post(url, json=params)
        # # 打印请求的编码
        # print("Request encoding:", response.request.body.decode('utf-8'))  # 尝试解码请求体
        # json_object = response.json()
        # result = json_object.get("result", {})
        # suggest = result.get("suggest")
        # label = result.get("label")
        # print("suggest", suggest)
        # print(json.dumps(json_object, ensure_ascii=False))  # 输出完整响应
        # # 检查label值，label为100认为内容安全
        # return label==100
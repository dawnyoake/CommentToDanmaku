import requests
import json
import os
from dotenv import load_dotenv
from pathlib import Path
from hashlib import md5
from QuickTable import *

from Youdao.AuthV3Util import addAuthParams

# 获取 .env 文件的绝对路径
env_path = Path(__file__).resolve().parent.parent / '.env'

# 加载环境变量
load_dotenv(env_path)

# 获取密钥
appid = os.getenv('YOUDAO_APP_ID')
appkey = os.getenv('YOUDAO_APP_KEY')
vocab_id = os.getenv('YOUDAO_APP_VOCABID')

def createRequest(src_msg) -> str:
    '''
    note: 将下列变量替换为需要请求的参数
    '''
    q = src_msg
    lang_from = 'ja'
    lang_to = 'zh-CHS'

    data = {'q': q, 'from': lang_from, 'to': lang_to, 'vocabId': vocab_id}

    addAuthParams(appid, appkey, data)

    header = {'Content-Type': 'application/x-www-form-urlencoded'}
    res = doCall('https://openapi.youdao.com/api', header, data, 'post')
    
    # 解析JSON响应
    response = json.loads(res.content)
    
    print(src_msg, ": ", response)
    # 返回翻译结果
    return response["translation"][0]


def doCall(url, header, params, method):
    if 'get' == method:
        return requests.get(url, params)
    elif 'post' == method:
        return requests.post(url, params, header)

# 网易有道智云翻译服务api调用demo
# api接口: https://openapi.youdao.com/api
# if __name__ == '__main__':
#     res = createRequest("おしゃれな色かと思ったら透けてるのww")
#     print(res)
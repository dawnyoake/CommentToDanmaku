# -*- coding: utf-8 -*-
import sys
import requests
import random
import json
import os

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from dotenv import load_dotenv
from pathlib import Path
from hashlib import md5
from QuickTable import *


# 获取 .env 文件的绝对路径
env_path = Path(__file__).resolve().parent.parent / '.env'

# 加载环境变量
load_dotenv(env_path)

# 获取密钥
appid = os.getenv('BAIDU_APP_ID')
appkey = os.getenv('BAIDU_APP_KEY')

def make_md5(s, encoding='utf-8'):
    return md5(s.encode(encoding)).hexdigest()

def createRequestBaidu(text):
    # Trim input text
    text = text.strip()
    if not text:
        return text
        
    # API endpoints
    endpoint = 'http://api.fanyi.baidu.com'
    path = '/api/trans/vip/translate'
    url = endpoint + path

    # Generate salt and sign
    salt = random.randint(32768, 65536)
    sign = make_md5(appid + text + str(salt) + appkey)

    # Build request
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    payload = {
        'appid': appid,
        'q': text,
        'from': 'jp',
        'to': 'zh',
        'salt': salt,
        'sign': sign,
        'needIntervene': 1
    }

    # Send request
    r = requests.post(url, params=payload, headers=headers)
    result = r.json()
    
    # Return translated text
    if 'error_code' in result:
        print(text, ": ", result['error_code'], ", ", result['error_msg'])
        return result['error_code']
    return result['trans_result'][0]['dst']

# Please install OpenAI SDK first: `pip3 install openai`
# -*- coding: utf-8 -*-
import sys
import os
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from hashlib import md5
# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from QuickTable import *
from functools import lru_cache
from typing import Tuple  # 新增类型注解

# 环境变量加载
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)

# 缓存目录（自动创建）
CACHE_DIR = Path(__file__).parent / 'translation_cache'
CACHE_DIR.mkdir(exist_ok=True)

# 客户端初始化
client = OpenAI(
    api_key=os.getenv('DEEPSEEK_KEY'),
    base_url="https://api.deepseek.com"
)

# 专用翻译提示词
TRANSLATION_SYSTEM_PROMPT = """你是一个专业的日译中翻译引擎，请严格遵循以下规则：
1. 保持专业但口语化的自然语气
2. 保留动漫专业术语和品牌名称
3. 保留数字和单位格式
4. 不要添加额外内容或解释
5. 处理日语特有的拟声词和语气词
6. 对长句子进行合理分段"""

def createRequestDeepSeek(text: str, use_cache: bool = True) -> Tuple[str, int]:
    """
    日语到中文翻译函数（带tokens统计）
    :param text: 需要翻译的日文文本
    :param use_cache: 是否启用本地缓存（默认开启）
    :return: (中文译文 或 错误信息, 消耗的tokens总数)
    """
    text = text.strip()
    if not text:  # 如果文本为空，直接返回
        return text
        
    # 获取翻译映射表并检查是否存在对应翻译
    translation_map = get_translation_map()
    if text in translation_map:
        return (translation_map[text], 0)
    
    # 输入验证
    if not isinstance(text, str) or len(text) == 0:
        return ("[错误] 输入文本无效", 0)
    
    text_hash = md5(text.encode('utf-8')).hexdigest()
    cache_file = CACHE_DIR / f"{text_hash}.txt"
    
    # 缓存命中时返回0 tokens消耗
    if use_cache and cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            return (f.read(), 0)
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            max_tokens=2000,
            stream=False
        )
        
        translated_text = response.choices[0].message.content.strip()
        used_tokens = response.usage.total_tokens  # 获取总tokens消耗
        
        if use_cache:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(translated_text)
                
        return (translated_text, used_tokens)
        
    except Exception as e:
        return (f"[API错误] {str(e)}", 0)  # 错误时返回0 tokens

if __name__ == "__main__":
    # 更新测试用例
    test_text = """
    ソフトウェア開発において、APIの設計は極めて重要です。
    返信なくてもね、見てるだけの方もいつもありがとうございます。
    ちょっとね、ゆったりまったりやっていこうと思うので
    """
    
    translation, tokens = createRequestDeepSeek(test_text)
    print(f"翻译结果（消耗{tokens}tokens）:\n{translation}")
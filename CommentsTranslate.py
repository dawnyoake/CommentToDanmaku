import pandas as pd
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Semaphore
import queue

from translateUtils.BaiduTranslation import createRequestBaidu
from translateUtils.DeepSeekTranslate import createRequestDeepSeek
from translateUtils.QuickTable import *

# 读取 Excel 文件
excel_path = r"E:\R-User-File\R-Project-Myself\CommentCatcher\Comment2Ass2MP4\ytbcomments\04.xlsx"

# 创建限流器和锁
rate_limiter = Semaphore(10)  # 限制最大并发数为10
lock = Lock()
error_queue = queue.Queue()

def translate_with_rate_limit(text, translation_service=1):
    # 去除文本前后的空白字符
    text = text.strip()
    if not text:  # 如果文本为空，直接返回
        return {"trans_res": text, "tokens_cost": 0}
        
    # 获取翻译映射表并检查是否存在对应翻译
    translation_map = get_translation_map()
    if text in translation_map:
        return {"trans_res": translation_map[text], "tokens_cost": 0}
    
    api_tokens_cost = 0

    if len(text) > 11:
        translation_service = 2

    try:
        with rate_limiter:  # 使用信号量控制并发
            time.sleep(0.1)  # 确保QPS不超过10
            if translation_service == 1:
                trans_res = createRequestBaidu(text)  # 调用百度翻译
            elif translation_service == 2:
                trans_res, tokens_cost = createRequestDeepSeek(text)  # 调用Deepseek API
                api_tokens_cost += tokens_cost
            else:
                raise ValueError("不支持的翻译服务")
            return {"trans_res": trans_res, "tokens_cost": api_tokens_cost}
    except Exception as e:
        error_msg = f"翻译 {text} 时出错: {e}"
        error_queue.put(error_msg)
        return {"trans_res": text, "tokens_cost": 0}

if __name__ == '__main__':

    df = pd.read_excel(excel_path)

    print("开始翻译弹幕内容...")
    # 检查已有的翻译结果,如果翻译后内容与原始内容相同则重新翻译
    total_rows = len(df)
    if '翻译后' not in df.columns:
        df['翻译后'] = None
    for idx, row in tqdm(df.iterrows(), total=total_rows, desc="检查并重新翻译"):
        if pd.isna(row['翻译后']) or row['翻译后'] == row['弹幕内容']:  # 检查翻译后列是否为空或者是否等于弹幕内容
            df.at[idx, '翻译后'] = translate_with_rate_limit(row['弹幕内容'])

    # 保存为新的 Excel 文件
    new_excel_path = r".\output\04-comment-translation.xlsx"
    df.to_excel(new_excel_path, index=False)

    print(f"翻译后的文件已保存到 {new_excel_path}")
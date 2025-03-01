import pandas as pd
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Semaphore
import queue

from translateUtils.BaiduTranslation import createRequest
from translateUtils.QuickTable import *

# 读取 Excel 文件
excel_path = r".\data\AOI-ER1_baidu_translated.xlsx"
df = pd.read_excel(excel_path)

# 创建限流器和锁
rate_limiter = Semaphore(10)  # 限制最大并发数为10
lock = Lock()
error_queue = queue.Queue()

def translate_with_rate_limit(text):
    # 去除文本前后的空白字符
    text = text.strip()
    if not text:  # 如果文本为空，直接返回
        return text
        
    # 获取翻译映射表并检查是否存在对应翻译
    translation_map = get_translation_map()
    if text in translation_map:
        return translation_map[text]
    
    try:
        with rate_limiter:  # 使用信号量控制并发
            time.sleep(0.1)  # 确保QPS不超过10
            trans_res = createRequest(text)
            return trans_res
    except Exception as e:
        error_msg = f"翻译 {text} 时出错: {e}"
        error_queue.put(error_msg)
        return text

def translate_batch(texts):
    # 创建线程池
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(tqdm(
            executor.map(translate_with_rate_limit, texts),
            total=len(texts),
            desc="翻译进度"
        ))
    
    # 输出所有错误信息
    while not error_queue.empty():
        print(error_queue.get())
        
    return results

print("开始翻译弹幕内容...")
# 检查已有的翻译结果,如果翻译后内容与原始内容相同则重新翻译
total_rows = len(df)
for idx, row in tqdm(df.iterrows(), total=total_rows, desc="检查并重新翻译"):
    if pd.notna(row['翻译后']) and row['翻译后'] == row['弹幕内容']:  # 检查翻译后内容是否与原始内容相同
        df.at[idx, '翻译后'] = translate_with_rate_limit(row['弹幕内容'])

# 保存为新的 Excel 文件
new_excel_path = r".\output\AOI-ER1_baidu_translated2.xlsx"
df.to_excel(new_excel_path, index=False)

print(f"翻译后的文件已保存到 {new_excel_path}")
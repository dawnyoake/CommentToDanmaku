import re
import pandas as pd
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Semaphore
import queue
from Translate import translate_with_rate_limit

from translateUtils.BaiduTranslation import createRequestBaidu
from translateUtils.QuickTable import *

def translate_ass(input_path, output_path):
    """
    翻译ASS字幕文件
    :param input_path: 输入ASS文件路径
    :param output_path: 输出ASS文件路径
    """
    # 读取文件
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 查找[Events]部分
    events_index = -1
    for i, line in enumerate(lines):
        if line.strip().lower() == '[events]':
            events_index = i
            break

    if events_index == -1:
        raise ValueError("ASS文件中缺少[Events]部分")

    # 检查Format行
    format_line = events_index + 1
    if not lines[format_line].lower().startswith('format:'):
        raise ValueError("Format行格式异常")

    # 预处理：获取所有需要处理的行索引
    process_indices = []
    for idx in range(events_index + 2, len(lines)):
        if lines[idx].strip().startswith('Dialogue:'):
            process_indices.append(idx)

    total_lines = len(process_indices)  # 准确的总进度

    all_token_cost = 0

    # 使用tqdm显示进度条
    with tqdm(total=total_lines, desc="翻译进度", unit="line") as pbar:
        for idx in process_indices:
            line = lines[idx].strip()

            # 高级分割逻辑：保留原始结构
            parts = re.split(r',\s*(?![^{}]*\})', line, maxsplit=9)
            if len(parts) < 10:
                continue

            # 提取需要翻译的文本（保留特效标签）
            original_text = parts[9].split('}')[1] if '}' in parts[9] else parts[9]

            # 调用翻译函数
            result = translate_with_rate_limit(original_text, 2)
            translated = result['trans_res']
            all_token_cost += result['tokens_cost']

            # 保留原始特效标签
            if '\\N' in original_text:
                translated = translated.replace('\n', '\\N')
            if '}' in parts[9]:
                translated_text = parts[9].split('}', 1)[0] + '}' + translated
            else:
                translated_text = translated

            # 重构完整行
            parts[9] = translated_text
            lines[idx] = ','.join(parts) + '\n'

            # 更新进度条
            pbar.update(1)
            pbar.set_postfix({
                '当前行': f"{idx + 1}/{len(lines)}",
                '原文': original_text[:20] + '...' if len(original_text) > 20 else original_text,
                '译文': translated[:20] + '...' if len(translated) > 20 else translated
            })

    # 写入翻译后的文件
    with open(output_path, 'w', encoding='utf-8-sig') as f:  # 保持BOM头
        f.writelines(lines)

    print('总消耗tokens = ', all_token_cost)

if __name__ == '__main__':
    translate_ass(r"E:\R-User-File\R-Project-Myself\CommentCatcher\kirinuki\03\trans\03-cut1.ass", r"E:\R-User-File\R-Project-Myself\CommentCatcher\kirinuki\03\trans\03-cut1-dstrans.ass")
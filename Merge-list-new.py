import os
import json
import subprocess
import time
from dataclasses import dataclass
import concurrent.futures
from typing import List, Dict
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import pandas as pd
from tqdm import tqdm

# --------------------------
# 配置类（集中管理所有参数）
# --------------------------
@dataclass
class AppConfig:
    # 输入输出路径
    video_path: str = r"E:\R-User-File\R-Project-Myself\CommentCatcher\kirinuki\04\04-MASK.mp4"
    excel_path: str = r"E:\R-User-File\R-Project-Myself\CommentCatcher\kirinuki\04\04-comment-translation.xlsx"
    output_path: str = r"E:\R-User-File\R-Project-Myself\CommentCatcher\kirinuki\04\04-MASK-DANMU-TEST-17.mp4"

    main_ass_path : str = r"trans04-audio-align.ass"
    
    # 视频参数
    video_resolution: tuple = (1920, 1080)  # 视频分辨率，根据实际情况调整
    
    # 弹幕框参数
    comment_block_capacity = 12
    comment_font_size = 29
    comment_row_space = 42
    comment_block_start_x = 1620
    comment_block_start_y = 100
    comment_block_max_wide_chars = 10
    comment_block_max_lines = 16

    # 弹幕参数
    start_comment_index: int = 22
    gamestart = 226
    gameend = 2220 - 22
    scroll_speed: int = 150          # 像素/秒
    vertical_layers: int = 8         # 最大垂直分层数
    min_layer_height: int = 50       # 最小层高度（像素）
    font_size: int = 40              # 字体大小
    scroll_duration: int = 12        # 默认滚动时长（秒）

    # FFmpeg参数
    ffmpeg_preset: str = 'fast'      # slow, fast

# --------------------------
# 数据类（结构化数据处理）
# --------------------------
@dataclass
class DanmuInfo:
    text: str
    start_time: float
    end_time: float
    layer: int
    scroll_speed: int
    text_width: int
    lines: int

# --------------------------
# 核心功能类
# --------------------------
class DanmuProcessor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.video = VideoFileClip(config.video_path)
        self.danmu_data = None
        self.layer_system = None
        self.thread_num = 8

        # 初始化验证
        self._validate_video()
        self._load_data()

    def _validate_video(self):
        """验证视频基础信息"""
        print(f"视频分辨率: {self.video.size}")
        print(f"视频时长: {self.video.duration:.2f}秒")
        print(f"视频帧率: {self.video.fps}")

    def _load_data(self):
        """加载并预处理弹幕数据"""
        # 读取Excel
        self.danmu_data = pd.read_excel(self.config.excel_path)
        print(f"原始弹幕数: {len(self.danmu_data)}条")

        # 截取起始弹幕
        if len(self.danmu_data) < self.config.start_comment_index:
            raise ValueError("弹幕数据不足")
        
        baseline_time = self.danmu_data.loc[self.config.start_comment_index-1, "时间"]
        self.danmu_data = self.danmu_data.iloc[self.config.start_comment_index-1:]
        self.danmu_data["时间"] = (self.danmu_data["时间"] - baseline_time) / 1000
        
        # 过滤超长弹幕
        original_count = len(self.danmu_data)
        self.danmu_data = self.danmu_data[self.danmu_data["时间"] <= self.video.duration]
        print(f"过滤后弹幕数: {len(self.danmu_data)}条 (过滤{original_count - len(self.danmu_data)}条)")

    def generate_danmu_clips(self) -> List[DanmuInfo]:
        """生成弹幕剪辑信息"""
        print("正在生成弹幕剪辑信息...")
        start_time = time.time()
        danmu_clips = []
        video_width, _ = self.video.size

        def process_danmu(row):
            # 解析基础信息
            start_time = row["时间"]
            
            try:
                translated_data = json.loads(row["翻译后"].replace("'", "\""))  # 处理单引号问题
                text = translated_data["trans_res"]
            except json.JSONDecodeError:
                print("JSON 解析失败，请检查字符串格式:", row["翻译后"])
            except KeyError:
                print("trans_res 字段不存在:", row["翻译后"])

            # 创建文本剪辑
            text_clip = TextClip(
                text,
                fontsize=self.config.font_size,
                color='white',
                font='SimHei',
                stroke_color='black',
                stroke_width=1
            )

            # 计算滚动参数
            scroll_time = min(
                self.config.scroll_duration,
                self.video.duration - start_time
            )
            text_width = text_clip.size[0]
            _, lines = ASSGenerator._process_text(text, max_chars=10)
            
            # 记录弹幕信息
            danmu_info = DanmuInfo(
                text=text,
                start_time=start_time,
                end_time=start_time + scroll_time,
                layer=0,
                scroll_speed=self.config.scroll_speed,
                text_width=text_width,
                lines=lines
            )
            return danmu_info

        total_count = len(self.danmu_data)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            for _, row in self.danmu_data.iterrows():
                future = executor.submit(process_danmu, row)
                futures.append(future)

            for future in tqdm(concurrent.futures.as_completed(futures), total=total_count, desc="生成弹幕"):
                danmu = future.result()
                danmu_clips.append(danmu)

        print(f"弹幕信息处理完成，耗时: {time.time() - start_time:.2f}秒")
        return danmu_clips


class ASSGenerator:
    @staticmethod
    def generate_capacity_based_ass(danmu_clips: List[DanmuInfo], video_size: tuple = (1920, 1080)) -> str:
        """生成基于容量队列的ASS字幕内容"""
        # 初始化队列和记录列表
        queue = []
        lines_queue = []
        current_lines = 0
        ass_quickshot_list = []
        prev_time = None

        # 按时间排序弹幕
        sorted_danmu = sorted(danmu_clips, key=lambda x: x.start_time)

        for danmu in sorted_danmu:
            current_time = danmu.start_time

            # 维护队列
            if len(queue) >= AppConfig().comment_block_capacity:
                queue.pop(0)
                current_lines -= lines_queue.pop(0)

            queue.append(danmu.text)
            lines_queue.append(danmu.lines)
            current_lines += danmu.lines

            # 如果总行数超过限制，让元素出队直到小于等于限制
            while current_lines > AppConfig().comment_block_max_lines:
                queue.pop(0)
                current_lines -= lines_queue.pop(0)

            # 记录当前队列状态和时间
            if prev_time is not None:
                ass_quickshot_list.append({
                    'start_time': prev_time,
                    'end_time': current_time,
                    'danmus': queue.copy()[::-1]
                })
            prev_time = current_time

        # 处理最后一个时间点，设置结束时间为视频结束时间
        if prev_time is not None:
            video_clip = VideoFileClip(AppConfig().video_path)
            video_duration = video_clip.duration
            video_clip.close()
            ass_quickshot_list.append({
                'start_time': prev_time,
                'end_time': video_duration,
                'danmus': queue.copy()[::-1]
            })

        # 生成ASS内容
        ass_content = f"""\
        
    [Script Info]
    Title: Danmu Subtitles
    ScriptType: v4.00+
    WrapStyle: 0
    ScaledBorderAndShadow: yes
    YCbCr Matrix: TV.601
    PlayResX: {video_size[0]}
    PlayResY: {video_size[1]}

    [V4+ Styles]
    Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    Style: Default,黑体,29,&H00E1E1E1,&H007F7F7F,&HD3000000,&H80000000,-1,0,0,0,100,100,0,0,3,3,3,7,0,0,0,1

    [Events]
    Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    """

        current_y = AppConfig().comment_block_start_y  # 当前Y位置

        for i, entry in enumerate(ass_quickshot_list):
            start_tc = ASSGenerator._seconds_to_timecode(entry['start_time'])
            end_tc = ASSGenerator._seconds_to_timecode(entry['end_time'])
            danmus = entry['danmus']

            # 计算每个字幕的位置，从上到下排列，右对齐显示
            video_width, video_height = video_size
            for j, text in enumerate(danmus[:AppConfig().comment_block_capacity]):
                # 处理换行并获取行数
                processed_text, lines = ASSGenerator._process_text(text, max_chars=10)
                
                y_pos = current_y

                if i < AppConfig().gamestart or i > AppConfig().gameend:
                    x_pos = 1550
                    y_bonus = 120
                else:
                    x_pos = AppConfig().comment_block_start_x
                    y_bonus = 0
                
                # 添加字幕
                ass_content += (
                    f"Dialogue: 0,{start_tc},{end_tc},Default,,0,0,0,,"
                    f"{{\\pos({x_pos}, {y_pos + y_bonus})}}{processed_text}\n"
                )
                
                # 更新当前Y位置，为下个弹幕留出空间
                current_y += lines * AppConfig().comment_row_space

            # 重置current_y为起始位置
            current_y = AppConfig().comment_block_start_y

        return ass_content

    @staticmethod
    def _process_text(text: str, max_chars: int = AppConfig().comment_block_max_wide_chars) -> tuple:
        """处理文本，使其不超过max_chars个字符，并添加换行符，返回处理后的文本和行数"""
        processed = []
        current_line = ""
        lines = 0
        char_count = 0
        
        for char in text:
            if '\u4e00' <= char <= '\u9fa5':  # 判断是否为中文字符
                char_count += 1
            else:
                char_count += 0.5  # 英文/标点算半个字符
            
            if char_count <= max_chars:
                current_line += char
            else:
                processed.append(current_line)
                current_line = char
                char_count = 1 if '\u4e00' <= char <= '\u9fa5' else 0.5
                lines += 1
        if current_line:
            processed.append(current_line)
            lines += 1
        
        return ('\\N'.join(processed), lines)

    @staticmethod
    def _seconds_to_timecode(seconds: float) -> str:
        """秒数转时间码"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours:01d}:{minutes:02d}:{seconds:06.2f}"

# --------------------------
# 工具函数
# --------------------------
def run_ffmpeg(config: AppConfig, ass_path: str):
    """执行FFmpeg命令"""
    video_width, video_height = VideoFileClip(config.video_path).size
    output_resolution = f"{video_width}:{video_height}"  # 根据输入视频调整输出分辨率
    command_1ass = [
        'ffmpeg',
        '-hwaccel', 'cuda',                  # 启用CUDA解码
        '-hwaccel_output_format', 'cuda',
        '-i', config.video_path,              # 输入视频路径
        '-ss', '00:00:00',                    # 开始时间
        '-t', '280',                          # 持续时间
        '-vf', f"hwupload,scale_cuda={output_resolution}:format=yuv420p,hwdownload,ass='{ass_path}'",  # 关键修改点
        '-c:v', 'h264_nvenc',                 # 使用NVIDIA编码器
        '-preset', config.ffmpeg_preset,
        '-c:a', 'aac',
        '-b:a', '192k',
        config.output_path
    ]
    command_2ass = [
        'ffmpeg',
        '-hwaccel', 'cuda',                  # 启用CUDA解码
        '-hwaccel_output_format', 'cuda',
        '-i', config.video_path,             # 输入视频路径
        '-ss', '00:00:00',                   # 开始时间
        '-t', '280',                         # 持续时间
        '-vf', f"hwupload,scale_cuda={output_resolution}:format=yuv420p,hwdownload," 
            f"ass='{ass_path}',ass='{AppConfig().main_ass_path}'",  # 关键修改：叠加双字幕
        '-c:v', 'h264_nvenc',                # 使用NVIDIA编码器
        '-preset', config.ffmpeg_preset,
        '-c:a', 'aac',
        '-b:a', '192k',
        config.output_path
    ]
    command = [
        'ffmpeg',
        '-hwaccel', 'cuda',
        '-hwaccel_output_format', 'cuda',
        '-i', config.video_path,
        # '-ss', '00:11:00',
        # '-t', '280',
        '-vf', f"hwupload,scale_cuda={output_resolution}:format=yuv420p,hwdownload,ass='{ass_path}',ass='{AppConfig().main_ass_path}'", 
        '-c:v', 'hevc_nvenc',
        '-preset', 'p6',          # 改用 p6 规避兼容性问题
        '-rc', 'vbr',             # 替代 vbr_hq，更稳定的高质量模式
        '-cq', '18',              # 恒定质量模式（18-23为推荐范围）
        '-qmin', '0',             # 最小量化器（防止低动态场景模糊）
        '-qmax', '30',            # 最大量化器（控制最差质量）
        '-profile:v', 'main',     # 通用兼容性（若输入是8bit）
        '-multipass', 'fullres',  # 启用完整多阶段编码提升质量
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',
        '-y',                     # 自动覆盖输出文件
        config.output_path
    ]
   
    print("正在合并视频...")
    start_time = time.time()
    subprocess.run(command, check=True)
    print(f"合并完成，耗时: {time.time() - start_time:.2f}秒")

# --------------------------
# 主程序
# --------------------------
def CommentAssVideo():
    # 初始化配置
    config = AppConfig()
    
    try:
        # 保存ASS文件到临时文件夹
        ass_path = 'temp_danmu_block.ass'

        if not os.path.exists(ass_path):
            # 处理弹幕
            processor = DanmuProcessor(config)
            danmu_clips = processor.generate_danmu_clips()

            # 生成ASS文件
            ass_content = ASSGenerator.generate_capacity_based_ass(
                danmu_clips, 
                processor.video.size
            )

            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
        else:
            print('Skipped ass generation...')

        # 合并视频
        run_ffmpeg(config, ass_path)
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
    finally:
        if 'processor' in locals():
            processor.video.close()

if __name__ == "__main__":
    CommentAssVideo()

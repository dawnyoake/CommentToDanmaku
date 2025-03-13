import os
import subprocess
import time
from dataclasses import dataclass
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
    video_path: str = r".\data\AOI-ER02\AOI-ER02.mp4"
    excel_path: str = r".\data\AOI-ER02\AOI-ER02.xlsx"
    output_path: str = r".\output\MKH-02-output-fast.mp4"
    
    # 弹幕参数
    start_comment_index: int = 1
    scroll_speed: int = 150          # 像素/秒
    vertical_layers: int = 8         # 最大垂直分层数
    min_layer_height: int = 50       # 最小层高度（像素）
    font_size: int = 40              # 字体大小
    scroll_duration: int = 12        # 默认滚动时长（秒）

    # FFmpeg参数
    ffmpeg_preset: str = 'fast'      # veryslowe, fast

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

# --------------------------
# 核心功能类
# --------------------------
class DanmuProcessor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.video = VideoFileClip(config.video_path)
        self.danmu_data = None
        self.layer_system = None

        # 初始化验证
        self._validate_video()
        self._load_data()
        self._init_layer_system()

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

    def _init_layer_system(self):
        """初始化弹幕分层系统"""
        video_width, video_height = self.video.size
        top_third_height = video_height / 3
        
        # 动态计算层高
        layer_height = max(
            self.config.min_layer_height, 
            top_third_height / self.config.vertical_layers
        )
        self.vertical_layers = int(top_third_height / layer_height)
        
        self.layer_system = {
            'layer_height': layer_height,
            'end_times': [0] * self.vertical_layers
        }
        print(f"初始化分层系统: {self.vertical_layers}层，层高{layer_height:.1f}像素")

    def _allocate_layer(self, start_time: float) -> int:
        """智能分配弹幕层"""
        # 似乎可以再优化一下
        # 优先查找可用层
        for layer, end_time in enumerate(self.layer_system['end_times']):
            if start_time >= end_time:
                return layer
        
        # 没有可用层时选择最早结束的层
        return self.layer_system['end_times'].index(min(self.layer_system['end_times']))

    def generate_danmu_clips(self) -> List[DanmuInfo]:
        """生成弹幕剪辑信息"""
        danmu_clips = []
        video_width, _ = self.video.size
        
        for _, row in tqdm(self.danmu_data.iterrows(), total=len(self.danmu_data), desc="生成弹幕"):
            # 解析基础信息
            start_time = row["时间"]
            text = row["翻译后"]
            
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
            
            # 分配弹幕层
            layer = self._allocate_layer(start_time)
            self.layer_system['end_times'][layer] = start_time + scroll_time
            
            # 记录弹幕信息
            danmu_clips.append(DanmuInfo(
                text=text,
                start_time=start_time,
                end_time=start_time + scroll_time,
                layer=layer,
                scroll_speed=self.config.scroll_speed,
                text_width=text_width
            ))
        
        return danmu_clips

class ASSGenerator:
    @staticmethod
    def generate(danmu_clips: List[DanmuInfo], video_size: tuple, config: AppConfig) -> str:
        """生成ASS字幕内容"""
        # 样式头
        ass_content = f"""\
[Script Info]
; Generated by Danmu Processor
Title: Danmu Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {video_size[0]}
PlayResY: {video_size[1]}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""
        # 生成样式
        layer_height = config.min_layer_height  # 实际计算值需从processor获取
        for layer in range(config.vertical_layers):
            ass_content += f"Style: Layer{layer},SimHei,40,&H00000000,&H000000FF,&H00FFFFFF,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,7,0,0,{layer * layer_height},0\n"

        # 事件头
        ass_content += "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

        # 弹幕条目
        for danmu in danmu_clips:
            start_tc = ASSGenerator._seconds_to_timecode(danmu.start_time)
            end_tc = ASSGenerator._seconds_to_timecode(danmu.end_time)
            y_pos = danmu.layer * config.min_layer_height  # 需与实际计算层高一致
            
            ass_content += (
                f"Dialogue: 0,{start_tc},{end_tc},Layer{danmu.layer},,0,0,0,,"
                f"{{\\move({video_size[0]}, {y_pos}, -500, {y_pos})}}{danmu.text}\n"
            )
        
        return ass_content

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
    command = [
        'ffmpeg',
        '-hwaccel', 'cuda',
        '-i', config.video_path,
        '-vf', f"scale={output_resolution},ass='{ass_path}',format=yuv420p",
        '-c:v', 'libx264',
        '-preset', config.ffmpeg_preset,
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
        # 处理弹幕
        processor = DanmuProcessor(config)
        danmu_clips = processor.generate_danmu_clips()
        
        # 生成ASS文件
        ass_content = ASSGenerator.generate(
            danmu_clips, 
            processor.video.size, 
            config
        )
        
        # 保存ASS文件到临时文件夹
        # 修改后（方法一：转义反斜杠）
        ass_path = 'temp_danmu.ass'
        if not os.path.exists('temp'):
            os.makedirs('temp')
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)
        
        # 合并视频
        run_ffmpeg(config, ass_path)
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
    finally:
        if 'processor' in locals():
            processor.video.close()

if __name__ == "__main__":
    CommentAssVideo()
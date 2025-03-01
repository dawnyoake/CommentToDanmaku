import pytchat
import pandas as pd
import os

# 获取 YouTube 视频 ID
def get_video_id(url):
    if 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    raise ValueError("Invalid YouTube URL")

# 获取实时弹幕数据
def get_live_chat(video_id):
    chat = pytchat.create(video_id=video_id)
    chat_data = []

    while chat.is_alive():
        for message in chat.get().items:
            chat_data.append({
                '时间': message.timestamp,
                '用户名': message.author.name,
                '弹幕内容': message.message,
                '用户ID': message.author.channelId
            })
        print(f"已获取 {len(chat_data)} 条弹幕...")

    return chat_data

# 保存数据到 Excel 文件
def save_to_excel(data, video_id):
    df = pd.DataFrame(data)
    if not os.path.exists('./ytbcomments'):
        os.makedirs('./ytbcomments')
    file_path = f'./ytbcomments/{video_id}_live_chat.xlsx'
    df.to_excel(file_path, index=False)
    print(f"弹幕数据已保存到 {file_path}")

# 主函数
def main(url):
    video_id = get_video_id(url)
    print(f"正在获取视频 {video_id} 的实时弹幕...")
    chat_data = get_live_chat(video_id)
    save_to_excel(chat_data, video_id)

if __name__ == '__main__':
    url = 'https://www.youtube.com/watch?v=nDI6TC8Sahk&ab_channel=amiamiHobbyChannel'
    main(url)
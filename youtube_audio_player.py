import sys
import tkinter as tk
from tkinter import messagebox
import threading
import random
import time
from yt_dlp import YoutubeDL
import vlc
import requests as req
from PIL import Image, ImageTk
import io
from collections import OrderedDict

urls, titles = [], []
pos = 0
is_shuffle = False
shuffled_list = []
play_thread = None
stop_event = threading.Event()
player = None
thumbnail = None
thumbnail_cache = {}

class ThumbnailCache:
    def __init__(self, max_size = 100):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

thumbnail_cache = ThumbnailCache(max_size=100)


def get_playlist_video_urls(playlist_url):
    ydl_opts = {'extract_flat': True, 'quiet': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        return [entry["url"] for entry in info["entries"]]

def get_audio_url(video_url):
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return info.get("url")
    
def get_playlist_video_titles(playlist_url):
    ydl_opts = {'extract_flat': True, 'quiet': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        titles = [entry.get('title', '제목 없음') for entry in info['entries']]
        return titles
    
def get_thumbnail_url(video_url):
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return info.get("thumbnail")
    
def get_thumbnail_content(thumbnail_url):
    thumbnail_response = req.get(thumbnail_url)
    return thumbnail_response.content

def get_thumbnail_Image_from_video_url(video_url):
    global thumbnail_cache
    url = get_thumbnail_url(video_url)
    img = thumbnail_cache.get(url)
    if img is not None:
        print("이미지가 캐시 내에 있음.")
        return img
    else:
        try:
            img_raw = Image.open(io.BytesIO(get_thumbnail_content(get_thumbnail_url(video_url))))
            w, h = img_raw.size
            target_ratio = 16 / 9
            if w / h > target_ratio:
                # 가로가 더 길다 → 좌우를 crop
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                img_cropped = img_raw.crop((left, 0, left + new_w, h))
            else:
                # 세로가 더 길다 → 위아래를 crop
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                img_cropped = img_raw.crop((0, top, w, top + new_h))

            img_final = img_cropped.resize((480, 270))
            tk_img = ImageTk.PhotoImage(img_final)
            thumbnail_cache.set(url, tk_img)
            return tk_img
        except Exception as e:
            print(f"섬네일 로딩 오류: {e}")
            # 썸네일이 없으면 기본 이미지나 None 반환
            return None

def update_title(title):
    status_label.config(text=f"지금 재생 중: {title}")


def play_audio_stream(audio_url):
    global player
    player = vlc.MediaPlayer(audio_url)
    player.play()
    time.sleep(1)

def play_playlist_auto(stop_event, start_pos=0):
    global pos, urls, is_shuffle, shuffled_list, thumbnail
    btn_shuffle.config(state="normal")

    pos = start_pos
    while pos < len(urls):
        if stop_event.is_set():
            break
        idx = shuffled_list[pos] if is_shuffle else pos
        print(idx + 1,"번째 곡을 재생합니다.")
        

        thumbnail = get_thumbnail_Image_from_video_url(urls[idx])
        label_thumbnail.config(image=thumbnail)
        update_title(f"{idx + 1} / {len(urls)} : {titles[idx]}")
        play_audio_stream(get_audio_url(urls[idx]))

        dur = player.get_length() / 1000
        if dur < 1:
            time.sleep(1)
            while player.is_playing() and not stop_event.is_set():
                time.sleep(0.5)
        else:
            for _ in range(int(dur) + 2):
                if stop_event.is_set():
                    break
                time.sleep(1)

        pos += 1

def play_from_index(start_pos):
    global play_thread, stop_event, player
    if play_thread and play_thread.is_alive():
        stop_event.set()
        play_thread.join()
    if player:
        player.stop()
        player.release()
        player = None
    stop_event = threading.Event()
    play_thread = threading.Thread(target=play_playlist_auto, args=(stop_event, start_pos), daemon=True)
    play_thread.start()

def shuffle_and_play():
    global is_shuffle, shuffled_list, pos, urls
    if not urls:
        return
    shuffled_list = list(range(len(urls))) 
    random.shuffle(shuffled_list) #곡 번호만 랜덤으로 섞기.
    pos = 0
    is_shuffle = True
    play_from_index(pos)

def play_next():
    global pos
    if pos + 1 < len(urls):
        pos += 1
        play_from_index(pos)

def play_prev():
    global pos
    if pos - 1 >= 0:
        pos -= 1
        play_from_index(pos)

def load_playlist():
    global urls, titles, pos, play_thread, stop_event, player

    # 기존 재생 중지(있으면) + 이전 쓰레드 종료
    if play_thread and play_thread.is_alive():
        stop_event.set()
        play_thread.join()
    if player:
        player.stop()
        player.release()
        player = None

    # 새 목록 불러오기
    playlist_url = entry.get()
    urls.clear()
    titles.clear()
    pos = 0

    urls = get_playlist_video_urls(playlist_url)
    titles = get_playlist_video_titles(playlist_url)

    stop_event = threading.Event()
    play_thread = threading.Thread(target=play_playlist_auto, args=(stop_event, 0), daemon=True)
    play_thread.start()

def exit_program():
    global play_thread, stop_event, player, root
    if play_thread and play_thread.is_alive():
        stop_event.set()
        play_thread.join()
    if player:
        player.stop()
        player.release()
    root.destroy()
    sys.exit()

def confirm_exit():
    if messagebox.askokcancel("종료 확인", "정말 종료할까요?"):
        exit_program()

# GUI

root = tk.Tk()
root.title("YouTube 오디오 플레이어 BETA")

main_frame = tk.Frame(root, padx=20, pady=20)
main_frame.grid(row=0, column=0)

url_label = tk.Label(main_frame, text="재생목록 URL:")
url_label.grid(row=0, column=0, sticky="e")

entry = tk.Entry(main_frame, width=50)
entry.grid(row=0, column=1, columnspan=3, padx=5, pady=5)

load_button = tk.Button(main_frame, text="불러오기", width=10, command=load_playlist)
load_button.grid(row=0, column=5)

status_label = tk.Label(main_frame, text="아직 재생 안됨", font=("Arial", 14)) #제목 보여주기
status_label.grid(row=1, column=0, columnspan=5, pady=20)

label_thumbnail = tk.Label(root, image=thumbnail)
label_thumbnail.grid(row=2, column=0)

prev_button = tk.Button(main_frame, text="⏮ 이전", width=10, command=play_prev)
prev_button.grid(row=6, column=0)

# pause_button = tk.Button(main_frame, text="⏸ 일시정지", width=10, command=toggle_play_pause)
# pause_button.grid(row=3, column=1)

next_button = tk.Button(main_frame, text="다음 ⏭", width=10, command=play_next)
next_button.grid(row=6, column=2)

btn_shuffle = tk.Button(main_frame, text="셔플 재생", width=10, command=shuffle_and_play, state="disabled")
btn_shuffle.grid(row=6, column=3)

exit_button = tk.Button(main_frame, text="종료", width=10, command=confirm_exit)
exit_button.grid(row=6, column=4)

root.mainloop()


# root = tk.Tk()
# entry = tk.Entry(root)
# entry.pack()
# btn_load = tk.Button(root, text="재생목록 불러오기", command=load_playlist)
# btn_load.pack()
# btn_shuffle = tk.Button(root, text="셔플 재생", command=shuffle_and_play)
# btn_shuffle.pack()
# btn_next = tk.Button(root, text="다음 곡", command=play_next)
# btn_next.pack()
# btn_prev = tk.Button(root, text="이전 곡", command=play_prev)
# btn_prev.pack()
# label_thumbnail = tk.Label(root, image=thumbnail)
# label_thumbnail.pack()
# root.mainloop()

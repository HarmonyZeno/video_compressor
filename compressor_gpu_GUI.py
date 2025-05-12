import subprocess
import os
import re
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from rich.console import Console
from rich.progress import Progress

console = Console()

def get_video_duration(input_file):
    try:
        result = subprocess.run([
            'ffmpeg', '-i', input_file
        ], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8')
        
        duration = None
        for line in result.stderr.split('\n'):
            match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', line)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
                seconds = float(match.group(3))
                duration = hours * 3600 + minutes * 60 + seconds
                break
        
        if duration is None:
            raise ValueError("无法获取视频时长")
        
        return duration
    except subprocess.CalledProcessError as e:
        console.print(f'获取视频时长失败: {e}', style="bold red")
        return None

def compress_video(input_file, output_file, bitrate='1M', progress_callback=None, file_callback=None, remaining_time_callback=None, terminate_flag=None, use_gpu=True):
    try:
        total_duration = get_video_duration(input_file)
        if total_duration is None:
            console.print("无法获取视频时长，无法继续压缩", style="bold red")
            return
        
        start_time = time.time()

        codec = 'h264_nvenc' if use_gpu else 'libx264'
        process = subprocess.Popen([
            'ffmpeg',
            '-i', input_file,
            '-b:v', bitrate,
            '-c:v', codec,
            '-c:a', 'copy',
            '-vf', "scale=1440:1080",
            output_file
        ], stderr=subprocess.PIPE, text=True, encoding='utf-8')
        
        with Progress() as progress:
            task = progress.add_task(f"[cyan]压缩 {os.path.basename(input_file)}", total=total_duration)
            for line in process.stderr:
                if terminate_flag and terminate_flag.is_set():
                    console.print('\n中断信号接收，终止子进程...', style="bold yellow")
                    process.terminate()
                    process.wait()
                    elapsed_time = time.time() - start_time
                    console.print(f'\n压缩被中断，运行时间: {elapsed_time:.2f} 秒', style="bold yellow")
                    return
                
                match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                if match:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = float(match.group(3))
                    elapsed_time = hours * 3600 + minutes * 60 + seconds
                    progress.update(task, completed=elapsed_time)

                    if progress_callback:
                        progress_callback(elapsed_time / total_duration)
                    if remaining_time_callback:
                        remaining_time = total_duration - elapsed_time
                        remaining_time_callback(remaining_time)
                    if file_callback:
                        file_callback(os.path.basename(input_file))

        elapsed_time = time.time() - start_time
        console.print(f'\n压缩完成，运行时间: {elapsed_time:.2f} 秒', style="bold green")
    except Exception as e:
        console.print(f'压缩失败: {e}', style="bold red")

def compress_videos_in_directory(input_dir, output_dir, bitrate, file_extension, post_task, progress_callback=None, file_callback=None, remaining_time_callback=None, terminate_flag=None, use_gpu=True):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.mkv'):
                input_file = os.path.join(root, file)
                base_name = os.path.splitext(file)[0]
                if any(os.path.splitext(f)[0] == base_name for f in os.listdir(output_dir)):
                    console.print(f'跳过已存在的文件: {file}', style="bold yellow")
                    continue

                output_file = os.path.join(output_dir, base_name + file_extension)
                compress_video(input_file, output_file, bitrate, progress_callback, file_callback, remaining_time_callback, terminate_flag, use_gpu)
                if terminate_flag and terminate_flag.is_set():
                    return

    if post_task == "shutdown":
        console.print("压缩完成，正在关机...", style="bold green")
        os.system("shutdown /s /t 1")
    elif post_task == "hibernate":
        console.print("压缩完成，正在休眠...", style="bold green")
        os.system("shutdown /h /t 1")

def select_input_directory():
    input_dir = filedialog.askdirectory()
    input_dir_entry.delete(0, tk.END)
    input_dir_entry.insert(0, input_dir)

def select_output_directory():
    output_dir = filedialog.askdirectory()
    output_dir_entry.delete(0, tk.END)
    output_dir_entry.insert(0, output_dir)

def update_progress(progress):
    progress_var.set(progress)
    root.update_idletasks()

def update_current_file(file_name):
    current_file_label.config(text=f"当前文件: {file_name}")
    root.update_idletasks()

def update_remaining_time(remaining_time):
    remaining_time_label.config(text=f"剩余时间: {time.strftime('%H:%M:%S', time.gmtime(remaining_time))}")
    root.update_idletasks()

def start_compression():
    global terminate_flag
    terminate_flag = threading.Event()
    input_dir = input_dir_entry.get()
    output_dir = output_dir_entry.get()
    bitrate = bitrate_entry.get()
    file_extension = file_extension_var.get()
    post_task = post_task_var.get()
    use_gpu = use_gpu_var.get()

    compression_thread = threading.Thread(
        target=compress_videos_in_directory,
        args=(input_dir, output_dir, bitrate, file_extension, post_task, update_progress, update_current_file, update_remaining_time, terminate_flag),
        kwargs={"use_gpu": use_gpu}
    )
    compression_thread.start()

def terminate_compression():
    global terminate_flag
    if terminate_flag:
        terminate_flag.set()
        root.quit()

# GUI 创建
root = tk.Tk()
root.title("视频压缩工具")

# 输入目录选择
tk.Label(root, text="输入目录:").grid(row=0, column=0, padx=10, pady=10)
input_dir_entry = tk.Entry(root, width=50)
input_dir_entry.grid(row=0, column=1, padx=10, pady=10)
tk.Button(root, text="选择", command=select_input_directory).grid(row=0, column=2, padx=10, pady=10)

# 输出目录选择
tk.Label(root, text="输出目录:").grid(row=1, column=0, padx=10, pady=10)
output_dir_entry = tk.Entry(root, width=50)
output_dir_entry.grid(row=1, column=1, padx=10, pady=10)
tk.Button(root, text="选择", command=select_output_directory).grid(row=1, column=2, padx=10, pady=10)

# 比特率设置
tk.Label(root, text="比特率:").grid(row=2, column=0, padx=10, pady=10)
bitrate_entry = tk.Entry(root, width=50)
bitrate_entry.grid(row=2, column=1, padx=10, pady=10)
bitrate_entry.insert(0, '2M')

# 文件后缀选择
tk.Label(root, text="文件后缀:").grid(row=3, column=0, padx=10, pady=10)
file_extension_var = tk.StringVar(value=".mp4")
file_extension_choices = [".mp4", ".mkv", ".avi", ".mov", ".flv"]
file_extension_dropdown = ttk.Combobox(root, textvariable=file_extension_var, values=file_extension_choices)
file_extension_dropdown.grid(row=3, column=1, padx=10, pady=10)

# 计划任务选择
tk.Label(root, text="计划任务:").grid(row=4, column=0, padx=10, pady=10)
post_task_var = tk.StringVar(value="none")
post_task_choices = ["none", "shutdown", "hibernate"]
post_task_dropdown = ttk.Combobox(root, textvariable=post_task_var, values=post_task_choices)
post_task_dropdown.grid(row=4, column=1, padx=10, pady=10)

# GPU加速选项
use_gpu_var = tk.BooleanVar(value=True)
tk.Checkbutton(root, text="使用 GPU 加速 (h264_nvenc)", variable=use_gpu_var).grid(row=5, column=0, padx=10, pady=10)

# 当前文件标签
current_file_label = tk.Label(root, text="当前文件: 无")
current_file_label.grid(row=5, column=1, padx=10, pady=10)

# 进度条
progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=1.0, length=300)
progress_bar.grid(row=6, column=1, padx=10, pady=10)

# 剩余时间标签
remaining_time_label = tk.Label(root, text="剩余时间: 00:00:00")
remaining_time_label.grid(row=6, column=2, padx=10, pady=10)

# 控制按钮
tk.Button(root, text="开始压缩", command=start_compression).grid(row=7, column=1, padx=10, pady=10)
tk.Button(root, text="终止压缩", command=terminate_compression).grid(row=7, column=2, padx=10, pady=10)

root.mainloop()

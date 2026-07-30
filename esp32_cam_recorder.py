import os
import http.server
import subprocess
import struct
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


MAX_AVI_BYTES = 3_800_000_000
PREVIEW_BUFFER_SECONDS = 0.65
PREVIEW_QUEUE_LIMIT = 120


def _chunk(tag, payload):
    padding = b"\x00" if len(payload) & 1 else b""
    return tag + struct.pack("<I", len(payload)) + payload + padding


def _list_chunk(tag, payload):
    return b"LIST" + struct.pack("<I", len(payload) + 4) + tag + payload


def jpeg_dimensions(jpeg):
    i = 2
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while i + 9 < len(jpeg):
        if jpeg[i] != 0xFF:
            i += 1
            continue
        while i < len(jpeg) and jpeg[i] == 0xFF:
            i += 1
        if i >= len(jpeg):
            break
        marker = jpeg[i]
        i += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > len(jpeg):
            break
        length = struct.unpack(">H", jpeg[i:i + 2])[0]
        if marker in sof and i + 7 <= len(jpeg):
            height = struct.unpack(">H", jpeg[i + 3:i + 5])[0]
            width = struct.unpack(">H", jpeg[i + 5:i + 7])[0]
            return width, height
        if length < 2:
            break
        i += length
    raise ValueError("无法从图像帧读取分辨率")


class MjpegAviWriter:
    def __init__(self, path, width, height):
        self.path = Path(path)
        self.width = width
        self.height = height
        self.frames = 0
        self.max_frame = 0
        self.index = []
        self.started = time.monotonic()
        self.file = self.path.open("w+b")
        placeholder = self._header(0, 1.0, 0, 0)
        self.header_size = len(placeholder)
        self.file.write(placeholder)
        self.movi_data_start = self.header_size

    def _header(self, frame_count, fps, movi_payload_size, file_size):
        fps = max(0.1, fps)
        scale = 1000
        rate = max(1, round(fps * scale))
        usec = max(1, round(1_000_000 / fps))
        max_bps = max(1, round(self.max_frame * fps))
        avih = struct.pack(
            "<IIIIIIIIII4I", usec, max_bps, 0, 0x10, frame_count, 0, 1,
            self.max_frame, self.width, self.height, 0, 0, 0, 0
        )
        strh = struct.pack(
            "<4s4sIHHIIIIIIIIhhhh", b"vids", b"MJPG", 0, 0, 0, 0,
            scale, rate, 0, frame_count, self.max_frame, 0xFFFFFFFF, 0,
            0, 0, self.width, self.height
        )
        strf = struct.pack(
            "<IiiHH4sIiiII", 40, self.width, self.height, 1, 24, b"MJPG",
            self.width * self.height * 3, 0, 0, 0, 0
        )
        hdrl = _list_chunk(b"hdrl", _chunk(b"avih", avih) + _list_chunk(
            b"strl", _chunk(b"strh", strh) + _chunk(b"strf", strf)
        ))
        riff_size = max(4 + len(hdrl) + 12, file_size - 8)
        return (
            b"RIFF" + struct.pack("<I", riff_size) + b"AVI " + hdrl +
            b"LIST" + struct.pack("<I", movi_payload_size + 4) + b"movi"
        )

    def add_frame(self, jpeg):
        if self.file.tell() + len(jpeg) + 32 >= MAX_AVI_BYTES:
            raise RuntimeError("录像已接近 AVI 4GB 上限，已自动停止")
        chunk_pos = self.file.tell()
        self.file.write(b"00dc")
        self.file.write(struct.pack("<I", len(jpeg)))
        self.file.write(jpeg)
        if len(jpeg) & 1:
            self.file.write(b"\x00")
        # AVI idx1 offsets are relative to the beginning of the 'movi' list.
        offset = chunk_pos - (self.movi_data_start - 4)
        self.index.append((offset, len(jpeg)))
        self.frames += 1
        self.max_frame = max(self.max_frame, len(jpeg))

    @property
    def elapsed(self):
        return max(0.001, time.monotonic() - self.started)

    def close(self):
        if self.file.closed:
            return
        movi_end = self.file.tell()
        entries = bytearray()
        for offset, size in self.index:
            entries.extend(struct.pack("<4sIII", b"00dc", 0x10, offset, size))
        self.file.write(_chunk(b"idx1", bytes(entries)))
        final_size = self.file.tell()
        fps = self.frames / self.elapsed if self.frames else 1.0
        movi_payload = movi_end - self.movi_data_start
        header = self._header(self.frames, fps, movi_payload, final_size)
        if len(header) != self.header_size:
            raise RuntimeError("AVI 头长度异常")
        self.file.seek(0)
        self.file.write(header)
        self.file.flush()
        self.file.close()


def stream_url(value):
    value = value.strip()
    if not value:
        raise ValueError("请输入串口显示的摄像头 IP")
    if "://" not in value:
        value = "http://" + value
    parsed = urllib.parse.urlparse(value)
    if not parsed.hostname:
        raise ValueError("IP 或网址格式不正确")
    port = parsed.port or 81
    path = parsed.path if parsed.path not in ("", "/") else "/stream"
    return urllib.parse.urlunparse(("http", f"{parsed.hostname}:{port}", path, "", "", ""))


class RecorderApp:
    def __init__(self, root):
        self.root = root
        self.stop_event = threading.Event()
        self.worker = None
        self.closing = False
        self.close_requested = False
        self.current_response = None
        self.preview_frames = deque(maxlen=PREVIEW_QUEUE_LIMIT)
        self.preview_interval = 1.0 / 10.0
        self.last_frame_arrival = None
        self.frame_condition = threading.Condition()
        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos"))
        self.address = tk.StringVar(value="192.168.1.100")
        self.status = tk.StringVar(value="等待开始")
        self.current_file = None
        self.working_file = None

        root.title("ESP32S3-Cam 平滑预览与录像工具")
        root.geometry("660x300")
        root.resizable(False, False)

        panel = ttk.Frame(root, padding=16)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="摄像头 IP 或图传网址：").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(panel, textvariable=self.address, width=48).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(panel, text="打开本地预览", command=self.open_preview).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(panel, text="录像保存目录：").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(panel, textvariable=self.output_dir, width=48).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(panel, text="选择目录", command=self.choose_dir).grid(row=1, column=2, padx=(8, 0))

        self.start_button = ttk.Button(panel, text="开始录像", command=self.start)
        self.start_button.grid(row=2, column=0, pady=16, sticky="ew")
        self.stop_button = ttk.Button(panel, text="停止并保存", command=self.stop, state="disabled")
        self.stop_button.grid(row=2, column=1, pady=16, padx=8, sticky="ew")
        ttk.Button(panel, text="打开录像目录", command=self.open_folder).grid(row=2, column=2, pady=16, sticky="ew")

        ttk.Separator(panel).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(2, 10))
        ttk.Label(panel, textvariable=self.status, foreground="#075985").grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(
            panel,
            text="预览先缓冲约 0.65 秒并匀速播放；录像直接封装 MJPEG，不二次编码。",
            foreground="#555555"
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))
        panel.columnconfigure(1, weight=1)
        self.start_proxy()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_proxy(self):
        app = self

        class PreviewHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>ESP32S3-Cam 本地预览</title>
<style>html,body{{width:100%;height:100%;margin:0;background:#000;overflow:hidden}}
img{{display:block;width:100vw;height:100vh;object-fit:contain;background:#000}}</style></head>
<body><img src="/stream" alt="正在等待图传画面"></body></html>""".encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(page)))
                    self.end_headers()
                    self.wfile.write(page)
                    return
                if self.path != "/stream":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                playback_started = False
                next_send = time.monotonic()
                try:
                    while not app.closing:
                        with app.frame_condition:
                            target_frames = max(
                                4,
                                min(30, round(PREVIEW_BUFFER_SECONDS / app.preview_interval)),
                            )
                            if not playback_started:
                                app.frame_condition.wait_for(
                                    lambda: len(app.preview_frames) >= target_frames or app.closing,
                                    timeout=2.0,
                                )
                                if app.preview_frames:
                                    playback_started = True
                                    next_send = time.monotonic()
                            else:
                                app.frame_condition.wait_for(
                                    lambda: bool(app.preview_frames) or app.closing,
                                    timeout=1.0,
                                )
                            if app.closing:
                                break
                            if not app.preview_frames:
                                continue
                            frame = app.preview_frames.popleft()
                            interval = app.preview_interval
                            buffered = len(app.preview_frames)
                            # Gently keep the buffer near its target without making
                            # frame spacing visibly jump when Wi-Fi arrival times vary.
                            if buffered > target_frames * 1.5:
                                interval *= 0.98
                            elif buffered < target_frames * 0.5:
                                interval *= 1.02
                        if not frame:
                            continue
                        now = time.monotonic()
                        if next_send > now:
                            time.sleep(next_send - now)
                        elif now - next_send > interval * 2:
                            next_send = now
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                            str(len(frame)).encode("ascii") + b"\r\n\r\n" + frame + b"\r\n"
                        )
                        next_send += interval
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

        self.preview_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), PreviewHandler)
        self.preview_server.daemon_threads = True
        self.preview_port = self.preview_server.server_address[1]
        threading.Thread(target=self.preview_server.serve_forever, daemon=True).start()

    def choose_dir(self):
        selected = filedialog.askdirectory(initialdir=self.output_dir.get())
        if selected:
            self.output_dir.set(selected)

    def open_folder(self):
        folder = Path(self.output_dir.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def open_preview(self):
        if not self.worker or not self.worker.is_alive():
            messagebox.showinfo("本地预览", "请先点击“开始录像”，再打开本地预览。")
            return
        url = f"http://127.0.0.1:{self.preview_port}/"
        edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        if edge.exists():
            subprocess.Popen([
                str(edge), "--new-window", "--start-fullscreen", f"--app={url}"
            ])
        else:
            webbrowser.open(url)

    def start(self):
        try:
            url = stream_url(self.address.get())
            folder = Path(self.output_dir.get()).expanduser()
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("无法开始", str(exc))
            return
        filename = datetime.now().strftime("ESP32Cam_%Y%m%d_%H%M%S.avi")
        self.current_file = folder / filename
        self.working_file = folder / (filename + ".recording")
        self.stop_event.clear()
        with self.frame_condition:
            self.preview_frames.clear()
            self.preview_interval = 1.0 / 10.0
            self.last_frame_arrival = None
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"正在连接 {url} ...")
        self.worker = threading.Thread(target=self.record_worker, args=(url,), daemon=True)
        self.worker.start()
        self.root.after(800, self.open_preview)

    def stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status.set("正在停止并写入 AVI 索引，请稍候...")
        response = self.current_response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def record_worker(self, url):
        writer = None
        error = None
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ESP32CamRecorder/1.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                self.current_response = response
                buffer = bytearray()
                last_update = time.monotonic()
                while not self.stop_event.is_set():
                    data = response.read(16384)
                    if not data:
                        raise ConnectionError("图传连接已断开")
                    buffer.extend(data)
                    while True:
                        start = buffer.find(b"\xff\xd8")
                        if start < 0:
                            if len(buffer) > 2_000_000:
                                del buffer[:-2]
                            break
                        end = buffer.find(b"\xff\xd9", start + 2)
                        if end < 0:
                            if start:
                                del buffer[:start]
                            break
                        frame = bytes(buffer[start:end + 2])
                        del buffer[:end + 2]
                        arrived = time.monotonic()
                        with self.frame_condition:
                            if self.last_frame_arrival is not None:
                                sample = arrived - self.last_frame_arrival
                                if 0.015 <= sample <= 1.0:
                                    self.preview_interval = (
                                        self.preview_interval * 0.92 + sample * 0.08
                                    )
                            self.last_frame_arrival = arrived
                            self.preview_frames.append(frame)
                            self.frame_condition.notify_all()
                        if writer is None:
                            width, height = jpeg_dimensions(frame)
                            writer = MjpegAviWriter(self.working_file, width, height)
                        writer.add_frame(frame)
                        now = time.monotonic()
                        if now - last_update >= 0.5:
                            fps = writer.frames / writer.elapsed
                            size_mb = writer.file.tell() / 1_048_576
                            message = (
                                f"录像中：{writer.width}x{writer.height} | {fps:.1f} fps | "
                                f"{writer.frames} 帧 | {size_mb:.1f} MB"
                            )
                            self.root.after(0, self.status.set, message)
                            last_update = now
        except Exception as exc:
            if not self.stop_event.is_set():
                error = exc
        finally:
            self.current_response = None
            if writer is None:
                if error is None:
                    error = RuntimeError("未收到任何图像帧")
            else:
                try:
                    writer.close()
                    writer = None
                    os.replace(self.working_file, self.current_file)
                except Exception as exc:
                    error = exc
            if error is None:
                self.root.after(0, self.finish_ok)
            else:
                self.root.after(0, self.finish_error, str(error))

    def finish_ok(self):
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status.set(f"已保存：{self.current_file}")

    def finish_error(self, error):
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status.set(f"录像停止：{error}")
        messagebox.showerror("录像停止", error)

    def on_close(self):
        if self.close_requested:
            return
        self.close_requested = True
        self.closing = True
        self.stop()
        with self.frame_condition:
            self.frame_condition.notify_all()
        self.wait_for_close()

    def wait_for_close(self):
        if self.worker is not None and self.worker.is_alive():
            self.status.set("正在完成录像文件，请勿强制关闭...")
            self.root.after(100, self.wait_for_close)
            return
        self.preview_server.shutdown()
        self.preview_server.server_close()
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    RecorderApp(window)
    window.mainloop()

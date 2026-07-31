# 给 AI 的 Windows 环境安装提示词

把下面整段内容复制给能够操作本机文件和终端的 AI。建议先把 ESP32S3-Cam 接到电脑，并告诉 AI 仓库准备放在哪个目录。

```text
你是我的 Windows 环境部署助手。请直接检查并配置这台电脑，让下面的 ESP32S3-Cam 图传项目能够使用，不要只给我教程；在需要管理员权限、下载安装程序或烧录硬件时再向我申请确认。

项目仓库：
https://github.com/125090390shuaige-design/diansai.git

硬件和已验证电脑所用的完全一致：
- ESP32-S3 Cam 模块
- GC2145 摄像头
- 8 MB Flash
- OPI PSRAM
- 使用 USB 串口连接电脑

目标效果：
- 使用仓库中的 CameraWebServer_STA_0x0.bin。
- 开发板连接 2.4 GHz 手机热点：名称 nihao，密码 welcometohere。
- Windows 运行“启动录像工具.bat”。
- 预览为 HVGA 480×320、JPEG 质量 70，并限制 GC2145 暗处最长曝光档以优先保证帧率。
- 电脑端缓存约 4 秒，不主动抽帧，按录像平均帧率匀速预览。
- 录像保存为 MJPEG AVI。

请按以下顺序完成：

1. 检查系统
- 确认是 Windows 10 或 Windows 11 64 位。
- 检查网络、剩余磁盘空间和当前用户是否可以安装软件。
- 检查仓库目录是否已经存在；存在时先查看 git status，保留用户未提交的修改，不得删除或覆盖。
- 不存在时克隆仓库；如果没有 Git，优先通过 winget 安装官方 Git for Windows，然后克隆。

2. 安装并验证 Python
- 检查 C:\Program Files\Python314\python.exe。
- 如果不存在，优先通过 winget 或 python.org 官方安装包安装 Python 3.14 64 位。
- 安装时必须包含 Tcl/Tk 和 tkinter，并尽量安装到 C:\Program Files\Python314。
- 不需要安装 OpenCV、FFmpeg、NumPy、Pillow 或任何 pip 第三方库；esp32_cam_recorder.py 只使用 Python 标准库。
- 安装后运行以下验证：
  - Python版本必须能正常输出。
  - 执行 import tkinter，必须成功。
  - 对“recorder/esp32_cam_recorder.py”执行 python -m py_compile，必须无错误。
- 如果 Python 安装在其他目录，不要复制或伪造 python.exe；只修改“启动录像工具.bat”中的 PYTHON_EXE，使其指向真实解释器，并告诉我改了什么。

3. 检查浏览器和 BAT
- 优先检查 Microsoft Edge；脚本找不到 Edge 时可以使用系统默认浏览器。
- 检查根目录的“启动录像工具.bat”存在，并且“recorder/esp32_cam_recorder.py”存在。
- 从终端运行一次 BAT，不能闪退；如果失败，保留完整错误信息并修复。
- 不要为了修复环境而改变预览缓存、录像格式、摄像头分辨率、JPEG质量或Wi-Fi配置。

4. 检查 USB 串口
- 连接开发板后检查设备管理器和可用 COM 端口。
- 根据硬件 ID 判断 USB 串口芯片；只有确认缺少驱动时，才从芯片厂商官方来源安装对应驱动（例如 CH340/CH343 或 CP210x），不要使用第三方驱动网站。
- 使用仓库中的 UartAssist.exe 或其他串口工具，以 115200、8N1、无流控打开正确 COM 口。

5. 检查固件
- 计算 CameraWebServer_STA_0x0.bin 的 SHA-256，预期为：
  68A904328DE688885FFDFF6ED03BC81614AF2FEF44C1A608C4367244D58736E9
- 如果开发板已经烧录该版本，不要重复烧录。
- 如果需要烧录，打开根目录的 flash_download_tool_3.9.7.exe，并参考根目录的“烧录配置说明.txt”。启动后检查：
  - ChipType：ESP32-S3
  - WorkMode：Develop
  - 只选择 CameraWebServer_STA_0x0.bin
  - 地址：0x0
  - 勾选 DoNotChgBin
  - 先 ERASE，再 START
  - 完成后按 RESET
- 烧录是硬件写入操作，执行前先向我确认。
- 不要重新编译固件，除非我明确要求；不要修改热点名称、密码、引脚、分辨率或编码参数。

6. 做端到端验证
- 提醒我把手机热点设置为 2.4 GHz/最大兼容性，名称 nihao，密码 welcometohere。
- 电脑也连接同一个热点。
- 串口应看到 WiFi connected、Camera Ready 和摄像头 IP。
- 运行 BAT，填写该 IP，开始录像。
- 等待约 4 秒缓存后应出现全屏预览；这段延迟是正常设计。
- 至少测试 30 秒：预览持续、录像文件生成、停止后 AVI 能打开。
- 录像时不要另外打开开发板原始视频网页，避免建立第二路上游视频连接。

7. 最终向我报告
- Python和Tkinter版本及安装位置。
- 串口名称和驱动状态。
- 是否烧录；如果烧录，使用的BIN哈希。
- 摄像头IP。
- BAT、预览和30秒录像测试结果。
- 你修改过的文件及具体修改内容。
- 尚未解决的问题和完整错误信息。

安全要求：
- 不删除仓库外的任何文件。
- 不覆盖用户未提交的修改。
- 不从非官方网站下载驱动或Python。
- 不擅自更改固件参数或Wi-Fi凭据。
- 遇到需要登录、管理员权限、烧录或防火墙放行时，先向我确认。
```

## 效果一致性的说明

相同硬件、相同固件和相同软件参数可以保证处理流程一致，但实际帧率仍会受到手机热点信号、2.4 GHz 干扰、电脑性能和USB供电稳定性的影响。环境安装完成后，应以30秒预览与录像测试作为最终验收。

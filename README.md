# ESP32S3-Cam 图传程序

本仓库保存当前可用的 ESP32S3-Cam 图传固件、源码、JPEG 编码依赖和 Windows 平滑预览/录像工具，方便后续继续修改。

## 当前配置

- 摄像头：GC2145
- Wi-Fi STA 热点名称：`nihao`
- Wi-Fi 密码：`welcometohere`
- 默认分辨率：HVGA 480×320
- JPEG 质量：70
- 图传协议：HTTP MJPEG
- 编码器：Espressif `esp_new_jpeg` 1.0.0
- 优化：ESP32-S3 SIMD、双核 JPEG、DRAM 分块、双帧缓冲、关闭 Wi-Fi 休眠
- 电脑预览：约 4 秒缓存、不抽帧，按录像平均帧率匀速播放
- Flash SPI：DIO 80 MHz（最终BIN头已写入80 MHz）

## 目录

- `CameraWebServer_STA_0x0.bin`：可直接从地址 `0x0` 烧录的合并固件。
- `flash_download_tool_3.9.7.exe` 与 `configure/`：根目录烧录程序和必要配置。
- `烧录配置说明.txt`：烧录界面的完整参数和操作顺序。
- `固件源码/CameraWebServer_STA/`：Arduino 固件源码。
- `固件源码/libraries/ESP_New_JPEG/`：编译所需的预编译 JPEG 库。
- `recorder/esp32_cam_recorder.py`：Windows 平滑预览和 MJPEG AVI 录像工具。
- `启动录像工具.bat`：录像工具启动入口。
- `文档/README_烧录说明.txt`：烧录和连接步骤。
- `文档/版本信息.txt`：当前固件参数和 SHA-256。
- `给AI的环境安装提示词.md`：在其他 Windows 电脑上交给 AI 执行的自动部署与验收提示词。
- `UartAssist.exe`：查看115200波特率串口日志和摄像头IP。
- `wifi设置.txt`：当前手机热点名称和密码。

## 烧录

双击根目录的 `flash_download_tool_3.9.7.exe`，详细参数见 `烧录配置说明.txt`。关键设置：

1. 芯片选择 ESP32-S3。
2. 确认固件行左侧已经勾选，地址为 `0x0`。
3. 确认勾选 `DoNotChgBin`。
4. 选择正确 COM 口，建议先擦除，再开始烧录。

Flash Download Tool右侧显示的 `crystal: 40 MHz` 是ESP32-S3主晶振，不是Flash SPI频率。使用本项目合并BIN并勾选 `DoNotChgBin` 时，以BIN头中的DIO 80 MHz为准。

## 电脑端使用

1. 电脑和开发板连接同一个热点。
2. 双击 `启动录像工具.bat`。
3. 填写串口输出的摄像头 IP。
4. 点击开始录像，程序会自动打开全屏平滑预览。

录像工具不会二次压缩 JPEG，只把收到的帧封装为 AVI。预览完整缓存收到的帧并增加约 4 秒延迟，用更大的缓存换取与录像结果一致的连续播放。

## 编译环境

- ESP32 Arduino Core 2.0.11
- Board：ESP32S3 Dev Module
- Flash：8 MB
- Partition Scheme：Huge APP
- PSRAM：OPI PSRAM

将 `固件源码/libraries/ESP_New_JPEG` 复制到 Arduino 用户库目录后，再编译 `固件源码/CameraWebServer_STA`。

## 提醒

Wi-Fi 名称和密码目前直接保存在源码中。如果仓库公开，任何人都能看到这两个值；修改热点信息后必须重新编译和烧录固件。

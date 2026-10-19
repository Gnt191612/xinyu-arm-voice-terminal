# 心语 ARM 语音交互终端

本项目是嵌入式系统课程的协作开发原型：ARM板端采集音频，用A32汇编完成声音活动门控，再由电脑进行中文语音识别、调用既有心语文本服务、合成语音并通过电脑外放。当前请优先阅读[无HUB方案](无HUB方案.md)，下文旧板端播放步骤仅供兼容参考；USB音频、RNDIS和板端运行时仍需固件适配及实机验收。

本仓库只包含新增源码与复现说明，**不包含心语权重、训练数据、语音记录、个人信息或访问令牌**。新增代码采用[MIT许可证](LICENSE)，第三方模型与组件仍遵守各自许可，详见[第三方说明](THIRD_PARTY_NOTICES.md)。部分代码由AI辅助编写，协作者须实际验证并理解其行为。

## 方案和当前边界

目标硬件为LCPI-PC-T113、USB麦克风以及USB供电、3.5mm输入的HA-210音箱。硬件已到货，实物芯片标T113-S3。麦克风USB传输音频，音箱USB只供电，3.5mm才是音频输入。固件、驱动、网络、ABI和音频接线仍待实测确认，不保证任意镜像即插即用。环境清点与部署见[商家资料核查与部署](商家资料核查与部署.md)。

流程为按回车录制5秒（`--seconds` 可调 1～15 秒） → ARM处理20毫秒PCM帧 → 有连续声音才上传 → Vosk转文字 → 心语回复 → Windows中文语音合成 → 电脑外放（无HUB方案默认；板端播放仅兼容保留）。采用半双工，不实现唤醒词、全双工或回声消除。声音门限不是人声分类器，持续噪声可能误触发。

当前已验证：电脑端自动测试、A32实际机器码执行、模拟客户端、中文TTS与Vosk，以及**T113实机整条链路一轮**（板端USB麦克风采集 → 板端 `libpcm_gate.so` 汇编门控 → RNDIS上传 → 识别 → 心语 → 合成 → 电脑外放，用户确认听到）。尚未验证：连续多轮稳定性与板端本地播放。详见[验证状态](验证状态.md)。电脑时间、指令执行次数和ARM7模拟结果不代表T113性能。

## 演示快捷方式（Windows）

| 文件 | 作用 |
|------|------|
| `演示_1_启动电脑桥接.cmd` | 启动电脑桥接（真实模式，监听 `config.json` 中的地址，默认 `192.168.113.1:8765`） |
| `演示_2_板端跑一轮.cmd` | 自动找 adb → 推送板端脚本 → 提示说话 → 板端录 5 秒并走完整链路 |
| `演示_3_板端终端.cmd` | 打开板端 shell，排查用 |
| `tools/board_round.sh` | 板端执行体：`arecord plughw:2,0` → 汇编门控 → RNDIS 上传 |

顺序：先开 `演示_1`（保持窗口），再双击 `演示_2`，看到提示后对着板子麦克风说一句话。板端需已部署
`/mnt/UDISK/xinyu-runtime35`（Python 3.5.6）与 `/mnt/UDISK/xinyu-arm-check`（客户端与 `libpcm_gate.so`）。

## 快速开始

电脑端使用Windows64位和Python3.11；离线门控和模拟接口测试也可在其他支持Python的平台运行。心语是独立服务，本仓库不重新加载或训练它。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-test.txt
.\.venv\Scripts\python.exe tools/init_config.py
.\.venv\Scripts\python.exe tools/run_tests.py
.\.venv\Scripts\python.exe tools/check_client.py
```

`init_config.py`只在配置不存在时创建随机令牌，不覆盖现有配置。`config.json`不得提交。以上测试无需心语或真实设备，模拟回复和440Hz测试音都有明确标记，不是实际模型输出。

下载中文识别模型，校验ZIP后解压：

```powershell
New-Item -ItemType Directory -Path models -Force
curl.exe -L --fail --ssl-revoke-best-effort -o models/vosk-model-small-cn-0.22.zip https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
.\.venv\Scripts\python.exe tools/prepare_model.py
.\.venv\Scripts\python.exe tools/check_speech.py
```

模型官方标注约42MB。准备脚本检查体积、ZIP CRC和路径安全，记录本次SHA256；它不是官方签名验证。请从项目目录运行，避免Windows下Vosk的中文绝对路径兼容问题。`check_speech.py`生成合成语音并识别，不自动播放、不冒充真人输入。

启动你有权使用的心语服务，默认本机地址`http://127.0.0.1:7860`。服务应支持GET `/health`与POST `/chat`：

```json
{"history": [{"role": "user", "content": "你好"}]}
```

回复须包含非空`response_text`。心语项目可能需要独立访问授权，不承诺公开可下载其权重。确认正确模型版本后启动真实桥接：

```powershell
.\.venv\Scripts\python.exe tools/check_xinyu.py
.\.venv\Scripts\python.exe pc_server.py
```

桥接默认仅监听127.0.0.1:8765。板端接入需使用可信专网的实际IP和随机令牌，不将服务开放到公网。完整配置、板端编译与取证见[运行说明](运行说明.md)。

## 文件职责

- `audio_core.py`：PCM16 WAV校验、参考门控和ARM动态库接口。
- `pc_server.py`：Vosk、心语HTTP调用、Windows中文TTS和原始记录。
- `board_client.py`：ALSA录音、门控、上传和播放；文件联调需显式`--reference`。
- `arm/pcm_gate.S`：T113 Linux工具链使用的A32汇编。
- `arm/pcm_gate_ads.s`：相同指令的ADS语法版本。
- `arm/compare.c`、`reference.c`、`Makefile`：同输入C与汇编结果及时间对比。
- `arm/axd_demo.c`、`axd_start.s`：课堂独立运行和取证源码。
- `tools/verify_arm.py`：Unicorn执行ADS生成的实际机器码，记录寄存器和输入内存变化。
- `tests/test_project.py`：正常、边界、干扰与协议测试。

汇编实质使用LDRSH后变址、RSBLT、ADD、SUBS/BNE、MUL/CMP、条件执行和BX返回。空帧无效，阈值相等有效，`-32768`先符号扩展再取绝对值；样本数最大65535保证累加与门限乘积不溢出。r0-r2传参、r0返回，只使用调用者保存寄存器。不能以无关加法或反汇编截图替代项目验证。

## 协作

按[协作说明](CONTRIBUTING.md)建立功能分支、提交小改动和测试证据。不提交私人日志、访问令牌或模型文件，不伪造实机成功，不预设汇编比优化C更快。首次公开发布是可验证的开发原型，不是最终课程报告。

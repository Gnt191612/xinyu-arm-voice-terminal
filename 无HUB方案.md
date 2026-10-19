# 当前方案：开发板采集，电脑外放

本方案替代旧文档中“HOST接HUB、USB声卡和音箱”的部署步骤。旧板端播放仅作为兼容模式保留。

接线：T113的HOST直连USB麦克风；OTG连接电脑，计划使用RNDIS专网传输。音箱连接电脑的音频输出并正常供电，也可以使用电脑自带扬声器。板端不接HUB、不需要USB声卡或播放设备。

链路：USB麦克风 → T113录制16kHz单声道PCM16 → ARM汇编门控 → OTG/RNDIS上传 → 电脑Vosk识别 → 心语对话 → 中文TTS → 电脑默认音频设备同步播放。电脑播放命令完成后才返回本轮响应，下一轮由回车开始，避免边播放边录音。电脑模式不把回复音频回传开发板。

电脑启动（在项目目录，沿用已有Python依赖与私有config.json）：

```powershell
python pc_server.py --playback-target pc
```

板端部署环境就绪后启动（地址必须替换为实际确认的电脑RNDIS地址；设备ID通过arecord -l核对，不能照抄）：

```sh
export XINYU_BRIDGE_TOKEN='与电脑配置相同的令牌'
python3 board_client.py --server http://电脑RNDIS地址:8765 --capture-device plughw:CARD=实际麦克风ID,DEV=0 --playback-target pc --records-dir /mnt/UDISK/xinyu-records
```

须先确认UDISK实际挂载点。电脑config.json的listen_host必须绑定已确认的RNDIS地址，或在可信专网内按需绑定；默认127.0.0.1不能供板端访问。不要开放公网端口。两端播放模式必须一致。

兼容旧方案：电脑使用--playback-target board，板端同时使用--playback-target board及--playback-device。该模式才会回传WAV并调用aplay。

当前阻碍：已检查的原固件未启用CONFIG_SND_USB_AUDIO及CONFIG_USB_CONFIGFS_RNDIS，也没有Python运行时。仍需在匹配的Tina SDK中补齐USB麦克风驱动、保留ADB的RNDIS配置、Python及ARM动态库，再实际部署。代码修改不能替代这些固件工作，不应直接把现有TF卡当作新方案已部署完成。

验收顺序：确认USB麦克风枚举及录音 → 核对真实ARM汇编结果 → 测试OTG网络上传 → 真实识别和心语回复 → 电脑实际出声。自动测试只验证协议和逻辑，记录中的播放命令完成不等于人耳确认出声。录音可能收进电脑外放，先采用半双工并保持麦克风与音箱距离。

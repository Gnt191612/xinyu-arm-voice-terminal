# 第三方组件与许可边界

本仓库MIT许可证只覆盖新增的桥接、音频门控、汇编、测试与说明文件，不改变下列第三方组件或模型的许可。安装依赖不意味着它们被重新许可为MIT。

- Vosk语音识别API：https://github.com/alphacep/vosk-api ，按其Apache许可证使用。
- `vosk-model-small-cn-0.22`：https://alphacephei.com/vosk/models ，官方模型列表标注Apache 2.0；模型不入本仓库，下载后保留其许可和来源。
- 心语服务：https://github.com/Gnt191612/xinyu-companion ，独立部署，不复制其完整服务、训练数据或权重。integration/task_intent.py仅为本次终端集成新增的明确任务判断与提示。该仓库可能为私有，协作者需独立取得使用权限。
- Qwen2.5-3B-Instruct是心语当前使用的基座；其模型与适配器不入本仓库。使用者须遵守实际取得版本的Qwen研究许可及相关限制，不能以本仓库MIT许可证主张无条件商用权。
- Unicorn：https://github.com/unicorn-engine/unicorn ，仅用于本地ARM指令验证；Python包与底层引擎应按各自随附许可证使用，不能将整套依赖视为本项目MIT代码。
- Windows System.Speech由系统提供，需合法安装的Windows和可用中文语音包，本仓库不分发系统声音。
- 实时AEC使用SpeexDSP 1.2.1，官方源码附带的BSD风格许可及版权声明应保留；本仓库仅提供调用管道及构建脚本，不分发其源码归档或二进制。
- sherpa-onnx与SenseVoice模型分别遵守其发布版本的许可，不能以本仓库MIT替代。模型及依赖不进入仓库，下载时保留上游许可。
- sounddevice、WebRTC VAD和NumPy按各自安装包的许可使用。Microsoft Yaoyao通过本机WinRT语音接口使用，不分发音色文件。
- ADS/CodeWarrior/AXD为可选课堂工具，需用户合法持有，本仓库不分发工具、授权文件或编译产物。ARM Linux动态库使用匹配固件的GNU或厂商工具链。

调用约定参考：https://github.com/ARM-software/abi-aa/blob/main/aapcs32/aapcs32.rst 。本仓库没有复制标准全文。

第三方模型、软件和许可可能更新，分发或商用前应核验实际取得的版本。原始语音与对话可能包含个人信息，默认只保存在本地，分享前须有参与者授权并脱敏。

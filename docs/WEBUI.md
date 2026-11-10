# Chronos Document WebUI 1.1.4

独立运行的英文 PDF 到中文翻译器。模型来自 Yufeng Zhan 的 [Project_Chronos](https://github.com/FonaTech/Project_Chronos)。本程序与技能版分别发布，安装技能时不会安装或调用它。

## 下载哪个文件

在 [Translation Skills 1.0.3 Release](https://github.com/FonaTech/Translation_Skills/releases/tag/v1.0.3) 的附件中选择：

| 文件 | 用途 |
|---|---|
| [Translation_Skills_v1.0.3.zip](https://github.com/FonaTech/Translation_Skills/releases/download/v1.0.3/Translation_Skills_v1.0.3.zip) | 安装到 Codex、Claude Code、OpenCode 或 Clouds_Coder 的技能包 |
| [Chronos-Document-WebUI-v1.1.4.zip](https://github.com/FonaTech/Translation_Skills/releases/download/v1.0.3/Chronos-Document-WebUI-v1.1.4.zip) | 独立程序源码、随附 Chronos 权重、解析与排版资源、离线编辑器 |
| 各 ZIP 对应的 `.sha256` 文件 | 下载完整性校验 |

程序版有自己的运行副本、依赖和版本号。其代码与权重只随程序附件分发，不进入技能的运行目录。源码包需要安装 Python 和依赖，不是免安装可执行文件。

## 启动

1. 安装 64 位 Python 3.12 或 3.13，解压程序包。
2. macOS 双击 `start.command`；Windows 双击 `start.bat`；Linux 运行 `bash start.sh`。
3. 首次启动需要联网安装 Python 依赖与 Chromium。翻译权重已包含在包内，安装后推理在本机进行。
4. 浏览器打开 `http://127.0.0.1:3930`，上传 PDF。原件、任务进度、译文和导出文件保存在程序的 `data/` 目录。

已有可用依赖环境时，可运行 `python launch.py`。关闭启动窗口会停止本次启动的服务。程序默认提供局域网访问，以直接连接 IP 区分文档空间；同一 IP 共用历史。需要仅在本机使用时，将 `HOST` 设为 `127.0.0.1`。这套 IP 空间机制不等同于账号认证。

## 与技能版的区别

| 项目 | 技能版 1.0.3 | 程序版 1.1.4 |
|---|---|---|
| 翻译模型 | agent 客户端当前模型 | 随包 Project_Chronos 本地模型 |
| 输入 | 技能支持的多种文档 | 当前 WebUI 接收 PDF |
| 翻译方向 | 按请求选择语言 | 英文到简体中文 |
| 译文 | 忠实全译、理解性译写、原文对照 | 中文阅读版、中英逐单元对照 |
| 运行方式 | 在支持技能的客户端内运行 | 独立 Python 服务和浏览器 |

程序还导出 CSV、自动检查报告、布局标注 HTML 和离线编辑器。PDF 路径不使用 OCR；没有可恢复原生文字的扫描内容会保留源图并标记。自动数字、覆盖和排版检查不包含完整语义复核。

模型与第三方组件保留随包许可证。具体参数、历史保留设置和升级方法见程序包内 README。

## 使用范围

程序版当前适合试用与逐项校对。科研文献需要核对专业术语、限定条件、作者信息、公式和图表；自动完成流水线不等于译文已通过语义复核。图形外观检查覆盖已识别区域，不能证明原文所有图形均已识别。请同时打开源 PDF 检查图形缺漏，并查看 `needs_attention` 状态和检查报告。

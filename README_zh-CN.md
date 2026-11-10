# Translation Skills · 文档翻译技能

将文档译成两个完整版本，生成 HTML、PDF 和原文对照册。

[English](README.md) · [安装说明](docs/INSTALL.md) · [操作流程](docs/WORKFLOW.md) · [支持格式](docs/SUPPORT.md)

Yufeng Zhan · MIT · v1.0.3

Translation Skills 可用于 Codex、Claude Code、OpenCode 和 Clouds_Coder。你可以翻译一份文件，也可以按指定顺序合编多份手册、报告、文章、故事或其他材料。文件范围、目标语言和阅读对象由你决定。

译文由客户端当前使用的模型完成。本地脚本负责提取原文、标记段落、检查遗漏并排版，无需另配翻译 API。客户端读取文件时，仍适用该客户端自身的数据处理方式。

## 会得到什么

| 产物 | 用途 |
|---|---|
| 忠实全译版 | 完整翻译所选内容，保留事实、语气、限定条件、数字、注释和引用。 |
| 理解性译写版 | 保留同样的内容和细节，面向阅读对象调整表达，例如澄清指代、拆开长句。 |
| 原文对照册 | 并列呈现原文和两个译文，附段落编号及原文页码或元素位置，提供 HTML、PDF 和 CSV。 |

表格、图注、脚注和图内文字也属于翻译范围。无法辨认的内容，以及保留原文的图内标注，会列出具体位置；额外解释会单独标为译注。

## 开始使用

需要 Python 3.10 或更新版本。PDF 输出和图形核对使用本地 Chromium 浏览器。PDF 提取需要 PyMuPDF 1.26.4 或更新版本。没有可恢复原生文字的 PDF 扫描页保留未完成状态；非 PDF 图片的可选识别工具单独使用。

```bash
git clone https://github.com/FonaTech/Translation_Skills.git
cd Translation_Skills
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-core.txt
python3 -m playwright install chromium
```

环境激活命令适用于 macOS/Linux。Windows PowerShell 使用 `.venv\Scripts\Activate.ps1`。

以 Codex 项目为例，先查看安装位置，再执行复制：

```bash
python3 tools/install.py --targets codex --project /path/to/project
python3 tools/install.py --targets codex --project /path/to/project --apply
```

其他客户端的命令见[安装说明](docs/INSTALL.md)。替换已有技能目录前，安装器会创建备份。运行辅助脚本时，客户端需要能使用装好依赖的 Python 环境。翻译项目保存在技能目录之外。

安装后，可以直接提出需求：

> 使用 document-translation，把 /path/to/manual.pdf 翻译成日语，供初次使用者阅读。生成忠实全译版、理解性译写版和原文对照册，提供 HTML 和 PDF。保留警告、表格和图内标注，并列出无法辨认的内容。

## 1.0.3 更新

- 新增原生表格单元连接模型及独立合并单元格检查，受支持的行列合并可保留到 HTML 分页和 DOCX 导出。
- 改进数学字形、图形归属和字体映射恢复，同时保留原始证据及未解决问题。
- 将重复页眉、页脚和边缘页码从正文翻译中分离，原文记录仍可追溯。
- 文件、控制台和子进程明确使用 UTF-8，并增加 Windows CP936 编码回归。
- PDF 仅使用原生文字、字体轮廓、矢量和页面几何，不再调用 OCR 或页面／表格识字补入；无法恢复的文字保留源图并标记未完成。

详细内容见[变更记录](CHANGELOG.md)和[操作流程](docs/WORKFLOW.md)。

## 独立程序版

同一个 [1.0.3 Release](https://github.com/FonaTech/Translation_Skills/releases/tag/v1.0.3) 另附 **Chronos Document WebUI 1.1.4** 实验程序，使用作者的 [Project_Chronos](https://github.com/FonaTech/Project_Chronos) 翻译模型，在本机提供英文 PDF 到中文的翻译界面。

技能版调用 agent 客户端当前的模型，生成两个完整译文版本；独立程序使用自己的本地模型，生成中文阅读版和中英对照。两者分别下载、安装和运行，详见[程序版下载与启动说明](docs/WEBUI.md)。

## 排版与编辑

初稿参考原文的页面比例、标题层级、栏数和图文关系。译文长度变化后会重新分页，模型需要对照原页与输出页，调整呈现并复查。

生成的 HTML 带有阅读工具栏和离线布局编辑器入口。使用入口时，请将 `document-layout-editor.html` 与译文 HTML 放在同一目录。两个界面均提供 16 种语言，切换界面语言不会改动正文。

编辑器支持导入 HTML 和 DOCX，导出 HTML、浏览器打印 PDF、DOCX、ODT、Markdown、RTF、TXT 及可继续编辑的项目 JSON。复杂 Word 格式和原页精确重建存在限制，详见[格式说明](docs/SUPPORT.md)。

## 参与开发

技能入口位于 [`skills/document-translation`](skills/document-translation/SKILL.md)。其中，`references/` 存放翻译和复核方法，`scripts/` 存放本地处理脚本；仓库根目录下的 `tools/` 用于安装、验证、模型训练和打包。

```bash
python3 -m pip install -r requirements-optional.txt
python3 tools/validate.py
python3 -m pip install pytest
python3 -m pytest tests -q
python3 tools/checksums.py
```

更多内容见[复现检查](docs/REPRODUCIBILITY.md)和[贡献指南](CONTRIBUTING.md)。自动测试覆盖特定的结构和格式行为；译文含义与实际渲染页面仍需直接核对。

## 许可证

原创代码、技能说明、模型参数和作者自有测试材料采用 [MIT](LICENSE) 协议。输入文档和依赖项保留各自许可，见[第三方材料说明](THIRD_PARTY_NOTICES.md)。

# Translation Skills · 文档翻译技能

将文档译成两个完整版本，生成 HTML、PDF 和原文对照册。

[English](README.md) · [安装说明](docs/INSTALL.md) · [操作流程](docs/WORKFLOW.md) · [支持格式](docs/SUPPORT.md) · [示例](skills/document-translation/examples/index.html)

Yufeng Zhan · MIT · v1.0.1

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

需要 Python 3.10 或更新版本。PDF 输出和图形核对使用本地 Chromium 浏览器。扫描件识别可选用 Tesseract 或 macOS Vision。

```bash
git clone https://github.com/FonaTech/Translation_Skills.git
cd Translation_Skills
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-core.txt
python3 -m playwright install chromium
```

上面的环境激活命令适用于 macOS/Linux。Windows PowerShell 使用 `.venv\Scripts\Activate.ps1`。

以 Codex 项目为例，先查看安装位置，再执行复制：

```bash
python3 tools/install.py --targets codex --project /path/to/project
python3 tools/install.py --targets codex --project /path/to/project --apply
```

其他客户端的命令见[安装说明](docs/INSTALL.md)。替换已有技能目录前，安装器会创建备份。运行辅助脚本时，客户端需要能使用装好依赖的 Python 环境。

安装后，可以直接提出需求：

> 使用 document-translation，把 /path/to/manual.pdf 翻译成日语，供初次使用者阅读。生成忠实全译版、理解性译写版和原文对照册，提供 HTML 和 PDF。保留警告、表格和图内标注，并列出无法辨认的内容。

翻译项目会保存在技能目录之外。需要按命令操作时，参见[完整流程](docs/WORKFLOW.md)。

## 排版与编辑

初稿参考原文的页面比例、标题层级、栏数和图文关系。译文长度变化后会重新分页，模型需要对照原页与输出页，调整布局并复查。

生成的 HTML 带有阅读工具栏和布局编辑器入口。编辑器可离线修改文字、页面设置、图片和表格。使用入口时，请将 `document-layout-editor.html` 与译文 HTML 放在同一目录。阅读工具栏和编辑器均提供 16 种界面语言，切换界面语言不会改动文档正文。

编辑器支持导入 HTML 和 DOCX，导出 HTML、浏览器打印 PDF、DOCX、ODT、Markdown、RTF、TXT 及可继续编辑的项目 JSON。复杂 Word 格式和原页精确重建存在限制，详见[格式说明](docs/SUPPORT.md)。

## 查看示例

下载或克隆仓库后，在浏览器中打开[示例展示页](skills/document-translation/examples/index.html)。GitHub 会显示 HTML 源码，页面不会直接运行；各示例的 PDF 可以在 GitHub 中预览。

示例包含中文、日语、阿拉伯语、西班牙语和法语，以及扫描文字重建、图内标注和公开 PDF 选段。示例用于展示输出形式，不能据此推断所有语言和文档的翻译质量。

## 参与开发

技能入口位于 [`skills/document-translation`](skills/document-translation/SKILL.md)。其中，`references/` 存放翻译和复核方法，`scripts/` 存放本地处理脚本；仓库根目录下的 `tools/` 用于安装、检查和打包。

```bash
python3 tools/validate.py
python3 -m unittest discover -s tests -v
python3 tools/checksums.py
```

更多内容见[复现检查](docs/REPRODUCIBILITY.md)、[架构说明](docs/ARCHITECTURE.md)和[贡献指南](CONTRIBUTING.md)。自动检查能发现结构、覆盖和部分格式问题；译文含义与实际渲染页面仍需直接核对。

## 许可证

原创代码、技能说明和作者自有示例采用 [MIT](LICENSE) 协议。输入文档、第三方选段和依赖项保留各自许可，见[第三方材料说明](THIRD_PARTY_NOTICES.md)。

# Translation Skills · 通用文档翻译与整理技能

**忠实全译版 + 理解性译写版，一套可追溯的 HTML/PDF 工作流。**

作者：**Yufeng Zhan**　协议：**MIT**　版本：**1.0.1**

[英文 README](README.md) · [安装说明](docs/INSTALL.md) · [操作流程](docs/WORKFLOW.md) · [排版优化机制](skills/document-translation/references/visual-refinement.md) · [支持格式](docs/SUPPORT.md) · [演示入口](skills/document-translation/examples/index.html)

本项目面向 Clouds_Coder、OpenCode、Claude Code 和 Codex。根据明确的文件路径、附件或授权目录中的候选文档，确定用户需要的材料、合编顺序、目标语言和阅读对象；随后生成两种完整译文及原文对照档案。论文、故事、合同、说明书、表格、报告和多文件集合共用同一套来源与核对规则，没有固化的学科、品牌、单位、中文模板或特定论文要素。

## 两个版本的边界

| 产物 | 内容要求 |
|---|---|
| 忠实全译版 | 完整保留所选内容、事实、限定条件、语气、数字、引用与例外；译文自然，不能偷换含义 |
| 理解性译写版 | 基于相同内容澄清指代、拆解长句、调整表达；不得当成摘要，不得添情节、改义务或加强结论 |
| 逐句／单元对照册 | 原文、双译文、稳定编号、页码或元素位置；一句原文可对应多句译文，保持可追溯关系 |

图内文字、脚注、表格空值、代码标识符、公式与附录同样纳入范围。无法识别的内容保留问题记录，不用猜测补全。新增背景解释必须作为明确标注的译注，而非原作者观点。

## 安装与使用

```bash
python3 -m pip install -r requirements-core.txt
python3 -m playwright install chromium
python3 tools/install.py --targets codex claude opencode --project /path/to/project
python3 tools/install.py --targets codex claude opencode --project /path/to/project --apply
python3 tools/install.py --targets clouds --clouds-root /path/to/skills --apply
```

首次命令只显示安装位置；带 `--apply` 才复制，已有目录会备份。Clouds_Coder 指定其真实技能根目录。生成文档存放在技能目录之外，不污染安装包，也不改客户端全局指令或权限。

向客户端直接提出需求即可，例如：

> 使用 document-translation。把指定文件夹中的用户手册及勘误合编成法语，生成忠实全译版、面向初次使用者的理解性译写版、逐句对照 HTML/PDF。保留警告级别、操作先后、参数、表格和图示；有歧义的版本先列候选，不能擅自替换。

翻译由调用技能的模型完成。脚本负责取文、编号、任务交换、检查、排版和归档，**脚本本身不包含翻译模型，也不会无提示上传文件**。CLI 详细步骤见 [WORKFLOW](docs/WORKFLOW.md)。

## 布局与核对

- 首轮依据输入文档的实际页面、阅读顺序、栏数、层级、图表比例及留白设计，不把某一篇的模板强套到其他文件。
- 输出页标明所对应的原文页。模型需要亲自查看原页和实际渲染页，逐页检查字体、图表、图注、表格、标题、页脚和疏密；记录问题后提交呈现补丁，重新渲染并复查。
- 图像与图注作为一体处理，表题与表格相连，长表续页重复表头，列宽和图像尺寸实际测量。只有源版式严重且无法调整时，才按匹配度尝试24种版式预设。
- 提取、双版本译文及所有输出 PDF 页都有绑定当前快照与图像哈希的覆盖清单。检查工具不能代替模型实际查看，布局分数也不是审美判断。
- 几何、数字、覆盖与哈希检查只辅助核对；不能把脚本通过或 OCR 高置信度称为翻译正确证明。

## 内置资料与验证范围

包内包含跨领域案例、不同版式 demo、提取与 OCR 脚本、24种回退版式、可复用的页面核对工作流，以及内置 HTML 编辑器。格式能力、转换路径和边界见 [支持格式说明](docs/SUPPORT.md)。

运行单元及格式回归：`python3 -m unittest discover -s tests -v`。真实语义压力测试要求调用模型逐项翻译并核对，不能用源文回填冒充；四个宿主平台目前提供安装和资源契约，不代表完成了所有客户端的交互式端到端测试。可复现实测步骤见 [REPRODUCIBILITY](docs/REPRODUCIBILITY.md)。

## 发布

已准备 README、MIT 协议、贡献说明、变更记录、GitHub Actions、Claude 插件元数据、校验清单和打包工具。[GitHub 上传步骤](docs/UPLOAD_zh-CN.md)供上传到 FonaTech 使用；本项目不会自动创建仓库或发布。

本仓库原创代码、方法和自有案例采用 MIT；第三方 PDF、译文片段及字体的权利独立，未将用户原始材料纳入公开包。

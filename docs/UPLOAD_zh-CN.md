# 上传到 FonaTech

建议仓库名：`Translation_Skills`。作者为 **Yufeng Zhan**，协议为 **MIT**。这是待上传的本地发布包，未替你创建、推送或公开仓库。

1. 解压发布 ZIP，进入其中的 `Translation_Skills` 目录，确认根目录直接包含 `README.md`、`LICENSE`、`skills/` 与隐藏的 `.claude-plugin/`、`.github/`。
2. 查看 `skills/document-translation/examples/index.html`，确认示例素材许可记录；阅读 `docs/SUPPORT.md` 和 `docs/REPRODUCIBILITY.md`。
3. 执行 `python3 tools/validate.py`、`python3 -m unittest discover -s tests -v` 和 `python3 tools/checksums.py`。
4. 在 GitHub 的 FonaTech 组织下创建空仓库，自行选择公开或私有；不要再生成第二份冲突的 LICENSE。
5. 在你准备好的本地仓库执行以下命令。URL 是建议名称，若实际仓库名不同请替换。

```bash
git init
git add .
git commit -m "Release portable document translation skills v1.0.1"
git branch -M main
git remote add origin https://github.com/FonaTech/Translation_Skills.git
git push -u origin main
```

网页手动上传可能忽略隐藏目录，优先使用 Git。确认 README 相对链接、Demo PDF 和 workflow 均存在。验证通过后可自行创建 v1.0.1 tag/release，附 ZIP 与 SHA-256。修改文件后先更新 VERSION/CHANGELOG，再用 `tools/checksums.py --write` 和 `tools/pack_release.py` 重新打包。

本地安装不是 GitHub 发布；安装脚本不会推送任何内容。用户私人 PDF 和此次具体论文译文已与通用技能包分开。

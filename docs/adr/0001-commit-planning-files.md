# 提交 Planning Files

GCW 会将 planning files 提交到 Issue 分支的 `.gcw/issues/<issue-id>/` 下，推送到 Git hosting platform，从 issue progress comment 链接这些文件，并允许它们出现在 review request diff 中，最终随 base branch 合并。

这样做可以通过稳定的远程链接保留 agent planning、findings、progress 和 review context，避免 workflow 的工作记忆只隐藏在聊天或本地文件里。代价是仓库历史会保留 GCW collaboration metadata，项目接受这一点。

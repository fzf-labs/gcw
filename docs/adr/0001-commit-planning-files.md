# 提交 Planning Files

GCW 会将 planning files 提交到 Issue 分支中的 `.gcw/issues/<issue-id>/`，推送到 Git hosting platform，并在 issue progress comment 中链接这些文件。它们也会出现在 review request diff 中，并可能随 base branch 一起合并。

这样做可以通过稳定的远程链接保留 agent 的计划、发现、进展和 review 上下文，避免工作流记忆只存在于聊天记录或本地文件里。对应的代价是：仓库历史会保留 GCW 协作元数据。项目接受这个取舍。

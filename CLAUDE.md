## Agent skills

### Issue tracker

Issues 通过 GitHub Issues 管理，使用 `gh` CLI 操作。详见 `docs/agents/issue-tracker.md`。

### Triage labels

使用五个默认分流标签：needs-triage、needs-info、ready-for-agent、ready-for-human、wontfix。详见 `docs/agents/triage-labels.md`。

### Domain docs

单一上下文布局：仓库根目录的 `CONTEXT.md` + `docs/adr/`。详见 `docs/agents/domain.md`。


## 重要约定

- 所有回复和 Git Message 均使用中文
- 创建新的自定义 Skill 时，统一使用 `wwj-` 前缀命名
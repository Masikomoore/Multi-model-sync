# Changelog

## 2026-10-06

- 在安装模板中加入 `glm-5.3`。参数来自智谱官网：仅文本、1M 上下文（1048576）、思考档 `low`/`high`/`max`，默认 `max`。
- 同步时如果本地目录没有同族模板，会使用安装模板里的对应条目。已有目录因此可以直接同步 `glm-5.3`。

## 2026-10-05

- 增加 xclis 模型同步触发。Codex 显式调用为 `$xclis-sync`。
- 「同步xclis模型」「更新xclis模型」「升级xclis模型」按技能描述隐式触发同一套目录同步。
- 记录当前 Codex CLI 会拒绝未知斜杠命令 `/xclis-sync`。安装目录仍是 `~/.codex/skills/codex-model-sync`。

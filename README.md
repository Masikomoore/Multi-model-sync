# Codex Model Sync

一个可安装到 Codex 的 Skill：从中转站公开模型清单中选择指定分组，并同步更新本地 Codex 自定义模型目录，无需手工编辑 JSON。

## 特性

- 优先读取中转站公开 JSON 接口，不依赖页面 DOM 抓取。
- 默认只执行 dry-run；只有显式传入 `--apply` 才会写入本地目录。
- 保留已有模型的完整配置；新模型只从同族模板克隆，不猜测上下文、工具或推理能力。
- 默认排除图像计费模型。
- `--prune` 为显式删除开关，用于将本地目录镜像为指定分组。
- 更新前自动生成时间戳备份，并使用原子替换写入。
- 支持使用 `--payload` 导入已捕获的 JSON，便于测试或需要浏览器会话的中转站。

## 安装

在 macOS/Linux 上执行：

```bash
./install.sh
```

默认安装到：

```text
~/.codex/skills/codex-model-sync
```

也可以指定安装目录：

```bash
CODEX_HOME=/custom/codex ./install.sh
```

安装后重启 Codex，使 Skill 被重新发现。

## 使用

先执行 dry-run：

```bash
~/.codex/skills/codex-model-sync/scripts/sync_catalog.sh \
  --source-url https://xclis.ai/pricing \
  --group 'GPT-稳定-STABLE' \
  --platform openai \
  --catalog ~/.codex/model-catalogs/custom-models.json
```

确认差异后应用：

```bash
~/.codex/skills/codex-model-sync/scripts/sync_catalog.sh \
  --source-url https://xclis.ai/pricing \
  --group 'GPT-稳定-STABLE' \
  --platform openai \
  --catalog ~/.codex/model-catalogs/custom-models.json \
  --apply
```

如果需要删除本地存在、但分组中已不存在的模型：

```bash
.../sync_catalog.sh ... --apply --prune
```

`--prune` 使用前应先查看 dry-run 的删除列表。默认不删除本地独有模型。

## 参数

| 参数 | 说明 |
| --- | --- |
| `--source-url` | 中转站定价页、公开 JSON 地址或 API 基地址 |
| `--group` | 精确分组名称 |
| `--platform` | 可选平台过滤，例如 `openai` |
| `--catalog` | Codex 自定义模型文件，默认 `~/.codex/model-catalogs/custom-models.json` |
| `--payload` | 使用本地 JSON 响应文件，不联网请求 |
| `--apply` | 写入目录；省略时为 dry-run |
| `--prune` | 删除分组中不存在的本地模型 |
| `--include-image` | 包含图像计费模型 |
| `--template-slug` | 为新模型指定模板，可重复传入 |
| `--json` | 输出机器可读 JSON |

## 安全行为

- 只请求公开 JSON 接口，不自动提交 Cookie、API Key 或 Bearer Token。
- 分组不存在、匹配多个平台、模型为空、模型重复或新模型缺少安全模板时会停止。
- `--prune` 会启用模型数量缩减保护，避免异常接口响应造成大规模删除。
- 每次应用都会生成类似以下备份：

```text
custom-models.json.bak-20260930-120000-GPT---STABLE
```

回滚：

```bash
cp /path/to/custom-models.json.bak-YYYYMMDD-HHMMSS-group \
   /path/to/custom-models.json
```

应用后重启 Codex。

## 开发与验证

本项目只使用 Python 标准库：

```bash
python3 scripts/test_sync_catalog.py
python3 -m py_compile scripts/sync_catalog.py scripts/test_sync_catalog.py
```

Skill 结构校验：

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

## 目录结构

```text
.
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── catalog-schema.md
│   └── research-brief.md
├── scripts/
│   ├── sync_catalog.py
│   ├── sync_catalog.sh
│   └── test_sync_catalog.py
├── install.sh
├── LICENSE
└── README.md
```

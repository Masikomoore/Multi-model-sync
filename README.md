# Codex Model Sync

一个可安装到 Codex 的 Skill：从中转站公开模型清单中选择指定分组，并同步更新本地 Codex 自定义模型目录，无需手工编辑 JSON。

## 特性

- 优先读取中转站公开 JSON 接口，不依赖页面 DOM 抓取。
- 默认只执行 dry-run；只有显式传入 `--apply` 才会写入本地目录。
- 保留已有模型的完整配置；新模型只从同族模板克隆，不猜测上下文、工具或推理能力。
- 默认排除图像计费模型。
- 默认排除 `grok-4.5`、`qwen3.8-27b`、`deepseek-v4-flash` 和 `hy3`，避免被中转站重新发布后再次写入本地目录。
- `--prune` 为显式删除开关，用于将本地目录镜像为指定分组。
- 更新前自动生成时间戳备份，并使用原子替换写入。
- 支持使用 `--payload` 导入已捕获的 JSON，便于测试或需要浏览器会话的中转站。
- 安装时自动把 Codex 的 `config.toml` 指向模型目录，避免只安装 Skill 但 Codex 不加载自定义模型。
- 首次安装时提供交互式向导：同步模型、选择默认模型、选择 US/JP 中转站、配置 API Key、OpenAI 登录认证和功能开关。

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

如果要使用已有的其他目录：

```bash
./install.sh --catalog /path/to/custom-models.json
```

安装脚本会创建模型目录，并在 `${CODEX_HOME}/config.toml` 中写入：

```toml
model_catalog_json = "/absolute/path/to/.codex/model-catalogs/custom-models.json"
```

如果原来已有这项配置，安装脚本默认保留现有目录；只有未配置时才写入默认目录。使用 `--catalog` 或 `CODEX_MODEL_CATALOG` 时会显式切换目录，并先创建带时间戳的配置备份；其他配置内容保持不变。

安装后重启 Codex，使 Skill 被重新发现并重新加载模型目录。

### Windows 安装

在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

Windows 默认使用 `$env:CODEX_HOME`；未设置时使用当前用户目录下的 `.codex`，通常是：

```text
C:\Users\<用户名>\.codex
```

也可以显式指定目录和模型：

```powershell
.\install.ps1 `
  -Catalog "$env:USERPROFILE\.codex\model-catalogs\custom-models.json" `
  -ProviderRegion us `
  -Model gpt-6.1-sol
```

非交互安装：

```powershell
$env:CODEX_API_KEY = "从安全环境变量注入"
.\install.ps1 -NonInteractive -ProviderRegion us -Model gpt-6.1-sol
```

如果 Python 启动器没有加入 PATH，可设置：

```powershell
$env:PYTHON = "C:\Path\To\python.exe"
```

PowerShell 入口只负责复制文件、定位 Python 和转发参数，实际配置逻辑仍由 Python 脚本执行。也可以直接运行 `scripts\setup_codex.ps1`、`scripts\sync_catalog.ps1` 或 `scripts\configure_codex.ps1`。

### 首次安装向导

首次安装会：

1. 使用 xclis `GPT-稳定-STABLE / openai` 分组同步模型；
2. 在同步后的模型列表中选择默认模型；
3. 选择北美 `https://us.xclis.ai` 或亚洲 `https://jp.xclis.ai`；
4. 以隐藏输入方式询问 API Key，直接回车则写入 `YOUR-API-KEY` 占位符；
5. 询问是否启用 OpenAI 登录认证、生图和手机/App 远程控制相关配置；
6. 展示脱敏摘要，确认后备份并更新 `config.toml`。

API Key 不会出现在终端输出、命令行参数或模型目录中。若留空，向导会输出需要编辑的 `config.toml` 路径。

已有 `xclis_ai` 配置时，重复运行安装脚本只同步模型并保留现有 provider 配置。需要重新选择时：

```bash
./install.sh --reconfigure
```

非交互安装示例：

```bash
CODEX_API_KEY='从安全环境变量注入' ./install.sh \
  --non-interactive \
  --model gpt-6.1-sol \
  --provider-region us
```

也支持 `CODEX_DEFAULT_MODEL`、`CODEX_PROVIDER_REGION`、`CODEX_REQUIRES_OPENAI_AUTH`、`CODEX_IMAGE_GENERATION` 和 `CODEX_REMOTE_CONNECTIONS` 环境变量。

`requires_openai_auth`、`features.image_generation` 和 `features.remote_connections` 属于版本相关配置。向导只在用户确认后写入；如启用 OpenAI 登录认证，配置完成后还需执行 `codex login`。

## 使用

先执行 dry-run：

```bash
~/.codex/skills/codex-model-sync/scripts/sync_catalog.sh \
  --source-url https://xclis.ai/pricing \
  --group 'GPT-稳定-STABLE' \
  --platform openai \
  --catalog "${CODEX_HOME:-$HOME/.codex}/model-catalogs/custom-models.json"
```

确认差异后应用：

```bash
~/.codex/skills/codex-model-sync/scripts/sync_catalog.sh \
  --source-url https://xclis.ai/pricing \
  --group 'GPT-稳定-STABLE' \
  --platform openai \
  --catalog "${CODEX_HOME:-$HOME/.codex}/model-catalogs/custom-models.json" \
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
| `--exclude-model` | 额外排除模型；可重复传入，默认排除四个已配置模型 |
| `--template-slug` | 为新模型指定模板，可重复传入 |
| `--json` | 输出机器可读 JSON |

也可以只重新配置 Codex，而不复制 Skill：

```bash
~/.codex/skills/codex-model-sync/scripts/configure_codex.sh
```

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
python3 scripts/test_configure_codex.py
python3 scripts/test_setup_codex.py
python3 scripts/test_windows_entrypoints.py
python3 -m py_compile scripts/*.py
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
├── assets/
│   └── catalog-template.json
├── scripts/
│   ├── configure_codex.py
│   ├── configure_codex.sh
│   ├── configure_codex.ps1
│   ├── test_configure_codex.py
│   ├── setup_codex.py
│   ├── setup_codex.sh
│   ├── setup_codex.ps1
│   ├── sync_catalog.ps1
│   ├── test_setup_codex.py
│   ├── test_windows_entrypoints.py
│   ├── sync_catalog.py
│   ├── sync_catalog.sh
│   └── test_sync_catalog.py
├── install.sh
├── install.ps1
├── LICENSE
└── README.md
```

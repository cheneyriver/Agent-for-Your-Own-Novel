# Dream of Red Agents (MVP)

一个基于多智能体交互、角色记忆与叙事调度的古典小说续写系统。

## 目标
先做一个能跑、能产出内容的“红楼梦多 Agent 续写器”，再逐步抽象到研究方向。

MVP 只做：
1. 3-5 个角色在单一场景互动
2. 人物相对稳定、关系相对合理
3. 输出有一点古典叙事气质

## 运行
本项目当前支持 LLM 或模板模式（未配置 API 时自动回退模板）。

```bash
python src/main.py
```

输出会写入 `outputs/scene_01_story.md`。

## 交互选择模型（推荐）
默认执行 `python src/main.py` 会在启动时提示你选择：
- provider（如 `openai` / `qwen` / `template`）
- model（可使用配置默认，或手动输入覆盖）
- base_url（可使用配置默认，或手动输入覆盖）
- key index（当 `API_KEY_LIST` 里有多个 key 时，从 0 开始）

如果你想脚本化/不交互运行，可使用 `--no-prompt` 与命令行参数覆盖：

```bash
python src/main.py --provider openai --model gpt-4o-mini --base-url https://api.openai.com/v1 --key-index 0 --no-prompt
```

## LLM 配置
- 配置文件：`configs/llm.json`
- API Key：放在 `API_KEY_LIST`（已加入 `.gitignore`）
- 也可用环境变量覆盖：`LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`
- 选择第几个 key：`LLM_KEY_INDEX`（从 0 开始）

`configs/llm.json` 按“厂商”分别配置：
```json
{
  "provider": "qwen",
  "providers": {
    "openai": {
      "model": "gpt-4o-mini",
      "base_url": "https://api.openai.com/v1"
    },
    "qwen": {
      "model": "qwen-plus",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    }
  }
}
```

可选：如果你希望“选择 model”也能像 provider 一样列出候选项，可以在某个 provider 下加入 `models` 列表，例如：

```json
{
  "providers": {
    "openai": {
      "models": ["gpt-4o-mini", "gpt-4.1-mini"]
    }
  }
}
```

## 目录结构
```text
dream-of-red-agents/
├─ README.md
├─ requirements.txt
├─ configs/
│  ├─ world.json
│  ├─ relations.json
│  ├─ scene_01.json
│  └─ llm.json
├─ characters/
│  ├─ baoyu.json
│  ├─ daiyu.json
│  ├─ baochai.json
│  └─ xifeng.json
├─ prompts/
│  ├─ character_template.txt
│  ├─ narrator_prompt.txt
│  └─ reflection_prompt.txt
├─ src/
│  ├─ main.py
│  ├─ agent.py
│  ├─ memory.py
│  ├─ world.py
│  ├─ orchestrator.py
│  ├─ narrator.py
│  ├─ utils.py
│  └─ llm.py
├─ outputs/
│  └─ scene_01_story.md
└─ docs/
   └─ design.md
```

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

输出会写入 `outputs/scene_01_story_<run_id>.md`。

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

## 日志与调试
每次运行都会生成独立日志文件，路径为：

- `logs/run_<run_id>.log`

日志覆盖内容包括：
- 模型选择与 LLM 客户端状态
- Orchestrator 每轮 speaker/turn
- Character/Narrator/Reflection 每个 Agent 的执行状态
- LLM 请求与响应长度（不记录 API key）
- 回退路径（LLM 失败时 fallback）

可通过参数控制日志级别：

```bash
python src/main.py --log-level DEBUG
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
│  ├─ reflection_prompt.txt
│  └─ planner_prompt.txt
├─ src/
│  ├─ main.py
│  ├─ agent.py
│  ├─ reflection.py
│  ├─ memory.py
│  ├─ world.py
│  ├─ orchestrator.py
│  ├─ narrator.py
│  ├─ utils.py
│  └─ llm.py
├─ outputs/
│  └─ scene_01_story.md
└─ docs/
   ├─ design.md
   └─ agent_modules.md
```

## Multi-Agent 流程
当前版本将任务拆为 3 个 Agent（共用同一套 LLM API）：

1. `CharacterAgent`：按角色设定与关系生成对白
2. `NarratorAgent`：把对白整理为连贯叙事
3. `ReflectionAgent`：对成文进行编辑评估并给出建议
4. `StoryPlannerAgent`：每轮生成“剧情任务卡”，约束对白必须推进事件

详细说明见 `docs/agent_modules.md`。

## M2 剧情推进机制
M2 版本新增“每轮任务卡”，避免对话空泛：

- 每轮由 `StoryPlannerAgent` 生成：
  - `TASK`：本轮剧情任务
  - `FOCUS`：重点人物
  - `RULE`：推进规则（必须新增具体信息并给出动作）
- `CharacterAgent` 在发言时会接收：
  - 本轮任务卡
  - 角色 `hidden_goal`
- 最终输出文末会附带 `【剧情任务轨迹】`，方便复盘每轮推进。

## 长程记忆 + Human Feedback（当前版本）
系统新增章节状态卡（`memory/story_state.json`）：

- `facts`：近期事实记忆
- `narrative_debts`：待回收叙事债务
- `human_feedback_history`：每章你的反馈记录
- `last_chapter_summary`：上一章摘要
- `chapter_summaries`：**M4a** 章节级摘要（含关键事件）
- `foreshadowing_table`：**M4b** 伏笔表（待回收/已回收）

每次运行会在 3 个 checkpoint（章前/中段/章末）收集你的反馈，并注入 Planner 与角色发言上下文。可选输入「本章拟埋设的伏笔」，会写入伏笔表供后续章节回收。

如需跳过交互（自动默认值）：

```bash
python src/main.py --no-human-feedback
```

## M4 输出扩展
- 每章对话轮数：`configs/scene_01.json` 中 `turns` 默认 12
- 叙事成文：3-5 段，max_tokens 1800

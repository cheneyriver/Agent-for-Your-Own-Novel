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

## LLM 配置
- 配置文件：`configs/llm.json`
- API Key：放在 `API_KEY_LIST`（已加入 `.gitignore`）
- 也可用环境变量覆盖：`LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`

`configs/llm.json` 现在按“厂商”分别配置：
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

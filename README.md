# Dream of Red Agents (MVP)

一个基于多智能体交互、角色记忆与叙事调度的古典小说续写系统。

## 目标
先做一个能跑、能产出内容的“红楼梦多 Agent 续写器”，再逐步抽象到研究方向。

MVP 只做：
1. 3-5 个角色在单一场景互动
2. 人物相对稳定、关系相对合理
3. 输出有一点古典叙事气质

## 运行
本项目当前不依赖外部模型，采用模板与随机抽样生成示例文本。

```bash
python src/main.py
```

输出会写入 `outputs/scene_01_story.md`。

## 目录结构
```text
dream-of-red-agents/
├─ README.md
├─ requirements.txt
├─ configs/
│  ├─ world.json
│  ├─ relations.json
│  └─ scene_01.json
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
│  └─ utils.py
├─ outputs/
│  └─ scene_01_story.md
└─ docs/
   └─ design.md
```

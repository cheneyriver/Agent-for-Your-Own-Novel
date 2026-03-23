import os
from memory import Memory
from utils import pick


class CharacterAgent:
    def __init__(self, config, relations, llm_client=None, prompt_template="", logger=None):
        self.name = config.get("name")
        self.persona = config.get("persona", "")
        self.speaking_style = config.get("speaking_style", "")
        self.goals = config.get("goals", [])
        self.hidden_goal = config.get("hidden_goal", "")
        self.taboo = config.get("taboo", [])
        self.memory = Memory(config.get("long_term_memory", []))
        self.relations = relations
        self.llm = llm_client
        self.prompt_template = prompt_template or ""
        self.logger = logger

    def _memory_snippet(self):
        if not self.memory.long_term:
            return ""
        item = pick(self.memory.long_term)
        content = item.get("content", "")
        return content.rstrip("。！？")

    def _relation_hint(self, target):
        rel = self.relations.get(self.name, target)
        if not rel:
            return ""
        rel_type = rel.get("type", "")
        tension = rel.get("hidden_tension", "")
        if rel_type and tension:
            return f"{rel_type}之情，暗藏{tension}"
        return rel_type or tension

    def _build_messages(self, world, target, dialog_history, turn_plan=None):
        relation_hint = self._relation_hint(target)
        memory_snippet = self._memory_snippet()
        recent_dialog = "\n".join(
            [f"{d['speaker']}对{d.get('target') or '众人'}说：{d['text']}" for d in dialog_history[-4:]]
        )
        last_utter = dialog_history[-1]["text"] if dialog_history else ""
        relationships = relation_hint or "关系未明"
        scene_context = f"{world.brief()}；场景目标：{world.scene_goal}；长期记忆：{memory_snippet or '无'}"

        if self.prompt_template:
            system = self.prompt_template.format(
                character_name=self.name,
                persona=self.persona,
                speaking_style=self.speaking_style,
                goals="，".join(self.goals),
                taboo="，".join(self.taboo),
                relationships=relationships,
                scene=scene_context,
            )
        else:
            system = (
                f"你是{self.name}。性情：{self.persona}。"
                f"说话风格：{self.speaking_style}。"
                f"目标：{'，'.join(self.goals)}。禁忌：{'，'.join(self.taboo)}。"
                f"与{target}关系：{relationships}。"
                f"长期记忆线索：{memory_snippet or '无'}。"
            )
        user = (
            f"场景：{world.brief()}。场景目标：{world.scene_goal}。\n"
            f"最近对话：\n{recent_dialog or '（无）'}\n"
            f"上一句：{last_utter or '（无）'}\n"
            f"你的隐性目标：{self.hidden_goal or '无'}\n"
            f"本轮剧情任务：{(turn_plan or {}).get('task', '推进人物关系并揭示新信息')}\n"
            f"本轮推进要求：{(turn_plan or {}).get('progress_rule', '必须抛出一个具体信息点或行动主张')}\n"
            f"请以古典语气对{target}说话，1-2 句即可。\n"
            f"要求：避免复用上句的句式或关键短语；不要套用固定模板；有回应、有转折；必须包含一个具体细节。"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]

    def _fallback_act(self, target):
        memory_snippet = self._memory_snippet()
        relation_hint = self._relation_hint(target)

        classical = [
            "风物依稀",
            "旧梦难寻",
            "人事已非",
            "花影犹在",
            "心事难明"
        ]
        openers = [
            "轻轻叹道",
            "低声说道",
            "含笑道",
            "缓缓道",
            "沉吟片刻道"
        ]
        templates = [
            "{classical}，{target}可还记得{memory}？",
            "{classical}，{target}今日重逢，心下难言",
            "{classical}，{target}一别经年，言语都生疏了",
            "{classical}，{target}，{relation}，不敢多言",
            "{classical}，旧园如此，{target}又作何打算？"
        ]

        line = pick(templates).format(
            classical=pick(classical),
            target=target or "诸位",
            memory=memory_snippet or "往日旧事",
            relation=relation_hint or "情意难说"
        )

        return {
            "speaker": self.name,
            "target": target,
            "text": line,
            "tone": pick(openers)
        }

    def act(self, world, others, dialog_history, turn_plan=None):
        target = pick([o.name for o in others]) if others else ""
        if self.logger:
            self.logger.info(
                "[CharacterAgent] speaker=%s target=%s history_len=%s",
                self.name,
                target or "众人",
                len(dialog_history),
            )

        if self.llm and self.llm.enabled:
            messages = self._build_messages(world, target or "众人", dialog_history, turn_plan=turn_plan)
            if self.logger:
                self.logger.debug(
                    "[CharacterAgent] prompt speaker=%s system=%s user=%s",
                    self.name,
                    messages[0].get("content", ""),
                    messages[1].get("content", ""),
                )
            try:
                content = self.llm.generate(messages, temperature=0.9, max_tokens=180)
                if self.logger:
                    self.logger.info(
                        "[CharacterAgent] llm_ok speaker=%s target=%s text=%s",
                        self.name,
                        target or "众人",
                        content,
                    )
                return {
                    "speaker": self.name,
                    "target": target,
                    "text": content,
                    "tone": ""
                }
            except Exception:
                if self.logger:
                    self.logger.exception(
                        "[CharacterAgent] llm_failed speaker=%s fallback=template",
                        self.name,
                    )
                if os.getenv("LLM_STRICT", "") == "1":
                    raise
                return self._fallback_act(target)

        if self.logger:
            self.logger.info("[CharacterAgent] llm_disabled speaker=%s fallback=template", self.name)
        return self._fallback_act(target)

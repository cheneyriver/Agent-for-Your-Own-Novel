from utils import pick


class StoryPlannerAgent:
    def __init__(self, llm_client=None, prompt_template="", logger=None):
        self.llm = llm_client
        self.prompt_template = prompt_template or ""
        self.logger = logger

    def _fallback_plan(self, turn_index, total_turns, speakers):
        templates = [
            "揭示旧信中的一条关键信息",
            "让两位角色发生立场冲突",
            "抛出一个可执行决定（去处、见人、查证）",
            "揭露一段被隐瞒的旧事",
            "在情感与现实之间做出选择",
        ]
        return {
            "task": templates[(turn_index - 1) % len(templates)],
            "focus": speakers[(turn_index - 1) % len(speakers)] if speakers else "众人",
            "progress_rule": "本轮必须新增一个具体信息点，并给出下一步动作",
        }

    def plan_turn(self, world, dialog_history, turn_index, total_turns, speakers, chapter_context=None):
        if self.logger:
            self.logger.info("[PlannerAgent] plan_start turn=%s/%s", turn_index, total_turns)
        if not (self.llm and self.llm.enabled):
            plan = self._fallback_plan(turn_index, total_turns, speakers)
            if self.logger:
                self.logger.info("[PlannerAgent] plan_fallback turn=%s plan=%s", turn_index, plan)
            return plan

        system = self.prompt_template or "你是剧情策划。输出本轮剧情任务卡。"
        recent = "\n".join(
            [f"{d['speaker']}对{d.get('target') or '众人'}：{d['text']}" for d in dialog_history[-5:]]
        )
        user = (
            f"场景：{world.brief()}。场景目标：{world.scene_goal}\n"
            f"当前回合：{turn_index}/{total_turns}\n"
            f"可用角色：{','.join(speakers)}\n"
            f"章节约束：\n{chapter_context or '无'}\n"
            f"最近对话：\n{recent or '（无）'}\n"
            "请仅输出三行：\n"
            "TASK: <本轮任务>\n"
            "FOCUS: <本轮重点人物>\n"
            "RULE: <推进规则>\n"
        )
        if self.logger:
            self.logger.debug("[PlannerAgent] prompt system=%s", system)
            self.logger.debug("[PlannerAgent] prompt user=%s", user)
        try:
            content = self.llm.generate(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.6,
                max_tokens=220,
            )
            task = ""
            focus = ""
            rule = ""
            for line in content.splitlines():
                raw = line.strip()
                upper = raw.upper()
                if upper.startswith("TASK:"):
                    task = raw.split(":", 1)[1].strip()
                elif upper.startswith("FOCUS:"):
                    focus = raw.split(":", 1)[1].strip()
                elif upper.startswith("RULE:"):
                    rule = raw.split(":", 1)[1].strip()
            if not task:
                task = "推进冲突并揭示具体信息"
            if not focus:
                focus = pick(speakers) if speakers else "众人"
            if not rule:
                rule = "必须新增一个具体信息点，并给出下一步动作"
            plan = {"task": task, "focus": focus, "progress_rule": rule}
            if self.logger:
                self.logger.info("[PlannerAgent] plan_ok turn=%s plan=%s", turn_index, plan)
            return plan
        except Exception:
            if self.logger:
                self.logger.exception("[PlannerAgent] plan_failed turn=%s fallback=template", turn_index)
            return self._fallback_plan(turn_index, total_turns, speakers)

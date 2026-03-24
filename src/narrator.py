class NarratorAgent:
    def __init__(self, llm_client=None, prompt_template="", logger=None):
        self.llm = llm_client
        self.prompt_template = prompt_template or ""
        self.logger = logger

    def _dialog_text(self, dialog):
        lines = []
        for utter in dialog:
            speaker = utter.get("speaker")
            target = utter.get("target") or "众人"
            text = utter.get("text") or ""
            lines.append(f"{speaker}对{target}道：{text}")
        return "\n".join(lines)

    def compose(self, world, dialog):
        if self.logger:
            self.logger.info("[NarratorAgent] compose_start dialog_len=%s", len(dialog))
        if self.llm and self.llm.enabled:
            system = self.prompt_template or "你是叙述者。请将对话整理为连贯叙事。"
            user = (
                f"场景：{world.brief()}。场景目标：{world.scene_goal}\n"
                f"对话记录：\n{self._dialog_text(dialog) or '（无）'}\n"
                f"请输出 3-5 段连贯小说文本，保留主要冲突与人物弧光。\n"
                f"必须自然收束，最后一句必须完整结束。"
            )
            if self.logger:
                self.logger.debug("[NarratorAgent] prompt system=%s", system)
                self.logger.debug("[NarratorAgent] prompt user=%s", user)
            try:
                result = self.llm.generate(
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.7,
                    max_tokens=1800,
                )
                if self.logger:
                    self.logger.info("[NarratorAgent] compose_llm_ok text=%s", result)
                return result
            except Exception:
                if self.logger:
                    self.logger.exception("[NarratorAgent] compose_llm_failed fallback=template")
                return narrate(world, dialog)
        if self.logger:
            self.logger.info("[NarratorAgent] compose_llm_disabled fallback=template")
        return narrate(world, dialog)


def narrate(world, dialog):
    lines = []
    intro = f"{world.time}，{world.location}尚存旧影。{world.family_status}，众人因一封旧信重聚。"
    lines.append(intro)

    for utter in dialog:
        speaker = utter.get("speaker")
        target = utter.get("target")
        text = utter.get("text") or ""
        if not text.endswith(("？", "！", "。")):
            text = text + "。"
        if target:
            line = f"{speaker}对{target}道：\"{text}\""
        else:
            line = f"{speaker}道：\"{text}\""
        lines.append(line)

    ending = "众人言辞未尽，旧园风起，似把往事又吹回。"
    lines.append(ending)

    return "\n".join(lines)

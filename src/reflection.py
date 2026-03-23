class ReflectionAgent:
    def __init__(self, llm_client=None, prompt_template="", logger=None):
        self.llm = llm_client
        self.prompt_template = prompt_template or ""
        self.logger = logger

    def review(self, world, dialog, story_text):
        if self.logger:
            self.logger.info("[ReflectionAgent] review_start dialog_len=%s", len(dialog))
        if not (self.llm and self.llm.enabled):
            if self.logger:
                self.logger.info("[ReflectionAgent] review_skipped reason=llm_disabled")
            return ""

        transcript = []
        for utter in dialog:
            transcript.append(
                f"{utter.get('speaker')}对{utter.get('target') or '众人'}道：{utter.get('text') or ''}"
            )
        transcript_text = "\n".join(transcript)

        system = self.prompt_template or "你是编辑。请给出简短评估与建议。"
        user = (
            f"场景：{world.brief()}。场景目标：{world.scene_goal}\n"
            f"对话：\n{transcript_text or '（无）'}\n"
            f"成文：\n{story_text}\n"
            "请输出：\n"
            "1) 100字内总体评价\n"
            "2) 3条可执行改进建议\n"
        )
        if self.logger:
            self.logger.debug("[ReflectionAgent] prompt system=%s", system)
            self.logger.debug("[ReflectionAgent] prompt user=%s", user)
        try:
            result = self.llm.generate(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.5,
                max_tokens=300,
            )
            if self.logger:
                self.logger.info("[ReflectionAgent] review_llm_ok text=%s", result)
            return result
        except Exception:
            if self.logger:
                self.logger.exception("[ReflectionAgent] review_llm_failed")
            return ""

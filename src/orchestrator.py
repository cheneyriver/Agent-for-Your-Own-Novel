class Orchestrator:
    def __init__(self, world, logger=None):
        self.world = world
        self.logger = logger

    def run(self, agents, turns):
        dialog = []
        if not agents:
            if self.logger:
                self.logger.warning("[Orchestrator] no_agents turns=%s", turns)
            return dialog

        if self.logger:
            self.logger.info("[Orchestrator] start turns=%s agent_count=%s", turns, len(agents))
        for i in range(turns):
            speaker = agents[i % len(agents)]
            others = [a for a in agents if a is not speaker]
            if self.logger:
                self.logger.info("[Orchestrator] turn=%s speaker=%s", i + 1, speaker.name)
            utter = speaker.act(self.world, others, dialog)
            dialog.append(utter)

            event = f"{utter['speaker']}对{utter['target'] or '众人'}说：{utter['text']}"
            for a in agents:
                a.memory.remember(event)
            if self.logger:
                self.logger.debug("[Orchestrator] turn=%s event=%s", i + 1, event)

        if self.logger:
            self.logger.info("[Orchestrator] done turns=%s dialog_len=%s", turns, len(dialog))
        return dialog

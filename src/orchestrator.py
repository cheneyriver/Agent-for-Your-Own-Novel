class Orchestrator:
    def __init__(self, world, logger=None):
        self.world = world
        self.logger = logger

    def run(self, agents, turns, planner=None):
        dialog = []
        if not agents:
            if self.logger:
                self.logger.warning("[Orchestrator] no_agents turns=%s", turns)
            return dialog

        if self.logger:
            self.logger.info("[Orchestrator] start turns=%s agent_count=%s", turns, len(agents))
        turn_plans = []
        for i in range(turns):
            speaker = agents[i % len(agents)]
            others = [a for a in agents if a is not speaker]
            turn_index = i + 1
            speakers = [a.name for a in agents]
            turn_plan = (
                planner.plan_turn(self.world, dialog, turn_index, turns, speakers)
                if planner
                else {"task": "推进人物关系", "focus": speaker.name, "progress_rule": "给出具体信息与动作"}
            )
            turn_plans.append(turn_plan)
            if self.logger:
                self.logger.info(
                    "[Orchestrator] turn=%s speaker=%s task=%s",
                    turn_index,
                    speaker.name,
                    turn_plan.get("task"),
                )
            utter = speaker.act(self.world, others, dialog, turn_plan=turn_plan)
            dialog.append(utter)

            event = f"{utter['speaker']}对{utter['target'] or '众人'}说：{utter['text']}"
            for a in agents:
                a.memory.remember(event)
            if self.logger:
                self.logger.debug("[Orchestrator] turn=%s event=%s", i + 1, event)

        if self.logger:
            self.logger.info("[Orchestrator] done turns=%s dialog_len=%s", turns, len(dialog))
        return dialog, turn_plans

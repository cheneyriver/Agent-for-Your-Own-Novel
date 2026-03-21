class Orchestrator:
    def __init__(self, world):
        self.world = world

    def run(self, agents, turns):
        dialog = []
        if not agents:
            return dialog

        for i in range(turns):
            speaker = agents[i % len(agents)]
            others = [a for a in agents if a is not speaker]
            utter = speaker.act(self.world, others, dialog)
            dialog.append(utter)

            event = f"{utter['speaker']}对{utter['target'] or '众人'}说：{utter['text']}"
            for a in agents:
                a.memory.remember(event)

        return dialog

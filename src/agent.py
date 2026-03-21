from memory import Memory
from utils import pick


class CharacterAgent:
    def __init__(self, config, relations):
        self.name = config.get("name")
        self.persona = config.get("persona", "")
        self.speaking_style = config.get("speaking_style", "")
        self.goals = config.get("goals", [])
        self.taboo = config.get("taboo", [])
        self.memory = Memory(config.get("long_term_memory", []))
        self.relations = relations

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

    def act(self, world, others, dialog_history):
        target = pick([o.name for o in others]) if others else ""
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

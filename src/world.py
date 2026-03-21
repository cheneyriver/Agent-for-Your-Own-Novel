class WorldState:
    def __init__(self, data):
        self.time = data.get("time", "")
        self.location = data.get("location", "")
        self.family_status = data.get("family_status", "")
        self.major_events = data.get("major_events", [])
        self.scene_goal = data.get("scene_goal", "")

    def brief(self):
        parts = [self.time, self.location, self.family_status]
        return "，".join([p for p in parts if p])


class RelationshipGraph:
    def __init__(self, data):
        self.data = data or {}

    def get(self, src, dst):
        return self.data.get(src, {}).get(dst)

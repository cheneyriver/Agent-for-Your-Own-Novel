class Memory:
    def __init__(self, long_term=None):
        self.long_term = long_term or []
        self.short_term = []

    def remember(self, event, limit=8):
        self.short_term.append(event)
        if len(self.short_term) > limit:
            self.short_term = self.short_term[-limit:]

    def short_summary(self):
        if not self.short_term:
            return ""
        return "；".join(self.short_term[-3:])

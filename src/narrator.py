
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

"""M4a: 章节摘要生成。M4b: 伏笔提取与建议。"""

import re


def _heuristic_summary(story_text, max_len=200):
    if not story_text or not isinstance(story_text, str):
        return ""
    s = story_text.strip()
    for sep in ["\n\n", "\n", "。"]:
        parts = s.split(sep)
        if len(parts) >= 2:
            first = parts[0].strip() + ("。" if not parts[0].rstrip().endswith("。") else "")
            return first[:max_len]
    return s[:max_len]


def _heuristic_foreshadowing(turn_plans, human_feedback):
    items = []
    for p in turn_plans or []:
        task = p.get("task", "")
        if task and "揭示" in task:
            items.append(task)
        elif task and "揭露" in task:
            items.append(task)
        elif task and ("决定" in task or "去处" in task or "查证" in task):
            items.append(task)
    hook = (human_feedback or {}).get("ending_hook", "")
    if hook and len(hook) > 5:
        items.append(hook)
    return items[:5]


def summarize_chapter(llm_client, story_text, dialog, turn_plans, human_feedback, logger=None):
    """
    生成章节摘要字典，用于 commit_chapter_state。
    若有 LLM 则调用；否则用启发式。
    """
    if llm_client and llm_client.enabled:
        dialog_lines = []
        for u in (dialog or [])[-6:]:
            dialog_lines.append(f"{u.get('speaker')}对{u.get('target') or '众人'}：{u.get('text','')}")
        user = (
            f"本章成文：\n{story_text[:1500]}\n\n"
            f"对话要点：\n" + "\n".join(dialog_lines) + "\n\n"
            "请输出三块，每块以标签开头：\n"
            "SUMMARY: 80字内本章摘要\n"
            "EVENTS: 2-3个关键事件，每行一个\n"
            "FORESHADOWING: 本章埋设的待回收伏笔，每行一条，无则写无"
        )
        try:
            content = llm_client.generate(
                [
                    {"role": "system", "content": "你是摘要助手。按要求输出 SUMMARY/EVENTS/FORESHADOWING 三块。"},
                    {"role": "user", "content": user},
                ],
                temperature=0.4,
                max_tokens=350,
            )
            summary = ""
            events = []
            foreshadowing = []
            for block in re.split(r"\n\n+", content):
                block = block.strip()
                if block.upper().startswith("SUMMARY:"):
                    summary = re.sub(r"^summary:\s*", "", block, flags=re.I).strip()[:150]
                elif block.upper().startswith("EVENTS:"):
                    raw = re.sub(r"^events:\s*", "", block, flags=re.I)
                    events = [ln.strip().lstrip("-•0123456789. ").strip() for ln in raw.splitlines() if ln.strip()][:3]
                elif block.upper().startswith("FORESHADOWING:"):
                    raw = re.sub(r"^foreshadowing:\s*", "", block, flags=re.I)
                    foreshadowing = [ln.strip().lstrip("-• ").strip() for ln in raw.splitlines() if ln.strip() and ln.strip().lower() != "无"]
            if not summary:
                summary = _heuristic_summary(story_text, 150)
            if logger:
                logger.info("[Summarizer] llm_ok summary_len=%s events=%s foreshadowing=%s", len(summary), len(events), len(foreshadowing))
            return {
                "summary": summary,
                "key_events": events,
                "key_characters": [],
                "foreshadowing": foreshadowing,
            }
        except Exception:
            if logger:
                logger.exception("[Summarizer] llm_failed fallback=heuristic")
    summary = _heuristic_summary(story_text, 150)
    foreshadowing = _heuristic_foreshadowing(turn_plans, human_feedback)
    return {
        "summary": summary,
        "key_events": [],
        "key_characters": [],
        "foreshadowing": foreshadowing,
    }

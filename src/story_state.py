import json
from pathlib import Path


def default_story_state():
    return {
        "chapter_index": 1,
        "facts": [],
        "relation_deltas": [],
        "narrative_debts": [],
        "chapter_summaries": [],
        "foreshadowing_table": [],
        "style_preferences": {
            "tone": "含蓄古典",
            "must_have_progress": True,
        },
        "human_feedback_history": [],
        "last_chapter_summary": "",
    }


def load_story_state(path):
    p = Path(path)
    if not p.exists():
        return default_story_state()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default_story_state()


def save_story_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_story_state(state, max_items=5, max_summaries=5, max_foreshadowing=8, max_relation_deltas=6):
    facts = state.get("facts", [])[-max_items:]
    debts = state.get("narrative_debts", [])[-max_items:]
    summaries = state.get("chapter_summaries", [])[-max_summaries:]
    foreshadowing = [f for f in state.get("foreshadowing_table", []) if f.get("status") == "open"][-max_foreshadowing:]
    relation_deltas = state.get("relation_deltas", [])[-max_relation_deltas:]

    summary_lines = [
        f"章节序号：{state.get('chapter_index', 1)}",
        "近期事实：" + ("；".join(facts) if facts else "无"),
        "未回收叙事债务：" + ("；".join(debts) if debts else "无"),
    ]
    if summaries:
        chap_lines = []
        for s in summaries:
            idx = s.get("chapter_idx", "?")
            text = s.get("summary", "")[:120]
            if text:
                chap_lines.append(f"第{idx}章：{text}…")
        if chap_lines:
            summary_lines.append("近期章节摘要：\n" + "\n".join(chap_lines))
    if foreshadowing:
        f_lines = [f"  - {f.get('description', '')}（第{f.get('introduced_chapter', '?')}章埋设）" for f in foreshadowing]
        summary_lines.append("待回收伏笔：\n" + "\n".join(f_lines))
    if relation_deltas:
        rd_lines = [f"  {d.get('from','')}→{d.get('to','')}: {d.get('recent_change','')}" for d in relation_deltas if d.get("recent_change")]
        if rd_lines:
            summary_lines.append("近期关系变化：\n" + "\n".join(rd_lines))
    return "\n".join(summary_lines)


def commit_chapter_state(state, chapter_summary, dialog, human_feedback, turns_plans,
                         chapter_summary_dict=None, new_foreshadowing=None, resolved_foreshadowing_ids=None,
                         relation_deltas_this_chapter=None):
    chapter_idx = int(state.get("chapter_index", 1))
    state["chapter_index"] = chapter_idx + 1
    state["last_chapter_summary"] = chapter_summary[:600]
    state.setdefault("human_feedback_history", []).append(human_feedback)

    facts = state.setdefault("facts", [])
    for utter in dialog[-6:]:
        facts.append(f"{utter.get('speaker')}对{utter.get('target') or '众人'}：{utter.get('text')}")
    state["facts"] = facts[-80:]

    debts = state.setdefault("narrative_debts", [])
    for p in turns_plans[-3:]:
        task = p.get("task", "")
        if task:
            debts.append(f"待回收：{task}")
    state["narrative_debts"] = debts[-40:]

    summaries = state.setdefault("chapter_summaries", [])
    if chapter_summary_dict:
        summaries.append({
            "chapter_idx": chapter_idx,
            "summary": chapter_summary_dict.get("summary", chapter_summary[:300]),
            "key_events": chapter_summary_dict.get("key_events", []),
            "key_characters": chapter_summary_dict.get("key_characters", []),
        })
    else:
        summaries.append({"chapter_idx": chapter_idx, "summary": chapter_summary[:300], "key_events": [], "key_characters": []})
    state["chapter_summaries"] = summaries[-20:]

    foreshadowing = state.setdefault("foreshadowing_table", [])
    if resolved_foreshadowing_ids:
        for f in foreshadowing:
            if str(f.get("id", "")) in resolved_foreshadowing_ids:
                f["status"] = "resolved"
                f["resolved_chapter"] = chapter_idx
    if new_foreshadowing:
        for i, item in enumerate(new_foreshadowing):
            desc = item if isinstance(item, str) else item.get("description", str(item))
            if desc:
                foreshadowing.append({
                    "id": f"f{chapter_idx}_{len(foreshadowing) + i}",
                    "description": desc,
                    "introduced_chapter": chapter_idx,
                    "status": "open",
                })
    state["foreshadowing_table"] = foreshadowing[-60:]

    if relation_deltas_this_chapter:
        deltas = state.setdefault("relation_deltas", [])
        deltas.extend(relation_deltas_this_chapter)
        state["relation_deltas"] = deltas[-100:]

    return state

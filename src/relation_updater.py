"""M4c: 章末增量关系更新。"""

import copy
import re


def merge_relations(base_relations, relation_deltas):
    """
    合并基础关系与累积 deltas，得到当前有效关系。
    返回与 base_relations 相同结构的 dict，供 RelationshipGraph 使用。
    """
    if not isinstance(base_relations, dict):
        return base_relations or {}
    effective = copy.deepcopy(base_relations)
    for d in (relation_deltas or []):
        src = d.get("from") or d.get("src")
        dst = d.get("to") or d.get("dst")
        if not src or not dst:
            continue
        if src not in effective:
            effective[src] = {}
        if dst not in effective[src]:
            effective[src][dst] = {}
        rel = effective[src][dst]
        if d.get("recent_change"):
            rel["recent_change"] = d["recent_change"]
        if d.get("type"):
            rel["type"] = d["type"]
        if d.get("hidden_tension"):
            rel["hidden_tension"] = d["hidden_tension"]
        delta_i = d.get("intensity_delta")
        if delta_i is not None:
            try:
                rel["intensity"] = float(rel.get("intensity", 0.5)) + float(delta_i)
                rel["intensity"] = max(0, min(1, rel["intensity"]))
            except (TypeError, ValueError):
                pass
    return effective


def _dialog_text(dialog):
    lines = []
    for u in dialog or []:
        lines.append(f"{u.get('speaker')}对{u.get('target') or '众人'}：{u.get('text','')}")
    return "\n".join(lines)


def _relations_text(relations_data):
    if not isinstance(relations_data, dict):
        return ""
    lines = []
    for src, targets in relations_data.items():
        if not isinstance(targets, dict):
            continue
        for dst, rel in targets.items():
            if isinstance(rel, dict):
                t = rel.get("type", "")
                rc = rel.get("recent_change", "")
                ht = rel.get("hidden_tension", "")
                i = rel.get("intensity", "")
                lines.append(f"  {src}→{dst}: type={t}, recent_change={rc}, hidden_tension={ht}, intensity={i}")
    return "\n".join(lines) if lines else "（无）"


def _parse_deltas_from_llm(content):
    """从 LLM 输出解析 delta 列表。格式示例：
    FROM: 贾宝玉
    TO: 林黛玉
    RECENT_CHANGE: 本章被质疑后更添愧疚
    INTENSITY_DELTA: -0.05
    ---
    FROM: 王熙凤
    TO: 薛宝钗
    ...
    """
    deltas = []
    blocks = re.split(r"\n---+\n", content)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        d = {}
        for line in block.splitlines():
            line = line.strip()
            if line.upper().startswith("FROM:"):
                d["from"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("TO:"):
                d["to"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("RECENT_CHANGE:"):
                d["recent_change"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("INTENSITY_DELTA:"):
                try:
                    d["intensity_delta"] = float(line.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    pass
            elif line.upper().startswith("TYPE:"):
                d["type"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("HIDDEN_TENSION:"):
                d["hidden_tension"] = line.split(":", 1)[1].strip()
        if d.get("from") and d.get("to"):
            deltas.append(d)
    return deltas


def update_relations(llm_client, base_relations, relation_deltas, chapter_dialog, chapter_story, chapter_idx, logger=None):
    """
    根据本章内容推断关系变化，返回本章的 delta 列表。
    增量：只传入当前有效关系（base + 已有 deltas）+ 本章内容。
    """
    effective = merge_relations(base_relations, relation_deltas)
    relations_text = _relations_text(effective)
    dialog_text = _dialog_text(chapter_dialog)[:1200]
    story_snippet = (chapter_story or "")[:800]

    if not (llm_client and llm_client.enabled):
        if logger:
            logger.info("[RelationUpdater] llm_disabled skip")
        return []

    user = (
        f"当前人物关系（章前状态）：\n{relations_text}\n\n"
        f"本章对话：\n{dialog_text}\n\n"
        f"本章成文片段：\n{story_snippet}\n\n"
        "请根据本章内容，输出 0-6 条关系变化。每条格式：\n"
        "FROM: 人物A\nTO: 人物B\nRECENT_CHANGE: 本章发生的变化描述（20字内）\nINTENSITY_DELTA: -0.1 或 +0.05（可选）\n"
        "多条之间用 --- 分隔。若无明显变化则只输出：NONE"
    )
    try:
        content = llm_client.generate(
            [
                {"role": "system", "content": "你是关系分析师。根据本章对话与成文，推断人物关系变化。只输出变化，格式严格。"},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        if logger:
            logger.info("[RelationUpdater] llm_ok content_len=%s", len(content or ""))
        if content and "NONE" in content.upper() and len(content.strip()) < 20:
            return []
        deltas = _parse_deltas_from_llm(content or "")
        for d in deltas:
            d["chapter"] = chapter_idx
        if logger:
            logger.info("[RelationUpdater] parsed deltas=%s", len(deltas))
        return deltas
    except Exception:
        if logger:
            logger.exception("[RelationUpdater] llm_failed")
        return []

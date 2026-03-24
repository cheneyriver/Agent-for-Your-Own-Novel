from datetime import datetime
from pathlib import Path
import argparse
import sys
import uuid

from agent import CharacterAgent
from logger import setup_run_logger
from llm import available_providers, build_client, count_keys_for_provider
from narrator import NarratorAgent
from orchestrator import Orchestrator
from planner import StoryPlannerAgent
from reflection import ReflectionAgent
from story_state import (
    commit_chapter_state,
    load_story_state,
    save_story_state,
    summarize_story_state,
)
from relation_updater import merge_relations, update_relations
from summarizer import summarize_chapter
from utils import load_json, save_text, seed_everything
from world import RelationshipGraph, WorldState


def _read_prompt(path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_characters(relations, base_dir, llm_client, character_prompt, logger=None):
    characters_dir = base_dir / "characters"
    configs = [
        "baoyu.json",
        "daiyu.json",
        "baochai.json",
        "xifeng.json"
    ]
    agents = []
    for name in configs:
        data = load_json(characters_dir / name)
        agents.append(
            CharacterAgent(
                data,
                relations,
                llm_client,
                prompt_template=character_prompt,
                logger=logger,
            )
        )
    return agents


def make_run_id():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"{stamp}_{short}"


def _prompt_choice(title, options, default_index=0):
    print(title)
    for i, opt in enumerate(options):
        marker = " (default)" if i == default_index else ""
        print(f"  [{i}] {opt}{marker}")
    raw = input("请输入编号（回车默认）：").strip()
    if raw == "":
        return options[default_index]
    try:
        idx = int(raw)
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass
    print("输入无效，将使用默认选项。")
    return options[default_index]


def _prompt_text(title, default_value=""):
    hint = f"（回车默认：{default_value}）" if default_value else "（可直接回车跳过）"
    raw = input(f"{title}{hint}: ").strip()
    return raw if raw != "" else default_value


def _build_arg_parser():
    p = argparse.ArgumentParser(description="Dream of Red Agents (MVP)")
    p.add_argument("--provider", default=None, help="LLM provider: openai/qwen/template")
    p.add_argument("--model", default=None, help="LLM model name")
    p.add_argument("--base-url", default=None, help="LLM base url, e.g. https://api.openai.com/v1")
    p.add_argument("--key-index", default=None, type=int, help="Which API key to use (0-based)")
    p.add_argument("--no-prompt", action="store_true", help="Disable interactive selection")
    p.add_argument("--debug-llm", action="store_true", help="Print LLM request debug info")
    p.add_argument("--log-level", default="INFO", help="Log level: DEBUG/INFO/WARNING/ERROR")
    p.add_argument("--no-human-feedback", action="store_true", help="Disable interactive human feedback checkpoints")
    return p


def select_llm_settings(base_dir, llm_config, args):
    # Default behavior: prompt every run (unless --no-prompt or explicit --provider is provided).
    should_prompt = (not args.no_prompt) and (args.provider is None) and sys.stdin.isatty()
    if not should_prompt:
        provider = args.provider or "openai"
        model = args.model
        base_url = args.base_url
        key_index = args.key_index
        debug = True if args.debug_llm else None
        return provider, model, base_url, key_index, debug

    providers = available_providers(llm_config)
    model_options = [p for p in providers if p != "template"]
    options = model_options + ["template"]
    default_index = options.index("openai") if "openai" in options else 0
    choice = _prompt_choice("选择要使用的模型提供方（provider）", options, default_index=default_index)
    if choice == "template":
        return "template", None, None, None, None

    provider_cfg = {}
    providers_cfg = llm_config.get("providers", {}) if isinstance(llm_config, dict) else {}
    if isinstance(providers_cfg, dict):
        provider_cfg = providers_cfg.get(choice, {}) or {}

    count = count_keys_for_provider(str(base_dir), choice)
    if count <= 0:
        print(f"提示：未检测到 {choice} 的 API Key，将自动回退到模板模式。")
        return "template", None, None, None, None

    if count > 1:
        raw_idx = _prompt_text(f"检测到 {count} 个 API Key，选择 key index", default_value="0")
        try:
            key_index = int(raw_idx)
        except ValueError:
            key_index = 0
    else:
        key_index = 0

    default_model = provider_cfg.get("model", "") if isinstance(provider_cfg, dict) else ""
    models = provider_cfg.get("models", []) if isinstance(provider_cfg, dict) else []
    if isinstance(models, list) and models:
        model_choice = _prompt_choice("选择 model", [str(m) for m in models], default_index=0)
        model = model_choice
    else:
        model = _prompt_text("输入 model", default_value=default_model)
        model = model if model != "" else None

    default_base_url = provider_cfg.get("base_url", "") if isinstance(provider_cfg, dict) else ""
    base_url = _prompt_text("输入 base_url", default_value=default_base_url)
    base_url = base_url if base_url != "" else None
    return choice, model, base_url, key_index, None


def collect_human_feedback(chapter_idx, scene_data, state_summary, no_human_feedback=False):
    should_prompt = (not no_human_feedback) and sys.stdin.isatty()
    defaults = {
        "chapter_goal": scene_data.get("prompt", "推进关系并揭示新信息"),
        "must_advance_1": "揭示旧信的一条具体内容",
        "must_advance_2": "至少一位角色提出下一步行动",
        "forbidden": "避免空泛重复抒情",
        "mid_twist": "新增一条信息差或误会",
        "ending_hook": "留下下一章可追踪的问题",
        "new_foreshadowing": [],
    }
    if not should_prompt:
        return defaults

    print("\n===== Human Feedback Checkpoint A（章前）=====")
    print("当前长期状态：")
    print(state_summary)
    chapter_goal = _prompt_text("本章主目标", defaults["chapter_goal"])
    must_advance_1 = _prompt_text("本章必须推进点 1", defaults["must_advance_1"])
    must_advance_2 = _prompt_text("本章必须推进点 2", defaults["must_advance_2"])
    forbidden = _prompt_text("本章禁止项", defaults["forbidden"])

    print("\n===== Human Feedback Checkpoint B（中段转折）=====")
    mid_twist = _prompt_text("本章中段转折类型", defaults["mid_twist"])

    print("\n===== Human Feedback Checkpoint C（章末钩子）=====")
    ending_hook = _prompt_text("本章结尾钩子", defaults["ending_hook"])

    print("\n===== Human Feedback 伏笔（可选）=====")
    new_foreshadowing_raw = _prompt_text("本章拟埋设的伏笔，多个用分号分隔", default_value="")
    new_foreshadowing = [s.strip() for s in new_foreshadowing_raw.split(";") if s.strip()]

    return {
        "chapter_goal": chapter_goal,
        "must_advance_1": must_advance_1,
        "must_advance_2": must_advance_2,
        "forbidden": forbidden,
        "mid_twist": mid_twist,
        "ending_hook": ending_hook,
        "new_foreshadowing": new_foreshadowing,
    }


def build_chapter_context(story_state, human_feedback):
    state_summary = summarize_story_state(story_state)
    feedback_summary = (
        f"本章主目标：{human_feedback.get('chapter_goal','')}\n"
        f"必须推进1：{human_feedback.get('must_advance_1','')}\n"
        f"必须推进2：{human_feedback.get('must_advance_2','')}\n"
        f"禁止项：{human_feedback.get('forbidden','')}\n"
        f"中段转折：{human_feedback.get('mid_twist','')}\n"
        f"章末钩子：{human_feedback.get('ending_hook','')}"
    )
    return state_summary + "\n\n" + feedback_summary


def main():
    args = _build_arg_parser().parse_args()
    seed_everything(42)
    base_dir = Path(__file__).resolve().parents[1]
    run_id = make_run_id()
    logger, log_path = setup_run_logger(base_dir, run_id, level=args.log_level)
    logger.info("[Main] run_start run_id=%s", run_id)

    world_data = load_json(base_dir / "configs" / "world.json")
    scene_data = load_json(base_dir / "configs" / "scene_01.json")
    relations_data = load_json(base_dir / "configs" / "relations.json")
    llm_config = load_json(base_dir / "configs" / "llm.json")
    story_state_path = base_dir / "memory" / "story_state.json"
    story_state = load_story_state(story_state_path)
    prompts_dir = base_dir / "prompts"
    character_prompt = _read_prompt(prompts_dir / "character_template.txt")
    narrator_prompt = _read_prompt(prompts_dir / "narrator_prompt.txt")
    reflection_prompt = _read_prompt(prompts_dir / "reflection_prompt.txt")
    planner_prompt = _read_prompt(prompts_dir / "planner_prompt.txt")

    world = WorldState(world_data)
    effective_relations_data = merge_relations(relations_data, story_state.get("relation_deltas", []))
    relations = RelationshipGraph(effective_relations_data)
    logger.info(
        "[Main] config_loaded scene_turns=%s prompt_files=%s",
        scene_data.get("turns", 6),
        "character_template.txt,narrator_prompt.txt,reflection_prompt.txt,planner_prompt.txt",
    )
    human_feedback = collect_human_feedback(
        story_state.get("chapter_index", 1),
        scene_data,
        summarize_story_state(story_state),
        no_human_feedback=args.no_human_feedback,
    )
    chapter_context = build_chapter_context(story_state, human_feedback)
    logger.info("[Main] human_feedback=%s", human_feedback)
    provider, model, base_url, key_index, debug = select_llm_settings(base_dir, llm_config, args)
    if debug is None:
        debug = True if args.debug_llm else None
    logger.info(
        "[Main] llm_selection provider=%s model=%s base_url=%s key_index=%s",
        provider,
        model or "(config default)",
        base_url or "(config default)",
        key_index if key_index is not None else "(auto)",
    )
    llm_client = build_client(
        str(base_dir),
        llm_config,
        provider=provider,
        model=model,
        base_url=base_url,
        key_index=key_index,
        debug=debug,
        logger=logger,
    )
    logger.info(
        "[Main] llm_client enabled=%s provider=%s model=%s",
        llm_client.enabled,
        llm_client.provider,
        llm_client.model,
    )
    agents = load_characters(relations, base_dir, llm_client, character_prompt, logger=logger)
    narrator_agent = NarratorAgent(llm_client=llm_client, prompt_template=narrator_prompt, logger=logger)
    reflection_agent = ReflectionAgent(llm_client=llm_client, prompt_template=reflection_prompt, logger=logger)
    planner_agent = StoryPlannerAgent(llm_client=llm_client, prompt_template=planner_prompt, logger=logger)

    orchestrator = Orchestrator(world, logger=logger)
    dialog, turn_plans = orchestrator.run(
        agents,
        scene_data.get("turns", 6),
        planner=planner_agent,
        chapter_context=chapter_context,
    )
    logger.info("[Main] dialog_generated count=%s", len(dialog))

    story_core = narrator_agent.compose(world, dialog)
    review = reflection_agent.review(world, dialog, story_core)
    story = story_core
    if review:
        logger.info("[Main] reflection_attached")
        story = f"{story}\n\n---\n【编辑评注】\n{review}"
    if turn_plans:
        plan_lines = []
        for idx, plan in enumerate(turn_plans, start=1):
            plan_lines.append(
                f"- 第{idx}轮：任务={plan.get('task','')}；重点={plan.get('focus','')}；规则={plan.get('progress_rule','')}"
            )
        story = f"{story}\n\n---\n【剧情任务轨迹】\n" + "\n".join(plan_lines)
    chapter_idx = story_state.get("chapter_index", 1)
    relation_deltas_this_chapter = update_relations(
        llm_client,
        relations_data,
        story_state.get("relation_deltas", []),
        dialog,
        story_core,
        chapter_idx,
        logger=logger,
    )
    if relation_deltas_this_chapter:
        rd_lines = [f"- {d.get('from','')}→{d.get('to','')}: {d.get('recent_change','')}" for d in relation_deltas_this_chapter]
        story = f"{story}\n\n---\n【本章关系变化】\n" + "\n".join(rd_lines)
    story = f"{story}\n\n---\n【人类反馈约束】\n{chapter_context}"
    story = f"【{run_id}】\n" + story
    output_path = base_dir / "outputs" / f"scene_01_story_{run_id}.md"
    logger.info("[Main] writing_output path=%s", output_path)
    save_text(output_path, story)
    summary_result = summarize_chapter(
        llm_client,
        story_core,
        dialog,
        turn_plans,
        human_feedback,
        logger=logger,
    )
    chapter_summary_dict = {
        "summary": summary_result.get("summary", story_core[:300]),
        "key_events": summary_result.get("key_events", []),
        "key_characters": summary_result.get("key_characters", []),
    }
    new_foreshadowing = list(summary_result.get("foreshadowing", []))
    human_foreshadowing = human_feedback.get("new_foreshadowing") or []
    new_foreshadowing.extend(human_foreshadowing)
    story_state = commit_chapter_state(
        story_state,
        chapter_summary=story_core,
        dialog=dialog,
        human_feedback=human_feedback,
        turns_plans=turn_plans,
        chapter_summary_dict=chapter_summary_dict,
        new_foreshadowing=new_foreshadowing,
        relation_deltas_this_chapter=relation_deltas_this_chapter,
    )
    save_story_state(story_state_path, story_state)
    logger.info("[Main] story_state_saved path=%s", story_state_path)

    logger.info("[Main] run_done output=%s", output_path)
    print(f"Story saved to: {output_path}")
    print(f"Log saved to: {log_path}")


if __name__ == "__main__":
    main()

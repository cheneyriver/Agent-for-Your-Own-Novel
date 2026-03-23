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
from reflection import ReflectionAgent
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
    prompts_dir = base_dir / "prompts"
    character_prompt = _read_prompt(prompts_dir / "character_template.txt")
    narrator_prompt = _read_prompt(prompts_dir / "narrator_prompt.txt")
    reflection_prompt = _read_prompt(prompts_dir / "reflection_prompt.txt")

    world = WorldState(world_data)
    relations = RelationshipGraph(relations_data)
    logger.info(
        "[Main] config_loaded scene_turns=%s prompt_files=%s",
        scene_data.get("turns", 6),
        "character_template.txt,narrator_prompt.txt,reflection_prompt.txt",
    )
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

    orchestrator = Orchestrator(world, logger=logger)
    dialog = orchestrator.run(agents, scene_data.get("turns", 6))
    logger.info("[Main] dialog_generated count=%s", len(dialog))

    story = narrator_agent.compose(world, dialog)
    review = reflection_agent.review(world, dialog, story)
    if review:
        logger.info("[Main] reflection_attached")
        story = f"{story}\n\n---\n【编辑评注】\n{review}"
    story = f"【{run_id}】\n" + story
    output_path = base_dir / "outputs" / f"scene_01_story_{run_id}.md"
    logger.info("[Main] writing_output path=%s", output_path)
    save_text(output_path, story)

    logger.info("[Main] run_done output=%s", output_path)
    print(f"Story saved to: {output_path}")
    print(f"Log saved to: {log_path}")


if __name__ == "__main__":
    main()

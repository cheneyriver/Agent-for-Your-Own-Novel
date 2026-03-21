from datetime import datetime
from pathlib import Path
import argparse
import sys
import uuid

from agent import CharacterAgent
from llm import available_providers, build_client, count_keys_for_provider
from narrator import narrate
from orchestrator import Orchestrator
from utils import load_json, save_text, seed_everything
from world import RelationshipGraph, WorldState


def load_characters(relations, base_dir, llm_client):
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
        agents.append(CharacterAgent(data, relations, llm_client))
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
    return p


def select_llm_settings(base_dir, llm_config, args):
    # Default behavior: prompt every run (unless --no-prompt or explicit --provider is provided).
    should_prompt = (not args.no_prompt) and (args.provider is None) and sys.stdin.isatty()
    if not should_prompt:
        provider = args.provider
        model = args.model
        base_url = args.base_url
        key_index = args.key_index
        debug = True if args.debug_llm else None
        return provider, model, base_url, key_index, debug

    providers = available_providers(llm_config)
    options = ["template"] + providers
    choice = _prompt_choice("选择要使用的模型提供方（provider）", options, default_index=0)
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

    world_data = load_json(base_dir / "configs" / "world.json")
    scene_data = load_json(base_dir / "configs" / "scene_01.json")
    relations_data = load_json(base_dir / "configs" / "relations.json")
    llm_config = load_json(base_dir / "configs" / "llm.json")

    world = WorldState(world_data)
    relations = RelationshipGraph(relations_data)
    provider, model, base_url, key_index, debug = select_llm_settings(base_dir, llm_config, args)
    if debug is None:
        debug = True if args.debug_llm else None
    llm_client = build_client(
        str(base_dir),
        llm_config,
        provider=provider,
        model=model,
        base_url=base_url,
        key_index=key_index,
        debug=debug,
    )
    agents = load_characters(relations, base_dir, llm_client)

    orchestrator = Orchestrator(world)
    dialog = orchestrator.run(agents, scene_data.get("turns", 6))

    story = narrate(world, dialog)
    run_id = make_run_id()
    story = f"【{run_id}】\n" + story
    output_path = base_dir / "outputs" / f"scene_01_story_{run_id}.md"
    save_text(output_path, story)

    print(f"Story saved to: {output_path}")


if __name__ == "__main__":
    main()

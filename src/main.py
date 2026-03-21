from datetime import datetime
from pathlib import Path
import uuid

from agent import CharacterAgent
from llm import build_client
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


def main():
    seed_everything(42)
    base_dir = Path(__file__).resolve().parents[1]

    world_data = load_json(base_dir / "configs" / "world.json")
    scene_data = load_json(base_dir / "configs" / "scene_01.json")
    relations_data = load_json(base_dir / "configs" / "relations.json")
    llm_config = load_json(base_dir / "configs" / "llm.json")

    world = WorldState(world_data)
    relations = RelationshipGraph(relations_data)
    llm_client = build_client(str(base_dir), llm_config)
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

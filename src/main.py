from pathlib import Path

from agent import CharacterAgent
from narrator import narrate
from orchestrator import Orchestrator
from utils import load_json, save_text, seed_everything
from world import RelationshipGraph, WorldState


def load_characters(relations, base_dir):
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
        agents.append(CharacterAgent(data, relations))
    return agents


def main():
    seed_everything(42)
    base_dir = Path(__file__).resolve().parents[1]

    world_data = load_json(base_dir / "configs" / "world.json")
    scene_data = load_json(base_dir / "configs" / "scene_01.json")
    relations_data = load_json(base_dir / "configs" / "relations.json")

    world = WorldState(world_data)
    relations = RelationshipGraph(relations_data)
    agents = load_characters(relations, base_dir)

    orchestrator = Orchestrator(world)
    dialog = orchestrator.run(agents, scene_data.get("turns", 6))

    story = narrate(world, dialog)
    output_path = base_dir / "outputs" / "scene_01_story.md"
    save_text(output_path, story)

    print(f"Story saved to: {output_path}")


if __name__ == "__main__":
    main()

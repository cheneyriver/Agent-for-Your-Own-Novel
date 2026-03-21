import json
import random
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_text(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def seed_everything(seed):
    random.seed(seed)


def pick(seq):
    return random.choice(seq)

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_api_keys(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _first_key(keys, name):
    values = keys.get(name, [])
    if isinstance(values, list) and values:
        return values[0]
    if isinstance(values, str):
        return values
    return ""


def _post_json(url, headers, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class LLMClient:
    def __init__(self, provider, model, api_key, base_url=None, debug=False):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.debug = debug

    @property
    def enabled(self):
        return bool(self.api_key and self.model and self.base_url)

    def generate(self, messages, temperature=0.8, max_tokens=200):
        if not self.enabled:
            raise RuntimeError("LLM client is not configured")

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if self.debug:
            print(f"[LLM] provider={self.provider} model={self.model}")
            print(f"[LLM] url={url}")

        try:
            data = _post_json(url, headers, payload)
        except HTTPError as e:
            if self.debug:
                print(f"[LLM] HTTPError {e.code}: {e.reason}")
                try:
                    body = e.read().decode("utf-8")
                    print(f"[LLM] body: {body}")
                except Exception:
                    pass
            raise RuntimeError(f"LLM HTTP error: {e.code}") from e
        except URLError as e:
            if self.debug:
                print(f"[LLM] URLError: {e.reason}")
            raise RuntimeError("LLM network error") from e

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("LLM returned no choices")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        return content.strip()



def _pick_provider_config(config, provider):
    providers = config.get("providers", {}) if isinstance(config, dict) else {}
    return providers.get(provider, {}) if isinstance(providers, dict) else {}



def build_client(base_dir, config):
    keys = load_api_keys(os.path.join(base_dir, "API_KEY_LIST"))
    provider = os.getenv("LLM_PROVIDER", config.get("provider", ""))
    provider_lower = provider.lower()
    provider_cfg = _pick_provider_config(config, provider_lower)

    model = os.getenv("LLM_MODEL", provider_cfg.get("model", config.get("model", "")))
    base_url = os.getenv("LLM_BASE_URL", provider_cfg.get("base_url", config.get("base_url", "")))
    debug = os.getenv("LLM_DEBUG", "") == "1"

    if provider_lower == "openai":
        api_key = _first_key(keys, "OPENAI") or _first_key(keys, "AGENT_KEY")
        base_url = base_url or "https://api.openai.com/v1"
        return LLMClient("openai", model, api_key, base_url, debug=debug)

    if provider_lower == "qwen":
        api_key = _first_key(keys, "Qwen")
        base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return LLMClient("qwen", model or "qwen-plus", api_key, base_url, debug=debug)

    return LLMClient(provider_lower, model, "", base_url, debug=debug)

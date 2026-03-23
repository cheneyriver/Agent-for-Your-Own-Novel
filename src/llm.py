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
    except json.JSONDecodeError:
        # Allow a simple line-based format as fallback:
        # OPENAI=sk-xxx
        # Qwen:sk-yyy
        try:
            text = open(path, "r", encoding="utf-8").read()
        except Exception:
            return {}
        data = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
            elif ":" in line:
                k, v = line.split(":", 1)
            else:
                continue
            k = k.strip()
            v = v.strip()
            if not k or not v:
                continue
            data.setdefault(k, []).append(v)
        return data


def _first_key(keys, name, index=None):
    values = keys.get(name, [])
    if isinstance(values, list):
        if index is not None:
            try:
                return values[int(index)]
            except (ValueError, IndexError):
                return ""
        return values[0] if values else ""
    if isinstance(values, str):
        return values
    return ""


def _post_json(url, headers, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class LLMClient:
    def __init__(self, provider, model, api_key, base_url=None, debug=False, logger=None):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.debug = debug
        self.logger = logger

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
        if self.logger:
            self.logger.info(
                "[LLMClient] request provider=%s model=%s temperature=%s max_tokens=%s messages=%s",
                self.provider,
                self.model,
                temperature,
                max_tokens,
                len(messages),
            )

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
        choice0 = choices[0] or {}
        message = choice0.get("message", {})
        content = message.get("content", "")
        finish_reason = choice0.get("finish_reason", "")
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        if self.logger:
            self.logger.info(
                "[LLMClient] response_ok chars=%s finish_reason=%s prompt_tokens=%s completion_tokens=%s",
                len(content or ""),
                finish_reason or "(unknown)",
                usage.get("prompt_tokens", "(n/a)"),
                usage.get("completion_tokens", "(n/a)"),
            )
            if finish_reason and finish_reason != "stop":
                self.logger.warning(
                    "[LLMClient] non_stop_finish reason=%s possible_truncation=True",
                    finish_reason,
                )
        return content.strip()



def _pick_provider_config(config, provider):
    providers = config.get("providers", {}) if isinstance(config, dict) else {}
    return providers.get(provider, {}) if isinstance(providers, dict) else {}


def _normalize_base_url(base_url):
    if not base_url:
        return base_url
    trimmed = base_url.rstrip("/")
    # Some users mistakenly put ".../v1/models"; our client will append "/chat/completions".
    if trimmed.endswith("/models"):
        trimmed = trimmed[: -len("/models")]
    return trimmed


def _get_key_index(explicit=None):
    if explicit is not None:
        return explicit
    raw = os.getenv("LLM_KEY_INDEX", "")
    if raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _case_insensitive_get(keys, name):
    if not isinstance(keys, dict):
        return None
    if name in keys:
        return name
    lower = name.lower()
    for k in keys.keys():
        if isinstance(k, str) and k.lower() == lower:
            return k
    return None


def _first_key_ci(keys, name, index=None):
    actual = _case_insensitive_get(keys, name)
    if not actual:
        return ""
    return _first_key(keys, actual, index=index)


def available_providers(config):
    if not isinstance(config, dict):
        return []
    providers = config.get("providers", {})
    if isinstance(providers, dict):
        return sorted([k for k in providers.keys() if isinstance(k, str)])
    return []


def count_keys_for_provider(base_dir, provider):
    keys = load_api_keys(os.path.join(base_dir, "API_KEY_LIST"))
    provider_lower = (provider or "").lower()

    if provider_lower == "openai":
        n1 = len(keys.get(_case_insensitive_get(keys, "OPENAI") or "OPENAI", []) or [])
        n2 = len(keys.get(_case_insensitive_get(keys, "AGENT_KEY") or "AGENT_KEY", []) or [])
        return max(n1, n2)
    if provider_lower == "qwen":
        n = len(keys.get(_case_insensitive_get(keys, "QWEN") or _case_insensitive_get(keys, "Qwen") or "Qwen", []) or [])
        return n
    return 0



def build_client(base_dir, config, provider=None, model=None, base_url=None, key_index=None, debug=None, logger=None):
    keys = load_api_keys(os.path.join(base_dir, "API_KEY_LIST"))
    provider = provider if provider is not None else os.getenv("LLM_PROVIDER", config.get("provider", ""))
    provider_lower = (provider or "").lower()
    provider_cfg = _pick_provider_config(config, provider_lower)

    model = model if model is not None else os.getenv("LLM_MODEL", provider_cfg.get("model", config.get("model", "")))
    base_url = base_url if base_url is not None else os.getenv("LLM_BASE_URL", provider_cfg.get("base_url", config.get("base_url", "")))
    base_url = _normalize_base_url(base_url)
    debug = debug if debug is not None else (os.getenv("LLM_DEBUG", "") == "1")
    key_index = _get_key_index(explicit=key_index)

    if provider_lower == "openai":
        api_key = _first_key_ci(keys, "OPENAI", key_index) or _first_key_ci(keys, "AGENT_KEY", key_index)
        base_url = _normalize_base_url(base_url) or "https://api.openai.com/v1"
        return LLMClient("openai", model, api_key, base_url, debug=debug, logger=logger)

    if provider_lower == "qwen":
        api_key = _first_key_ci(keys, "Qwen", key_index) or _first_key_ci(keys, "QWEN", key_index)
        base_url = _normalize_base_url(base_url) or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return LLMClient("qwen", model or "qwen-plus", api_key, base_url, debug=debug, logger=logger)

    return LLMClient(provider_lower, model, "", base_url, debug=debug, logger=logger)

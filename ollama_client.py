import json
import logging
import sys
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ollama_client")

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = _get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
SETTINGS_FILE = CONFIG_DIR / "app_settings.json"

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODELS_PREFERENCE = [
    "qwen3.5:4b",
    "qwen3.5:2b",
    "qwen3.5:0.8b",
    "llama3.2:3b",
    "llama3.1:8b",
    "mistral:latest",
]

class OllamaClient:
    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL):
        self.base_url = base_url.rstrip("/")
        self._cached_available_models: List[str] = []
        self._last_check_time: float = 0.0

    def is_available(self, timeout: float = 1.5) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers={"User-Agent": "Jennifer-AI"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self, refresh: bool = False, timeout: float = 2.0) -> List[str]:
        """Return list of model tags installed in Ollama."""
        import time
        now = time.time()
        if not refresh and self._cached_available_models and (now - self._last_check_time < 30):
            return self._cached_available_models

        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers={"User-Agent": "Jennifer-AI"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                    self._cached_available_models = models
                    self._last_check_time = now
                    return models
        except Exception as e:
            logger.debug(f"[Ollama] Failed to list models: {e}")
        return []

    def get_preferred_model(self) -> str:
        """Select the best installed model based on preference hierarchy."""
        available = self.list_models()
        if not available:
            return "qwen3.5:4b"

        # Check configured preference in settings
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cfg_model = data.get("ollama_model")
                    if cfg_model and any(m == cfg_model or m.startswith(cfg_model) for m in available):
                        return cfg_model
        except Exception:
            pass

        # Check against default preferences
        for pref in DEFAULT_MODELS_PREFERENCE:
            for avail in available:
                if avail == pref or avail.startswith(pref.split(":")[0]):
                    return avail

        # Return first available model
        return available[0]

    def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        timeout: float = 60.0,
    ) -> str:
        """Send a chat completion request to local Ollama."""
        selected_model = model or self.get_preferred_model()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": selected_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Jennifer-AI"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    msg = data.get("message", {}).get("content", "").strip()
                    # Clean reasoning tags like <think>...</think>
                    cleaned = re.sub(r"<think>.*?</think>", "", msg, flags=re.DOTALL).strip()
                    return cleaned or msg
                else:
                    logger.warning(f"[Ollama] Chat failed with HTTP {resp.status}")
                    return ""
        except Exception as e:
            logger.warning(f"[Ollama] Chat error: {e}")
            return ""

client = OllamaClient()

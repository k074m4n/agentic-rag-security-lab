import os
import re
import time
import random
import threading
from loguru import logger
from typing import Any, Dict, Optional

from smolagents.models import LiteLLMModel

# Global single-channel concurrency (only 1 request at a time)
_GLOBAL_CONCURRENCY = threading.Semaphore(1)

DEFAULT_MODEL_ID = os.getenv("LITELLM_MODEL", "openai/gpt-4.1-mini")

def _model_id_for_role(role: str) -> str:
    """
    Her rol için env'den uygun model id'sini seçer.
    Ayarlı değilse DEFAULT_MODEL_ID'ye düşer.
    """
    role = (role or "default").lower()

    role_env_map = {
        "manager": "LITELLM_MODEL_MANAGER",
        "kb_worker": "LITELLM_MODEL_KB_WORKER",
        "chat": "LITELLM_MODEL_CHAT",
        "code": "LITELLM_MODEL_CODE",
        "supervisor": "LITELLM_MODEL_SUPERVISOR",
        "default": "LITELLM_MODEL",
    }

    env_name = role_env_map.get(role)
    if env_name:
        val = os.getenv(env_name)
        if val:
            return val

    # Role için özel env yoksa, genel default'a dön
    return DEFAULT_MODEL_ID


# RPM throttling with jitter to avoid thundering herd
class SimpleRateLimiter:
    def __init__(self, rpm: int = 8):
        self.interval = 60.0 / float(rpm)
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        with self._lock:
            now = time.time()
            wait_for = max(0.0, self._last + self.interval - now)
            wait_for += random.uniform(0.0, 0.2)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last = time.time()


rate_limiter = SimpleRateLimiter(rpm=int(os.getenv("GLOBAL_RPM", "8")))

# Retry-After parsing helpers
_RETRY_AFTER_RE = re.compile(r"Retry(?:-|\s)?After['\"]?\s*[:=]\s*['\"]?(\d+)", re.IGNORECASE)
_SECONDS_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s['\"]?", re.IGNORECASE)


def _parse_retry_after_seconds(message: str) -> Optional[int]:
    m = _RETRY_AFTER_RE.search(message)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    m2 = _SECONDS_RE.search(message)
    if m2:
        try:
            return int(m2.group(1))
        except Exception:
            pass
    return None


class ThrottledLiteLLMModel(LiteLLMModel):
    """
    Wrap LiteLLMModel with global rate-limit + single concurrency + backoff.
    Also guards occasional empty/choices=[] edge-cases with retry/fallback.
    """

    def __init__(
        self,
        model_id: str,
        api_key: Optional[str] = None,
        max_retries: int = 0,  # LiteLLM internal retry => 0
        request_timeout: int = 60,
        temperature: float = 0.1,
        top_p: float = 0.9,
        max_output_tokens: int = 800,
        fallback_model_id: Optional[str] = None,  # env'den make_model içinde geçeceğiz
        **kwargs: Any,
    ):
        super().__init__(
            model_id=model_id,
            api_key=api_key,
            max_retries=max_retries,
            request_timeout=request_timeout,
            temperature=temperature,
            top_p=top_p,
            **kwargs,
        )
        self._max_output_tokens = max_output_tokens
        self._fallback_model_id = fallback_model_id
        self._using_fallback = False  # başlangıçta ana modeldeyiz

    def generate(self, *args, **kwargs):
        # Varsayılan / güvenli max_tokens
        max_tokens = kwargs.get("max_tokens", None)
        if max_tokens is None:
            kwargs["max_tokens"] = max(1, int(self._max_output_tokens))
        else:
            try:
                max_tokens_int = int(max_tokens)
            except Exception:
                max_tokens_int = 0
            if max_tokens_int < 1:
                logger.warning(
                    f"[ThrottledLiteLLMModel] Invalid max_tokens={max_tokens!r}; "
                    f"overriding to {max(1, int(self._max_output_tokens))}."
                )
                kwargs["max_tokens"] = max(1, int(self._max_output_tokens))

        attempt = 0
        base = 1.6  # exponential backoff tabanı

        no_choice_retry_limit = int(os.getenv("LITELLM_NO_CHOICE_MAX_RETRIES", "3"))
        no_choice_hits = 0
        
        rate_limit_hits = 0
        max_rate_limit_retries = int(os.getenv("LITELLM_RATE_LIMIT_MAX_RETRIES", "5"))

        while True:
            attempt += 1
            rate_limiter.wait()
            with _GLOBAL_CONCURRENCY:
                try:
                    # Asıl model çağrısı
                    chat_message = super().generate(*args, **kwargs)

                    # ---- BOŞ MESAJ GUARD'I ----
                    content = getattr(chat_message, "content", None)
                    tool_calls = getattr(chat_message, "tool_calls", None)

                    if (
                        (content is None or (isinstance(content, str) and content.strip() == ""))
                        and not tool_calls
                    ):
                        # Bunu, OpenAI/Gemini "choices=[]" hatası gibi ele al
                        raise RuntimeError(
                            "Model returned empty message (no choices / no content / no tool_calls)."
                        )
                    # -----------------------------

                    return chat_message

                except Exception as e:
                    msg = str(e)

                    # 1) "no choices" / boş cevap case'leri => retry + optional fallback
                    if (
                        "returned no choices" in msg
                        or "'choices': []" in msg
                        or "no choices / no content / no tool_calls" in msg
                    ):
                        no_choice_hits += 1

                        # İkinci kez olursa fallback modele geç (varsa)
                        if (
                            self._fallback_model_id
                            and not self._using_fallback
                            and no_choice_hits >= 2
                        ):
                            logger.warning(
                                f"[ThrottledLiteLLMModel] Empty response from {self.model_id}; "
                                f"switching to fallback model {self._fallback_model_id}."
                            )
                            self.model_id = self._fallback_model_id
                            self._using_fallback = True
                            attempt = 0
                            continue

                        # Çok fazla denedik, hâlâ olmuyorsa pes et
                        if no_choice_hits > no_choice_retry_limit:
                            raise

                        # Exponential backoff + küçük jitter
                        sleep_s = min(5, base ** no_choice_hits) + random.uniform(0.0, 0.4)
                        time.sleep(sleep_s)
                        continue

                    # 2) 429 / RateLimit / QUOTA case'leri => backoff + optional fallback
                    if "429" in msg or "RateLimit" in msg or "RESOURCE_EXHAUSTED" in msg:
                        # Eğer quota bitti mesajıysa retry etmenin anlamı yok, direkt fırlat
                        if "quota" in msg.lower():
                            raise

                        rate_limit_hits += 1
                        if rate_limit_hits > max_rate_limit_retries:
                            # Çok fazla denedik, hâlâ 429 geliyorsa pes et
                            raise

                        # Birkaç denemeden sonra fallback modele (ör: lokal Qwen) geç
                        if (
                            self._fallback_model_id
                            and not self._using_fallback
                            and attempt >= 2
                        ):
                            logger.warning(
                                f"[ThrottledLiteLLMModel] Repeated 429 from {self.model_id}; "
                                f"switching to fallback model {self._fallback_model_id}."
                            )
                            self.model_id = self._fallback_model_id
                            self._using_fallback = True

                            attempt = 0
                            no_choice_hits = 0
                            continue

                        ra = _parse_retry_after_seconds(msg)
                        if ra is None:
                            sleep_s = min(30, base ** attempt) + random.uniform(0.0, 0.6)
                        else:
                            sleep_s = int(ra) + random.uniform(0.0, 0.6)
                        time.sleep(sleep_s)
                        continue


                    # 3) Diğer hatalar => gerçekten fatal, yukarı fırlat
                    raise


def make_model(role: str = "default") -> "ThrottledLiteLLMModel":
    """
    Verilen role göre uygun LLM modelini seçer.
    Örn:
      make_model("manager")
      make_model("kb_worker")
      make_model("chat")
    """
    model_id = _model_id_for_role(role)
    fallback_model_id = os.getenv("LITELLM_FALLBACK_MODEL") or None

    try:
        max_output_tokens = int(os.getenv("LITELLM_MAX_OUTPUT_TOKENS", "2048"))
    except Exception:
        max_output_tokens = 2048
    max_output_tokens = max(1, max_output_tokens)

    return ThrottledLiteLLMModel(
        model_id=model_id,
        max_output_tokens=max_output_tokens,
        fallback_model_id=fallback_model_id,
    )

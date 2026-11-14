"""Groq LLM Provider using the OpenAI-compatible SDK.

Uses the `openai` Python package pointed at Groq's OpenAI-compatible endpoint.
Implements an internal model fallback: on a 429 rate limit with the default
model (`llama-3.3-70b-versatile`), the exact same prompt is retried once with
`llama-3.1-8b-instant`.
"""

import ast
import json
import uuid
from typing import Any

from friday.core.exceptions import LLMProviderError
from friday.core.logging import get_logger
from friday.core.types import Message, Role, ToolCall
from friday.llm.base import BaseLLMProvider

try:  # Soft dependency: SDK only required for live calls, not for import/tests
    import openai as _openai_sdk
except ImportError:  # pragma: no cover - exercised only when SDK absent
    _openai_sdk = None

logger = get_logger("llm.groq")

GROQ_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"
GROQ_FALLBACK_MODEL = "openai/gpt-oss-20b"
GROQ_UNIVERSAL_FALLBACK_MODEL = "openai/gpt-oss-120b"

# TASK-REL-031: appended to the last-resort text-only TPM retry. When a
# request is too large to carry its tools, the model must not improvise
# the facts a tool would have checked — the TASK-REL-010 live proof of
# the failover quality gap was exactly that: a hedged, invented answer
# to "time in Tokyo" because the clock tool had been stripped.
_TOOLS_UNAVAILABLE_NOTICE = (
    "Tools are unavailable for this single response because the request "
    "exceeded the provider's size limit. Do not guess or invent facts that "
    "a tool would normally check (such as the current time, stored "
    "memories, or system state). If the user's request needs a tool, say "
    "plainly that you cannot check it right now; otherwise answer only "
    "from what the conversation already establishes."
)


def _is_tpm_sized_error(err_text: str) -> bool:
    """Detect TPM / request-too-large rejections in an error's lowered text."""
    return (
        "tpm" in err_text
        or "too large" in err_text
        or "token" in err_text
        or "413" in err_text
    )


class _RateLimitedError(Exception):
    """Internal signal that the current model hit a 429 and a fallback may help."""


class _ModelNotFoundError(Exception):
    """Internal signal that the current model returned 404 model_not_found."""


def _is_rate_limit(error: Exception) -> bool:
    """Detect rate limits (429 or 413 TPM limits) across SDK exceptions."""
    if _openai_sdk is not None and isinstance(error, _openai_sdk.RateLimitError):
        return True
    if getattr(error, "status_code", None) in (413, 429):
        return True
    err = str(error).lower()
    return (
        "429" in err
        or "413" in err
        or "rate limit" in err
        or "rate_limit_exceeded" in err
        or "tpm" in err
        or "tokens per minute" in err
    )


def _is_model_not_found(error: Exception) -> bool:
    """Detect a 404 model_not_found (including decommissioned models)."""
    if _openai_sdk is not None and isinstance(error, _openai_sdk.NotFoundError):
        return True
    if getattr(error, "status_code", None) == 404:
        return True
    err = str(error).lower()
    return "404" in err or "model_not_found" in err or "model not found" in err or "decommissioned" in err


def _error_body_dict(error: Exception) -> dict[str, Any] | None:
    """Best-effort access to the provider's structured error body.

    The OpenAI SDK stores the parsed body on the exception (``error.body``);
    when only the string form survives, it embeds the body as a Python dict
    repr after the ``"Error code: NNN - "`` prefix, which ``ast.literal_eval``
    can still read. Returns None when no structured body is available.
    """
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        return body
    text = str(error)
    idx = text.find(" - ")
    if idx >= 0:
        try:
            parsed = ast.literal_eval(text[idx + 3 :].strip())
        except (ValueError, SyntaxError):
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _is_tool_use_failed(error: Exception) -> bool:
    """Detect Groq's 400 tool_use_failed rejection.

    Groq answers 'Tool choice is none, but model called a tool' when the
    model emits a tool call for a request that carried no usable tools —
    which is exactly the shape of this provider's own TPM retry (tools
    stripped) and of any caller that disables tools for a turn. The
    conversation still solicits tool use, so the model is not at fault;
    the request shape is. (TASK-REL-022, production 2026-11-14.)
    """
    body = _error_body_dict(error)
    if body is not None:
        err = body.get("error") or {}
        if isinstance(err, dict) and err.get("code") == "tool_use_failed":
            return True
    text = str(error).lower()
    return "tool_use_failed" in text or "tool choice is none" in text


def _extract_failed_tool_call(error: Exception) -> tuple[str, dict[str, Any]] | None:
    """Recover the attempted tool call Groq preserves in the error body.

    A tool_use_failed body carries ``failed_generation`` — the generation
    Groq refused — as a JSON string like
    ``{"name": "memora_memory", "arguments": {"query": "safe word"}}``.
    Returns (name, arguments) when it parses into that shape, else None
    (some models emit raw non-JSON generations, e.g. source code as
    arguments, which cannot be executed safely sight-unseen).
    """
    body = _error_body_dict(error)
    if body is None:
        return None
    err = body.get("error") or {}
    if not isinstance(err, dict):
        return None
    generation = err.get("failed_generation")
    if isinstance(generation, str):
        try:
            generation = json.loads(generation)
        except json.JSONDecodeError:
            return None
    if not isinstance(generation, dict):
        return None
    name = generation.get("name")
    arguments = generation.get("arguments")
    if not isinstance(name, str) or not name:
        return None
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"raw_arguments": arguments}
    if not isinstance(arguments, dict):
        return None
    return name, arguments


def compact_messages_and_tools(
    messages: list[Message],
    tools: list[dict[str, Any]] | None = None,
    include_tools: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
    """Compact messages and tools to comfortably fit within free-tier provider TPM limits (e.g. Groq 8k TPM)."""
    if not messages:
        return [], None

    system_msgs = [m for m in messages if m.role == Role.SYSTEM]
    other_msgs = [m for m in messages if m.role != Role.SYSTEM]

    recent_msgs = other_msgs[-4:] if len(other_msgs) > 4 else other_msgs

    compacted_dicts: list[dict[str, Any]] = []
    for sm in system_msgs:
        d = sm.to_provider_dict()
        if isinstance(d.get("content"), str) and len(d["content"]) > 3000:
            d["content"] = d["content"][:3000] + "\n...[truncated for token limit]"
        compacted_dicts.append(d)

    for om in recent_msgs:
        d = om.to_provider_dict()
        if isinstance(d.get("content"), str) and len(d["content"]) > 1000:
            d["content"] = d["content"][:1000] + "\n...[truncated]"
        compacted_dicts.append(d)

    compacted_tools = tools if include_tools else None
    return compacted_dicts, compacted_tools


class GroqLLMProvider(BaseLLMProvider):
    """LLM Provider for Groq via the OpenAI SDK with automatic model fallback on 429."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = GROQ_DEFAULT_BASE_URL,
        model: str = GROQ_DEFAULT_MODEL,
        fallback_model: str = GROQ_FALLBACK_MODEL,
        universal_fallback_model: str = GROQ_UNIVERSAL_FALLBACK_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 60.0,
        credential_pool: Any | None = None,
        client: Any | None = None,
    ):
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.credential_pool = credential_pool
        if not api_key and credential_pool is not None:
            try:
                api_key = credential_pool.get_active_key()
            except Exception:
                api_key = None
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.fallback_model = fallback_model
        self.universal_fallback_model = universal_fallback_model
        self.timeout = timeout
        self._clients: dict[str, Any] = {}
        # An explicitly supplied SDK-compatible client is useful for custom
        # transports and tests. Keep it separate from keyed production clients
        # so an injected mock can never silently fall through to the network.
        self._client = client

    @property
    def provider_name(self) -> str:
        return "groq"

    def _get_active_api_key(self) -> str:
        if self.credential_pool:
            try:
                key = self.credential_pool.get_active_key()
                if key and key.strip():
                    return key.strip()
            except Exception:
                pass
        return self.api_key

    def _get_client_for_key(self, api_key: str) -> Any:
        if self._client is not None:
            return self._client
        if _openai_sdk is None:
            raise LLMProviderError(
                "The 'openai' Python package is required for the Groq provider. "
                "Install it with: pip install openai"
            )
        if not api_key:
            raise LLMProviderError("Groq API key is not configured (FRIDAY_GROQ_API_KEY)")
        if api_key not in self._clients:
            self._clients[api_key] = _openai_sdk.OpenAI(
                api_key=api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._clients[api_key]

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Call Groq chat completions with automatic multi-key pool rotation and in-provider model fallbacks."""
        pool_creds = getattr(self.credential_pool, "credentials", []) if self.credential_pool else []
        max_attempts = max(1, len(pool_creds))
        last_error = None

        for attempt in range(max_attempts):
            active_key = self._get_active_api_key()
            if not active_key:
                raise LLMProviderError("Groq API key is not configured (FRIDAY_GROQ_API_KEY)")

            try:
                return self._generate_with_key_and_model(active_key, self.model, messages, tools)
            except _RateLimitedError as primary_error:
                last_error = primary_error
                if self.credential_pool and len(pool_creds) > 1:
                    self.credential_pool.report_failure(active_key, error=primary_error)
                    logger.warning(
                        f"Groq key rate limited (429/413). Rotating to next key in pool ({attempt + 1}/{max_attempts})..."
                    )
                    continue

                if self.fallback_model and self.fallback_model != self.model:
                    logger.warning(
                        f"Groq rate limit (429) on model '{self.model}'. "
                        f"Retrying same prompt with fallback model '{self.fallback_model}'..."
                    )
                    try:
                        return self._generate_with_key_and_model(active_key, self.fallback_model, messages, tools)
                    except _ModelNotFoundError:
                        logger.warning(
                            f"Groq fallback model '{self.fallback_model}' not found (404). "
                            f"Retrying with universally available model '{self.universal_fallback_model}'..."
                        )
                        return self._generate_with_key_and_model(active_key, self.universal_fallback_model, messages, tools)
                    except _RateLimitedError as fallback_error:
                        raise LLMProviderError(
                            f"Groq rate limited on both '{self.model}' and '{self.fallback_model}': {fallback_error}"
                        ) from fallback_error
                raise LLMProviderError(f"Groq rate limited on '{self.model}': {primary_error}") from primary_error
            except _ModelNotFoundError:
                logger.warning(
                    f"Groq model '{self.model}' not found (404). Retrying same prompt with "
                    f"universally available model '{self.universal_fallback_model}'..."
                )
                try:
                    return self._generate_with_key_and_model(active_key, self.universal_fallback_model, messages, tools)
                except (_RateLimitedError, _ModelNotFoundError) as universal_error:
                    raise LLMProviderError(
                        f"Groq failed on '{self.model}' (model_not_found) and on "
                        f"'{self.universal_fallback_model}': {universal_error}"
                    ) from universal_error

        raise LLMProviderError(f"All {max_attempts} Groq credentials exhausted: {last_error}")

    def _generate_with_key_and_model(
        self,
        api_key: str,
        model: str,
        messages: list[Message],
        tools: list[dict[str, Any]] | None,
    ) -> Message:
        client = self._get_client_for_key(api_key)
        
        # Check if messages + tools are excessively large
        total_est_chars = sum(len(m.content or "") for m in messages)
        should_compact = total_est_chars > 8000
        
        msg_dicts, active_tools = compact_messages_and_tools(
            messages,
            tools,
            include_tools=True
        ) if should_compact else ([m.to_provider_dict() for m in messages], tools)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": msg_dicts,
            "temperature": self.temperature,
            "max_tokens": min(self.max_tokens, 2048),
        }
        if active_tools:
            kwargs["tools"] = active_tools
            kwargs["tool_choice"] = "auto"

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            err_text = str(e).lower()
            # If rate limit is due to TPM / Request too large, climb the
            # TASK-REL-031 retry ladder (compact with tools retained first;
            # text-only only as the last resort) instead of disarming the
            # request on the first failure, which is what made failover-mode
            # answers guess at tool-shaped questions (TASK-REL-010 residual).
            if _is_tpm_sized_error(err_text) and active_tools:
                outcome = self._tpm_retry_ladder(client, model, messages, tools, kwargs)
                if isinstance(outcome, Message):
                    return outcome
                e = outcome

            if _is_tool_use_failed(e):
                return self._handle_tool_use_failed(
                    e,
                    client=client,
                    model=model,
                    msg_dicts=msg_dicts,
                    had_tools=bool(active_tools),
                )

            if _is_rate_limit(e):
                raise _RateLimitedError(str(e)) from e
            if _is_model_not_found(e):
                raise _ModelNotFoundError(str(e)) from e
            err_msg = str(e)
            if self.api_key and self.api_key in err_msg:
                err_msg = err_msg.replace(self.api_key, "***")
            logger.error(f"Groq API request failed: {err_msg}")
            raise LLMProviderError(f"Groq API request failed: {err_msg}") from e

        return self._parse_response(response)

    def _tpm_retry_ladder(
        self,
        client: Any,
        model: str,
        messages: list[Message],
        tools: list[dict[str, Any]] | None,
        kwargs: dict[str, Any],
    ) -> Message | Exception:
        """Retry a TPM / request-too-large failure without disarming the turn.

        TASK-REL-031 (the TASK-REL-010 failover quality gap): the old
        behaviour stripped the tools on the FIRST TPM failure, so when
        Groq served as the exhaustion fallback, tool-shaped questions
        (current time, memory, actions) were answered from text alone —
        hedged guesses instead of tool calls. The ladder:

        - Rung 1: compact the conversation (``compact_messages_and_tools``)
          but KEEP the tools attached, so the turn's tool discipline
          survives TPM pressure.
        - Rung 2 (last resort): the old text-only retry, now carrying
          ``_TOOLS_UNAVAILABLE_NOTICE`` so the model states plainly that
          it cannot check, instead of inventing an answer.

        Returns the parsed Message on success; on failure returns the
        exception so the caller's shared handlers (tool_use_failed
        recovery, rate-limit rotation, model fallback) can judge it —
        the same contract the inline strip-retry had.
        """
        logger.warning(
            "Groq TPM limit reached with tools. Retrying with compacted "
            "messages and tools retained..."
        )
        compact_msgs, kept_tools = compact_messages_and_tools(
            messages, tools, include_tools=True
        )
        retry_kwargs = dict(kwargs)
        retry_kwargs["messages"] = compact_msgs
        retry_kwargs["max_tokens"] = min(self.max_tokens, 1024)
        if kept_tools:
            retry_kwargs["tools"] = kept_tools
            retry_kwargs["tool_choice"] = "auto"
        try:
            return self._parse_response(client.chat.completions.create(**retry_kwargs))
        except Exception as compact_error:
            if _is_tool_use_failed(compact_error) or not _is_tpm_sized_error(
                str(compact_error).lower()
            ):
                return compact_error

        logger.warning(
            "Groq TPM limit persisted after compaction. Retrying text-only "
            "with an explicit no-tools notice..."
        )
        strip_msgs, _ = compact_messages_and_tools(messages, None, include_tools=False)
        strip_kwargs = dict(kwargs)
        strip_kwargs["messages"] = strip_msgs + [
            {"role": "system", "content": _TOOLS_UNAVAILABLE_NOTICE}
        ]
        strip_kwargs.pop("tools", None)
        strip_kwargs.pop("tool_choice", None)
        strip_kwargs["max_tokens"] = min(self.max_tokens, 1024)
        try:
            return self._parse_response(client.chat.completions.create(**strip_kwargs))
        except Exception as strip_error:
            return strip_error

    def _handle_tool_use_failed(
        self,
        error: Exception,
        *,
        client: Any,
        model: str,
        msg_dicts: list[dict[str, Any]],
        had_tools: bool,
    ) -> Message:
        """Resolve a Groq tool_use_failed 400 without leaking it upstream.

        TASK-REL-022 (production 2026-11-14): the TPM retry strips tools
        from the request, but the conversation still solicits tool calls —
        gpt-oss-120b called memora_memory anyway and Groq's 400 became the
        user-visible chat reply. Two honest resolutions, never a raw 400:

        - Tools WERE attached for this turn (the strip was this provider's
          own TPM fallback): recover the attempted call Groq preserved in
          ``failed_generation`` and return it as a real ToolCall, so the
          agent loop executes exactly what the model intended — the same
          recovery philosophy as TASK-REL-006A's markup recovery.
        - Tools were genuinely disabled by the caller (or the attempted
          generation is not safely parseable): retry ONCE with an explicit
          plain-text instruction appended. A second failure raises a
          sanitised LLMProviderError — the raw provider body (which embeds
          the model's generation) never travels upstream.
        """
        recovered = _extract_failed_tool_call(error) if had_tools else None
        if recovered is not None:
            name, arguments = recovered
            logger.warning(
                f"Groq rejected a '{name}' tool call made while tools were stripped "
                "for TPM headroom; recovering the attempted call for the agent loop."
            )
            return Message(
                role=Role.ASSISTANT,
                content="",
                tool_calls=[
                    ToolCall(
                        id=f"groq-recovered-{uuid.uuid4().hex[:12]}",
                        name=name,
                        arguments=arguments,
                    )
                ],
            )

        logger.warning(
            "Groq tool_use_failed with tools disabled for this call; "
            "retrying once with an explicit plain-text instruction."
        )
        retry_messages = list(msg_dicts) + [
            {
                "role": "system",
                "content": (
                    "Tool calls are disabled for this response. Do not call any "
                    "tool and do not emit tool markup. Answer the user in plain "
                    "text only."
                ),
            }
        ]
        try:
            response = client.chat.completions.create(
                model=model,
                messages=retry_messages,
                temperature=self.temperature,
                max_tokens=min(self.max_tokens, 1024),
            )
        except Exception as retry_error:
            raise LLMProviderError(
                "Groq model attempted a tool call while tools were disabled "
                "for this request (tool_use_failed), and the plain-text "
                "retry failed as well."
            ) from retry_error
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: Any) -> Message:
        """Convert an OpenAI-SDK ChatCompletion into a FRIDAY Message."""
        try:
            choice = response.choices[0]
            choice_msg = choice.message
        except (AttributeError, IndexError) as e:
            raise LLMProviderError("Malformed response from Groq API: no choices") from e

        content = getattr(choice_msg, "content", None) or ""
        tool_calls_raw = getattr(choice_msg, "tool_calls", None)
        tool_calls: list[ToolCall] | None = None

        if not tool_calls_raw and content:
            # TASK-REL-006A: gpt-oss models on Groq sometimes spell the tool
            # call as text markup (<tool name="..." params='...'/>) instead of
            # using the structured channel. Recover it here so the call is
            # executed, never shown to the user as the reply.
            from friday.llm.tool_markup import extract_markup_tool_calls

            markup_calls, remaining = extract_markup_tool_calls(content)
            if markup_calls:
                return Message(
                    role=Role.ASSISTANT, content=remaining, tool_calls=markup_calls
                )

        if tool_calls_raw:
            tool_calls = []
            for tc in tool_calls_raw:
                func = getattr(tc, "function", None)
                args_raw = getattr(func, "arguments", "{}") if func else "{}"
                if isinstance(args_raw, str):
                    try:
                        args_dict = json.loads(args_raw)
                    except json.JSONDecodeError:
                        args_dict = {"raw_arguments": args_raw}
                else:
                    args_dict = args_raw or {}
                tool_calls.append(
                    ToolCall(
                        id=getattr(tc, "id", "") or "",
                        name=getattr(func, "name", "") if func else "",
                        arguments=args_dict,
                    )
                )

        return Message(role=Role.ASSISTANT, content=content, tool_calls=tool_calls)

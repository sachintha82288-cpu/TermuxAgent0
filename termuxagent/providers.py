"""Built-in catalogue of 27 API providers (all OpenAI-compatible).

Every cloud provider speaks the same ``POST {base_url}/chat/completions``
protocol with Bearer auth, so one client covers them all.  Local servers
(Ollama, LM Studio, llama.cpp) need no API key.  ``custom`` lets you point
the agent at any other OpenAI-compatible endpoint (vLLM, LiteLLM, OpenProxy…).
"""
from __future__ import annotations

from typing import Dict, List, Optional

PROVIDERS: List[Dict] = [
    # ------------------------------------------------------------------ cloud
    {
        "id": "groq", "name": "Groq", "group": "cloud",
        "base_url": "https://api.groq.com/openai/v1",
        "key_url": "https://console.groq.com/keys", "key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct-maas",
            "openai/gpt-oss-120b", "openai/gpt-oss-20b",
            "moonshotai/kimi-k2-instruct-0905", "qwen/qwen3-32b",
            "deepseek-r1-distill-llama-70b",
        ],
        "tools": True, "note": "free tier · fastest for Termux (recommended)",
    },
    {
        "id": "openai", "name": "OpenAI", "group": "cloud",
        "base_url": "https://api.openai.com/v1",
        "key_url": "https://platform.openai.com/api-keys", "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4.1-mini",
        "models": ["gpt-4.1-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini", "o4-mini"],
        "tools": True,
    },
    {
        "id": "anthropic", "name": "Anthropic (Claude)", "group": "cloud",
        "base_url": "https://api.anthropic.com/v1",
        "key_url": "https://console.anthropic.com/settings/keys", "key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
        "models": ["claude-sonnet-4-20250514", "claude-3-7-sonnet-20250219",
                   "claude-3-5-haiku-20241022"],
        "tools": True, "headers": {"anthropic-version": "2023-06-01"},
        "key_header": "x-api-key",
    },
    {
        "id": "gemini", "name": "Google Gemini", "group": "cloud",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_url": "https://aistudio.google.com/apikey", "key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        "tools": True, "note": "generous free tier via AI Studio",
    },
    {
        "id": "openrouter", "name": "OpenRouter", "group": "cloud",
        "base_url": "https://openrouter.ai/api/v1",
        "key_url": "https://openrouter.ai/keys", "key_env": "OPENROUTER_API_KEY",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "models": ["meta-llama/llama-3.3-70b-instruct", "openai/gpt-4o-mini",
                   "anthropic/claude-3.5-haiku", "google/gemini-2.0-flash-001",
                   "deepseek/deepseek-chat", "qwen/qwen-2.5-72b-instruct"],
        "tools": True, "note": "one key → hundreds of models",
    },
    {
        "id": "xai", "name": "xAI (Grok)", "group": "cloud",
        "base_url": "https://api.x.ai/v1",
        "key_url": "https://console.x.ai", "key_env": "XAI_API_KEY",
        "default_model": "grok-4-fast",
        "models": ["grok-4", "grok-4-fast", "grok-3", "grok-3-mini"],
        "tools": True,
    },
    {
        "id": "deepseek", "name": "DeepSeek", "group": "cloud",
        "base_url": "https://api.deepseek.com/v1",
        "key_url": "https://platform.deepseek.com/api_keys", "key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "tools": True, "note": "very cheap, strong coding models",
    },
    {
        "id": "mistral", "name": "Mistral AI", "group": "cloud",
        "base_url": "https://api.mistral.ai/v1",
        "key_url": "https://console.mistral.ai/api-keys", "key_env": "MISTRAL_API_KEY",
        "default_model": "mistral-large-latest",
        "models": ["mistral-large-latest", "mistral-small-latest",
                   "open-mistral-nemo", "codestral-latest"],
        "tools": True,
    },
    {
        "id": "together", "name": "Together AI", "group": "cloud",
        "base_url": "https://api.together.xyz/v1",
        "key_url": "https://api.together.ai/settings/api-keys", "key_env": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo",
                   "deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct-Turbo"],
        "tools": True,
    },
    {
        "id": "cerebras", "name": "Cerebras", "group": "cloud",
        "base_url": "https://api.cerebras.ai/v1",
        "key_url": "https://cloud.cerebras.ai", "key_env": "CEREBRAS_API_KEY",
        "default_model": "llama-3.3-70b",
        "models": ["llama-3.3-70b", "llama3.1-8b", "qwen-3-32b", "gpt-oss-120b"],
        "tools": True, "note": "insanely fast inference, free tier",
    },
    {
        "id": "sambanova", "name": "SambaNova", "group": "cloud",
        "base_url": "https://api.sambanova.ai/v1",
        "key_url": "https://cloud.sambanova.ai/apis", "key_env": "SAMBANOVA_API_KEY",
        "default_model": "Meta-Llama-3.3-70B-Instruct",
        "models": ["Meta-Llama-3.3-70B-Instruct", "DeepSeek-R1-Distill-Llama-70B",
                   "Qwen3-32B"],
        "tools": True,
    },
    {
        "id": "fireworks", "name": "Fireworks AI", "group": "cloud",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "key_url": "https://fireworks.ai/account/api-keys", "key_env": "FIREWORKS_API_KEY",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "models": ["accounts/fireworks/models/llama-v3p3-70b-instruct",
                   "accounts/fireworks/models/deepseek-v3",
                   "accounts/fireworks/models/kimi-k2-instruct"],
        "tools": True,
    },
    {
        "id": "perplexity", "name": "Perplexity", "group": "cloud",
        "base_url": "https://api.perplexity.ai",
        "key_url": "https://www.perplexity.ai/settings/api", "key_env": "PERPLEXITY_API_KEY",
        "default_model": "sonar",
        "models": ["sonar", "sonar-pro", "sonar-reasoning", "sonar-deep-research"],
        "tools": False, "note": "web-search answers (no function calling)",
    },
    {
        "id": "hyperbolic", "name": "Hyperbolic", "group": "cloud",
        "base_url": "https://api.hyperbolic.xyz/v1",
        "key_url": "https://app.hyperbolic.xyz/settings", "key_env": "HYPERBOLIC_API_KEY",
        "default_model": "meta-llama/meta-llama-3.1-70b-instruct",
        "models": ["meta-llama/meta-llama-3.1-70b-instruct",
                   "deepseek-ai/DeepSeek-V3"],
        "tools": True,
    },
    {
        "id": "novita", "name": "Novita AI", "group": "cloud",
        "base_url": "https://api.novita.ai/v3/openai",
        "key_url": "https://novita.ai/dashboard/settings", "key_env": "NOVITA_API_KEY",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "models": ["meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-v3.1",
                   "qwen/qwen3-32b"],
        "tools": True,
    },
    {
        "id": "lambda", "name": "Lambda Labs", "group": "cloud",
        "base_url": "https://api.lambda.ai/v1",
        "key_url": "https://cloud.lambdalabs.com/api", "key_env": "LAMBDA_API_KEY",
        "default_model": "llama-3.3-70b-instruct",
        "models": ["llama-3.3-70b-instruct", "hermes-3-llama-3.1-405b-instruct",
                   "deepseek-r1"],
        "tools": True,
    },
    {
        "id": "moonshot", "name": "Moonshot (Kimi)", "group": "cloud",
        "base_url": "https://api.moonshot.ai/v1",
        "key_url": "https://platform.moonshot.ai/console/api-keys", "key_env": "MOONSHOT_API_KEY",
        "default_model": "kimi-k2-0905-preview",
        "models": ["kimi-k2-0905-preview", "moonshot-v1-128k",
                   "moonshot-v1-128k-vision-preview"],
        "tools": True,
    },
    {
        "id": "qwen", "name": "Alibaba Qwen", "group": "cloud",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "key_url": "https://www.alibabacloud.com/help/en/model-studio", "key_env": "DASHSCOPE_API_KEY",
        "default_model": "qwen-plus",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen3-235b-a22b"],
        "tools": True,
    },
    {
        "id": "cohere", "name": "Cohere", "group": "cloud",
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "key_url": "https://dashboard.cohere.com/api-keys", "key_env": "COHERE_API_KEY",
        "default_model": "command-a-03-2025",
        "models": ["command-a-03-2025", "command-r-plus-08-2024",
                   "command-r7b-12-2024"],
        "tools": True,
    },
    {
        "id": "nvidia", "name": "NVIDIA NIM", "group": "cloud",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_url": "https://build.nvidia.com", "key_env": "NVIDIA_API_KEY",
        "default_model": "meta/llama-3.3-70b-instruct",
        "models": ["meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1",
                   "qwen/qwen2.5-coder-32b-instruct"],
        "tools": True, "note": "1000 free credits to start",
    },
    {
        "id": "huggingface", "name": "Hugging Face Router", "group": "cloud",
        "base_url": "https://router.huggingface.co/v1",
        "key_url": "https://huggingface.co/settings/tokens", "key_env": "HF_TOKEN",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "models": ["meta-llama/Llama-3.3-70B-Instruct",
                   "openai/gpt-oss-120b", "deepseek-ai/DeepSeek-V3-0324"],
        "tools": True,
    },
    {
        "id": "glama", "name": "Glama Gateway", "group": "cloud",
        "base_url": "https://glama.ai/api/gateway/openai/v1",
        "key_url": "https://glama.ai/settings/api-keys", "key_env": "GLAMA_API_KEY",
        "default_model": "openai/gpt-4o-mini",
        "models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku",
                   "meta-llama/llama-3.3-70b-instruct"],
        "tools": True,
    },
    {
        "id": "chutes", "name": "Chutes AI", "group": "cloud",
        "base_url": "https://llm.chutes.ai/v1",
        "key_url": "https://chutes.ai", "key_env": "CHUTES_API_KEY",
        "default_model": "deepseek-ai/DeepSeek-V3",
        "models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct"],
        "tools": True,
    },
    # ------------------------------------------------------------------ local
    {
        "id": "ollama", "name": "Ollama (local)", "group": "local",
        "base_url": "http://127.0.0.1:11434/v1",
        "key_url": "", "key_env": "OLLAMA_API_KEY", "needs_key": False,
        "default_model": "llama3.2",
        "models": ["llama3.2", "llama3.1", "qwen2.5", "llama3.3", "mistral"],
        "tools": True, "note": "run 'ollama serve' first — fully private",
    },
    {
        "id": "lmstudio", "name": "LM Studio (local)", "group": "local",
        "base_url": "http://127.0.0.1:1234/v1",
        "key_url": "", "key_env": "LMSTUDIO_API_KEY", "needs_key": False,
        "default_model": "",
        "models": [],
        "tools": True, "note": "start the LM Studio local server first",
    },
    {
        "id": "llamacpp", "name": "llama.cpp server (local)", "group": "local",
        "base_url": "http://127.0.0.1:8080/v1",
        "key_url": "", "key_env": "LLAMACPP_API_KEY", "needs_key": False,
        "default_model": "",
        "models": [],
        "tools": True, "note": "llama-server / any gguf server",
    },
    # ------------------------------------------------------------------ custom
    {
        "id": "custom", "name": "Custom OpenAI-compatible API", "group": "custom",
        "base_url": "",
        "key_url": "", "key_env": "CUSTOM_API_KEY",
        "default_model": "",
        "models": [],
        "tools": True, "note": "vLLM, LiteLLM, any /chat/completions server",
    },
]


def get(provider_id: str) -> Optional[Dict]:
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return p
    return None


def ids() -> List[str]:
    return [p["id"] for p in PROVIDERS]


def by_group(group: str) -> List[Dict]:
    return [p for p in PROVIDERS if p["group"] == group]


def label(p: Dict) -> str:
    text = p["name"]
    if p.get("note"):
        text += f"  — {p['note']}"
    return text

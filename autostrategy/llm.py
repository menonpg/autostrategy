"""
Shared LLM client for AutoStrategy.
Auto-selects Azure OpenAI if AZURE_OPENAI_KEY is set, falls back to Anthropic.
Exposes the same interface as the Anthropic SDK so existing code works unchanged.
"""
import os
import json
import urllib.request


class _AzureMessage:
    """Mimics anthropic response.content[0].text"""
    def __init__(self, text):
        self.text = text


class _AzureResponse:
    """Mimics anthropic Messages response."""
    def __init__(self, text):
        self.content = [_AzureMessage(text)]


class _AzureMessagesNamespace:
    """Mimics client.messages with a .create() method."""
    def __init__(self, url, api_key):
        self._url = url
        self._api_key = api_key

    def create(self, model, max_tokens, messages, system=None, **kwargs):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        payload = json.dumps({"messages": msgs, "max_tokens": max_tokens}).encode()
        req = urllib.request.Request(
            self._url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "api-key": self._api_key,
            }
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        text = resp["choices"][0]["message"]["content"].strip()
        return _AzureResponse(text)


class AzureOpenAIClient:
    """Azure OpenAI client with Anthropic-compatible client.messages.create() interface."""

    def __init__(self):
        endpoint    = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        api_key     = os.environ.get("AZURE_OPENAI_KEY", "")
        deployment  = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5-chat")
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        self.messages = _AzureMessagesNamespace(url, api_key)


def get_client():
    """
    Returns an LLM client.
    - If AZURE_OPENAI_KEY is set → AzureOpenAIClient (Anthropic-compatible interface)
    - Otherwise → anthropic.Anthropic()
    """
    if os.environ.get("AZURE_OPENAI_KEY"):
        return AzureOpenAIClient()
    import anthropic
    return anthropic.Anthropic()

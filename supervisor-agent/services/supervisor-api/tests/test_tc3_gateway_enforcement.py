# Licensed under the MIT License. See LICENSE file in the project root.
"""TC-3 (Zero Bypass Gateway Enforcement) tests.

Verifies the supervisor's outbound inter-agent calls always carry the
APIM subscription key header and are addressed at an APIM gateway URL,
not at a direct container/AWS hostname.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
import respx

# tools/ lives at services/supervisor-api/tools (sibling of tests/)
_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

# Stub `agent_framework` so we can import knowledge.py without the runtime dep.
# The @tool decorator is replaced with an identity decorator that exposes the
# wrapped function via a `.func` attribute.
if "agent_framework" not in sys.modules:
    _af = types.ModuleType("agent_framework")

    def _tool(*_args, **_kwargs):
        def _decorate(fn):
            fn.func = fn  # mimic the attribute used by callers
            return fn

        return _decorate

    _af.tool = _tool
    sys.modules["agent_framework"] = _af

from tools import knowledge as knowledge_tool  # noqa: E402


_APIM_UC1 = "https://ai-alz-apim-i3ro.azure-api.net/uc1"
_APIM_KEY = "test-apim-subscription-key"


def _underlying(fn):
    """Strip the @tool wrapper and return the raw callable for direct invocation."""
    return getattr(fn, "func", getattr(fn, "_func", fn))


def _is_apim_gateway_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and parsed.hostname.endswith(".azure-api.net")
    )


@respx.mock
def test_search_knowledge_sends_apim_key_header(monkeypatch: pytest.MonkeyPatch):
    """UC2→UC1 RAG calls MUST include Ocp-Apim-Subscription-Key (TC-3)."""
    monkeypatch.setenv("UC1_RAG_ENDPOINT", _APIM_UC1)
    monkeypatch.setenv("APIM_SUBSCRIPTION_KEY", _APIM_KEY)

    route = respx.post(f"{_APIM_UC1}/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"text": "stub knowledge result"}],
                    }
                ]
            },
        )
    )

    result = _underlying(knowledge_tool.search_knowledge)(query="safety report")

    assert "stub knowledge result" in result
    assert route.called
    sent = route.calls.last.request
    assert sent.headers.get("Ocp-Apim-Subscription-Key") == _APIM_KEY
    # Must be an APIM gateway URL, not a direct container FQDN
    assert _is_apim_gateway_url(str(sent.url))


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/azure-api.net",
        "https://azure-api.net.evil.example",
        "https://notazure-api.net",
        "https://evil.example/?next=ai-alz.azure-api.net",
        "http://ai-alz-apim.azure-api.net/uc1",
        "https://[invalid",
    ],
)
def test_apim_gateway_url_validation_rejects_untrusted_hosts(url: str):
    assert not _is_apim_gateway_url(url)


def test_apim_gateway_url_validation_accepts_apim_subdomains():
    assert _is_apim_gateway_url("https://ai-alz-apim.azure-api.net/uc1")
    assert _is_apim_gateway_url("https://gateway.region.azure-api.net/uc1")


def test_uc1_endpoint_in_tfvars_is_apim_gateway():
    """terraform.tfvars must point UC1_RAG_ENDPOINT at the APIM gateway (TC-3)."""
    from pathlib import Path

    tfvars = Path(__file__).resolve().parents[3] / "infra" / "terraform.tfvars"
    text = tfvars.read_text(encoding="utf-8")
    # Find the uc1_rag_endpoint line
    line = next(
        (ln for ln in text.splitlines() if ln.strip().startswith("uc1_rag_endpoint")),
        "",
    )
    endpoint = line.partition("=")[2].strip().strip('"')
    assert _is_apim_gateway_url(endpoint), (
        f"uc1_rag_endpoint must use APIM gateway: {line!r}"
    )


def test_bedrock_gateway_url_in_tfvars_is_apim_gateway():
    """terraform.tfvars must expose an APIM-fronted Bedrock proxy URL (TC-3)."""
    from pathlib import Path

    tfvars = Path(__file__).resolve().parents[3] / "infra" / "terraform.tfvars"
    text = tfvars.read_text(encoding="utf-8")
    line = next(
        (
            ln
            for ln in text.splitlines()
            if ln.strip().startswith("aws_bedrock_apim_endpoint")
        ),
        "",
    )
    endpoint = line.partition("=")[2].strip().strip('"')
    assert _is_apim_gateway_url(endpoint), (
        f"aws_bedrock_apim_endpoint must use APIM gateway: {line!r}"
    )
    assert "/uc2-bedrock" in line, (
        f"aws_bedrock_apim_endpoint must target the /uc2-bedrock proxy path: {line!r}"
    )

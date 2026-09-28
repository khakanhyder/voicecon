"""
Voice library: provider lookups and the rules around voice ids and keys.

ElevenLabs is stubbed with an httpx MockTransport, so nothing here needs the
network or a key.
"""
import httpx
import pytest

from app.services.voice import voice_library
from app.services.voice.providers.base import AuthenticationError, ProviderError
from app.services.voice.voice_library import (
    ElevenLabsVoices,
    InvalidVoiceId,
    UnsupportedVoiceProvider,
    VoiceLookupUnavailable,
    VoiceNotFound,
)

VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


def _adapter(handler) -> ElevenLabsVoices:
    return ElevenLabsVoices(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_lookup_describes_the_voice_and_sends_the_key_as_a_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("xi-api-key")
        return httpx.Response(200, json={
            "voice_id": VOICE_ID,
            "name": "My Clone",
            "category": "cloned",
            "description": "Warm and steady",
            "labels": {"accent": "british", "age": None},
        })

    info = await _adapter(handler).lookup(VOICE_ID, "sk_customer")

    assert info.name == "My Clone"
    assert info.category == "cloned"
    assert info.labels == {"accent": "british"}
    assert seen["key"] == "sk_customer"
    assert seen["url"].endswith(f"/v1/voices/{VOICE_ID}")
    assert "sk_customer" not in seen["url"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 404])
async def test_lookup_of_an_unknown_voice_is_not_found(status_code):
    adapter = _adapter(lambda r: httpx.Response(
        status_code, json={"detail": {"status": "voice_not_found"}}
    ))
    with pytest.raises(VoiceNotFound):
        await adapter.lookup(VOICE_ID, "sk")


@pytest.mark.asyncio
async def test_a_rejected_key_is_an_authentication_error():
    adapter = _adapter(lambda r: httpx.Response(
        401, json={"detail": {"status": "invalid_api_key"}}
    ))
    with pytest.raises(AuthenticationError):
        await adapter.lookup(VOICE_ID, "sk")


@pytest.mark.asyncio
async def test_a_speech_only_key_is_told_apart_from_a_bad_key():
    adapter = _adapter(lambda r: httpx.Response(
        401, json={"detail": {"status": "missing_permissions"}}
    ))
    with pytest.raises(VoiceLookupUnavailable):
        await adapter.lookup(VOICE_ID, "sk")


@pytest.mark.parametrize("bad", ["", "   ", "abc", "../user", "21m00Tcm4TlvDq8ikWAM/../x", "has space in the id 123"])
def test_voice_ids_that_could_not_be_real_are_refused(bad):
    with pytest.raises(InvalidVoiceId):
        ElevenLabsVoices().clean_voice_id(bad)


def test_a_voice_id_is_trimmed():
    assert ElevenLabsVoices().clean_voice_id(f"  {VOICE_ID}\n") == VOICE_ID


def test_unknown_provider_is_refused():
    with pytest.raises(UnsupportedVoiceProvider):
        voice_library.get_adapter("cartesia")


@pytest.mark.asyncio
async def test_a_speech_only_key_proves_the_voice_by_speaking(monkeypatch):
    adapter = _adapter(lambda r: httpx.Response(
        401, json={"detail": {"status": "missing_permissions"}}
    ))
    monkeypatch.setitem(voice_library.ADAPTERS, "elevenlabs", adapter)
    spoken = []

    class FakeTTS:
        def _get_api_key(self, provider):
            return "platform-key"

        async def synthesize(self, **kwargs):
            spoken.append(kwargs)
            return object()

    monkeypatch.setattr(voice_library, "get_tts_service", lambda: FakeTTS())

    info = await voice_library.inspect_voice("elevenlabs", VOICE_ID, "sk_customer")

    assert info.name is None
    assert spoken[0]["api_key"] == "sk_customer"
    assert spoken[0]["voice_id"] == VOICE_ID


@pytest.mark.asyncio
async def test_preview_reports_a_missing_voice(monkeypatch):
    class FakeTTS:
        def _get_api_key(self, provider):
            return "platform-key"

        async def synthesize(self, **kwargs):
            raise ProviderError('ElevenLabs API error: {"detail":{"status":"voice_not_found"}}')

    monkeypatch.setattr(voice_library, "get_tts_service", lambda: FakeTTS())

    with pytest.raises(VoiceNotFound):
        await voice_library.preview_voice("elevenlabs", VOICE_ID)


@pytest.mark.asyncio
async def test_preview_without_any_key_says_so(monkeypatch):
    class FakeTTS:
        def _get_api_key(self, provider):
            return None

    monkeypatch.setattr(voice_library, "get_tts_service", lambda: FakeTTS())

    with pytest.raises(voice_library.ProviderNotConfigured):
        await voice_library.preview_voice("elevenlabs", VOICE_ID)

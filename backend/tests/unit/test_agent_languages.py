"""
The agent's language, end to end: every language the editor offers has a
speech-to-text model that takes it, an instruction for the model, a language
for the voice, and the platform's own lines translated.
"""
import re
from pathlib import Path

import pytest

from app.schemas.agent import STTConfig
from app.services.voice import languages
from app.services.voice.providers.elevenlabs import ElevenLabsTTS
from app.services.voice.turn_taking import (
    extra_wait_seconds,
    is_echo,
    pop_sentences,
    speech_units,
    word_count,
)

CODES = [code for code, _, _ in languages.LANGUAGES]
FRONTEND_TABLE = Path(__file__).resolve().parents[3] / "frontend/src/lib/agentLanguages.ts"


# ── Speech-to-text ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("code", CODES)
@pytest.mark.parametrize("model", [None, *languages.STT_MODEL_LANGUAGES])
def test_every_language_gets_a_model_that_supports_it(code, model):
    resolved = languages.resolve_stt_model(model, code)
    assert code in languages.STT_MODEL_LANGUAGES[resolved]


def test_a_supported_choice_is_kept():
    assert languages.resolve_stt_model("nova-2", "es") == "nova-2"
    assert languages.resolve_stt_model("enhanced", "de") == "enhanced"


def test_an_unsupported_choice_falls_back_to_the_model_that_takes_everything():
    # Arabic on the form's default model: the stream was refused and the
    # agent heard nothing.
    assert languages.resolve_stt_model("nova-2", "ar") == "nova-3"
    assert languages.resolve_stt_model(None, "ar") == "nova-3"
    assert languages.resolve_stt_model("nova", "fr") == "nova-3"


def test_unknown_language_or_model_is_left_alone():
    assert languages.resolve_stt_model("nova-2", "xx") == "nova-2"
    assert languages.resolve_stt_model("whisper-large", "ar") == "whisper-large"


def test_saving_an_agent_stores_a_pair_that_works():
    assert STTConfig(language="ar").model == "nova-3"
    assert STTConfig(language="fi", model="enhanced").model == "nova-3"
    assert STTConfig(language="es", model="nova-2").model == "nova-2"
    assert STTConfig(language="ES-mx").language == "es-MX"


# ── LLM ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("code", CODES)
def test_the_model_is_told_the_language(code):
    note = languages.language_instruction(code)
    if languages.is_english(code):
        assert note == ""
    else:
        assert languages.language_name(code) in note
        assert "from your first word" in note


# ── Voice ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("code", CODES)
def test_the_voice_is_pinned_to_the_language(code):
    pinned = languages.tts_language_code(code)
    if languages.is_english(code):
        assert pinned is None
    else:
        assert pinned == code.split("-")[0].lower()


def test_the_language_reaches_the_voice_request_only_where_it_is_accepted():
    provider = ElevenLabsTTS(api_key="k", model_id="eleven_flash_v2_5")
    body = provider._request_body("Hola", {}, {"language_code": "es"})
    assert body["language_code"] == "es"
    assert "language_code" not in provider._request_body("Hello", {}, {})
    assert "language_code" not in provider._request_body("Hello", {}, {"language_code": None})
    older = provider._request_body("Hola", {}, {"language_code": "es", "model_id": "eleven_multilingual_v2"})
    assert "language_code" not in older


# ── The platform's own lines ─────────────────────────────────────────────────
@pytest.mark.parametrize("code", CODES)
def test_every_line_exists_in_every_language(code):
    english = languages.PHRASES["en"]
    for key in english:
        line = languages.phrase(key, code, name="Ava") if "{name}" in english[key] else languages.phrase(key, code)
        assert line.strip()
        if not languages.is_english(code):
            assert line != english[key], f"{key} is not translated for {code}"


def test_traditional_chinese_has_its_own_lines():
    assert languages.phrase("still_there", "zh-TW") != languages.phrase("still_there", "zh")


def test_untouched_default_greeting_follows_the_language():
    assert languages.spoken_greeting("Hello! How can I help you today?", "es-MX") == languages.PHRASES["es"]["greeting"]
    # Left over from a language the agent was switched away from.
    assert languages.spoken_greeting(languages.PHRASES["fr"]["greeting"], "de") == languages.PHRASES["de"]["greeting"]
    assert languages.spoken_greeting("Hello! How can I help you today?", "en-GB") == "Hello! How can I help you today?"


def test_a_written_greeting_is_spoken_as_written():
    assert languages.spoken_greeting("Thanks for calling Pearl Dental.", "es") == "Thanks for calling Pearl Dental."


def test_no_greeting_at_all_gets_one_in_the_language():
    assert "Ava" in languages.spoken_greeting("", "de", "Ava")
    assert languages.spoken_greeting(None, "de") == languages.PHRASES["de"]["greeting"]


def test_a_tools_own_holding_line_is_kept():
    assert languages.spoken_filler("Checking the diary.", "es") == "Checking the diary."
    assert languages.spoken_filler("", "es") == languages.PHRASES["es"]["filler"]


# ── Turn-taking in other scripts ─────────────────────────────────────────────
@pytest.mark.parametrize("text, words", [
    ("I'd like to book", 4),
    ("Здравствуйте, я хочу записаться", 4),
    ("مرحبا، أريد حجز موعد", 4),
    ("नमस्ते, मुझे अपॉइंटमेंट चाहिए।", 4),
    ("안녕하세요 예약하고 싶어요", 3),
    ("你好，我想预约", 3),
    ("はい", 1),
])
def test_words_are_counted_in_every_script(text, words):
    assert word_count(text) == words


def test_the_agents_own_voice_is_recognised_in_other_scripts():
    assert is_echo("чем я могу вам помочь", "Здравствуйте! Чем я могу вам помочь?")
    assert is_echo("请问今天有什么", "您好！请问今天有什么可以帮您？")
    assert not is_echo("我想预约明天", "您好！请问今天有什么可以帮您？")


def test_sentences_are_spoken_one_at_a_time_in_other_scripts():
    done, rest = pop_sentences("您好！请问今天有什么可以帮您？我可以为您预约时间。还有")
    assert done == ["您好！请问今天有什么可以帮您？"]
    done, rest = pop_sentences("नमस्ते! आज मैं आपकी क्या मदद करूँ? मैं यहाँ हूँ। और")
    assert done == ["नमस्ते! आज मैं आपकी क्या मदद करूँ?"]
    done, rest = pop_sentences("Hello there. How can I help you today? And")
    assert done == ["Hello there. How can I help you today?"] and rest == "And"


def test_speech_units_rebuild_the_text():
    for text in ("Hello there, how are you?", "您好！请问今天有什么可以帮您？", "مرحباً! كيف يمكنني مساعدتك؟"):
        assert "".join(speech_units(text)) == text
    assert len(speech_units("您好！请问今天")) == 6


def test_a_finished_sentence_is_not_held_in_other_scripts():
    assert extra_wait_seconds("我想预约明天下午三点。", None, "zh") == 0.0
    assert extra_wait_seconds("¿Tienen cita para mañana?", None, "es") == 0.0


# ── The editor's copy ────────────────────────────────────────────────────────
@pytest.mark.skipif(not FRONTEND_TABLE.exists(), reason="frontend sources not present")
def test_the_editor_offers_exactly_what_the_backend_supports():
    source = FRONTEND_TABLE.read_text(encoding="utf-8")

    listed = re.findall(r'\{ value: "([^"]+)", label: "([^"]+)" \}', source)
    assert listed == [(code, label) for code, label, _ in languages.LANGUAGES]

    for model, supported in languages.STT_MODEL_LANGUAGES.items():
        row = re.search(rf'"{re.escape(model)}": \[([^\]]*)\]', source)
        assert row, f"{model} is missing from the editor's table"
        assert set(re.findall(r'"([^"]+)"', row.group(1))) == set(supported)

    block = source[source.index("DEFAULT_GREETINGS"):]
    greetings = dict(re.findall(r'^\s+"([^"]+)": "(.*)",$', block[: block.index("\n}")], re.M))
    assert {k.lower(): v for k, v in greetings.items()} == {
        k: v["greeting"] for k, v in languages.PHRASES.items()
    }

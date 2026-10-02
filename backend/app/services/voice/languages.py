"""
The agent's language, in one place.

An agent has one language setting (``stt_language``, the Language dropdown on
the Transcriber tab). It used to reach only the speech-to-text request, so an
agent set to Spanish heard Spanish and then: was never told to answer in
Spanish, greeted with the English default, apologised and checked in with
English lines the platform writes itself, and had those lines read by a voice
left to guess the language. And some model/language pairs in the dropdowns do
not exist at the provider, which rejects the connection — the call then runs
with no transcription at all.

Everything that depends on the language is derived here and shared by real
calls (voice_session.py) and the browser test (agents.py):

* ``resolve_stt_model``    — a speech-to-text model that supports the language
* ``language_instruction`` — what the LLM is told
* ``tts_language_code``    — what the voice is told
* ``phrase`` / ``spoken_greeting`` — the lines the platform says itself

The lists below are mirrored in ``frontend/src/lib/agentLanguages.ts`` (the
editor needs them to offer only pairs that work);
``tests/unit/test_agent_languages.py`` fails when the two drift apart.
"""
from __future__ import annotations

import logging
from typing import Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: (code, label shown in the editor, name the LLM is given).
LANGUAGES: Tuple[Tuple[str, str, str], ...] = (
    ("en", "English", "English"),
    ("en-US", "English (US)", "American English"),
    ("en-GB", "English (UK)", "British English"),
    ("en-AU", "English (AU)", "Australian English"),
    ("es", "Spanish", "Spanish"),
    ("es-MX", "Spanish (Mexico)", "Mexican Spanish"),
    ("fr", "French", "French"),
    ("fr-CA", "French (Canada)", "Canadian French"),
    ("de", "German", "German"),
    ("it", "Italian", "Italian"),
    ("pt", "Portuguese", "Portuguese"),
    ("pt-BR", "Portuguese (Brazil)", "Brazilian Portuguese"),
    ("nl", "Dutch", "Dutch"),
    ("pl", "Polish", "Polish"),
    ("ja", "Japanese", "Japanese"),
    ("ko", "Korean", "Korean"),
    ("zh", "Chinese (Mandarin)", "Mandarin Chinese"),
    ("zh-TW", "Chinese (Traditional)", "Mandarin Chinese as spoken in Taiwan"),
    ("ar", "Arabic", "Arabic"),
    ("hi", "Hindi", "Hindi"),
    ("ru", "Russian", "Russian"),
    ("tr", "Turkish", "Turkish"),
    ("sv", "Swedish", "Swedish"),
    ("da", "Danish", "Danish"),
    ("fi", "Finnish", "Finnish"),
    ("no", "Norwegian", "Norwegian"),
)

_BY_CODE: Dict[str, Tuple[str, str, str]] = {row[0].lower(): row for row in LANGUAGES}

DEFAULT_LANGUAGE = "en"

#: The one speech-to-text model that takes every language above.
FALLBACK_STT_MODEL = "nova-3"

_ALL = frozenset(row[0] for row in LANGUAGES)

#: Which languages each Deepgram model accepts on the streaming endpoint.
#: Measured against Deepgram on 2026-10-02 by opening a stream for every pair
#: (an unsupported pair is refused with HTTP 400 "No such model/language/tier
#: combination"). Re-measure rather than guess when adding a model or language.
STT_MODEL_LANGUAGES: Dict[str, FrozenSet[str]] = {
    "nova-3": _ALL,
    "nova-2": _ALL - {"ar"},
    "nova": frozenset({"en", "en-US", "en-GB", "en-AU", "es"}),
    "enhanced": frozenset({
        "en", "en-US", "es", "fr", "de", "it", "pt", "pt-BR", "nl", "pl",
        "ja", "ko", "hi", "sv", "da", "no",
    }),
    "base": _ALL - {"es-MX", "ar", "fi"},
}


def canonical(code: Optional[str]) -> str:
    """The code as listed above ("ES-mx" → "es-MX"); unknown codes pass through."""
    raw = (code or "").strip() or DEFAULT_LANGUAGE
    row = _BY_CODE.get(raw.lower())
    return row[0] if row else raw


def base_language(code: Optional[str]) -> str:
    """The language without its region: "es-MX" → "es"."""
    return canonical(code).split("-")[0].lower()


def is_english(code: Optional[str]) -> bool:
    return base_language(code) == "en"


def language_name(code: Optional[str]) -> str:
    row = _BY_CODE.get(canonical(code).lower())
    return row[2] if row else canonical(code)


def stt_models_for(code: Optional[str]) -> List[str]:
    """The speech-to-text models that accept this language, best first."""
    lang = canonical(code)
    return [m for m, langs in STT_MODEL_LANGUAGES.items() if lang in langs]


def resolve_stt_model(model: Optional[str], code: Optional[str], default: str = "nova-2") -> str:
    """
    The model to actually open the speech-to-text stream with.

    The agent's own choice when the provider supports it for this language;
    otherwise the one model that supports every language. A pair the provider
    refuses is not an error the caller can see — the stream never opens and
    the agent hears nothing — so it is corrected here rather than attempted.
    """
    chosen = (model or "").strip() or default
    lang = canonical(code)
    supported = STT_MODEL_LANGUAGES.get(chosen)
    if lang not in _ALL or supported is None or lang in supported:
        # An unknown language or model is left for the provider to judge.
        return chosen
    logger.warning(
        "Speech-to-text model %s does not support language %s; using %s instead",
        chosen, lang, FALLBACK_STT_MODEL,
    )
    return FALLBACK_STT_MODEL


def tts_language_code(code: Optional[str]) -> Optional[str]:
    """
    The language to pin the voice to, or None to leave it to the voice.

    Without it the voice model guesses the language from each sentence, and a
    short one — "12", "OK", a name — is guessed wrong and read in English.
    English agents are left unpinned: that is how they have always run, and
    an English agent whose own prompt has it speak something else keeps
    working.
    """
    if is_english(code):
        return None
    lang = canonical(code)
    return base_language(lang) if lang in _ALL else None


def language_instruction(code: Optional[str]) -> str:
    """
    The block appended to the system prompt so the model speaks the agent's
    language. Empty for English, where the model already follows the caller.
    """
    if is_english(code) or canonical(code) not in _ALL:
        return ""
    name = language_name(code)
    return (
        "\n\nLANGUAGE (always applies):\n"
        f"- This agent speaks {name}. Say everything in {name}, from your first "
        "word to your last: answers, questions, confirmations, apologies and "
        "goodbyes. These instructions, and anything a tool or the knowledge base "
        f"returns, may be in another language; you still speak {name} and "
        "translate what you need from them.\n"
        "- Only change language if the caller clearly asks to, or keeps speaking "
        "another language. Then carry on in theirs until they change back. One "
        "foreign word, a name or a brand is not a reason to switch.\n"
        f"- Say numbers, dates, times, prices and email symbols the way they are "
        f"said in {name}.\n"
        "- In tool calls, pass names, emails, phone numbers and reference codes "
        "exactly as the caller gave them, and dates, times and option values in "
        "the format the tool asks for. Do not translate them.\n"
        "- A phrase you are told to use word for word is said exactly as written."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Lines the platform says itself
# ─────────────────────────────────────────────────────────────────────────────
# Keyed by base language; a regional variant uses its base language's lines.
#   greeting        the default greeting in the agent editor
#   greeting_named  spoken when an agent has no greeting at all
#   no_reply        the model returned nothing, or the turn failed
#   still_there     the caller has been silent
#   silence_goodbye silent again after the check-in; the call ends
#   time_limit      Max Call Duration reached
#   must_end        the call has to end (prepaid credit used up)
#   tool_trouble    a tool kept failing
#   filler          said before a slow tool runs
#   unavailable     the browser test could not get a reply
# The voice may be male or female, so no line uses a gendered form of "I".
PHRASES: Dict[str, Dict[str, str]] = {
    "en": {
        "greeting": "Hello! How can I help you today?",
        "greeting_named": "Hello! This is {name}. How can I help you today?",
        "no_reply": "I'm sorry, I didn't catch that. Could you say it again?",
        "still_there": "Are you still there?",
        "silence_goodbye": "I haven't heard from you, so I'll end the call here. Take care!",
        "time_limit": "We've reached the time limit for this call. Thank you for calling, goodbye.",
        "must_end": "I'm sorry, I have to end our call here. Thank you for calling, goodbye.",
        "tool_trouble": "I apologize, but I'm having trouble completing that request.",
        "filler": "One moment while I check that.",
        "unavailable": "I'm having a technical issue right now. Please try again.",
    },
    "es": {
        "greeting": "¡Hola! ¿En qué puedo ayudarle hoy?",
        "greeting_named": "¡Hola! Le habla {name}. ¿En qué puedo ayudarle hoy?",
        "no_reply": "Disculpe, no le he entendido. ¿Podría repetirlo?",
        "still_there": "¿Sigue ahí?",
        "silence_goodbye": "Como no le escucho, voy a finalizar la llamada. ¡Que tenga un buen día!",
        "time_limit": "Hemos alcanzado el tiempo máximo de esta llamada. Gracias por llamar, hasta luego.",
        "must_end": "Lo siento, tengo que finalizar la llamada aquí. Gracias por llamar, hasta luego.",
        "tool_trouble": "Disculpe, estoy teniendo problemas para completar esa solicitud.",
        "filler": "Un momento, por favor, lo estoy comprobando.",
        "unavailable": "Tengo un problema técnico en este momento. Por favor, inténtelo de nuevo.",
    },
    "fr": {
        "greeting": "Bonjour ! Comment puis-je vous aider aujourd'hui ?",
        "greeting_named": "Bonjour ! Ici {name}. Comment puis-je vous aider aujourd'hui ?",
        "no_reply": "Excusez-moi, je n'ai pas bien compris. Pourriez-vous répéter ?",
        "still_there": "Êtes-vous toujours là ?",
        "silence_goodbye": "Comme je ne vous entends plus, je vais mettre fin à l'appel. Bonne journée !",
        "time_limit": "Nous avons atteint la durée maximale de cet appel. Merci de votre appel, au revoir.",
        "must_end": "Excusez-moi, je dois mettre fin à notre appel. Merci de votre appel, au revoir.",
        "tool_trouble": "Excusez-moi, je n'arrive pas à traiter cette demande.",
        "filler": "Un instant, je vérifie cela.",
        "unavailable": "Je rencontre un problème technique en ce moment. Veuillez réessayer.",
    },
    "de": {
        "greeting": "Hallo! Wie kann ich Ihnen heute helfen?",
        "greeting_named": "Hallo! Hier ist {name}. Wie kann ich Ihnen heute helfen?",
        "no_reply": "Entschuldigung, das habe ich nicht verstanden. Könnten Sie das bitte wiederholen?",
        "still_there": "Sind Sie noch da?",
        "silence_goodbye": "Da ich nichts mehr von Ihnen höre, beende ich das Gespräch jetzt. Alles Gute!",
        "time_limit": "Wir haben die maximale Gesprächsdauer erreicht. Vielen Dank für Ihren Anruf, auf Wiederhören.",
        "must_end": "Es tut mir leid, ich muss unser Gespräch hier beenden. Vielen Dank für Ihren Anruf, auf Wiederhören.",
        "tool_trouble": "Es tut mir leid, ich kann diese Anfrage gerade nicht abschließen.",
        "filler": "Einen Moment bitte, ich sehe nach.",
        "unavailable": "Ich habe gerade ein technisches Problem. Bitte versuchen Sie es noch einmal.",
    },
    "it": {
        "greeting": "Buongiorno! Come posso aiutarla oggi?",
        "greeting_named": "Buongiorno! Sono {name}. Come posso aiutarla oggi?",
        "no_reply": "Mi scusi, non ho capito. Potrebbe ripetere?",
        "still_there": "È ancora in linea?",
        "silence_goodbye": "Non la sento più, quindi termino la chiamata. Buona giornata!",
        "time_limit": "Abbiamo raggiunto il tempo massimo per questa chiamata. Grazie per aver chiamato, arrivederci.",
        "must_end": "Mi dispiace, devo terminare qui la chiamata. Grazie per aver chiamato, arrivederci.",
        "tool_trouble": "Mi dispiace, non riesco a completare questa richiesta.",
        "filler": "Un momento, sto verificando.",
        "unavailable": "In questo momento ho un problema tecnico. Per favore, riprovi.",
    },
    "pt": {
        "greeting": "Olá! Como posso ajudar hoje?",
        "greeting_named": "Olá! Aqui é {name}. Como posso ajudar hoje?",
        "no_reply": "Desculpe, não entendi. Pode repetir, por favor?",
        "still_there": "Ainda está aí?",
        "silence_goodbye": "Como não estou ouvindo você, vou encerrar a chamada. Tenha um bom dia!",
        "time_limit": "Chegamos ao tempo máximo desta chamada. Agradecemos a sua ligação, até logo.",
        "must_end": "Desculpe, preciso encerrar a chamada aqui. Agradecemos a sua ligação, até logo.",
        "tool_trouble": "Desculpe, não estou conseguindo concluir esse pedido.",
        "filler": "Um momento, estou verificando.",
        "unavailable": "Estou com um problema técnico neste momento. Por favor, tente novamente.",
    },
    "nl": {
        "greeting": "Hallo! Waarmee kan ik u vandaag helpen?",
        "greeting_named": "Hallo! U spreekt met {name}. Waarmee kan ik u vandaag helpen?",
        "no_reply": "Sorry, dat heb ik niet goed verstaan. Kunt u het herhalen?",
        "still_there": "Bent u er nog?",
        "silence_goodbye": "Ik hoor u niet meer, dus ik beëindig het gesprek. Een fijne dag!",
        "time_limit": "We hebben de maximale gespreksduur bereikt. Bedankt voor het bellen, tot ziens.",
        "must_end": "Het spijt me, ik moet ons gesprek hier beëindigen. Bedankt voor het bellen, tot ziens.",
        "tool_trouble": "Het spijt me, het lukt me niet om dat verzoek af te ronden.",
        "filler": "Een ogenblik, ik kijk het even na.",
        "unavailable": "Ik heb op dit moment een technisch probleem. Probeer het alstublieft opnieuw.",
    },
    "pl": {
        "greeting": "Dzień dobry! W czym mogę dziś pomóc?",
        "greeting_named": "Dzień dobry! Mówi {name}. W czym mogę dziś pomóc?",
        "no_reply": "Przepraszam, nie było dobrze słychać. Czy można prosić o powtórzenie?",
        "still_there": "Czy nadal Państwo tam są?",
        "silence_goodbye": "Nikogo nie słyszę, więc zakończę rozmowę. Miłego dnia!",
        "time_limit": "Osiągnęliśmy maksymalny czas tej rozmowy. Dziękuję za telefon, do widzenia.",
        "must_end": "Przepraszam, muszę w tym miejscu zakończyć rozmowę. Dziękuję za telefon, do widzenia.",
        "tool_trouble": "Przepraszam, mam problem z realizacją tej prośby.",
        "filler": "Chwileczkę, już sprawdzam.",
        "unavailable": "Mam w tej chwili problem techniczny. Proszę spróbować ponownie.",
    },
    "ja": {
        "greeting": "こんにちは。本日はどのようなご用件でしょうか。",
        "greeting_named": "こんにちは。{name}です。本日はどのようなご用件でしょうか。",
        "no_reply": "申し訳ありません、聞き取れませんでした。もう一度お願いできますか。",
        "still_there": "お電話は繋がっていますでしょうか。",
        "silence_goodbye": "お声が確認できませんので、お電話を終了いたします。失礼いたします。",
        "time_limit": "通話の制限時間になりました。お電話ありがとうございました。失礼いたします。",
        "must_end": "申し訳ありませんが、ここでお電話を終了させていただきます。お電話ありがとうございました。",
        "tool_trouble": "申し訳ありません、そのご依頼を完了できませんでした。",
        "filler": "少々お待ちください、確認いたします。",
        "unavailable": "ただいま技術的な問題が発生しています。もう一度お試しください。",
    },
    "ko": {
        "greeting": "안녕하세요! 무엇을 도와드릴까요?",
        "greeting_named": "안녕하세요! {name}입니다. 무엇을 도와드릴까요?",
        "no_reply": "죄송합니다, 잘 듣지 못했습니다. 다시 한 번 말씀해 주시겠어요?",
        "still_there": "아직 통화 중이신가요?",
        "silence_goodbye": "응답이 없으셔서 통화를 종료하겠습니다. 좋은 하루 보내세요!",
        "time_limit": "통화 가능 시간이 다 되었습니다. 전화 주셔서 감사합니다. 안녕히 계세요.",
        "must_end": "죄송합니다, 여기서 통화를 종료해야 합니다. 전화 주셔서 감사합니다. 안녕히 계세요.",
        "tool_trouble": "죄송합니다, 해당 요청을 처리하는 데 문제가 있습니다.",
        "filler": "잠시만 기다려 주세요, 확인해 보겠습니다.",
        "unavailable": "지금 기술적인 문제가 발생했습니다. 다시 시도해 주세요.",
    },
    "zh": {
        "greeting": "您好！请问今天有什么可以帮您？",
        "greeting_named": "您好！我是{name}。请问今天有什么可以帮您？",
        "no_reply": "抱歉，我没有听清楚，您能再说一遍吗？",
        "still_there": "请问您还在吗？",
        "silence_goodbye": "我没有听到您的声音，先结束这次通话了。祝您一切顺利！",
        "time_limit": "本次通话已达到时间上限。感谢您的来电，再见。",
        "must_end": "抱歉，我需要在这里结束通话。感谢您的来电，再见。",
        "tool_trouble": "抱歉，我暂时无法完成这个请求。",
        "filler": "请稍等，我帮您查一下。",
        "unavailable": "我现在遇到了技术问题，请再试一次。",
    },
    "zh-tw": {
        "greeting": "您好！請問今天有什麼可以為您服務的？",
        "greeting_named": "您好！我是{name}。請問今天有什麼可以為您服務的？",
        "no_reply": "抱歉，我沒有聽清楚，可以請您再說一次嗎？",
        "still_there": "請問您還在嗎？",
        "silence_goodbye": "我沒有聽到您的聲音，先結束這次通話了。祝您一切順利！",
        "time_limit": "本次通話已達到時間上限。感謝您的來電，再見。",
        "must_end": "抱歉，我需要在這裡結束通話。感謝您的來電，再見。",
        "tool_trouble": "抱歉，我暫時無法完成這個請求。",
        "filler": "請稍等，我幫您查一下。",
        "unavailable": "我現在遇到了技術問題，請再試一次。",
    },
    "ar": {
        "greeting": "مرحباً! كيف يمكنني مساعدتك اليوم؟",
        "greeting_named": "مرحباً! معك {name}. كيف يمكنني مساعدتك اليوم؟",
        "no_reply": "عذراً، لم أسمعك جيداً. هل يمكنك إعادة ما قلته؟",
        "still_there": "هل ما زلت معي؟",
        "silence_goodbye": "لم أعد أسمعك، لذلك سأنهي المكالمة الآن. أتمنى لك يوماً سعيداً!",
        "time_limit": "لقد وصلنا إلى الحد الأقصى لمدة هذه المكالمة. شكراً لاتصالك، مع السلامة.",
        "must_end": "عذراً، يجب أن أنهي المكالمة هنا. شكراً لاتصالك، مع السلامة.",
        "tool_trouble": "أعتذر، أواجه مشكلة في إتمام هذا الطلب.",
        "filler": "لحظة من فضلك، سأتحقق من ذلك.",
        "unavailable": "أواجه مشكلة تقنية في الوقت الحالي. يرجى المحاولة مرة أخرى.",
    },
    "hi": {
        "greeting": "नमस्ते! आज मैं आपकी क्या मदद करूँ?",
        "greeting_named": "नमस्ते! यह {name} है। आज मैं आपकी क्या मदद करूँ?",
        "no_reply": "माफ़ कीजिए, मुझे ठीक से सुनाई नहीं दिया। क्या आप दोबारा कहेंगे?",
        "still_there": "क्या आप अभी भी लाइन पर हैं?",
        "silence_goodbye": "मुझे आपकी आवाज़ नहीं आ रही है, इसलिए यह कॉल यहीं समाप्त हो रही है। अपना ध्यान रखिए!",
        "time_limit": "इस कॉल की समय सीमा पूरी हो गई है। कॉल करने के लिए धन्यवाद, नमस्ते।",
        "must_end": "माफ़ कीजिए, मुझे यह कॉल यहीं समाप्त करनी होगी। कॉल करने के लिए धन्यवाद, नमस्ते।",
        "tool_trouble": "माफ़ कीजिए, मुझे यह अनुरोध पूरा करने में दिक्कत हो रही है।",
        "filler": "एक क्षण रुकिए, अभी जाँच हो रही है।",
        "unavailable": "अभी मुझे एक तकनीकी समस्या आ रही है। कृपया दोबारा कोशिश करें।",
    },
    "ru": {
        "greeting": "Здравствуйте! Чем я могу вам помочь?",
        "greeting_named": "Здравствуйте! Это {name}. Чем я могу вам помочь?",
        "no_reply": "Извините, было плохо слышно. Не могли бы вы повторить?",
        "still_there": "Вы ещё на линии?",
        "silence_goodbye": "Я вас не слышу, поэтому завершаю звонок. Всего доброго!",
        "time_limit": "Мы достигли максимальной длительности звонка. Спасибо за звонок, до свидания.",
        "must_end": "Извините, мне нужно завершить наш разговор. Спасибо за звонок, до свидания.",
        "tool_trouble": "Извините, у меня не получается выполнить этот запрос.",
        "filler": "Одну минуту, я проверю.",
        "unavailable": "Сейчас у меня техническая неполадка. Пожалуйста, попробуйте ещё раз.",
    },
    "tr": {
        "greeting": "Merhaba! Bugün size nasıl yardımcı olabilirim?",
        "greeting_named": "Merhaba! Ben {name}. Bugün size nasıl yardımcı olabilirim?",
        "no_reply": "Özür dilerim, anlayamadım. Tekrar eder misiniz?",
        "still_there": "Hâlâ hatta mısınız?",
        "silence_goodbye": "Sizi duyamadığım için aramayı sonlandırıyorum. İyi günler!",
        "time_limit": "Bu arama için süre sınırına ulaştık. Aradığınız için teşekkürler, hoşça kalın.",
        "must_end": "Üzgünüm, aramayı burada sonlandırmam gerekiyor. Aradığınız için teşekkürler, hoşça kalın.",
        "tool_trouble": "Özür dilerim, bu isteği tamamlarken bir sorun yaşıyorum.",
        "filler": "Bir saniye, hemen kontrol ediyorum.",
        "unavailable": "Şu anda teknik bir sorun yaşıyorum. Lütfen tekrar deneyin.",
    },
    "sv": {
        "greeting": "Hej! Hur kan jag hjälpa dig idag?",
        "greeting_named": "Hej! Det här är {name}. Hur kan jag hjälpa dig idag?",
        "no_reply": "Ursäkta, jag uppfattade inte det. Kan du säga det igen?",
        "still_there": "Är du kvar?",
        "silence_goodbye": "Jag hör dig inte längre, så jag avslutar samtalet. Ha det bra!",
        "time_limit": "Vi har nått tidsgränsen för det här samtalet. Tack för att du ringde, hej då.",
        "must_end": "Tyvärr måste jag avsluta samtalet här. Tack för att du ringde, hej då.",
        "tool_trouble": "Tyvärr har jag problem med att slutföra den begäran.",
        "filler": "Ett ögonblick, jag kollar det.",
        "unavailable": "Jag har ett tekniskt problem just nu. Försök igen.",
    },
    "da": {
        "greeting": "Hej! Hvordan kan jeg hjælpe dig i dag?",
        "greeting_named": "Hej! Du taler med {name}. Hvordan kan jeg hjælpe dig i dag?",
        "no_reply": "Undskyld, det fik jeg ikke fat i. Vil du gentage det?",
        "still_there": "Er du der stadig?",
        "silence_goodbye": "Jeg kan ikke høre dig længere, så jeg afslutter opkaldet. Hav det godt!",
        "time_limit": "Vi har nået tidsgrænsen for dette opkald. Tak fordi du ringede, farvel.",
        "must_end": "Jeg beklager, jeg er nødt til at afslutte opkaldet her. Tak fordi du ringede, farvel.",
        "tool_trouble": "Jeg beklager, jeg har problemer med at gennemføre den anmodning.",
        "filler": "Et øjeblik, jeg tjekker det.",
        "unavailable": "Jeg har et teknisk problem lige nu. Prøv venligst igen.",
    },
    "fi": {
        "greeting": "Hei! Kuinka voin auttaa tänään?",
        "greeting_named": "Hei! Täällä {name}. Kuinka voin auttaa tänään?",
        "no_reply": "Anteeksi, en saanut selvää. Voisitko toistaa?",
        "still_there": "Oletko vielä linjalla?",
        "silence_goodbye": "En kuule sinua enää, joten lopetan puhelun. Hyvää päivänjatkoa!",
        "time_limit": "Tämän puhelun enimmäisaika on täyttynyt. Kiitos soitostasi, näkemiin.",
        "must_end": "Olen pahoillani, minun on lopetettava puhelu tähän. Kiitos soitostasi, näkemiin.",
        "tool_trouble": "Olen pahoillani, en saa tätä pyyntöä tehtyä.",
        "filler": "Hetkinen, tarkistan asian.",
        "unavailable": "Minulla on juuri nyt tekninen ongelma. Yritä uudelleen.",
    },
    "no": {
        "greeting": "Hei! Hvordan kan jeg hjelpe deg i dag?",
        "greeting_named": "Hei! Dette er {name}. Hvordan kan jeg hjelpe deg i dag?",
        "no_reply": "Beklager, det fikk jeg ikke med meg. Kan du gjenta det?",
        "still_there": "Er du der fortsatt?",
        "silence_goodbye": "Jeg hører deg ikke lenger, så jeg avslutter samtalen. Ha det bra!",
        "time_limit": "Vi har nådd tidsgrensen for denne samtalen. Takk for at du ringte, ha det.",
        "must_end": "Beklager, jeg må avslutte samtalen her. Takk for at du ringte, ha det.",
        "tool_trouble": "Beklager, jeg har problemer med å fullføre den forespørselen.",
        "filler": "Et øyeblikk, jeg sjekker det.",
        "unavailable": "Jeg har et teknisk problem akkurat nå. Prøv igjen.",
    },
}


def _phrases(code: Optional[str]) -> Dict[str, str]:
    lang = canonical(code).lower()
    return PHRASES.get(lang) or PHRASES.get(base_language(code)) or PHRASES["en"]


def phrase(key: str, code: Optional[str], **values: str) -> str:
    """One of the platform's own lines, in the agent's language."""
    text = _phrases(code).get(key) or PHRASES["en"][key]
    return text.format(**values) if values else text


#: Every default greeting, normalised, so one left over from another language
#: can be recognised and replaced.
_DEFAULT_GREETINGS = frozenset(
    " ".join(p["greeting"].split()).casefold() for p in PHRASES.values()
)


def is_default_greeting(text: Optional[str]) -> bool:
    return " ".join((text or "").split()).casefold() in _DEFAULT_GREETINGS


def spoken_greeting(
    first_message: Optional[str], code: Optional[str], agent_name: Optional[str] = None
) -> str:
    """
    The greeting a call opens with.

    A greeting the customer wrote is spoken exactly as written. The editor's
    untouched default ("Hello! How can I help you today?") is not something
    they wrote, so it follows the agent's language; so does an agent with no
    greeting at all.
    """
    text = (first_message or "").strip()
    if not text:
        if agent_name:
            return phrase("greeting_named", code, name=agent_name)
        return phrase("greeting", code)
    if is_default_greeting(text):
        return phrase("greeting", code)
    return text


def spoken_filler(configured: Optional[str], code: Optional[str]) -> str:
    """A tool's own holding line, or the default one in the agent's language."""
    text = (configured or "").strip()
    return text or phrase("filler", code)

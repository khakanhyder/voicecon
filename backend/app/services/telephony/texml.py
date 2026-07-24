"""
Carrier-neutral TwiML/TeXML builders.

Twilio's TwiML and Telnyx's TeXML are the same XML dialect, so one builder
serves both. These functions deliberately avoid the Twilio SDK: a Telnyx-only
deployment has no Twilio credentials, and `TwilioService` refuses to start
without them.
"""
from xml.sax.saxutils import escape


def build_stream_response(websocket_url: str, agent_name: str = None) -> str:
    """
    Build the response that connects an inbound call to the media WebSocket.

    Args:
        websocket_url: wss:// URL of the media stream endpoint
        agent_name: Optional agent name, spoken before connecting

    Returns:
        TwiML/TeXML XML string
    """
    greeting = ""
    if agent_name:
        greeting = f"<Say>Hello, connecting you with {escape(agent_name)}</Say>"

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"{greeting}"
        f'<Connect><Stream url="{escape(websocket_url, {chr(34): "&quot;"})}" /></Connect>'
        "</Response>"
    )


def build_error_response(message: str = "We're sorry, an error occurred") -> str:
    """
    Build a spoken-error response that ends the call.

    Args:
        message: Message to speak before hanging up

    Returns:
        TwiML/TeXML XML string
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Say>{escape(message)}</Say><Hangup /></Response>"
    )

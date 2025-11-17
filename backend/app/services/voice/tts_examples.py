"""
Examples demonstrating TTS service usage.

Run these examples to test the TTS implementation.
"""
import asyncio
import logging
from pathlib import Path

from app.services.voice.tts_service import get_tts_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_1_simple_synthesis():
    """
    Example 1: Simple text-to-speech synthesis.

    This is the simplest way to convert text to speech.
    """
    print("\n" + "="*60)
    print("Example 1: Simple TTS Synthesis")
    print("="*60)

    tts = get_tts_service()

    try:
        # Synthesize speech
        result = await tts.synthesize(
            text="Hello! Welcome to Voicecon. How can I help you today?",
            provider="elevenlabs",
            voice_id="rachel",  # Can use name or ID
        )

        print(f"\nSynthesis complete:")
        print(f"  Audio size: {len(result.audio_data)} bytes")
        print(f"  Sample rate: {result.sample_rate} Hz")
        print(f"  Format: {result.format}")
        print(f"  Characters: {result.character_count}")
        print(f"  Voice: {result.voice_id}")

        # Save to file
        output_path = Path("output_example1.mp3")
        output_path.write_bytes(result.audio_data)
        print(f"\nSaved to: {output_path}")

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_2_streaming_synthesis():
    """
    Example 2: Streaming TTS for low latency.

    Demonstrates streaming audio chunks as they're generated.
    """
    print("\n" + "="*60)
    print("Example 2: Streaming TTS")
    print("="*60)

    tts = get_tts_service()

    try:
        text = "Streaming allows us to start playing audio before the entire synthesis is complete. This reduces latency significantly."

        print(f"\nSynthesizing: {text}")
        print("Streaming chunks...\n")

        chunks = []
        total_bytes = 0

        async for chunk in tts.synthesize_stream(
            text=text,
            provider="elevenlabs",
            voice_id="rachel",
        ):
            chunks.append(chunk)
            total_bytes += len(chunk)
            print(f"  Received chunk: {len(chunk)} bytes (total: {total_bytes} bytes)")

        # Save combined audio
        output_path = Path("output_example2.mp3")
        output_path.write_bytes(b''.join(chunks))
        print(f"\nSaved {len(chunks)} chunks to: {output_path}")

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_3_multiple_voices():
    """
    Example 3: Using different voices.

    Demonstrates various voices available in ElevenLabs.
    """
    print("\n" + "="*60)
    print("Example 3: Multiple Voices")
    print("="*60)

    tts = get_tts_service()

    voices = [
        ("rachel", "Female - Calm and professional"),
        ("domi", "Female - Energetic"),
        ("bella", "Female - Soft and warm"),
        ("antoni", "Male - Deep and authoritative"),
        ("josh", "Male - Friendly"),
    ]

    text = "Hello, this is a test of the text to speech system."

    for voice_name, description in voices:
        print(f"\n{voice_name.upper()} ({description})")
        print("-" * 40)

        try:
            result = await tts.synthesize(
                text=text,
                provider="elevenlabs",
                voice_id=voice_name,
            )

            output_path = Path(f"output_{voice_name}.mp3")
            output_path.write_bytes(result.audio_data)

            print(f"  Synthesized: {len(result.audio_data)} bytes")
            print(f"  Saved to: {output_path}")

        except Exception as e:
            logger.error(f"Error with voice {voice_name}: {e}")


async def example_4_voice_settings():
    """
    Example 4: Customizing voice settings.

    Demonstrates stability, similarity_boost, and style parameters.
    """
    print("\n" + "="*60)
    print("Example 4: Voice Settings")
    print("="*60)

    tts = get_tts_service()

    text = "This demonstrates different voice settings."

    settings = [
        {
            "name": "Default",
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
        },
        {
            "name": "More Stable",
            "stability": 0.9,
            "similarity_boost": 0.75,
            "style": 0.0,
        },
        {
            "name": "More Expressive",
            "stability": 0.3,
            "similarity_boost": 0.75,
            "style": 0.5,
        },
    ]

    for setting in settings:
        print(f"\n{setting['name']}:")
        print(f"  Stability: {setting['stability']}")
        print(f"  Similarity boost: {setting['similarity_boost']}")
        print(f"  Style: {setting['style']}")

        try:
            result = await tts.synthesize(
                text=text,
                provider="elevenlabs",
                voice_id="rachel",
                stability=setting['stability'],
                similarity_boost=setting['similarity_boost'],
                style=setting['style'],
            )

            output_path = Path(f"output_{setting['name'].replace(' ', '_').lower()}.mp3")
            output_path.write_bytes(result.audio_data)
            print(f"  Saved to: {output_path}")

        except Exception as e:
            logger.error(f"Error: {e}")


async def example_5_cost_tracking():
    """
    Example 5: Track usage and costs.

    Demonstrates how to monitor TTS usage and costs.
    """
    print("\n" + "="*60)
    print("Example 5: Usage and Cost Tracking")
    print("="*60)

    tts = get_tts_service()

    texts = [
        "Hello, welcome to our service.",
        "How can I help you today?",
        "Thank you for calling. Have a great day!",
    ]

    for text in texts:
        print(f"\nSynthesizing: {text}")
        try:
            await tts.synthesize(
                text=text,
                provider="elevenlabs",
                voice_id="rachel",
            )
        except Exception as e:
            logger.error(f"Error: {e}")

    # Get usage stats
    stats = await tts.get_usage_stats()

    print("\n" + "="*60)
    print("Usage Statistics")
    print("="*60)

    total_characters = 0
    total_cost = 0.0

    for stat in stats:
        print(f"\nProvider: {stat.provider}")
        print(f"Voice: {stat.voice_id}")
        print(f"Characters: {stat.character_count}")
        print(f"Cost: ${stat.cost:.4f}")
        print(f"Timestamp: {stat.timestamp}")

        total_characters += stat.character_count
        total_cost += stat.cost

    print("\n" + "-"*60)
    print(f"Total Characters: {total_characters}")
    print(f"Total Cost: ${total_cost:.4f}")
    print(f"Average Cost per Character: ${(total_cost / total_characters):.6f}")


async def example_6_caching():
    """
    Example 6: Audio caching for repeated phrases.

    Demonstrates how caching reduces costs for common phrases.
    """
    print("\n" + "="*60)
    print("Example 6: Audio Caching")
    print("="*60)

    tts = get_tts_service()

    # Get provider to access cache stats
    provider = tts.get_provider(provider="elevenlabs", enable_cache=True)

    common_phrase = "Hello, how can I help you today?"

    print("\nFirst synthesis (no cache):")
    result1 = await tts.synthesize(
        text=common_phrase,
        provider="elevenlabs",
        voice_id="rachel",
    )
    print(f"  Size: {len(result1.audio_data)} bytes")

    cache_stats = tts.get_cache_stats()
    print(f"  Cache stats: {cache_stats}")

    print("\nSecond synthesis (should hit cache):")
    result2 = await tts.synthesize(
        text=common_phrase,
        provider="elevenlabs",
        voice_id="rachel",
    )
    print(f"  Size: {len(result2.audio_data)} bytes")
    print(f"  Same audio: {result1.audio_data == result2.audio_data}")

    cache_stats = tts.get_cache_stats()
    print(f"  Cache stats: {cache_stats}")

    # Clear cache
    print("\nClearing cache...")
    tts.clear_cache()

    cache_stats = tts.get_cache_stats()
    print(f"  Cache stats after clear: {cache_stats}")


async def example_7_available_voices():
    """
    Example 7: List available voices.

    Shows how to get all available voices from the provider.
    """
    print("\n" + "="*60)
    print("Example 7: Available Voices")
    print("="*60)

    tts = get_tts_service()

    try:
        voices = await tts.get_voices(provider="elevenlabs")

        print(f"\nFound {len(voices)} voices:\n")

        for voice in voices:
            print(f"Name: {voice.get('name')}")
            print(f"  ID: {voice.get('voice_id')}")
            print(f"  Category: {voice.get('category', 'N/A')}")
            print(f"  Description: {voice.get('description', 'N/A')}")
            print()

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_8_error_handling():
    """
    Example 8: Error handling.

    Demonstrates handling various error scenarios.
    """
    print("\n" + "="*60)
    print("Example 8: Error Handling")
    print("="*60)

    tts = get_tts_service()

    # Test 1: Invalid API key
    print("\nTest 1: Invalid API key")
    try:
        await tts.synthesize(
            text="Test",
            provider="elevenlabs",
            api_key="invalid_key",
        )
    except Exception as e:
        print(f"  Caught error: {type(e).__name__}: {e}")

    # Test 2: Empty text
    print("\nTest 2: Empty text")
    try:
        await tts.synthesize(
            text="",
            provider="elevenlabs",
        )
    except Exception as e:
        print(f"  Caught error: {type(e).__name__}: {e}")

    # Test 3: Invalid voice
    print("\nTest 3: Invalid voice ID")
    try:
        await tts.synthesize(
            text="Test",
            provider="elevenlabs",
            voice_id="invalid_voice_id_12345",
        )
    except Exception as e:
        print(f"  Caught error: {type(e).__name__}: {e}")


async def example_9_long_text():
    """
    Example 9: Synthesizing longer text.

    Demonstrates handling longer passages of text.
    """
    print("\n" + "="*60)
    print("Example 9: Long Text Synthesis")
    print("="*60)

    tts = get_tts_service()

    long_text = """
    Welcome to Voicecon, the leading voice AI platform.
    Our advanced text-to-speech technology provides natural-sounding voices
    that can be customized to match your brand's personality.
    Whether you're building a customer service bot, creating audiobooks,
    or adding voice to your applications, Voicecon has you covered.
    We support multiple languages, voices, and customization options.
    Get started today and bring your applications to life with voice!
    """

    print(f"\nText length: {len(long_text)} characters")

    try:
        result = await tts.synthesize(
            text=long_text.strip(),
            provider="elevenlabs",
            voice_id="rachel",
        )

        output_path = Path("output_long_text.mp3")
        output_path.write_bytes(result.audio_data)

        print(f"\nSynthesis complete:")
        print(f"  Audio size: {len(result.audio_data)} bytes")
        print(f"  Duration: {result.duration if result.duration else 'N/A'}")
        print(f"  Saved to: {output_path}")

    except Exception as e:
        logger.error(f"Error: {e}")


async def run_all_examples():
    """Run all examples sequentially."""
    examples = [
        ("Simple Synthesis", example_1_simple_synthesis),
        ("Streaming Synthesis", example_2_streaming_synthesis),
        ("Multiple Voices", example_3_multiple_voices),
        ("Voice Settings", example_4_voice_settings),
        ("Cost Tracking", example_5_cost_tracking),
        ("Audio Caching", example_6_caching),
        ("Available Voices", example_7_available_voices),
        ("Error Handling", example_8_error_handling),
        ("Long Text", example_9_long_text),
    ]

    print("\n" + "="*60)
    print("VOICECON TTS SERVICE EXAMPLES")
    print("="*60)

    for name, example_func in examples:
        try:
            await example_func()
            await asyncio.sleep(1)  # Pause between examples
        except Exception as e:
            logger.error(f"Error in {name}: {e}")
            continue

    print("\n" + "="*60)
    print("ALL EXAMPLES COMPLETED")
    print("="*60)


if __name__ == "__main__":
    # Run specific example
    asyncio.run(example_1_simple_synthesis())

    # Or run all examples
    # asyncio.run(run_all_examples())

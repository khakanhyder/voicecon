"""
Examples demonstrating STT service usage.

Run these examples to test the STT implementation.
"""
import asyncio
import logging
from pathlib import Path

from app.services.voice import get_stt_service, AudioChunk, TranscriptionResult
from app.services.voice.audio_utils import (
    AudioBuffer,
    AudioStream,
    create_audio_stream_from_file,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_1_simple_file_transcription():
    """
    Example 1: Transcribe a complete audio file.

    This is the simplest way to transcribe audio.
    """
    print("\n" + "="*60)
    print("Example 1: Simple File Transcription")
    print("="*60)

    stt = get_stt_service()

    try:
        # Transcribe audio file
        result = await stt.transcribe_file(
            audio_file_path="path/to/audio.wav",
            provider="deepgram",
            language="en",
            model="nova-2",
        )

        print(f"\nTranscription: {result.text}")
        print(f"Confidence: {result.confidence:.2%}")
        print(f"Is Final: {result.is_final}")
        print(f"Duration: {result.duration:.2f}s")

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_2_streaming_transcription():
    """
    Example 2: Real-time streaming transcription.

    Demonstrates WebSocket streaming with interim results.
    """
    print("\n" + "="*60)
    print("Example 2: Streaming Transcription")
    print("="*60)

    stt = get_stt_service()

    # Create audio buffer
    buffer = AudioBuffer(max_size=1000)

    # Start background task to feed audio
    async def feed_audio():
        """Simulate feeding audio chunks"""
        for i in range(100):
            chunk = AudioChunk(
                data=b'\x00' * 3200,  # 100ms of 16kHz audio
                sample_rate=16000,
                channels=1,
            )
            await buffer.put(chunk)
            await asyncio.sleep(0.1)  # 100ms

        await buffer.close()

    feed_task = asyncio.create_task(feed_audio())

    try:
        # Create stream from buffer
        audio_stream = AudioStream(buffer)

        # Transcribe stream
        async for result in stt.transcribe_stream(
            audio_stream,
            provider="deepgram",
            language="en",
            model="nova-2",
            interim_results=True,
        ):
            if result.is_final:
                print(f"\n[FINAL] {result.text}")
            else:
                print(f"[INTERIM] {result.text}", end='\r')

        await feed_task

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_3_file_streaming():
    """
    Example 3: Stream transcription from file.

    Useful for testing with pre-recorded audio.
    """
    print("\n" + "="*60)
    print("Example 3: File Streaming Transcription")
    print("="*60)

    stt = get_stt_service()

    try:
        # Create audio stream from file
        audio_stream = create_audio_stream_from_file(
            file_path="path/to/audio.wav",
            chunk_size=8192,
            sample_rate=16000,
        )

        # Transcribe stream
        full_transcription = []

        async for result in stt.transcribe_stream(
            audio_stream,
            provider="deepgram",
            interim_results=False,  # Only final results
        ):
            if result.is_final:
                print(f"{result.text} ", end='')
                full_transcription.append(result.text)

        print("\n\nFull Transcription:")
        print(" ".join(full_transcription))

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_4_multiple_languages():
    """
    Example 4: Transcription in multiple languages.

    Shows how to handle different languages.
    """
    print("\n" + "="*60)
    print("Example 4: Multiple Languages")
    print("="*60)

    stt = get_stt_service()

    languages = [
        ("en", "English audio file"),
        ("es", "Spanish audio file"),
        ("fr", "French audio file"),
    ]

    for lang_code, description in languages:
        print(f"\nTranscribing {description} ({lang_code})...")

        try:
            result = await stt.transcribe_file(
                audio_file_path=f"audio_{lang_code}.wav",
                provider="deepgram",
                language=lang_code,
            )

            print(f"Result: {result.text}")

        except Exception as e:
            logger.error(f"Error for {lang_code}: {e}")


async def example_5_cost_tracking():
    """
    Example 5: Track usage and costs.

    Demonstrates how to monitor STT usage.
    """
    print("\n" + "="*60)
    print("Example 5: Usage and Cost Tracking")
    print("="*60)

    stt = get_stt_service()

    # Perform multiple transcriptions
    files = ["audio1.wav", "audio2.wav", "audio3.wav"]

    for file_path in files:
        try:
            await stt.transcribe_file(
                audio_file_path=file_path,
                provider="deepgram",
            )
        except Exception as e:
            logger.error(f"Error with {file_path}: {e}")

    # Get usage stats
    stats = await stt.get_usage_stats()

    print("\nUsage Statistics:")
    print("-" * 40)

    total_duration = 0.0
    total_cost = 0.0

    for stat in stats:
        print(f"Provider: {stat.provider}")
        print(f"Duration: {stat.duration_seconds:.2f}s")
        print(f"Cost: ${stat.cost:.4f}")
        print(f"Timestamp: {stat.timestamp}")
        print("-" * 40)

        total_duration += stat.duration_seconds
        total_cost += stat.cost

    print(f"\nTotal Duration: {total_duration:.2f}s")
    print(f"Total Cost: ${total_cost:.4f}")


async def example_6_error_handling():
    """
    Example 6: Error handling and reconnection.

    Shows how to handle connection errors gracefully.
    """
    print("\n" + "="*60)
    print("Example 6: Error Handling")
    print("="*60)

    stt = get_stt_service()

    # Create audio buffer
    buffer = AudioBuffer()

    # Simulate network interruption
    async def feed_with_interruption():
        for i in range(10):
            chunk = AudioChunk(
                data=b'\x00' * 3200,
                sample_rate=16000,
                channels=1,
            )
            await buffer.put(chunk)
            await asyncio.sleep(0.1)

            # Simulate interruption
            if i == 5:
                print("\n[SIMULATING NETWORK INTERRUPTION]")
                await asyncio.sleep(2)

        await buffer.close()

    feed_task = asyncio.create_task(feed_with_interruption())

    try:
        audio_stream = AudioStream(buffer)

        async for result in stt.transcribe_stream(audio_stream):
            print(f"Received: {result.text[:50]}...")

        await feed_task

    except Exception as e:
        logger.error(f"Error (expected): {e}")
        print("\n[ERROR HANDLED] Connection issue detected and handled")


async def example_7_websocket_call_simulation():
    """
    Example 7: Simulate a real phone call.

    Complete example showing a typical call flow.
    """
    print("\n" + "="*60)
    print("Example 7: Phone Call Simulation")
    print("="*60)

    stt = get_stt_service()
    buffer = AudioBuffer()

    # Simulate incoming call audio
    async def simulate_call_audio():
        """Simulate 10 seconds of call audio"""
        print("📞 Call started...")

        for i in range(100):  # 10 seconds
            chunk = AudioChunk(
                data=b'\x00' * 3200,  # 100ms chunks
                sample_rate=16000,
                channels=1,
            )
            await buffer.put(chunk)
            await asyncio.sleep(0.1)

        print("\n📞 Call ended...")
        await buffer.close()

    call_task = asyncio.create_task(simulate_call_audio())

    try:
        # Start transcription
        audio_stream = AudioStream(buffer)
        conversation = []

        print("\n🎤 Transcription:")
        print("-" * 40)

        async for result in stt.transcribe_stream(
            audio_stream,
            provider="deepgram",
            interim_results=True,
        ):
            if result.is_final:
                conversation.append(result.text)
                print(f"[{result.timestamp.strftime('%H:%M:%S')}] {result.text}")

        await call_task

        # Show call summary
        print("\n" + "="*60)
        print("Call Summary")
        print("="*60)
        print(f"Duration: 10.0s")
        print(f"Sentences: {len(conversation)}")
        print(f"\nFull Transcript:")
        print(" ".join(conversation))

        # Get cost
        stats = await stt.get_usage_stats()
        if stats:
            latest = stats[-1]
            print(f"\nCost: ${latest.cost:.4f}")

    except Exception as e:
        logger.error(f"Error: {e}")


async def run_all_examples():
    """Run all examples sequentially."""
    examples = [
        ("Simple File Transcription", example_1_simple_file_transcription),
        ("Streaming Transcription", example_2_streaming_transcription),
        ("File Streaming", example_3_file_streaming),
        ("Multiple Languages", example_4_multiple_languages),
        ("Cost Tracking", example_5_cost_tracking),
        ("Error Handling", example_6_error_handling),
        ("Call Simulation", example_7_websocket_call_simulation),
    ]

    print("\n" + "="*60)
    print("VOICECON STT SERVICE EXAMPLES")
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
    asyncio.run(example_2_streaming_transcription())

    # Or run all examples
    # asyncio.run(run_all_examples())

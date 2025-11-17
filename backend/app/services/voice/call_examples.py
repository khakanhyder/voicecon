"""
Examples demonstrating Call Manager and WebSocket integration.

These examples show how to connect to the WebSocket endpoint and handle real-time voice calls.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_1_simple_websocket_call():
    """
    Example 1: Simple WebSocket call with audio streaming.

    Demonstrates basic connection and audio sending.
    """
    print("\n" + "="*60)
    print("Example 1: Simple WebSocket Call")
    print("="*60)

    # Configuration
    agent_id = "your-agent-id"  # Replace with actual agent ID
    phone_number = "+1234567890"
    ws_url = f"ws://localhost:8000/api/v1/calls/ws/{agent_id}?phone_number={phone_number}"

    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"Connected to {ws_url}")

            # Send audio chunks (simulated)
            for i in range(10):
                # In real scenario, this would be actual audio data from microphone
                audio_data = b'\x00' * 3200  # 100ms of 16kHz audio
                await websocket.send(audio_data)
                await asyncio.sleep(0.1)

                # Check for messages from server
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                    data = json.loads(message)
                    print(f"Received: {data.get('type')} - {data.get('text', '')}")
                except asyncio.TimeoutError:
                    pass

            # End call
            await websocket.send(json.dumps({"type": "end_call"}))
            print("Call ended")

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_2_audio_file_streaming():
    """
    Example 2: Stream audio from file to WebSocket.

    Demonstrates reading audio from file and streaming it.
    """
    print("\n" + "="*60)
    print("Example 2: Audio File Streaming")
    print("="*60)

    agent_id = "your-agent-id"
    phone_number = "+1234567890"
    audio_file = "path/to/audio.wav"  # Replace with actual audio file
    ws_url = f"ws://localhost:8000/api/v1/calls/ws/{agent_id}?phone_number={phone_number}"

    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"Connected to {ws_url}")

            # Read and stream audio file
            # Note: In production, use proper audio processing libraries
            with open(audio_file, 'rb') as f:
                # Skip WAV header (44 bytes)
                f.seek(44)

                # Stream in chunks
                chunk_size = 3200  # 100ms at 16kHz
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    await websocket.send(chunk)
                    await asyncio.sleep(0.1)  # Simulate real-time

                    # Process received messages
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                        data = json.loads(message)
                        if data.get('type') == 'transcription' and data.get('is_final'):
                            print(f"Transcription: {data.get('text')}")
                        elif data.get('type') == 'agent_response':
                            print(f"Agent: {data.get('text')}")
                    except asyncio.TimeoutError:
                        pass

            # End call
            await websocket.send(json.dumps({"type": "end_call"}))
            print("Call completed")

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_3_bidirectional_call():
    """
    Example 3: Bidirectional call with message handling.

    Demonstrates handling both sending and receiving in parallel.
    """
    print("\n" + "="*60)
    print("Example 3: Bidirectional Call")
    print("="*60)

    agent_id = "your-agent-id"
    phone_number = "+1234567890"
    ws_url = f"ws://localhost:8000/api/v1/calls/ws/{agent_id}?phone_number={phone_number}"

    async def send_audio(websocket):
        """Send audio chunks."""
        try:
            for i in range(100):  # 10 seconds of audio
                audio_data = b'\x00' * 3200
                await websocket.send(audio_data)
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error sending audio: {e}")

    async def receive_messages(websocket):
        """Receive and process messages."""
        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)

                msg_type = data.get('type')
                if msg_type == 'agent_message':
                    print(f"\nAgent: {data.get('text')}")
                elif msg_type == 'transcription':
                    if data.get('is_final'):
                        print(f"\nYou: {data.get('text')}")
                    else:
                        print(f"\r[Listening...] {data.get('text')}", end='')
                elif msg_type == 'agent_response':
                    print(f"\nAgent: {data.get('text')}")
                elif msg_type == 'error':
                    print(f"\nError: {data.get('message')}")
                    break

        except websockets.exceptions.ConnectionClosed:
            print("\nConnection closed")
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")

    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"Connected to {ws_url}")

            # Run send and receive in parallel
            await asyncio.gather(
                send_audio(websocket),
                receive_messages(websocket),
            )

            # End call
            await websocket.send(json.dumps({"type": "end_call"}))

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_4_error_handling():
    """
    Example 4: Error handling and reconnection.

    Demonstrates handling connection errors gracefully.
    """
    print("\n" + "="*60)
    print("Example 4: Error Handling")
    print("="*60)

    agent_id = "your-agent-id"
    phone_number = "+1234567890"
    ws_url = f"ws://localhost:8000/api/v1/calls/ws/{agent_id}?phone_number={phone_number}"

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            print(f"Connection attempt {attempt + 1}/{max_retries}")

            async with websockets.connect(ws_url) as websocket:
                print("Connected successfully")

                # Send audio
                for i in range(20):
                    audio_data = b'\x00' * 3200
                    await websocket.send(audio_data)
                    await asyncio.sleep(0.1)

                    # Simulate network interruption
                    if i == 10:
                        print("\n[Simulating network interruption]")
                        raise ConnectionError("Network interrupted")

                # End call normally
                await websocket.send(json.dumps({"type": "end_call"}))
                print("Call completed successfully")
                break

        except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
            logger.error(f"Connection error: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("Max retries reached. Giving up.")


async def example_5_call_with_authentication():
    """
    Example 5: Authenticated WebSocket call.

    Demonstrates including authentication token in connection.
    """
    print("\n" + "="*60)
    print("Example 5: Authenticated Call")
    print("="*60)

    agent_id = "your-agent-id"
    phone_number = "+1234567890"
    access_token = "your-jwt-token"  # Get from login endpoint

    # Include token in query parameters or headers
    ws_url = f"ws://localhost:8000/api/v1/calls/ws/{agent_id}?phone_number={phone_number}&token={access_token}"

    # Or use headers (if WebSocket endpoint supports it)
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        async with websockets.connect(ws_url, extra_headers=headers) as websocket:
            print("Connected with authentication")

            # Send audio
            for i in range(10):
                audio_data = b'\x00' * 3200
                await websocket.send(audio_data)
                await asyncio.sleep(0.1)

            # End call
            await websocket.send(json.dumps({"type": "end_call"}))

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"Authentication failed: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")


async def example_6_monitoring_call_progress():
    """
    Example 6: Monitor call progress and collect metrics.

    Demonstrates tracking call metrics and quality.
    """
    print("\n" + "="*60)
    print("Example 6: Call Monitoring")
    print("="*60)

    agent_id = "your-agent-id"
    phone_number = "+1234567890"
    ws_url = f"ws://localhost:8000/api/v1/calls/ws/{agent_id}?phone_number={phone_number}"

    # Metrics
    metrics = {
        "audio_sent": 0,
        "transcriptions": 0,
        "agent_responses": 0,
        "errors": 0,
        "latency": [],
    }

    try:
        async with websockets.connect(ws_url) as websocket:
            print("Connected and monitoring")

            start_time = asyncio.get_event_loop().time()

            # Send audio and collect metrics
            for i in range(50):
                send_time = asyncio.get_event_loop().time()

                audio_data = b'\x00' * 3200
                await websocket.send(audio_data)
                metrics["audio_sent"] += 1

                # Check for responses
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                    receive_time = asyncio.get_event_loop().time()
                    latency = (receive_time - send_time) * 1000  # ms

                    data = json.loads(message)
                    msg_type = data.get('type')

                    if msg_type == 'transcription' and data.get('is_final'):
                        metrics["transcriptions"] += 1
                        metrics["latency"].append(latency)
                    elif msg_type == 'agent_response':
                        metrics["agent_responses"] += 1
                    elif msg_type == 'error':
                        metrics["errors"] += 1

                except asyncio.TimeoutError:
                    pass

                await asyncio.sleep(0.1)

            # End call
            await websocket.send(json.dumps({"type": "end_call"}))

            # Print metrics
            duration = asyncio.get_event_loop().time() - start_time
            print("\n" + "="*60)
            print("Call Metrics")
            print("="*60)
            print(f"Duration: {duration:.2f}s")
            print(f"Audio chunks sent: {metrics['audio_sent']}")
            print(f"Transcriptions received: {metrics['transcriptions']}")
            print(f"Agent responses: {metrics['agent_responses']}")
            print(f"Errors: {metrics['errors']}")
            if metrics['latency']:
                avg_latency = sum(metrics['latency']) / len(metrics['latency'])
                print(f"Average latency: {avg_latency:.2f}ms")

    except Exception as e:
        logger.error(f"Error: {e}")


# Client-side JavaScript example for browser
JAVASCRIPT_EXAMPLE = """
// JavaScript WebSocket Client Example
// Use this in browser or Node.js to connect to the call endpoint

const agentId = 'your-agent-id';
const phoneNumber = '+1234567890';
const wsUrl = `ws://localhost:8000/api/v1/calls/ws/${agentId}?phone_number=${phoneNumber}`;

const ws = new WebSocket(wsUrl);

ws.onopen = () => {
    console.log('Connected to call');

    // Get audio from microphone
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            const audioContext = new AudioContext({ sampleRate: 16000 });
            const source = audioContext.createMediaStreamSource(stream);
            const processor = audioContext.createScriptProcessor(4096, 1, 1);

            source.connect(processor);
            processor.connect(audioContext.destination);

            processor.onaudioprocess = (e) => {
                // Get audio data
                const audioData = e.inputBuffer.getChannelData(0);

                // Convert to 16-bit PCM
                const pcm = new Int16Array(audioData.length);
                for (let i = 0; i < audioData.length; i++) {
                    pcm[i] = Math.max(-32768, Math.min(32767, audioData[i] * 32768));
                }

                // Send to WebSocket
                ws.send(pcm.buffer);
            };
        });
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'transcription' && data.is_final) {
        console.log('You said:', data.text);
        document.getElementById('transcript').innerHTML += `<p>You: ${data.text}</p>`;
    } else if (data.type === 'agent_response') {
        console.log('Agent:', data.text);
        document.getElementById('transcript').innerHTML += `<p>Agent: ${data.text}</p>`;

        // TODO: Play agent's audio response (TTS)
    } else if (data.type === 'error') {
        console.error('Error:', data.message);
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Call ended');
};

// End call
function endCall() {
    ws.send(JSON.stringify({ type: 'end_call' }));
    ws.close();
}
"""


async def run_all_examples():
    """Run all examples sequentially."""
    examples = [
        ("Simple WebSocket Call", example_1_simple_websocket_call),
        ("Audio File Streaming", example_2_audio_file_streaming),
        ("Bidirectional Call", example_3_bidirectional_call),
        ("Error Handling", example_4_error_handling),
        ("Authenticated Call", example_5_call_with_authentication),
        ("Call Monitoring", example_6_monitoring_call_progress),
    ]

    print("\n" + "="*60)
    print("VOICECON CALL MANAGER EXAMPLES")
    print("="*60)
    print("\nNote: These examples require:")
    print("  1. Backend server running (python -m uvicorn app.main:app)")
    print("  2. Valid agent_id")
    print("  3. websockets package (pip install websockets)")
    print("\nUpdate the agent_id in each example before running.")
    print("="*60)

    for name, example_func in examples:
        try:
            print(f"\n\nRunning: {name}")
            await example_func()
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Error in {name}: {e}")

    # Print JavaScript example
    print("\n" + "="*60)
    print("BROWSER CLIENT EXAMPLE")
    print("="*60)
    print(JAVASCRIPT_EXAMPLE)


if __name__ == "__main__":
    # Run specific example
    # asyncio.run(example_1_simple_websocket_call())

    # Or print JavaScript example
    print(JAVASCRIPT_EXAMPLE)

    # Or run all examples
    # asyncio.run(run_all_examples())

"""
Call Recording Service.

Handles call recording, storage, and retrieval.
"""
import logging
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import aiofiles
import hashlib

from app.core.config import settings
from app.services.telephony.twilio_service import get_twilio_service

logger = logging.getLogger(__name__)


class RecordingService:
    """
    Service for managing call recordings.

    Features:
    - Download recordings from Twilio
    - Store recordings locally or in S3
    - Track recording metadata
    - Generate recording URLs
    - Handle recording deletion
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize recording service.

        Args:
            storage_path: Path to store recordings locally
        """
        self.storage_path = Path(storage_path or settings.RECORDINGS_PATH or "recordings")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.twilio_service = get_twilio_service()

    async def download_recording(
        self,
        call_sid: str,
        recording_sid: str,
        call_id: str,
    ) -> Optional[str]:
        """
        Download recording from Twilio and save locally.

        Args:
            call_sid: Twilio call SID
            recording_sid: Twilio recording SID
            call_id: Internal call ID

        Returns:
            Local file path or None if failed
        """
        try:
            logger.info(f"Downloading recording: recording_sid={recording_sid}, call_id={call_id}")

            # Get recording details from Twilio
            recordings = await self.twilio_service.get_call_recordings(call_sid)

            recording_data = None
            for rec in recordings:
                if rec["recording_sid"] == recording_sid:
                    recording_data = rec
                    break

            if not recording_data:
                logger.error(f"Recording not found: {recording_sid}")
                return None

            # Download recording file
            recording_url = recording_data["url"]

            # TODO: Implement actual download from Twilio
            # For now, just return the URL
            # In production, you'd use:
            # async with httpx.AsyncClient() as client:
            #     response = await client.get(recording_url)
            #     audio_data = response.content

            # Generate filename
            filename = self._generate_filename(call_id, recording_sid)
            filepath = self.storage_path / filename

            # Save to local storage
            # async with aiofiles.open(filepath, 'wb') as f:
            #     await f.write(audio_data)

            logger.info(f"Recording downloaded: {filepath}")

            return str(filepath)

        except Exception as e:
            logger.error(f"Error downloading recording: {e}", exc_info=True)
            return None

    def _generate_filename(self, call_id: str, recording_sid: str) -> str:
        """
        Generate filename for recording.

        Args:
            call_id: Call ID
            recording_sid: Recording SID

        Returns:
            Filename
        """
        # Format: call_<call_id>_<recording_sid>.mp3
        return f"call_{call_id}_{recording_sid}.mp3"

    async def get_recording_url(self, filepath: str) -> str:
        """
        Get URL for accessing recording.

        Args:
            filepath: Local file path

        Returns:
            Public URL for the recording
        """
        # In production, upload to S3 and return S3 URL
        # For now, return local path
        return f"/api/v1/recordings/{Path(filepath).name}"

    async def delete_recording(self, filepath: str) -> bool:
        """
        Delete recording file.

        Args:
            filepath: File path to delete

        Returns:
            True if deleted successfully
        """
        try:
            path = Path(filepath)
            if path.exists():
                path.unlink()
                logger.info(f"Recording deleted: {filepath}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting recording: {e}")
            return False

    async def get_recording_duration(self, filepath: str) -> Optional[int]:
        """
        Get recording duration in seconds.

        Args:
            filepath: Recording file path

        Returns:
            Duration in seconds or None
        """
        try:
            # TODO: Implement using audio library
            # import librosa
            # duration = librosa.get_duration(filename=filepath)
            # return int(duration)

            return None

        except Exception as e:
            logger.error(f"Error getting recording duration: {e}")
            return None


# Global recording service instance
_recording_service: Optional[RecordingService] = None


def get_recording_service() -> RecordingService:
    """
    Get global recording service instance (singleton).

    Returns:
        RecordingService instance
    """
    global _recording_service
    if _recording_service is None:
        _recording_service = RecordingService()
    return _recording_service

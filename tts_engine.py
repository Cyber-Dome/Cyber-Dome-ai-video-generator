# UPGRADED VERSION

import asyncio
import logging
from pathlib import Path
import edge_tts

logger = logging.getLogger(__name__)

VOICE_STYLES = {
    "narration": {"rate": "+0%", "pitch": "+0Hz"},
    "cinematic": {"rate": "-15%", "pitch": "-10Hz"},
    "calm": {"rate": "-10%", "pitch": "-5Hz"},
    "energetic": {"rate": "+20%", "pitch": "+10Hz"},
    "deep": {"rate": "-20%", "pitch": "-15Hz"},
}

EDGE_VOICES = {
    "male": "en-US-ChristopherNeural",
    "female": "en-US-JennyNeural"
}


async def _generate(text, output_path, voice, rate, pitch):
    communicate = edge_tts.Communicate(
        text,
        voice=voice,
        rate=rate,
        pitch=pitch
    )
    await communicate.save(str(output_path))


def generate_voice_pro(text: str, output_path: Path, style="narration", gender="male"):
    try:
        style_cfg = VOICE_STYLES.get(style.lower(), VOICE_STYLES["narration"])
        voice = EDGE_VOICES.get(gender, EDGE_VOICES["male"])

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(
            _generate(
                text,
                output_path,
                voice,
                style_cfg["rate"],
                style_cfg["pitch"]
            )
        )

        loop.close()

        return output_path

    except Exception as e:
        logger.error(f"TTS failed: {e}")
        return None
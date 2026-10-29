"""Pluggable TTS providers for tts_router.py. Contract: lines.json → <id>.wav + dur.json."""
PROVIDERS = ("edge", "kokoro", "qwen3", "omnivoice", "stepaudio", "elevenlabs", "elevenlabs-dialogue")

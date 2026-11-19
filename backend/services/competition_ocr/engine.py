"""Use the backend model provider instead of an experiment environment."""
from services.recognition.provider import PaddleProvider

PaddleEngine = PaddleProvider

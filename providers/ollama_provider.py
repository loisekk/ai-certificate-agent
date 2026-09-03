"""
Ollama Provider - Local LLM inference
Runs models locally via Ollama server.
"""

import requests
from typing import Dict, Optional
from .base import LLMProvider
import logging

logger = logging.getLogger('OllamaProvider')


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = config.get('ollama_url', 'http://localhost:11434')
        self.model = config.get('ollama_model', 'qwen2.5:3b')
        self.timeout = config.get('timeout', 300)
    
    def generate(self, prompt: str, system_prompt: str = None,
                 max_tokens: int = 4096, temperature: float = 0.7) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            },
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            return response.json()['message']['content']
        else:
            raise Exception(f"Ollama error {response.status_code}: {response.text}")
    
    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
    
    def get_model_info(self) -> Dict:
        return {
            'provider': 'ollama',
            'model': self.model,
            'base_url': self.base_url,
            'type': 'local'
        }

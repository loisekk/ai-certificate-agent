"""
OpenAI Provider - GPT models via OpenAI API
Supports GPT-4o, GPT-4o-mini, GPT-3.5-turbo.
"""

import requests
from typing import Dict, Optional
from .base import LLMProvider
import logging

logger = logging.getLogger('OpenAIProvider')


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get('openai_api_key', '')
        self.model = config.get('openai_model', 'gpt-4o-mini')
        self.base_url = config.get('openai_base_url', 'https://api.openai.com/v1')
        self.timeout = config.get('timeout', 120)
    
    def generate(self, prompt: str, system_prompt: str = None,
                 max_tokens: int = 4096, temperature: float = 0.7) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            raise Exception(f"OpenAI error {response.status_code}: {response.text}")
    
    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(f"{self.base_url}/models", headers=headers, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False
    
    def get_model_info(self) -> Dict:
        return {
            'provider': 'openai',
            'model': self.model,
            'base_url': self.base_url,
            'type': 'cloud'
        }

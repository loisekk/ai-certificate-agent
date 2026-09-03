"""
DeepSeek Provider - Affordable cloud LLM
Supports DeepSeek-V2, DeepSeek-Coder, etc.
"""

import requests
from typing import Dict, Optional
from .base import LLMProvider
import logging

logger = logging.getLogger('DeepSeekProvider')


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider (OpenAI-compatible)."""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get('deepseek_api_key', '')
        self.model = config.get('deepseek_model', 'deepseek-chat')
        self.base_url = config.get('deepseek_base_url', 'https://api.deepseek.com/v1')
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
            raise Exception(f"DeepSeek error {response.status_code}: {response.text}")
    
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
            'provider': 'deepseek',
            'model': self.model,
            'base_url': self.base_url,
            'type': 'cloud'
        }

"""
Anthropic Provider - Claude models via Anthropic API
Supports Claude 3.5 Sonnet, Claude 3 Haiku, etc.
"""

import requests
from typing import Dict, Optional
from .base import LLMProvider
import logging

logger = logging.getLogger('AnthropicProvider')


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get('anthropic_api_key', '')
        self.model = config.get('anthropic_model', 'claude-3-5-sonnet-20241022')
        self.base_url = config.get('anthropic_base_url', 'https://api.anthropic.com')
        self.timeout = config.get('timeout', 120)
    
    def generate(self, prompt: str, system_prompt: str = None,
                 max_tokens: int = 4096, temperature: float = 0.7) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        response = requests.post(
            f"{self.base_url}/v1/messages",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['content'][0]['text']
        else:
            raise Exception(f"Anthropic error {response.status_code}: {response.text}")
    
    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            # Anthropic doesn't have a simple health endpoint, check with a minimal request
            resp = requests.get(f"{self.base_url}/v1/models", headers=headers, timeout=10)
            # Even a 405 means the server is reachable
            return resp.status_code in [200, 405]
        except Exception:
            return False
    
    def get_model_info(self) -> Dict:
        return {
            'provider': 'anthropic',
            'model': self.model,
            'base_url': self.base_url,
            'type': 'cloud'
        }

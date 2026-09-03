"""
Base LLM Provider Interface
All providers (Ollama, OpenAI, Anthropic, DeepSeek, Groq) implement this.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List
import logging

logger = logging.getLogger('LLMProvider')


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: Dict):
        """
        Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = None,
                 max_tokens: int = 4096, temperature: float = 0.7) -> str:
        """
        Generate text from a prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available/reachable.
        
        Returns:
            True if provider is ready to use
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict:
        """
        Get information about the current model.
        
        Returns:
            Dict with model name, provider, etc.
        """
        pass
    
    def generate_with_retry(self, prompt: str, system_prompt: str = None,
                           max_retries: int = 2, **kwargs) -> str:
        """Generate with retry logic."""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = self.generate(prompt, system_prompt, **kwargs)
                if result:
                    return result
                last_error = "Empty response from provider"
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
        
        raise Exception(f"Provider {self.name} failed after {max_retries + 1} attempts: {last_error}")

"""
Provider Factory - Creates the right LLM provider based on config.
Supports: ollama, openai, anthropic, deepseek, groq
"""

import os
from typing import Dict, Optional
from .base import LLMProvider
import logging

logger = logging.getLogger('ProviderFactory')

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    # Look for .env in parent directory (project root)
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"Loaded .env from {env_path}")
except ImportError:
    pass


# Provider registry
PROVIDERS = {
    'ollama': 'providers.ollama_provider.OllamaProvider',
    'openai': 'providers.openai_provider.OpenAIProvider',
    'anthropic': 'providers.anthropic_provider.AnthropicProvider',
    'deepseek': 'providers.deepseek_provider.DeepSeekProvider',
    'groq': 'providers.groq_provider.GroqProvider',
}


def create_provider(provider_name: str = None, config: Dict = None) -> LLMProvider:
    """
    Factory function to create an LLM provider.
    
    Args:
        provider_name: Name of provider ('ollama', 'openai', 'anthropic', 'deepseek', 'groq')
                      If None, reads from LLM_PROVIDER env var, defaults to 'groq'
        config: Provider configuration dict. If None, reads from env vars.
    
    Returns:
        Initialized LLMProvider instance
    
    Raises:
        ValueError: If provider name is not recognized
    """
    if provider_name is None:
        provider_name = os.environ.get('LLM_PROVIDER', 'groq')
    
    provider_name = provider_name.lower().strip()
    
    if provider_name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: '{provider_name}'. "
            f"Available: {', '.join(PROVIDERS.keys())}"
        )
    
    # Build config from env vars if not provided
    if config is None:
        config = _config_from_env(provider_name)
    
    # Dynamically import and instantiate
    module_path, class_name = PROVIDERS[provider_name].rsplit('.', 1)
    import importlib
    module = importlib.import_module(module_path)
    provider_class = getattr(module, class_name)
    
    provider = provider_class(config)
    logger.info(f"Created provider: {provider_name} ({provider.get_model_info()})")
    
    return provider


def _config_from_env(provider_name: str) -> Dict:
    """Build provider config from environment variables."""
    base_config = {
        'postgres_host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'postgres_port': os.environ.get('POSTGRES_PORT', '5432'),
        'postgres_db': os.environ.get('POSTGRES_DB', 'certificate_tracker'),
        'postgres_user': os.environ.get('POSTGRES_USER', 'postgres'),
        'postgres_password': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
    }
    
    if provider_name == 'ollama':
        base_config.update({
            'ollama_url': os.environ.get('OLLAMA_URL', 'http://localhost:11434'),
            'ollama_model': os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b'),
        })
    elif provider_name == 'openai':
        base_config.update({
            'openai_api_key': os.environ.get('OPENAI_API_KEY', ''),
            'openai_model': os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
            'openai_base_url': os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
        })
    elif provider_name == 'anthropic':
        base_config.update({
            'anthropic_api_key': os.environ.get('ANTHROPIC_API_KEY', ''),
            'anthropic_model': os.environ.get('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022'),
        })
    elif provider_name == 'deepseek':
        base_config.update({
            'deepseek_api_key': os.environ.get('DEEPSEEK_API_KEY', ''),
            'deepseek_model': os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat'),
        })
    elif provider_name == 'groq':
        base_config.update({
            'groq_api_key': os.environ.get('GROQ_API_KEY', ''),
            'groq_model': os.environ.get('GROQ_MODEL', 'llama3-70b-8192'),
        })
    
    return base_config


def list_providers() -> Dict[str, Dict]:
    """List all available providers and their status."""
    results = {}
    for name in PROVIDERS:
        try:
            provider = create_provider(name)
            results[name] = {
                'available': provider.is_available(),
                'info': provider.get_model_info()
            }
        except Exception as e:
            results[name] = {
                'available': False,
                'error': str(e)
            }
    return results

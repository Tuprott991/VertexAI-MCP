from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.base_agent import BaseAgent
from typing import Any

class ResponseCachePlugin(BasePlugin):
    """A plugin to cache agent responses."""

    def __init__(self):
        super().__init__()
        self.cache = {}

    async def before_response(self, agent: BaseAgent, prompt: str, **kwargs: Any) -> Any:
        """Check if the response is cached before generating a new one."""
        if prompt in self.cache:
            return self.cache[prompt]
        return None

    async def after_response(self, agent: BaseAgent, prompt: str, response: str, **kwargs: Any) -> None:
        """Cache the response after it has been generated."""
        self.cache[prompt] = response

# For testing purposes, prompt will cache as vector, if there is a similar vector in the cache, return the response

    # def calculate_similarity(self, vec1: Any, vec2: Any) -> float:
    #     # Simple cosine similarity or other metric can be implemented here
    #     return vec1.dot(vec2) / (vec1.norm() * vec2.norm()) if vec1.norm() != 0 and vec2.norm() != 0 else 0.0

    # async def get_cached_response(self, prompt_vector: Any, similarity_threshold: float = 0.9) -> Any: 
    #     """Retrieve a cached response based on vector similarity."""
    #     for cached_vector, response in self.cache.items():
    #         similarity = self.calculate_similarity(prompt_vector, cached_vector)
    #         if similarity >= similarity_threshold:
    #             return response
    #     return None
    
    # async def cache_response(self, prompt_vector: Any, response: str) -> None:
    #     """Cache the response with its corresponding vector."""
    #     self.cache[prompt_vector] = response
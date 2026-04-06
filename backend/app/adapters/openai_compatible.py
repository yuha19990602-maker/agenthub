"""OpenAI Compatible API adapter for native chat resources"""

import json
import os
import logging
from typing import List, Optional, Dict, Any, AsyncIterator

import httpx

from ..models import Resource, PortalMessage


logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter:
    """
    Adapter for OpenAI Compatible API endpoints.
    Supports both streaming and non-streaming chat completions.
    """

    async def send_message(
        self,
        resource: Resource,
        history: List[PortalMessage],
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Send a non-streaming message to OpenAI Compatible API.
        
        Args:
            resource: Resource configuration
            history: Previous messages in the session
            text: User's message text
            context: Additional context (system_prompt, etc.)
            
        Returns:
            Assistant's response text
        """
        messages = self._build_messages_from_history(history, text, context)
        
        payload = {
            "model": resource.config.model,
            "messages": messages,
            **resource.config.default_params,
            "stream": False,
        }
        
        headers = self._build_headers(resource.config)
        url = f"{resource.config.base_url.rstrip('/')}/{resource.config.request_path.lstrip('/')}"
        
        try:
            async with httpx.AsyncClient(timeout=resource.config.timeout_sec) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return self._extract_text_from_completion(data)
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling OpenAI Compatible API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling OpenAI Compatible API: {e}")
            raise

    async def send_message_stream(
        self,
        resource: Resource,
        history: List[PortalMessage],
        text: str,
        context: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """
        Send a streaming message to OpenAI Compatible API.
        
        Args:
            resource: Resource configuration
            history: Previous messages in the session
            text: User's message text
            context: Additional context (system_prompt, etc.)
            
        Yields:
            Text chunks from the streaming response
        """
        messages = self._build_messages_from_history(history, text, context)
        
        payload = {
            "model": resource.config.model,
            "messages": messages,
            **resource.config.default_params,
            "stream": True,
        }
        
        headers = self._build_headers(resource.config)
        url = f"{resource.config.base_url.rstrip('/')}/{resource.config.request_path.lstrip('/')}"
        
        try:
            async with httpx.AsyncClient(timeout=resource.config.timeout_sec) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=headers,
                    json=payload
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        
                        data_str = line[5:].strip()  # Remove "data: " prefix
                        
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data_str)
                            delta = self._extract_delta_text(chunk)
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE chunk: {data_str}")
                            continue
                            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in streaming OpenAI Compatible API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in streaming OpenAI Compatible API: {e}")
            raise

    def _build_headers(self, config) -> Dict[str, str]:
        """Build request headers from config"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **config.headers,
        }
        
        # Get API key from environment variable if configured
        if config.api_key_env:
            api_key = os.getenv(config.api_key_env)
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        
        return headers

    def _build_messages_from_history(
        self,
        history: List[PortalMessage],
        user_input: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Build OpenAI format messages from Portal history.
        
        Args:
            history: Previous messages (already limited by history_window)
            user_input: Current user input
            context: May contain 'system_prompt'
            
        Returns:
            List of messages in OpenAI format
        """
        messages = []
        
        # Add system prompt if provided
        system_prompt = context.get("system_prompt")
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add history messages
        for msg in history:
            if msg.role in ("user", "assistant", "system"):
                messages.append({"role": msg.role, "content": msg.text})
        
        # Add current user input
        messages.append({"role": "user", "content": user_input})
        
        return messages

    def _extract_text_from_completion(self, data: Dict[str, Any]) -> str:
        """
        Extract text from OpenAI chat completion response.
        Handles both string content and array content (for vision models).
        """
        choices = data.get("choices", [])
        if not choices:
            return ""
        
        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content")
        
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            # Handle array content (vision models)
            return "".join(
                part.get("text", "") 
                for part in content 
                if isinstance(part, dict)
            )
        
        return ""

    def _extract_delta_text(self, chunk: Dict[str, Any]) -> str:
        """
        Extract delta text from OpenAI streaming chunk.
        Handles both string content and array content.
        """
        choices = chunk.get("choices", [])
        if not choices:
            return ""
        
        choice = choices[0]
        delta = choice.get("delta", {})
        content = delta.get("content")
        
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            # Handle array content (vision models)
            return "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
        
        return ""


# Global adapter instance
openai_compatible_adapter = OpenAICompatibleAdapter()

"""OpenCode adapter for native dialogue"""

import json
import uuid
import httpx
import logging
import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime
from fastapi import UploadFile

from .base import ExecutionAdapter
from ..models import Message
from ..config import settings


logger = logging.getLogger(__name__)


class OpenCodeAdapter(ExecutionAdapter):
    """
    Adapter for OpenCode server HTTP API
    Handles native dialogue sessions
    """

    def __init__(self):
        self.base_url = settings.opencode_base_url.rstrip("/")
        self.username = settings.opencode_username
        self.password = settings.opencode_password
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with event loop safety"""
        current_loop = asyncio.get_running_loop()
        
        async with self._client_lock:
            # Check if we need to recreate client (new loop or no client)
            if self._client is None or self._loop != current_loop:
                # Close old client if exists
                if self._client is not None:
                    try:
                        await self._client.aclose()
                    except Exception as e:
                        logger.warning(f"Error closing old client: {e}")
                
                # Only use auth if both username and password are provided
                auth = (self.username, self.password) if self.username and self.password else None
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    auth=auth,
                    timeout=60.0
                )
                self._loop = current_loop
                logger.debug(f"Created new httpx client for loop {id(current_loop)}")
            
            return self._client

    async def close(self):
        """Close HTTP client"""
        async with self._client_lock:
            if self._client:
                try:
                    await self._client.aclose()
                except Exception as e:
                    logger.warning(f"Error closing client: {e}")
                finally:
                    self._client = None
                    self._loop = None

    async def create_session(
        self,
        resource_id: str,
        user_context: Dict[str, Any],
        config: Dict[str, Any]
    ) -> str:
        """
        Create a new OpenCode session
        Returns the OpenCode session ID
        """
        client = await self._get_client()

        title = config.get("title") or config.get("name") or resource_id

        try:
            response = await client.post(
                "/session",
                json={"title": title}
            )
            response.raise_for_status()

            data = response.json()
            session_id = data.get("id")
            if not session_id:
                raise ValueError("OpenCode create_session response missing 'id'")

            logger.info(
                "Created OpenCode session %s for emp_no=%s",
                session_id,
                user_context.get("emp_no", "unknown")
            )
            return session_id

        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"Failed to create OpenCode session: {e}")
            raise

    async def send_message(
        self,
        session_id: str,
        message: str,
        trace_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Send a message to OpenCode session
        Returns the assistant's response text
        """
        client = await self._get_client()

        headers = {}
        if trace_id:
            headers["X-Trace-ID"] = trace_id

        payload: Dict[str, Any] = {
            "parts": [{"type": "text", "text": message}]
        }
        if system_prompt:
            payload["system"] = system_prompt
        if agent:
            payload["agent"] = agent
        if tools:
            payload["tools"] = tools
        if extra_body:
            payload.update(extra_body)

        try:
            response = await client.post(
                f"/session/{session_id}/message",
                json=payload,
                headers=headers
            )
            response.raise_for_status()

            data = response.json()
            assistant_message = self._extract_text_from_parts(data.get("parts", []))

            logger.info(f"Sent message to session {session_id}, trace_id={trace_id}")
            return assistant_message

        except httpx.HTTPError as e:
            logger.error(f"Failed to send message to session {session_id}: {e}")
            raise

    async def send_message_stream(
        self,
        session_id: str,
        message: str,
        trace_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """
        Send a message to OpenCode session with streaming response
        Yields chunks of the assistant's response
        """
        client = await self._get_client()

        headers = {}
        if trace_id:
            headers["X-Trace-ID"] = trace_id

        payload: Dict[str, Any] = {
            "parts": [{"type": "text", "text": message}],
            "stream": True
        }
        if system_prompt:
            payload["system"] = system_prompt
        if agent:
            payload["agent"] = agent
        if tools:
            payload["tools"] = tools
        if extra_body:
            payload.update(extra_body)

        try:
            async with client.stream(
                "POST",
                f"/session/{session_id}/message",
                json=payload,
                headers=headers,
                timeout=120.0
            ) as response:
                response.raise_for_status()
                
                # Process SSE stream
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    # OpenCode returns JSON lines directly (not standard SSE with 'data: ' prefix)
                    # Try to parse as JSON first
                    try:
                        data = json.loads(line)
                        
                        # Extract text from OpenCode response format
                        if isinstance(data, dict):
                            chunk_text = self._extract_stream_chunk_text(data)
                            if chunk_text:
                                yield chunk_text
                    except json.JSONDecodeError:
                        # Not valid JSON, handle as SSE format or plain text
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                envelope = json.loads(data_str)
                                if isinstance(envelope, dict):
                                    chunk_text = self._extract_stream_chunk_text(envelope)
                                    if chunk_text:
                                        yield chunk_text
                            except json.JSONDecodeError:
                                if data_str and data_str != "[DONE]":
                                    yield data_str
                        elif line and not line.startswith(":"):
                            yield line

            logger.info(f"Streamed message to session {session_id}, trace_id={trace_id}")

        except httpx.HTTPError as e:
            logger.error(f"Failed to stream message to session {session_id}: {e}")
            raise

    def _extract_stream_chunk_text(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract text from stream chunk data"""
        # Try different possible formats
        
        # OpenCode specific format: { "parts": [...] }
        if "parts" in data and isinstance(data["parts"], list):
            text_parts = []
            for part in data["parts"]:
                if part.get("type") == "text" and "text" in part:
                    text_parts.append(part["text"])
            if text_parts:
                return "\n".join(text_parts)
        
        # OpenAI-style format
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "delta" in choice:
                return choice["delta"].get("content", "")
            if "text" in choice:
                return choice["text"]
        
        if "content" in data:
            return data["content"]
        
        if "text" in data:
            return data["text"]
        
        if "message" in data and isinstance(data["message"], dict):
            return data["message"].get("content", "")
        
        return None

    async def get_messages(
        self,
        session_id: str,
        trace_id: Optional[str] = None
    ) -> List[Message]:
        """
        Get message history from OpenCode session
        """
        client = await self._get_client()

        headers = {}
        if trace_id:
            headers["X-Trace-ID"] = trace_id

        try:
            response = await client.get(
                f"/session/{session_id}/message",
                headers=headers
            )
            response.raise_for_status()

            payload = response.json()
            #raw_messages = payload if isinstance(payload, list) else []
            if isinstance(payload, list):
                raw_messages = payload
            elif isinstance(payload, dict):
                raw_messages = payload.get("messages", [])
            else:
                raw_messages = []
            messages: List[Message] = []

            for msg in raw_messages:
                info = msg.get("info", {})
                role = info.get("role", "assistant")
                timestamp_raw = info.get("createdAt")
                timestamp = self._parse_iso_datetime(timestamp_raw)
                text = self._extract_text_from_parts(msg.get("parts", []))

                messages.append(Message(role=role, text=text, timestamp=timestamp))

            logger.info(f"Retrieved {len(messages)} messages from session {session_id}")
            return messages

        except httpx.HTTPError as e:
            logger.error(f"Failed to get messages from session {session_id}: {e}")
            raise

    async def close_session(
        self,
        session_id: str,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Close an OpenCode session
        """
        client = await self._get_client()

        headers = {}
        if trace_id:
            headers["X-Trace-ID"] = trace_id

        try:
            response = await client.delete(
                f"/session/{session_id}",
                headers=headers
            )
            response.raise_for_status()

            logger.info(f"Closed OpenCode session: {session_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to close session {session_id}: {e}")
            return False

    async def upload_file(
        self,
        session_id: str,
        file: UploadFile,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to the OpenCode session
        """
        client = await self._get_client()

        try:
            # Read file content
            content = await file.read()
            
            # Prepare multipart form data
            files = {
                "file": (file.filename, content, file.content_type or "application/octet-stream")
            }
            data = {}
            if description:
                data["description"] = description

            response = await client.post(
                f"/session/{session_id}/upload",
                files=files,
                data=data
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Uploaded file {file.filename} to session {session_id}")
            
            # Return standardized response
            return {
                "file_id": result.get("id") or result.get("file_id") or str(uuid.uuid4()),
                "file_name": file.filename,
                "file_type": file.content_type or "application/octet-stream",
                "file_size": len(content),
                "url": result.get("url") or f"/session/{session_id}/files/{result.get('id', 'unknown')}"
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to upload file to session {session_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {e}")
            raise

    @staticmethod
    def _extract_text_from_parts(parts: List[Dict[str, Any]]) -> str:
        """Extract readable text from OpenCode message parts."""
        text_chunks = []
        for part in parts:
            if part.get("type") == "text" and part.get("text"):
                text_chunks.append(part["text"])
            elif part.get("type") == "image" and part.get("url"):
                text_chunks.append(f"[Image: {part['url']}]")
            elif part.get("type") == "file" and part.get("name"):
                text_chunks.append(f"[File: {part['name']}]")
        return "\n".join(text_chunks)

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse ISO-8601 datetime string into datetime object."""
        if not value:
            return None

        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            logger.warning("Failed to parse message timestamp: %s", value)
            return None

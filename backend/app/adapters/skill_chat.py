"""Skill Chat adapter for skill-based conversations"""

import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from fastapi import UploadFile

from .base import ExecutionAdapter
from .opencode import OpenCodeAdapter
from ..models import Message


logger = logging.getLogger(__name__)


class SkillChatAdapter(ExecutionAdapter):
    """
    Adapter for skill-based conversations
    Wraps OpenCodeAdapter with skill-specific behavior
    """

    def __init__(self):
        self.opencode_adapter = OpenCodeAdapter()
        # Hot cache for skill_name lookup; not the source of truth after restart.
        self._session_skill_map: Dict[str, str] = {}

    async def create_session(
        self,
        resource_id: str,
        user_context: Dict[str, Any],
        config: Dict[str, Any]
    ) -> str:
        """
        Create a new skill chat session
        Stores skill_name in a hot cache for convenience; callers should persist binding.
        """
        skill_name = config.get("skill_name", resource_id)

        session_id = await self.opencode_adapter.create_session(
            resource_id,
            user_context,
            config
        )
        self._session_skill_map[session_id] = skill_name

        logger.info(f"Created skill chat session: {session_id} for skill: {skill_name}")
        return session_id

    async def send_message(
        self,
        session_id: str,
        message: str,
        trace_id: Optional[str] = None,
        skill_name: Optional[str] = None,
        workspace_id: Optional[str] = None,
        entrypoint_id: Optional[str] = None,
    ) -> str:
        """
        Send a message to skill chat session
        Injects system prompt to enforce skill mode behavior.
        skill_name is preferred; falls back to in-memory cache.
        """
        resolved_skill = skill_name or self._session_skill_map.get(session_id, "unknown_skill")
        system_prompt = self._build_skill_mode_system_prompt(resolved_skill)

        extra_body = {
            "portal_metadata": {
                "workspace_id": workspace_id,
                "entrypoint_id": entrypoint_id,
                "skill_name": resolved_skill,
            }
        }

        return await self.opencode_adapter.send_message(
            session_id=session_id,
            message=message,
            trace_id=trace_id,
            system_prompt=system_prompt,
            extra_body=extra_body,
        )

    async def send_message_stream(
        self,
        session_id: str,
        message: str,
        trace_id: Optional[str] = None,
        skill_name: Optional[str] = None,
        workspace_id: Optional[str] = None,
        entrypoint_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Send a message to skill chat session with streaming response
        Injects system prompt to enforce skill mode behavior.
        skill_name is preferred; falls back to in-memory cache.
        """
        resolved_skill = skill_name or self._session_skill_map.get(session_id, "unknown_skill")
        system_prompt = self._build_skill_mode_system_prompt(resolved_skill)

        extra_body = {
            "portal_metadata": {
                "workspace_id": workspace_id,
                "entrypoint_id": entrypoint_id,
                "skill_name": resolved_skill,
            }
        }

        async for chunk in self.opencode_adapter.send_message_stream(
            session_id=session_id,
            message=message,
            trace_id=trace_id,
            system_prompt=system_prompt,
            extra_body=extra_body,
        ):
            yield chunk

    async def get_messages(
        self,
        session_id: str,
        trace_id: Optional[str] = None
    ) -> List[Message]:
        """
        Get message history from skill chat session
        Delegates to OpenCode adapter
        """
        return await self.opencode_adapter.get_messages(session_id, trace_id)

    async def close_session(
        self,
        session_id: str,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Close skill chat session
        Delegates to OpenCode adapter
        """
        self._session_skill_map.pop(session_id, None)
        return await self.opencode_adapter.close_session(session_id, trace_id)

    async def upload_file(
        self,
        session_id: str,
        file: UploadFile,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to the skill chat session
        Delegates to OpenCode adapter
        """
        return await self.opencode_adapter.upload_file(session_id, file, description)

    async def close(self):
        """Close underlying adapter"""
        self._session_skill_map.clear()
        await self.opencode_adapter.close()

    @staticmethod
    def _build_skill_mode_system_prompt(skill_name: str) -> str:
        return (
            f'You are in skill mode "{skill_name}".\n'
            "Treat this skill as the primary workflow for this session.\n"
            f'Use the native skill tool to load "{skill_name}" when needed.\n'
            "Do not silently switch to another skill."
        )

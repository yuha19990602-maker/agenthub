"""In-memory storage layer for sessions and launch records (Primary implementation)"""

import itertools
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from collections import OrderedDict, defaultdict

from ..models import (
    PortalSession, LaunchRecord, SessionBinding, PortalMessage, 
    ContextScope, AuthSession
)


logger = logging.getLogger(__name__)


class MemoryStore:
    """
    In-memory storage for all portal data.
    This is the primary storage implementation - Redis has been deprecated.
    """

    def __init__(self):
        # Global sequence counter for ordering
        self._seq = itertools.count(1)
        self._lock = asyncio.Lock()
        
        # Primary data stores
        self._sessions: OrderedDict[str, PortalSession] = OrderedDict()
        self._launches: OrderedDict[str, LaunchRecord] = OrderedDict()
        self._bindings: OrderedDict[str, SessionBinding] = OrderedDict()
        self._messages: OrderedDict[str, PortalMessage] = OrderedDict()
        self._contexts: OrderedDict[str, ContextScope] = OrderedDict()
        
        # V2: Auth session storage
        self._auth_sessions: Dict[str, AuthSession] = {}
        self._oauth_states: Dict[str, tuple[str, int]] = {}  # state -> (next_url, expires_at)
        
        # Indexes
        self._user_sessions: Dict[str, List[str]] = defaultdict(list)
        self._user_launches: Dict[str, List[str]] = defaultdict(list)
        self._session_messages: Dict[str, List[str]] = defaultdict(list)
        self._session_bindings: Dict[str, List[str]] = defaultdict(list)
        self._context_scopes: Dict[str, List[str]] = defaultdict(list)
        
        # Deduplication
        self._message_dedupe: Dict[str, str] = {}  # dedupe_key -> message_id
        
        # Limits to prevent unbounded growth
        self._max_sessions = 1000
        self._max_launches = 1000
        self._max_bindings = 2000
        self._max_messages = 10000
        self._max_contexts = 2000
        self._max_user_sessions = 100
        self._max_user_launches = 100
        self._max_session_messages = 200
        self._max_auth_sessions = 1000
        self._max_oauth_states = 100

    # Session operations
    async def save_session(self, session: PortalSession) -> PortalSession:
        """Save portal session to memory - returns the session object"""
        async with self._lock:
            self._sessions[session.portal_session_id] = session

            if len(self._sessions) > self._max_sessions:
                oldest_id = next(iter(self._sessions))
                del self._sessions[oldest_id]

            emp_no = session.user_emp_no
            if session.portal_session_id in self._user_sessions[emp_no]:
                self._user_sessions[emp_no].remove(session.portal_session_id)

            self._user_sessions[emp_no].insert(0, session.portal_session_id)

            if len(self._user_sessions[emp_no]) > self._max_user_sessions:
                self._user_sessions[emp_no] = self._user_sessions[emp_no][:self._max_user_sessions]

            logger.info(f"Saved session: {session.portal_session_id}")
            return session

    async def get_session(self, portal_session_id: str) -> Optional[PortalSession]:
        """Get portal session by ID"""
        return self._sessions.get(portal_session_id)

    async def list_user_sessions(
        self,
        emp_no: str,
        limit: int = 50,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[PortalSession]:
        """List user's sessions sorted by time with optional filters"""
        session_ids = self._user_sessions.get(emp_no, [])
        sessions = []

        for session_id in session_ids:
            session = self._sessions.get(session_id)
            if not session:
                continue
            if resource_id and session.resource_id != resource_id:
                continue
            if resource_type and session.resource_type != resource_type:
                continue
            if status and session.status != status:
                continue
            sessions.append(session)
            if len(sessions) >= limit:
                break

        logger.info(f"Listed {len(sessions)} sessions for user {emp_no}")
        return sessions

    async def delete_session(self, portal_session_id: str) -> None:
        """Delete a session"""
        async with self._lock:
            session = self._sessions.get(portal_session_id)
            if session:
                emp_no = session.user_emp_no
                if portal_session_id in self._user_sessions[emp_no]:
                    self._user_sessions[emp_no].remove(portal_session_id)

            if portal_session_id in self._sessions:
                del self._sessions[portal_session_id]

            logger.info(f"Deleted session: {portal_session_id}")

    # Launch operations
    async def save_launch(self, launch: LaunchRecord) -> LaunchRecord:
        """Save launch record to memory"""
        async with self._lock:
            self._launches[launch.launch_id] = launch

            if len(self._launches) > self._max_launches:
                oldest_id = next(iter(self._launches))
                del self._launches[oldest_id]

            emp_no = launch.user_emp_no
            if launch.launch_id in self._user_launches[emp_no]:
                self._user_launches[emp_no].remove(launch.launch_id)

            self._user_launches[emp_no].insert(0, launch.launch_id)

            if len(self._user_launches[emp_no]) > self._max_user_launches:
                self._user_launches[emp_no] = self._user_launches[emp_no][:self._max_user_launches]

            logger.info(f"Saved launch: {launch.launch_id}")
            return launch

    async def get_launch(self, launch_id: str) -> Optional[LaunchRecord]:
        """Get launch record by ID"""
        return self._launches.get(launch_id)

    async def list_user_launches(
        self,
        emp_no: str,
        limit: int = 50
    ) -> List[LaunchRecord]:
        """List user's launches sorted by time"""
        launch_ids = self._user_launches.get(emp_no, [])
        launches = []

        for launch_id in launch_ids[:limit]:
            launch = self._launches.get(launch_id)
            if launch:
                launches.append(launch)

        logger.info(f"Listed {len(launches)} launches for user {emp_no}")
        return launches

    # Binding operations
    async def save_binding(self, binding: SessionBinding) -> SessionBinding:
        """Save session binding to memory"""
        async with self._lock:
            self._bindings[binding.binding_id] = binding

            if len(self._bindings) > self._max_bindings:
                oldest_id = next(iter(self._bindings))
                del self._bindings[oldest_id]

            session_id = binding.portal_session_id
            if binding.binding_id in self._session_bindings[session_id]:
                self._session_bindings[session_id].remove(binding.binding_id)

            self._session_bindings[session_id].insert(0, binding.binding_id)

            logger.info(f"Saved binding: {binding.binding_id}")
            return binding

    async def get_binding(self, binding_id: str) -> Optional[SessionBinding]:
        """Get session binding by ID"""
        return self._bindings.get(binding_id)

    async def get_bindings_by_session(self, portal_session_id: str) -> List[SessionBinding]:
        """Get all bindings for a session"""
        binding_ids = self._session_bindings.get(portal_session_id, [])
        bindings = []
        for bid in binding_ids:
            binding = self._bindings.get(bid)
            if binding:
                bindings.append(binding)
        return bindings
    
    async def get_active_binding(self, portal_session_id: str) -> Optional[SessionBinding]:
        """Get active binding for a session"""
        bindings = await self.get_bindings_by_session(portal_session_id)
        for binding in bindings:
            if binding.binding_status == "active":
                return binding
        return None

    async def delete_binding(self, binding_id: str) -> None:
        """Delete a session binding"""
        async with self._lock:
            binding = self._bindings.get(binding_id)
            if binding:
                session_id = binding.portal_session_id
                if session_id in self._session_bindings:
                    if binding_id in self._session_bindings[session_id]:
                        self._session_bindings[session_id].remove(binding_id)
                del self._bindings[binding_id]
            logger.info(f"Deleted binding: {binding_id}")

    # Message operations - V2 with seq and upsert
    async def save_message(self, message: PortalMessage) -> PortalMessage:
        """Save portal message to memory (legacy, use upsert_message for new code)"""
        return await self.upsert_message(message)
    
    async def upsert_message(self, message: PortalMessage) -> PortalMessage:
        """
        Upsert message with deduplication support.
        If message has dedupe_key and a message with same key exists, update it.
        Otherwise, insert as new message.
        """
        async with self._lock:
            # Check deduplication
            if message.dedupe_key and message.dedupe_key in self._message_dedupe:
                existed_id = self._message_dedupe[message.dedupe_key]
                if existed_id in self._messages:
                    existed = self._messages[existed_id]
                    # Update fields
                    if message.text is not None:
                        existed.text = message.text
                    if message.status is not None:
                        existed.status = message.status
                    if message.source_provider is not None:
                        existed.source_provider = message.source_provider
                    if message.source_message_id is not None:
                        existed.source_message_id = message.source_message_id
                    existed.metadata.update(message.metadata)
                    logger.info(f"Updated existing message via dedupe: {existed_id}")
                    return existed
            
            # Assign sequence number if not set
            if not message.seq:
                message.seq = next(self._seq)
            
            # Store message
            self._messages[message.message_id] = message

            if len(self._messages) > self._max_messages:
                oldest_id = next(iter(self._messages))
                del self._messages[oldest_id]

            session_id = message.portal_session_id
            if message.message_id in self._session_messages[session_id]:
                self._session_messages[session_id].remove(message.message_id)

            self._session_messages[session_id].append(message.message_id)

            if len(self._session_messages[session_id]) > self._max_session_messages:
                # Keep most recent messages
                to_remove = self._session_messages[session_id][:-self._max_session_messages]
                self._session_messages[session_id] = self._session_messages[session_id][-self._max_session_messages:]
                # Also remove from dedupe index
                for mid in to_remove:
                    for key, val in list(self._message_dedupe.items()):
                        if val == mid:
                            del self._message_dedupe[key]

            # Update dedupe index
            if message.dedupe_key:
                self._message_dedupe[message.dedupe_key] = message.message_id

            logger.info(f"Saved message: {message.message_id} seq={message.seq}")
            return message

    async def get_message(self, message_id: str) -> Optional[PortalMessage]:
        """Get portal message by ID"""
        return self._messages.get(message_id)
    
    async def get_message_by_dedupe_key(self, dedupe_key: str) -> Optional[PortalMessage]:
        """Get message by dedupe key"""
        message_id = self._message_dedupe.get(dedupe_key)
        if message_id:
            return self._messages.get(message_id)
        return None

    async def list_session_messages(
        self,
        portal_session_id: str,
        limit: int = 500,
        offset: int = 0
    ) -> List[PortalMessage]:
        """List messages for a session in chronological order (by seq)"""
        message_ids = self._session_messages.get(portal_session_id, [])
        messages = []
        for mid in message_ids[offset:offset + limit]:
            msg = self._messages.get(mid)
            if msg:
                messages.append(msg)
        # Sort by seq to ensure order
        messages.sort(key=lambda m: m.seq)
        return messages
    
    async def update_message_status(
        self,
        message_id: str,
        status: str,
        text: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Optional[PortalMessage]:
        """Update message status and optionally text/metadata"""
        async with self._lock:
            msg = self._messages.get(message_id)
            if not msg:
                return None
            
            msg.status = status
            if text is not None:
                msg.text = text
            if metadata:
                msg.metadata.update(metadata)
            
            return msg

    async def delete_session_messages(self, portal_session_id: str) -> None:
        """Delete all messages for a session"""
        async with self._lock:
            message_ids = self._session_messages.pop(portal_session_id, [])
            for mid in message_ids:
                msg = self._messages.pop(mid, None)
                # Clean up dedupe index
                if msg and msg.dedupe_key:
                    self._message_dedupe.pop(msg.dedupe_key, None)
            logger.info(f"Deleted messages for session: {portal_session_id}")

    # Context operations
    async def save_context(self, context: ContextScope) -> ContextScope:
        """Save context scope to memory"""
        async with self._lock:
            self._contexts[context.context_id] = context

            if len(self._contexts) > self._max_contexts:
                oldest_id = next(iter(self._contexts))
                del self._contexts[oldest_id]

            key = context.scope_key
            if context.context_id in self._context_scopes[key]:
                self._context_scopes[key].remove(context.context_id)

            self._context_scopes[key].insert(0, context.context_id)

            logger.info(f"Saved context: {context.context_id}")
            return context

    async def get_context(self, context_id: str) -> Optional[ContextScope]:
        """Get context scope by ID"""
        return self._contexts.get(context_id)

    async def get_contexts_by_scope(
        self,
        scope_type: str,
        scope_key: str,
        limit: int = 10
    ) -> List[ContextScope]:
        """Get contexts by scope type and key"""
        context_ids = self._context_scopes.get(scope_key, [])
        contexts = []
        for cid in context_ids[:limit]:
            ctx = self._contexts.get(cid)
            if ctx and ctx.scope_type == scope_type:
                contexts.append(ctx)
        return contexts
    
    async def get_latest_context(
        self,
        scope_type: str,
        scope_key: str
    ) -> Optional[ContextScope]:
        """Get latest context for a scope"""
        contexts = await self.get_contexts_by_scope(scope_type, scope_key, limit=1)
        return contexts[0] if contexts else None

    async def delete_context(self, context_id: str) -> None:
        """Delete a context scope"""
        async with self._lock:
            context = self._contexts.get(context_id)
            if context:
                key = context.scope_key
                if key in self._context_scopes:
                    if context_id in self._context_scopes[key]:
                        self._context_scopes[key].remove(context_id)
                del self._contexts[context_id]
            logger.info(f"Deleted context: {context_id}")

    # Auth Session operations (V2)
    async def save_auth_session(self, session: AuthSession) -> AuthSession:
        """Save authentication session"""
        import time
        async with self._lock:
            self._auth_sessions[session.session_id] = session
            
            # Cleanup expired sessions if over limit
            if len(self._auth_sessions) > self._max_auth_sessions:
                now = int(time.time())
                expired = [
                    sid for sid, s in self._auth_sessions.items()
                    if s.expires_at < now
                ]
                for sid in expired:
                    del self._auth_sessions[sid]
            
            logger.info(f"Saved auth session: {session.session_id}")
            return session
    
    async def get_auth_session(self, session_id: str) -> Optional[AuthSession]:
        """Get authentication session by ID"""
        return self._auth_sessions.get(session_id)
    
    async def delete_auth_session(self, session_id: str) -> None:
        """Delete authentication session"""
        async with self._lock:
            if session_id in self._auth_sessions:
                del self._auth_sessions[session_id]
                logger.info(f"Deleted auth session: {session_id}")
    
    # OAuth State operations (V2)
    async def save_oauth_state(self, state: str, next_url: str) -> None:
        """Save OAuth state for CSRF protection"""
        import time
        async with self._lock:
            expires_at = int(time.time()) + 600  # 10 minutes
            self._oauth_states[state] = (next_url, expires_at)
            
            # Cleanup expired states
            now = int(time.time())
            expired = [
                s for s, (_, exp) in self._oauth_states.items()
                if exp < now
            ]
            for s in expired:
                del self._oauth_states[s]
    
    async def consume_oauth_state(self, state: str) -> Optional[str]:
        """Consume OAuth state and return next_url if valid"""
        import time
        async with self._lock:
            data = self._oauth_states.pop(state, None)
            if not data:
                return None
            next_url, expires_at = data
            if expires_at < int(time.time()):
                return None
            return next_url

    def clear_all(self):
        """Clear all data (for testing)"""
        self._sessions.clear()
        self._launches.clear()
        self._bindings.clear()
        self._messages.clear()
        self._contexts.clear()
        self._auth_sessions.clear()
        self._oauth_states.clear()
        self._user_sessions.clear()
        self._user_launches.clear()
        self._context_scopes.clear()
        self._session_messages.clear()
        self._session_bindings.clear()
        self._message_dedupe.clear()
        logger.info("Cleared all data from memory store")


# Global memory store instance
memory_store = MemoryStore()

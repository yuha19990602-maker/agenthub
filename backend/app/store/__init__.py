"""Storage module - Memory store is the primary implementation

Note: Redis support has been removed. This module now always exports
MemoryStore as the primary (and only) storage implementation.
"""

from .memory_store import MemoryStore, memory_store as store

__all__ = ['store', 'MemoryStore']

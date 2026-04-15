"""Compatibility shim for legacy imports.

The runtime now lives in memory/episodic.py.
"""

from memory.episodic import EpisodicMemory, episodic


def get_memory_system():
    return episodic

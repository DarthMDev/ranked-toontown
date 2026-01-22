"""
Base managers for all minigames.
Each minigame can have their own managers that inherit from these base classes.
"""

from .ModifierManagerAI import ModifierManagerAI
from .RoundManagerAI import RoundManagerAI

__all__ = [
    'ModifierManagerAI',
    'RoundManagerAI',
]

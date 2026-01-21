"""
PlayerManager - Handles client-side player/participant management and UI.
"""


class PlayerManager:
    """Manages client-side player-related functionality: participants, spectators, spawn points."""
    
    def __init__(self, game):
        self.game = game
        self.toonSpawnpointOrder = [i for i in range(16)]
        self.participantsPanel = None
        self.participantsList = None
        self.participantsPanelVisible = False
        self.participantsButton = None
    
    def setToonSpawnpointOrder(self, order):
        """Receive updated spawn order from server"""
        self.toonSpawnpointOrder = order[:]
        self.game.notify.info(f"Received spawn order update: {self.toonSpawnpointOrder}")

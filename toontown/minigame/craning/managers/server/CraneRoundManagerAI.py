"""
CraneRoundManagerAI - Handles best-of rounds, round wins, and spawn rotation for the crane game.
Inherits from the base RoundManagerAI and uses crane-specific ModifierFirstToXWins.
"""

from direct.task.TaskManagerGlobal import taskMgr
from toontown.minigame.craning import CraneGameGlobals
from toontown.minigame.utils.managers import RoundManagerAI


class CraneRoundManagerAI(RoundManagerAI):
    """
    Manages round progression, first-to-X-wins matches, and round wins for the crane game.
    Extends the base round manager with crane-specific functionality like spawn rotation.
    """
    
    def __init__(self, game):
        # Initialize base class - this sets up currentRound, roundWins, etc.
        RoundManagerAI.__init__(self, game)
        
        # Crane-specific properties
        self._bestOfValue = 1  # Internal storage, kept for backward compatibility
        self._inMultiRoundMatch = False
    
    def getWinsNeeded(self):
        """
        Get the number of wins needed from the First to X Wins modifier, or 1 if not set.
        Uses crane-specific ModifierFirstToXWins (MODIFIER_ENUM = 39).
        """
        if not hasattr(self.game, 'modifierManager'):
            return 1
        
        # Look for the First to X Wins modifier (crane-specific, enum 39)
        for modifier in self.game.modifierManager.modifiers:
            if modifier.MODIFIER_ENUM == CraneGameGlobals.ModifierFirstToXWins.MODIFIER_ENUM:
                return modifier.tier
        
        # Default to 1 if modifier not found
        return 1
    
    @property
    def bestOfValue(self):
        """Property to get wins needed (reads from modifier for backward compatibility)"""
        return self.getWinsNeeded()
    
    @bestOfValue.setter
    def bestOfValue(self, value):
        """Setter kept for backward compatibility but does nothing"""
        self._bestOfValue = value
    
    def setBestOf(self, value):
        """Deprecated: Best Of is now controlled by the First to X Wins modifier"""
        # This method is kept for backward compatibility but does nothing
        # The modifier system now handles this
        self.game.notify.warning("setBestOf is deprecated - use First to X Wins modifier instead")
    
    def d_setBestOf(self):
        """Send wins needed value to all clients (for backward compatibility)"""
        winsNeeded = self.getWinsNeeded()
        self.game.sendUpdate('setBestOf', [winsNeeded])
    
    def _startNextRound(self, task=None):
        """Start the next round in a best-of match"""
        # Rotate spawn positions for variety (delegated to PlayerManager)
        if hasattr(self.game, 'playerManager') and not self.game.playerManager.customSpawnOrderSet:
            self._rotateSpawnPositions()
        
        # Use proper FSM transitions like the RestartCraneRound magic word
        self.game.gameFSM.request("cleanup")
        self.game.gameFSM.request('prepare')
        
        # Note: round info will be sent in enterPrepare, no need to send here
        return task.done if task else None
    
    def _rotateSpawnPositions(self):
        """Rotate spawn positions for the next round"""
        # Get participating toons (not spectating)
        participatingToons = self.game.getParticipantIdsNotSpectating()
        numParticipants = len(participatingToons)
        
        if numParticipants <= 1:
            return  # No rotation needed for single player
        
        # Get spawn order from PlayerManager
        if not hasattr(self.game, 'playerManager'):
            return
        
        # Store the original spawn positions if this is the first rotation
        if not self.originalSpawnOrder:
            self.originalSpawnOrder = self.game.playerManager.toonSpawnpointOrder[:numParticipants]
        
        # Get the current spawn positions for participating players
        currentPositions = self.game.playerManager.toonSpawnpointOrder[:numParticipants]
        
        # Rotate positions: each player moves to the next position
        # Player at position 0 -> position 1, position 1 -> position 2, etc.
        # Last player wraps around to position 0
        rotatedPositions = [currentPositions[(i + 1) % numParticipants] for i in range(numParticipants)]
        
        # Update the spawn order with rotated positions
        for i in range(numParticipants):
            self.game.playerManager.toonSpawnpointOrder[i] = rotatedPositions[i]
        
        # Mark spawn order as customized so setupSpawnpoints() doesn't override it
        self.game.playerManager.customSpawnOrderSet = True
        
        self.game.playerManager.d_setToonSpawnpointOrder()
        self.game.notify.info(f"Rotated spawn positions for round {self.currentRound}: {self.game.playerManager.toonSpawnpointOrder[:numParticipants]}")
    
    def reset(self):
        """Reset round information for new games (not restarts)"""
        # Call base class reset
        RoundManagerAI.reset(self)
        
        # Reset crane-specific properties
        self._inMultiRoundMatch = False

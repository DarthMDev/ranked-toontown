"""
RoundManagerAI - Handles best-of rounds, round wins, and spawn rotation.
"""

from direct.task.TaskManagerGlobal import taskMgr
from toontown.minigame.craning import CraneGameGlobals


class RoundManagerAI:
    """Manages round progression, first-to-X-wins matches, and round wins."""
    
    def __init__(self, game):
        self.game = game
        self._bestOfValue = 1  # Internal storage, kept for backward compatibility
        self.currentRound = 1
        self.roundWins = {}  # Maps avId -> number of rounds won
        self.originalSpawnOrder = []  # Store original spawn order for rotation
        self._inMultiRoundMatch = False
    
    def getWinsNeeded(self):
        """Get the number of wins needed from the First to X Wins modifier, or 1 if not set"""
        if not hasattr(self.game, 'modifierManager'):
            return 1
        
        # Look for the First to X Wins modifier
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
    
    @property
    def winsNeeded(self):
        """Property to get wins needed (reads from modifier)"""
        return self.getWinsNeeded()
    
    def setBestOf(self, value):
        """Deprecated: Best Of is now controlled by the First to X Wins modifier"""
        # This method is kept for backward compatibility but does nothing
        # The modifier system now handles this
        self.game.notify.warning("setBestOf is deprecated - use First to X Wins modifier instead")
    
    def d_setBestOf(self):
        """Send wins needed value to all clients (for backward compatibility)"""
        winsNeeded = self.getWinsNeeded()
        self.game.sendUpdate('setBestOf', [winsNeeded])
    
    def d_setRoundInfo(self):
        """Send round information to all clients"""
        # Convert roundWins dict to list format for transmission
        roundWinsList = []
        for avId in self.game.avIdList:
            roundWinsList.append(self.roundWins.get(avId, 0))
        self.game.sendUpdate('setRoundInfo', [self.currentRound, roundWinsList])
    
    def nextRound(self):
        """Handle transition to next round in first-to-X-wins matches"""
        winsNeeded = self.getWinsNeeded()
        if winsNeeded <= 1:
            return  # Single round match
        
        self.currentRound += 1
        self._inMultiRoundMatch = True  # Flag to indicate we're in a multi-round match
        
        # Start the next round after a brief delay
        taskMgr.doMethodLater(0.5, self._startNextRound, self.game.uniqueName("startNextRound"))
    
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
    
    def recordRoundWin(self, victorId):
        """Record a round win for a player"""
        winsNeeded = self.getWinsNeeded()
        if winsNeeded <= 1:
            return  # Single round match
        
        self.roundWins[victorId] = self.roundWins.get(victorId, 0) + 1
        self.d_setRoundInfo()
    
    def isMatchComplete(self, victorId):
        """Check if the match is complete (player has enough wins)"""
        winsNeeded = self.getWinsNeeded()
        if winsNeeded <= 1:
            return True  # Single round match is always "complete"
        
        return self.roundWins.get(victorId, 0) >= winsNeeded
    
    def getWinners(self):
        """Find who has most round wins"""
        # Find who has most round wins.
        most = -1
        for avId, wins in self.roundWins.items():
            if wins > most:
                most = wins
        
        # Filter who has most round wins
        winners = []
        for avId, wins in self.roundWins.items():
            if wins == most:
                winners.append(avId)
        
        return winners
    
    def reset(self):
        """Reset round information for new games (not restarts)"""
        self.roundWins = {}
        self.originalSpawnOrder = []
        self._inMultiRoundMatch = False
        self.currentRound = 1

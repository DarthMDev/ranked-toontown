"""
RoundManagerAI - Base round manager for all minigames.
Each minigame can have their own round manager that inherits from this.
"""

from direct.task.TaskManagerGlobal import taskMgr


class RoundManagerAI:
    """Base class for managing rounds in any minigame."""
    
    def __init__(self, game):
        self.game = game
        self.currentRound = 1
        self.roundWins = {}  # Maps avId -> number of rounds won
        self.originalSpawnOrder = []  # Store original spawn order for rotation (if applicable)
        self._inMultiRoundMatch = False
    
    def getWinsNeeded(self):
        """
        Get the number of wins needed from the First to X Wins modifier, or 1 if not set.
        First to X Wins modifier uses MODIFIER_ENUM = 0 in all minigames.
        """
        if not hasattr(self.game, 'modifierManager'):
            return 1
        
        # Look for the First to X Wins modifier (MODIFIER_ENUM = 0 in all minigames)
        for modifier in self.game.modifierManager.modifiers:
            if modifier.MODIFIER_ENUM == 0:  # First to X Wins is always enum 0
                return modifier.tier
        
        # Default to 1 if modifier not found
        return 1
    
    @property
    def winsNeeded(self):
        """Property to get wins needed (reads from modifier)"""
        return self.getWinsNeeded()
    
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
        # For minigames that support it, we can rotate spawn positions
        # This is a no-op by default, but can be overridden by specific minigames
        
        # Use proper FSM transitions if the game has a gameFSM
        if hasattr(self.game, 'gameFSM'):
            self.game.gameFSM.request("cleanup")
            self.game.gameFSM.request('prepare')
        else:
            # Fallback: just restart the game
            if hasattr(self.game, 'setGameReady'):
                self.game.setGameReady()
        
        # Note: round info will be sent in enterPrepare or equivalent, no need to send here
        return task.done if task else None
    
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

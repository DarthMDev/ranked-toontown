"""
RoundManager - Handles client-side round management and UI.
"""

from toontown.minigame.craning import CraneGameGlobals


class RoundManager:
    """Manages client-side round progression, first-to-X-wins matches, and UI."""
    
    def __init__(self, game):
        self.game = game
        self.bestOfValue = 1  # Kept for backward compatibility, now reads from modifier
        self.currentRound = 1
        self.roundWins = {}  # Maps avId -> number of rounds won
    
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
    def winsNeeded(self):
        """Property to get wins needed (reads from modifier)"""
        return self.getWinsNeeded()
    
    def setBestOf(self, value):
        """Deprecated: Best Of is now controlled by the First to X Wins modifier"""
        # This method is kept for backward compatibility but does nothing
        # The modifier system now handles this
        self.bestOfValue = value
    
    def setRoundInfo(self, currentRound, roundWins):
        """Receive round information from server"""
        self.currentRound = currentRound
        
        # Convert roundWins list back to dict using avIdList
        self.roundWins = {}
        for i, avId in enumerate(self.game.avIdList):
            if i < len(roundWins):
                self.roundWins[avId] = roundWins[i]
        
        # Update scoreboard with round information
        if hasattr(self.game, 'scoreboard') and self.game.scoreboard:
            winsNeeded = self.getWinsNeeded()
            self.game.scoreboard.setRoundInfo(currentRound, roundWins, winsNeeded, self.game.avIdList)

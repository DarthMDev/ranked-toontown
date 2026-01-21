"""
RoundManager - Handles client-side round management and UI.
"""


class RoundManager:
    """Manages client-side round progression, best-of matches, and UI."""
    
    def __init__(self, game):
        self.game = game
        self.bestOfValue = 1  # Default to Best of 1
        self.currentRound = 1
        self.roundWins = {}  # Maps avId -> number of rounds won
        # Note: bestOfButton is kept on game for UI access
    
    def setBestOf(self, value):
        """Receive best-of setting from server"""
        self.bestOfValue = value
        # Update UI button if it exists (button is on game instance, not manager)
        if hasattr(self.game, 'bestOfButton') and self.game.bestOfButton:
            self.game.bestOfButton['text'] = f'Best of {self.bestOfValue}'
        # Also update via GameButtonsUI if available
        if hasattr(self.game, 'gameButtonsUI') and self.game.gameButtonsUI.bestOfButton:
            self.game.gameButtonsUI.updateBestOfButton(value)
        self.game.notify.info(f"Best of value set to: {self.bestOfValue}")
    
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
            self.game.scoreboard.setRoundInfo(currentRound, roundWins, self.bestOfValue, self.game.avIdList)

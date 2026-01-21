"""
ComboManagerAI - Handles combo tracking and bonuses.
"""

from toontown.minigame.craning.boss.CashbotBossComboTracker import CashbotBossComboTracker


class ComboManagerAI:
    """Manages combo tracking for all players."""
    
    def __init__(self, game):
        self.game = game
        self.comboTrackers = {}
    
    def initializeComboTrackers(self):
        """Initialize combo trackers for all participants"""
        self.cleanupComboTrackers()
        for avId in self.game.getParticipants():
            if avId in self.game.air.doId2do:
                self.comboTrackers[avId] = CashbotBossComboTracker(self.game, avId)
                # Update combo display when tracker is created
                self.d_updateCombo(avId, 0)
    
    def incrementCombo(self, avId, amount):
        """Increment combo for a player"""
        tracker = self.comboTrackers.get(avId)
        if not tracker:
            return
        
        tracker.incrementCombo(amount)
    
    def resetCombo(self, avId):
        """Reset combo for a player"""
        tracker = self.comboTrackers.get(avId)
        if not tracker:
            return
        
        tracker.resetCombo()
    
    def getComboLength(self, avId):
        """Get current combo length for a player"""
        tracker = self.comboTrackers.get(avId)
        if not tracker:
            return 0
        
        return tracker.combo
    
    def getComboAmount(self, avId):
        """Get current combo point bonus for a player"""
        tracker = self.comboTrackers.get(avId)
        if not tracker:
            return 0
        
        return tracker.pointBonus
    
    def cleanupComboTrackers(self):
        """Clean up all combo trackers"""
        for comboTracker in self.comboTrackers.values():
            comboTracker.cleanup()
        self.comboTrackers.clear()
    
    def finishAllCombos(self):
        """Finish all active combos (called when exiting play state)"""
        for comboTracker in self.comboTrackers.values():
            comboTracker.finishCombo()
    
    def d_updateCombo(self, avId, comboLength):
        """Send combo update to clients"""
        self.game.sendUpdate('updateCombo', [avId, comboLength])

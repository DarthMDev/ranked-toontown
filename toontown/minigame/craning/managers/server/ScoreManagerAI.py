"""
ScoreManagerAI - Handles scoring, winner tracking, and bonuses.
"""

import random
from toontown.minigame.craning import CraneGameGlobals


class ScoreManagerAI:
    """Manages scoring, winner tracking, and bonus calculations."""
    
    def __init__(self, game):
        self.game = game
        self.currentWinners: list[int] = []  # Keeps track of who's in the lead so we know when to trigger overtime.
    
    def addScore(self, avId: int, amount: int, reason: CraneGameGlobals.ScoreReason = CraneGameGlobals.ScoreReason.DEFAULT):
        """Add score to a player"""
        if amount == 0:
            return
        
        # Get current round from RoundManager if available
        currentRound = 1
        if hasattr(self.game, 'roundManager'):
            currentRound = self.game.roundManager.currentRound
        
        self.game.getScoringContext().get_round(currentRound).add_score(avId, amount)
        self.d_addScore(avId, amount, reason)
        
        # Update current winners so we can check for position overtakes (where we should enable overtime)
        self._updateCurrentWinners()
        
        # If we are in overtime, check the overtime state. There is a chance this toon overtook 1st place when
        # everyone is dead and should be declared winner.
        if hasattr(self.game, 'overtimeManager') and self.game.overtimeManager.currentlyInOvertime:
            if reason != CraneGameGlobals.ScoreReason.COIN_FLIP:
                self.game.overtimeManager.checkOvertimeState()
        
        # Check if we can award an uber bonus for being low laff
        self._awardUberBonusIfEligible(avId, amount, reason)
    
    def _updateCurrentWinners(self):
        """Update the list of current winners"""
        newLeaders = self.getHighestScorers()
        
        # Perform a quick check for overtime enabling.
        # This check basically is making sure that we are the clock is running low and there is a new leader to check.
        if (self.game.ruleset.TIMER_MODE and 
            hasattr(self.game, 'overtimeManager') and 
            not self.game.overtimeManager.overtimeWillHappen and 
            len(newLeaders) > 0 and 
            self.game._calculateTimeToSend() < self.game.OVERTIME_OVERTAKE_ACTIVATION_THRESHOLD):
            
            # Is there a tie (or was there a tie)?
            tie = len(newLeaders) > 1 or len(self.currentWinners) > 1
            # Is the new leader not the previous?
            overtake = len(self.currentWinners) > 0 and newLeaders[0] != self.currentWinners[0]
            if tie or overtake:
                self.game.overtimeManager.enableOvertime()
        
        # Update who is currently winning
        self.currentWinners = newLeaders
    
    def _awardUberBonusIfEligible(self, avId, amount, reason):
        """Award uber bonus if player is low on laff"""
        if not self.game.ruleset.WANT_LOW_LAFF_BONUS:
            return
        
        if reason.ignore_uber_bonus():
            return
        
        toon = self.game.air.getDo(avId)
        if toon is None:
            return
        
        if toon.getHp() > self.game.ruleset.LOW_LAFF_BONUS_THRESHOLD:
            return
        
        uberAmount = int(self.game.ruleset.LOW_LAFF_BONUS * amount)
        if uberAmount == 0:
            return
        
        # Add additional score if uber bonus is on.
        self.addScore(avId, uberAmount, reason=CraneGameGlobals.ScoreReason.LOW_LAFF)
    
    def getHighestScorers(self):
        """
        Gets a list of who is currently in the lead.
        If the list is empty, we have no players playing.
        If the list has one person, someone is in the lead.
        If the last has multiple people, they are tied for 1st place.
        """
        # Get current round from RoundManager if available
        currentRound = 1
        if hasattr(self.game, 'roundManager'):
            currentRound = self.game.roundManager.currentRound
        
        all_scores = self.game.getScoringContext().get_round(currentRound).get_all_scores()
        
        # Are there no players?
        if len(all_scores) <= 0:
            return []
        
        # Create a reversed dict where we map score to the players who have that score.
        results = {}
        highestScore = -999_999
        for player, score in all_scores.items():
            toonsWithScore = results.get(score, [])
            toonsWithScore.append(player)
            results[score] = toonsWithScore
            highestScore = max(highestScore, score)
        
        # Query the players with the highest score.
        return results[highestScore]
    
    def d_addScore(self, avId: int, amount: int, reason: CraneGameGlobals.ScoreReason = CraneGameGlobals.ScoreReason.DEFAULT):
        """Send score update to clients"""
        self.game.sendUpdate('addScore', [avId, amount, reason.to_astron()])

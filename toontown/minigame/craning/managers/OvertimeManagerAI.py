"""
OvertimeManagerAI - Handles overtime logic and state management.
"""

import random
from direct.task.TaskManagerGlobal import taskMgr
from toontown.minigame.craning import CraneGameGlobals


class OvertimeManagerAI:
    """Manages overtime mode: enabling, entering, and checking state."""
    
    def __init__(self, game):
        self.game = game
        self.overtimeWillHappen = False  # Setting this to True will cause the CFO to enter "overtime" mode when time runs out.
        self.currentlyInOvertime = False  # Only true when the game is currently in overtime.
    
    def enableOvertime(self):
        """
        Marks this game in progress to enter overtime when time is up.
        """
        self.overtimeWillHappen = True
        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_ENABLE)
    
    def enterOvertimeMode(self):
        """
        Adjust the state of the boss to force this game to find a winner with more extreme measures.
        """
        self.currentlyInOvertime = True
        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_START)
        
        modifiers = [
            CraneGameGlobals.ModifierGoonCapIncreaser(tier=1),
            CraneGameGlobals.ModifierNoSafeHelmet(tier=1),
            CraneGameGlobals.ModifierTreasureHealDecreaser(tier=2),
            CraneGameGlobals.ModifierLaffDrain(tier=3),
            CraneGameGlobals.ModifierNoRevives(tier=1),
        ]
        
        if hasattr(self.game, 'modifierManager'):
            self.game.modifierManager.applyModifiers(modifiers, updateClient=True)
        
        # Some modifiers don't exactly support us adding them mid-round based on state. Perform that logic here.
        self.game.getBoss().stopHelmets()
        
        # Start laff drain if available
        if hasattr(self.game, 'startDrainingLaff'):
            self.game.startDrainingLaff(self.game.ruleset.LAFF_DRAIN_FREQUENCY)
        
        # Cancel revive tasks
        self._cancelReviveTasks()
        
        if hasattr(self.game, 'modifierManager'):
            self.game.modifierManager.d_setModifiers()
    
    def checkOvertimeState(self):
        """
        Analyze the state of the game right now.
        We can only end overtime if it is impossible for someone else to win.
        """
        aliveToons = []
        for toon in self.game.getParticipantsNotSpectating():
            if toon.getHp() > 0:
                aliveToons.append(toon)
        
        allToonsAreDead = len(aliveToons) == 0
        
        # Get current winners from ScoreManager
        currentWinners = []
        if hasattr(self.game, 'scoreManager'):
            currentWinners = self.game.scoreManager.currentWinners
        
        winnerIsAlreadyDetermined = (
            len(aliveToons) == 1 and 
            len(currentWinners) == 1 and 
            currentWinners[0] == aliveToons[0].getDoId()
        )
        
        # Absolute freak incident check. Are we STILL tied for first place when everyone died?
        # If so, assign one lucky person the win.
        # In the future, we can probably determine this another way, but right now I am lazy.
        if allToonsAreDead and len(currentWinners) > 1:
            if hasattr(self.game, 'scoreManager'):
                self.game.scoreManager.addScore(
                    random.choice(currentWinners), 
                    1, 
                    CraneGameGlobals.ScoreReason.COIN_FLIP
                )
        
        # End the game if everyone died or if it is literally impossible for the winner to be overtaken.
        if allToonsAreDead or winnerIsAlreadyDetermined:
            self.game.toonsWon = False
            self.game.gameFSM.request('victory')
            return
    
    def _cancelReviveTasks(self):
        """Cleanup function to cancel any impending revives."""
        for toonId in self.game.getParticipants():
            taskMgr.remove(self.game.uniqueName(f"reviveToon-{toonId}"))
    
    def d_setOvertime(self, flag):
        """Send overtime flag to clients"""
        self.game.sendUpdate('setOvertime', [flag])
    
    def reset(self):
        """Reset overtime state (called when exiting play)"""
        self.currentlyInOvertime = False
        self.overtimeWillHappen = False
        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_DISABLE)

"""
GoonManagerAI - Handles goon spawning, caching, and management.
"""

import math
import random
from direct.task.TaskManagerGlobal import taskMgr
from toontown.minigame.craning.objects.DistributedCashbotGoonAI import DistributedCashbotGoonAI
from toontown.minigame.craning.objects.DistributedCashbotSideCraneAI import DistributedCashbotSideCraneAI
from toontown.minigame.craning import CraneGameGlobals


class GoonManagerAI:
    """Manages goon spawning, caching, and lifecycle."""
    
    def __init__(self, game):
        self.game = game
        self.goonCache = ("Recent emerging side", 0)  # Cache for goon spawn bad luck protection
        self.goonMinScale = 0.8
        self.goonMaxScale = 2.4
    
    def getMaxGoons(self):
        """Get maximum number of goons based on progress"""
        return self.game.progressValue(
            self.game.ruleset.MAX_GOON_AMOUNT_START, 
            self.game.ruleset.MAX_GOON_AMOUNT_END
        )
    
    def _chooseGoonEmergeSide(self) -> str:
        """
        Determines the next side for a goon to emerge from.
        To limit the amount of RNG present, we prevent goons from spawning from the same side over and over in a row.
        """
        # Default goon spawning logic.
        # Is it okay to pick a random side?
        if self.goonCache[1] < 2:
            return random.choice(['EmergeA', 'EmergeB'])
        
        # There's too many goons coming from a certain side. Pick the opposite one.
        if self.goonCache[0] == 'EmergeA':
            return 'EmergeB'
        return 'EmergeA'
    
    def _isPositionClear(self, x, y, minDistance=5):
        """Check if a position is clear of safes and cranes"""
        # Check distance to all safes
        for safe in self.game.safes:
            safePos = safe.getPos()
            if abs(safePos[0] - x) < minDistance and abs(safePos[1] - y) < minDistance:
                return False
                
        # Check distance to all cranes
        for crane in self.game.cranes:
            # Get crane position based on its type and index
            if isinstance(crane, DistributedCashbotSideCraneAI):
                poshpr = CraneGameGlobals.SIDE_CRANE_POSHPR[
                    crane.index - len(CraneGameGlobals.NORMAL_CRANE_POSHPR)
                ]
            else:
                poshpr = CraneGameGlobals.NORMAL_CRANE_POSHPR[crane.index]
            cranePos = (poshpr[0], poshpr[1], poshpr[2])
            if abs(cranePos[0] - x) < minDistance and abs(cranePos[1] - y) < minDistance:
                return False
                
        return True
    
    def makeGoon(self, side=None, forceNormalSpawn=False, fallingChance=0.5):
        """
        Create and spawn a goon. Picks a side for a goon to generate on if not specified.
        """
        # Picks a side for a goon to generate on if not specified
        if side is None:
            side = self._chooseGoonEmergeSide()
        
        # Should this goon fall if we are in overtime?
        falling = random.random() < fallingChance
        
        # Long logic process to determine whether a goon should be made and what type.
        # If we are at max goon size, do not make a new goon
        if len(self.game.goons) >= self.getMaxGoons():
            return
        
        # Check overtime state from OvertimeManager if available
        currentlyInOvertime = False
        if hasattr(self.game, 'overtimeManager'):
            currentlyInOvertime = self.game.overtimeManager.currentlyInOvertime
        
        # Only 2 current cases where goons should spawn when the CFO is stunned
        if self.game.boss.isStunned():
            # If we are in OT and we roll a falling goon and it's not a forced normal spawn
            if currentlyInOvertime and falling and not forceNormalSpawn:
                pass
            else:
                return
        
        # From here on out, a goon is guaranteed to be created on a specific side of the room
        self._updateGoonCache(side)
        
        # Create and generate the goon
        goon = DistributedCashbotGoonAI(self.game.air, self.game)
        goon.generateWithRequired(self.game.zoneId)
        self.game.goons.append(goon)
        
        # Attributes for desperation mode goons
        goon_stun_time = 6
        goon_velocity = 7
        goon_hfov = 90
        goon_attack_radius = 17
        goon_strength = self.game.ruleset.MAX_GOON_DAMAGE + 10
        goon_scale = self.goonMaxScale + .1
        
        # If the battle isn't in desperation yet override the values to normal values
        if self.game.getBattleThreeTime() <= 1.0:
            goon_stun_time = self.game.progressValue(30, 8)
            goon_velocity = self.game.progressRandomValue(3, 7)
            goon_hfov = self.game.progressRandomValue(70, 80)
            goon_attack_radius = self.game.progressRandomValue(6, 15)
            goon_strength = int(self.game.progressRandomValue(
                self.game.ruleset.MIN_GOON_DAMAGE, 
                self.game.ruleset.MAX_GOON_DAMAGE
            ))
            goon_scale = self.game.progressRandomValue(self.goonMinScale, self.goonMaxScale)
        
        # Apply multipliers if necessary
        goon_velocity *= self.game.ruleset.GOON_SPEED_MULTIPLIER
        
        # Apply attributes to the goon
        goon.STUN_TIME = goon_stun_time
        goon.b_setupGoon(
            velocity=goon_velocity, 
            hFov=goon_hfov, 
            attackRadius=goon_attack_radius,
            strength=goon_strength, 
            scale=goon_scale
        )
        
        # Properly set up the goon in "Falling" state if necessary
        if currentlyInOvertime and falling:
            self._makeFallingGoon(goon, side)
        else:
            goon.request(side)
    
    def _updateGoonCache(self, side):
        """Update the goon cache to track spawn side"""
        if side == self.goonCache[0]:
            self.goonCache = (side, self.goonCache[1] + 1)
        else:
            self.goonCache = (side, 1)
    
    def _makeFallingGoon(self, goon, side):
        """Create a falling goon for overtime mode"""
        bossPos = self.game.boss.getPos()
        
        # Keep trying positions until we find a clear one
        # Took out prevent infinite loops code because 8 safes give a maximum of 200pi area covered
        # Half of our allotted area for falling goons is 250 pi. Chance of 21+ iterations is 1.15%. 41+ is 0.013%.
        while True:
            # Random position 15-20 units away from CFO on correct side
            radius = random.uniform(20, 30)
            theta = random.uniform(-math.pi, math.pi)
            xPos = bossPos[0] + radius * math.cos(theta)
            
            # Bad luck protection position calculation
            if side == "EmergeA":
                yPos = bossPos[1] + abs(radius * math.sin(theta))
            else:
                yPos = bossPos[1] - abs(radius * math.sin(theta))
            
            # Check if position is clear
            if self._isPositionClear(xPos, yPos):
                randomH = random.uniform(0, 360)  # Random heading between 0-360 degrees
                goon.b_setPosHpr(xPos, yPos, 40, randomH, 0, 0)
                goon.request('Falling')
                return
    
    def waitForNextGoon(self, delayTime):
        """Schedule the next goon spawn"""
        taskName = self.game.uniqueName('NextGoon')
        taskMgr.remove(taskName)
        if hasattr(self.game, '_allTaskNames'):
            self.game._allTaskNames.add(taskName)
        taskMgr.doMethodLater(delayTime, self.doNextGoon, taskName)
    
    def stopGoons(self):
        """Stop spawning goons"""
        taskName = self.game.uniqueName('NextGoon')
        taskMgr.remove(taskName)
    
    def doNextGoon(self, task):
        """Callback to spawn the next goon"""
        self.makeGoon()
        # How long to wait for the next goon?
        delayTime = self.game.progressValue(10, 2)
        self.waitForNextGoon(delayTime)
        return task.done
    
    def resetGoonCache(self):
        """Reset the goon cache (called at start of round)"""
        self.goonCache = (None, 0)

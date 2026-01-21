"""
Base AI class for drone goons with common functionality.
Specialized drone types inherit from this class.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.minigame.utils.objects import DistributedGoonAI
from toontown.minigame.craning import CraneGameGlobals


class DistributedCashbotDroneBaseAI(DistributedGoonAI.DistributedGoonAI):
    """
    Base AI class for all drone goons. Contains common functionality like:
    - Owner and target management
    - Finding opponents/boss
    - Vanishing and cleanup
    
    Subclasses must implement:
    - getDroneType() - returns the CraneGameGlobals.DroneType enum
    - startBehavior() - implements the type-specific AI behavior
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotDroneBaseAI')
    
    def __init__(self, air, boss, ownerId):
        DistributedGoonAI.DistributedGoonAI.__init__(self, air, 0)
        self.boss = boss
        self.ownerId = ownerId
        self.targetId = None
        self.deployTime = globalClock.getFrameTime()
        self.flyTask = None
        self.hitToons = set()  # Track toons hit to prevent duplicate damage
        # Initialize pos to None - will be set by b_setPosition
        if not hasattr(self, 'pos'):
            self.pos = None
    
    def getDroneType(self):
        """
        Override in subclass to return the drone type enum.
        Returns: CraneGameGlobals.DroneType
        """
        raise NotImplementedError("Subclass must implement getDroneType()")
    
    def startBehavior(self):
        """
        Override in subclass to implement type-specific AI behavior.
        Called after drone is generated and ready to start its action.
        """
        raise NotImplementedError("Subclass must implement startBehavior()")
    
    def setOwnerId(self, ownerId):
        """Set the owner ID (toon who deployed this drone)."""
        self.ownerId = ownerId
        self.d_setOwnerId(ownerId)
    
    def d_setOwnerId(self, ownerId):
        """Send owner ID to clients."""
        self.sendUpdate('setOwnerId', [ownerId])
    
    def setTargetId(self, targetId):
        """Set the target ID (toon being targeted)."""
        self.targetId = targetId
        self.d_setTargetId(targetId)
    
    def d_setTargetId(self, targetId):
        """Send target ID to clients."""
        self.sendUpdate('setTargetId', [targetId if targetId else 0])
    
    def generate(self):
        DistributedGoonAI.DistributedGoonAI.generate(self)
        self.d_setOwnerId(self.ownerId)
        self.d_setDroneType(self.getDroneType().value)
        
    def setDroneType(self, droneType):
        """Set the drone type (received from AI)."""
        if isinstance(droneType, int):
            droneTypeEnum = CraneGameGlobals.DroneType(droneType)
        else:
            droneTypeEnum = droneType
        self.d_setDroneType(droneTypeEnum.value)
    
    def d_setDroneType(self, droneTypeValue):
        """Send drone type to clients."""
        self.sendUpdate('setDroneType', [droneTypeValue])
        
    def announceGenerate(self):
        DistributedGoonAI.DistributedGoonAI.announceGenerate(self)
        
        # Start the type-specific behavior
        self.startBehavior()
    
    def findNearestOpponent(self):
        """Find the nearest opponent toon ID (cannot be the owner/deployer)."""
        if not self.boss:
            return None
        
        nearestId = None
        nearestDist = float('inf')
        
        # Get owner position for distance calculation
        owner = self.air.doId2do.get(self.ownerId)
        if not owner:
            return None
        ownerPos = owner.getPos()
        
        # Get all toons in the battle
        if hasattr(self.boss, 'game') and self.boss.game:
            involvedToons = self.boss.game.getParticipantIdsNotSpectating()
        elif hasattr(self.boss, 'involvedToons'):
            involvedToons = self.boss.involvedToons
        else:
            return None
        
        for toonId in involvedToons:
            # Cannot target the owner/deployer
            if toonId == self.ownerId:
                continue
            toon = self.air.doId2do.get(toonId)
            if toon and hasattr(toon, 'getPos'):
                targetPos = toon.getPos()
                dist = (targetPos - ownerPos).length()
                if dist < nearestDist:
                    nearestDist = dist
                    nearestId = toonId
        
        return nearestId
    
    def findCFO(self):
        """Find the CFO boss for explodey drone targeting."""
        return self.boss if self.boss else None
    
    def vanishWithPoof(self, task=None):
        """Vanish the drone with a poof effect."""
        # Prevent double deletion
        if self.isDeleted():
            if task:
                return Task.done
            return
        
        self.sendUpdate('vanishWithPoof', [])
        self.requestDelete()
        if task:
            return Task.done
    
    def destroyDrone(self):
        """Destroy the drone (called when hit by safe)."""
        # Prevent duplicate destruction
        if hasattr(self, '_isDestroyed') and self._isDestroyed:
            return
        if self.isDeleted():
            return
        self._isDestroyed = True
        
        self.sendUpdate('destroyDrone', [])
        self.requestDelete()
    
    def delete(self):
        """Clean up when deleted."""
        # Clean up tasks
        if self.flyTask:
            taskMgr.remove(self.flyTask)
            self.flyTask = None
        
        # Call parent delete
        DistributedGoonAI.DistributedGoonAI.delete(self)


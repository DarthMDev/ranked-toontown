"""
Heal Drone AI - Heals the deployer over time.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.minigame.craning import CraneGameGlobals
from toontown.coghq.DistributedGoonDroneBaseAI import DistributedGoonDroneBaseAI


class DistributedGoonDroneHealAI(DistributedGoonDroneBaseAI):
    """
    Heal drone AI that:
    1. Hovers above owner
    2. After 1 second, starts healing over time (+10 laff twice per second)
    3. Continues healing until owner is at full laff or drone is destroyed
    4. Vanishes after healing completes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneHealAI')
    
    def __init__(self, air, boss, ownerId):
        DistributedGoonDroneBaseAI.__init__(self, air, boss, ownerId)
        self.healingActive = False
        self.totalHealAmount = 0
        self.healTicksRemaining = 5  # Total of 5 ticks = 50 laff
    
    def getDroneType(self):
        return CraneGameGlobals.DroneType.HEAL
    
    def startBehavior(self):
        """Initialize heal drone behavior."""
        # Heal drone doesn't need a target, just heals the owner
        # Wait 1 second then start healing over time
        taskMgr.doMethodLater(1.0, self.startHealing, self.uniqueName('startHealing'))
    
    def startHealing(self, task):
        """Start the over-time healing process."""
        owner = self.air.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return Task.done
        
        # Send visual effect to client to start particles
        self.sendUpdate('performVisualEffect', [CraneGameGlobals.DroneType.HEAL.value])

        # Start healing over time: +10 laff per second, up to 50 laff total (5 ticks)
        self.healingActive = True
        self.healTicksRemaining = 5  # Total of 5 ticks = 50 laff
        # Schedule first heal tick immediately (1 second after deployment)
        taskMgr.doMethodLater(0.0, self.performHealTick, self.uniqueName('healTick'))
        
        return Task.done
    
    def performHealTick(self, task):
        """Perform one tick of healing (+10 laff)."""
        if not self.healingActive:
            return Task.done
        
        owner = self.air.doId2do.get(self.ownerId)
        if not owner:
            self.stopHealing()
            self.vanishWithPoof()
            return Task.done
        
        # Get current HP and max HP
        currentHp = owner.getHp()
        maxHp = owner.getMaxHp()
        
        # Check if already at full health or no more ticks remaining
        if currentHp >= maxHp or self.healTicksRemaining <= 0:
            self.stopHealing()
            # Vanish after a short delay
            taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishAfterHeal'))
            return Task.done
        
        # Heal +10 laff (capped at max)
        healAmount = 10
        newHp = min(currentHp + healAmount, maxHp)
        owner.b_setHp(newHp)
        self.totalHealAmount += (newHp - currentHp)
        self.healTicksRemaining -= 1
        
        # Schedule next heal tick (1 second = once per second)
        if self.healTicksRemaining > 0:
            taskMgr.doMethodLater(1.0, self.performHealTick, self.uniqueName('healTick'))
        else:
            # All ticks done, vanish after a short delay
            self.stopHealing()
            taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishAfterHeal'))
        
        return Task.done
    
    def stopHealing(self):
        """Stop the healing process."""
        self.healingActive = False
        taskMgr.remove(self.uniqueName('healTick'))
    
    def delete(self):
        """Clean up heal-specific resources."""
        self.stopHealing()
        taskMgr.remove(self.uniqueName('startHealing'))
        taskMgr.remove(self.uniqueName('vanishAfterHeal'))
        
        DistributedGoonDroneBaseAI.delete(self)


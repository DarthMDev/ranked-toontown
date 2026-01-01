"""
Heal Drone AI - Heals the deployer to full laff.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBaseAI import DistributedGoonDroneBaseAI


class DistributedGoonDroneHealAI(DistributedGoonDroneBaseAI):
    """
    Heal drone AI that:
    1. Hovers above owner
    2. After 2 seconds, heals owner to full laff
    3. Vanishes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneHealAI')
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.HEAL
    
    def startBehavior(self):
        """Initialize heal drone behavior."""
        # Heal drone doesn't need a target, just heals the owner
        # Wait 2 seconds then heal
        taskMgr.doMethodLater(2.0, self.performHeal, self.uniqueName('performHeal'))
    
    def performHeal(self, task):
        """Heal the deployer to full laff."""
        owner = self.air.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return Task.done
        
        # Send heal request to client for visual feedback
        self.sendUpdate('performVisualEffect', [CraneLeagueGlobals.DroneType.HEAL.value])
        
        # Heal to full on AI side
        maxHp = owner.getMaxHp()
        owner.b_setHp(maxHp)
        
        # Vanish after healing
        taskMgr.doMethodLater(1.0, self.vanishWithPoof, self.uniqueName('vanishAfterHeal'))
        return Task.done
    
    def delete(self):
        """Clean up heal-specific resources."""
        taskMgr.remove(self.uniqueName('performHeal'))
        taskMgr.remove(self.uniqueName('vanishAfterHeal'))
        
        DistributedGoonDroneBaseAI.delete(self)


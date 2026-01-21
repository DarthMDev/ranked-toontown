"""
Laser Drone AI - Finds nearest opponent and shoots lasers at them.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.minigame.craning import CraneGameGlobals
from toontown.minigame.craning.objects.DistributedCashbotDroneBaseAI import DistributedCashbotDroneBaseAI


class DistributedCashbotDroneLaserAI(DistributedCashbotDroneBaseAI):
    """
    Laser drone AI that:
    1. Determines nearest opponent at spawn
    2. Schedules laser shots at the right time
    3. Handles laser damage application
    4. Vanishes after attack sequence
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotDroneLaserAI')
    
    def getDroneType(self):
        return CraneGameGlobals.DroneType.LASER
    
    def startBehavior(self):
        """Initialize laser drone behavior."""
        # Determine target immediately when drone spawns (cannot be the owner)
        targetId = self.findNearestOpponent()
        if targetId:
            self.setTargetId(targetId)
        else:
            # No target found, vanish immediately
            self.vanishWithPoof()
            return
        
        # Schedule laser shots
        # Sequence: 1s hover + 2s lerp + 1s lock = 4 seconds before lasers
        taskMgr.doMethodLater(4.0, self.shootLasers, self.uniqueName('shootLasers'))
    
    def shootLasers(self, task):
        """Shoot 3 lasers at the target over 1 second."""
        # Clear hit tracking for new volley
        self.hitToons.clear()
        
        # Use the target that was determined at spawn
        if not self.targetId:
            self.vanishWithPoof()
            return Task.done
        
        # Verify target still exists and is not the owner
        target = self.air.doId2do.get(self.targetId)
        if not target or self.targetId == self.ownerId:
            self.vanishWithPoof()
            return Task.done
        
        # Shoot 3 lasers with 0.5 seconds between each
        targetId = self.targetId
        for i in range(3):
            delay = i * 0.5
            def makeShootLaserTask(tid):
                def shootLaserTask(task):
                    return self.shootSingleLaser(tid, task)
                return shootLaserTask
            taskMgr.doMethodLater(delay, makeShootLaserTask(targetId), 
                                 self.uniqueName('shootLaser-%d' % i))
        
        # Vanish after all lasers are done (1.5 seconds for lasers + 2 second pause = 3.5 seconds)
        taskMgr.doMethodLater(3.5, self.vanishWithPoof, self.uniqueName('vanishAfterAttack'))
        
        return Task.done
    
    def shootSingleLaser(self, targetId, task=None):
        """Shoot a single laser at the target."""
        target = self.air.doId2do.get(targetId)
        if not target:
            if task:
                return Task.done
            return
        
        # Send laser shot to client (visual only)
        self.sendUpdate('shootLaser', [targetId])
        
        if task:
            return Task.done
    
    def requestLaserHit(self, toonId):
        """Handle laser hit damage application (sent from client)."""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate the request
        if not self.validate(avId, avId in self.boss.game.getParticipants(), 'requestLaserHit from unknown avatar'):
            return
        
        if self.boss.game.isSpectating(avId):
            return
        
        # Prevent duplicate hits from the same drone's volley
        if toonId in self.hitToons:
            return
        
        # Mark as hit to prevent duplicate damage
        self.hitToons.add(toonId)
        
        toon = self.air.doId2do.get(toonId)
        if not toon:
            return
        
        # Apply damage using the same system as goons
        laserDamage = 15  # Same as default goon strength
        
        # Apply damage
        if hasattr(self.boss, 'game') and hasattr(self.boss.game, 'damageToon'):
            self.boss.game.damageToon(toon, laserDamage)
        else:
            # Fallback to boss.damageToon for non-stripped boss
            self.boss.damageToon(toon, laserDamage)
    
    def delete(self):
        """Clean up laser-specific resources."""
        taskMgr.remove(self.uniqueName('shootLasers'))
        taskMgr.remove(self.uniqueName('vanishAfterAttack'))
        # Remove all shootLaser tasks
        for i in range(3):
            taskMgr.remove(self.uniqueName('shootLaser-%d' % i))
        
        DistributedCashbotDroneBaseAI.delete(self)


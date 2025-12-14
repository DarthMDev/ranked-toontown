from panda3d.core import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from direct.distributed import DistributedObjectAI
from toontown.suit import DistributedGoonAI
import math

class DistributedGoonDroneAI(DistributedGoonAI.DistributedGoonAI):
    """AI-side drone goon that flies around and targets opponents."""
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneAI')
    
    def __init__(self, air, boss, ownerId):
        DistributedGoonAI.DistributedGoonAI.__init__(self, air, 0)
        self.boss = boss
        self.ownerId = ownerId
        self.targetId = None
        self.deployTime = globalClock.getFrameTime()
        self.flyTask = None
        self.hitToons = set()  # Track toons hit by this drone to prevent duplicate damage
        # Initialize pos to None - will be set by b_setPosition
        if not hasattr(self, 'pos'):
            self.pos = None
        
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
        
    def announceGenerate(self):
        DistributedGoonAI.DistributedGoonAI.announceGenerate(self)
        
        # Determine target immediately when drone spawns (cannot be the owner)
        targetId = self.findNearestOpponent()
        if targetId:
            self.setTargetId(targetId)
        else:
            # No target found, vanish immediately
            self.vanishWithPoof()
            return
        
        # The client will handle the full behavior sequence
        # We just need to schedule the laser shots at the right time
        # Sequence: 1s hover + 2s lerp + 1s lock = 4 seconds before lasers
        taskMgr.doMethodLater(4.0, self.shootLasers, self.uniqueName('shootLasers'))
        
    def flyBehavior(self, task):
        """Fly around and gradually move toward target."""
        if not self.boss:
            return Task.done
            
        # Find nearest opponent
        targetId = self.findNearestOpponent()
        if targetId:
            if self.targetId != targetId:
                self.setTargetId(targetId)
            target = self.air.doId2do.get(targetId)
            if target:
                # Gradually move toward target
                # Use self.pos which is set by setPosition (from DistributedCrushableEntityAI)
                if not hasattr(self, 'pos') or self.pos is None:
                    return Task.cont
                currentPos = Point3(self.pos[0], self.pos[1], self.pos[2])
                targetPos = target.getPos()
                
                # Calculate direction
                direction = targetPos - currentPos
                distance = direction.length()
                if distance > 0.1:
                    direction.normalize()
                    
                    # Move at a reasonable speed
                    flySpeed = 5.0  # units per second
                    dt = globalClock.getDt()
                    newPos = currentPos + direction * flySpeed * dt
                    
                    # Keep at a reasonable height above the floor
                    newPos.setZ(max(newPos.getZ(), 10))
                    
                    # Update position using b_setPosition
                    self.b_setPosition([newPos.getX(), newPos.getY(), newPos.getZ()])
                    
                    # Look at target (AI doesn't have lookAt, skip for now)
                    # self.lookAt(targetPos)
                    # self.setP(0)  # Keep level
        else:
            # No target, roam around
            self.roamBehavior()
            
        return Task.cont
        
    def roamBehavior(self):
        """Roam around when no target is available."""
        # Simple roaming - move in a circle or random direction
        # Use self.pos which is set by setPosition (from DistributedCrushableEntityAI)
        if not hasattr(self, 'pos') or self.pos is None:
            return
        currentPos = Point3(self.pos[0], self.pos[1], self.pos[2])
        # Add some random movement
        import random
        angle = random.uniform(0, 360)
        rad = math.radians(angle)
        direction = Vec3(math.cos(rad), math.sin(rad), 0)
        flySpeed = 3.0
        dt = globalClock.getDt()
        newPos = currentPos + direction * flySpeed * dt
        newPos.setZ(max(newPos.getZ(), 10))
        self.b_setPosition([newPos.getX(), newPos.getY(), newPos.getZ()])
        
    def findNearestOpponent(self):
        """Find the nearest opponent toon ID (cannot be the owner/deployer)."""
        if not self.boss:
            return None
            
        nearestId = None
        nearestDist = float('inf')
        
        # Get owner position for distance calculation (from deployer's position)
        owner = self.air.doId2do.get(self.ownerId)
        if not owner:
            return None
        ownerPos = owner.getPos()
        
        # Get all toons in the battle - check if boss has game attribute (crane game) or involvedToons (standalone boss)
        if hasattr(self.boss, 'game') and self.boss.game:
            # Crane game - use game's participant list
            involvedToons = self.boss.game.getParticipantIdsNotSpectating()
        elif hasattr(self.boss, 'involvedToons'):
            # Standalone boss - use boss's involvedToons
            involvedToons = self.boss.involvedToons
        else:
            return None
        
        for toonId in involvedToons:
            # CRITICAL: Cannot target the owner/deployer
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
        
    def shootLasers(self, task):
        """Shoot 3 lasers at the target over 1 second (1/3 second each)."""
        # Clear hit tracking for new volley (prevents duplicate hits from multiple requests)
        self.hitToons.clear()
        
        # Use the target that was determined at spawn
        if not self.targetId:
            # No target found, vanish with poof
            self.vanishWithPoof()
            return Task.done
        
        # Verify target still exists and is not the owner
        target = self.air.doId2do.get(self.targetId)
        if not target or self.targetId == self.ownerId:
            self.vanishWithPoof()
            return Task.done
        
        # Shoot 3 lasers with 0.5 seconds between each
        targetId = self.targetId  # Store in local variable for closure
        for i in range(3):
            delay = i * 0.5  # 0.0, 0.5, 1.0 seconds
            # Create a closure to capture targetId
            def makeShootLaserTask(tid):
                def shootLaserTask(task):
                    return self.shootSingleLaser(tid, task)
                return shootLaserTask
            taskMgr.doMethodLater(delay, makeShootLaserTask(targetId), 
                                 self.uniqueName('shootLaser-%d' % i))
        
        # Vanish with poof after all lasers are done (1.5 seconds for lasers + 2 second pause = 3.5 seconds)
        taskMgr.doMethodLater(3.5, self.vanishWithPoof, self.uniqueName('vanishAfterAttack'))
                                 
        return Task.done
    
    def vanishWithPoof(self, task=None):
        """Vanish the drone with a poof effect."""
        self.sendUpdate('vanishWithPoof', [])
        self.requestDelete()
        if task:
            return Task.done
        
    def shootSingleLaser(self, targetId, task=None):
        """Shoot a single laser at the target."""
        target = self.air.doId2do.get(targetId)
        if not target:
            if task:
                return Task.done
            return
            
        # Send laser shot to client
        self.sendUpdate('shootLaser', [targetId])
        
        # Calculate laser travel time (1 second)
        # The client will handle the visual and damage application
        
        if task:
            return Task.done
    
    def requestLaserHit(self, toonId):
        """Handle laser hit damage application (same system as goons use)."""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate the request - use same validation as zapToon
        if not self.validate(avId, avId in self.boss.game.getParticipants(), 'requestLaserHit from unknown avatar'):
            return
        
        if self.boss.game.isSpectating(avId):
            return
        
        # CRITICAL: Prevent duplicate hits from the same drone's volley
        # Even if client sends multiple requests (due to bugs or exploits), only apply damage once
        if toonId in self.hitToons:
            return  # Already hit by this drone in this volley, skip
        
        # Mark as hit to prevent duplicate damage
        self.hitToons.add(toonId)
        
        toon = self.air.doId2do.get(toonId)
        if not toon:
            return
        
        # Use the same system as goons - call boss.damageToon with strength
        # Use a damage value similar to goon strength (default 15, but can vary)
        # For drone lasers, we'll use a fixed damage value (e.g., 10-15)
        laserDamage = 15  # Same as default goon strength
        
        # Apply damage using the same method goons use
        # For stripped boss, use game.damageToon instead of boss.damageToon
        if hasattr(self.boss, 'game') and hasattr(self.boss.game, 'damageToon'):
            self.boss.game.damageToon(toon, laserDamage)
        else:
            # Fallback to boss.damageToon for non-stripped boss
            self.boss.damageToon(toon, laserDamage)
        
    def destroyDrone(self):
        """Destroy the drone (called when hit by safe)."""
        self.sendUpdate('destroyDrone', [])
        self.requestDelete()
    
    def delete(self):
        """Clean up when deleted."""
        # Clean up tasks
        if self.flyTask:
            taskMgr.remove(self.flyTask)
            self.flyTask = None
        taskMgr.remove(self.uniqueName('shootLasers'))
        # Remove all shootLaser tasks
        for i in range(3):
            taskMgr.remove(self.uniqueName('shootLaser-%d' % i))
        taskMgr.remove(self.uniqueName('vanishAfterAttack'))
        
        # Call parent delete
        DistributedGoonAI.DistributedGoonAI.delete(self)


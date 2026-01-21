"""
Base class for drone goons with common functionality.
Specialized drone types inherit from this class.
"""

from panda3d.core import *
from direct.interval.IntervalGlobal import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.minigame.utils.objects import DistributedGoon
from toontown.coghq import DistributedCrushableEntity
from toontown.minigame.craning import CraneGameGlobals
from toontown.battle import BattleProps
from toontown.effects import DustCloud


class DistributedCashbotDroneBase(DistributedGoon.DistributedGoon, DistributedCrushableEntity.DistributedCrushableEntity):
    """
    Base class for all drone goons. Contains common functionality like:
    - Propeller attachment and spinning
    - Collision detection with safes
    - Visual effects (poof, dust cloud)
    - Owner and target management
    
    Subclasses must implement:
    - getDroneType() - returns the CraneGameGlobals.DroneType enum
    - startBehavior() - implements the type-specific behavior
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotDroneBase')
    
    def __init__(self, cr):
        DistributedCrushableEntity.DistributedCrushableEntity.__init__(self, cr)
        DistributedGoon.DistributedGoon.__init__(self, cr)
        self.boss = None
        self.ownerId = 0  # Toon who deployed this drone
        self.targetId = None  # Target toon ID
        self.deployTime = 0
        self.propeller = None
        self.propellerSpinTask = None
        self.behaviorSequence = None
        
    def getDroneType(self):
        """
        Override in subclass to return the drone type enum.
        Returns: CraneGameGlobals.DroneType
        """
        raise NotImplementedError("Subclass must implement getDroneType()")
    
    def startBehavior(self):
        """
        Override in subclass to implement type-specific behavior.
        Called after drone is set up and ready to start its action.
        """
        raise NotImplementedError("Subclass must implement startBehavior()")
    
    def setOwnerId(self, ownerId):
        """Set the owner ID (received from AI)."""
        self.ownerId = ownerId
        
    def setDroneType(self, droneTypeValue):
        """Set the drone type (received from AI) - updates hat color."""
        # Update hat color based on drone type
        self.updateHatColor()
    
    def updateHatColor(self):
        """Update the hat color based on drone type."""
        hatColor = self.getDroneType().getHatColor()
        
        # Try multiple methods to find the hat
        hat = None
        
        # Method 1: Try hat directly (if goon has created it)
        if hasattr(self, 'hat') and self.hat and not self.hat.isEmpty():
            hat = self.hat
        
        # Method 2: Try finding via head
        if not hat and hasattr(self, 'head') and self.head and not self.head.isEmpty():
            hat = self.head.find('**/hat')
        
        # Method 3: Try finding via joint8 (hat joint)
        if hat.isEmpty() if hat else True:
            hat = self.find('**/joint8')
        
        # Method 4: Try finding any hat in the model
        if hat.isEmpty() if hat else True:
            hat = self.find('**/hat')
        
        if hat and not hat.isEmpty():
            hat.setColorScale(hatColor)
        else:
            # Hat not found yet, try again later (head might not be set up)
            taskMgr.remove(self.uniqueName('updateHatColor'))
            taskMgr.doMethodLater(0.2, self.updateHatColor, self.uniqueName('updateHatColor'))
    
    def setTargetId(self, targetId):
        """Set the target ID (received from AI)."""
        if targetId == 0:
            targetId = None
        self.targetId = targetId
        
        # If we're already set up and waiting for target, start the behavior now
        if targetId and hasattr(self, 'propeller') and self.propeller:
            # Check if behavior hasn't started yet
            if not hasattr(self, 'behaviorSequence') or self.behaviorSequence is None:
                taskMgr.remove(self.uniqueName('startBehavior'))
                self.startBehavior()
    
    def generate(self):
        DistributedCrushableEntity.DistributedCrushableEntity.generate(self)
        DistributedGoon.DistributedGoon.generate(self)
        
    def announceGenerate(self):
        DistributedCrushableEntity.DistributedCrushableEntity.announceGenerate(self)
        DistributedGoon.DistributedGoon.announceGenerate(self)
        
        # Get boss reference
        self._findBoss()
        
        # Check if there are any opponents (only for types that need opponents)
        if self.needsOpponents() and not self.hasOpponents():
            # No opponents, vanish immediately with poof
            def vanishNoOpponents(task):
                self.vanishWithPoof()
                return Task.done
            taskMgr.doMethodLater(0.1, vanishNoOpponents, self.uniqueName('vanishNoOpponents'))
            return
        
        # Set up the drone visuals and behavior
        def setupDrone(task):
            if not self.isEmpty():
                # Create poof effect when appearing
                self._createPoofEffect(spawn=True)
                
                self.show()
                self.reparentTo(render)
                # Request 'Stunned' state to show the collapsed animation
                self.request('Stunned')
                
                # Set up collision for safe detection (can be destroyed by safes)
                # Skip if drone type doesn't want safe collision (e.g., stun drone when growing)
                if not hasattr(self, 'skipSafeCollision') or not self.skipSafeCollision:
                    self.setupSafeCollision()
                
                # Set up as disabled goon (collapsed animation)
                self.loop('collapse')
                
                # Attach propellers to head
                self.attachPropellers()
                
                # Start propeller rotation
                self.startPropellerSpin()
                
                # Wait for drone type and target to be set before starting behavior
                def startBehaviorDelayed(task):
                    self.startBehavior()
                    return Task.done
                taskMgr.doMethodLater(0.2, startBehaviorDelayed, self.uniqueName('startBehavior'))
            return Task.done
        
        taskMgr.doMethodLater(0.1, setupDrone, self.uniqueName('setupDrone'))
    
    def needsOpponents(self):
        """
        Override in subclasses that need opponents to function.
        Returns: bool - True if this drone type needs opponents to work
        """
        return False
    
    def _findBoss(self):
        """Find and store reference to the boss."""
        # First try to get from game if owner is in a crane game
        owner = base.cr.doId2do.get(self.ownerId)
        if owner:
            # Check if owner is in a minigame that has a boss
            if hasattr(base, 'curMinigame') and base.curMinigame:
                if hasattr(base.curMinigame, 'boss') and base.curMinigame.boss:
                    self.boss = base.curMinigame.boss
        
        # Fallback: try other methods
        if not self.boss:
            if hasattr(base, 'boss'):
                self.boss = base.boss
            elif hasattr(base, 'cr') and hasattr(base.cr, 'doId2do'):
                # Try to find boss in scene
                for obj in base.cr.doId2do.values():
                    if hasattr(obj, '__class__') and 'CashbotBoss' in obj.__class__.__name__:
                        self.boss = obj
                        break
    
    def _createPoofEffect(self, spawn=True):
        """Create a poof visual effect at the drone's position."""
        owner = base.cr.doId2do.get(self.ownerId)
        if owner:
            ownerPos = owner.getPos(render)
            poofPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        else:
            poofPos = self.getPos(render) if not spawn else Point3(0, 0, 15)
        
        dustCloud = DustCloud.DustCloud(render, wantSound=1)
        dustCloud.setBillboardPointEye()
        dustCloud.setPos(render, poofPos)
        dustCloud.setScale(0.5)
        dustCloud.play()
    
    def setupSafeCollision(self):
        """Set up collision detection so safes can destroy this drone."""
        # Add collision sphere for safe detection
        # Name it 'goon' so the safe's collision event pattern '-goon' matches
        cn = CollisionNode('goon')
        cs = CollisionSphere(0, 0, 4, 4)  # Same as regular goons
        cn.addSolid(cs)
        # Use PieBitmask so safes (which have PieBitmask in FromCollideMask) can collide with us
        cn.setIntoCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CashbotBossObjectBitmask)
        self.droneCollisionNodePath = self.attachNewNode(cn)
        
        # Set the doId tag on both the collision node path and the drone itself
        self.droneCollisionNodePath.setTag('doId', str(self.doId))
        self.setTag('doId', str(self.doId))
    
    def vanishWithPoof(self, task=None):
        """Vanish the drone with a poof effect."""
        if self.isEmpty():
            if task:
                return Task.done
            return
        
        # Create poof effect
        self.poof()
        
        # Disable the drone after a short delay to let the poof play
        def disableAfterPoof():
            self.disable()
        taskMgr.doMethodLater(0.3, lambda task: disableAfterPoof(), self.uniqueName('vanishPoof'))
        
        if task:
            return Task.done
    
    def poof(self):
        """Create a vanish poof effect at the drone's current position."""
        dronePos = self.getPos(render)
        poofPos = Point3(dronePos.getX(), dronePos.getY(), dronePos.getZ())
        
        vanishDustCloud = DustCloud.DustCloud(render, wantSound=1)
        vanishDustCloud.setBillboardPointEye()
        vanishDustCloud.setPos(render, poofPos)
        vanishDustCloud.setScale(0.5)
        vanishDustCloud.play()
        self.hide()
    
    def b_destroyGoon(self):
        """Called by safes when they hit this drone."""
        # Send update to AI to destroy this drone
        self.sendUpdate('destroyDrone', [])
        # Don't call destroyDrone() locally - wait for the AI broadcast
    
    def doLocalStun(self):
        """Called by safes when SAFES_STUN_GOONS is enabled."""
        # For drones, stunning just destroys them
        self.b_destroyGoon()
    
    def destroyDrone(self):
        """Destroy the drone visually (called from AI broadcast)."""
        # Prevent duplicate destruction
        if hasattr(self, '_isDestroyed') and self._isDestroyed:
            return
        self._isDestroyed = True
        
        if not self.isEmpty():
            # Use the same crush effect as regular goons
            self.playCrushMovie(None, None)
        # Don't call disable() here - playCrushMovie handles cleanup via dead()
    
    def attachPropellers(self):
        """Attach rotating propellers to the goon's head."""
        if self.propeller is None:
            self.propeller = BattleProps.globalPropPool.getProp('propeller')
            head = self.find('**/joint35')
            if head.isEmpty():
                head = self.find('**/joint40')
            if not head.isEmpty():
                self.propeller.reparentTo(head)
                self.propeller.setPos(0, 0, 0)
                self.propeller.setHpr(0, 0, 0)
                
                # Find the propeller blades (not the handle)
                self.propellerBlades = []
                index = 1
                blade = self.propeller.find('**/propeller%d' % index)
                while not blade.isEmpty():
                    self.propellerBlades.append(blade)
                    index += 1
                    blade = self.propeller.find('**/propeller%d' % index)
                
                # If no numbered propellers found, try finding any child that might be blades
                if not self.propellerBlades:
                    for name in ['blade', 'prop', 'rotor']:
                        blade = self.propeller.find('**/%s' % name)
                        if not blade.isEmpty():
                            self.propellerBlades.append(blade)
    
    def startPropellerSpin(self):
        """Start rotating the propellers."""
        if self.propeller and not self.propeller.isEmpty():
            self.propellerSpinTask = taskMgr.add(self.spinPropeller, self.uniqueName('spinPropeller'))
    
    def spinPropeller(self, task):
        """Rotate only the propeller blades, not the handle."""
        if self.propeller and not self.propeller.isEmpty():
            # Rotate each blade
            if hasattr(self, 'propellerBlades') and self.propellerBlades:
                for blade in self.propellerBlades:
                    blade.setH(blade.getH() + 360 * globalClock.getDt())
            else:
                # Fallback: if we can't find blades, try rotating children
                for child in self.propeller.getChildren():
                    if 'handle' not in child.getName().lower() and 'base' not in child.getName().lower():
                        child.setH(child.getH() + 360 * globalClock.getDt())
        return Task.cont
    
    def hasOpponents(self):
        """Check if there are any opponents."""
        if not self.boss:
            return False
        # Check if boss has game attribute (crane game) or involvedToons (standalone boss)
        if hasattr(self.boss, 'game') and self.boss.game:
            involvedToons = self.boss.game.getParticipantIdsNotSpectating()
        elif hasattr(self.boss, 'involvedToons'):
            involvedToons = self.boss.involvedToons
        else:
            return False
        opponents = [tid for tid in involvedToons if tid != self.ownerId]
        return len(opponents) > 0
    
    def findNearestOpponent(self):
        """Find the nearest opponent toon."""
        if not self.boss:
            return None
        
        nearest = None
        nearestDist = float('inf')
        currentPos = self.getPos()
        
        # Get all toons in the battle
        if hasattr(self.boss, 'game') and self.boss.game:
            involvedToons = self.boss.game.getParticipantIdsNotSpectating()
        elif hasattr(self.boss, 'involvedToons'):
            involvedToons = self.boss.involvedToons
        else:
            return None
        
        for toonId in involvedToons:
            if toonId == self.ownerId:
                continue  # Skip owner
            toon = base.cr.doId2do.get(toonId)
            if toon and hasattr(toon, 'getPos'):
                dist = (toon.getPos(render) - currentPos).length()
                if dist < nearestDist:
                    nearestDist = dist
                    nearest = toon
        
        return nearest
    
    def performVisualEffect(self, droneType: int):
        """Handle visual effect request from AI for this drone type."""
        droneTypeEnum = CraneGameGlobals.DroneType(droneType)
        if droneTypeEnum == CraneGameGlobals.DroneType.STUN:
            self.performStunVisualEffect()
        elif droneTypeEnum == CraneGameGlobals.DroneType.HEAL:
            self.performHealVisualEffect()
        elif droneTypeEnum == CraneGameGlobals.DroneType.EXPLODEY:
            self.performExplodeVisualEffect()
    
    def performHealVisualEffect(self):
        """Handle heal request from AI - show heal effect."""
        # The heal drone subclass handles its own visual effects
        # This is just a placeholder for the base class
        pass
    
    def performExplodeVisualEffect(self):
        """Handle explosion request from AI - show explosion effect."""
        # Create explosion effect
        explosionPos = self.getPos(render)
        explosion = DustCloud.DustCloud(render, wantSound=1)
        explosion.setBillboardPointEye()
        explosion.setPos(render, explosionPos)
        explosion.setScale(2.0)  # Larger scale for explosion
        explosion.play()
        
        # Vanish immediately after explosion
        self.vanishWithPoof()
    
    def performStunVisualEffect(self):
        """Handle stun request from AI - show stun effect."""
        lerpDuration = 1.75
        startPos = self.getPos()
        targetPos = (self.getX(), self.getY(), self.getZ() - 16)
        sfx = base.loader.loadSfx('phase_3.5/audio/sfx/ENC_cogfall_apart.ogg')
        self.behaviorSequence = Sequence(
            Wait(lerpDuration * .2),
            LerpScaleInterval(self, lerpDuration * .7, 3),
            LerpPosInterval(self, lerpDuration * .1, targetPos, startPos=startPos, blendType='easeIn'),
            Parallel(
                Func(base.playSfx, sfx),
                Func(self.poof)
            )
        )
        self.behaviorSequence.start()
    
    def disable(self):
        """Clean up when disabled."""
        if self.propellerSpinTask:
            taskMgr.remove(self.propellerSpinTask)
            self.propellerSpinTask = None
        if hasattr(self, 'behaviorSequence') and self.behaviorSequence:
            self.behaviorSequence.pause()
            self.behaviorSequence = None
        taskMgr.remove(self.uniqueName('vanishAfterHeal'))
        taskMgr.remove(self.uniqueName('setupDrone'))
        taskMgr.remove(self.uniqueName('startBehavior'))
        taskMgr.remove(self.uniqueName('vanishNoOpponents'))
        taskMgr.remove(self.uniqueName('updateHatColor'))
        
        if hasattr(self, 'dustCloud') and self.dustCloud:
            self.dustCloud.destroy()
            self.dustCloud = None
        if self.propeller:
            self.propeller.cleanup()
            self.propeller.removeNode()
            self.propeller = None
        if hasattr(self, 'droneCollisionNodePath') and self.droneCollisionNodePath:
            if not self.droneCollisionNodePath.isEmpty():
                self.droneCollisionNodePath.removeNode()
            self.droneCollisionNodePath = None
        
        # Clean up DistributedGoon tasks and animations
        taskMgr.remove(self.taskName('resumeWalk'))
        taskMgr.remove(self.taskName('recoveryDone'))
        if hasattr(self, 'animTrack') and self.animTrack:
            self.animTrack.finish()
            self.animTrack = None
        if hasattr(self, 'walkTrack') and self.walkTrack:
            self.walkTrack.pause()
            self.walkTrack = None
        
        # Manually handle the FSM state
        if hasattr(self, 'disableBodyCollisions'):
            self.disableBodyCollisions()
        if hasattr(self, 'disableClipPlanes'):
            self.disableClipPlanes()
        
        # Only call parent disable if node is not empty
        if not self.isEmpty():
            try:
                DistributedCrushableEntity.DistributedCrushableEntity.disable(self)
            except:
                pass
    
    def delete(self):
        """Clean up when deleted."""
        self.disable()
        DistributedGoon.DistributedGoon.delete(self)
        DistributedCrushableEntity.DistributedCrushableEntity.delete(self)


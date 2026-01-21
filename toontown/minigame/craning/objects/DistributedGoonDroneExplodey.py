"""
Explodey Drone - Charges at CFO and explodes on impact, dealing damage.
"""

from panda3d.core import *
from direct.interval.IntervalGlobal import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from direct.showbase.ShowBaseGlobal import aspect2d
from toontown.toonbase import ToontownGlobals
from otp.otpbase import OTPGlobals
from toontown.minigame.craning import CraneGameGlobals
from toontown.minigame.craning.objects.DistributedGoonDroneBase import DistributedGoonDroneBase
from toontown.suit import GoonDeath
import random
import math


class DistributedGoonDroneExplodey(DistributedGoonDroneBase):
    """
    Explodey drone that:
    1. Spawns above owner
    2. Locks onto CFO within 0.5 seconds
    3. Moves backwards and shakes for 1.5 seconds (like being pulled by a bow)
    4. Charges at CFO at high speed
    5. Explodes on collision with CFO, dealing damage and stunning
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneExplodey')
    
    def __init__(self, cr):
        DistributedGoonDroneBase.__init__(self, cr)
        self.cfoTargetPos = None
        self.chargeDirection = None
        self.collisionNodePath = None
        self.collisionHandler = None
        self.hitCFO = False
        self.deploymentPos = None
        self.deploymentH = None
        self.lockedHeading = None
        self.shakeStartTime = None  # Track when shaking started for intensity progression
    
    def getDroneType(self):
        return CraneGameGlobals.DroneType.EXPLODEY
    
    def needsOpponents(self):
        """Explodey drones don't need opponents - they target the boss."""
        return False
    
    def startBehavior(self):
        """Start the explodey drone behavior."""
        if not self.boss:
            self._findBoss()
        
        if not self.boss:
            self.notify.warning('Explodey drone could not find CFO boss')
            self.vanishWithPoof()
            return
        
        # Capture deployment position NOW (when behavior starts, not later)
        # This ensures the position is fixed even if the player moves
        owner = base.cr.doId2do.get(self.ownerId)
        if owner:
            ownerPos = owner.getPos(render)
            self.deploymentPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
            self.setPos(self.deploymentPos)  # Set position immediately
            self.deploymentH = self.getH()  # Store initial heading
        else:
            # Fallback: use current position
            self.deploymentPos = self.getPos(render)
            self.deploymentH = self.getH()
        
        # Start the sequence: lock on -> pull back and shake -> charge
        taskMgr.doMethodLater(0.5, self.lockOntoCFO, self.uniqueName('lockOntoCFO'))
    
    def getCFOHeadPosition(self):
        """Get CFO head position based on whether he's stunned or not."""
        if not self.boss:
            return None
        
        bossPos = self.boss.getPos(render)
        
        # Check if CFO is stunned (head is lower when stunned)
        isStunned = False
        if hasattr(self.boss, 'attackCode'):
            isStunned = (self.boss.attackCode == ToontownGlobals.BossCogDizzy or 
                        self.boss.attackCode == ToontownGlobals.BossCogDizzyNow)
        
        # Get head target position if available
        if hasattr(self.boss, 'headTarget') and self.boss.headTarget:
            headPos = self.boss.headTarget.getPos(render)
        elif hasattr(self.boss, 'neck') and self.boss.neck:
            neckPos = self.boss.neck.getPos(render)
            # Head is higher when not stunned, lower when stunned
            if isStunned:
                headPos = Point3(neckPos.getX(), neckPos.getY(), neckPos.getZ() + 2)  # Lower when stunned
            else:
                headPos = Point3(neckPos.getX(), neckPos.getY(), neckPos.getZ() + 8)  # Higher when not stunned
        else:
            # Fallback: use boss position with offset
            if isStunned:
                headPos = Point3(bossPos.getX(), bossPos.getY(), bossPos.getZ() + 5)  # Lower when stunned
            else:
                headPos = Point3(bossPos.getX(), bossPos.getY(), bossPos.getZ() + 15)  # Higher when not stunned
        
        return headPos
    
    def lockOntoCFO(self, task):
        """Lock onto CFO position within 0.5 seconds with smooth rotation."""
        if not self.boss or self.isEmpty():
            return Task.done
        
        # Ensure we're still at deployment position (don't recalculate it!)
        if self.deploymentPos:
            self.setPos(self.deploymentPos)
        else:
            # Fallback: if deploymentPos wasn't set, get it now (shouldn't happen)
            owner = base.cr.doId2do.get(self.ownerId)
            if owner:
                ownerPos = owner.getPos(render)
                self.deploymentPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
                self.setPos(self.deploymentPos)
                self.deploymentH = self.getH()
            else:
                self.vanishWithPoof()
                return Task.done
        
        # Get CFO head position (accounts for stun state)
        self.cfoTargetPos = self.getCFOHeadPosition()
        if not self.cfoTargetPos:
            self.vanishWithPoof()
            return Task.done
        
        # Calculate heading to face CFO using lookAt
        # First, use lookAt to properly orient the drone
        self.lookAt(self.cfoTargetPos)
        targetH = self.getH()  # Get the heading after lookAt
        self.lockedHeading = targetH
        
        # Reset to deployment heading for smooth rotation
        if self.deploymentH is not None:
            self.setH(self.deploymentH)
        else:
            self.deploymentH = self.getH()
        
        # Smoothly rotate to face CFO over 0.5 seconds
        rotateInterval = LerpHprInterval(
            self,
            duration=0.5,
            hpr=Point3(targetH, 0, 0),
            startHpr=Point3(self.deploymentH, 0, 0),
            blendType='easeInOut'
        )
        
        # After rotation completes, start pull back
        self.behaviorSequence = Sequence(
            rotateInterval,
            Func(self.startPullBackAndShake)
        )
        self.behaviorSequence.start()
        
        return Task.done
    
    def startPullBackAndShake(self):
        """Move backwards and shake for 1.5 seconds (like being pulled by a bow)."""
        if not self.cfoTargetPos or not self.deploymentPos or self.isEmpty():
            return
        
        # ALWAYS use deploymentPos as the starting point (never recalculate or move to it)
        # This prevents any repositioning issues
        self.setPos(self.deploymentPos)  # Ensure we're at deployment position
        
        # Pull back direction is OPPOSITE of the heading (away from CFO)
        # Heading points TO CFO, so we need to go in the opposite direction

        # Calculate direction vector from deployment to CFO
        directionToCFO = self.cfoTargetPos - self.deploymentPos
        directionToCFO.normalize()
        
        # Pull back is opposite direction (away from CFO)
        pullBackDirection = -directionToCFO
        
        # Move backwards by 5 units from deployment position
        pullBackDistance = 5.0
        pullBackPos = self.deploymentPos + (pullBackDirection * pullBackDistance)
        
        # Start shake task immediately (shaking starts during pull-back)
        self.shakeStartTime = globalClock.getFrameTime()  # Track when shaking started
        
        # Pull back duration - reduced for faster pull-back
        pullBackDuration = 0.6  # Faster pull-back (was 1.2)
        
        # Total shake duration: pull-back + 1.5 seconds
        totalShakeDuration = pullBackDuration + 1.5
        
        # Store pull-back parameters for shake task to handle both interpolation and shake
        # ALWAYS start from deploymentPos (never use currentPos)
        self.pullBackStartPos = self.deploymentPos
        self.pullBackEndPos = pullBackPos
        self.pullBackDuration = pullBackDuration
        self.pullBackStartTime = None  # Will be set when pull-back actually starts
        self.isPullingBack = False  # Flag to track if we're in pull-back phase
        
        # Initialize shake base position to deployment position
        self.shakeBasePos = self.deploymentPos
        
        # Start shake task immediately - it will handle both pull-back interpolation and shake
        self.shakeTask = taskMgr.add(self.shakeTremble, self.uniqueName('shakeTremble'))
        
        # Start pull-back immediately (no position adjustment needed)
        self.behaviorSequence = Sequence(
            Func(lambda: setattr(self, 'pullBackStartTime', globalClock.getFrameTime())),  # Start pull-back tracking
            Func(lambda: setattr(self, 'isPullingBack', True)),  # Enable pull-back in shake task
            LerpHprInterval(
                self,
                pullBackDuration,
                Point3(self.lockedHeading, 0, 0),
                blendType='easeOut'  # Maintain heading
            ),
            Func(lambda: setattr(self, 'isPullingBack', False)),  # Pull-back complete
            Func(lambda: setattr(self, 'shakeBasePos', pullBackPos)),  # Set final base position after pull-back
            Func(lambda: setattr(self, 'pullBackStartTime', None)),  # Clear pull-back tracking
            Wait(1.5),  # Continue shaking for 1.5 seconds at final position
            Func(self.stopShake),
            Func(self.startCharge)
        )
        
        self.behaviorSequence.start()
    
    def shakeTremble(self, task):
        """Tremble/shake the drone rapidly, increasing in intensity over time."""
        if self.isEmpty():
            return Task.done
        
        # Calculate elapsed time since shaking started
        if not self.shakeStartTime:
            self.shakeStartTime = globalClock.getFrameTime()
        
        elapsedTime = globalClock.getFrameTime() - self.shakeStartTime
        
        # Total shake duration: 1.2s (pull-back) + 1.5s (wait) = 2.7s
        totalShakeDuration = 2.7
        
        # Calculate intensity progression: 0.0 (calm) to 1.0 (aggressive)
        # Start very calm, ramp up to maximum intensity
        intensity = min(1.0, elapsedTime / totalShakeDuration)
        # Use ease-in curve for smoother progression (starts slow, accelerates)
        intensity = intensity * intensity  # Quadratic ease-in
        
        # Base shake amount (calm) and max shake amount (aggressive)
        baseShake = 0.1
        maxShake = 0.6
        
        # Interpolate shake amount based on intensity
        shakeAmount = baseShake + (maxShake - baseShake) * intensity
        
        # During pull-back, interpolate base position manually (shake task controls position)
        if hasattr(self, 'isPullingBack') and self.isPullingBack and hasattr(self, 'pullBackStartTime') and self.pullBackStartTime is not None:
            pullBackElapsed = globalClock.getFrameTime() - self.pullBackStartTime
            if hasattr(self, 'pullBackDuration') and hasattr(self, 'pullBackStartPos') and hasattr(self, 'pullBackEndPos'):
                if pullBackElapsed < self.pullBackDuration:
                    # Calculate interpolated position (easeOut blend)
                    t = min(1.0, pullBackElapsed / self.pullBackDuration)
                    # EaseOut: 1 - (1-t)^2
                    easedT = 1.0 - (1.0 - t) * (1.0 - t)
                    # Interpolate position
                    from panda3d.core import Point3
                    self.shakeBasePos = Point3(
                        self.pullBackStartPos.getX() + (self.pullBackEndPos.getX() - self.pullBackStartPos.getX()) * easedT,
                        self.pullBackStartPos.getY() + (self.pullBackEndPos.getY() - self.pullBackStartPos.getY()) * easedT,
                        self.pullBackStartPos.getZ() + (self.pullBackEndPos.getZ() - self.pullBackStartPos.getZ()) * easedT
                    )
                else:
                    # Pull-back complete, use end position
                    self.shakeBasePos = self.pullBackEndPos
        elif not hasattr(self, 'shakeBasePos') or not self.shakeBasePos:
            # Fallback: use current position if shakeBasePos not set
            self.shakeBasePos = self.getPos(render)
        
        # Random offset for shake (trembling effect) - intensity increases over time
        shakeOffset = Vec3(
            random.uniform(-shakeAmount, shakeAmount),
            random.uniform(-shakeAmount, shakeAmount),
            random.uniform(-shakeAmount * 0.75, shakeAmount * 0.75)  # Slightly less vertical shake
        )
        
        # Apply shake offset to base position
        shakenPos = self.shakeBasePos + shakeOffset
        self.setPos(shakenPos)
        
        return Task.cont
    
    def stopShake(self):
        """Stop the shake effect."""
        if hasattr(self, 'shakeTask'):
            taskMgr.remove(self.shakeTask)
        # Return to base position
        if hasattr(self, 'shakeBasePos'):
            self.setPos(self.shakeBasePos)
    
    def startCharge(self):
        """Charge at CFO at incredibly fast speed (like a bow and arrow launch)."""
        if not self.cfoTargetPos or self.isEmpty() or self.hitCFO:
            return
        
        # Update CFO head position in case stun state changed
        self.cfoTargetPos = self.getCFOHeadPosition()
        if not self.cfoTargetPos:
            return
        
        currentPos = self.getPos(render)
        
        # Calculate direction to CFO
        direction = self.cfoTargetPos - currentPos
        distance = direction.length()
        direction.normalize()
        self.chargeDirection = direction
        
        # Set up collision detection for CFO
        self.setupCFOCollision()
        
        # Charge at VERY high speed (like a bow and arrow launch)
        # Much faster than before - starts fast and accelerates
        chargeSpeed = 150.0  # Units per second (3x faster than before)
        chargeDuration = distance / chargeSpeed
        
        # Calculate heading to CFO for charge
        targetH = math.degrees(math.atan2(direction.getX(), direction.getY()))
        
        # Charge interval - move and rotate simultaneously
        # Use 'easeOut' for bow-like acceleration (fast start, maintains speed)
        self.chargeSequence = Parallel(
            LerpPosInterval(
                self,
                chargeDuration,
                self.cfoTargetPos,
                startPos=currentPos,
                blendType='easeOut'  # Fast start like a bow launch
            ),
            LerpHprInterval(
                self,
                chargeDuration,
                Point3(targetH, 0, 0),
                blendType='easeOut'
            )
        )
        self.chargeSequence.start()
        
        # Check for collision during charge
        # Use both collision events and distance checking
        self.chargeTask = taskMgr.add(self.checkCFOCollision, self.uniqueName('checkCFOCollision'))
        
        # Also ensure collision traverser is updated during charge
        # The collision system needs to be traversed each frame to detect collisions
        self.collisionCheckTask = taskMgr.add(self.updateCollisionCheck, self.uniqueName('updateCollisionCheck'))
    
    def setupCFOCollision(self):
        """Set up collision detection to detect hitting the CFO."""
        # Create collision sphere - same setup as safes
        cn = CollisionNode('object')  # Use 'object' name like safes do
        cs = CollisionSphere(0, 0, 0, 2.5)  # 2.5 unit radius
        cn.addSolid(cs)
        # Use EXACT same collision masks as safes to detect CFO headTarget
        # CFO headTarget has PieBitmask, so we need PieBitmask in FromCollideMask
        cn.setIntoCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.WallBitmask | ToontownGlobals.CashbotBossObjectBitmask | OTPGlobals.CameraBitmask)
        cn.setFromCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.FloorBitmask)
        self.collisionNodePath = self.attachNewNode(cn)
        
        # Set up collision handler - use same pattern as safes
        self.collideName = self.uniqueName('collide')
        self.collisionHandler = CollisionHandlerEvent()
        self.collisionHandler.addInPattern(self.collideName + '-%in')
        self.collisionHandler.addAgainPattern(self.collideName + '-%in')  # Also check for continuous collisions
        base.cTrav.addCollider(self.collisionNodePath, self.collisionHandler)
        
        # Listen for headTarget collision specifically (like safes do)
        # Use acceptOnce since we only want to hit once
        self.acceptOnce(self.collideName + '-headTarget', self.handleCFOCollision)
    
    def updateCollisionCheck(self, task):
        """Update collision traverser to ensure collisions are detected."""
        if self.hitCFO or self.isEmpty():
            return Task.done
        
        # Force collision traverser to check collisions this frame
        # This is important when objects move via LerpPosInterval (not physics)
        if hasattr(self, 'collisionNodePath') and self.collisionNodePath:
            # The collision traverser should automatically check, but we can force it
            pass  # Collision traverser is checked automatically by base.cTrav
        
        return Task.cont
    
    def checkCFOCollision(self, task):
        """Check if we've collided with the CFO during charge (backup distance check)."""
        if self.hitCFO or self.isEmpty():
            return Task.done
        
        # Primary: Rely on collision events (handleCFOCollision)
        # Backup: Distance check in case collision events don't fire
        if self.boss:
            try:
                currentPos = self.getPos(render)
                # Get CFO head position (accounts for stun state)
                bossHeadPos = self.getCFOHeadPosition()
                
                if bossHeadPos:
                    distance = (currentPos - bossHeadPos).length()
                    
                    # If very close to CFO head, trigger hit
                    if distance < 5.0:  # 5 unit hit radius (headTarget sphere is radius 3, we add buffer)
                        self.notify.info(f'Explodey drone hit CFO via distance check: {distance}')
                        self.onHitCFO()
                        return Task.done
            except Exception as e:
                self.notify.warning(f'Error in distance check: {e}')
        
        return Task.cont
    
    def handleCFOCollision(self, entry):
        """Handle collision event with CFO headTarget."""
        if self.hitCFO:
            return
        
        # This event only fires for headTarget collisions (we're listening specifically for it)
        self.onHitCFO()
    
    def onHitCFO(self):
        """Called when explodey drone hits the CFO."""
        if self.hitCFO:
            return
        
        self.hitCFO = True
        
        # Stop movement
        if hasattr(self, 'chargeSequence') and self.chargeSequence:
            self.chargeSequence.pause()
            self.chargeSequence = None
        
        if hasattr(self, 'chargeTask'):
            taskMgr.remove(self.chargeTask)
        
        if hasattr(self, 'collisionCheckTask'):
            taskMgr.remove(self.collisionCheckTask)
        
        # Clean up any ongoing gear attacks immediately to prevent them from completing
        if self.boss and hasattr(self.boss, 'cleanupAttacks'):
            self.boss.cleanupAttacks()
        
        # Notify AI that we hit the CFO
        self.sendUpdate('requestExplode', [])
        
        # Show explosion visual immediately
        self.performExplodeVisualEffect()
    
    def performExplodeVisualEffect(self):
        """Show explosion effect (not poof - actual goon destruction) with enlarged explosion, camera shake, and screen flash."""
        if self.isEmpty():
            return
        
        # Use the same destruction effect as goons (playCrushMovie)
        # Make it MUCH bigger for explodey drone - 5-6x the normal size (enlarged from 3.5x)
        goonPos = self.getPos()
        baseScale = self.scale if hasattr(self, 'scale') and self.scale > 0 else 1.0
        # Much larger explosion - 5-6x normal goon explosion size
        sx = random.uniform(0.9, 1.5) * baseScale * 5.5  # Enlarged X scale
        sz = random.uniform(0.9, 1.5) * baseScale * 5.5  # Enlarged Z scale
        crushTrack = Sequence(
            GoonDeath.createGoonExplosion(self.getParent(), goonPos, VBase3(sx, 1, sz)),
            name=self.uniqueName('crushTrack'),
            autoFinish=1
        )
        crushTrack.start()
        
        # Add camera shake and screen flash (like elementals)
        self._createCameraShake()
        self._createScreenFlash()
        
        # Call dead() like goons do, then disable
        self.dead()
        self.disable()
    
    def _createScreenFlash(self):
        """Create a subtle orange/red screen flash (epilepsy-friendly version, like elementals)."""
        try:
            from panda3d.core import GeomNode, Geom, GeomVertexData, GeomVertexFormat, GeomVertexWriter, GeomTristrips, TransparencyAttrib
            
            # Create base node on aspect2d
            screenFlashBase = aspect2d.attachNewNode('explodeyScreenFlash')
            
            # Create GeomNode
            overlayGN = GeomNode('FlashOverlay')
            screenFlashNode = screenFlashBase.attachNewNode(overlayGN)
            screenFlashNode.setDepthWrite(False)
            screenFlashNode.setTransparency(TransparencyAttrib.MAlpha)
            screenFlashNode.setBin('fixed', 999999)  # Maximum priority
            
            # Create vertices for fullscreen quad
            aspectRatio = base.getAspectRatio()
            xSize = aspectRatio * 3.0
            zSize = 3.0
            shapeVertices = [
                (-xSize, 0.0, zSize),   # Top-left
                (-xSize, 0.0, -zSize),  # Bottom-left
                (xSize, 0.0, zSize),    # Top-right
                (xSize, 0.0, -zSize),   # Bottom-right
            ]
            
            # Create vertex format with position and color
            gFormat = GeomVertexFormat.getV3cp()
            overlayVertexData = GeomVertexData('flashVertices', gFormat, Geom.UHStatic)
            overlayVertexWriter = GeomVertexWriter(overlayVertexData, 'vertex')
            overlayColorWriter = GeomVertexWriter(overlayVertexData, 'color')
            
            # Write vertices with orange/red color (subtle)
            flashColor = Vec4(1.0, 0.4, 0.0, 0.15)  # Subtle orange/red, low alpha
            for vertex in shapeVertices:
                overlayVertexWriter.addData3f(vertex[0], vertex[1], vertex[2])
                overlayColorWriter.addData4f(flashColor)
            
            # Create triangle strip
            overlayTris = GeomTristrips(overlayVertexData)
            overlayTris.addVertex(0)
            overlayTris.addVertex(1)
            overlayTris.addVertex(2)
            overlayTris.addVertex(3)
            overlayTris.closePrimitive()
            
            # Create geom
            overlayGeom = Geom(overlayVertexData)
            overlayGeom.addPrimitive(overlayTris)
            overlayGN.addGeom(overlayGeom)
            
            # Animate: quick flash then fade out
            flashSequence = Sequence(
                LerpColorScaleInterval(screenFlashNode, 0.1, Vec4(1.0, 0.4, 0.0, 0.25), startColorScale=Vec4(1.0, 0.4, 0.0, 0.0)),
                Wait(0.1),
                LerpColorScaleInterval(screenFlashNode, 0.3, Vec4(1.0, 0.4, 0.0, 0.0)),
                Func(screenFlashBase.removeNode)
            )
            flashSequence.start()
        except Exception as e:
            self.notify.warning(f'Error creating screen flash: {e}')
    
    def _createCameraShake(self):
        """Create a camera shake effect for the explosion (like elementals)."""
        try:
            camera = base.camera
            if not camera or camera.isEmpty():
                return
            
            # Shake intensity - strong for explodey drone
            shakeIntensity = 1.5
            shakeDuration = 0.5
            
            # Initialize shake state
            self.cameraShakeActive = True
            self.cameraShakeStartTime = globalClock.getFrameTime()
            self.cameraShakeDuration = shakeDuration
            self.cameraShakeIntensity = shakeIntensity
            self.cameraShakeOffset = Vec3(0, 0, 0)
            self.cameraShakeLastUpdate = 0.0
            self.cameraShakeDirection = Vec3(
                (random.random() - 0.5) * 2.0,
                (random.random() - 0.5) * 2.0,
                (random.random() - 0.5) * 0.8
            )
            if self.cameraShakeDirection.length() > 0:
                self.cameraShakeDirection.normalize()
            
            # Store camera reference
            self.shakeCamera = camera
            
            # Start shake update task
            taskMgr.add(self._updateCameraShake, self.uniqueName('cameraShake'), priority=50)
            
            # Schedule shake end
            taskMgr.doMethodLater(shakeDuration, self._stopCameraShake, self.uniqueName('stopCameraShake'))
        except Exception as e:
            self.notify.warning(f'Error creating camera shake: {e}')
    
    def _updateCameraShake(self, task):
        """Update camera shake every frame."""
        if not hasattr(self, 'cameraShakeActive') or not self.cameraShakeActive:
            return task.done
        if not hasattr(self, 'shakeCamera') or not self.shakeCamera:
            return task.done
        
        try:
            currentTime = globalClock.getFrameTime()
            elapsed = currentTime - self.cameraShakeStartTime
            
            if elapsed >= self.cameraShakeDuration:
                self._removeCameraShakeOffset()
                return task.done
            
            # Calculate shake progress (0.0 to 1.0)
            progress = elapsed / self.cameraShakeDuration
            
            # Decay intensity over time (strong at start, weak at end)
            intensityMultiplier = 1.0 - (progress * progress)  # Quadratic decay
            
            # Calculate current shake offset
            import math
            shakeFrequency = 15.0
            timeValue = elapsed * shakeFrequency
            
            # Random direction changes periodically
            if int(timeValue) != self.cameraShakeLastUpdate:
                self.cameraShakeDirection = Vec3(
                    (random.random() - 0.5) * 2.0,
                    (random.random() - 0.5) * 2.0,
                    (random.random() - 0.5) * 0.8
                )
                if self.cameraShakeDirection.length() > 0:
                    self.cameraShakeDirection.normalize()
                self.cameraShakeLastUpdate = int(timeValue)
            
            # Calculate shake offset
            shakeAmount = self.cameraShakeIntensity * intensityMultiplier
            noiseValue = math.sin(timeValue * 2 * math.pi) * 0.5 + 0.5
            self.cameraShakeOffset = self.cameraShakeDirection * shakeAmount * noiseValue
            
            # Apply offset to camera
            if hasattr(self, 'cameraShakeBasePos'):
                self.shakeCamera.setPos(self.cameraShakeBasePos + self.cameraShakeOffset)
            else:
                # Store base position on first update
                self.cameraShakeBasePos = self.shakeCamera.getPos()
                self.shakeCamera.setPos(self.cameraShakeBasePos + self.cameraShakeOffset)
            
            return task.cont
        except Exception as e:
            self.notify.warning(f'Error updating camera shake: {e}')
            return task.done
    
    def _removeCameraShakeOffset(self):
        """Remove camera shake offset and restore original position."""
        if hasattr(self, 'cameraShakeActive'):
            self.cameraShakeActive = False
        if hasattr(self, 'shakeCamera') and hasattr(self, 'cameraShakeBasePos'):
            try:
                self.shakeCamera.setPos(self.cameraShakeBasePos)
            except:
                pass
        taskMgr.remove(self.uniqueName('cameraShake'))
    
    def _stopCameraShake(self, task):
        """Stop camera shake task."""
        self._removeCameraShakeOffset()
        return task.done
    
    def vanishWithPoof(self, task=None):
        """Vanish the drone with a poof effect, unless already destroyed by collision."""
        # Don't poof if we already hit the CFO and got destroyed
        if self.hitCFO:
            if task:
                return Task.done
            return
        
        # Otherwise, use normal poof behavior
        return DistributedGoonDroneBase.vanishWithPoof(self, task)
    
    def disable(self):
        """Clean up when disabled."""
        if hasattr(self, 'chargeTask'):
            taskMgr.remove(self.chargeTask)
        
        if hasattr(self, 'collisionCheckTask'):
            taskMgr.remove(self.collisionCheckTask)
        
        if hasattr(self, 'shakeTask'):
            taskMgr.remove(self.shakeTask)
        
        if hasattr(self, 'collideName'):
            self.ignore(self.collideName + '-headTarget')
        
        if hasattr(self, 'collisionNodePath') and self.collisionNodePath:
            base.cTrav.removeCollider(self.collisionNodePath)
            self.collisionNodePath.removeNode()
        
        # Stop any sequences
        if hasattr(self, 'behaviorSequence') and self.behaviorSequence:
            self.behaviorSequence.pause()
            self.behaviorSequence = None
        
        if hasattr(self, 'chargeSequence') and self.chargeSequence:
            self.chargeSequence.pause()
            self.chargeSequence = None
        
        DistributedGoonDroneBase.disable(self)


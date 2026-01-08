"""
Stun Drone - Goes high above CFO, grows while rotating, then launches down to stun.
"""

from panda3d.core import *
from panda3d.physics import *
from direct.interval.IntervalGlobal import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from otp.otpbase import OTPGlobals
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBase import DistributedGoonDroneBase
import math


class DistributedGoonDroneStun(DistributedGoonDroneBase):
    """
    Stun drone that:
    1. Goes high above CFO
    2. Rotates while growing and moving upward
    3. Stops for 0.5 seconds
    4. Launches down at CFO head
    5. Stuns CFO and all goons on collision
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneStun')
    
    def __init__(self, cr):
        DistributedGoonDroneBase.__init__(self, cr)
        self.cfoTargetPos = None
        self.hitCFO = False
        self.collisionNodePath = None
        self.collisionHandler = None
        self.isGrowing = False  # Flag to track if we're growing (invulnerable)
        self.originalScale = None
        # Don't skip collision setup - we need collision node for safes to collide
        # We'll just make it invulnerable when growing (doHitGoon checks isGrowing)
        self.skipSafeCollision = False
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.STUN
    
    def needsOpponents(self):
        """Stun drones don't need opponents to function."""
        return False
    
    def startBehavior(self):
        """Start the stun drone behavior."""
        if not self.boss:
            self._findBoss()
        
        if not self.boss:
            self.notify.warning('Stun drone could not find CFO boss')
            self.vanishWithPoof()
            return
        
        # Get CFO head position
        self.cfoTargetPos = self.getCFOHeadPosition()
        if not self.cfoTargetPos:
            self.vanishWithPoof()
            return
        
        # Start the sequence: go high -> grow and rotate -> launch down
        self.startAscendAndGrow()
    
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
    
    def startAscendAndGrow(self):
        """Go high above CFO, then grow while rotating and moving upward."""
        if not self.cfoTargetPos or self.isEmpty():
            return
        
        # Get current position (should be above owner)
        currentPos = self.getPos(render)
        
        # Calculate position high above CFO (20 units above head)
        highPos = Point3(
            self.cfoTargetPos.getX(),
            self.cfoTargetPos.getY(),
            self.cfoTargetPos.getZ() + 10
        )
        
        # Store original scale
        self.originalScale = self.getScale()
        
        # Mark as growing (invulnerable)
        # Keep collision node active so safes can still collide with it
        # but doHitGoon will check isGrowing and not destroy it
        self.isGrowing = True
        
        # Ascend to high position, then grow and rotate while moving up more
        ascendDuration = 1.0  # Time to reach high position
        growDuration = 2.0  # Time to grow and rotate
        finalHighPos = Point3(
            self.cfoTargetPos.getX(),
            self.cfoTargetPos.getY(),
            self.cfoTargetPos.getZ() + 15  # A bit higher after growing
        )
        
        # Final scale (3x larger)
        finalScale = self.originalScale * 3.0
        
        # Sequence: ascend -> grow/rotate/rise -> pause -> launch
        self.behaviorSequence = Sequence(
            # Ascend to high position
            LerpPosInterval(
                self,
                ascendDuration,
                highPos,
                startPos=currentPos,
                blendType='easeInOut'
            ),
            # Grow, rotate, and rise simultaneously
            Parallel(
                LerpScaleInterval(
                    self,
                    growDuration,
                    finalScale,
                    startScale=self.originalScale,
                    blendType='easeInOut'
                ),
                LerpPosInterval(
                    self,
                    growDuration,
                    finalHighPos,
                    startPos=highPos,
                    blendType='easeOut'
                ),
                LerpHprInterval(
                    self,
                    growDuration,
                    Point3(720, 0, 0),  # Rotate 2 full rotations
                    startHpr=Point3(0, 0, 0),
                    blendType='noBlend'  # Constant rotation speed
                )
            ),
            # Pause for 0.5 seconds
            Wait(0.5),
            # Launch down at CFO
            Func(self.startLaunchDown)
        )
        self.behaviorSequence.start()
    
    def startLaunchDown(self):
        """Launch down at CFO head at high speed."""
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
        
        # Keep collision node active - safes can still collide but won't destroy
        # (doHitGoon checks isGrowing and returns early)
        
        # Launch at VERY high speed
        launchSpeed = 200.0  # Units per second
        launchDuration = distance / launchSpeed
        
        # Calculate heading to CFO
        targetH = math.degrees(math.atan2(direction.getX(), direction.getY()))
        
        # Launch interval - move and rotate simultaneously
        self.launchSequence = Parallel(
            LerpPosInterval(
                self,
                launchDuration,
                self.cfoTargetPos,
                startPos=currentPos,
                blendType='easeIn'  # Accelerate as it falls
            ),
            LerpHprInterval(
                self,
                launchDuration,
                Point3(targetH, 0, 0),
                blendType='easeIn'
            )
        )
        self.launchSequence.start()
        
        # Check for collision during launch (distance-based, no collision node needed)
        self.collisionCheckTask = taskMgr.add(self.checkCFOCollision, self.uniqueName('checkCFOCollision'))
    
    def setupCFOCollision(self):
        """Set up collision detection to detect hitting the CFO."""
        # Use distance-based collision detection instead of collision events
        # This avoids triggering the CFO's collision handler which expects safe objects
        # We'll check distance in the checkCFOCollision task instead
        pass  # No collision node needed - we use distance checking only
    
    def checkCFOCollision(self, task):
        """Check if we've collided with the CFO during launch (distance-based detection)."""
        if self.hitCFO or self.isEmpty():
            return Task.done
        
        # Update CFO head position
        self.cfoTargetPos = self.getCFOHeadPosition()
        if not self.cfoTargetPos:
            return Task.cont
        
        # Check distance to CFO head
        currentPos = self.getPos(render)
        distance = (self.cfoTargetPos - currentPos).length()
        
        # If very close, trigger collision (use larger radius for grown drone)
        if distance < 4.0:  # Larger hit radius for grown drone
            self.handleCFOCollision(None)
            return Task.done
        
        return Task.cont
    
    def handleCFOCollision(self, entry):
        """Handle collision with CFO head (called from distance check)."""
        if self.hitCFO:
            return
        
        self.hitCFO = True
        
        # Stop movement
        if hasattr(self, 'launchSequence') and self.launchSequence:
            self.launchSequence.finish()
            self.launchSequence = None
        
        if hasattr(self, 'behaviorSequence') and self.behaviorSequence:
            self.behaviorSequence.finish()
            self.behaviorSequence = None
        
        taskMgr.remove(self.uniqueName('checkCFOCollision'))
        
        # Perform explosion visual effect (similar to explodey drone)
        self.performExplodeVisualEffect()
        
        # Request stun from AI
        self.sendUpdate('requestStun', [])
    
    def performExplodeVisualEffect(self):
        """Perform explosion visual effect when hitting CFO (similar to explodey drone)."""
        if self.isEmpty():
            return
        
        from toontown.suit import GoonDeath
        from toontown.battle import BattleParticles
        from direct.interval.ParticleInterval import ParticleInterval
        import random
        
        # Load particles if not already loaded
        BattleParticles.loadParticles()
        
        goonPos = self.getPos(render)
        baseScale = self.scale if hasattr(self, 'scale') and self.scale > 0 else 1.0

        # Get CFO position at ground level for shockwave
        cfoPos = None
        if self.boss:
            cfoPos = self.boss.getPos(render)
            # Position at ground level (Z = 0 or CFO's base) - ensure it's at ground, not inside CFO
            if hasattr(self.boss, 'getGeomNode'):
                try:
                    cfoBase = self.boss.getGeomNode().getPos(render)
                    # Use CFO base Z, but ensure it's at ground level (not negative)
                    groundZ = max(0, cfoBase.getZ())
                    cfoPos = Point3(cfoPos.getX(), cfoPos.getY(), groundZ)
                except:
                    cfoPos = Point3(cfoPos.getX(), cfoPos.getY(), 0)
            else:
                cfoPos = Point3(cfoPos.getX(), cfoPos.getY(), 0)
        else:
            # Fallback to drone position at ground
            dronePos = self.getPos(render)
            cfoPos = Point3(dronePos.getX(), dronePos.getY(), 0)
        
        # Create sequential horizontal shockwave rings (like boss ground slam)
        # Each ring is a single expanding circle on the ground plane
        numRings = 3  # Number of sequential shockwave rings
        ringDelay = 0.4  # Delay between each ring (seconds)
        ringDuration = 2.0  # How long each ring expands
        startRadius = 0.5  # Starting radius (small)
        endRadius = 50.0  # Ending radius (expands twice as far - doubled from 25.0)
        shockwaveHeight = 0.5  # Height above ground for visibility
        
        # Helper function to create a single horizontal shockwave ring
        def createShockwaveRing(ringIndex):
            # Create a horizontal ring on the ground plane
            # In Toontown: X and Y are horizontal, Z is vertical (like shield rings)
            lines = LineSegs('shockwaveRing%d' % ringIndex)
            lines.setColor(1.0, 1.0, 1.0, 0.8)  # White
            lines.setThickness(5.0)  # Thick line for visibility
            
            # Draw a horizontal circle (ring slightly above ground)
            # X and Y form the circle, Z is slightly above ground for visibility
            numSegments = 64  # Smooth circle
            for j in range(numSegments + 1):
                angle = (2 * math.pi / numSegments) * j
                # Horizontal ring: x and y form the circle, z is slightly above ground
                x = math.cos(angle) * startRadius
                y = math.sin(angle) * startRadius
                z = shockwaveHeight  # Slightly above ground
                if j == 0:
                    lines.moveTo(x, y, z)
                else:
                    lines.drawTo(x, y, z)
            
            # Create the ring node
            ringNode = render.attachNewNode(lines.create())
            ringNode.setPos(render, cfoPos)
            ringNode.setLightOff()
            ringNode.setFogOff()
            ringNode.setDepthWrite(True)
            ringNode.setDepthTest(True)
            ringNode.setTransparency(TransparencyAttrib.MAlpha)
            ringNode.setBin('default', 0)
            
            return ringNode
        
        # Create all rings
        ringNodes = []
        for i in range(numRings):
            ringNode = createShockwaveRing(i)
            ringNodes.append(ringNode)
        
        # Large explosion - similar to explodey drone
        sx = random.uniform(0.9, 1.5) * baseScale * 3.5
        sz = random.uniform(0.9, 1.5) * baseScale * 3.5
        
        # Create sequential expanding shockwave rings
        shockwaveTracks = []
        for i, ringNode in enumerate(ringNodes):
            startDelay = i * ringDelay
            
            # Scale and fade animation for each ring
            # Scale X and Y (the horizontal circle), keep Z at 1.0 (vertical)
            scaleTrack = LerpScaleInterval(
                ringNode,
                ringDuration,
                Vec3(endRadius / startRadius, endRadius / startRadius, 1.0),
                startScale=Vec3(1.0, 1.0, 1.0),
                blendType='easeOut'
            )
            
            fadeTrack = LerpColorScaleInterval(
                ringNode,
                ringDuration,
                Vec4(1.0, 1.0, 1.0, 0.0),  # Fade to transparent
                startColorScale=Vec4(1.0, 1.0, 1.0, 1.0),
                blendType='easeIn'
            )
            
            # Combine scale and fade, then remove the node
            ringTrack = Sequence(
                Wait(startDelay),
                Parallel(scaleTrack, fadeTrack),
                Func(ringNode.removeNode)
            )
            
            shockwaveTracks.append(ringTrack)
        
        # Combine explosion with sequential shockwave rings
        crushTrack = Sequence(
            Parallel(
                GoonDeath.createGoonExplosion(self.getParent(), goonPos, VBase3(sx, 1, sz)),
                *shockwaveTracks  # All shockwave rings
            ),
            name=self.uniqueName('crushTrack'),
            autoFinish=1
        )
        crushTrack.start()
        
        # Call dead() for cleanup, but don't disable yet (AI will handle that)
        self.dead()
    
    def disableSafeCollision(self):
        """Disable collision with safes (make invulnerable)."""
        # Remove collision node if it exists
        if hasattr(self, 'droneCollisionNodePath') and self.droneCollisionNodePath:
            if not self.droneCollisionNodePath.isEmpty():
                # Remove from collision traverser
                base.cTrav.removeCollider(self.droneCollisionNodePath)
                # Remove the node
                self.droneCollisionNodePath.removeNode()
            self.droneCollisionNodePath = None
    
    def performVisualEffect(self, droneTypeValue, healAmount=0, healInterval=0):
        """Handle visual effects from AI."""
        # Trigger flinch animation on CFO when stun drone hits
        # Also clean up any ongoing gear attacks immediately to prevent them from completing
        if self.boss and hasattr(self.boss, 'doAnimate') and hasattr(self.boss, 'ruleset'):
            # Clean up gear attacks immediately when flinch happens (before server stun arrives)
            if hasattr(self.boss, 'cleanupAttacks'):
                self.boss.cleanupAttacks()
            if self.boss.ruleset.CFO_FLINCHES_ON_HIT:
                self.boss.doAnimate('hit', now=1)
    
    def delete(self):
        """Clean up stun-specific resources."""
        taskMgr.remove(self.uniqueName('checkCFOCollision'))
        DistributedGoonDroneBase.delete(self)
    
    def disable(self):
        """Clean up when disabled."""
        taskMgr.remove(self.uniqueName('checkCFOCollision'))
        DistributedGoonDroneBase.disable(self)

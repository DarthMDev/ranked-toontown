"""
Shield Drone - Hovers above owner and creates a protective shield that absorbs one hit.
"""

from panda3d.core import *
from direct.interval.IntervalGlobal import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBase import DistributedGoonDroneBase
from toontown.effects import DustCloud
import math


class DistributedGoonDroneShield(DistributedGoonDroneBase):
    """
    Shield drone that:
    1. Spawns above owner
    2. Hovers and creates a protective shield bubble around owner
    3. Shield absorbs exactly 1 hit from enemies (CFO, goons, laser drones)
    4. Shield can also be broken by safes (counterplay - no i-frames granted)
    5. Lasts 8 seconds or until hit
    6. Visual indicator shows time remaining (pulsing/fading)
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneShield')
    
    def __init__(self, cr):
        DistributedGoonDroneBase.__init__(self, cr)
        self.shieldBubble = None
        self.shieldActive = False
        self.shieldStartTime = None
        self.shieldDuration = 8.0  # 8 seconds
        self.shieldCollisionNode = None
        self.shieldSound = None
        self.pulseTask = None
        self.shieldRings = []
        self.ringRotationTask = None
        self._shatterEffectCreated = False  # Flag to prevent duplicate shatter effects
        self.droneVanished = False  # Track if drone has already vanished
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.SHIELD
    
    def needsOpponents(self):
        """Shield drones don't need opponents to function."""
        return False
    
    def startBehavior(self):
        """Start the shield drone hovering behavior."""
        self.startHovering()
    
    def startHovering(self):
        """Start hovering behavior - hovers above owner."""
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return
        
        ownerPos = owner.getPos(render)
        hoverPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        self.setPos(hoverPos)
        
        # After 0.5s hover, activate shield
        taskMgr.doMethodLater(0.5, self.activateShield, self.uniqueName('activateShield'))
    
    def activateShield(self, task=None):
        """Activate the shield bubble around the owner."""
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner or self.isEmpty():
            if task:
                return Task.done
            return
        
        self.shieldActive = True
        self.shieldStartTime = globalClock.getFrameTime()
        
        # Create shield bubble visual
        self.createShieldBubble(owner)
        
        # Play shield activation sound
        self.playShieldSound()
        
        # Start pulse task to show time remaining (use owner's doId for unique name so it persists)
        # Create a standalone function that doesn't depend on self
        def pulseTask(task):
            return DistributedGoonDroneShield._updateShieldPulseStatic(task, owner)
        
        self.pulseTask = taskMgr.add(
            pulseTask,
            owner.uniqueName('shieldPulse')
        )
        
        # Schedule shield expiration after 8 seconds
        taskMgr.doMethodLater(self.shieldDuration, self.expireShield, self.uniqueName('expireShield'))
        
        # Vanish the drone after 1 second, but keep the shield active
        taskMgr.doMethodLater(1.0, self.vanishDroneOnly, self.uniqueName('vanishDrone'))
        
        if task:
            return Task.done
    
    def vanishDroneOnly(self, task=None):
        """Vanish the drone visual but keep the shield active."""
        # Mark that drone has vanished
        self.droneVanished = True
        # Just vanish the drone itself, don't remove the shield
        return DistributedGoonDroneBase.vanishWithPoof(self, task)
    
    def createShieldBubble(self, owner):
        """Create 3 spinning cyan rings around the owner."""
        if self.shieldBubble:
            return
        
        from panda3d.core import LineSegs, TransparencyAttrib
        
        # Create shield node attached to owner
        self.shieldBubble = owner.attachNewNode('shieldBubble')
        self.shieldOwner = owner  # Store reference for cleanup
        
        # Store shield references on owner so tasks can access them after drone vanishes
        owner._shieldBubble = self.shieldBubble
        owner._shieldRings = []
        owner._shieldActive = True
        owner._shieldStartTime = globalClock.getFrameTime()
        owner._shieldDuration = self.shieldDuration
        
        # Create 3 spinning rings at different heights and sizes
        self.shieldRings = []
        ringConfigs = [
            {'radius': 2.0, 'height': 1.5, 'thickness': 3.0, 'alpha': 0.6},  # Bottom ring
            {'radius': 2.2, 'height': 3.0, 'thickness': 3.5, 'alpha': 0.7},  # Middle ring
            {'radius': 2.4, 'height': 4.5, 'thickness': 4.0, 'alpha': 0.8},  # Top ring
        ]
        
        for i, config in enumerate(ringConfigs):
            # Create ring using line segments - vertical rings around the toon
            lines = LineSegs('shieldRing%d' % i)
            lines.setColor(0.0, 0.8, 1.0, config['alpha'])  # Cyan
            lines.setThickness(config['thickness'])
            
            # Draw a vertical circle (ring) around the toon
            numSegments = 64  # More segments for smoother circle
            radius = config['radius']
            height = config['height']
            
            for j in range(numSegments + 1):
                angle = (2 * math.pi / numSegments) * j
                # Create vertical ring: x and y form the circle, z is the height
                x = math.cos(angle) * radius
                y = math.sin(angle) * radius
                z = height
                if j == 0:
                    lines.moveTo(x, y, z)
                else:
                    lines.drawTo(x, y, z)
            
            ringNode = self.shieldBubble.attachNewNode(lines.create())
            ringNode.setLightOff()
            ringNode.setFogOff()
            ringNode.setDepthWrite(False)
            ringNode.setTransparency(TransparencyAttrib.MAlpha)
            ringNode.setBin('fixed', 0)
            
            # Store ring node for rotation
            self.shieldRings.append(ringNode)
            owner._shieldRings.append(ringNode)
        
        # Start rotation task for rings (use owner's doId for unique name so it persists)
        # Create a standalone function that doesn't depend on self
        def rotateRingsTask(task):
            return DistributedGoonDroneShield._rotateRingsStatic(task, owner)
        
        self.ringRotationTask = taskMgr.add(
            rotateRingsTask,
            owner.uniqueName('shieldRotateRings')
        )
        
        # Add sparkle particles
        self.createShieldSparkles()
        
        # Set up collision sphere for safe detection
        self.setupShieldCollision(owner)
    
    @staticmethod
    def _rotateRingsStatic(task, owner):
        """Rotate the 3 rings at different speeds (static method, doesn't need self)."""
        # Get shield data from owner (persists after drone vanishes)
        if not hasattr(owner, '_shieldBubble') or not owner._shieldBubble or owner._shieldBubble.isEmpty():
            return Task.done
        
        if not hasattr(owner, '_shieldRings') or not owner._shieldRings:
            return Task.done
        
        dt = globalClock.getDt()
        
        # Rotate each ring at different speeds
        speeds = [60.0, -45.0, 75.0]  # Degrees per second (different directions)
        
        for i, ring in enumerate(owner._shieldRings):
            if ring and not ring.isEmpty():
                ring.setH(ring.getH() + speeds[i] * dt)
        
        return Task.cont
    
    def rotateRings(self, task, owner):
        """Rotate the 3 rings at different speeds (instance method for backwards compatibility)."""
        return DistributedGoonDroneShield._rotateRingsStatic(task, owner)
    
    def createShieldSparkles(self):
        """Create sparkle particles around the shield."""
        try:
            from direct.particles import ParticleEffect, Particles, ForceGroup
            
            self.shieldParticles = ParticleEffect.ParticleEffect('ShieldSparkles')
            
            sparkles = Particles.Particles('sparkles')
            sparkles.setFactory('PointParticleFactory')
            sparkles.setRenderer('SpriteParticleRenderer')
            sparkles.setEmitter('SphereVolumeEmitter')
            self.shieldParticles.addParticles(sparkles)
            
            # Configure sparkle particles
            sparkles.setPoolSize(20)
            sparkles.setBirthRate(0.2)
            sparkles.setLitterSize(1)
            sparkles.setLitterSpread(0)
            sparkles.factory.setLifespanBase(0.8)
            sparkles.factory.setLifespanSpread(0.2)
            sparkles.factory.setMassBase(0.1)
            sparkles.factory.setMassSpread(0.05)
            
            # Renderer - small white sparkles
            sparkles.renderer.setAlphaMode(3)
            sparkles.renderer.setUserAlpha(1.0)
            sparkles.renderer.setColor(Vec4(0.5, 1.0, 1.0, 1.0))  # Cyan-white
            sparkles.renderer.setInitialXScale(0.05)
            sparkles.renderer.setFinalXScale(0.01)
            sparkles.renderer.setInitialYScale(0.05)
            sparkles.renderer.setFinalYScale(0.01)
            sparkles.renderer.setXScaleFlag(True)
            sparkles.renderer.setYScaleFlag(True)
            
            # Emitter - around shield surface
            sparkles.emitter.setEmissionType(1)  # ETRADIATE
            sparkles.emitter.setRadius(2.0)
            sparkles.emitter.setAmplitude(0.5)
            sparkles.emitter.setAmplitudeSpread(0.2)
            
            # Start particles
            self.shieldParticles.start(parent=self.shieldBubble, renderParent=render)
            self.shieldParticles.setPos(0, 0, 0)
        except:
            # If particles fail, just continue without them
            pass
    
    def setupShieldCollision(self, owner):
        """Set up collision detection for safes hitting the shield."""
        from panda3d.core import CollisionSphere, CollisionNode
        from toontown.toonbase import ToontownGlobals
        
        # Create collision sphere around owner
        cn = CollisionNode('shield')
        cs = CollisionSphere(0, 0, 3, 3.0)  # Radius 3 units, centered on shield
        cn.addSolid(cs)
        
        # Use PieBitmask so safes can collide with it
        cn.setIntoCollideMask(ToontownGlobals.PieBitmask)
        
        self.shieldCollisionNode = owner.attachNewNode(cn)
        self.shieldCollisionNode.setTag('shieldOwnerId', str(self.ownerId))
        self.shieldCollisionNode.setTag('droneId', str(self.doId))
    
    @staticmethod
    def _updateShieldPulseStatic(task, owner):
        """Update shield visual to show time remaining (static method, doesn't need self)."""
        # Get shield data from owner (persists after drone vanishes)
        if not hasattr(owner, '_shieldBubble') or not owner._shieldBubble or owner._shieldBubble.isEmpty():
            return Task.done
        
        if not hasattr(owner, '_shieldActive') or not owner._shieldActive:
            return Task.done
        
        if not hasattr(owner, '_shieldStartTime') or not owner._shieldStartTime:
            return Task.done
        
        # Calculate time remaining
        elapsed = globalClock.getFrameTime() - owner._shieldStartTime
        timeRemaining = owner._shieldDuration - elapsed
        
        if timeRemaining <= 0:
            return Task.done
        
        # Calculate pulse based on time remaining
        # Start pulsing faster as time runs out
        pulseFrequency = 2.0  # Base frequency
        if timeRemaining < 2.0:
            pulseFrequency = 6.0  # Fast pulse in last 2 seconds
        elif timeRemaining < 4.0:
            pulseFrequency = 4.0  # Medium pulse
        
        # Pulse between 0.8 and 1.2 scale
        pulseAmount = 0.2
        pulseValue = 1.0 + pulseAmount * math.sin(elapsed * pulseFrequency * 2 * math.pi)
        
        # Apply pulse scale to entire shield (safely)
        if not owner._shieldBubble.isEmpty():
            try:
                owner._shieldBubble.setScale(pulseValue)
            except:
                return Task.done
        
        # Fade alpha as time runs out
        alphaMultiplier = timeRemaining / owner._shieldDuration
        if hasattr(owner, '_shieldRings') and owner._shieldRings:
            for ring in owner._shieldRings:
                if ring and not ring.isEmpty():
                    try:
                        # Adjust alpha while maintaining color
                        ring.setColorScale(1.0, 1.0, 1.0, alphaMultiplier)
                    except:
                        continue
        
        return Task.cont
    
    def updateShieldPulse(self, task, owner):
        """Update shield visual to show time remaining (instance method for backwards compatibility)."""
        return DistributedGoonDroneShield._updateShieldPulseStatic(task, owner)
    
    def playShieldSound(self):
        """Play shield activation sound effect."""
        try:
            # Use teleport reappear sound for shield activation (magical/energy feel)
            self.shieldSound = base.loader.loadSfx('phase_5/audio/sfx/teleport_reappear.ogg')
            if self.shieldSound:
                self.shieldSound.play()
        except:
            # Fallback: try device appear sound
            try:
                self.shieldSound = base.loader.loadSfx('phase_5/audio/sfx/General_device_appear.ogg')
                if self.shieldSound:
                    self.shieldSound.play()
            except:
                # Final fallback: healing pixiedust sound
                try:
                    self.shieldSound = base.loader.loadSfx('phase_5/audio/sfx/AA_heal_pixiedust.ogg')
                    if self.shieldSound:
                        self.shieldSound.play()
                except:
                    pass
    
    def breakShield(self, grantIframes):
        """
        Break the shield (called from AI broadcast or locally for visual feedback).
        
        Args:
            grantIframes: uint8 (0 or 1) - If 1, grant i-frames (enemy hit). If 0, no i-frames (safe hit).
        """
        # Convert uint8 to boolean
        grantIframes = bool(grantIframes)
        
        if not self.shieldActive:
            return
        
        # Update owner's shield state
        owner = base.cr.doId2do.get(self.ownerId)
        if owner and hasattr(owner, '_shieldActive'):
            owner._shieldActive = False
        
        self.shieldActive = False
        
        # Stop pulse task first to prevent manipulation of removed nodes
        if self.pulseTask:
            taskMgr.remove(self.pulseTask)
            self.pulseTask = None
        
        # Stop ring rotation task (use task name string, not task object)
        taskMgr.remove(self.uniqueName('rotateRings'))
        self.ringRotationTask = None
        
        # Grant i-frames to owner on client side (if enemy hit) - no visual effects
        if grantIframes:
            owner = base.cr.doId2do.get(self.ownerId)
            if owner and not owner.isStunned:
                # Grant i-frames silently without any visual effects
                # Set isStunned flag directly to grant i-frames without animation
                owner.isStunned = 1
                # Create a silent i-frame track that just sets and clears the flag
                from direct.interval.IntervalGlobal import Sequence, Wait, Func
                def setStunned(stunned):
                    if owner and not owner.isEmpty():
                        owner.isStunned = stunned
                        if owner == base.localAvatar:
                            messenger.send('toonStunned-' + str(owner.doId), [owner.isStunned])
                
                # Standard i-frame duration (same as stunToon uses - approximately 3 seconds)
                iframeDuration = 3.0
                silentIframeTrack = Sequence(
                    Func(setStunned, 1),
                    Wait(iframeDuration),
                    Func(setStunned, 0)
                )
                silentIframeTrack.start()
                # Store track for cleanup if needed
                if not hasattr(owner, '_shieldIframeTrack'):
                    owner._shieldIframeTrack = None
                if owner._shieldIframeTrack:
                    owner._shieldIframeTrack.finish()
                owner._shieldIframeTrack = silentIframeTrack
        
        # Clear any lingering i-frame state when shield breaks/expires (important for natural expiration)
        if not grantIframes:
            # Natural expiration or safe hit - clear any lingering i-frame state
            if owner:
                # Clear isStunned if it was set
                if hasattr(owner, 'isStunned') and owner.isStunned:
                    owner.isStunned = 0
                    if owner == base.localAvatar:
                        messenger.send('toonStunned-' + str(owner.doId), [0])
                
                # Clean up any lingering i-frame track
                if hasattr(owner, '_shieldIframeTrack') and owner._shieldIframeTrack:
                    try:
                        owner._shieldIframeTrack.finish()
                    except:
                        pass
                    owner._shieldIframeTrack = None
        
        # Create shield break visual effect (only if shield still exists)
        if self.shieldBubble and not self.shieldBubble.isEmpty():
            self.createShieldBreakEffect(grantIframes)
        else:
            # Shield already removed, just clean up
            self.removeShieldBubble()
        
        # Don't try to vanish drone if it's already gone
        # Drone should have vanished after 1 second of activation
    
    def createShieldBreakEffect(self, grantIframes):
        """Create visual effect when shield breaks."""
        if not self.shieldBubble or self.shieldBubble.isEmpty():
            return
        
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            return
        
        # Use shattering effect for both enemy hits and safe hits
        # Enemy hits grant i-frames, safe hits don't
        self.createExplosionShatterEffect()
    
    def createCrackEffect(self):
        """Create crack lines on shield before shattering."""
        # Simple approach: quickly scale and fade out the shield
        if not self.shieldBubble or self.shieldBubble.isEmpty():
            return
        
        def safeSetColorScale(r, g, b, a):
            if self.shieldBubble and not self.shieldBubble.isEmpty():
                try:
                    self.shieldBubble.setColorScale(r, g, b, a)
                except:
                    pass
        
        def safeLerpScale(duration, scale):
            if self.shieldBubble and not self.shieldBubble.isEmpty():
                try:
                    return LerpScaleInterval(self.shieldBubble, duration, scale)
                except:
                    return Wait(duration)
            return Wait(duration)
        
        def safeLerpColorScale(duration, endColor):
            if self.shieldBubble and not self.shieldBubble.isEmpty():
                try:
                    return LerpColorScaleInterval(self.shieldBubble, duration, endColor)
                except:
                    return Wait(duration)
            return Wait(duration)
        
        def safeRemoveNode():
            if self.shieldBubble and not self.shieldBubble.isEmpty():
                try:
                    self.shieldBubble.removeNode()
                except:
                    pass
        
        crackSequence = Sequence(
            # Flash bright
            Func(safeSetColorScale, 1.5, 1.5, 1.5, 1.0),
            Wait(0.1),
            # Expand and fade
            Parallel(
                safeLerpScale(0.3, 1.5),
                safeLerpColorScale(0.3, (1.0, 1.0, 1.0, 0.0))
            ),
            Func(safeRemoveNode)
        )
        crackSequence.start()
    
    def createExplosionShatterEffect(self):
        """Create violent explosion effect when safe breaks shield (with Opera singer glass crack)."""
        if not self.shieldBubble or self.shieldBubble.isEmpty():
            return
        
        from toontown.battle import BattleParticles
        from direct.interval.ParticleInterval import ParticleInterval
        
        # Load particles if not already loaded
        BattleParticles.loadParticles()
        
        # Helper function to position effect (replaces setPosFromOther)
        def setPosFromOther(dest, source, offset=Point3(0, 0, 0)):
            pos = render.getRelativePoint(source, offset)
            dest.setPos(render, pos)
        
        # Helper function to create particle track (replaces __getPartTrack)
        def getPartTrack(particleEffect, startDelay, durationDelay, partExtraArgs, softStop=0):
            pEffect = partExtraArgs[0]
            parent = partExtraArgs[1]
            if len(partExtraArgs) == 3:
                worldRelative = partExtraArgs[2]
            else:
                worldRelative = 1
            return Sequence(Wait(startDelay), ParticleInterval(pEffect, parent, worldRelative, duration=durationDelay, cleanup=True, softStopT=softStop))
        
        # Create Opera singer glass crack effect
        breakEffect = BattleParticles.createParticleEffect(file='soundBreak')
        breakEffect.setDepthWrite(1)  # Enable for 3D visibility
        breakEffect.setDepthTest(1)   # Enable for 3D visibility
        breakEffect.setTwoSided(1)
        # Don't use 'fixed' bin - let it render in 3D space
        breakEffect.setBin('default', 0)
        
        # Change color to match shield (cyan: 0.0, 0.8, 1.0)
        shieldColor = Vec4(0.0, 0.8, 1.0, 1.0)  # Cyan shield color
        try:
            # Get the particles and set their color
            particles = breakEffect.getParticlesNamed('particles-1')
            if particles:
                particles.renderer.setColor(shieldColor)
        except:
            pass  # If we can't set color, continue anyway
        
        # Position crack effect at shield location
        owner = base.cr.doId2do.get(self.ownerId)
        if owner:
            # Position at shield height (around torso/chest level)
            ownerPos = owner.getPos(render)
            shieldHeight = 3.0  # Height of shield above ground
            breakPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + shieldHeight)
            breakEffect.setPos(render, breakPos)
        else:
            # Fallback to render origin if owner not found
            breakEffect.setPos(render, Point3(0, 0, 3.0))
        
        # Play Opera singer glass crack sound
        try:
            glassCrackSound = base.loader.loadSfx('phase_5/audio/sfx/AA_sound_Opera_Singer_Cog_Glass.ogg')
        except:
            glassCrackSound = None
        
        def safeSetColorScale(r, g, b, a):
            if self.shieldBubble and not self.shieldBubble.isEmpty():
                try:
                    self.shieldBubble.setColorScale(r, g, b, a)
                except:
                    pass
        
        def safeLerpScale(duration, scale):
            if self.shieldBubble and not self.shieldBubble.isEmpty():
                try:
                    return LerpScaleInterval(self.shieldBubble, duration, scale)
                except:
                    return Wait(duration)
            return Wait(duration)
        
        def safeLerpColorScale(duration, endColor):
            if self.shieldBubble and not self.shieldBubble.isEmpty():
                try:
                    return LerpColorScaleInterval(self.shieldBubble, duration, endColor)
                except:
                    return Wait(duration)
            return Wait(duration)
        
        def safeRemoveNode():
            if self.shieldBubble and not self.shieldBubble.isEmpty():
                try:
                    self.shieldBubble.removeNode()
                except:
                    pass
        
        # Rapid expansion and fade with Opera singer crack effect
        # Ensure breakEffect is properly positioned before starting
        explosionSequence = Sequence(
            # Flash very bright
            Func(safeSetColorScale, 2.0, 2.0, 2.0, 1.0),
            Wait(0.05),
            # Explode outward with crack effect and sound
            Parallel(
                safeLerpScale(0.2, 2.5),
                safeLerpColorScale(0.2, (1.0, 1.0, 1.0, 0.0)),
                getPartTrack(breakEffect, 0.0, 1.5, [breakEffect, render, 0], softStop=-0.5),  # Use render as parent, longer duration
                Func(lambda: glassCrackSound.play() if glassCrackSound else None)
            ),
            Func(safeRemoveNode)
        )
        explosionSequence.start()
    
    def expireShield(self, task=None):
        """Called when shield expires naturally (not hit)."""
        if not self.shieldActive:
            if task:
                return Task.done
            return
        
        self.shieldActive = False
        
        # Update owner's shield state
        owner = base.cr.doId2do.get(self.ownerId)
        if owner and hasattr(owner, '_shieldActive'):
            owner._shieldActive = False
        
        # Clear any lingering i-frame state (shouldn't exist on natural expiration, but clean up just in case)
        if owner:
            # Clear isStunned if it was set
            if hasattr(owner, 'isStunned') and owner.isStunned:
                owner.isStunned = 0
                if owner == base.localAvatar:
                    messenger.send('toonStunned-' + str(owner.doId), [0])
            
            # Clean up any lingering i-frame track
            if hasattr(owner, '_shieldIframeTrack') and owner._shieldIframeTrack:
                try:
                    owner._shieldIframeTrack.finish()
                except:
                    pass
                owner._shieldIframeTrack = None
        
        # Fade out shield smoothly (no shattering effect on natural expiration)
        if self.shieldBubble and not self.shieldBubble.isEmpty():
            fadeSequence = Sequence(
                LerpColorScaleInterval(self.shieldBubble, 1.0, (1.0, 1.0, 1.0, 0.0)),
                Func(self.removeShieldBubble)
            )
            fadeSequence.start()
        else:
            # Shield already removed, just clean up
            self.removeShieldBubble()
        
        # Drone should already be vanished after 1 second of activation
        # Shield cleanup is handled by removeShieldBubble above
        
        if task:
            return Task.done
    
    def removeShieldBubble(self):
        """Remove the shield bubble and cleanup."""
        # Get owner first
        owner = base.cr.doId2do.get(self.ownerId) if hasattr(self, 'ownerId') else None
        
        # Clear any lingering i-frame state (important for natural expiration)
        if owner:
            # Clear isStunned if it was set (shouldn't be set on natural expiration, but clean up just in case)
            if hasattr(owner, 'isStunned') and owner.isStunned:
                owner.isStunned = 0
                if owner == base.localAvatar:
                    messenger.send('toonStunned-' + str(owner.doId), [0])
            
            # Clean up any lingering i-frame track
            if hasattr(owner, '_shieldIframeTrack') and owner._shieldIframeTrack:
                try:
                    owner._shieldIframeTrack.finish()
                except:
                    pass
                owner._shieldIframeTrack = None
        
        if self.pulseTask:
            taskMgr.remove(self.pulseTask)
            self.pulseTask = None
        
        # Stop ring rotation tasks (both drone and owner unique names)
        taskMgr.remove(self.uniqueName('rotateRings'))
        if owner:
            taskMgr.remove(owner.uniqueName('shieldRotateRings'))
        self.ringRotationTask = None
        
        # Stop pulse task (both drone and owner unique names)
        if owner:
            taskMgr.remove(owner.uniqueName('shieldPulse'))
        
        # Stop particles
        if hasattr(self, 'shieldParticles') and self.shieldParticles:
            try:
                self.shieldParticles.softStop()
                self.shieldParticles.cleanup()
            except:
                pass
            self.shieldParticles = None
        
        # Remove collision node
        if self.shieldCollisionNode:
            try:
                if not self.shieldCollisionNode.isEmpty():
                    self.shieldCollisionNode.removeNode()
            except:
                pass
            self.shieldCollisionNode = None
        
        # Remove visual
        if self.shieldBubble:
            try:
                if not self.shieldBubble.isEmpty():
                    self.shieldBubble.removeNode()
            except:
                pass
            self.shieldBubble = None
        
        # Clear rings reference
        if hasattr(self, 'shieldRings'):
            self.shieldRings = None
        
        # Clear owner's shield references
        if owner:
            if hasattr(owner, '_shieldBubble'):
                owner._shieldBubble = None
            if hasattr(owner, '_shieldRings'):
                owner._shieldRings = None
            if hasattr(owner, '_shieldActive'):
                owner._shieldActive = False
    
    def vanishWithPoof(self, task=None):
        """Vanish the drone with a poof effect."""
        # Mark that drone has vanished
        self.droneVanished = True
        # Don't remove shield here - shield should only be removed when it expires or breaks
        # This method is called when the drone is destroyed, but shield should persist
        # Only vanish if we haven't already vanished
        if not self.isEmpty():
            return DistributedGoonDroneBase.vanishWithPoof(self, task)
        if task:
            return Task.done
    
    
    def disable(self):
        """Clean up when disabled."""
        # Don't remove shield here - shield should persist after drone vanishes
        # The shield will clean itself up when it expires or breaks
        # Only clean up drone-specific tasks, NOT owner-based shield tasks
        
        taskMgr.remove(self.uniqueName('activateShield'))
        taskMgr.remove(self.uniqueName('expireShield'))
        taskMgr.remove(self.uniqueName('vanishAfterBreak'))
        taskMgr.remove(self.uniqueName('vanishAfterExpire'))
        taskMgr.remove(self.uniqueName('vanishDrone'))
        taskMgr.remove(self.uniqueName('pulseShield'))
        taskMgr.remove(self.uniqueName('rotateRings'))
        
        # DO NOT remove owner-based tasks here - they should continue after drone is gone
        # They will be cleaned up in removeShieldBubble() when shield expires or breaks
        
        DistributedGoonDroneBase.disable(self)

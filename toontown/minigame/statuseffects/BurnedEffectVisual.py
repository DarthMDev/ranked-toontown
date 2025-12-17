"""
Visual effect for the BURNED status effect.

Creates animated fire/flame particles around the object.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, NodePath
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import Sequence, Parallel, LerpColorScaleInterval, Wait, Func
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase


class BurnedEffectVisual(StatusEffectVisualBase):
    """
    Visual for the BURNED status effect.
    
    Creates a particle effect with:
    - Orange/red flame particles rising from the object
    - Scaled appropriately to object size
    - Additive blending for glow effect
    - Orange/red glow on the object itself
    """
    
    def __init__(self, obj: NodePath, cr):
        """Initialize the burned effect visual."""
        super().__init__(obj, cr)
        self.particleEffect = None
        self.particles = None
        self.particlePos = None
        self.originalColorScales = {}  # Store original color scales for all parts
        self.glowInterval = None
        self.glowParts = []  # List of all parts that have glow applied
    
    def create(self):
        """Create the fire particle effect."""
        if self.active:
            return
            
        # Create root node for effect
        self._createEffectNode('burnedEffect')
        
        # Get object dimensions for scaling
        minPt, maxPt, center, height = self.objDimensions
        
        # Calculate width (X and Y dimensions) for objects that are wide
        widthX = maxPt.getX() - minPt.getX()
        widthY = maxPt.getY() - minPt.getY()
        avgWidth = (widthX + widthY) / 2.0
        
        # Debug logging
        self.notify.info(f"Creating burned effect for {self.obj.getName()}: height={height}, width={avgWidth}, minPt={minPt}, maxPt={maxPt}, center={center}")
        
        # Check if this is the CFO boss (pyramid-shaped, wide at bottom)
        isCFOBoss = False
        try:
            from toontown.suit import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying larger, wider fire effect")
        except:
            pass
        
        # Calculate scale factor based on object size
        # For CFO boss, use both height and width since it's pyramid-shaped
        if isCFOBoss:
            # CFO is ~26 units tall and very wide at base
            # Use a combination of height and width for proper scaling
            heightScale = height / 26.0  # Normalize to CFO's height
            widthScale = avgWidth / 20.0  # Normalize to approximate CFO base width
            # Use the larger of the two scales, but cap it reasonably
            baseScale = max(1.5, min(max(heightScale, widthScale) * 1.5, 3.0))
        else:
            # For other objects (safes), use height-based scaling
            baseScale = max(0.5, min(height / 3.0, 2.0))
        
        self.notify.info(f"Burned effect baseScale: {baseScale} (isCFO={isCFOBoss})")
        
        # Create the particle effect (don't parent it yet - start() will handle that)
        self.particleEffect = ParticleEffect.ParticleEffect('BurnedFlames')
        
        # Store the desired position for later - position at object base in local space
        # Since effectNode is attached to obj, we use local coordinates
        # Position slightly above the base (minPt.getZ() in world becomes ~0 in local, so use small offset)
        baseOffset = 0.1  # Small offset above base
        self.particlePos = Point3(0, 0, baseOffset)
        
        # Create particles
        self.particles = Particles.Particles('flames')
        self.particles.setFactory('PointParticleFactory')
        self.particles.setRenderer('SpriteParticleRenderer')
        self.particles.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.particles)
        
        # Configure particle pool - more particles for larger objects
        # CFO boss needs significantly more particles due to its size
        if isCFOBoss:
            poolSize = int(200 * baseScale)  # Much more particles for CFO
            birthRate = 0.015  # Even faster for CFO
            litterSize = 8  # More particles per spawn for CFO
        else:
            poolSize = int(100 * baseScale)
            birthRate = 0.02
            litterSize = 5
        
        self.particles.setPoolSize(poolSize)
        self.particles.setBirthRate(birthRate)
        self.particles.setLitterSize(litterSize)
        self.particles.setLitterSpread(2)
        
        # Configure factory (particle properties)
        # CFO needs longer lifespan so flames can reach the top of the tall body
        if isCFOBoss:
            lifespanBase = 0.8 * baseScale  # Longer for CFO
        else:
            lifespanBase = 0.5 * baseScale  # Shorter for safes
        
        self.particles.factory.setLifespanBase(lifespanBase)
        self.particles.factory.setLifespanSpread(0.2)
        self.particles.factory.setMassBase(1.0)
        self.particles.factory.setMassSpread(0.2)
        self.particles.factory.setTerminalVelocityBase(400.0)
        self.particles.factory.setTerminalVelocitySpread(50.0)
        
        # Configure renderer (how particles look)
        # Try PRALPHANONE (3) which uses texture alpha channel directly
        # If that doesn't work, the texture itself may have a solid background
        self.particles.renderer.setAlphaMode(3)  # PRALPHANONE - use texture alpha channel
        self.particles.renderer.setUserAlpha(1.0)
        self.particles.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR - linear alpha blending
        self.particles.renderer.setAlphaDisable(0)  # Enable alpha blending for transparency
        
        # Load proper fire texture - use setTextureFromNode like the original fire particle file
        try:
            # Use the actual fire texture from suit particles
            # This method directly loads the texture without needing to load the model first
            self.particles.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/fire")
            self.notify.info("Loaded fire texture for burned effect")
        except Exception as e:
            import traceback
            self.notify.warning(f"Could not load fire texture: {e}")
            self.notify.warning(traceback.format_exc())
        
        # Set colors - use white so the fire texture shows through properly
        # The texture itself provides the orange/red fire color
        self.particles.renderer.setColor(Vec4(1.0, 1.0, 1.0, 1.0))  # White to let texture show through
        
        # Scale particles based on object size
        # CFO boss needs much larger particles to be visible
        if isCFOBoss:
            # Much larger particles for CFO to match its massive size
            particleBaseScale = max(0.4, 0.6 * baseScale)
        else:
            # Smaller particles for safes
            particleBaseScale = max(0.15, 0.25 * baseScale)
        
        self.particles.renderer.setInitialXScale(particleBaseScale * 0.6)
        self.particles.renderer.setFinalXScale(particleBaseScale * 0.8)
        self.particles.renderer.setInitialYScale(particleBaseScale * 0.8)  # Taller flames
        self.particles.renderer.setFinalYScale(particleBaseScale * 1.5)
        self.particles.renderer.setXScaleFlag(True)  # Enable scaling
        self.particles.renderer.setYScaleFlag(True)
        self.particles.renderer.setIgnoreScale(False)  # Don't ignore scale
        
        # Configure emitter (where particles spawn)
        self.particles.emitter.setEmissionType(1)  # ETRADIATE - particles radiate outward
        # Emit from a sphere volume at the base of the object
        # CFO boss needs a much wider emitter to match its pyramid base
        if isCFOBoss:
            # Use average width to account for CFO's wide base
            # CFO base is very wide, so use a larger portion of the width
            emitterRadius = max(2.0, avgWidth / 2.0 * 0.8)  # Much wider for CFO
            amplitude = 2.0 * baseScale  # Stronger for CFO
        else:
            # For safes, use X width
            emitterRadius = max(0.4, (maxPt.getX() - minPt.getX()) / 2.0) * 0.6
            amplitude = 1.5 * baseScale
        
        self.particles.emitter.setRadius(emitterRadius)
        self.particles.emitter.setAmplitude(amplitude)
        self.particles.emitter.setAmplitudeSpread(0.5)
        # Add upward offset force to make flames rise from base
        # CFO needs stronger upward force due to its height
        if isCFOBoss:
            offsetForceZ = 4.0 * baseScale  # Stronger for CFO
            upwardForceZ = 7.0 * baseScale  # Much stronger for CFO
        else:
            offsetForceZ = 3.0 * baseScale
            upwardForceZ = 5.0 * baseScale
        
        self.particles.emitter.setOffsetForce(Vec3(0.0, 0.0, offsetForceZ))
        
        # Add upward force to make flames rise
        forceGroup = ForceGroup.ForceGroup('flameRise')
        upwardForce = LinearVectorForce(Vec3(0.0, 0.0, upwardForceZ), 1.0, 0)
        upwardForce.setActive(True)
        forceGroup.addForce(upwardForce)
        self.particleEffect.addForceGroup(forceGroup)
        
        # Set rendering properties for fire glow
        self.effectNode.setLightOff()
        self.effectNode.setFogOff()
        self.effectNode.setDepthWrite(False)
        self.effectNode.setBin('fixed', 0)
        self.effectNode.setTransparency(1)  # Enable transparency on the effect node
        # Additive blending for fire glow
        self.effectNode.setAttrib(ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd,
            ColorBlendAttrib.OIncomingAlpha,
            ColorBlendAttrib.OOne
        ))
        
        self.active = True
        
    def _getAllParts(self):
        """Get all parts of the object that should have glow applied."""
        # Apply glow to the object as a whole - color scales are inherited by child nodes
        # This ensures consistent tinting across all parts (including CFO's legs, torso, head, treads)
        return [self.obj]
    
    def _isFlashRedActive(self):
        """Check if flashRed() is currently active on the object."""
        try:
            # Check if the object has a flashInterval that's active
            if hasattr(self.obj, 'flashInterval') and self.obj.flashInterval:
                # Check if the interval is still playing
                if hasattr(self.obj.flashInterval, 'isPlaying'):
                    return self.obj.flashInterval.isPlaying()
                # If we can't check, assume it might be active if it exists
                return True
        except:
            pass
        return False
    
    def _applyGlow(self):
        """Apply orange/red glow effect to the object using multiplicative color scale."""
        if not self.obj or self.obj.isEmpty():
            return
        
        try:
            # Get all parts that need glow
            parts = self._getAllParts()
            self.glowParts = []
            
            # Store original color scales and apply glow to each part
            for part in parts:
                if part and not part.isEmpty():
                    # Store original color scale (only if not already stored)
                    partId = id(part)
                    if partId not in self.originalColorScales:
                        currentColor = part.getColorScale()
                        # Validate the color is reasonable before storing
                        # Check for corrupted colors (extremely high values, negative, etc.)
                        if (0.0 <= currentColor.getX() <= 2.0 and 
                            0.0 <= currentColor.getY() <= 2.0 and 
                            0.0 <= currentColor.getZ() <= 2.0 and 
                            0.0 <= currentColor.getW() <= 2.0):
                            # Check if color looks like it's from flashRed (red or white)
                            isRed = (currentColor.getX() > 0.8 and 
                                    currentColor.getY() < 0.3 and 
                                    currentColor.getZ() < 0.3)
                            isWhite = (abs(currentColor.getX() - 1.0) < 0.1 and 
                                      abs(currentColor.getY() - 1.0) < 0.1 and 
                                      abs(currentColor.getZ() - 1.0) < 0.1)
                            
                            # If color is from flashRed, wait a moment for it to finish
                            if isRed or (isWhite and self._isFlashRedActive()):
                                # flashRed is active, use white as base (flashRed ends at white)
                                self.originalColorScales[partId] = Vec4(1.0, 1.0, 1.0, 1.0)
                            else:
                                # Store the actual current color
                                self.originalColorScales[partId] = currentColor
                        else:
                            # Color is corrupted, use default white
                            self.notify.warning(f"Detected corrupted color when applying glow: {currentColor}, using default")
                            self.originalColorScales[partId] = Vec4(1.0, 1.0, 1.0, 1.0)
                    
                    # Get original color scale
                    originalColor = self.originalColorScales[partId]
                    
                    # Apply multiplicative glow - multiply existing color by orange tint
                    # This preserves the original color while adding orange glow
                    glowMultiplier = Vec4(1.0, 0.75, 0.4, 1.0)  # Orange tint
                    newColor = Vec4(
                        originalColor.getX() * glowMultiplier.getX(),
                        originalColor.getY() * glowMultiplier.getY(),
                        originalColor.getZ() * glowMultiplier.getZ(),
                        originalColor.getW() * glowMultiplier.getW()  # Preserve alpha
                    )
                    part.setColorScale(newColor)
                    self.glowParts.append(part)
            
            # Create pulsing glow effect for all parts
            # Pulse between orange and slightly dark orange
            brightMultiplier = Vec4(1.05, 0.8, 0.45, 1.0)  # Orange
            dimMultiplier = Vec4(0.95, 0.65, 0.3, 1.0)  # Slightly dark orange
            
            # Create pulsing intervals - all parts pulse together
            # Phase 1: All parts brighten together
            brightIntervals = []
            dimIntervals = []
            returnIntervals = []
            
            for part in self.glowParts:
                if part and not part.isEmpty():
                    partId = id(part)
                    originalColor = self.originalColorScales[partId]
                    currentColor = part.getColorScale()
                    
                    brightColor = Vec4(
                        originalColor.getX() * brightMultiplier.getX(),
                        originalColor.getY() * brightMultiplier.getY(),
                        originalColor.getZ() * brightMultiplier.getZ(),
                        originalColor.getW() * brightMultiplier.getW()
                    )
                    dimColor = Vec4(
                        originalColor.getX() * dimMultiplier.getX(),
                        originalColor.getY() * dimMultiplier.getY(),
                        originalColor.getZ() * dimMultiplier.getZ(),
                        originalColor.getW() * dimMultiplier.getW()
                    )
                    
                    brightIntervals.append(LerpColorScaleInterval(part, 0.5, brightColor, currentColor))
                    dimIntervals.append(LerpColorScaleInterval(part, 0.5, dimColor, brightColor))
                    returnIntervals.append(LerpColorScaleInterval(part, 0.5, currentColor, dimColor))
            
            # Create sequence: all brighten -> all dim -> all return to base
            if brightIntervals and dimIntervals and returnIntervals:
                self.glowInterval = Sequence(
                    Parallel(*brightIntervals),
                    Parallel(*dimIntervals),
                    Parallel(*returnIntervals)
                )
                self.glowInterval.loop()
            
        except Exception as e:
            self.notify.warning(f"Error applying glow effect: {e}")
    
    def _fadeOutGlow(self):
        """Fade out the glow effect gradually."""
        if not self.obj or self.obj.isEmpty():
            return
        
        try:
            # Stop the pulsing interval
            if self.glowInterval:
                self.glowInterval.finish()
                self.glowInterval = None
            
            # Check if flashRed is active - if so, wait for it to finish
            if self._isFlashRedActive():
                # flashRed takes 0.4 seconds total (0.1 red + 0.3 fade to white)
                # Wait a bit longer to be safe, then restore our original color
                taskMgr.doMethodLater(0.5, self._removeGlow, self.uniqueName('fadeOutGlow'))
                return
            
            # Fade all parts back to original color scales
            intervals = []
            for part in self.glowParts:
                if part and not part.isEmpty():
                    partId = id(part)
                    if partId in self.originalColorScales:
                        currentColor = part.getColorScale()
                        targetColor = self.originalColorScales[partId]
                        intervals.append(LerpColorScaleInterval(part, 0.5, targetColor, currentColor))
            
            if intervals:
                fadeInterval = Parallel(*intervals)
                fadeInterval.start()
            
            # Schedule removal after fade completes
            taskMgr.doMethodLater(0.5, self._removeGlow, self.uniqueName('fadeOutGlow'))
            
        except Exception as e:
            self.notify.warning(f"Error fading out glow effect: {e}")
            # Fallback to immediate removal
            self._removeGlow()
    
    def _removeGlow(self, task=None):
        """Remove the glow effect from all parts."""
        if not self.obj or self.obj.isEmpty():
            return task.done if task else None
        
        try:
            # Stop the pulsing interval if still running
            if self.glowInterval:
                self.glowInterval.finish()
                self.glowInterval = None
            
            # Check if flashRed is still active - if so, wait a bit more
            if self._isFlashRedActive():
                # flashRed might still be running, wait a bit more
                taskMgr.doMethodLater(0.2, self._removeGlow, self.uniqueName('fadeOutGlow'))
                return task.done if task else None
            
            # Restore original color scales for all parts
            # But first, check current color to avoid conflicts
            for part in self.glowParts:
                if part and not part.isEmpty():
                    partId = id(part)
                    if partId in self.originalColorScales:
                        try:
                            currentColor = part.getColorScale()
                            originalColor = self.originalColorScales[partId]
                            
                            # If current color looks like it's from flashRed (red tint or white),
                            # we should restore to original after a brief delay to let flashRed finish
                            # Check if color is close to white (1,1,1) or red (high red, low green/blue)
                            isWhite = (abs(currentColor.getX() - 1.0) < 0.1 and 
                                      abs(currentColor.getY() - 1.0) < 0.1 and 
                                      abs(currentColor.getZ() - 1.0) < 0.1)
                            isRed = (currentColor.getX() > 0.8 and 
                                    currentColor.getY() < 0.3 and 
                                    currentColor.getZ() < 0.3)
                            
                            # If color looks like it's from flashRed, restore immediately
                            # (flashRed should have finished by now if we waited)
                            if isWhite or isRed:
                                # Restore to original - flashRed should be done
                                part.setColorScale(originalColor)
                            else:
                                # Color might be from our glow or something else, restore normally
                                part.setColorScale(originalColor)
                        except Exception as e:
                            self.notify.warning(f"Error restoring color scale for part: {e}")
                            # Fallback: set to white to avoid stuck colors
                            try:
                                part.setColorScale(Vec4(1.0, 1.0, 1.0, 1.0))
                            except:
                                pass
            
            # Clear stored data
            self.originalColorScales.clear()
            self.glowParts = []
            
        except Exception as e:
            self.notify.warning(f"Error removing glow effect: {e}")
            # Last resort: try to set to white to avoid stuck colors
            try:
                if self.obj and not self.obj.isEmpty():
                    self.obj.setColorScale(Vec4(1.0, 1.0, 1.0, 1.0))
            except:
                pass
        
        return task.done if task else None
        
    def start(self):
        """Start the particle effect."""
        if not self.active:
            self.create()
        
        # Apply glow to the object
        self._applyGlow()
        
        if self.particleEffect:
            # Start the particle effect with proper parent and render nodes
            # parent is where the effect is positioned (effectNode)
            # renderParent is the coordinate system for physics (render)
            self.particleEffect.start(parent=self.effectNode, renderParent=render)
            
            # Set the stored position
            if hasattr(self, 'particlePos'):
                self.particleEffect.setPos(self.particlePos)
    
    def stop(self):
        """Stop the particle effect without destroying it."""
        if self.particleEffect:
            try:
                # Soft stop allows the particles to fade out naturally
                # Don't disable particles immediately - let them fade out
                self.particleEffect.softStop()
            except Exception as e:
                self.notify.warning(f"Error stopping particle effect: {e}")
    
    def gracefulCleanup(self):
        """
        Gracefully clean up the effect by stopping new particles but allowing
        existing particles to fade out naturally. Use this for natural effect removal.
        """
        if not self.active:
            return
        
        # Check if already cleaned up
        if not hasattr(self, 'particleEffect') or self.particleEffect is None:
            return
        
        # Stop spawning new particles but let existing ones fade out
        if hasattr(self, 'particles') and self.particles:
            try:
                # Stop spawning new particles
                self.particles.disableParticles()
            except Exception as e:
                self.notify.warning(f"Error disabling particles: {e}")
        
        # Soft stop the effect to let particles fade out
        if self.particleEffect:
            try:
                self.particleEffect.softStop()
            except Exception as e:
                self.notify.warning(f"Error soft stopping particle effect: {e}")
        
        # Mark as inactive but don't remove nodes yet
        self.active = False
        
        # Fade out the glow gradually
        self._fadeOutGlow()
        
        # Schedule actual cleanup after particles have time to fade out
        # Use the longest particle lifespan to ensure all particles fade
        maxLifespan = 1.0  # Maximum expected particle lifespan
        if hasattr(self, 'particles') and self.particles:
            try:
                # Get the actual lifespan from the factory
                lifespanBase = self.particles.factory.getLifespanBase()
                lifespanSpread = self.particles.factory.getLifespanSpread()
                maxLifespan = lifespanBase + lifespanSpread
            except:
                pass
        
        # Clean up after particles have faded (add small buffer)
        cleanupDelay = maxLifespan + 0.5
        taskMgr.doMethodLater(cleanupDelay, self._delayedCleanup, self.uniqueName('gracefulCleanup'))
    
    def _delayedCleanup(self, task):
        """Actually remove the nodes after particles have faded out."""
        # Check if cleanup was already called (nodes might already be removed)
        if not hasattr(self, 'particleEffect') or self.particleEffect is None:
            return task.done
        
        # Ensure glow is removed
        self._removeGlow()
        
        if self.particleEffect:
            try:
                self.particleEffect.cleanup()
                if not self.particleEffect.isEmpty():
                    self.particleEffect.detachNode()
                    self.particleEffect.removeNode()
            except Exception as e:
                self.notify.warning(f"Error during delayed cleanup: {e}")
            self.particleEffect = None
        
        if hasattr(self, 'particles'):
            self.particles = None
        
        if self.effectNode and not self.effectNode.isEmpty():
            try:
                self.effectNode.detachNode()
                self.effectNode.removeNode()
            except Exception as e:
                self.notify.warning(f"Error removing effect node in delayed cleanup: {e}")
            self.effectNode = None
        
        return task.done
    
    def uniqueName(self, name):
        """Generate a unique task name for this effect."""
        if hasattr(self, 'obj') and self.obj:
            return f'burnedEffect-{self.obj.getDoId()}-{name}'
        return f'burnedEffect-{name}'
    
    def cleanup(self, force=False):
        """
        Completely clean up the effect immediately.
        Use force=True for game end/restart scenarios.
        """
        # Cancel any pending graceful cleanup
        taskMgr.remove(self.uniqueName('gracefulCleanup'))
        taskMgr.remove(self.uniqueName('fadeOutGlow'))
        
        # Remove glow immediately
        self._removeGlow()
        
        # Stop first to prevent new particles from spawning
        self.stop()
        
        if hasattr(self, 'particles') and self.particles:
            try:
                # Explicitly disable particles first to stop spawning
                self.particles.disableParticles()
                # Clear the particles
                self.particles = None
            except Exception as e:
                self.notify.warning(f"Error disabling particles: {e}")
        
        if hasattr(self, 'particleEffect') and self.particleEffect:
            try:
                # Force disable the particle effect
                self.particleEffect.disable()
                # Cleanup the particle effect completely
                self.particleEffect.cleanup()
                # Remove from scene graph - detach from parent first
                if not self.particleEffect.isEmpty():
                    self.particleEffect.detachNode()
                    self.particleEffect.removeNode()
            except Exception as e:
                self.notify.warning(f"Error during particle effect cleanup: {e}")
            self.particleEffect = None
            
        if self.effectNode and not self.effectNode.isEmpty():
            try:
                # Detach from parent first, then remove
                self.effectNode.detachNode()
                self.effectNode.removeNode()
            except Exception as e:
                self.notify.warning(f"Error removing effect node: {e}")
            self.effectNode = None
            
        self.active = False
    
    def updateStack(self, stackCount: int):
        """Update flame intensity based on stack count."""
        super().updateStack(stackCount)
        
        if not self.active or not self.particles:
            return
        
        # Increase birth rate for more stacks (more intense flames)
        baseBirthRate = 0.05
        self.particles.setBirthRate(baseBirthRate / max(1, stackCount))
        
        # Optionally increase color intensity
        if stackCount >= 2:
            # More stacks = redder/hotter flames
            redIntensity = min(1.0, 0.8 + (stackCount * 0.1))
            self.particles.renderer.setColor(Vec4(redIntensity, 0.6, 0.2, 1.0))


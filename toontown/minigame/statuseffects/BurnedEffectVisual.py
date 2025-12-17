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
    - Pulsing orange/red aura glow around the object
    - Scaled appropriately to object size
    - Additive blending for glow effect
    """
    
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
        
        # Create aura glow effect
        self._createAuraGlow(minPt, maxPt, center, height, avgWidth, isCFOBoss, baseScale)
        
        self.active = True
    
    def _createAuraGlow(self, minPt, maxPt, center, height, avgWidth, isCFOBoss, baseScale):
        """Create a pulsing orange/red aura glow around the object."""
        try:
            # Load the glow texture from particle cards
            glowModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
            if glowModel.isEmpty():
                self.notify.warning("Could not load glow model for aura effect")
                return
            
            # Get the white glow texture
            self.glowCard = glowModel.find('**/tt_t_efx_ext_particleWhiteGlow')
            if self.glowCard.isEmpty():
                self.notify.warning("Could not find glow texture in model")
                return
            
            # Create a node for the glow effect
            self.glowNode = self.effectNode.attachNewNode('auraGlow')
            
            # Reparent the glow card to our glow node
            self.glowCard.reparentTo(self.glowNode)
            self.glowCard.setBillboardAxis(0)  # Billboard always faces camera
            
            # Calculate glow size based on object dimensions
            # Make it slightly larger than the object to create an aura effect
            if isCFOBoss:
                # CFO is wide, so use average width and height
                glowSize = max(avgWidth, height) * 1.8  # 30% larger than object
            else:
                # For safes, use the larger dimension
                glowSize = max(avgWidth, height) * 1.6  # 40% larger than object
            
            # Scale the glow card
            self.glowCard.setScale(glowSize)
            
            # Position at object center (in local space, center is relative to effectNode)
            # effectNode is attached to obj, so center is already at origin
            self.glowNode.setPos(0, 0, height / 2.2)  # Center vertically
            
            # Set up rendering properties for additive glow
            self.glowNode.setAttrib(ColorBlendAttrib.make(
                ColorBlendAttrib.MAdd,
                ColorBlendAttrib.OIncomingAlpha,
                ColorBlendAttrib.OOne
            ))
            self.glowNode.setBillboardPointWorld()  # Always face camera
            self.glowNode.setDepthWrite(False)
            self.glowNode.setLightOff()
            self.glowNode.setFogOff()
            self.glowNode.setTransparency(True)
            self.glowNode.setBin('fixed', 0)
            
            # Set initial orange/red color
            # Orange-red: high red, medium orange, low blue
            self.glowBaseColor = Vec4(1.0, 0.5, 0.1, 0.6)  # Base orange-red with moderate alpha
            self.glowBrightColor = Vec4(1.0, 0.6, 0.15, 0.8)  # Brighter orange-red
            self.glowDimColor = Vec4(0.9, 0.4, 0.05, 0.5)  # Dimmer orange-red
            
            # Start at transparent - will fade in when effect starts
            self.glowCard.setColorScale(Vec4(1.0, 0.5, 0.1, 0.0))  # Transparent initially
            
            # Create pulsing animation (will start after fade-in)
            # Pulse between bright and dim orange-red
            self.glowPulseInterval = Sequence(
                LerpColorScaleInterval(self.glowCard, 0.6, self.glowBrightColor, self.glowBaseColor),
                LerpColorScaleInterval(self.glowCard, 0.6, self.glowDimColor, self.glowBrightColor),
                LerpColorScaleInterval(self.glowCard, 0.6, self.glowBaseColor, self.glowDimColor)
            )
            # Don't start pulsing yet - wait for fade-in
            self.glowPulseInterval.pause()
            
            self.notify.info(f"Created aura glow effect: size={glowSize}, isCFO={isCFOBoss}")
            
        except Exception as e:
            import traceback
            self.notify.warning(f"Error creating aura glow: {e}")
            self.notify.warning(traceback.format_exc())
            # Set to None so cleanup doesn't fail
            if not hasattr(self, 'glowNode'):
                self.glowNode = None
            if not hasattr(self, 'glowCard'):
                self.glowCard = None
            if not hasattr(self, 'glowPulseInterval'):
                self.glowPulseInterval = None
        
    def start(self):
        """Start the particle effect."""
        if not self.active:
            self.create()
        
        if self.particleEffect:
            # Start the particle effect with proper parent and render nodes
            # parent is where the effect is positioned (effectNode)
            # renderParent is the coordinate system for physics (render)
            self.particleEffect.start(parent=self.effectNode, renderParent=render)
            
            # Set the stored position
            if hasattr(self, 'particlePos'):
                self.particleEffect.setPos(self.particlePos)
        
        # Fade in the aura glow
        self._fadeInAuraGlow()
    
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
        
        # Fade out the aura glow first
        self._fadeOutAuraGlow()
        
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
    
    def _fadeInAuraGlow(self):
        """Fade in the aura glow gradually."""
        if not hasattr(self, 'glowCard') or self.glowCard is None or self.glowCard.isEmpty():
            return
        
        try:
            # Get current color
            currentColor = self.glowCard.getColorScale()
            currentAlpha = currentColor.getW()
            
            # If already visible (alpha > 0.1), don't fade in again
            if currentAlpha > 0.1:
                # Just make sure pulsing is running
                if hasattr(self, 'glowPulseInterval') and self.glowPulseInterval:
                    if not self.glowPulseInterval.isPlaying():
                        self.glowPulseInterval.loop()
                return
            
            # Fade in from transparent to base color
            fadeIn = LerpColorScaleInterval(
                self.glowCard,
                0.5,  # Fade in over 0.5 seconds
                self.glowBaseColor,  # Fade to base color
                currentColor  # Start from current (transparent)
            )
            
            # After fade-in completes, start the pulsing animation
            def startPulsing():
                if hasattr(self, 'glowPulseInterval') and self.glowPulseInterval:
                    try:
                        self.glowPulseInterval.loop()
                    except:
                        pass
            
            # Create sequence: fade in, then start pulsing
            fadeInSequence = Sequence(
                fadeIn,
                Func(startPulsing)
            )
            fadeInSequence.start()
            
        except Exception as e:
            self.notify.warning(f"Error fading in aura glow: {e}")
            # Fallback: just start pulsing if fade-in fails
            if hasattr(self, 'glowPulseInterval') and self.glowPulseInterval:
                try:
                    self.glowCard.setColorScale(self.glowBaseColor)
                    self.glowPulseInterval.loop()
                except:
                    pass
    
    def _fadeOutAuraGlow(self):
        """Fade out the aura glow gradually."""
        if not hasattr(self, 'glowPulseInterval') or self.glowPulseInterval is None:
            return
        
        try:
            # Stop the pulsing animation
            if self.glowPulseInterval:
                self.glowPulseInterval.finish()
                self.glowPulseInterval = None
            
            # Fade out the glow to transparent
            if hasattr(self, 'glowCard') and self.glowCard and not self.glowCard.isEmpty():
                currentColor = self.glowCard.getColorScale()
                fadeOut = LerpColorScaleInterval(
                    self.glowCard,
                    0.5,  # Fade out over 0.5 seconds
                    Vec4(currentColor.getX(), currentColor.getY(), currentColor.getZ(), 0.0),  # Fade to transparent
                    currentColor
                )
                fadeOut.start()
        except Exception as e:
            self.notify.warning(f"Error fading out aura glow: {e}")
    
    def _delayedCleanup(self, task):
        """Actually remove the nodes after particles have faded out."""
        # Check if cleanup was already called (nodes might already be removed)
        if not hasattr(self, 'particleEffect') or self.particleEffect is None:
            return task.done
        
        # Clean up aura glow
        if hasattr(self, 'glowNode') and self.glowNode and not self.glowNode.isEmpty():
            try:
                self.glowNode.detachNode()
                self.glowNode.removeNode()
            except Exception as e:
                self.notify.warning(f"Error removing glow node in delayed cleanup: {e}")
            self.glowNode = None
        
        if hasattr(self, 'glowCard'):
            self.glowCard = None
        
        if hasattr(self, 'glowPulseInterval') and self.glowPulseInterval:
            try:
                self.glowPulseInterval.finish()
            except:
                pass
            self.glowPulseInterval = None
        
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
        
        # Stop first to prevent new particles from spawning
        self.stop()
        
        # Immediately remove aura glow
        if hasattr(self, 'glowPulseInterval') and self.glowPulseInterval:
            try:
                self.glowPulseInterval.finish()
            except:
                pass
            self.glowPulseInterval = None
        
        if hasattr(self, 'glowNode') and self.glowNode and not self.glowNode.isEmpty():
            try:
                self.glowNode.detachNode()
                self.glowNode.removeNode()
            except Exception as e:
                self.notify.warning(f"Error removing glow node: {e}")
            self.glowNode = None
        
        if hasattr(self, 'glowCard'):
            self.glowCard = None
        
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
        """Update flame intensity and glow based on stack count."""
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
        
        # Increase aura glow intensity with stack count
        if hasattr(self, 'glowCard') and self.glowCard and not self.glowCard.isEmpty():
            try:
                # More stacks = brighter, more intense glow
                alphaMultiplier = min(1.0, 0.6 + (stackCount * 0.15))  # Increase alpha with stacks
                redMultiplier = min(1.0, 1.0 + (stackCount * 0.05))  # Slightly redder with more stacks
                
                # Update glow colors based on stack count
                self.glowBaseColor = Vec4(redMultiplier, 0.5, 0.1, 0.6 * alphaMultiplier)
                self.glowBrightColor = Vec4(redMultiplier, 0.6, 0.15, 0.8 * alphaMultiplier)
                self.glowDimColor = Vec4(0.9 * redMultiplier, 0.4, 0.05, 0.5 * alphaMultiplier)
                
                # Update current color if pulse interval is running
                if hasattr(self, 'glowPulseInterval') and self.glowPulseInterval:
                    # Restart pulse with new colors
                    if self.glowPulseInterval.isPlaying():
                        self.glowPulseInterval.finish()
                    self.glowPulseInterval = Sequence(
                        LerpColorScaleInterval(self.glowCard, 0.6, self.glowBrightColor, self.glowBaseColor),
                        LerpColorScaleInterval(self.glowCard, 0.6, self.glowDimColor, self.glowBrightColor),
                        LerpColorScaleInterval(self.glowCard, 0.6, self.glowBaseColor, self.glowDimColor)
                    )
                    self.glowPulseInterval.loop()
            except Exception as e:
                self.notify.warning(f"Error updating glow intensity: {e}")


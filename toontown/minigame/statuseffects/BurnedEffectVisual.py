"""
Visual effect for the BURNED status effect.

Creates animated fire/flame particles around the object.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import Sequence, LerpColorScaleInterval, Wait, Func
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase


class BurnedEffectVisual(StatusEffectVisualBase):
    """
    Visual for the BURNED status effect.
    
    Creates a particle effect with:
    - Orange/red flame particles rising from the object
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
        
        # Create glow aura particle effect for ambient glow around the object
        self.glowParticleEffect = ParticleEffect.ParticleEffect('BurnedGlowAura')
        
        # Position glow at object center (height/2) instead of base
        glowCenterOffset = height / 2.5
        self.glowParticlePos = Point3(0, 0, glowCenterOffset)
        
        self.glowParticles = Particles.Particles('glowAura')
        self.glowParticles.setFactory('PointParticleFactory')
        self.glowParticles.setRenderer('SpriteParticleRenderer')
        self.glowParticles.setEmitter('SphereVolumeEmitter')
        self.glowParticleEffect.addParticles(self.glowParticles)
        
        # Calculate object dimensions for glow sizing
        widthX = maxPt.getX() - minPt.getX()
        widthY = maxPt.getY() - minPt.getY()
        avgWidth = (widthX + widthY) / 2.0
        
        # Configure glow particles - slower, longer-lived particles for persistent aura
        if isCFOBoss:
            glowPoolSize = int(40 * baseScale)  # Reduced from 80 for less intensity
            glowBirthRate = 0.15  # Slower spawn rate for more subtle glow
            glowLitterSize = 2  # Reduced from 3
        else:
            glowPoolSize = int(50 * baseScale)
            glowBirthRate = 0.1
            glowLitterSize = 2
        
        self.glowParticles.setPoolSize(glowPoolSize)
        self.glowParticles.setBirthRate(glowBirthRate)
        self.glowParticles.setLitterSize(glowLitterSize)
        self.glowParticles.setLitterSpread(1)
        
        # Longer lifespan for persistent glow effect
        if isCFOBoss:
            glowLifespanBase = 1.5 * baseScale
        else:
            glowLifespanBase = 1.0 * baseScale
        
        self.glowParticles.factory.setLifespanBase(glowLifespanBase)
        self.glowParticles.factory.setLifespanSpread(0.3)
        self.glowParticles.factory.setMassBase(1.0)
        self.glowParticles.factory.setMassSpread(0.1)
        # Slower movement for subtle, ambient glow
        self.glowParticles.factory.setTerminalVelocityBase(50.0)
        self.glowParticles.factory.setTerminalVelocitySpread(20.0)
        
        # Configure glow renderer - use white glow texture with orange/red tint
        self.glowParticles.renderer.setAlphaMode(3)  # PRALPHANONE - use texture alpha
        self.glowParticles.renderer.setUserAlpha(1.0)
        self.glowParticles.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.glowParticles.renderer.setAlphaDisable(0)
        # Make particles always face camera (billboard)
        self.glowParticles.renderer.setAnimAngleFlag(1)  # Animate angle
        self.glowParticles.renderer.setNonanimatedTheta(0.0)  # Face camera
        
        # Load white glow texture - use the same method as GlowTrail
        # loader is available as a global in Panda3D (from ShowBase)
        try:
            # Try to access loader - it's typically available as a global
            try:
                # First try: use loader directly (global in Panda3D)
                glowModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
            except NameError:
                # Fallback: access via base
                from direct.showbase.ShowBase import ShowBase
                glowModel = base.loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
            
            if not glowModel.isEmpty():
                glowTemplate = glowModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                if not glowTemplate.isEmpty():
                    self.glowParticles.renderer.setFromNode(glowTemplate)
                    self.notify.info("Loaded white glow texture for aura effect")
                else:
                    self.notify.warning("Could not find white glow texture in model")
            else:
                self.notify.warning("Could not load glow model")
        except Exception as e:
            import traceback
            self.notify.warning(f"Could not load glow texture: {e}")
            self.notify.warning(traceback.format_exc())
        
        # Set orange/red glow color - bright but not overpowering
        # CFO gets less intense glow (lower alpha)
        if isCFOBoss:
            glowColor = Vec4(1.0, 0.6, 0.2, 0.4)  # Lower alpha for CFO (0.4 vs 0.7)
        else:
            glowColor = Vec4(1.0, 0.6, 0.2, 0.7)  # Normal intensity for safes
        self.glowParticles.renderer.setColor(glowColor)
        
        # Calculate glow size to surround the object
        if isCFOBoss:
            # CFO is wide and tall, use the larger dimension
            # Reduced scale for less intense glow
            glowSize = max(avgWidth, height)
            glowBaseScale = max(0.5, glowSize * 0.2)  # Reduced from 0.3 for less intensity
        else:
            # For safes, use the larger dimension
            glowSize = max(avgWidth, height)
            glowBaseScale = max(0.4, glowSize * 0.25)  # Scale to object size
        
        # Particles start smaller and grow slightly, then fade
        self.glowParticles.renderer.setInitialXScale(glowBaseScale * 0.8)
        self.glowParticles.renderer.setFinalXScale(glowBaseScale * 1.5)
        self.glowParticles.renderer.setInitialYScale(glowBaseScale * 0.8)
        self.glowParticles.renderer.setFinalYScale(glowBaseScale * 1.5)
        self.glowParticles.renderer.setXScaleFlag(True)  # Enable scaling
        self.glowParticles.renderer.setYScaleFlag(True)
        self.glowParticles.renderer.setIgnoreScale(False)
        
        # Configure glow emitter - sphere around object center
        self.glowParticles.emitter.setEmissionType(1)  # ETRADIATE - radiate outward
        # Emit from a sphere around the object center
        if isCFOBoss:
            # Larger radius for CFO to surround the whole body
            glowEmitterRadius = max(3.0, avgWidth / 2.0 * 0.6)
            glowAmplitude = 0.5 * baseScale  # Gentle movement
        else:
            # Smaller radius for safes
            glowEmitterRadius = max(1.0, avgWidth / 2.0 * 0.5)
            glowAmplitude = 0.3 * baseScale
        
        self.glowParticles.emitter.setRadius(glowEmitterRadius)
        self.glowParticles.emitter.setAmplitude(glowAmplitude)
        self.glowParticles.emitter.setAmplitudeSpread(0.2)
        # Very gentle upward drift
        self.glowParticles.emitter.setOffsetForce(Vec3(0.0, 0.0, 0.5 * baseScale))
        
        # Add gentle upward force for slow drift
        glowForceGroup = ForceGroup.ForceGroup('glowRise')
        glowUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, 1.0 * baseScale), 0.5, 0)
        glowUpwardForce.setActive(True)
        glowForceGroup.addForce(glowUpwardForce)
        self.glowParticleEffect.addForceGroup(glowForceGroup)
        
        self.notify.info(f"Created glow aura: size={glowBaseScale}, radius={glowEmitterRadius}, isCFO={isCFOBoss}")
        
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
        
        if hasattr(self, 'glowParticleEffect') and self.glowParticleEffect:
            # Start the glow particle effect at object center
            self.glowParticleEffect.start(parent=self.effectNode, renderParent=render)
            
            # Set the glow position at object center
            if hasattr(self, 'glowParticlePos'):
                self.glowParticleEffect.setPos(self.glowParticlePos)
    
    def stop(self):
        """Stop the particle effect without destroying it."""
        if self.particleEffect:
            try:
                # Soft stop allows the particles to fade out naturally
                # Don't disable particles immediately - let them fade out
                self.particleEffect.softStop()
            except Exception as e:
                self.notify.warning(f"Error stopping particle effect: {e}")
        
        if hasattr(self, 'glowParticleEffect') and self.glowParticleEffect:
            try:
                # Soft stop the glow effect
                self.glowParticleEffect.softStop()
            except Exception as e:
                self.notify.warning(f"Error stopping glow particle effect: {e}")
    
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
        
        # Stop spawning glow particles
        if hasattr(self, 'glowParticles') and self.glowParticles:
            try:
                # Stop spawning new glow particles
                self.glowParticles.disableParticles()
            except Exception as e:
                self.notify.warning(f"Error disabling glow particles: {e}")
        
        # Soft stop both effects to let particles fade out
        if self.particleEffect:
            try:
                self.particleEffect.softStop()
            except Exception as e:
                self.notify.warning(f"Error soft stopping particle effect: {e}")
        
        if hasattr(self, 'glowParticleEffect') and self.glowParticleEffect:
            try:
                self.glowParticleEffect.softStop()
            except Exception as e:
                self.notify.warning(f"Error soft stopping glow particle effect: {e}")
        
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
                maxLifespan = max(maxLifespan, lifespanBase + lifespanSpread)
            except:
                pass
        
        # Also check glow particles lifespan
        if hasattr(self, 'glowParticles') and self.glowParticles:
            try:
                glowLifespanBase = self.glowParticles.factory.getLifespanBase()
                glowLifespanSpread = self.glowParticles.factory.getLifespanSpread()
                maxLifespan = max(maxLifespan, glowLifespanBase + glowLifespanSpread)
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
        
        if self.particleEffect:
            try:
                self.particleEffect.cleanup()
                if not self.particleEffect.isEmpty():
                    self.particleEffect.detachNode()
                    self.particleEffect.removeNode()
            except Exception as e:
                self.notify.warning(f"Error during delayed cleanup: {e}")
            self.particleEffect = None
        
        if hasattr(self, 'glowParticleEffect') and self.glowParticleEffect:
            try:
                self.glowParticleEffect.cleanup()
                if not self.glowParticleEffect.isEmpty():
                    self.glowParticleEffect.detachNode()
                    self.glowParticleEffect.removeNode()
            except Exception as e:
                self.notify.warning(f"Error during delayed glow cleanup: {e}")
            self.glowParticleEffect = None
        
        if hasattr(self, 'particles'):
            self.particles = None
        
        if hasattr(self, 'glowParticles'):
            self.glowParticles = None
        
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
        
        if hasattr(self, 'particles') and self.particles:
            try:
                # Explicitly disable particles first to stop spawning
                self.particles.disableParticles()
                # Clear the particles
                self.particles = None
            except Exception as e:
                self.notify.warning(f"Error disabling particles: {e}")
        
        if hasattr(self, 'glowParticles') and self.glowParticles:
            try:
                # Explicitly disable glow particles
                self.glowParticles.disableParticles()
                self.glowParticles = None
            except Exception as e:
                self.notify.warning(f"Error disabling glow particles: {e}")
        
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
        
        if hasattr(self, 'glowParticleEffect') and self.glowParticleEffect:
            try:
                # Force disable the glow particle effect
                self.glowParticleEffect.disable()
                # Cleanup the glow particle effect completely
                self.glowParticleEffect.cleanup()
                # Remove from scene graph
                if not self.glowParticleEffect.isEmpty():
                    self.glowParticleEffect.detachNode()
                    self.glowParticleEffect.removeNode()
            except Exception as e:
                self.notify.warning(f"Error during glow particle effect cleanup: {e}")
            self.glowParticleEffect = None
            
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


"""
Visual effect for the GROUNDED status effect.

Creates animated earth/dirt particles and dust clouds around the object.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, VBase4
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import Sequence, LerpColorScaleInterval, Wait, Func
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase


class GroundedEffectVisual(StatusEffectVisualBase):
    """
    Visual for the GROUNDED status effect.
    
    Creates a particle effect with:
    - Brown/tan dust clouds around the object
    - Earthy particles settling downward
    - Scaled appropriately to object size
    """
    
    def create(self):
        """Create the earth/dirt particle effect."""
        if self.active:
            return
            
        # Create root node for effect
        self._createEffectNode('groundedEffect')
        
        # Get object dimensions for scaling
        minPt, maxPt, center, height = self.objDimensions
        
        # Calculate width (X and Y dimensions) for objects that are wide
        widthX = maxPt.getX() - minPt.getX()
        widthY = maxPt.getY() - minPt.getY()
        avgWidth = (widthX + widthY) / 2.0
        
        # Debug logging
        self.notify.info(f"Creating grounded effect for {self.obj.getName()}: height={height}, width={avgWidth}, minPt={minPt}, maxPt={maxPt}, center={center}")
        
        # Check if this is the CFO boss (pyramid-shaped, wide at bottom)
        isCFOBoss = False
        isSafe = False
        try:
            from toontown.suit import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying larger, wider earth effect")
            else:
                # Check if this is a safe (not CFO)
                from toontown.coghq import DistributedCashbotBossSafe
                if isinstance(self.obj, DistributedCashbotBossSafe.DistributedCashbotBossSafe):
                    isSafe = True
                    self.notify.info("Detected safe - will apply brown/tan glow color")
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
        
        self.notify.info(f"Grounded effect baseScale: {baseScale} (isCFO={isCFOBoss})")
        
        # Create a renderParent node for particle physics with proper depth settings
        # This ensures particles don't occlude other objects
        self.particleRenderParent = render.attachNewNode('groundedParticleRenderParent')
        self.particleRenderParent.setBin('fixed', -50)  # Lower priority than damage numbers
        self.particleRenderParent.setDepthWrite(False)  # Don't write to depth (won't occlude things behind)
        # Keep depthTest enabled (default) so particles respect depth for proper rendering
        self.particleRenderParent.setLightOff()
        self.particleRenderParent.setFogOff()
        
        # Create the particle effect (don't parent it yet - start() will handle that)
        self.particleEffect = ParticleEffect.ParticleEffect('GroundedEarth')
        
        # Store the desired position for later - position at object base in local space
        # Since effectNode is attached to obj, we use local coordinates
        # Position slightly above the base (minPt.getZ() in world becomes ~0 in local, so use small offset)
        baseOffset = 0.1  # Small offset above base
        self.particlePos = Point3(0, 0, baseOffset)
        
        # ===== LAYER 1: DUST CLOUDS (Floating brown dust) =====
        self.dustClouds = Particles.Particles('dustClouds')
        self.dustClouds.setFactory('PointParticleFactory')
        self.dustClouds.setRenderer('SpriteParticleRenderer')
        self.dustClouds.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.dustClouds)
        
        # ===== LAYER 2: EARTH PARTICLES (Small settling particles) =====
        self.earthParticles = Particles.Particles('earthParticles')
        self.earthParticles.setFactory('PointParticleFactory')
        self.earthParticles.setRenderer('SpriteParticleRenderer')
        self.earthParticles.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.earthParticles)
        
        # Calculate emitter settings
        if isCFOBoss:
            emitterRadius = max(2.0, avgWidth / 2.0 * 0.8)
            amplitude = 1.5 * baseScale
            downwardForceZ = -3.0 * baseScale  # Downward force for falling particles
            dustRiseZ = 0.5 * baseScale  # Dust rises slightly
        else:
            # Wider spread for safes - use larger multiplier for radius to ensure particles spawn around the safe
            emitterRadius = max(0.8, (maxPt.getX() - minPt.getX()) / 2.0) * 1.5  # Increased from 0.8 to 1.5 for wider spread
            amplitude = 1.0 * baseScale
            downwardForceZ = -2.0 * baseScale
            dustRiseZ = 0.3 * baseScale
        
        # ===== CONFIGURE DUST CLOUDS (Floating brown dust) =====
        if isCFOBoss:
            dustPoolSize = int(80 * baseScale)
            dustBirthRate = 0.04
            dustLitterSize = 3
            dustLifespan = 1.5 * baseScale
            dustScale = max(0.3, 0.5 * baseScale)
        else:
            dustPoolSize = int(40 * baseScale)
            dustBirthRate = 0.06
            dustLitterSize = 2
            dustLifespan = 1.2 * baseScale
            dustScale = max(0.2, 0.35 * baseScale)
        
        self.dustClouds.setPoolSize(dustPoolSize)
        self.dustClouds.setBirthRate(dustBirthRate)
        self.dustClouds.setLitterSize(dustLitterSize)
        self.dustClouds.setLitterSpread(1)
        self.dustClouds.factory.setLifespanBase(dustLifespan)
        self.dustClouds.factory.setLifespanSpread(0.4)
        self.dustClouds.factory.setMassBase(0.3)  # Light for floating
        self.dustClouds.factory.setMassSpread(0.15)
        self.dustClouds.factory.setTerminalVelocityBase(120.0)  # Slow floating
        self.dustClouds.factory.setTerminalVelocitySpread(40.0)
        
        # Dust clouds renderer - earthy brown/tan
        self.dustClouds.renderer.setAlphaMode(3)  # PRALPHANONE
        self.dustClouds.renderer.setUserAlpha(1.0)
        self.dustClouds.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.dustClouds.renderer.setAlphaDisable(0)
        self.dustClouds.renderer.setAnimAngleFlag(1)  # Animated for dust
        self.dustClouds.renderer.setNonanimatedTheta(0.0)
        
        # Try to load smoke or white glow texture for dust
        try:
            # Try smoke texture first (good for dust clouds)
            try:
                smokeModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
                if not smokeModel.isEmpty():
                    smokeTemplate = smokeModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                    if not smokeTemplate.isEmpty():
                        self.dustClouds.renderer.setFromNode(smokeTemplate)
            except:
                # Fallback to fire texture (can be colored brown)
                self.dustClouds.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/fire")
        except:
            pass
        
        # Earthy brown/tan color for dust clouds (0.6, 0.4, 0.2, 1.0) - slightly lighter for visibility
        self.dustClouds.renderer.setColor(Vec4(0.65, 0.45, 0.25, 0.7))  # Earthy brown, slightly transparent
        # Dust particles grow as they float and fade
        self.dustClouds.renderer.setInitialXScale(dustScale * 0.7)
        self.dustClouds.renderer.setFinalXScale(dustScale * 1.8)  # Expand as they float
        self.dustClouds.renderer.setInitialYScale(dustScale * 0.7)
        self.dustClouds.renderer.setFinalYScale(dustScale * 2.0)  # Taller as they float
        self.dustClouds.renderer.setXScaleFlag(True)
        self.dustClouds.renderer.setYScaleFlag(True)
        self.dustClouds.renderer.setIgnoreScale(False)
        
        # Dust emitter - wider spread, around the object
        self.dustClouds.emitter.setEmissionType(1)  # ETRADIATE
        if isCFOBoss:
            self.dustClouds.emitter.setRadius(emitterRadius * 1.0)
        else:
            self.dustClouds.emitter.setRadius(emitterRadius * 1.2)  # Even wider for safes
        self.dustClouds.emitter.setAmplitude(amplitude * 0.4)  # Gentle spread
        self.dustClouds.emitter.setAmplitudeSpread(0.8)  # More random spread
        # Dust rises slightly and floats
        self.dustClouds.emitter.setOffsetForce(Vec3(0.0, 0.0, dustRiseZ))  # Slight upward
        
        # ===== CONFIGURE EARTH PARTICLES (Small settling particles) =====
        if isCFOBoss:
            earthPoolSize = int(50 * baseScale)
            earthBirthRate = 0.06
            earthLitterSize = 2
            earthLifespan = 1.3 * baseScale
            earthScale = max(0.08, 0.12 * baseScale)
        else:
            earthPoolSize = int(25 * baseScale)
            earthBirthRate = 0.1
            earthLitterSize = 1
            earthLifespan = 1.0 * baseScale
            earthScale = max(0.05, 0.1 * baseScale)
        
        self.earthParticles.setPoolSize(earthPoolSize)
        self.earthParticles.setBirthRate(earthBirthRate)
        self.earthParticles.setLitterSize(earthLitterSize)
        self.earthParticles.setLitterSpread(1)
        self.earthParticles.factory.setLifespanBase(earthLifespan)
        self.earthParticles.factory.setLifespanSpread(0.4)
        self.earthParticles.factory.setMassBase(0.8)  # Medium weight for settling
        self.earthParticles.factory.setMassSpread(0.2)
        self.earthParticles.factory.setTerminalVelocityBase(300.0)  # Moderate falling
        self.earthParticles.factory.setTerminalVelocitySpread(80.0)
        
        # Earth particles renderer - medium brown
        self.earthParticles.renderer.setAlphaMode(3)  # PRALPHANONE
        self.earthParticles.renderer.setUserAlpha(1.0)
        self.earthParticles.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.earthParticles.renderer.setAlphaDisable(0)
        self.earthParticles.renderer.setAnimAngleFlag(1)  # Animated for particles
        self.earthParticles.renderer.setNonanimatedTheta(0.0)
        
        # Try to load spark texture for small earth particles
        try:
            self.earthParticles.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/spark")
        except:
            try:
                # Fallback to fire texture
                self.earthParticles.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/fire")
            except:
                pass
        
        # Medium brown color for earth particles
        self.earthParticles.renderer.setColor(Vec4(0.6, 0.4, 0.2, 0.8))  # Earthy brown (matches globals)
        # Earth particles shrink as they settle
        self.earthParticles.renderer.setInitialXScale(earthScale)
        self.earthParticles.renderer.setFinalXScale(earthScale * 0.6)  # Shrink as they settle
        self.earthParticles.renderer.setInitialYScale(earthScale)
        self.earthParticles.renderer.setFinalYScale(earthScale * 0.6)
        self.earthParticles.renderer.setXScaleFlag(True)
        self.earthParticles.renderer.setYScaleFlag(True)
        self.earthParticles.renderer.setIgnoreScale(False)
        
        # Earth particles emitter - wider spread
        self.earthParticles.emitter.setEmissionType(1)  # ETRADIATE
        if isCFOBoss:
            self.earthParticles.emitter.setRadius(emitterRadius * 0.9)
        else:
            self.earthParticles.emitter.setRadius(emitterRadius * 1.1)  # Wider for safes
        self.earthParticles.emitter.setAmplitude(amplitude * 0.6)  # Moderate spread
        self.earthParticles.emitter.setAmplitudeSpread(0.7)
        # Earth particles fall slowly
        self.earthParticles.emitter.setOffsetForce(Vec3(0.0, 0.0, downwardForceZ * 0.6))  # Slower fall
        
        # ===== ADD FORCES FOR ALL LAYERS =====
        # Downward force for earth particles (gravity)
        gravityForceGroup = ForceGroup.ForceGroup('earthGravity')
        if isCFOBoss:
            gravityStrength = -5.0 * baseScale
        else:
            gravityStrength = -4.0 * baseScale
        gravityForce = LinearVectorForce(Vec3(0.0, 0.0, gravityStrength), 1.0, 0)
        gravityForce.setActive(True)
        gravityForceGroup.addForce(gravityForce)
        self.particleEffect.addForceGroup(gravityForceGroup)
        
        # Gentle upward force for dust clouds (floating effect)
        dustForceGroup = ForceGroup.ForceGroup('dustFloat')
        dustUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, dustRiseZ * 0.4), 0.3, 0)
        dustUpwardForce.setActive(True)
        dustForceGroup.addForce(dustUpwardForce)
        self.particleEffect.addForceGroup(dustForceGroup)
        
        # Store particles reference for cleanup
        self.particles = self.dustClouds  # Keep for compatibility with existing code
        
        # Apply brown/tan glow color to safe (not CFO) - will fade in when effect starts
        if isSafe and not isCFOBoss:
            try:
                # Store original color scale if not already stored
                if not hasattr(self.obj, '_originalGroundedColorScale'):
                    originalColor = self.obj.getColorScale()
                    # Validate the color is reasonable
                    if (0.0 <= originalColor.getX() <= 2.0 and 
                        0.0 <= originalColor.getY() <= 2.0 and 
                        0.0 <= originalColor.getZ() <= 2.0 and 
                        0.0 <= originalColor.getW() <= 2.0):
                        self.obj._originalGroundedColorScale = originalColor
                    else:
                        # Color is corrupted, use default white
                        self.obj._originalGroundedColorScale = VBase4(1, 1, 1, 1)
                
                # Calculate lighter brown/tan tint (less intense)
                # Blend between original and earthy brown: 70% original, 30% brown
                # This creates a subtle glow effect
                originalColor = self.obj._originalGroundedColorScale
                brownTint = VBase4(0.6, 0.4, 0.2, 1.0)  # Earthy brown tint (matches globals)
                blendFactor = 0.5  # 50% of the tint (lighter effect)
                
                glowColor = VBase4(
                    originalColor.getX() * (1.0 - blendFactor) + brownTint.getX() * blendFactor,
                    originalColor.getY() * (1.0 - blendFactor) + brownTint.getY() * blendFactor,
                    originalColor.getZ() * (1.0 - blendFactor) + brownTint.getZ() * blendFactor,
                    originalColor.getW()  # Alpha - preserve original
                )
                
                # Store the glow color for fade in/out
                self.obj._groundedGlowColor = glowColor
                self.notify.info("Prepared brown/tan glow color for safe (will fade in)")
            except Exception as e:
                self.notify.warning(f"Error preparing glow color for safe: {e}")
        
        # Set rendering properties for earth particles
        self.effectNode.setLightOff()
        self.effectNode.setFogOff()
        self.effectNode.setDepthWrite(False)  # Don't write to depth buffer (so particles won't occlude things behind them)
        # Keep depthTest enabled (default) so particles still respect depth for proper rendering
        # Earth particles render at lower priority than damage numbers
        # Earth at -50 (low), damage numbers at 100 (highest)
        # Use negative priority to ensure earth renders before damage numbers
        self.effectNode.setBin('fixed', -50)
        self.effectNode.setTransparency(1)  # Enable transparency on the effect node
        # Additive blending for earth glow
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
        
        # Fade in the glow color for safe
        self._fadeInSafeColor()
        
        if self.particleEffect:
            # Start the particle effect with proper parent and render nodes
            # parent is where the effect is positioned (effectNode)
            # renderParent is the coordinate system for physics (particleRenderParent with depth settings)
            self.particleEffect.start(parent=self.effectNode, renderParent=self.particleRenderParent)
            
            # Set the stored position
            if hasattr(self, 'particlePos'):
                self.particleEffect.setPos(self.particlePos)
            
            # Ensure particle effect doesn't occlude damage numbers
            # Apply depth settings to the particle effect node and all its children recursively
            # Do this after a short delay to ensure all particle system nodes are created
            if not self.particleEffect.isEmpty():
                self._applyDepthSettingsRecursive(self.particleEffect)
                # Also apply to effectNode to ensure inheritance
                self._applyDepthSettingsRecursive(self.effectNode)
                # Use a task to reapply settings after particles are fully initialized
                taskMgr.doMethodLater(0.1, self._ensureDepthSettings, self.uniqueName('ensureDepthSettings'))
    
    def _applyDepthSettingsRecursive(self, node):
        """Recursively apply depth settings to node and all its children."""
        if node.isEmpty():
            return
        
        # Only disable depth write (so particles don't occlude things behind them)
        # Keep depth test enabled (default) so particles still respect depth for proper rendering
        node.setDepthWrite(False)
        
        # Recursively apply to all children
        for child in node.getChildren():
            self._applyDepthSettingsRecursive(child)
    
    def _ensureDepthSettings(self, task):
        """Task to ensure depth settings are applied to all particle nodes."""
        if not self.active:
            return task.done
        
        # Reapply depth settings to ensure they stick
        if hasattr(self, 'particleEffect') and self.particleEffect and not self.particleEffect.isEmpty():
            self._applyDepthSettingsRecursive(self.particleEffect)
        
        if hasattr(self, 'effectNode') and self.effectNode and not self.effectNode.isEmpty():
            self._applyDepthSettingsRecursive(self.effectNode)
        
        if hasattr(self, 'particleRenderParent') and self.particleRenderParent and not self.particleRenderParent.isEmpty():
            self.particleRenderParent.setDepthWrite(False)
            # Keep depthTest enabled (default) - don't disable it
        
        return task.done
    
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
        
        # Fade out the glow color immediately (don't wait for particles to fade)
        self._fadeOutSafeColor()
        
        # Stop spawning new particles but let existing ones fade out
        # Set birth rate to very high value to effectively stop spawning
        for particleLayer in ['dustClouds', 'earthParticles', 'particles']:
            if hasattr(self, particleLayer):
                particles = getattr(self, particleLayer)
                if particles:
                    try:
                        # Set very high birth rate to stop spawning (particles will fade out naturally)
                        particles.setBirthRate(100.0)
                    except Exception as e:
                        self.notify.warning(f"Error stopping {particleLayer}: {e}")
        
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
        
        # Check all earth particle layers
        for particleLayer in ['dustClouds', 'earthParticles', 'particles']:
            if hasattr(self, particleLayer):
                particles = getattr(self, particleLayer)
                if particles:
                    try:
                        lifespanBase = particles.factory.getLifespanBase()
                        lifespanSpread = particles.factory.getLifespanSpread()
                        maxLifespan = max(maxLifespan, lifespanBase + lifespanSpread)
                    except:
                        pass
        
        # Clean up after particles have faded (add small buffer)
        cleanupDelay = maxLifespan + 0.5
        taskMgr.doMethodLater(cleanupDelay, self._delayedCleanup, self.uniqueName('gracefulCleanup'))
    
    def _delayedCleanup(self, task):
        """Actually remove the nodes after particles have faded out."""
        # Color should already be restored by fade out in gracefulCleanup()
        # But ensure it's restored here too in case cleanup was called directly
        
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
        
        # Clean up all particle layer references
        for particleLayer in ['dustClouds', 'earthParticles', 'particles']:
            if hasattr(self, particleLayer):
                setattr(self, particleLayer, None)
        
        if hasattr(self, 'particleRenderParent') and self.particleRenderParent and not self.particleRenderParent.isEmpty():
            try:
                self.particleRenderParent.removeNode()
            except Exception as e:
                self.notify.warning(f"Error removing particle render parent in delayed cleanup: {e}")
            self.particleRenderParent = None
        
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
            return f'groundedEffect-{self.obj.getDoId()}-{name}'
        return f'groundedEffect-{name}'
    
    def _fadeInSafeColor(self):
        """Fade in the brown/tan glow color on the safe."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from toontown.coghq import DistributedCashbotBossSafe
            from toontown.suit import BossCog
            
            if isinstance(self.obj, DistributedCashbotBossSafe.DistributedCashbotBossSafe) and not isinstance(self.obj, BossCog.BossCog):
                if hasattr(self.obj, '_groundedGlowColor') and hasattr(self.obj, '_originalGroundedColorScale'):
                    # Cancel any existing color interval
                    if hasattr(self.obj, '_groundedColorInterval'):
                        if self.obj._groundedColorInterval:
                            self.obj._groundedColorInterval.finish()
                    
                    # Fade in to glow color over 0.4 seconds
                    self.obj._groundedColorInterval = LerpColorScaleInterval(
                        self.obj,
                        duration=0.4,
                        colorScale=self.obj._groundedGlowColor,
                        blendType='easeInOut'
                    )
                    self.obj._groundedColorInterval.start()
                    self.notify.info("Fading in brown/tan glow color on safe")
        except Exception as e:
            self.notify.warning(f"Error fading in safe color: {e}")
    
    def _fadeOutSafeColor(self):
        """Fade out the brown/tan glow color on the safe back to original."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from toontown.coghq import DistributedCashbotBossSafe
            from toontown.suit import BossCog
            
            if isinstance(self.obj, DistributedCashbotBossSafe.DistributedCashbotBossSafe) and not isinstance(self.obj, BossCog.BossCog):
                if hasattr(self.obj, '_originalGroundedColorScale'):
                    # Cancel any existing color interval
                    if hasattr(self.obj, '_groundedColorInterval'):
                        if self.obj._groundedColorInterval:
                            self.obj._groundedColorInterval.finish()
                    
                    # Fade out to original color over 0.4 seconds
                    self.obj._groundedColorInterval = LerpColorScaleInterval(
                        self.obj,
                        duration=0.4,
                        colorScale=self.obj._originalGroundedColorScale,
                        blendType='easeInOut'
                    )
                    self.obj._groundedColorInterval.start()
                    self.notify.info("Fading out brown/tan glow color on safe")
        except Exception as e:
            self.notify.warning(f"Error fading out safe color: {e}")
    
    def _restoreSafeColor(self):
        """Immediately restore the original color of the safe if it was changed (no fade)."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from toontown.coghq import DistributedCashbotBossSafe
            from toontown.suit import BossCog
            
            if isinstance(self.obj, DistributedCashbotBossSafe.DistributedCashbotBossSafe) and not isinstance(self.obj, BossCog.BossCog):
                # Cancel any existing color interval
                if hasattr(self.obj, '_groundedColorInterval'):
                    if self.obj._groundedColorInterval:
                        self.obj._groundedColorInterval.finish()
                    self.obj._groundedColorInterval = None
                
                # Restore original color immediately
                if hasattr(self.obj, '_originalGroundedColorScale'):
                    self.obj.setColorScale(self.obj._originalGroundedColorScale)
                    self.notify.info("Restored original color to safe")
        except Exception as e:
            self.notify.warning(f"Error restoring safe color: {e}")
    
    def cleanup(self, force=False):
        """
        Completely clean up the effect immediately.
        Use force=True for game end/restart scenarios.
        """
        # Cancel any pending graceful cleanup and depth settings tasks
        taskMgr.remove(self.uniqueName('gracefulCleanup'))
        taskMgr.remove(self.uniqueName('ensureDepthSettings'))
        
        # Stop first to prevent new particles from spawning
        self.stop()
        
        # Restore original color to safe
        self._restoreSafeColor()
        
        # Stop all earth particle layers from spawning
        for particleLayer in ['dustClouds', 'earthParticles', 'particles']:
            if hasattr(self, particleLayer):
                particles = getattr(self, particleLayer)
                if particles:
                    try:
                        # Set very high birth rate to stop spawning
                        particles.setBirthRate(100.0)
                        setattr(self, particleLayer, None)
                    except Exception as e:
                        self.notify.warning(f"Error stopping {particleLayer}: {e}")
        
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
        
        if hasattr(self, 'particleRenderParent') and self.particleRenderParent and not self.particleRenderParent.isEmpty():
            try:
                self.particleRenderParent.removeNode()
            except Exception as e:
                self.notify.warning(f"Error removing particle render parent: {e}")
            self.particleRenderParent = None
        
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
        """Update earth effect intensity based on stack count."""
        super().updateStack(stackCount)
        
        if not self.active:
            return
        
        # Update all earth layers based on stack count
        # More stacks = more intense earth effect (faster birth rate, more particles)
        intensityMultiplier = 1.0 / max(1, stackCount)
        
        # Update dust clouds
        if hasattr(self, 'dustClouds') and self.dustClouds:
            try:
                baseDustBirthRate = 0.06  # Match safe birth rate
                self.dustClouds.setBirthRate(baseDustBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More visible dust for more stacks
                    self.dustClouds.renderer.setColor(Vec4(0.7, 0.5, 0.3, 0.8))  # Slightly brighter brown
            except:
                pass
        
        # Update earth particles
        if hasattr(self, 'earthParticles') and self.earthParticles:
            try:
                baseEarthBirthRate = 0.1  # Match safe birth rate
                self.earthParticles.setBirthRate(baseEarthBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More visible particles for more stacks
                    self.earthParticles.renderer.setColor(Vec4(0.65, 0.45, 0.25, 0.9))  # Slightly brighter
            except:
                pass
        
        # Legacy support for self.particles (which points to dustClouds)
        if hasattr(self, 'particles') and self.particles:
            try:
                baseBirthRate = 0.06  # Match safe birth rate
                self.particles.setBirthRate(baseBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    self.particles.renderer.setColor(Vec4(0.7, 0.5, 0.3, 0.8))  # Brighter brown
            except:
                pass


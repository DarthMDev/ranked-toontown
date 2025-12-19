"""
Visual effect for the GROUNDED status effect.

Creates animated earth/dirt particles orbiting around the object in 3D.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, VBase4, Filename, DSearchPath
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import Sequence, LerpColorScaleInterval, Wait, Func
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase
import math


class GroundedEffectVisual(StatusEffectVisualBase):
    """
    Visual for the GROUNDED status effect.
    
    Creates a particle effect with:
    - Brown earth/dirt particles rising from the base
    - Dust particles floating around the object
    - Scaled appropriately to object size
    """
    
    def create(self):
        """Create the earth particle effect."""
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
                self.notify.info("Detected CFO boss - applying larger earth effect")
            else:
                # Check if this is a safe (not CFO)
                from toontown.coghq import DistributedCashbotBossSafe
                if isinstance(self.obj, DistributedCashbotBossSafe.DistributedCashbotBossSafe):
                    isSafe = True
                    self.notify.info("Detected safe - will apply brown glow color")
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
        
        # Try to load PTF file first, fallback to manual creation
        self.particleEffect = None
        particleSearchPath = DSearchPath()
        particleSearchPath.appendDirectory(Filename('/phase_5/etc'))
        particleSearchPath.appendDirectory(Filename('/phase_4/etc'))
        particleSearchPath.appendDirectory(Filename('/phase_3.5/etc'))
        
        pfile = Filename('groundedEarth.ptf')
        found = vfs.resolveFilename(pfile, particleSearchPath)
        
        if found:
            try:
                self.particleEffect = ParticleEffect.ParticleEffect('GroundedEarth')
                self.particleEffect.loadConfig(pfile)
                self.notify.info("Loaded groundedEarth.ptf particle file")
                # Scale the effect based on object size
                if isCFOBoss:
                    self.particleEffect.setScale(baseScale)
                else:
                    self.particleEffect.setScale(baseScale)
            except Exception as e:
                self.notify.warning(f"Failed to load PTF file, using manual particles: {e}")
                self.particleEffect = None
        
        # Fallback to manual particle creation if PTF failed
        if not self.particleEffect:
            self.particleEffect = ParticleEffect.ParticleEffect('GroundedEarth')
            # Create particles manually (fallback)
            self.earthParticles = Particles.Particles('earthParticles')
            self.earthParticles.setFactory('PointParticleFactory')
            self.earthParticles.setRenderer('SpriteParticleRenderer')
            self.earthParticles.setEmitter('SphereVolumeEmitter')
            self.particleEffect.addParticles(self.earthParticles)
        
        # Store the desired position for later - position at object center in local space
        # Since effectNode is attached to obj, we use local coordinates
        # Position at the center height of the object (particles will orbit around)
        centerZ = center.getZ()
        self.particlePos = Point3(0, 0, centerZ)
        
        # Store orbit parameters for random 3D orbiting
        if isCFOBoss:
            self.orbitRadius = max(2.5, avgWidth / 2.0 + 1.0)
            self.orbitSpeed = 1.0 * baseScale  # Slower for CFO
        else:
            self.orbitRadius = max(1.2, (maxPt.getX() - minPt.getX()) / 2.0 + 0.5)
            self.orbitSpeed = 1.5 * baseScale  # Faster for safes
        
        # If PTF was loaded, get the particles from it and configure
        ptfLoaded = False
        if self.particleEffect:
            try:
                # Try to get particles - PTF might use different naming
                # Try common names first
                for name in ['particles-1', 'particles-0', 'Particles']:
                    try:
                        self.earthParticles = self.particleEffect.getParticlesNamed(name)
                        if self.earthParticles:
                            ptfLoaded = True
                            break
                    except:
                        continue
                
                # If no named particles found, try to get the first particle system
                if not ptfLoaded:
                    try:
                        particlesList = self.particleEffect.getParticlesList()
                        if particlesList and len(particlesList) > 0:
                            self.earthParticles = particlesList[0]
                            ptfLoaded = True
                    except:
                        pass
                
                if ptfLoaded and self.earthParticles:
                    # Scale particles based on object size
                    if isCFOBoss:
                        self.earthParticles.setPoolSize(int(80 * baseScale))
                        self.earthParticles.setBirthRate(0.03)
                    else:
                        self.earthParticles.setPoolSize(int(40 * baseScale))
                        self.earthParticles.setBirthRate(0.05)
            except Exception as e:
                self.notify.warning(f"Error getting particles from PTF: {e}")
                self.earthParticles = None
        
        # If PTF didn't load or doesn't have particles, create fallback
        if not ptfLoaded or not hasattr(self, 'earthParticles') or self.earthParticles is None:
            # Fallback: create particles manually
            self.earthParticles = Particles.Particles('earthParticles')
            self.earthParticles.setFactory('PointParticleFactory')
            self.earthParticles.setRenderer('SpriteParticleRenderer')
            self.earthParticles.setEmitter('SphereVolumeEmitter')
            self.particleEffect.addParticles(self.earthParticles)
            
            # Configure fallback particles
            if isCFOBoss:
                earthPoolSize = int(80 * baseScale)
                earthBirthRate = 0.03
            else:
                earthPoolSize = int(40 * baseScale)
                earthBirthRate = 0.05
            
            self.earthParticles.setPoolSize(earthPoolSize)
            self.earthParticles.setBirthRate(earthBirthRate)
            self.earthParticles.setLitterSize(2)
            self.earthParticles.factory.setLifespanBase(0.8)
            self.earthParticles.renderer.setAlphaMode(3)
            self.earthParticles.renderer.setColor(Vec4(0.5, 0.35, 0.15, 0.95))
            try:
                self.earthParticles.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/spark")
            except:
                pass
        
        # Always create dust particles (separate from PTF)
        # ===== LAYER 2: DUST (Floating dust particles) =====
        self.dust = Particles.Particles('dust')
        self.dust.setFactory('PointParticleFactory')
        self.dust.setRenderer('SpriteParticleRenderer')
        self.dust.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.dust)
        
        # ===== CONFIGURE DUST (Floating dust particles) =====
        if isCFOBoss:
            dustPoolSize = int(60 * baseScale)
            dustBirthRate = 0.06
            dustLitterSize = 2
            dustLifespan = 1.5 * baseScale
            dustScale = max(0.25, 0.35 * baseScale)
        else:
            dustPoolSize = int(30 * baseScale)
            dustBirthRate = 0.08
            dustLitterSize = 1
            dustLifespan = 1.2 * baseScale
            dustScale = max(0.15, 0.25 * baseScale)
        
        self.dust.setPoolSize(dustPoolSize)
        self.dust.setBirthRate(dustBirthRate)
        self.dust.setLitterSize(dustLitterSize)
        self.dust.setLitterSpread(1)
        self.dust.factory.setLifespanBase(dustLifespan)
        self.dust.factory.setLifespanSpread(0.4)
        self.dust.factory.setMassBase(0.3)  # Light for floating
        self.dust.factory.setMassSpread(0.15)
        self.dust.factory.setTerminalVelocityBase(120.0)  # Slow floating
        self.dust.factory.setTerminalVelocitySpread(40.0)
        
        # Dust renderer - lighter brown dust
        self.dust.renderer.setAlphaMode(3)  # PRALPHANONE
        self.dust.renderer.setUserAlpha(1.0)
        self.dust.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.dust.renderer.setAlphaDisable(0)
        self.dust.renderer.setAnimAngleFlag(1)  # Animated for dust
        self.dust.renderer.setNonanimatedTheta(0.0)
        
        # Try to load texture for dust - use white glow for soft dust particles
        try:
            # Use white glow for dust (softer, more transparent)
            dustModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
            if not dustModel.isEmpty():
                dustTemplate = dustModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                if not dustTemplate.isEmpty():
                    self.dust.renderer.setFromNode(dustTemplate)
        except:
            pass
        
        # Lighter brown color for dust (more transparent)
        self.dust.renderer.setColor(Vec4(0.7, 0.5, 0.3, 0.5))  # Lighter, more transparent brown
        # Dust particles grow as they float and fade
        self.dust.renderer.setInitialXScale(dustScale * 0.5)
        self.dust.renderer.setFinalXScale(dustScale * 1.3)  # Expand as they float
        self.dust.renderer.setInitialYScale(dustScale * 0.5)
        self.dust.renderer.setFinalYScale(dustScale * 1.5)  # Taller as they float
        self.dust.renderer.setXScaleFlag(True)
        self.dust.renderer.setYScaleFlag(True)
        self.dust.renderer.setIgnoreScale(False)
        
        # Dust emitter - can keep as sphere for floating dust (optional)
        self.dust.emitter.setEmissionType(1)  # ETRADIATE
        if isCFOBoss:
            dustRadius = max(2.0, avgWidth / 2.0 * 0.8)
        else:
            dustRadius = max(0.6, (maxPt.getX() - minPt.getX()) / 2.0) * 1.2
        self.dust.emitter.setRadius(dustRadius * 1.0)  # Full radius
        self.dust.emitter.setAmplitude(0.1 * baseScale)  # Very gentle
        self.dust.emitter.setAmplitudeSpread(0.7)  # More random spread
        # Dust can float gently (minimal force)
        self.dust.emitter.setOffsetForce(Vec3(0.0, 0.0, 0.0))  # No upward force for orbiting effect
        
        # ===== ADD ORBITAL FORCES FOR RANDOM ORBITS =====
        # Create forces that make each particle orbit in a random direction
        # The PTF file has gravity, but we want orbiting instead
        if hasattr(self, 'earthParticles') and self.earthParticles:
            # Disable or override gravity from PTF - we want orbiting, not falling
            try:
                # Get existing force groups and disable gravity
                forceGroups = self.particleEffect.getForceGroupList()
                for fg in forceGroups:
                    forces = fg.getForceList()
                    for force in forces:
                        # Disable gravity (LinearVectorForce pointing down)
                        if hasattr(force, 'getVector'):
                            vec = force.getVector()
                            if vec and vec.getZ() < -5:  # Gravity force
                                force.setActive(False)
            except:
                pass
            
            # Add orbital force group for random orbits
            orbitForceGroup = ForceGroup.ForceGroup('randomOrbit')
            
            # Use LinearJitterForce to give each particle random orbital motion
            # This creates varied directions for each particle - each particle gets a different random force
            from panda3d.physics import LinearJitterForce
            jitterForce = LinearJitterForce(self.orbitSpeed * 5.0, 0)  # Random orbital motion - high amplitude for varied orbits
            jitterForce.setActive(True)
            orbitForceGroup.addForce(jitterForce)
            
            self.particleEffect.addForceGroup(orbitForceGroup)
            
            # Configure emitter to give particles random initial velocities for varied orbits
            # This makes each particle start with a different orbit direction
            try:
                # Set high amplitude spread so particles go in different directions
                # This is key - each particle gets a random initial velocity direction
                self.earthParticles.emitter.setAmplitudeSpread(4.0)  # Very high spread for random directions
                # Set emitter to radiate from center with random directions
                self.earthParticles.emitter.setEmissionType(1)  # ETRADIATE
                # Set radius to orbit radius so particles spawn around the object
                self.earthParticles.emitter.setRadius(self.orbitRadius)
                # Set amplitude for initial velocity - particles will radiate outward in random directions
                self.earthParticles.emitter.setAmplitude(self.orbitSpeed * 3.0)
            except Exception as e:
                self.notify.warning(f"Error configuring emitter for random orbits: {e}")
        
        # Store particles reference for cleanup
        if hasattr(self, 'earthParticles') and self.earthParticles:
            self.particles = self.earthParticles  # Keep for compatibility with existing code
        
        # Apply brown glow color to safe (not CFO) - will fade in when effect starts
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
                
                # Calculate lighter brown tint (less intense)
                # Blend between original and earthy brown: 70% original, 30% brown
                # This creates a subtle glow effect
                originalColor = self.obj._originalGroundedColorScale
                brownTint = VBase4(0.6, 0.4, 0.2, 1.0)  # Earthy brown tint
                blendFactor = 0.4  # 40% of the tint (lighter effect)
                
                glowColor = VBase4(
                    originalColor.getX() * (1.0 - blendFactor) + brownTint.getX() * blendFactor,
                    originalColor.getY() * (1.0 - blendFactor) + brownTint.getY() * blendFactor,
                    originalColor.getZ() * (1.0 - blendFactor) + brownTint.getZ() * blendFactor,
                    originalColor.getW()  # Alpha - preserve original
                )
                
                # Store the glow color for fade in/out
                self.obj._groundedGlowColor = glowColor
                self.notify.info("Prepared brown glow color for safe (will fade in)")
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
            
            # No need for orbit task - forces handle random orbital motion
            
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
        # Stop orbit task
        taskMgr.remove(self.uniqueName('orbitParticles'))
        
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
        for particleLayer in ['earthParticles', 'dust', 'particles']:
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
        
        # Check all earth and dust particle layers
        for particleLayer in ['earthParticles', 'dust', 'particles']:
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
        for particleLayer in ['earthParticles', 'dust', 'particles']:
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
        """Fade in the brown glow color on the safe."""
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
                    self.notify.info("Fading in brown glow color on safe")
        except Exception as e:
            self.notify.warning(f"Error fading in safe color: {e}")
    
    def _fadeOutSafeColor(self):
        """Fade out the brown glow color on the safe back to original."""
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
                    self.notify.info("Fading out brown glow color on safe")
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
        taskMgr.remove(self.uniqueName('orbitParticles'))
        
        # Stop first to prevent new particles from spawning
        self.stop()
        
        # Restore original color to safe
        self._restoreSafeColor()
        
        # Stop all earth and dust particle layers from spawning
        for particleLayer in ['earthParticles', 'dust', 'particles']:
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
        """Update earth intensity based on stack count."""
        super().updateStack(stackCount)
        
        if not self.active:
            return
        
        # Update all earth layers based on stack count
        # More stacks = more intense earth effect (faster birth rate, more particles)
        intensityMultiplier = 1.0 / max(1, stackCount)
        
        # Update earth particles
        if hasattr(self, 'earthParticles') and self.earthParticles:
            try:
                baseEarthBirthRate = 0.05
                self.earthParticles.setBirthRate(baseEarthBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More intense brown for more stacks
                    self.earthParticles.renderer.setColor(Vec4(0.5, 0.3, 0.15, 0.95))  # Darker brown
            except:
                pass
        
        # Update dust
        if hasattr(self, 'dust') and self.dust:
            try:
                baseDustBirthRate = 0.08
                self.dust.setBirthRate(baseDustBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More visible dust for more stacks
                    self.dust.renderer.setColor(Vec4(0.7, 0.5, 0.3, 0.6))  # Slightly more opaque
            except:
                pass
        
        # Legacy support for self.particles (which points to earthParticles)
        if hasattr(self, 'particles') and self.particles:
            try:
                baseBirthRate = 0.05
                self.particles.setBirthRate(baseBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    self.particles.renderer.setColor(Vec4(0.5, 0.3, 0.15, 0.95))  # Darker brown
            except:
                pass

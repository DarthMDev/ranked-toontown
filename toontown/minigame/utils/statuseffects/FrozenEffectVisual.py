"""
Visual effect for the FROZEN synergy status effect (Drenched + Winded).

Creates an animated ice/frost effect with:
- Ice crystals floating around the CFO
- Frost particles swirling
- Scaled appropriately for the CFO boss
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib
from panda3d.physics import LinearVectorForce
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase


class FrozenEffectVisual(StatusEffectVisualBase):
    """
    Visual for the FROZEN synergy status effect.
    
    Creates a particle effect with:
    - Ice crystals floating and swirling around the CFO
    - Frost particles creating a frozen atmosphere
    - Icy blue glow on the boss
    - Only applies to CFO boss (synergy effect)
    """
    
    def create(self):
        """Create the ice/frost particle effect."""
        if self.active:
            return
            
        # Create root node for effect
        self._createEffectNode('frozenEffect')
        
        # Get object dimensions for scaling
        minPt, maxPt, center, height = self.objDimensions
        
        # Calculate width (X and Y dimensions) for objects that are wide
        widthX = maxPt.getX() - minPt.getX()
        widthY = maxPt.getY() - minPt.getY()
        avgWidth = (widthX + widthY) / 2.0
        
        # Debug logging
        self.notify.info(f"Creating frozen effect for {self.obj.getName()}: height={height}, width={avgWidth}, minPt={minPt}, maxPt={maxPt}, center={center}")
        
        # Check if this is the CFO boss (FROZEN only applies to CFO)
        isCFOBoss = False
        try:
            from ..boss import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying large-scale frozen effect")
        except:
            pass
        
        # FROZEN only applies to CFO - warn if it's not
        if not isCFOBoss:
            self.notify.warning("FROZEN effect should only apply to CFO boss!")
        
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
            # Fallback for non-CFO (shouldn't happen, but handle gracefully)
            baseScale = max(0.5, min(height / 3.0, 2.0))
        
        self.notify.info(f"Frozen effect baseScale: {baseScale} (isCFO={isCFOBoss})")
        
        # Create a renderParent node for particle physics with proper depth settings
        # This ensures particles don't occlude other objects
        self.particleRenderParent = render.attachNewNode('frozenParticleRenderParent')
        self.particleRenderParent.setBin('fixed', -50)  # Lower priority than damage numbers
        self.particleRenderParent.setDepthWrite(False)  # Don't write to depth (won't occlude things behind)
        # Keep depthTest enabled (default) so particles respect depth for proper rendering
        self.particleRenderParent.setLightOff()
        self.particleRenderParent.setFogOff()
        
        # Create the particle effect (don't parent it yet - start() will handle that)
        self.particleEffect = ParticleEffect.ParticleEffect('FrozenIce')
        
        # Store the desired position for later - position at object center for swirling effect
        # Since effectNode is attached to obj, we use local coordinates
        # Position at center height for ice to swirl around
        centerOffset = center.getZ()
        self.particlePos = Point3(0, 0, centerOffset)
        
        # ===== LAYER 1: ICE CRYSTALS (Floating ice particles) =====
        self.iceCrystals = Particles.Particles('iceCrystals')
        self.iceCrystals.setFactory('PointParticleFactory')
        self.iceCrystals.setRenderer('SpriteParticleRenderer')
        self.iceCrystals.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.iceCrystals)
        
        # ===== LAYER 2: FROST MIST (Swirling frost particles) =====
        self.frostMist = Particles.Particles('frostMist')
        self.frostMist.setFactory('PointParticleFactory')
        self.frostMist.setRenderer('SpriteParticleRenderer')
        self.frostMist.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.frostMist)
        
        # Calculate emitter settings
        if isCFOBoss:
            emitterRadius = max(2.0, avgWidth / 2.0 * 0.8)
            amplitude = 1.5 * baseScale
            spiralForceZ = 1.5 * baseScale  # Gentle upward spiral for ice
        else:
            emitterRadius = max(0.8, (maxPt.getX() - minPt.getX()) / 2.0) * 1.2
            amplitude = 1.0 * baseScale
            spiralForceZ = 1.0 * baseScale
        
        # ===== CONFIGURE ICE CRYSTALS (Floating ice particles) =====
        if isCFOBoss:
            crystalPoolSize = int(80 * baseScale)
            crystalBirthRate = 0.12  # Less frequent snowflakes
            crystalLitterSize = 2
            crystalLifespan = 2.5 * baseScale  # Longer lifespan for visible float
            crystalScale = max(0.15, 0.25 * baseScale)
        else:
            crystalPoolSize = int(40 * baseScale)
            crystalBirthRate = 0.15  # Less frequent snowflakes
            crystalLitterSize = 1
            crystalLifespan = 1.8 * baseScale
            crystalScale = max(0.1, 0.18 * baseScale)
        
        self.iceCrystals.setPoolSize(crystalPoolSize)
        self.iceCrystals.setBirthRate(crystalBirthRate)
        self.iceCrystals.setLitterSize(crystalLitterSize)
        self.iceCrystals.setLitterSpread(1)
        self.iceCrystals.factory.setLifespanBase(crystalLifespan)
        self.iceCrystals.factory.setLifespanSpread(0.4)
        self.iceCrystals.factory.setMassBase(0.3)  # Light like ice crystals
        self.iceCrystals.factory.setMassSpread(0.1)
        self.iceCrystals.factory.setTerminalVelocityBase(200.0)  # Slow floating
        self.iceCrystals.factory.setTerminalVelocitySpread(80.0)
        
        # Ice crystals renderer - bright icy blue
        self.iceCrystals.renderer.setAlphaMode(3)  # PRALPHANONE
        self.iceCrystals.renderer.setUserAlpha(1.0)
        self.iceCrystals.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.iceCrystals.renderer.setAlphaDisable(0)
        self.iceCrystals.renderer.setAnimAngleFlag(1)  # Animated for tumbling
        self.iceCrystals.renderer.setNonanimatedTheta(0.0)
        
        # Load texture for ice crystals - use snowflake texture
        try:
            # Try snowflake particle texture first (best option)
            self.iceCrystals.renderer.setTextureFromNode("phase_8/models/props/snowflake_particle", "**/p1_2")
        except:
            try:
                # Fallback to snow-particle from suit-particles
                self.iceCrystals.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/snow-particle")
            except:
                try:
                    # Final fallback to white glow
                    crystalModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
                    if not crystalModel.isEmpty():
                        crystalTemplate = crystalModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                        if not crystalTemplate.isEmpty():
                            self.iceCrystals.renderer.setFromNode(crystalTemplate)
                except:
                    pass
        
        # Bright icy blue color for crystals (0.7, 0.9, 1.0, 1.0) - slightly brighter
        self.iceCrystals.renderer.setColor(Vec4(0.7, 0.9, 1.0, 0.9))  # Bright icy blue
        # Snowflake-shaped particles - square/round shape for snowflakes
        self.iceCrystals.renderer.setInitialXScale(crystalScale * 1.0)  # Square snowflakes
        self.iceCrystals.renderer.setFinalXScale(crystalScale * 0.9)  # Slight shrink as they fade
        self.iceCrystals.renderer.setInitialYScale(crystalScale * 1.0)  # Square snowflakes
        self.iceCrystals.renderer.setFinalYScale(crystalScale * 0.9)  # Slight shrink as they fade
        self.iceCrystals.renderer.setXScaleFlag(True)
        self.iceCrystals.renderer.setYScaleFlag(True)
        self.iceCrystals.renderer.setIgnoreScale(False)
        
        # Ice crystals emitter - radial emission for orbital motion
        self.iceCrystals.emitter.setEmissionType(1)  # ETRADIATE - radial emission creates initial orbital velocity
        self.iceCrystals.emitter.setRadius(emitterRadius)
        self.iceCrystals.emitter.setAmplitude(amplitude * 1.0)  # Good radial velocity for visible orbit
        self.iceCrystals.emitter.setAmplitudeSpread(0.3)  # Less spread for more consistent orbits
        # Set radiate origin to center (relative to particle effect position)
        self.iceCrystals.emitter.setRadiateOrigin(Point3(0, 0, 0))
        # Minimal vertical offset - let forces handle the spiral
        self.iceCrystals.emitter.setOffsetForce(Vec3(0.0, 0.0, spiralForceZ * 0.1))
        
        # ===== CONFIGURE FROST MIST (Swirling frost particles) =====
        if isCFOBoss:
            mistPoolSize = int(60 * baseScale)
            mistBirthRate = 0.06
            mistLitterSize = 2
            mistLifespan = 2.0 * baseScale  # Longer lifespan for visible swirl
            mistScale = max(0.08, 0.12 * baseScale)  # Much smaller mist particles
        else:
            mistPoolSize = int(30 * baseScale)
            mistBirthRate = 0.08
            mistLitterSize = 1
            mistLifespan = 1.5 * baseScale
            mistScale = max(0.05, 0.08 * baseScale)  # Much smaller mist particles
        
        self.frostMist.setPoolSize(mistPoolSize)
        self.frostMist.setBirthRate(mistBirthRate)
        self.frostMist.setLitterSize(mistLitterSize)
        self.frostMist.setLitterSpread(1)
        self.frostMist.factory.setLifespanBase(mistLifespan)
        self.frostMist.factory.setLifespanSpread(0.4)
        self.frostMist.factory.setMassBase(0.2)  # Very light like mist
        self.frostMist.factory.setMassSpread(0.1)
        self.frostMist.factory.setTerminalVelocityBase(150.0)  # Slow floating
        self.frostMist.factory.setTerminalVelocitySpread(50.0)
        
        # Frost mist renderer - lighter icy blue
        self.frostMist.renderer.setAlphaMode(3)  # PRALPHANONE
        self.frostMist.renderer.setUserAlpha(1.0)
        self.frostMist.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.frostMist.renderer.setAlphaDisable(0)
        self.frostMist.renderer.setAnimAngleFlag(1)  # Animated for swirling
        self.frostMist.renderer.setNonanimatedTheta(0.0)
        
        # Load texture for frost mist - use snow-particle or snowflake
        try:
            # Try snow-particle texture first (good for mist)
            self.frostMist.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/snow-particle")
        except:
            try:
                # Fallback to snowflake particle
                self.frostMist.renderer.setTextureFromNode("phase_8/models/props/snowflake_particle", "**/p1_2")
            except:
                try:
                    # Final fallback to white glow
                    mistModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
                    if not mistModel.isEmpty():
                        mistTemplate = mistModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                        if not mistTemplate.isEmpty():
                            self.frostMist.renderer.setFromNode(mistTemplate)
                except:
                    pass
        
        # Lighter icy blue color for mist (more transparent)
        self.frostMist.renderer.setColor(Vec4(0.75, 0.92, 1.0, 0.7))  # Lighter, more transparent icy blue
        # Small snow particles for mist - subtle background effect
        self.frostMist.renderer.setInitialXScale(mistScale * 1.0)  # Small square snow particles
        self.frostMist.renderer.setFinalXScale(mistScale * 1.15)  # Slight expansion as they float
        self.frostMist.renderer.setInitialYScale(mistScale * 1.0)  # Small square snow particles
        self.frostMist.renderer.setFinalYScale(mistScale * 1.15)  # Slight expansion as they float
        self.frostMist.renderer.setXScaleFlag(True)
        self.frostMist.renderer.setYScaleFlag(True)
        self.frostMist.renderer.setIgnoreScale(False)
        
        # Frost mist emitter - radial emission for orbital motion
        self.frostMist.emitter.setEmissionType(1)  # ETRADIATE - radial emission creates initial orbital velocity
        self.frostMist.emitter.setRadius(emitterRadius * 1.2)  # Slightly wider spread
        self.frostMist.emitter.setAmplitude(amplitude * 0.8)  # Gentler radial velocity
        self.frostMist.emitter.setAmplitudeSpread(0.5)  # More spread for misty effect
        # Set radiate origin to center (relative to particle effect position)
        self.frostMist.emitter.setRadiateOrigin(Point3(0, 0, 0))
        # Minimal vertical offset - let forces handle the spiral
        self.frostMist.emitter.setOffsetForce(Vec3(0.0, 0.0, spiralForceZ * 0.05))
        
        # ===== ADD FORCES FOR ALL LAYERS =====
        # Spiral force for ice crystals - use radial emission + gentle upward force
        # The emitter's ETRADIATE type gives particles radial velocity, creating circular motion
        # Combined with upward force, this creates a natural spiral around the object
        crystalForceGroup = ForceGroup.ForceGroup('crystalSpiral')
        
        # Upward component for spiral ascent - gentle to let radial motion dominate
        crystalUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, spiralForceZ * 0.4), 0.5, 0)
        crystalUpwardForce.setActive(True)
        crystalForceGroup.addForce(crystalUpwardForce)
        
        self.particleEffect.addForceGroup(crystalForceGroup)
        
        # Spiral force for frost mist - radial emission + upward force creates beautiful spiral
        mistSpiralForceGroup = ForceGroup.ForceGroup('mistSpiral')
        
        # Upward component for spiral ascent - very gentle for mist
        mistUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, spiralForceZ * 0.2), 0.3, 0)
        mistUpwardForce.setActive(True)
        mistSpiralForceGroup.addForce(mistUpwardForce)
        
        self.particleEffect.addForceGroup(mistSpiralForceGroup)
        
        # Store particles reference for cleanup
        self.particles = self.iceCrystals  # Keep for compatibility with existing code
        
        # Set rendering properties for ice particles
        self.effectNode.setLightOff()
        self.effectNode.setFogOff()
        self.effectNode.setDepthWrite(False)  # Don't write to depth buffer (so particles won't occlude things behind them)
        # Keep depthTest enabled (default) so particles still respect depth for proper rendering
        # Ice particles render at lower priority than damage numbers
        # Ice at -50 (low), damage numbers at 100 (highest)
        # Use negative priority to ensure ice renders before damage numbers
        self.effectNode.setBin('fixed', -50)
        self.effectNode.setTransparency(1)  # Enable transparency on the effect node
        # Additive blending for ice glow
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
        
        # Stop spawning new particles but let existing ones fade out
        # Set birth rate to very high value to effectively stop spawning
        for particleLayer in ['iceCrystals', 'frostMist', 'particles']:
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
        
        # Check all ice particle layers
        for particleLayer in ['iceCrystals', 'frostMist', 'particles']:
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
        for particleLayer in ['iceCrystals', 'frostMist', 'particles']:
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
            return f'frozenEffect-{self.obj.getDoId()}-{name}'
        return f'frozenEffect-{name}'
    
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
        
        # Stop all ice particle layers from spawning
        for particleLayer in ['iceCrystals', 'frostMist', 'particles']:
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
        """Update ice intensity based on stack count."""
        super().updateStack(stackCount)
        
        if not self.active:
            return
        
        # Update all ice layers based on stack count
        # More stacks = more intense ice effect (faster birth rate, brighter colors)
        intensityMultiplier = 1.0 / max(1, stackCount)
        
        # Update ice crystals
        if hasattr(self, 'iceCrystals') and self.iceCrystals:
            try:
                baseCrystalBirthRate = 0.12  # Updated to match new less frequent rate
                self.iceCrystals.setBirthRate(baseCrystalBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # Brighter icy blue for more stacks
                    self.iceCrystals.renderer.setColor(Vec4(0.8, 0.95, 1.0, 0.95))  # Brighter icy blue
            except:
                pass
        
        # Update frost mist
        if hasattr(self, 'frostMist') and self.frostMist:
            try:
                baseMistBirthRate = 0.06
                self.frostMist.setBirthRate(baseMistBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More visible mist for more stacks
                    self.frostMist.renderer.setColor(Vec4(0.8, 0.95, 1.0, 0.8))  # More opaque
            except:
                pass
        
        # Legacy support for self.particles (which points to iceCrystals)
        if hasattr(self, 'particles') and self.particles:
            try:
                baseBirthRate = 0.12  # Updated to match new less frequent rate
                self.particles.setBirthRate(baseBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    self.particles.renderer.setColor(Vec4(0.8, 0.95, 1.0, 0.95))  # Brighter icy blue
            except:
                pass


"""
Visual effect for the WINDED status effect.

Creates animated wind with white/greyish wind streams and green leaflets
spiraling around the object. Features a beautiful swirling effect with
reduced leaf frequency for better visual clarity.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, VBase4
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import LerpColorScaleInterval
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase


class WindedEffectVisual(StatusEffectVisualBase):
    """
    Visual for the WINDED status effect.
    
    Creates a particle effect with:
    - White/greyish wind streams swirling around the object
    - Green leaf particles spiraling in orbital motion
    - Reduced leaf frequency for cleaner visuals
    - Scaled appropriately to object size
    """
    
    def create(self):
        """Create the wind/air particle effect with leaf-like particles."""
        if self.active:
            return
            
        # Create root node for effect
        self._createEffectNode('windedEffect')
        
        # Get object dimensions for scaling
        minPt, maxPt, center, height = self.objDimensions
        
        # Calculate width (X and Y dimensions) for objects that are wide
        widthX = maxPt.getX() - minPt.getX()
        widthY = maxPt.getY() - minPt.getY()
        avgWidth = (widthX + widthY) / 2.0
        
        # Debug logging
        self.notify.info(f"Creating winded effect for {self.obj.getName()}: height={height}, width={avgWidth}, minPt={minPt}, maxPt={maxPt}, center={center}")
        
        # Check if this is the CFO boss (pyramid-shaped, wide at bottom)
        isCFOBoss = False
        isSafe = False
        try:
            from ..boss import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying larger, wider wind effect")
            else:
                # Check if this is a safe (not CFO)
                from ...craning.objects import DistributedCashbotSafe
                if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe):
                    isSafe = True
                    self.notify.info("Detected safe - will apply green glow color")
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
        
        self.notify.info(f"Winded effect baseScale: {baseScale} (isCFO={isCFOBoss})")
        
        # Create a renderParent node for particle physics with proper depth settings
        # This ensures particles don't occlude other objects
        self.particleRenderParent = render.attachNewNode('windedParticleRenderParent')
        self.particleRenderParent.setBin('fixed', -50)  # Lower priority than damage numbers
        self.particleRenderParent.setDepthWrite(False)  # Don't write to depth (won't occlude things behind)
        # Keep depthTest enabled (default) so particles respect depth for proper rendering
        self.particleRenderParent.setLightOff()
        self.particleRenderParent.setFogOff()
        
        # Create the particle effect (don't parent it yet - start() will handle that)
        self.particleEffect = ParticleEffect.ParticleEffect('WindedAir')
        
        # Store the desired position for later - position at object center for swirling effect
        # Since effectNode is attached to obj, we use local coordinates
        # Position at center height for wind to swirl around
        centerOffset = center.getZ()
        self.particlePos = Point3(0, 0, centerOffset)
        
        # ===== LAYER 1: WIND STREAMS (White/greyish wind particles) =====
        self.windStreams = Particles.Particles('windStreams')
        self.windStreams.setFactory('PointParticleFactory')
        self.windStreams.setRenderer('SpriteParticleRenderer')
        self.windStreams.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.windStreams)
        
        # ===== LAYER 2: GREEN LEAVES (Leaflets spiraling around) =====
        self.greenLeaves = Particles.Particles('greenLeaves')
        self.greenLeaves.setFactory('PointParticleFactory')
        self.greenLeaves.setRenderer('SpriteParticleRenderer')
        self.greenLeaves.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.greenLeaves)
        
        # Calculate emitter settings
        if isCFOBoss:
            emitterRadius = max(2.0, avgWidth / 2.0 * 0.8)
            amplitude = 2.0 * baseScale
            spiralForceZ = 3.0 * baseScale  # Upward spiral force
        else:
            # Wider spread for safes to ensure wind circles around them
            emitterRadius = max(0.8, (maxPt.getX() - minPt.getX()) / 2.0) * 1.2
            amplitude = 1.5 * baseScale
            spiralForceZ = 2.5 * baseScale
        
        # ===== CONFIGURE WIND STREAMS (White/greyish wind particles) =====
        if isCFOBoss:
            streamPoolSize = int(120 * baseScale)
            streamBirthRate = 0.015
            streamLitterSize = 3
            streamLifespan = 1.0 * baseScale
            streamScale = max(0.2, 0.3 * baseScale)
        else:
            streamPoolSize = int(60 * baseScale)
            streamBirthRate = 0.02
            streamLitterSize = 2
            streamLifespan = 0.8 * baseScale
            streamScale = max(0.1, 0.18 * baseScale)
        
        self.windStreams.setPoolSize(streamPoolSize)
        self.windStreams.setBirthRate(streamBirthRate)
        self.windStreams.setLitterSize(streamLitterSize)
        self.windStreams.setLitterSpread(1)
        self.windStreams.factory.setLifespanBase(streamLifespan)
        self.windStreams.factory.setLifespanSpread(0.25)
        self.windStreams.factory.setMassBase(0.3)  # Light like air
        self.windStreams.factory.setMassSpread(0.15)
        self.windStreams.factory.setTerminalVelocityBase(500.0)  # Fast wind movement
        self.windStreams.factory.setTerminalVelocitySpread(150.0)
        
        # Wind streams renderer - white/greyish
        self.windStreams.renderer.setAlphaMode(3)  # PRALPHANONE
        self.windStreams.renderer.setUserAlpha(1.0)
        self.windStreams.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.windStreams.renderer.setAlphaDisable(0)
        self.windStreams.renderer.setAnimAngleFlag(1)  # Animated for wind
        self.windStreams.renderer.setNonanimatedTheta(0.0)
        
        # Load texture for wind streams - use white glow for airy effect
        try:
            windModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
            if not windModel.isEmpty():
                windTemplate = windModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                if not windTemplate.isEmpty():
                    self.windStreams.renderer.setFromNode(windTemplate)
        except:
            pass
        
        # White/greyish color for wind - soft, airy appearance
        self.windStreams.renderer.setColor(Vec4(0.9, 0.9, 0.95, 0.7))  # Soft white-grey
        # Wind particles - elongated streaks
        self.windStreams.renderer.setInitialXScale(streamScale * 0.5)
        self.windStreams.renderer.setFinalXScale(streamScale * 0.4)  # Fade out
        self.windStreams.renderer.setInitialYScale(streamScale * 1.5)  # Elongated wind streaks
        self.windStreams.renderer.setFinalYScale(streamScale * 1.2)
        self.windStreams.renderer.setXScaleFlag(True)
        self.windStreams.renderer.setYScaleFlag(True)
        self.windStreams.renderer.setIgnoreScale(False)
        
        # Wind streams emitter - radial emission for orbital motion
        self.windStreams.emitter.setEmissionType(1)  # ETRADIATE - radial emission creates initial orbital velocity
        self.windStreams.emitter.setRadius(emitterRadius)
        self.windStreams.emitter.setAmplitude(amplitude * 1.5)  # Strong radial velocity for visible orbit
        self.windStreams.emitter.setAmplitudeSpread(0.4)  # Less spread for more consistent orbits
        # Set radiate origin to center (relative to particle effect position)
        self.windStreams.emitter.setRadiateOrigin(Point3(0, 0, 0))
        # Minimal vertical offset - let forces handle the spiral
        self.windStreams.emitter.setOffsetForce(Vec3(0.0, 0.0, spiralForceZ * 0.2))
        
        # ===== CONFIGURE GREEN LEAVES (Leaflets spiraling around) =====
        if isCFOBoss:
            leafPoolSize = int(40 * baseScale)
            leafBirthRate = 0.08  # Reduced frequency - leaves spawn less often
            leafLitterSize = 1
            leafLifespan = 2.0 * baseScale  # Longer lifespan for visible spiral
            leafScale = max(0.15, 0.25 * baseScale)
        else:
            leafPoolSize = int(20 * baseScale)
            leafBirthRate = 0.12  # Reduced frequency - much less frequent than before
            leafLitterSize = 1
            leafLifespan = 1.5 * baseScale
            leafScale = max(0.1, 0.18 * baseScale)
        
        self.greenLeaves.setPoolSize(leafPoolSize)
        self.greenLeaves.setBirthRate(leafBirthRate)
        self.greenLeaves.setLitterSize(leafLitterSize)
        self.greenLeaves.setLitterSpread(0)
        self.greenLeaves.factory.setLifespanBase(leafLifespan)
        self.greenLeaves.factory.setLifespanSpread(0.3)
        self.greenLeaves.factory.setMassBase(0.2)  # Very light like leaves
        self.greenLeaves.factory.setMassSpread(0.1)
        self.greenLeaves.factory.setTerminalVelocityBase(300.0)  # Moderate speed for visible spiral
        self.greenLeaves.factory.setTerminalVelocitySpread(100.0)
        
        # Green leaves renderer - vibrant green
        self.greenLeaves.renderer.setAlphaMode(3)  # PRALPHANONE
        self.greenLeaves.renderer.setUserAlpha(1.0)
        self.greenLeaves.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.greenLeaves.renderer.setAlphaDisable(0)
        self.greenLeaves.renderer.setAnimAngleFlag(1)  # Animated for tumbling
        self.greenLeaves.renderer.setNonanimatedTheta(0.0)
        
        # Load texture for leaves - try spark or white glow
        try:
            # Try spark texture for leaf-like appearance
            self.greenLeaves.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/spark")
        except:
            try:
                # Fallback to white glow
                leafModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
                if not leafModel.isEmpty():
                    leafTemplate = leafModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                    if not leafTemplate.isEmpty():
                        self.greenLeaves.renderer.setFromNode(leafTemplate)
            except:
                pass
        
        # Vibrant green color for leaves
        self.greenLeaves.renderer.setColor(Vec4(0.3, 0.85, 0.4, 0.9))  # Bright green
        # Leaf-shaped particles - wider than tall
        self.greenLeaves.renderer.setInitialXScale(leafScale * 1.2)  # Wider for leaf shape
        self.greenLeaves.renderer.setFinalXScale(leafScale * 1.0)  # Slight shrink
        self.greenLeaves.renderer.setInitialYScale(leafScale * 0.8)  # Slightly shorter
        self.greenLeaves.renderer.setFinalYScale(leafScale * 0.7)  # Tumble/shrink
        self.greenLeaves.renderer.setXScaleFlag(True)
        self.greenLeaves.renderer.setYScaleFlag(True)
        self.greenLeaves.renderer.setIgnoreScale(False)
        
        # Green leaves emitter - radial emission for orbital motion
        self.greenLeaves.emitter.setEmissionType(1)  # ETRADIATE - radial emission creates initial orbital velocity
        self.greenLeaves.emitter.setRadius(emitterRadius * 1.2)  # Slightly wider spread
        self.greenLeaves.emitter.setAmplitude(amplitude * 1.2)  # Good radial velocity for visible orbit
        self.greenLeaves.emitter.setAmplitudeSpread(0.3)  # Less spread for more consistent orbits
        # Set radiate origin to center (relative to particle effect position)
        self.greenLeaves.emitter.setRadiateOrigin(Point3(0, 0, 0))
        # Minimal vertical offset - let forces handle the spiral
        self.greenLeaves.emitter.setOffsetForce(Vec3(0.0, 0.0, spiralForceZ * 0.1))
        
        # ===== ADD FORCES FOR ALL LAYERS =====
        # Spiral force for wind streams - use radial emission + gentle upward force
        # The emitter's ETRADIATE type gives particles radial velocity, creating circular motion
        # Combined with upward force, this creates a natural spiral around the object
        windForceGroup = ForceGroup.ForceGroup('windSpiral')
        
        # Upward component for spiral ascent - gentle to let radial motion dominate
        windUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, spiralForceZ * 0.6), 0.7, 0)
        windUpwardForce.setActive(True)
        windForceGroup.addForce(windUpwardForce)
        
        self.particleEffect.addForceGroup(windForceGroup)
        
        # Spiral force for green leaves - radial emission + upward force creates beautiful spiral
        leafSpiralForceGroup = ForceGroup.ForceGroup('leafSpiral')
        
        # Upward component for spiral ascent - gentle to let radial motion dominate
        leafUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, spiralForceZ * 0.3), 0.4, 0)
        leafUpwardForce.setActive(True)
        leafSpiralForceGroup.addForce(leafUpwardForce)
        
        self.particleEffect.addForceGroup(leafSpiralForceGroup)
        
        # Store particles reference for cleanup
        self.particles = self.windStreams  # Keep for compatibility with existing code
        
        # Apply green glow color to safe (not CFO) - will fade in when effect starts
        if isSafe and not isCFOBoss:
            try:
                # Use centralized color management system
                # Get true original color scale
                if hasattr(self.obj, 'getTrueOriginalColorScale'):
                    originalColor = self.obj.getTrueOriginalColorScale()
                else:
                    # Fallback to current color if system not available
                    originalColor = self.obj.getColorScale()
                    if not (0.0 <= originalColor.getX() <= 2.0 and 
                            0.0 <= originalColor.getY() <= 2.0 and 
                            0.0 <= originalColor.getZ() <= 2.0 and 
                            0.0 <= originalColor.getW() <= 2.0):
                        originalColor = VBase4(1, 1, 1, 1)
                
                # Calculate lighter green tint (less intense)
                # Blend between original and light leaf green: 70% original, 30% green
                # This creates a subtle glow effect
                greenTint = VBase4(0.5, 0.9, 0.5, 1.0)  # Light leaf green tint
                blendFactor = 0.3  # 30% of the tint (lighter effect)
                
                glowColor = VBase4(
                    originalColor.getX() * (1.0 - blendFactor) + greenTint.getX() * blendFactor,
                    originalColor.getY() * (1.0 - blendFactor) + greenTint.getY() * blendFactor,
                    originalColor.getZ() * (1.0 - blendFactor) + greenTint.getZ() * blendFactor,
                    originalColor.getW()  # Alpha - preserve original
                )
                
                # Store the glow color for fade in/out
                self.obj._windedGlowColor = glowColor
                self.notify.info("Prepared green glow color for safe (will fade in)")
            except Exception as e:
                self.notify.warning(f"Error preparing glow color for safe: {e}")
        
        # Set rendering properties for wind particles
        self.effectNode.setLightOff()
        self.effectNode.setFogOff()
        self.effectNode.setDepthWrite(False)  # Don't write to depth buffer (so particles won't occlude things behind them)
        # Keep depthTest enabled (default) so particles still respect depth for proper rendering
        # Wind particles render at lower priority than damage numbers
        # Wind at -50 (low), damage numbers at 100 (highest)
        # Use negative priority to ensure wind renders before damage numbers
        self.effectNode.setBin('fixed', -50)
        self.effectNode.setTransparency(1)  # Enable transparency on the effect node
        # Additive blending for wind glow
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
        for particleLayer in ['windStreams', 'greenLeaves', 'particles']:
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
        
        # Check all wind particle layers
        for particleLayer in ['windStreams', 'greenLeaves', 'particles']:
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
        for particleLayer in ['windStreams', 'greenLeaves', 'particles']:
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
            return f'windedEffect-{self.obj.getDoId()}-{name}'
        return f'windedEffect-{name}'
    
    def _fadeInSafeColor(self):
        """Fade in the green glow color on the safe."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from ...craning.objects import DistributedCashbotSafe
            from ..boss import BossCog

            if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe) and not isinstance(self.obj, BossCog.BossCog):
                if hasattr(self.obj, '_windedGlowColor'):
                    # Use centralized color management system
                    if hasattr(self.obj, 'registerColorModification'):
                        self.obj.registerColorModification('winded', self.obj._windedGlowColor, priority='elemental')
                        self.notify.info("Registered winded color modification on safe")
                    else:
                        # Fallback if system not available
                        if hasattr(self.obj, '_windedColorInterval'):
                            if self.obj._windedColorInterval:
                                self.obj._windedColorInterval.finish()
                        self.obj._windedColorInterval = LerpColorScaleInterval(
                            self.obj,
                            duration=0.4,
                            colorScale=self.obj._windedGlowColor,
                            blendType='easeInOut'
                        )
                        self.obj._windedColorInterval.start()
                        self.notify.info("Fading in green glow color on safe (fallback)")
        except Exception as e:
            self.notify.warning(f"Error fading in safe color: {e}")
    
    def _fadeOutSafeColor(self):
        """Fade out the green glow color on the safe back to original."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from ...craning.objects import DistributedCashbotSafe
            from ..boss import BossCog

            if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe) and not isinstance(self.obj, BossCog.BossCog):
                # Use centralized color management system
                if hasattr(self.obj, 'unregisterColorModification'):
                    self.obj.unregisterColorModification('winded', priority='elemental')
                    self.notify.info("Unregistered winded color modification on safe")
                else:
                    # Fallback if system not available
                    if hasattr(self.obj, '_originalWindedColorScale'):
                        if hasattr(self.obj, '_windedColorInterval'):
                            if self.obj._windedColorInterval:
                                self.obj._windedColorInterval.finish()
                        self.obj._windedColorInterval = LerpColorScaleInterval(
                            self.obj,
                            duration=0.4,
                            colorScale=self.obj._originalWindedColorScale,
                            blendType='easeInOut'
                        )
                        self.obj._windedColorInterval.start()
                        self.notify.info("Fading out green glow color on safe (fallback)")
        except Exception as e:
            self.notify.warning(f"Error fading out safe color: {e}")
    
    def _restoreSafeColor(self):
        """Immediately restore the original color of the safe if it was changed (no fade)."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from ...craning.objects import DistributedCashbotSafe
            from ..boss import BossCog

            if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe) and not isinstance(self.obj, BossCog.BossCog):
                # Use centralized color management system
                if hasattr(self.obj, 'unregisterColorModification'):
                    self.obj.unregisterColorModification('winded', priority='elemental')
                    self.notify.info("Unregistered winded color modification on safe (immediate)")
                else:
                    # Fallback if system not available
                    if hasattr(self.obj, '_windedColorInterval'):
                        if self.obj._windedColorInterval:
                            self.obj._windedColorInterval.finish()
                        self.obj._windedColorInterval = None
                    if hasattr(self.obj, '_originalWindedColorScale'):
                        self.obj.setColorScale(self.obj._originalWindedColorScale)
                        self.notify.info("Restored original color to safe (fallback)")
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
        
        # Stop all wind particle layers from spawning
        for particleLayer in ['windStreams', 'greenLeaves', 'particles']:
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
        """Update wind intensity based on stack count."""
        super().updateStack(stackCount)
        
        if not self.active:
            return
        
        # Update all wind layers based on stack count
        # More stacks = more intense wind effect (faster birth rate, brighter colors)
        intensityMultiplier = 1.0 / max(1, stackCount)
        
        # Update wind streams
        if hasattr(self, 'windStreams') and self.windStreams:
            try:
                baseStreamBirthRate = 0.02
                self.windStreams.setBirthRate(baseStreamBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # Brighter white-grey for more stacks
                    self.windStreams.renderer.setColor(Vec4(1.0, 1.0, 1.0, 0.85))  # Brighter white
            except:
                pass
        
        # Update green leaves
        if hasattr(self, 'greenLeaves') and self.greenLeaves:
            try:
                baseLeafBirthRate = 0.12
                self.greenLeaves.setBirthRate(baseLeafBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More vibrant green for more stacks
                    self.greenLeaves.renderer.setColor(Vec4(0.25, 0.9, 0.35, 0.95))  # Brighter green
            except:
                pass
        
        # Legacy support for self.particles (which points to windStreams)
        if hasattr(self, 'particles') and self.particles:
            try:
                baseBirthRate = 0.02
                self.particles.setBirthRate(baseBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    self.particles.renderer.setColor(Vec4(1.0, 1.0, 1.0, 0.85))  # Brighter white
            except:
                pass



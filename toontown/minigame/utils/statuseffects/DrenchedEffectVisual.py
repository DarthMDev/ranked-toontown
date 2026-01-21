"""
Visual effect for the DRENCHED status effect.

Creates animated water droplets and mist particles around the object.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, VBase4
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import LerpColorScaleInterval
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase


class DrenchedEffectVisual(StatusEffectVisualBase):
    """
    Visual for the DRENCHED status effect.
    
    Creates a particle effect with:
    - Blue water droplets falling from the object
    - Misty water particles around the object
    - Scaled appropriately to object size
    """
    
    def create(self):
        """Create the water particle effect."""
        if self.active:
            return
            
        # Create root node for effect
        self._createEffectNode('drenchedEffect')
        
        # Get object dimensions for scaling
        minPt, maxPt, center, height = self.objDimensions
        
        # Calculate width (X and Y dimensions) for objects that are wide
        widthX = maxPt.getX() - minPt.getX()
        widthY = maxPt.getY() - minPt.getY()
        avgWidth = (widthX + widthY) / 2.0
        
        # Debug logging
        self.notify.info(f"Creating drenched effect for {self.obj.getName()}: height={height}, width={avgWidth}, minPt={minPt}, maxPt={maxPt}, center={center}")
        
        # Check if this is the CFO boss (pyramid-shaped, wide at bottom)
        isCFOBoss = False
        isSafe = False
        try:
            from ..boss import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying larger, wider water effect")
            else:
                # Check if this is a safe (not CFO)
                from ...craning.objects import DistributedCashbotSafe
                if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe):
                    isSafe = True
                    self.notify.info("Detected safe - will apply blue glow color")
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
        
        self.notify.info(f"Drenched effect baseScale: {baseScale} (isCFO={isCFOBoss})")
        
        # Create a renderParent node for particle physics with proper depth settings
        # This ensures particles don't occlude other objects
        self.particleRenderParent = render.attachNewNode('drenchedParticleRenderParent')
        self.particleRenderParent.setBin('fixed', -50)  # Lower priority than damage numbers
        self.particleRenderParent.setDepthWrite(False)  # Don't write to depth (won't occlude things behind)
        # Keep depthTest enabled (default) so particles respect depth for proper rendering
        self.particleRenderParent.setLightOff()
        self.particleRenderParent.setFogOff()
        
        # Create the particle effect (don't parent it yet - start() will handle that)
        self.particleEffect = ParticleEffect.ParticleEffect('DrenchedWater')
        
        # Store the desired position for later - position at object top in local space
        # Since effectNode is attached to obj, we use local coordinates
        # Position lower on the object (not at the very top)
        if isCFOBoss:
            # Use a smaller offset from center so it adapts better when CFO moves (stunned, etc.)
            # Since effectNode is attached to CFO, local coords move with CFO
            # Use center + smaller offset to stay near top but adapt to CFO's current position
            topOffset = center.getZ() + (height * 0.2)  # Center + 20% of height upward (smaller offset)
        else:
            topOffset = height * 0.6  # Lower on safes - start droplets mid-way down
        self.particlePos = Point3(0, 0, topOffset)
        
        # ===== LAYER 1: WATER DROPLETS (Falling raindrops) =====
        self.waterDroplets = Particles.Particles('waterDroplets')
        self.waterDroplets.setFactory('PointParticleFactory')
        self.waterDroplets.setRenderer('SpriteParticleRenderer')
        self.waterDroplets.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.waterDroplets)
        
        # ===== LAYER 2: MIST (Floating water mist) =====
        self.mist = Particles.Particles('mist')
        self.mist.setFactory('PointParticleFactory')
        self.mist.setRenderer('SpriteParticleRenderer')
        self.mist.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.mist)
        
        # Calculate emitter settings
        if isCFOBoss:
            emitterRadius = max(2.0, avgWidth / 2.0 * 0.8)
            amplitude = 1.5 * baseScale
            downwardForceZ = -2.0 * baseScale  # Reduced from -3.0 (less downward force = don't fall as far)
            mistRiseZ = 1.0 * baseScale  # Mist rises slightly
        else:
            # Wider spread for safes - use larger multiplier for radius
            emitterRadius = max(0.8, (maxPt.getX() - minPt.getX()) / 2.0) * 1.5  # Increased from 0.6 to 1.5 for wider spread
            amplitude = 1.0 * baseScale
            downwardForceZ = -1.5 * baseScale  # Reduced from -2.0 (less downward force = don't fall as far)
            mistRiseZ = 0.5 * baseScale
        
        # ===== CONFIGURE WATER DROPLETS (Falling raindrops) =====
        if isCFOBoss:
            dropletPoolSize = int(60 * baseScale)  # Reduced from 100
            dropletBirthRate = 0.04  # Increased from 0.02 (less frequent = less water)
            dropletLitterSize = 3  # Reduced from 4
            dropletLifespan = 1.2 * baseScale  # Longer lifespan so droplets can fall from top to bottom of pyramid
            dropletScale = max(0.1, 0.15 * baseScale)  # Reduced from 0.15-0.25 (smaller droplets)
        else:
            dropletPoolSize = int(30 * baseScale)  # Reduced from 50
            dropletBirthRate = 0.06  # Increased from 0.03 (less frequent = less water)
            dropletLitterSize = 1  # Reduced from 2
            dropletLifespan = 0.4 * baseScale  # Reduced from 0.6 (shorter lifespan = don't fall as far)
            dropletScale = max(0.05, 0.08 * baseScale)  # Reduced from 0.08-0.12 (smaller droplets)
        
        self.waterDroplets.setPoolSize(dropletPoolSize)
        self.waterDroplets.setBirthRate(dropletBirthRate)
        self.waterDroplets.setLitterSize(dropletLitterSize)
        self.waterDroplets.setLitterSpread(1)
        self.waterDroplets.factory.setLifespanBase(dropletLifespan)
        self.waterDroplets.factory.setLifespanSpread(0.2)
        self.waterDroplets.factory.setMassBase(1.2)  # Heavier for falling effect
        self.waterDroplets.factory.setMassSpread(0.2)
        self.waterDroplets.factory.setTerminalVelocityBase(500.0)  # Fast falling
        self.waterDroplets.factory.setTerminalVelocitySpread(100.0)
        
        # Water droplets renderer - misty blue
        self.waterDroplets.renderer.setAlphaMode(3)  # PRALPHANONE
        self.waterDroplets.renderer.setUserAlpha(1.0)
        self.waterDroplets.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.waterDroplets.renderer.setAlphaDisable(0)
        self.waterDroplets.renderer.setAnimAngleFlag(0)  # No rotation for droplets
        self.waterDroplets.renderer.setNonanimatedTheta(0.0)
        
        # Load raindrop texture
        try:
            self.waterDroplets.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/raindrop")
        except:
            pass
        
        # Misty blue color for droplets (0.6, 0.8, 0.9, 1.0) - slightly brighter
        self.waterDroplets.renderer.setColor(Vec4(0.6, 0.8, 0.9, 0.9))  # Misty blue
        # Smaller, narrower droplets
        self.waterDroplets.renderer.setInitialXScale(dropletScale * 0.7)  # Reduced from 0.5 (narrower)
        self.waterDroplets.renderer.setFinalXScale(dropletScale * 0.7)  # Reduced from 0.7 (narrower)
        self.waterDroplets.renderer.setInitialYScale(dropletScale * 1.2)  # Reduced from 1.2 (shorter)
        self.waterDroplets.renderer.setFinalYScale(dropletScale * 1.2)  # Reduced from 1.5 (shorter)
        self.waterDroplets.renderer.setXScaleFlag(True)
        self.waterDroplets.renderer.setYScaleFlag(True)
        self.waterDroplets.renderer.setIgnoreScale(False)
        
        # Droplet emitter - from top of object, falling down
        self.waterDroplets.emitter.setEmissionType(1)  # ETRADIATE
        if isCFOBoss:
            # Pyramid/cone effect: small radius at top, radiates outward as it falls
            dropletEmitterRadius = 0.3  # Small radius at the top of the pyramid
            # Set radiate origin to a point below (at the base) to create pyramid spread
            # This makes particles radiate outward as they fall down
            baseRadiateOrigin = Point3(0.0, 0.0, -height * 0.8)  # Point below at pyramid base
            self.waterDroplets.emitter.setRadiateOrigin(baseRadiateOrigin)
            self.waterDroplets.emitter.setAmplitude(amplitude * 1.2)  # More spread for pyramid effect
        else:
            dropletEmitterRadius = emitterRadius * 0.7  # Full radius for safes (wider spread)
            self.waterDroplets.emitter.setAmplitude(amplitude * 0.5)  # Less spread
        self.waterDroplets.emitter.setRadius(dropletEmitterRadius)
        self.waterDroplets.emitter.setAmplitudeSpread(0.4)
        self.waterDroplets.emitter.setOffsetForce(Vec3(0.0, 0.0, downwardForceZ))  # Downward force
        
        # ===== CONFIGURE MIST (Floating water mist) =====
        if isCFOBoss:
            mistPoolSize = int(50 * baseScale)  # Reduced from 80
            mistBirthRate = 0.08  # Increased from 0.04 (less frequent = less mist)
            mistLitterSize = 2  # Reduced from 3
            mistLifespan = 1.2 * baseScale
            mistScale = max(0.3, 0.4 * baseScale)
        else:
            mistPoolSize = int(25 * baseScale)  # Reduced from 40
            mistBirthRate = 0.1  # Increased from 0.05 (less frequent = less mist)
            mistLitterSize = 1  # Reduced from 2
            mistLifespan = 1.0 * baseScale
            mistScale = max(0.2, 0.3 * baseScale)
        
        self.mist.setPoolSize(mistPoolSize)
        self.mist.setBirthRate(mistBirthRate)
        self.mist.setLitterSize(mistLitterSize)
        self.mist.setLitterSpread(1)
        self.mist.factory.setLifespanBase(mistLifespan)
        self.mist.factory.setLifespanSpread(0.4)
        self.mist.factory.setMassBase(0.4)  # Light for floating
        self.mist.factory.setMassSpread(0.15)
        self.mist.factory.setTerminalVelocityBase(150.0)  # Slow floating
        self.mist.factory.setTerminalVelocitySpread(50.0)
        
        # Mist renderer - lighter blue mist
        self.mist.renderer.setAlphaMode(3)  # PRALPHANONE
        self.mist.renderer.setUserAlpha(1.0)
        self.mist.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.mist.renderer.setAlphaDisable(0)
        self.mist.renderer.setAnimAngleFlag(1)  # Animated for mist
        self.mist.renderer.setNonanimatedTheta(0.0)
        
        # Try to load raindrop texture for mist, or use white glow
        try:
            self.mist.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/raindrop")
        except:
            try:
                # Fallback to white glow
                mistModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
                if not mistModel.isEmpty():
                    mistTemplate = mistModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                    if not mistTemplate.isEmpty():
                        self.mist.renderer.setFromNode(mistTemplate)
            except:
                pass
        
        # Lighter misty blue color for mist (more transparent)
        self.mist.renderer.setColor(Vec4(0.7, 0.85, 0.95, 0.6))  # Lighter, more transparent blue
        # Mist particles grow as they float and fade
        self.mist.renderer.setInitialXScale(mistScale * 0.6)
        self.mist.renderer.setFinalXScale(mistScale * 0.6)  # Expand as they float
        self.mist.renderer.setInitialYScale(mistScale * 1.2)
        self.mist.renderer.setFinalYScale(mistScale * 1.2)  # Taller as they float
        self.mist.renderer.setXScaleFlag(True)
        self.mist.renderer.setYScaleFlag(True)
        self.mist.renderer.setIgnoreScale(False)
        
        # Mist emitter - wider spread, around the object
        self.mist.emitter.setEmissionType(1)  # ETRADIATE
        if isCFOBoss:
            mistEmitterRadius = emitterRadius * 1.0  # Wider spread for CFO
        else:
            mistEmitterRadius = emitterRadius * 0.8  # Reduced spread for safes (was 1.0)
        self.mist.emitter.setRadius(mistEmitterRadius)
        self.mist.emitter.setAmplitude(amplitude * 0.3)  # Very gentle
        self.mist.emitter.setAmplitudeSpread(0.8)  # More random spread
        # Mist rises slightly and floats
        self.mist.emitter.setOffsetForce(Vec3(0.0, 0.0, mistRiseZ))  # Slight upward
        
        # ===== ADD FORCES FOR ALL LAYERS =====
        # Downward force for water droplets (gravity) - reduced to prevent falling too far
        dropletForceGroup = ForceGroup.ForceGroup('dropletFall')
        if isCFOBoss:
            downwardForceStrength = -5.0 * baseScale  # Reduced from -8.0
        else:
            downwardForceStrength = -4.0 * baseScale  # Reduced from -8.0
        downwardForce = LinearVectorForce(Vec3(0.0, 0.0, downwardForceStrength), 1.0, 0)
        downwardForce.setActive(True)
        dropletForceGroup.addForce(downwardForce)
        self.particleEffect.addForceGroup(dropletForceGroup)
        
        # Gentle upward force for mist (floating effect)
        mistForceGroup = ForceGroup.ForceGroup('mistFloat')
        mistUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, mistRiseZ * 0.5), 0.3, 0)
        mistUpwardForce.setActive(True)
        mistForceGroup.addForce(mistUpwardForce)
        self.particleEffect.addForceGroup(mistForceGroup)
        
        # Store particles reference for cleanup
        self.particles = self.waterDroplets  # Keep for compatibility with existing code
        
        # Apply blue glow color to safe (not CFO) - will fade in when effect starts
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
                
                # Calculate lighter blue tint (less intense)
                # Blend between original and misty blue: 70% original, 30% blue
                # This creates a subtle glow effect
                blueTint = VBase4(0.6, 0.8, 0.9, 1.0)  # Misty blue tint
                blendFactor = 0.5  # 50% of the tint (lighter effect)
                
                glowColor = VBase4(
                    originalColor.getX() * (1.0 - blendFactor) + blueTint.getX() * blendFactor,
                    originalColor.getY() * (1.0 - blendFactor) + blueTint.getY() * blendFactor,
                    originalColor.getZ() * (1.0 - blendFactor) + blueTint.getZ() * blendFactor,
                    originalColor.getW()  # Alpha - preserve original
                )
                
                # Store the glow color for fade in/out
                self.obj._drenchedGlowColor = glowColor
                self.notify.info("Prepared blue glow color for safe (will fade in)")
            except Exception as e:
                self.notify.warning(f"Error preparing glow color for safe: {e}")
        
        # Set rendering properties for water particles
        self.effectNode.setLightOff()
        self.effectNode.setFogOff()
        self.effectNode.setDepthWrite(False)  # Don't write to depth buffer (so particles won't occlude things behind them)
        # Keep depthTest enabled (default) so particles still respect depth for proper rendering
        # Water particles render at lower priority than damage numbers
        # Water at -50 (low), damage numbers at 100 (highest)
        # Use negative priority to ensure water renders before damage numbers
        self.effectNode.setBin('fixed', -50)
        self.effectNode.setTransparency(1)  # Enable transparency on the effect node
        # Additive blending for water glow
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
        for particleLayer in ['waterDroplets', 'mist', 'particles']:
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
        
        # Check all water and mist particle layers
        for particleLayer in ['waterDroplets', 'mist', 'particles']:
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
        for particleLayer in ['waterDroplets', 'mist', 'particles']:
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
            return f'drenchedEffect-{self.obj.getDoId()}-{name}'
        return f'drenchedEffect-{name}'
    
    def _fadeInSafeColor(self):
        """Fade in the blue glow color on the safe."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from ...craning.objects import DistributedCashbotSafe
            from ..boss import BossCog

            if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe) and not isinstance(self.obj, BossCog.BossCog):
                if hasattr(self.obj, '_drenchedGlowColor'):
                    # Use centralized color management system
                    if hasattr(self.obj, 'registerColorModification'):
                        self.obj.registerColorModification('drenched', self.obj._drenchedGlowColor, priority='elemental')
                        self.notify.info("Registered drenched color modification on safe")
                    else:
                        # Fallback if system not available
                        if hasattr(self.obj, '_drenchedColorInterval'):
                            if self.obj._drenchedColorInterval:
                                self.obj._drenchedColorInterval.finish()
                        self.obj._drenchedColorInterval = LerpColorScaleInterval(
                            self.obj,
                            duration=0.4,
                            colorScale=self.obj._drenchedGlowColor,
                            blendType='easeInOut'
                        )
                        self.obj._drenchedColorInterval.start()
                        self.notify.info("Fading in blue glow color on safe (fallback)")
        except Exception as e:
            self.notify.warning(f"Error fading in safe color: {e}")
    
    def _fadeOutSafeColor(self):
        """Fade out the blue glow color on the safe back to original."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from ...craning.objects import DistributedCashbotSafe
            from ..boss import BossCog

            if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe) and not isinstance(self.obj, BossCog.BossCog):
                # Use centralized color management system
                if hasattr(self.obj, 'unregisterColorModification'):
                    self.obj.unregisterColorModification('drenched', priority='elemental')
                    self.notify.info("Unregistered drenched color modification on safe")
                else:
                    # Fallback if system not available
                    if hasattr(self.obj, '_originalDrenchedColorScale'):
                        if hasattr(self.obj, '_drenchedColorInterval'):
                            if self.obj._drenchedColorInterval:
                                self.obj._drenchedColorInterval.finish()
                        self.obj._drenchedColorInterval = LerpColorScaleInterval(
                            self.obj,
                            duration=0.4,
                            colorScale=self.obj._originalDrenchedColorScale,
                            blendType='easeInOut'
                        )
                        self.obj._drenchedColorInterval.start()
                        self.notify.info("Fading out blue glow color on safe (fallback)")
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
                    self.obj.unregisterColorModification('drenched', priority='elemental')
                    self.notify.info("Unregistered drenched color modification on safe (immediate)")
                else:
                    # Fallback if system not available
                    if hasattr(self.obj, '_drenchedColorInterval'):
                        if self.obj._drenchedColorInterval:
                            self.obj._drenchedColorInterval.finish()
                        self.obj._drenchedColorInterval = None
                    if hasattr(self.obj, '_originalDrenchedColorScale'):
                        self.obj.setColorScale(self.obj._originalDrenchedColorScale)
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
        
        # Stop all water and mist particle layers from spawning
        for particleLayer in ['waterDroplets', 'mist', 'particles']:
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
        """Update water intensity based on stack count."""
        super().updateStack(stackCount)
        
        if not self.active:
            return
        
        # Update all water layers based on stack count
        # More stacks = more intense water effect (faster birth rate, more droplets)
        intensityMultiplier = 1.0 / max(1, stackCount)
        
        # Update water droplets
        if hasattr(self, 'waterDroplets') and self.waterDroplets:
            try:
                baseDropletBirthRate = 0.06  # Updated to match new safe birth rate
                self.waterDroplets.setBirthRate(baseDropletBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More intense blue for more stacks
                    self.waterDroplets.renderer.setColor(Vec4(0.5, 0.75, 0.95, 0.95))  # Slightly brighter blue
            except:
                pass
        
        # Update mist
        if hasattr(self, 'mist') and self.mist:
            try:
                baseMistBirthRate = 0.1  # Updated to match new safe birth rate
                self.mist.setBirthRate(baseMistBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More visible mist for more stacks
                    self.mist.renderer.setColor(Vec4(0.7, 0.85, 0.95, 0.7))  # Slightly more opaque
            except:
                pass
        
        # Legacy support for self.particles (which points to waterDroplets)
        if hasattr(self, 'particles') and self.particles:
            try:
                baseBirthRate = 0.06  # Updated to match new safe birth rate
                self.particles.setBirthRate(baseBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    self.particles.renderer.setColor(Vec4(0.5, 0.75, 0.95, 0.95))  # Brighter blue
            except:
                pass


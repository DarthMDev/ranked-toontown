"""
Visual effect for the WINDED status effect.

Creates animated wind with leaf-like particles swirling around the object.
Features light green, natural-looking leaves fluttering in the wind.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, VBase4
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import Sequence, LerpColorScaleInterval, Wait, Func, LerpPosInterval, Parallel
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase
import math


class WindedEffectVisual(StatusEffectVisualBase):
    """
    Visual for the WINDED status effect.
    
    Creates a particle effect with:
    - Leaf-like particles swirling in the wind
    - Light green color palette (natural leaf tones)
    - Small leaf wisps floating around
    - Gentle air turbulence with leaf undertones
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
            from toontown.suit import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying larger, wider wind effect")
            else:
                # Check if this is a safe (not CFO)
                from toontown.coghq import DistributedCashbotBossSafe
                if isinstance(self.obj, DistributedCashbotBossSafe.DistributedCashbotBossSafe):
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
        
        # ===== LAYER 1: WIND STREAMS (Swirling leaf particles) =====
        self.windStreams = Particles.Particles('windStreams')
        self.windStreams.setFactory('PointParticleFactory')
        self.windStreams.setRenderer('SpriteParticleRenderer')
        self.windStreams.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.windStreams)
        
        # ===== LAYER 2: WIND WISPS (Small floating leaf particles) =====
        self.windWisps = Particles.Particles('windWisps')
        self.windWisps.setFactory('PointParticleFactory')
        self.windWisps.setRenderer('SpriteParticleRenderer')
        self.windWisps.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.windWisps)
        
        # ===== LAYER 3: AIR TURBULENCE (Gentle air with leaf undertones) =====
        self.airTurbulence = Particles.Particles('airTurbulence')
        self.airTurbulence.setFactory('PointParticleFactory')
        self.airTurbulence.setRenderer('SpriteParticleRenderer')
        self.airTurbulence.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.airTurbulence)
        
        # Calculate emitter settings
        if isCFOBoss:
            emitterRadius = max(2.0, avgWidth / 2.0 * 0.8)
            amplitude = 2.0 * baseScale
            spiralForceZ = 3.0 * baseScale  # Upward spiral force
            turbulenceRiseZ = 1.5 * baseScale
        else:
            # Wider spread for safes to ensure wind circles around them
            emitterRadius = max(0.8, (maxPt.getX() - minPt.getX()) / 2.0) * 1.2
            amplitude = 1.5 * baseScale
            spiralForceZ = 2.5 * baseScale
            turbulenceRiseZ = 1.0 * baseScale
        
        # ===== CONFIGURE WIND STREAMS (Swirling leaf particles) =====
        if isCFOBoss:
            streamPoolSize = int(100 * baseScale)
            streamBirthRate = 0.02
            streamLitterSize = 4
            streamLifespan = 0.8 * baseScale
            streamScale = max(0.15, 0.25 * baseScale)
        else:
            streamPoolSize = int(50 * baseScale)
            streamBirthRate = 0.03
            streamLitterSize = 2
            streamLifespan = 0.6 * baseScale
            streamScale = max(0.08, 0.15 * baseScale)
        
        self.windStreams.setPoolSize(streamPoolSize)
        self.windStreams.setBirthRate(streamBirthRate)
        self.windStreams.setLitterSize(streamLitterSize)
        self.windStreams.setLitterSpread(2)
        self.windStreams.factory.setLifespanBase(streamLifespan)
        self.windStreams.factory.setLifespanSpread(0.3)  # More variation for natural leaf movement
        self.windStreams.factory.setMassBase(0.4)  # Very light like leaves
        self.windStreams.factory.setMassSpread(0.2)  # Varied weight for natural flutter
        self.windStreams.factory.setTerminalVelocityBase(450.0)  # Medium-fast for leaf flutter
        self.windStreams.factory.setTerminalVelocitySpread(180.0)  # More variation
        
        # Wind streams renderer - bright greenish-white
        self.windStreams.renderer.setAlphaMode(3)  # PRALPHANONE
        self.windStreams.renderer.setUserAlpha(1.0)
        self.windStreams.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.windStreams.renderer.setAlphaDisable(0)
        self.windStreams.renderer.setAnimAngleFlag(1)  # Animated for wind
        self.windStreams.renderer.setNonanimatedTheta(0.0)
        
        # Load texture for wind streams
        try:
            # Try to use spark texture for wind streaks
            self.windStreams.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/spark")
        except:
            try:
                # Fallback to white glow
                windModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
                if not windModel.isEmpty():
                    windTemplate = windModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                    if not windTemplate.isEmpty():
                        self.windStreams.renderer.setFromNode(windTemplate)
            except:
                pass
        
        # Light green color for leaf-like wind streams
        # Softer, more natural leaf color
        self.windStreams.renderer.setColor(Vec4(0.6, 0.95, 0.5, 0.85))  # Light leaf green
        # Leaf-shaped particles - slightly elongated but not streaks
        self.windStreams.renderer.setInitialXScale(streamScale * 0.7)  # Wider for leaf shape
        self.windStreams.renderer.setFinalXScale(streamScale * 0.6)  # Shrink slightly
        self.windStreams.renderer.setInitialYScale(streamScale * 1.2)  # Slightly elongated leaf
        self.windStreams.renderer.setFinalYScale(streamScale * 1.0)  # Tumble/shrink
        self.windStreams.renderer.setXScaleFlag(True)
        self.windStreams.renderer.setYScaleFlag(True)
        self.windStreams.renderer.setIgnoreScale(False)
        
        # Wind streams emitter - circular emission for spiral effect
        self.windStreams.emitter.setEmissionType(1)  # ETRADIATE
        self.windStreams.emitter.setRadius(emitterRadius)
        self.windStreams.emitter.setAmplitude(amplitude * 1.2)  # Strong radial velocity for spiral
        self.windStreams.emitter.setAmplitudeSpread(0.6)
        # Wind spirals upward
        self.windStreams.emitter.setOffsetForce(Vec3(0.0, 0.0, spiralForceZ))
        
        # ===== CONFIGURE WIND WISPS (Small floating leaf particles) =====
        if isCFOBoss:
            wispPoolSize = int(80 * baseScale)
            wispBirthRate = 0.03
            wispLitterSize = 3
            wispLifespan = 1.0 * baseScale
            wispScale = max(0.2, 0.35 * baseScale)
        else:
            wispPoolSize = int(40 * baseScale)
            wispBirthRate = 0.045
            wispLitterSize = 2
            wispLifespan = 0.8 * baseScale
            wispScale = max(0.12, 0.25 * baseScale)
        
        self.windWisps.setPoolSize(wispPoolSize)
        self.windWisps.setBirthRate(wispBirthRate)
        self.windWisps.setLitterSize(wispLitterSize)
        self.windWisps.setLitterSpread(1)
        self.windWisps.factory.setLifespanBase(wispLifespan)
        self.windWisps.factory.setLifespanSpread(0.4)  # More variation for natural floating
        self.windWisps.factory.setMassBase(0.25)  # Very light like small leaves
        self.windWisps.factory.setMassSpread(0.15)  # Varied weight
        self.windWisps.factory.setTerminalVelocityBase(320.0)  # Gentle floating
        self.windWisps.factory.setTerminalVelocitySpread(140.0)  # More variation for flutter
        
        # Wind wisps renderer - lighter green-white
        self.windWisps.renderer.setAlphaMode(3)  # PRALPHANONE
        self.windWisps.renderer.setUserAlpha(1.0)
        self.windWisps.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.windWisps.renderer.setAlphaDisable(0)
        self.windWisps.renderer.setAnimAngleFlag(1)
        self.windWisps.renderer.setNonanimatedTheta(0.0)
        
        # Load texture for wisps
        try:
            # Use white glow for soft wisps
            wispModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
            if not wispModel.isEmpty():
                wispTemplate = wispModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                if not wispTemplate.isEmpty():
                    self.windWisps.renderer.setFromNode(wispTemplate)
        except:
            pass
        
        # Softer, lighter leaf green for wisps
        self.windWisps.renderer.setColor(Vec4(0.7, 1.0, 0.65, 0.65))  # Light leaf green, more transparent
        # Smaller leaf particles
        self.windWisps.renderer.setInitialXScale(wispScale * 0.9)
        self.windWisps.renderer.setFinalXScale(wispScale * 1.0)  # Slight grow while floating
        self.windWisps.renderer.setInitialYScale(wispScale * 1.1)  # Slightly oval like small leaves
        self.windWisps.renderer.setFinalYScale(wispScale * 1.15)
        self.windWisps.renderer.setXScaleFlag(True)
        self.windWisps.renderer.setYScaleFlag(True)
        self.windWisps.renderer.setIgnoreScale(False)
        
        # Wisps emitter - wider spread
        self.windWisps.emitter.setEmissionType(1)  # ETRADIATE
        self.windWisps.emitter.setRadius(emitterRadius * 1.1)
        self.windWisps.emitter.setAmplitude(amplitude * 0.8)
        self.windWisps.emitter.setAmplitudeSpread(0.9)  # More random
        # Wisps drift upward gently
        self.windWisps.emitter.setOffsetForce(Vec3(0.0, 0.0, spiralForceZ * 0.6))
        
        # ===== CONFIGURE AIR TURBULENCE (Gentle air puffs with leaf tint) =====
        if isCFOBoss:
            turbulencePoolSize = int(60 * baseScale)
            turbulenceBirthRate = 0.06
            turbulenceLitterSize = 2
            turbulenceLifespan = 1.5 * baseScale
            turbulenceScale = max(0.35, 0.55 * baseScale)
        else:
            turbulencePoolSize = int(30 * baseScale)
            turbulenceBirthRate = 0.08
            turbulenceLitterSize = 1
            turbulenceLifespan = 1.2 * baseScale
            turbulenceScale = max(0.25, 0.4 * baseScale)
        
        self.airTurbulence.setPoolSize(turbulencePoolSize)
        self.airTurbulence.setBirthRate(turbulenceBirthRate)
        self.airTurbulence.setLitterSize(turbulenceLitterSize)
        self.airTurbulence.setLitterSpread(1)
        self.airTurbulence.factory.setLifespanBase(turbulenceLifespan)
        self.airTurbulence.factory.setLifespanSpread(0.5)
        self.airTurbulence.factory.setMassBase(0.25)  # Very light
        self.airTurbulence.factory.setMassSpread(0.1)
        self.airTurbulence.factory.setTerminalVelocityBase(200.0)  # Slow drift
        self.airTurbulence.factory.setTerminalVelocitySpread(60.0)
        
        # Turbulence renderer - very soft white with hint of green
        self.airTurbulence.renderer.setAlphaMode(3)  # PRALPHANONE
        self.airTurbulence.renderer.setUserAlpha(1.0)
        self.airTurbulence.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.airTurbulence.renderer.setAlphaDisable(0)
        self.airTurbulence.renderer.setAnimAngleFlag(1)
        self.airTurbulence.renderer.setNonanimatedTheta(0.0)
        
        # Load texture for turbulence
        try:
            turbulenceModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
            if not turbulenceModel.isEmpty():
                turbulenceTemplate = turbulenceModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                if not turbulenceTemplate.isEmpty():
                    self.airTurbulence.renderer.setFromNode(turbulenceTemplate)
        except:
            pass
        
        # Very soft light green - gentle leaf undertone
        self.airTurbulence.renderer.setColor(Vec4(0.85, 1.0, 0.8, 0.45))  # Pale leaf green, very transparent
        # Turbulence puffs grow as they dissipate
        self.airTurbulence.renderer.setInitialXScale(turbulenceScale * 0.6)
        self.airTurbulence.renderer.setFinalXScale(turbulenceScale * 2.0)  # Expand significantly
        self.airTurbulence.renderer.setInitialYScale(turbulenceScale * 0.6)
        self.airTurbulence.renderer.setFinalYScale(turbulenceScale * 2.0)
        self.airTurbulence.renderer.setXScaleFlag(True)
        self.airTurbulence.renderer.setYScaleFlag(True)
        self.airTurbulence.renderer.setIgnoreScale(False)
        
        # Turbulence emitter - around the object
        self.airTurbulence.emitter.setEmissionType(1)  # ETRADIATE
        self.airTurbulence.emitter.setRadius(emitterRadius * 0.9)
        self.airTurbulence.emitter.setAmplitude(amplitude * 0.4)  # Gentle
        self.airTurbulence.emitter.setAmplitudeSpread(1.0)  # Very random
        # Turbulence drifts slowly
        self.airTurbulence.emitter.setOffsetForce(Vec3(0.0, 0.0, turbulenceRiseZ))
        
        # ===== ADD FORCES FOR ALL LAYERS =====
        # Strong spiral force for wind streams (creates circular motion)
        spiralForceGroup = ForceGroup.ForceGroup('windSpiral')
        spiralUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, spiralForceZ * 1.5), 1.0, 0)
        spiralUpwardForce.setActive(True)
        spiralForceGroup.addForce(spiralUpwardForce)
        self.particleEffect.addForceGroup(spiralForceGroup)
        
        # Gentle upward drift for wisps
        wispForceGroup = ForceGroup.ForceGroup('windWispDrift')
        wispUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, spiralForceZ * 0.7), 0.6, 0)
        wispUpwardForce.setActive(True)
        wispForceGroup.addForce(wispUpwardForce)
        self.particleEffect.addForceGroup(wispForceGroup)
        
        # Very gentle drift for turbulence
        turbulenceForceGroup = ForceGroup.ForceGroup('airTurbulenceDrift')
        turbulenceUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, turbulenceRiseZ * 0.5), 0.3, 0)
        turbulenceUpwardForce.setActive(True)
        turbulenceForceGroup.addForce(turbulenceUpwardForce)
        self.particleEffect.addForceGroup(turbulenceForceGroup)
        
        # Store particles reference for cleanup
        self.particles = self.windStreams  # Keep for compatibility with existing code
        
        # Apply green glow color to safe (not CFO) - will fade in when effect starts
        if isSafe and not isCFOBoss:
            try:
                # Store original color scale if not already stored
                if not hasattr(self.obj, '_originalWindedColorScale'):
                    originalColor = self.obj.getColorScale()
                    # Validate the color is reasonable
                    if (0.0 <= originalColor.getX() <= 2.0 and 
                        0.0 <= originalColor.getY() <= 2.0 and 
                        0.0 <= originalColor.getZ() <= 2.0 and 
                        0.0 <= originalColor.getW() <= 2.0):
                        self.obj._originalWindedColorScale = originalColor
                    else:
                        # Color is corrupted, use default white
                        self.obj._originalWindedColorScale = VBase4(1, 1, 1, 1)
                
                # Calculate lighter green tint (less intense)
                # Blend between original and light leaf green: 70% original, 30% green
                # This creates a subtle glow effect
                originalColor = self.obj._originalWindedColorScale
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
        for particleLayer in ['windStreams', 'windWisps', 'airTurbulence', 'particles']:
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
        for particleLayer in ['windStreams', 'windWisps', 'airTurbulence', 'particles']:
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
        for particleLayer in ['windStreams', 'windWisps', 'airTurbulence', 'particles']:
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
            from toontown.coghq import DistributedCashbotBossSafe
            from toontown.suit import BossCog
            
            if isinstance(self.obj, DistributedCashbotBossSafe.DistributedCashbotBossSafe) and not isinstance(self.obj, BossCog.BossCog):
                if hasattr(self.obj, '_windedGlowColor') and hasattr(self.obj, '_originalWindedColorScale'):
                    # Cancel any existing color interval
                    if hasattr(self.obj, '_windedColorInterval'):
                        if self.obj._windedColorInterval:
                            self.obj._windedColorInterval.finish()
                    
                    # Fade in to glow color over 0.4 seconds
                    self.obj._windedColorInterval = LerpColorScaleInterval(
                        self.obj,
                        duration=0.4,
                        colorScale=self.obj._windedGlowColor,
                        blendType='easeInOut'
                    )
                    self.obj._windedColorInterval.start()
                    self.notify.info("Fading in green glow color on safe")
        except Exception as e:
            self.notify.warning(f"Error fading in safe color: {e}")
    
    def _fadeOutSafeColor(self):
        """Fade out the green glow color on the safe back to original."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from toontown.coghq import DistributedCashbotBossSafe
            from toontown.suit import BossCog
            
            if isinstance(self.obj, DistributedCashbotBossSafe.DistributedCashbotBossSafe) and not isinstance(self.obj, BossCog.BossCog):
                if hasattr(self.obj, '_originalWindedColorScale'):
                    # Cancel any existing color interval
                    if hasattr(self.obj, '_windedColorInterval'):
                        if self.obj._windedColorInterval:
                            self.obj._windedColorInterval.finish()
                    
                    # Fade out to original color over 0.4 seconds
                    self.obj._windedColorInterval = LerpColorScaleInterval(
                        self.obj,
                        duration=0.4,
                        colorScale=self.obj._originalWindedColorScale,
                        blendType='easeInOut'
                    )
                    self.obj._windedColorInterval.start()
                    self.notify.info("Fading out green glow color on safe")
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
                if hasattr(self.obj, '_windedColorInterval'):
                    if self.obj._windedColorInterval:
                        self.obj._windedColorInterval.finish()
                    self.obj._windedColorInterval = None
                
                # Restore original color immediately
                if hasattr(self.obj, '_originalWindedColorScale'):
                    self.obj.setColorScale(self.obj._originalWindedColorScale)
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
        
        # Stop all wind particle layers from spawning
        for particleLayer in ['windStreams', 'windWisps', 'airTurbulence', 'particles']:
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
                baseStreamBirthRate = 0.03
                self.windStreams.setBirthRate(baseStreamBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # Brighter, more intense leaf green for more stacks
                    self.windStreams.renderer.setColor(Vec4(0.55, 1.0, 0.45, 0.95))  # Brighter light leaf green
            except:
                pass
        
        # Update wind wisps
        if hasattr(self, 'windWisps') and self.windWisps:
            try:
                baseWispBirthRate = 0.045
                self.windWisps.setBirthRate(baseWispBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More visible leaf wisps for more stacks
                    self.windWisps.renderer.setColor(Vec4(0.65, 1.0, 0.6, 0.75))  # Slightly more opaque leaf green
            except:
                pass
        
        # Update air turbulence
        if hasattr(self, 'airTurbulence') and self.airTurbulence:
            try:
                baseTurbulenceBirthRate = 0.08
                self.airTurbulence.setBirthRate(baseTurbulenceBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # More visible turbulence with light leaf tint for more stacks
                    self.airTurbulence.renderer.setColor(Vec4(0.8, 1.0, 0.75, 0.55))  # Slightly more visible leaf tint
            except:
                pass
        
        # Legacy support for self.particles (which points to windStreams)
        if hasattr(self, 'particles') and self.particles:
            try:
                baseBirthRate = 0.03
                self.particles.setBirthRate(baseBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    self.particles.renderer.setColor(Vec4(0.55, 1.0, 0.45, 0.95))  # Brighter light leaf green
            except:
                pass



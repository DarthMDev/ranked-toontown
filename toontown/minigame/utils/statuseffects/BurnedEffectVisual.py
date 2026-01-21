"""
Visual effect for the BURNED status effect.

Creates animated fire/flame particles around the object.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, VBase4
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import LerpColorScaleInterval
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase


class BurnedEffectVisual(StatusEffectVisualBase):
    """
    Visual for the BURNED status effect.
    
    Creates a particle effect with:
    - Orange/red flame particles rising from the object
    - Scaled appropriately to object size
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
        isSafe = False
        try:
            from ..boss import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying larger, wider fire effect")
            else:
                # Check if this is a safe (not CFO)
                from ...craning.objects import DistributedCashbotSafe
                if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe):
                    isSafe = True
                    self.notify.info("Detected safe - will apply orange/red glow color")
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
        
        # Create a renderParent node for particle physics with proper depth settings
        # This ensures particles don't occlude other objects
        self.particleRenderParent = render.attachNewNode('burnedParticleRenderParent')
        self.particleRenderParent.setBin('fixed', -50)  # Lower priority than damage numbers
        self.particleRenderParent.setDepthWrite(False)  # Don't write to depth (won't occlude things behind)
        # Keep depthTest enabled (default) so particles respect depth for proper rendering
        self.particleRenderParent.setLightOff()
        self.particleRenderParent.setFogOff()
        
        # Create the particle effect (don't parent it yet - start() will handle that)
        self.particleEffect = ParticleEffect.ParticleEffect('BurnedFlames')
        
        # Store the desired position for later - position at object base in local space
        # Since effectNode is attached to obj, we use local coordinates
        # Position slightly above the base (minPt.getZ() in world becomes ~0 in local, so use small offset)
        baseOffset = 0.1  # Small offset above base
        self.particlePos = Point3(0, 0, baseOffset)
        
        # ===== LAYER 1: CORE FLAMES (Hot white/yellow center) =====
        self.coreFlames = Particles.Particles('coreFlames')
        self.coreFlames.setFactory('PointParticleFactory')
        self.coreFlames.setRenderer('SpriteParticleRenderer')
        self.coreFlames.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.coreFlames)
        
        # ===== LAYER 2: MAIN FLAMES (Orange/red body) =====
        self.mainFlames = Particles.Particles('mainFlames')
        self.mainFlames.setFactory('PointParticleFactory')
        self.mainFlames.setRenderer('SpriteParticleRenderer')
        self.mainFlames.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.mainFlames)
        
        # ===== LAYER 3: EMBERS (Floating sparks) =====
        self.embers = Particles.Particles('embers')
        self.embers.setFactory('PointParticleFactory')
        self.embers.setRenderer('SpriteParticleRenderer')
        self.embers.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.embers)
        
        # Calculate emitter settings
        if isCFOBoss:
            emitterRadius = max(2.0, avgWidth / 2.0 * 0.8)
            amplitude = 2.0 * baseScale
            offsetForceZ = 4.0 * baseScale
            upwardForceZ = 7.0 * baseScale
        else:
            emitterRadius = max(0.4, (maxPt.getX() - minPt.getX()) / 2.0) * 0.6
            amplitude = 1.5 * baseScale
            offsetForceZ = 3.0 * baseScale
            upwardForceZ = 5.0 * baseScale
        
        # ===== CONFIGURE CORE FLAMES (Hot center) =====
        if isCFOBoss:
            corePoolSize = int(80 * baseScale)
            coreBirthRate = 0.025
            coreLitterSize = 3
            coreLifespan = 0.6 * baseScale
            coreScale = max(0.25, 0.35 * baseScale)
        else:
            corePoolSize = int(40 * baseScale)
            coreBirthRate = 0.03
            coreLitterSize = 2
            coreLifespan = 0.4 * baseScale
            coreScale = max(0.1, 0.15 * baseScale)
        
        self.coreFlames.setPoolSize(corePoolSize)
        self.coreFlames.setBirthRate(coreBirthRate)
        self.coreFlames.setLitterSize(coreLitterSize)
        self.coreFlames.setLitterSpread(1)
        self.coreFlames.factory.setLifespanBase(coreLifespan)
        self.coreFlames.factory.setLifespanSpread(0.15)
        self.coreFlames.factory.setMassBase(0.8)
        self.coreFlames.factory.setMassSpread(0.15)
        self.coreFlames.factory.setTerminalVelocityBase(450.0)
        self.coreFlames.factory.setTerminalVelocitySpread(60.0)
        
        # Core flames renderer - hot white/yellow
        self.coreFlames.renderer.setAlphaMode(3)  # PRALPHANONE
        self.coreFlames.renderer.setUserAlpha(1.0)
        self.coreFlames.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.coreFlames.renderer.setAlphaDisable(0)
        self.coreFlames.renderer.setAnimAngleFlag(1)
        self.coreFlames.renderer.setNonanimatedTheta(0.0)
        
        # Load fire texture for core
        try:
            self.coreFlames.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/fire")
        except:
            pass
        
        # Hot white/yellow color for core (brightest part of fire)
        self.coreFlames.renderer.setColor(Vec4(1.0, 0.95, 0.7, 1.0))  # Hot white-yellow
        self.coreFlames.renderer.setInitialXScale(coreScale * 0.5)
        self.coreFlames.renderer.setFinalXScale(coreScale * 0.7)
        self.coreFlames.renderer.setInitialYScale(coreScale * 0.7)
        self.coreFlames.renderer.setFinalYScale(coreScale * 1.2)
        self.coreFlames.renderer.setXScaleFlag(True)
        self.coreFlames.renderer.setYScaleFlag(True)
        self.coreFlames.renderer.setIgnoreScale(False)
        
        # Core emitter - smaller radius for center
        self.coreFlames.emitter.setEmissionType(1)  # ETRADIATE
        self.coreFlames.emitter.setRadius(emitterRadius * 0.4)  # Smaller, tighter core
        self.coreFlames.emitter.setAmplitude(amplitude * 0.8)
        self.coreFlames.emitter.setAmplitudeSpread(0.3)
        self.coreFlames.emitter.setOffsetForce(Vec3(0.0, 0.0, offsetForceZ * 1.1))  # Faster rise
        
        # ===== CONFIGURE MAIN FLAMES (Orange/red body) =====
        if isCFOBoss:
            mainPoolSize = int(150 * baseScale)
            mainBirthRate = 0.018
            mainLitterSize = 6
            mainLifespan = 0.75 * baseScale
            mainScale = max(0.35, 0.5 * baseScale)
        else:
            mainPoolSize = int(75 * baseScale)
            mainBirthRate = 0.025
            mainLitterSize = 4
            mainLifespan = 0.55 * baseScale
            mainScale = max(0.12, 0.2 * baseScale)
        
        self.mainFlames.setPoolSize(mainPoolSize)
        self.mainFlames.setBirthRate(mainBirthRate)
        self.mainFlames.setLitterSize(mainLitterSize)
        self.mainFlames.setLitterSpread(2)
        self.mainFlames.factory.setLifespanBase(mainLifespan)
        self.mainFlames.factory.setLifespanSpread(0.25)
        self.mainFlames.factory.setMassBase(1.0)
        self.mainFlames.factory.setMassSpread(0.25)
        self.mainFlames.factory.setTerminalVelocityBase(380.0)
        self.mainFlames.factory.setTerminalVelocitySpread(70.0)
        
        # Main flames renderer - orange/red
        self.mainFlames.renderer.setAlphaMode(3)  # PRALPHANONE
        self.mainFlames.renderer.setUserAlpha(1.0)
        self.mainFlames.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.mainFlames.renderer.setAlphaDisable(0)
        self.mainFlames.renderer.setAnimAngleFlag(1)
        self.mainFlames.renderer.setNonanimatedTheta(0.0)
        
        # Load fire texture
        try:
            self.mainFlames.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/fire")
        except:
            pass
        
        # Orange color for main flames (less red, more orange)
        self.mainFlames.renderer.setColor(Vec4(1.0, 0.65, 0.0, 1.0))  # Pure orange
        self.mainFlames.renderer.setInitialXScale(mainScale * 0.6)
        self.mainFlames.renderer.setFinalXScale(mainScale * 0.9)
        self.mainFlames.renderer.setInitialYScale(mainScale * 0.8)
        self.mainFlames.renderer.setFinalYScale(mainScale * 1.6)
        self.mainFlames.renderer.setXScaleFlag(True)
        self.mainFlames.renderer.setYScaleFlag(True)
        self.mainFlames.renderer.setIgnoreScale(False)
        
        # Main emitter - full radius
        self.mainFlames.emitter.setEmissionType(1)  # ETRADIATE
        self.mainFlames.emitter.setRadius(emitterRadius)
        self.mainFlames.emitter.setAmplitude(amplitude)
        self.mainFlames.emitter.setAmplitudeSpread(0.6)
        self.mainFlames.emitter.setOffsetForce(Vec3(0.0, 0.0, offsetForceZ))
        
        # ===== CONFIGURE EMBERS (Floating sparks) =====
        if isCFOBoss:
            emberPoolSize = int(60 * baseScale)
            emberBirthRate = 0.04
            emberLitterSize = 2
            emberLifespan = 1.2 * baseScale
            emberScale = max(0.08, 0.12 * baseScale)
        else:
            emberPoolSize = int(30 * baseScale)
            emberBirthRate = 0.05
            emberLitterSize = 1
            emberLifespan = 0.9 * baseScale
            emberScale = max(0.05, 0.08 * baseScale)
        
        self.embers.setPoolSize(emberPoolSize)
        self.embers.setBirthRate(emberBirthRate)
        self.embers.setLitterSize(emberLitterSize)
        self.embers.setLitterSpread(1)
        self.embers.factory.setLifespanBase(emberLifespan)
        self.embers.factory.setLifespanSpread(0.4)
        self.embers.factory.setMassBase(0.5)  # Lighter for floating
        self.embers.factory.setMassSpread(0.2)
        self.embers.factory.setTerminalVelocityBase(200.0)  # Slower for floating effect
        self.embers.factory.setTerminalVelocitySpread(80.0)
        
        # Embers renderer - orange/red sparks
        self.embers.renderer.setAlphaMode(3)  # PRALPHANONE
        self.embers.renderer.setUserAlpha(1.0)
        self.embers.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.embers.renderer.setAlphaDisable(0)
        self.embers.renderer.setAnimAngleFlag(1)
        self.embers.renderer.setNonanimatedTheta(0.0)
        
        # Try to load spark texture, fallback to fire
        try:
            self.embers.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/fire")
        except:
            pass
        
        # Orange-red ember color
        self.embers.renderer.setColor(Vec4(1.0, 0.4, 0.0, 0.9))  # Bright orange
        self.embers.renderer.setInitialXScale(emberScale)
        self.embers.renderer.setFinalXScale(emberScale * 0.5)  # Shrink as they fade
        self.embers.renderer.setInitialYScale(emberScale)
        self.embers.renderer.setFinalYScale(emberScale * 0.5)
        self.embers.renderer.setXScaleFlag(True)
        self.embers.renderer.setYScaleFlag(True)
        self.embers.renderer.setIgnoreScale(False)
        
        # Ember emitter - wider spread
        self.embers.emitter.setEmissionType(1)  # ETRADIATE
        self.embers.emitter.setRadius(emitterRadius * 1.2)  # Wider spread
        self.embers.emitter.setAmplitude(amplitude * 0.6)  # Gentler
        self.embers.emitter.setAmplitudeSpread(0.8)
        self.embers.emitter.setOffsetForce(Vec3(0.0, 0.0, offsetForceZ * 0.7))  # Slower rise
        
        # ===== LAYER 4: SMOKE (Dark gray/black wisps) =====
        self.smoke = Particles.Particles('smoke')
        self.smoke.setFactory('PointParticleFactory')
        self.smoke.setRenderer('SpriteParticleRenderer')
        self.smoke.setEmitter('SphereVolumeEmitter')
        self.particleEffect.addParticles(self.smoke)
        
        # Configure smoke particles - slower, longer-lived, darker
        if isCFOBoss:
            smokePoolSize = int(50 * baseScale)
            smokeBirthRate = 0.06
            smokeLitterSize = 2
            smokeLifespan = 2.0 * baseScale  # Longer lifespan for smoke
            smokeScale = max(0.3, 0.4 * baseScale)
        else:
            smokePoolSize = int(30 * baseScale)
            smokeBirthRate = 0.08
            smokeLitterSize = 1
            smokeLifespan = 1.5 * baseScale
            smokeScale = max(0.2, 0.3 * baseScale)
        
        self.smoke.setPoolSize(smokePoolSize)
        self.smoke.setBirthRate(smokeBirthRate)
        self.smoke.setLitterSize(smokeLitterSize)
        self.smoke.setLitterSpread(1)
        self.smoke.factory.setLifespanBase(smokeLifespan)
        self.smoke.factory.setLifespanSpread(0.5)
        self.smoke.factory.setMassBase(0.3)  # Very light for floating
        self.smoke.factory.setMassSpread(0.15)
        self.smoke.factory.setTerminalVelocityBase(150.0)  # Slow floating
        self.smoke.factory.setTerminalVelocitySpread(50.0)
        
        # Smoke renderer - dark gray/black
        self.smoke.renderer.setAlphaMode(3)  # PRALPHANONE
        self.smoke.renderer.setUserAlpha(1.0)
        self.smoke.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        self.smoke.renderer.setAlphaDisable(0)
        self.smoke.renderer.setAnimAngleFlag(1)
        self.smoke.renderer.setNonanimatedTheta(0.0)
        
        # Try to load smoke texture, fallback to white glow or fire
        try:
            # Try to find a smoke texture, or use white glow as base
            try:
                smokeModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
                if not smokeModel.isEmpty():
                    smokeTemplate = smokeModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                    if not smokeTemplate.isEmpty():
                        self.smoke.renderer.setFromNode(smokeTemplate)
            except:
                # Fallback to fire texture
                self.smoke.renderer.setTextureFromNode("phase_3.5/models/props/suit-particles", "**/fire")
        except:
            pass
        
        # Dark gray/black smoke color - starts darker, fades to lighter gray
        self.smoke.renderer.setColor(Vec4(0.2, 0.2, 0.2, 0.8))  # Dark gray smoke
        # Smoke particles grow as they rise and fade
        self.smoke.renderer.setInitialXScale(smokeScale * 0.8)
        self.smoke.renderer.setFinalXScale(smokeScale * 2.0)  # Expand as they rise
        self.smoke.renderer.setInitialYScale(smokeScale * 0.8)
        self.smoke.renderer.setFinalYScale(smokeScale * 2.5)  # Taller as they rise
        self.smoke.renderer.setXScaleFlag(True)
        self.smoke.renderer.setYScaleFlag(True)
        self.smoke.renderer.setIgnoreScale(False)
        
        # Smoke emitter - wider spread, starts above flames
        self.smoke.emitter.setEmissionType(1)  # ETRADIATE
        self.smoke.emitter.setRadius(emitterRadius * 0.8)  # Slightly smaller base
        self.smoke.emitter.setAmplitude(amplitude * 0.4)  # Very gentle
        self.smoke.emitter.setAmplitudeSpread(1.0)  # More random spread
        # Smoke rises slower and more gently
        self.smoke.emitter.setOffsetForce(Vec3(0.0, 0.0, offsetForceZ * 0.5))  # Slower rise
        
        # ===== ADD FORCES FOR ALL LAYERS =====
        # Upward force for flames
        flameForceGroup = ForceGroup.ForceGroup('flameRise')
        upwardForce = LinearVectorForce(Vec3(0.0, 0.0, upwardForceZ), 1.0, 0)
        upwardForce.setActive(True)
        flameForceGroup.addForce(upwardForce)
        self.particleEffect.addForceGroup(flameForceGroup)
        
        # Gentler upward force for embers (floating effect)
        emberForceGroup = ForceGroup.ForceGroup('emberFloat')
        emberUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, upwardForceZ * 0.4), 0.6, 0)
        emberUpwardForce.setActive(True)
        emberForceGroup.addForce(emberUpwardForce)
        self.particleEffect.addForceGroup(emberForceGroup)
        
        # Very gentle upward force for smoke (slow drift)
        smokeForceGroup = ForceGroup.ForceGroup('smokeRise')
        smokeUpwardForce = LinearVectorForce(Vec3(0.0, 0.0, upwardForceZ * 0.3), 0.4, 0)
        smokeUpwardForce.setActive(True)
        smokeForceGroup.addForce(smokeUpwardForce)
        self.particleEffect.addForceGroup(smokeForceGroup)
        
        # Store particles reference for cleanup
        self.particles = self.mainFlames  # Keep for compatibility with existing code
        
        # Apply orange/red glow color to safe (not CFO) - will fade in when effect starts
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
                
                # Calculate lighter orange/red tint (less intense)
                # Blend between original and orange-red: 70% original, 30% orange-red
                # This creates a subtle glow effect
                orangeRedTint = VBase4(1.0, 0.6, 0.2, 1.0)  # Pure orange-red tint
                blendFactor = 0.8  # Only 50% of the tint (lighter effect)
                
                glowColor = VBase4(
                    originalColor.getX() * (1.0 - blendFactor) + orangeRedTint.getX() * blendFactor,
                    originalColor.getY() * (1.0 - blendFactor) + orangeRedTint.getY() * blendFactor,
                    originalColor.getZ() * (1.0 - blendFactor) + orangeRedTint.getZ() * blendFactor,
                    originalColor.getW()  # Alpha - preserve original
                )
                
                # Store the glow color for fade in/out
                self.obj._burnedGlowColor = glowColor
                self.notify.info("Prepared orange/red glow color for safe (will fade in)")
            except Exception as e:
                self.notify.warning(f"Error preparing glow color for safe: {e}")
        
        # Set rendering properties for fire particles
        self.effectNode.setLightOff()
        self.effectNode.setFogOff()
        self.effectNode.setDepthWrite(False)  # Don't write to depth buffer (so particles won't occlude things behind them)
        # Keep depthTest enabled (default) so particles still respect depth for proper rendering
        # Fire particles render at lower priority than damage numbers
        # Fire at -50 (low), damage numbers at 100 (highest)
        # Use negative priority to ensure fire renders before damage numbers
        self.effectNode.setBin('fixed', -50)
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
        for particleLayer in ['coreFlames', 'mainFlames', 'embers', 'smoke', 'particles']:
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
        
        # Check all fire and smoke particle layers
        for particleLayer in ['coreFlames', 'mainFlames', 'embers', 'smoke', 'particles']:
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
        for particleLayer in ['coreFlames', 'mainFlames', 'embers', 'smoke', 'particles']:
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
            return f'burnedEffect-{self.obj.getDoId()}-{name}'
        return f'burnedEffect-{name}'
    
    def _fadeInSafeColor(self):
        """Fade in the orange/red glow color on the safe."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from ...craning.objects import DistributedCashbotSafe
            from ..boss import BossCog

            if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe) and not isinstance(self.obj, BossCog.BossCog):
                if hasattr(self.obj, '_burnedGlowColor'):
                    # Use centralized color management system
                    if hasattr(self.obj, 'registerColorModification'):
                        self.obj.registerColorModification('burned', self.obj._burnedGlowColor, priority='elemental')
                        self.notify.info("Registered burned color modification on safe")
                    else:
                        # Fallback if system not available
                        if hasattr(self.obj, '_burnedColorInterval'):
                            if self.obj._burnedColorInterval:
                                self.obj._burnedColorInterval.finish()
                        self.obj._burnedColorInterval = LerpColorScaleInterval(
                            self.obj,
                            duration=0.4,
                            colorScale=self.obj._burnedGlowColor,
                            blendType='easeInOut'
                        )
                        self.obj._burnedColorInterval.start()
                        self.notify.info("Fading in orange/red glow color on safe (fallback)")
        except Exception as e:
            self.notify.warning(f"Error fading in safe color: {e}")
    
    def _fadeOutSafeColor(self):
        """Fade out the orange/red glow color on the safe back to original."""
        if not hasattr(self, 'obj') or not self.obj:
            return
        
        try:
            # Check if this is a safe (not CFO)
            from ...craning.objects import DistributedCashbotSafe
            from ..boss import BossCog

            if isinstance(self.obj, DistributedCashbotSafe.DistributedCashbotSafe) and not isinstance(self.obj, BossCog.BossCog):
                # Use centralized color management system
                if hasattr(self.obj, 'unregisterColorModification'):
                    self.obj.unregisterColorModification('burned', priority='elemental')
                    self.notify.info("Unregistered burned color modification on safe")
                else:
                    # Fallback if system not available
                    if hasattr(self.obj, '_originalBurnedColorScale'):
                        if hasattr(self.obj, '_burnedColorInterval'):
                            if self.obj._burnedColorInterval:
                                self.obj._burnedColorInterval.finish()
                        self.obj._burnedColorInterval = LerpColorScaleInterval(
                            self.obj,
                            duration=0.4,
                            colorScale=self.obj._originalBurnedColorScale,
                            blendType='easeInOut'
                        )
                        self.obj._burnedColorInterval.start()
                        self.notify.info("Fading out orange/red glow color on safe (fallback)")
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
                    self.obj.unregisterColorModification('burned', priority='elemental')
                    self.notify.info("Unregistered burned color modification on safe (immediate)")
                else:
                    # Fallback if system not available
                    if hasattr(self.obj, '_burnedColorInterval'):
                        if self.obj._burnedColorInterval:
                            self.obj._burnedColorInterval.finish()
                        self.obj._burnedColorInterval = None
                    if hasattr(self.obj, '_originalBurnedColorScale'):
                        self.obj.setColorScale(self.obj._originalBurnedColorScale)
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
        
        # Stop all fire and smoke particle layers from spawning
        for particleLayer in ['coreFlames', 'mainFlames', 'embers', 'smoke', 'particles']:
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
        """Update flame intensity based on stack count."""
        super().updateStack(stackCount)
        
        if not self.active:
            return
        
        # Update all fire layers based on stack count
        # More stacks = more intense flames (faster birth rate, hotter colors)
        intensityMultiplier = 1.0 / max(1, stackCount)
        
        # Update core flames
        if hasattr(self, 'coreFlames') and self.coreFlames:
            try:
                baseCoreBirthRate = 0.03
                self.coreFlames.setBirthRate(baseCoreBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # Hotter core for more stacks
                    self.coreFlames.renderer.setColor(Vec4(1.0, 1.0, 0.8, 1.0))  # Brighter white-yellow
            except:
                pass
        
        # Update main flames
        if hasattr(self, 'mainFlames') and self.mainFlames:
            try:
                baseMainBirthRate = 0.025
                self.mainFlames.setBirthRate(baseMainBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    # Hotter/more intense orange for more stacks
                    orangeIntensity = min(1.0, 0.65 + (stackCount * 0.05))
                    self.mainFlames.renderer.setColor(Vec4(1.0, orangeIntensity, 0.0, 1.0))  # Pure orange, brighter with stacks
            except:
                pass
        
        # Update embers
        if hasattr(self, 'embers') and self.embers:
            try:
                baseEmberBirthRate = 0.05
                self.embers.setBirthRate(baseEmberBirthRate * intensityMultiplier)
            except:
                pass
        
        # Update smoke (more stacks = more smoke)
        if hasattr(self, 'smoke') and self.smoke:
            try:
                baseSmokeBirthRate = 0.08
                self.smoke.setBirthRate(baseSmokeBirthRate * intensityMultiplier)
            except:
                pass
        
        # Legacy support for self.particles (which points to mainFlames)
        if hasattr(self, 'particles') and self.particles:
            try:
                baseBirthRate = 0.025
                self.particles.setBirthRate(baseBirthRate * intensityMultiplier)
                if stackCount >= 2:
                    orangeIntensity = min(1.0, 0.65 + (stackCount * 0.05))
                    self.particles.renderer.setColor(Vec4(1.0, orangeIntensity, 0.0, 1.0))  # Pure orange
            except:
                pass


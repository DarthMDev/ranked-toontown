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
        
        # Create glow aura particle effect for ambient glow around the object
        self.glowParticleEffect = ParticleEffect.ParticleEffect('BurnedGlowAura')
        
        # Position glow a little bit above base
        glowCenterOffset = height * 0.5
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
        # Use local velocity so particles move relative to parent (object)
        self.glowParticles.setLocalVelocityFlag(1)
        
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
            glowColor = Vec4(1.0, 0.6, 0.2, 0.02)  # Lower alpha for CFO (0.4 vs 0.7)
        else:
            glowColor = Vec4(1.0, 0.6, 0.2, 0.02)  # Normal intensity for safes
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
        self.glowParticles.renderer.setInitialXScale(glowBaseScale * 2.0)
        self.glowParticles.renderer.setFinalXScale(glowBaseScale * 2.0)
        self.glowParticles.renderer.setInitialYScale(glowBaseScale * 4.0)
        self.glowParticles.renderer.setFinalYScale(glowBaseScale * 4.0)
        self.glowParticles.renderer.setXScaleFlag(True)  # Enable scaling
        self.glowParticles.renderer.setYScaleFlag(True)
        self.glowParticles.renderer.setIgnoreScale(False)
        
        # Configure glow emitter - sphere around object center
        # Glow should stick to object, so minimal movement
        self.glowParticles.emitter.setEmissionType(1)  # ETRADIATE - radiate outward
        # Emit from a sphere around the object center
        if isCFOBoss:
            # Larger radius for CFO to surround the whole body
            glowEmitterRadius = max(3.0, avgWidth / 2.0 * 0.6)
        else:
            # Smaller radius for safes
            glowEmitterRadius = max(1.0, avgWidth / 2.0 * 0.5)
        
        self.glowParticles.emitter.setRadius(glowEmitterRadius)
        # Minimal amplitude so particles stay close to object
        self.glowParticles.emitter.setAmplitude(0.1)  # Very small movement
        self.glowParticles.emitter.setAmplitudeSpread(0.05)  # Tight spread
        # No offset force - particles should stay in place
        self.glowParticles.emitter.setOffsetForce(Vec3(0.0, 0.0, 0.0))
        
        # Reduce terminal velocity so particles don't drift
        self.glowParticles.factory.setTerminalVelocityBase(10.0)  # Very slow
        self.glowParticles.factory.setTerminalVelocitySpread(5.0)
        
        # No upward force - glow should stick to object
        # (Removed glowForceGroup to prevent drifting)
        
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
            # Use render as renderParent (world space) but parent to effectNode
            # This way the glow rotates with the object but particles use world space physics
            self.glowParticleEffect.start(parent=self.effectNode, renderParent=render)
            
            # Set the glow position at object center (in local space relative to effectNode)
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
        # Disable all fire and smoke layers
        for particleLayer in ['coreFlames', 'mainFlames', 'embers', 'smoke', 'particles']:
            if hasattr(self, particleLayer):
                particles = getattr(self, particleLayer)
                if particles:
                    try:
                        particles.disableParticles()
                    except Exception as e:
                        self.notify.warning(f"Error disabling {particleLayer}: {e}")
        
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
        
        # Clean up all particle layer references
        for particleLayer in ['coreFlames', 'mainFlames', 'embers', 'smoke', 'particles']:
            if hasattr(self, particleLayer):
                setattr(self, particleLayer, None)
        
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
        
        # Disable all fire and smoke particle layers
        for particleLayer in ['coreFlames', 'mainFlames', 'embers', 'smoke', 'particles']:
            if hasattr(self, particleLayer):
                particles = getattr(self, particleLayer)
                if particles:
                    try:
                        particles.disableParticles()
                        setattr(self, particleLayer, None)
                    except Exception as e:
                        self.notify.warning(f"Error disabling {particleLayer}: {e}")
        
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


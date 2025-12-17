"""
Visual effect for the BURNED status effect.

Creates animated fire/flame particles around the object.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib
from panda3d.physics import LinearVectorForce
from direct.interval.IntervalGlobal import Sequence, LerpColorScaleInterval, Wait, Func
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
    
    def stop(self):
        """Stop the particle effect without destroying it."""
        if self.particleEffect:
            try:
                # Soft stop allows the particles to fade out naturally
                self.particleEffect.softStop()
            except Exception as e:
                self.notify.warning(f"Error stopping particle effect: {e}")
    
    def cleanup(self):
        """Completely clean up the effect."""
        self.stop()
        
        if hasattr(self, 'particleEffect') and self.particleEffect:
            try:
                # Cleanup the particle effect completely
                self.particleEffect.cleanup()
                self.particleEffect.removeNode()
            except Exception as e:
                self.notify.warning(f"Error during particle effect cleanup: {e}")
            self.particleEffect = None
            
        if hasattr(self, 'particles'):
            self.particles = None
            
        if self.effectNode and not self.effectNode.isEmpty():
            self.effectNode.removeNode()
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


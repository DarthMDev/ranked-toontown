"""
Heal Drone - Hovers above owner and heals them over time with visual particles.
"""

from panda3d.core import *
from direct.particles import ParticleEffect, Particles, ForceGroup
from direct.interval.IntervalGlobal import Sequence, Wait, Func, Parallel
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from panda3d.physics import LinearVectorForce
from toontown.minigame.craning import CraneGameGlobals
from toontown.coghq.DistributedGoonDroneBase import DistributedGoonDroneBase
import random


class DistributedGoonDroneHeal(DistributedGoonDroneBase):
    """
    Heal drone that:
    1. Spawns above owner
    2. Hovers and creates healing particles around owner
    3. Heals owner over time (+10 laff twice per second)
    4. Vanishes after healing completes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneHeal')
    
    def __init__(self, cr):
        DistributedGoonDroneBase.__init__(self, cr)
        self.healingParticles = None
        self.healingSound = None
        self.nurseSharkSound = None
        self.healingTask = None
    
    def getDroneType(self):
        return CraneGameGlobals.DroneType.HEAL
    
    def needsOpponents(self):
        """Heal drones don't need opponents to function."""
        return False
    
    def startBehavior(self):
        """Start the heal drone hovering behavior."""
        self.startHovering()
    
    def startHovering(self):
        """Start hovering behavior - hovers above owner."""
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return
        
        ownerPos = owner.getPos(render)
        hoverPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        self.setPos(hoverPos)
        # Healing particles will start when AI sends performVisualEffect (after 1 second)
    
    def performHealVisualEffect(self):
        """Handle heal visual effect request from AI - start healing particles."""
        owner = base.cr.doId2do.get(self.ownerId)
        if owner:
            self.startHealingParticles(None)
    
    def startHealingParticles(self, task):
        """Start the healing particle effect around the owner."""
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner or self.isEmpty():
            return Task.done
        
        # Create healing particle effect
        self.createHealingParticles(owner)
        
        # Play healing sound
        self.playHealingSound()
        
        return Task.done
    
    def createHealingParticles(self, owner):
        """Create green + sign particles rising from bottom to top around the owner."""
        if self.healingParticles:
            return
        
        # Create effect node attached to owner (will follow owner automatically)
        self.healingEffectNode = owner.attachNewNode('healingEffect')
        self.healingOwner = owner  # Store reference for cleanup
        
        # Get owner dimensions for scaling
        try:
            ownerBounds = owner.getBounds()
            if ownerBounds.isEmpty():
                # Fallback dimensions for toon
                height = 5.0
                width = 1.0
            else:
                minPt, maxPt = ownerBounds
                height = maxPt.getZ() - minPt.getZ()
                width = max(maxPt.getX() - minPt.getX(), maxPt.getY() - minPt.getY())
        except:
            # Fallback dimensions
            height = 5.0
            width = 1.0
        
        # Create particle effect
        self.healingParticles = ParticleEffect.ParticleEffect('HealingParticles')
        
        # Create healing particles (green + signs)
        healingParticles = Particles.Particles('healingParticles')
        healingParticles.setFactory('PointParticleFactory')
        healingParticles.setRenderer('SpriteParticleRenderer')
        healingParticles.setEmitter('SphereVolumeEmitter')
        self.healingParticles.addParticles(healingParticles)
        
        # Configure particles
        poolSize = 30
        birthRate = 0.15  # Spawn particles frequently
        litterSize = 2
        lifespan = 1.5
        
        healingParticles.setPoolSize(poolSize)
        healingParticles.setBirthRate(birthRate)
        healingParticles.setLitterSize(litterSize)
        healingParticles.setLitterSpread(1)
        healingParticles.factory.setLifespanBase(lifespan)
        healingParticles.factory.setLifespanSpread(0.3)
        healingParticles.factory.setMassBase(0.5)
        healingParticles.factory.setMassSpread(0.2)
        healingParticles.factory.setTerminalVelocityBase(200.0)
        healingParticles.factory.setTerminalVelocitySpread(50.0)
        
        # Renderer - green + signs
        healingParticles.renderer.setAlphaMode(3)  # PRALPHANONE
        healingParticles.renderer.setUserAlpha(1.0)
        healingParticles.renderer.setAlphaBlendMethod(0)  # PPBLENDLINEAR
        healingParticles.renderer.setAlphaDisable(0)
        healingParticles.renderer.setAnimAngleFlag(1)
        
        # Try to load a + sign texture, fallback to white glow
        try:
            # Try to find a plus sign or use white glow as base
            try:
                particleModel = loader.loadModel('phase_4/models/props/tt_m_efx_ext_particleCards')
                if not particleModel.isEmpty():
                    plusTemplate = particleModel.find('**/tt_t_efx_ext_particleWhiteGlow')
                    if not plusTemplate.isEmpty():
                        healingParticles.renderer.setFromNode(plusTemplate)
            except:
                # Fallback: try to use a simple texture
                pass
        except:
            pass
        
        # Bright green color for healing
        healingParticles.renderer.setColor(Vec4(0.2, 1.0, 0.3, 1.0))  # Bright green
        scale = 0.15
        healingParticles.renderer.setInitialXScale(scale)
        healingParticles.renderer.setFinalXScale(scale * 0.5)  # Shrink as they fade
        healingParticles.renderer.setInitialYScale(scale)
        healingParticles.renderer.setFinalYScale(scale * 0.5)
        healingParticles.renderer.setXScaleFlag(True)
        healingParticles.renderer.setYScaleFlag(True)
        healingParticles.renderer.setIgnoreScale(False)
        
        # Emitter - around the base of the toon, rising upward
        emitterRadius = max(0.5, width / 2.0)
        healingParticles.emitter.setEmissionType(1)  # ETRADIATE
        healingParticles.emitter.setRadius(emitterRadius)
        healingParticles.emitter.setAmplitude(1.0)
        healingParticles.emitter.setAmplitudeSpread(0.5)
        # Particles rise from bottom to top
        healingParticles.emitter.setOffsetForce(Vec3(0.0, 0.0, 3.0))
        
        # Add upward force
        forceGroup = ForceGroup.ForceGroup('healingRise')
        upwardForce = LinearVectorForce(Vec3(0.0, 0.0, 4.0), 1.0, 0)
        upwardForce.setActive(True)
        forceGroup.addForce(upwardForce)
        self.healingParticles.addForceGroup(forceGroup)
        
        # Position at base of toon (slightly above ground)
        self.healingParticles.start(parent=self.healingEffectNode, renderParent=render)
        self.healingParticles.setPos(0, 0, 0.1)  # Slightly above ground
        
        # Set rendering properties
        self.healingEffectNode.setLightOff()
        self.healingEffectNode.setFogOff()
        self.healingEffectNode.setDepthWrite(False)
        self.healingEffectNode.setBin('fixed', -50)
        self.healingEffectNode.setTransparency(1)
    
    def playHealingSound(self):
        """Play pixie dust healing sound effect and Nurse Shark sound effect."""
        try:
            # Load pixie dust sound effect
            self.healingSound = base.loader.loadSfx('phase_5/audio/sfx/AA_heal_pixiedust.ogg')
            if self.healingSound:
                # Play sound in a loop while healing
                self.healingSound.setLoop(True)
                self.healingSound.play()
        except:
            # Fallback: try other pixie/healing sounds
            try:
                self.healingSound = base.loader.loadSfx('phase_5/audio/sfx/AA_heal_happydance.ogg')
                if self.healingSound:
                    self.healingSound.setLoop(True)
                    self.healingSound.play()
            except:
                pass
        
        # Play Nurse Shark sound effect
        try:
            self.nurseSharkSound = base.loader.loadSfx('phase_4/audio/sfx/Nurse_Shark.ogg')
            if self.nurseSharkSound:
                # Play Nurse Shark sound (not looped, just once)
                self.nurseSharkSound.play()
        except:
            pass
    
    def stopHealingParticles(self):
        """Stop the healing particle effect."""
        if self.healingSound:
            self.healingSound.stop()
            self.healingSound = None
        
        if self.nurseSharkSound:
            self.nurseSharkSound.stop()
            self.nurseSharkSound = None
        
        if self.healingParticles:
            try:
                self.healingParticles.softStop()
                taskMgr.doMethodLater(2.0, self.cleanupHealingParticles, self.uniqueName('cleanupHealingParticles'))
            except:
                pass
        
        if hasattr(self, 'healingEffectNode') and self.healingEffectNode:
            try:
                self.healingEffectNode.removeNode()
            except:
                pass
            self.healingEffectNode = None
    
    def cleanupHealingParticles(self, task):
        """Clean up healing particles after they fade."""
        if self.healingParticles:
            try:
                self.healingParticles.cleanup()
                if not self.healingParticles.isEmpty():
                    self.healingParticles.detachNode()
                    self.healingParticles.removeNode()
            except:
                pass
            self.healingParticles = None
        return Task.done
    
    def vanishWithPoof(self, task=None):
        """Vanish the drone with a poof effect, stopping healing particles first."""
        # Stop healing particles before vanishing
        self.stopHealingParticles()
        return DistributedGoonDroneBase.vanishWithPoof(self, task)
    
    def disable(self):
        """Clean up when disabled."""
        self.stopHealingParticles()
        taskMgr.remove(self.uniqueName('startHealingParticles'))
        taskMgr.remove(self.uniqueName('cleanupHealingParticles'))
        DistributedGoonDroneBase.disable(self)


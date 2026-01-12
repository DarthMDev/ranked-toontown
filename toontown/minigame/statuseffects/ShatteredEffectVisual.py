"""
Visual effect for the SHATTERED synergy status effect (Frozen + Grounded).

Creates a shattering glass effect similar to the SHIELD drone's shield shatter,
with icy blue color (always, since SHATTERED comes from FROZEN + GROUNDED).
Positioned at the CFO's head when applied to the CFO boss.
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, VBase4, NodePath
from direct.interval.IntervalGlobal import Sequence, LerpColorScaleInterval, LerpScaleInterval, Wait, Func, Parallel
from direct.interval.ParticleInterval import ParticleInterval
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase
from toontown.battle import BattleParticles
import math


class ShatteredEffectVisual(StatusEffectVisualBase):
    """
    Visual for the SHATTERED synergy status effect.
    
    Creates a one-shot shattering glass effect:
    - Uses soundBreak particle effect (Opera singer glass crack)
    - Icy blue color (always, since SHATTERED comes from FROZEN + GROUNDED)
    - Positioned at CFO's head when applied to CFO boss
    - Similar to SHIELD drone's shield shatter effect
    """
    
    def create(self):
        """Create the shatter effect setup."""
        if self.active:
            return
            
        # Create root node for effect
        self._createEffectNode('shatteredEffect')
        
        # Get object dimensions for scaling
        minPt, maxPt, center, height = self.objDimensions
        
        # Calculate width (X and Y dimensions) for objects that are wide
        widthX = maxPt.getX() - minPt.getX()
        widthY = maxPt.getY() - minPt.getY()
        avgWidth = (widthX + widthY) / 2.0
        
        # Debug logging
        self.notify.info(f"Creating shattered effect for {self.obj.getName()}: height={height}, width={avgWidth}")
        
        # Check if this is the CFO boss
        isCFOBoss = False
        try:
            from toontown.suit import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying large-scale shatter effect")
        except:
            pass
        
        # Calculate scale factor based on object size
        if isCFOBoss:
            heightScale = height / 26.0
            widthScale = avgWidth / 20.0
            baseScale = max(2.0, min(max(heightScale, widthScale) * 2.0, 4.0))
        else:
            baseScale = max(0.8, min(height / 3.0, 2.5))
        
        self.notify.info(f"Shattered effect baseScale: {baseScale} (isCFO={isCFOBoss})")
        
        # Store scale for later use
        self.baseScale = baseScale
        self.isCFOBoss = isCFOBoss
        
        # Set rendering properties
        self.effectNode.setLightOff()
        self.effectNode.setFogOff()
        self.effectNode.setDepthWrite(False)
        self.effectNode.setBin('fixed', 50)
        self.effectNode.setTransparency(1)
        self.effectNode.setAttrib(ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd,
            ColorBlendAttrib.OIncomingAlpha,
            ColorBlendAttrib.OOne
        ))
        
        self.active = True
        
    def start(self):
        """Start the shatter effect immediately (one-shot effect)."""
        if not self.active:
            self.create()
        
        # Load particles for later use
        BattleParticles.loadParticles()
        
        # Play shatter effect immediately
        self._playShatterEffect()
    
    def _playShatterEffect(self):
        """Play the shattering glass effect."""
        try:
            # SHATTERED always comes from FROZEN + GROUNDED, so always use icy blue color
            shatterColor = Vec4(0.7, 0.9, 1.0, 1.0)  # Icy blue (same as FROZEN color)
            self.notify.info("Shattering from frozen - using icy blue color")
            
            # Get shatter position - at CFO's head if CFO, otherwise center
            if self.isCFOBoss:
                try:
                    # Try to get head position using headTarget (preferred)
                    if hasattr(self.obj, 'headTarget') and self.obj.headTarget:
                        shatterPos = self.obj.headTarget.getPos(render)
                        self.notify.info(f"Shatter position: headTarget at {shatterPos}")
                    elif hasattr(self.obj, 'neck') and self.obj.neck:
                        # Use neck position with offset for head
                        neckPos = self.obj.neck.getPos(render)
                        # Check if stunned (head is lower when stunned)
                        isStunned = False
                        if hasattr(self.obj, 'attackCode'):
                            from toontown.toonbase import ToontownGlobals
                            isStunned = (self.obj.attackCode == ToontownGlobals.BossCogDizzy or 
                                        self.obj.attackCode == ToontownGlobals.BossCogDizzyNow)
                        if isStunned:
                            shatterPos = Point3(neckPos.getX(), neckPos.getY(), neckPos.getZ() + 2)  # Lower when stunned
                        else:
                            shatterPos = Point3(neckPos.getX(), neckPos.getY(), neckPos.getZ() + 8)  # Higher when not stunned
                        self.notify.info(f"Shatter position: neck offset at {shatterPos}")
                    else:
                        # Fallback: use boss position with head offset
                        bossPos = self.obj.getPos(render)
                        isStunned = False
                        if hasattr(self.obj, 'attackCode'):
                            from toontown.toonbase import ToontownGlobals
                            isStunned = (self.obj.attackCode == ToontownGlobals.BossCogDizzy or 
                                        self.obj.attackCode == ToontownGlobals.BossCogDizzyNow)
                        if isStunned:
                            shatterPos = Point3(bossPos.getX(), bossPos.getY(), bossPos.getZ() + 5)  # Lower when stunned
                        else:
                            shatterPos = Point3(bossPos.getX(), bossPos.getY(), bossPos.getZ() + 15)  # Higher when not stunned
                        self.notify.info(f"Shatter position: boss offset at {shatterPos}")
                except Exception as e:
                    self.notify.warning(f"Error getting CFO head position: {e}")
                    # Fallback to center
                    shatterPos = render.getRelativePoint(self.effectNode, Point3(0, 0, 0))
            else:
                # For non-CFO objects, use center
                try:
                    shatterPos = render.getRelativePoint(self.effectNode, Point3(0, 0, 0))
                except Exception as e:
                    self.notify.warning(f"Error getting shatter position: {e}")
                    shatterPos = self.effectNode.getPos(render)
            
            # Create Opera singer glass crack effect
            breakEffect = BattleParticles.createParticleEffect(file='soundBreak')
            breakEffect.setDepthWrite(1)  # Enable for 3D visibility
            breakEffect.setDepthTest(1)   # Enable for 3D visibility
            breakEffect.setTwoSided(1)
            # Don't use 'fixed' bin - let it render in 3D space
            breakEffect.setBin('default', 0)
            
            # Set color to match shatter type (icy blue if frozen, white otherwise)
            try:
                # Get the particles and set their color
                particles = breakEffect.getParticlesNamed('particles-1')
                if particles:
                    particles.renderer.setColor(shatterColor)
                    self.notify.info(f"Set shatter particle color to {shatterColor}")
            except Exception as e:
                self.notify.warning(f"Could not set shatter particle color: {e}")
            
            # Position crack effect at boss head (or center for non-CFO)
            breakEffect.setPos(render, shatterPos)
            
            # Scale effect based on boss size
            if self.isCFOBoss:
                breakEffect.setScale(self.baseScale * 1.5)  # Larger for CFO
            else:
                breakEffect.setScale(self.baseScale)
            
            # Play Opera singer glass crack sound
            try:
                glassCrackSound = base.loader.loadSfx('phase_5/audio/sfx/AA_sound_Opera_Singer_Cog_Glass.ogg')
                if glassCrackSound:
                    glassCrackSound.play()
                    self.notify.info("Played glass crack sound")
            except Exception as e:
                self.notify.warning(f"Error playing glass crack sound: {e}")
            
            # Helper function to create particle track
            def getPartTrack(particleEffect, startDelay, durationDelay, partExtraArgs, softStop=0):
                pEffect = partExtraArgs[0]
                parent = partExtraArgs[1]
                if len(partExtraArgs) == 3:
                    worldRelative = partExtraArgs[2]
                else:
                    worldRelative = 1
                return Sequence(
                    Wait(startDelay),
                    ParticleInterval(pEffect, parent, worldRelative, duration=durationDelay, cleanup=True, softStopT=softStop)
                )
            
            # Play the shatter effect
            shatterTrack = getPartTrack(breakEffect, 0.0, 1.5, [breakEffect, render, 0], softStop=-0.5)
            shatterTrack.start()
            
            self.notify.info("Shatter effect started")
            
        except Exception as e:
            self.notify.error(f"CRITICAL ERROR in _playShatterEffect: {e}")
            import traceback
            self.notify.error(traceback.format_exc())
    
    def stop(self):
        """Stop the effect."""
        # Shatter is a one-shot effect, nothing to stop
        pass
    
    def gracefulCleanup(self):
        """Gracefully clean up the effect."""
        # Shatter is a one-shot effect that cleans itself up
        self.active = False
        
        # Schedule cleanup after effect has finished
        taskMgr.doMethodLater(2.0, self._delayedCleanup, self.uniqueName('gracefulCleanup'))
    
    def _delayedCleanup(self, task):
        """Actually remove the nodes after shatter has finished."""
        if self.effectNode and not self.effectNode.isEmpty():
            try:
                self.effectNode.detachNode()
                self.effectNode.removeNode()
            except:
                pass
            self.effectNode = None
        
        return task.done
    
    def uniqueName(self, name):
        """Generate a unique task name for this effect."""
        if hasattr(self, 'obj') and self.obj:
            try:
                return f'shatteredEffect-{self.obj.getDoId()}-{name}'
            except:
                pass
        return f'shatteredEffect-{name}'
    
    def cleanup(self, force=False):
        """Completely clean up the effect immediately."""
        # Cancel all pending tasks
        taskMgr.remove(self.uniqueName('gracefulCleanup'))
        
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
        """Update shatter intensity based on stack count."""
        super().updateStack(stackCount)
        
        # Shatter is a one-shot effect, stacking doesn't really apply
        # But we could make it more intense if stacked
        pass


"""
Visual effect for the EXPLOSION synergy effect (Burned + Winded).

Creates an animated explosion effect with:
- Particles burst outward from center (0.0-0.2s)
- Particles orbit and spiral inward around target (0.2-1.5s)
- At 0.75s: Burn damage consumed - particles speed up orbit
- At 1.5s: Massive explosion - flames burst out + explosion particles + white screen flash
- Scaled appropriately to object size (especially for CFO)
"""
from direct.particles import ParticleEffect, Particles, ForceGroup
from panda3d.core import Vec3, Vec4, Point3, ColorBlendAttrib, VBase4, NodePath
from panda3d.physics import LinearVectorForce, LinearFrictionForce, LinearSinkForce, LinearDistanceForce
from direct.interval.IntervalGlobal import Sequence, LerpColorScaleInterval, LerpScaleInterval, Wait, Func, Parallel, LerpPosInterval, LerpFunc
from direct.interval.ParticleInterval import ParticleInterval
from direct.task.TaskManagerGlobal import taskMgr
from .StatusEffectVisualBase import StatusEffectVisualBase
from toontown.battle import BattleParticles
from toontown.suit import GoonDeath
import random


class ExplosionEffectVisual(StatusEffectVisualBase):
    """
    Visual for the EXPLOSION synergy effect.
    
    Creates a multi-stage explosion effect:
    1. Burst phase (0.0-0.2s): Particles explode outward from center
    2. Orbit phase (0.2-0.75s): Particles orbit and slowly spiral inward
    3. Acceleration (0.75s): Orbit speeds up, spiral tightens
    4. Final explosion (1.5s): Flames burst outward + explosion particles + white screen flash
    """
    
    def create(self):
        """Create the explosion particle effect."""
        if self.active:
            return
            
        # Create root node for effect
        self._createEffectNode('explosionEffect')
        
        # Get object dimensions for scaling
        minPt, maxPt, center, height = self.objDimensions
        
        # Calculate width (X and Y dimensions) for objects that are wide
        widthX = maxPt.getX() - minPt.getX()
        widthY = maxPt.getY() - minPt.getY()
        avgWidth = (widthX + widthY) / 2.0
        
        # Debug logging
        self.notify.info(f"Creating explosion effect for {self.obj.getName()}: height={height}, width={avgWidth}")
        
        # Check if this is the CFO boss
        isCFOBoss = False
        try:
            from toontown.suit import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                isCFOBoss = True
                self.notify.info("Detected CFO boss - applying large-scale explosion effect")
        except:
            pass
        
        # Calculate scale factor based on object size
        if isCFOBoss:
            heightScale = height / 26.0
            widthScale = avgWidth / 20.0
            baseScale = max(2.0, min(max(heightScale, widthScale) * 2.0, 4.0))
        else:
            baseScale = max(0.8, min(height / 3.0, 2.5))
        
        self.notify.info(f"Explosion effect baseScale: {baseScale} (isCFO={isCFOBoss})")
        
        # Store scale for later use
        self.baseScale = baseScale
        self.isCFOBoss = isCFOBoss
        
        # Calculate orbit radius for flame burst positioning (used in final explosion)
        if isCFOBoss:
            self.orbitRadius = max(6.0, avgWidth * 0.8)  # Orbit radius around CFO
        else:
            self.orbitRadius = max(2.5, avgWidth * 0.7)  # Orbit radius around safe
        
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
        """Start the explosion effect sequence."""
        if not self.active:
            self.create()
        
        # Load particles for later use
        BattleParticles.loadParticles()
        
        # At 1.5s: Base explosion damage - massive explosion with all effects
        taskMgr.doMethodLater(1.5, self._finalExplosion, self.uniqueName('finalExplosion'))
    
    
    def _finalExplosion(self, task):
        """Massive explosion with flame burst, explosion particles, and white screen flash at 1.5s."""
        self.notify.info("=== _finalExplosion CALLED ===")
        
        # Don't check self.active - explosion should happen even if effect was "removed"
        # The status effect system might remove it at 1.5s, but we still need the explosion!
        
        try:
            
            # Get explosion position (center of target)
            try:
                explosionPos = render.getRelativePoint(self.effectNode, Point3(0, 0, 0))
                self.notify.info(f"Explosion position: {explosionPos}")
            except Exception as e:
                self.notify.warning(f"Error getting explosion position: {e}")
                explosionPos = self.effectNode.getPos(render)
            
            # Create flame burst outward
            try:
                self._createFlameBurst(explosionPos)
                self.notify.info("Created flame burst")
            except Exception as e:
                self.notify.warning(f"Error creating flame burst: {e}")
                import traceback
                self.notify.warning(traceback.format_exc())
            
            # Create explosion particle effects (gear explosion + wide gear explosion)
            try:
                self._createExplosionParticles(explosionPos)
                self.notify.info("Created explosion particles")
            except Exception as e:
                self.notify.warning(f"Error creating explosion particles: {e}")
                import traceback
                self.notify.warning(traceback.format_exc())
            
            # Create WHITE SCREEN FLASH overlay
            try:
                self._createScreenFlash()
                self.notify.info("Created screen flash")
            except Exception as e:
                self.notify.warning(f"ERROR creating screen flash: {e}")
                import traceback
                self.notify.warning(traceback.format_exc())
            
            # Create camera shake effect
            try:
                self._createCameraShake()
                self.notify.info("Created camera shake")
            except Exception as e:
                self.notify.warning(f"Error creating camera shake: {e}")
                import traceback
                self.notify.warning(traceback.format_exc())
            
            # Play massive explosion sound
            try:
                sfx = base.loader.loadSfx('phase_3.5/audio/sfx/ENC_cogfall_apart.ogg')
                if sfx:
                    base.playSfx(sfx, volume=1.0)
                    self.notify.info("Played explosion sound")
                else:
                    self.notify.warning("Explosion sound file not loaded")
            except Exception as e:
                self.notify.warning(f"Error playing explosion sound: {e}")
                import traceback
                self.notify.warning(traceback.format_exc())
            
            self.notify.info("=== _finalExplosion COMPLETED ===")
            
        except Exception as e:
            self.notify.error(f"CRITICAL ERROR in _finalExplosion: {e}")
            import traceback
            self.notify.error(traceback.format_exc())
        
        return task.done
    
    def _createFlameBurst(self, explosionPos):
        """Create flames bursting outward from center."""
        # Create multiple fire particle bursts radiating outward
        numBursts = 12 if self.isCFOBoss else 8
        burstScale = self.baseScale * 2.5 if self.isCFOBoss else self.baseScale * 1.5
        
        for i in range(numBursts):
            angle = (360.0 / numBursts) * i
            import math
            radians = math.radians(angle)
            
            # Calculate outward direction
            outwardDist = self.orbitRadius * 1.5
            offsetX = math.cos(radians) * outwardDist
            offsetY = math.sin(radians) * outwardDist
            
            # Create small fire burst
            fireModel = loader.loadModel('phase_3.5/models/props/explosion')
            fireNode = fireModel.copyTo(render)
            fireNode.setPos(explosionPos + Vec3(offsetX, offsetY, 0))
            fireNode.setScale(burstScale * 0.8)
            fireNode.setBillboardPointEye()
            fireNode.setTransparency(1)
            fireNode.setColorScale(1.0, 0.5, 0.0, 1.0)  # Orange flame
            
            # Animate: quick expand then fade
            flameTrack = Sequence(
                Parallel(
                    LerpScaleInterval(fireNode, 0.3, burstScale * 1.5, blendType='easeOut'),
                    LerpColorScaleInterval(fireNode, 0.3, Vec4(1.0, 0.3, 0.0, 0.0), blendType='easeIn')
                ),
                Func(fireNode.removeNode)
            )
            flameTrack.start()
    
    def _createExplosionParticles(self, explosionPos):
        """Create explosion particle effects using BattleParticles."""
        # Create gear explosion particles (small gears)
        gearExplosion = BattleParticles.createParticleEffect('GearExplosion', numParticles=30)
        
        # Create wide gear explosion (larger spread)
        wideGearExplosion = BattleParticles.createParticleEffect('WideGearExplosion', numParticles=50)
        
        # Create node for particles
        explosionNode = NodePath('explosionParticles')
        explosionNode.reparentTo(render)
        explosionNode.setPos(explosionPos)
        
        # Scale based on object size
        explosionScale = self.baseScale * 5.0 if self.isCFOBoss else self.baseScale * 2.5
        explosionNode.setScale(explosionScale)
        
        # Play both particle effects
        particleTrack = Parallel(
            ParticleInterval(gearExplosion, explosionNode, worldRelative=0, duration=4.0, cleanup=True),
            ParticleInterval(wideGearExplosion, explosionNode, worldRelative=0, duration=2.0, cleanup=True),
            Sequence(
                Wait(4.0),
                Func(explosionNode.removeNode)
            )
        )
        particleTrack.start()
    
    def _createScreenFlash(self):
        """Create a white screen flash using GeomNode approach (like FogOverlay) - more reliable."""
        try:
            from panda3d.core import GeomNode, Geom, GeomVertexData, GeomVertexFormat, GeomVertexWriter, GeomTristrips, TransparencyAttrib
            
            self.notify.info("=== CREATING WHITE SCREEN FLASH (GeomNode method) ===")
            
            # Create base node on aspect2d (like FogOverlay does)
            self.screenFlashBase = aspect2d.attachNewNode('explosionScreenFlash')
            
            # Create GeomNode
            overlayGN = GeomNode('FlashOverlay')
            self.screenFlashNode = self.screenFlashBase.attachNewNode(overlayGN)
            self.screenFlashNode.setDepthWrite(False)
            self.screenFlashNode.setTransparency(TransparencyAttrib.MAlpha)
            self.screenFlashNode.setBin('fixed', 999999)  # Maximum priority
            
            # Create vertices for fullscreen quad
            # aspect2d coordinates: X = left/right, Z = up/down, Y = forward/back (use 0)
            # Match FogOverlay format: (-2, 0, 1), (-2, 0, -1), (2, 0, 1), (2, 0, -1)
            # But make it much larger to cover entire screen
            aspectRatio = base.getAspectRatio()
            # Oversize to guarantee full coverage
            xSize = aspectRatio * 3.0  # Much larger than needed
            zSize = 3.0  # Much larger than needed
            shapeVertices = [
                (-xSize, 0.0, zSize),   # Top-left
                (-xSize, 0.0, -zSize),  # Bottom-left
                (xSize, 0.0, zSize),    # Top-right
                (xSize, 0.0, -zSize),   # Bottom-right
            ]
            
            # Create vertex format with position and color
            gFormat = GeomVertexFormat.getV3cp()
            overlayVertexData = GeomVertexData('flashVertices', gFormat, Geom.UHStatic)
            overlayVertexWriter = GeomVertexWriter(overlayVertexData, 'vertex')
            overlayColorWriter = GeomVertexWriter(overlayVertexData, 'color')
            
            # Write vertices and colors (white, fully opaque)
            for vertex in shapeVertices:
                overlayVertexWriter.addData3f(vertex[0], vertex[1], vertex[2])
                overlayColorWriter.addData4f(1.0, 1.0, 1.0, 1.0)  # White, opaque
            
            # Create triangle strip
            overlayTris = GeomTristrips(Geom.UHStatic)
            for i in range(len(shapeVertices)):
                overlayTris.addVertex(i)
            overlayTris.closePrimitive()
            
            # Create geometry
            overlayGeom = Geom(overlayVertexData)
            overlayGeom.addPrimitive(overlayTris)
            overlayGN.addGeom(overlayGeom)
            
            # Show it
            self.screenFlashNode.show()
            
            self.notify.info(f"Screen flash created on aspect2d, aspectRatio={aspectRatio}")
            
            # Fade out duration
            flashDuration = 0.5 if self.isCFOBoss else 0.35
            
            def destroyFlash():
                self.notify.info("Destroying screen flash")
                if hasattr(self, 'screenFlashBase') and self.screenFlashBase:
                    try:
                        self.screenFlashBase.removeNode()
                        self.screenFlashBase = None
                        self.screenFlashNode = None
                    except Exception as e:
                        self.notify.warning(f"Error destroying flash: {e}")
            
            # Fade out by modifying vertex colors
            def updateFlashAlpha(alpha):
                if hasattr(self, 'screenFlashNode') and self.screenFlashNode and not self.screenFlashNode.isEmpty():
                    try:
                        # Update color to fade alpha
                        self.screenFlashNode.setColorScale(1, 1, 1, alpha)
                    except:
                        pass
            
            # Create fade sequence
            self.flashSequence = Sequence(
                Wait(0.05),  # Brief hold at full white
                LerpColorScaleInterval(
                    self.screenFlashNode,
                    flashDuration,
                    Vec4(1, 1, 1, 0),  # Fade to transparent
                    startColorScale=Vec4(1, 1, 1, 1),
                    blendType='easeIn'
                ),
                Func(destroyFlash)
            )
            
            # Start immediately
            self.flashSequence.start()
            
            self.notify.info("Screen flash sequence started")
            
        except Exception as e:
            import traceback
            self.notify.warning(f"CRITICAL: Failed to create screen flash: {e}")
            self.notify.warning(traceback.format_exc())
    
    def _createCameraShake(self):
        """Create a camera shake effect for the explosion using a task-based approach."""
        try:
            # Use base.camera directly (standard Toontown approach)
            try:
                camera = base.camera
            except:
                self.notify.warning("Could not access camera for shake effect")
                return
            
            if not camera or camera.isEmpty():
                self.notify.warning("Camera not available for shake effect")
                return
            
            # Shake intensity - stronger for CFO
            if self.isCFOBoss:
                shakeIntensity = 1.2 * self.baseScale  # Strong shake for CFO
                shakeDuration = 0.5
            else:
                shakeIntensity = 0.6 * self.baseScale  # Moderate shake for safes
                shakeDuration = 0.35
            
            # Initialize shake state
            self.cameraShakeActive = True
            self.cameraShakeStartTime = globalClock.getFrameTime()
            self.cameraShakeDuration = shakeDuration
            self.cameraShakeIntensity = shakeIntensity
            self.cameraShakeOffset = Vec3(0, 0, 0)
            self.cameraShakeLastUpdate = 0.0
            self.cameraShakeDirection = Vec3(
                (random.random() - 0.5) * 2.0,
                (random.random() - 0.5) * 2.0,
                (random.random() - 0.5) * 0.8
            ).normalized()
            
            # Store camera reference
            self.shakeCamera = camera
            
            # Start shake update task
            taskMgr.add(self._updateCameraShake, self.uniqueName('cameraShake'), priority=50)
            
            # Schedule shake end
            taskMgr.doMethodLater(shakeDuration, self._stopCameraShake, self.uniqueName('stopCameraShake'))
            
            self.notify.info(f"Camera shake started - intensity={shakeIntensity}, duration={shakeDuration}")
            
        except Exception as e:
            import traceback
            self.notify.warning(f"Error creating camera shake: {e}")
            self.notify.warning(traceback.format_exc())
    
    def _updateCameraShake(self, task):
        """Update camera shake every frame - applies offset to current camera position."""
        if not self.cameraShakeActive or not hasattr(self, 'shakeCamera') or not self.shakeCamera:
            return task.done
        
        try:
            currentTime = globalClock.getFrameTime()
            elapsed = currentTime - self.cameraShakeStartTime
            
            if elapsed >= self.cameraShakeDuration:
                # Shake finished - remove offset
                self._removeCameraShakeOffset()
                return task.done
            
            # Calculate shake progress (0.0 to 1.0)
            progress = elapsed / self.cameraShakeDuration
            
            # Decay intensity over time (strong at start, weak at end)
            intensityMultiplier = 1.0 - (progress * progress)  # Quadratic decay
            
            # Calculate current shake offset
            # Use perlin-like noise for smoother shake
            import math
            shakeFrequency = 15.0  # How fast the shake oscillates
            timeValue = elapsed * shakeFrequency
            
            # Random direction changes periodically
            if int(timeValue) != self.cameraShakeLastUpdate:
                self.cameraShakeDirection = Vec3(
                    (random.random() - 0.5) * 2.0,
                    (random.random() - 0.5) * 2.0,
                    (random.random() - 0.5) * 0.8
                ).normalized()
                self.cameraShakeLastUpdate = int(timeValue)
            
            # Calculate offset magnitude (oscillates)
            offsetMagnitude = self.cameraShakeIntensity * intensityMultiplier
            oscillation = math.sin(timeValue * 2.0 * math.pi) * 0.5 + 0.5  # 0 to 1
            
            # Apply offset to camera
            currentPos = self.shakeCamera.getPos(render)
            newOffset = self.cameraShakeDirection * (offsetMagnitude * oscillation)
            
            # Remove old offset and apply new one
            self.shakeCamera.setPos(render, currentPos - self.cameraShakeOffset + newOffset)
            self.cameraShakeOffset = newOffset
            
            return task.cont
            
        except Exception as e:
            self.notify.warning(f"Error updating camera shake: {e}")
            return task.done
    
    def _removeCameraShakeOffset(self):
        """Remove the camera shake offset and restore original position."""
        if hasattr(self, 'shakeCamera') and self.shakeCamera and hasattr(self, 'cameraShakeOffset'):
            try:
                currentPos = self.shakeCamera.getPos(render)
                self.shakeCamera.setPos(render, currentPos - self.cameraShakeOffset)
                self.cameraShakeOffset = Vec3(0, 0, 0)
            except:
                pass
    
    def _stopCameraShake(self, task):
        """Stop the camera shake effect."""
        self.cameraShakeActive = False
        self._removeCameraShakeOffset()
        taskMgr.remove(self.uniqueName('cameraShake'))
        return task.done
    
    
    def _applyDepthSettingsRecursive(self, node):
        """Recursively apply depth settings to node and all its children."""
        if node.isEmpty():
            return
        
        node.setDepthWrite(False)
        
        for child in node.getChildren():
            self._applyDepthSettingsRecursive(child)
    
    def stop(self):
        """Stop the effect."""
        # Cancel pending effects
        taskMgr.remove(self.uniqueName('finalExplosion'))
        # Stop camera shake if active
        if hasattr(self, 'cameraShakeActive') and self.cameraShakeActive:
            self._stopCameraShake(None)
    
    def gracefulCleanup(self):
        """Gracefully clean up the effect."""
        # IMPORTANT: Don't cancel finalExplosion task - it needs to run!
        # The effect might be removed at 1.5s, but we need the explosion to happen
        
        # DON'T cancel finalExplosion - it needs to run!
        
        # Mark as inactive but don't stop the effect yet
        self.active = False
        
        # Schedule cleanup AFTER explosion happens (give it time)
        taskMgr.doMethodLater(3.0, self._delayedCleanup, self.uniqueName('gracefulCleanup'))
    
    def _delayedCleanup(self, task):
        """Actually remove the nodes after explosion has finished."""
        
        if hasattr(self, 'screenFlash') and self.screenFlash:
            try:
                self.screenFlash.destroy()
            except:
                pass
            self.screenFlash = None
        
        if hasattr(self, 'screenFlashCard') and self.screenFlashCard:
            try:
                self.screenFlashCard.removeNode()
            except:
                pass
            self.screenFlashCard = None
        
        if hasattr(self, 'screenFlashBase') and self.screenFlashBase:
            try:
                self.screenFlashBase.removeNode()
            except:
                pass
            self.screenFlashBase = None
            self.screenFlashNode = None
        
        if hasattr(self, 'particleRenderParent') and self.particleRenderParent and not self.particleRenderParent.isEmpty():
            try:
                self.particleRenderParent.removeNode()
            except:
                pass
            self.particleRenderParent = None
        
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
                return f'explosionEffect-{self.obj.getDoId()}-{name}'
            except:
                pass
        return f'explosionEffect-{name}'
    
    def cleanup(self, force=False):
        """Completely clean up the effect immediately."""
        # Cancel all pending tasks
        taskMgr.remove(self.uniqueName('finalExplosion'))
        taskMgr.remove(self.uniqueName('gracefulCleanup'))
        taskMgr.remove(self.uniqueName('stopCameraShake'))
        taskMgr.remove(self.uniqueName('cameraShake'))
        
        # Stop effect
        self.stop()
        
        # Stop camera shake if active
        if hasattr(self, 'cameraShakeActive') and self.cameraShakeActive:
            self._stopCameraShake(None)
        
        if hasattr(self, 'screenFlash') and self.screenFlash:
            try:
                self.screenFlash.destroy()
            except:
                pass
            self.screenFlash = None
        
        if hasattr(self, 'screenFlashCard') and self.screenFlashCard:
            try:
                self.screenFlashCard.removeNode()
            except:
                pass
            self.screenFlashCard = None
        
        if hasattr(self, 'screenFlashBase') and self.screenFlashBase:
            try:
                self.screenFlashBase.removeNode()
            except:
                pass
            self.screenFlashBase = None
            self.screenFlashNode = None
        
        if hasattr(self, 'particleRenderParent') and self.particleRenderParent and not self.particleRenderParent.isEmpty():
            try:
                self.particleRenderParent.removeNode()
            except:
                pass
            self.particleRenderParent = None
        
        if self.effectNode and not self.effectNode.isEmpty():
            try:
                self.effectNode.detachNode()
                self.effectNode.removeNode()
            except:
                pass
            self.effectNode = None
            
        self.active = False
    
    def updateStack(self, stackCount: int):
        """Update explosion intensity based on stack count."""
        super().updateStack(stackCount)
        
        # Explosion is a one-shot effect, stacking doesn't really apply
        # But we could make it more intense if stacked
        pass


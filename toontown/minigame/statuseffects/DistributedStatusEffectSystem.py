from toontown.minigame.statuseffects.StatusEffectGlobals import StatusEffect, STATUS_EFFECT_COLORS
from direct.gui.DirectLabel import DirectLabel
from panda3d.core import Point3, Point2, TextNode, Vec3, Vec4
from direct.interval.IntervalGlobal import Sequence, Wait, LerpColorScaleInterval, Func, ParticleInterval
from toontown.toonbase import ToontownGlobals
from direct.distributed.DistributedObject import DistributedObject
from toontown.battle import BattleParticles

class DistributedStatusEffectSystem(DistributedObject):
    def __init__(self, cr):
        DistributedObject.__init__(self, cr)
        self.activeEffectTexts = {}  # objectId -> {statusEffect -> DirectLabel}
        self.effectStacks = {}  # objectId -> {statusEffect -> int}
        self.activeEffectVisuals = {}  # objectId -> {statusEffect -> visual effect data}

    def applyStatusEffect(self, objectId, statusEffect):
        effect = StatusEffect.fromAstron(statusEffect)
        if effect is None:
            return
        
        # Get the object from the distributed object cache
        obj = self.cr.getDo(objectId)
        if obj is None:
            return
        
        # Initialize tracking for this object if needed
        if objectId not in self.activeEffectTexts:
            self.activeEffectTexts[objectId] = {}
        
        # Initialize tracking for this object if needed
        if objectId not in self.effectStacks:
            self.effectStacks[objectId] = {}

        if effect in self.effectStacks[objectId]:
            self.effectStacks[objectId][effect] += 1
            self.activeEffectTexts[objectId][effect].setText(f'{effect.name} ({self.effectStacks[objectId][effect]})')
        else:
            self.effectStacks[objectId][effect] = 1
        
        # Don't create duplicate text for the same effect on the same object
        if effect in self.activeEffectTexts[objectId]:
            return
        
        # Apply visual effects for this status effect first to determine if we need text
        hasVisualEffect = self._applyVisualEffect(objectId, effect, obj)
        
        # Skip text label if we have a visual effect (like fire for BURNED)
        if hasVisualEffect:
            # Still need to track the effect in activeEffectTexts for cleanup, but no actual label
            self.activeEffectTexts[objectId][effect] = None
            return
        
        # Get the color for this effect, default to white if not defined
        effectColor = STATUS_EFFECT_COLORS.get(effect, (1.0, 1.0, 1.0, 1.0))
        
        # Calculate height - try to get object bounds for proper positioning
        objHeight = 3.0  # Default height
        if hasattr(obj, 'getHeight'):
            objHeight = obj.getHeight()
        elif hasattr(obj, 'height'):
            objHeight = obj.height
        elif hasattr(obj, 'getBounds'):
            bounds = obj.getBounds()
            if bounds:
                objHeight = bounds.getRadius() * 1.05
        
        # Calculate vertical offset based on how many effects are already on this object
        numExistingEffects = len(self.activeEffectTexts[objectId])
        verticalOffset = objHeight + 2.0 + (numExistingEffects * 1.0)  # Stack effects vertically above object
        
        # Create the status effect text
        effectText = DirectLabel(
            text=effect.name,
            pos=(0, 0, verticalOffset),
            scale=1,
            text_fg=effectColor,
            text_shadow=(0, 0, 0, 0.5),  # Black shadow for readability
            parent=obj,
            text_align=TextNode.ACenter,
            relief=None  # No background
        )
        
        # Make the text always face the camera (billboarding)
        effectText.setBillboardPointEye()
        
        # Store the text so we can remove it later
        self.activeEffectTexts[objectId][effect] = effectText

    def removeStatusEffect(self, objectId, statusEffect):
        effect = StatusEffect.fromAstron(statusEffect)
        if effect is None:
            return
        
        if objectId not in self.effectStacks:
            return
        
        if effect not in self.effectStacks[objectId]:
            return
        
        if objectId not in self.activeEffectTexts:
            return
        
        if effect not in self.activeEffectTexts[objectId]:
            return
        
        self.effectStacks[objectId][effect] -= 1
        if self.effectStacks[objectId][effect] == 0:
            # Remove and cleanup the text (if it exists)
            effectText = self.activeEffectTexts[objectId][effect]
            if effectText:
                effectText.destroy()
            del self.activeEffectTexts[objectId][effect]
            del self.effectStacks[objectId][effect]
            
            # Remove visual effects
            self._removeVisualEffect(objectId, effect)
            
            # Clean up the object entry if no more effects
            if not self.activeEffectTexts[objectId]:
                del self.activeEffectTexts[objectId]
        else:
            # Update text count if text exists
            effectText = self.activeEffectTexts[objectId][effect]
            if effectText:
                effectText.setText(f'{effect.name} ({self.effectStacks[objectId][effect]})')

        # Reposition remaining effects to fill the gap
        self._repositionEffectTexts(objectId)
    
    def _repositionEffectTexts(self, objectId):
        """Reposition remaining status effect texts to fill gaps when one is removed"""
        if objectId not in self.activeEffectTexts:
            return
        
        # Get the object to calculate its height (same logic as applyStatusEffect)
        obj = self.cr.getDo(objectId)
        if not obj:
            return
        
        # Calculate height - try to get object bounds for proper positioning
        objHeight = 3.0  # Default height
        if hasattr(obj, 'getHeight'):
            objHeight = obj.getHeight()
        elif hasattr(obj, 'height'):
            objHeight = obj.height
        elif hasattr(obj, 'getBounds'):
            bounds = obj.getBounds()
            if bounds:
                objHeight = bounds.getRadius() * 1.05
        
        effects = list(self.activeEffectTexts[objectId].values())
        for i, effectText in enumerate(effects):
            # Skip None entries (visual effects without text)
            if effectText is None:
                continue
            verticalOffset = objHeight + 2.0 + (i * 1.0)  # Match the spacing from applyStatusEffect
            effectText.setPos(0, 0, verticalOffset)
    
    def _applyVisualEffect(self, objectId, effect, obj):
        """Apply visual particle effects based on the status effect type
        Returns True if a visual effect was created, False otherwise"""
        if objectId not in self.activeEffectVisuals:
            self.activeEffectVisuals[objectId] = {}
        
        # Don't create duplicate visuals
        if effect in self.activeEffectVisuals[objectId]:
            return True
        
        visualData = None
        
        if effect == StatusEffect.BURNED:
            visualData = self._createBurnedEffect(obj)
        elif effect == StatusEffect.FROZEN:
            visualData = self._createFrozenEffect(obj)
        # Add more effects as needed
        
        if visualData:
            self.activeEffectVisuals[objectId][effect] = visualData
            return True
        
        return False
    
    def _createBurnedEffect(self, obj):
        """Create fire/burn particle effect"""
        # Save original color scale before modifying
        hadColorScale = obj.hasColorScale()
        originalColorScale = obj.getColorScale() if hadColorScale else None
        
        # Load battle particles for fire effects
        BattleParticles.loadParticles()
        
        # Create a node to hold all fire effects, attach directly to the object
        fireNode = obj.attachNewNode('burnEffect')
        
        # Determine object type and use appropriate positioning
        # CBSafe model dimensions (from egg file):
        # - X: -3.919 to 4.284 (width: ~8.2 units)
        # - Y: -4.191 to 4.093 (depth: ~8.3 units)  
        # - Z: 0.061 to 8.201 (height: ~8.1 units)
        # - Center: (0.182, -0.049, 4.131)
        
        particles = []
        
        # Check if this is a safe (has 'safe' in the name)
        objName = obj.getName().lower()
        if 'safe' in objName:
            # For safes: single emitter at center, radiating outward and upward
            # Safe dimensions: radius ~4 units, height ~8.1 units, center at Z=4.1
            safeRadius = 4.0  # Radius of the safe
            safeHeight = 8.1  # Total height
            centerZ = 4.1  # Center of safe (from egg file analysis)
            
            # Single flame effect at center
            fireEffect = BattleParticles.createParticleEffect('FiredFlame')
            fireEffect.reparentTo(fireNode)
            fireEffect.setPos(0, 0, centerZ-1)  # Center of safe
            
            # Modify emitter to radiate outward with controlled radius
            try:
                particleSystem = fireEffect.getParticlesNamed('particles-1')
                if particleSystem:
                    emitter = particleSystem.getEmitter()
                    renderer = particleSystem.getRenderer()
                    if emitter:
                        # Set radiate origin at emitter position (center)
                        emitter.setRadiateOrigin(Point3(0, 0, 0))
                        # Moderate amplitude - adjust this to control how far particles radiate outward
                        emitter.setAmplitude(0.5)  # Reduced from 3.0
                        # Upward force to make flames extend above safe
                        emitter.setOffsetForce(Vec3(0, 0, safeHeight*0.9))  # Reduced from 1.2
                        # Emitter radius - adjust this to control emission area
                        emitter.setRadius(safeRadius * 0.5)  # Reduced from 0.8 (now ~1.6 units)
                    if renderer:
                        # Increase particle size - adjust these multipliers to make particles bigger
                        sizeMultiplier = 2.5  # Increase this to make particles larger
                        initialXScale = renderer.getInitialXScale()
                        finalXScale = renderer.getFinalXScale()
                        initialYScale = renderer.getInitialYScale() * sizeMultiplier
                        finalYScale = renderer.getFinalYScale() * sizeMultiplier
                        renderer.setInitialXScale(initialXScale)
                        renderer.setFinalXScale(finalXScale)
                        renderer.setInitialYScale(initialYScale)
                        renderer.setFinalYScale(finalYScale)
            except:
                pass
            
            fireEffect.setScale(2.5)  # Scale the whole effect
            # parent=fireNode: particles spawn relative to fireNode position
            # renderParent=base.render: particles render at render level to avoid clipping through safe
            fireEffect.start(parent=fireNode, renderParent=base.render)
            particles.append(fireEffect)
            
            # Single flecks effect at center
            flecksEffect = BattleParticles.createParticleEffect('SpriteFiredFlecks')
            flecksEffect.reparentTo(fireNode)
            flecksEffect.setPos(0, 0, centerZ)
            
            # Modify flecks emitter similarly
            try:
                particleSystem = flecksEffect.getParticlesNamed('particles-1')
                if particleSystem:
                    emitter = particleSystem.getEmitter()
                    renderer = particleSystem.getRenderer()
                    if emitter:
                        emitter.setRadiateOrigin(Point3(0, 0, 0))
                        emitter.setAmplitude(1.8)  # Reduced from 2.5
                        emitter.setOffsetForce(Vec3(0, 0, safeHeight * 0.9))  # Reduced from 1.0
                        emitter.setRadius(safeRadius * 0.4)  # Reduced from 0.7 (now ~1.2 units)
                    if renderer:
                        # Increase flecks particle size
                        sizeMultiplier = 3.0  # Increase this to make flecks larger
                        initialXScale = renderer.getInitialXScale() * sizeMultiplier
                        finalXScale = renderer.getFinalXScale() * sizeMultiplier
                        initialYScale = renderer.getInitialYScale() * sizeMultiplier
                        finalYScale = renderer.getFinalYScale() * sizeMultiplier
                        renderer.setInitialXScale(initialXScale)
                        renderer.setFinalXScale(finalXScale)
                        renderer.setInitialYScale(initialYScale)
                        renderer.setFinalYScale(finalYScale)
                        # Fix flecks color - make them orange/red like fire instead of white
                        renderer.setColor(Vec4(1.0, 0.6, 0.2, 1.0))  # Orange-red color
            except:
                pass
            
            flecksEffect.setScale(1.2)  # Reduced from 2.0
            # parent=fireNode: particles spawn relative to fireNode position
            # renderParent=base.render: particles render at render level to avoid clipping through safe
            flecksEffect.start(parent=fireNode, renderParent=base.render)
            particles.append(flecksEffect)
        else:
            # For other objects (like CFO), use single centered fire with larger scale
            scale = 4.0
            zOffset = 8.0
            
            try:
                if hasattr(obj, 'getBounds'):
                    bounds = obj.getBounds()
                    if bounds and not bounds.isEmpty() and not bounds.isInfinite():
                        center = bounds.getCenter()
                        radius = bounds.getRadius()
                        zOffset = center.getZ() + (radius * 0.3)
                        scale = max(3.0, min(8.0, radius / 2.0))
            except:
                pass
            
            # Create single large fire effect for CFO
            fireEffect1 = BattleParticles.createParticleEffect('FiredFlame')
            fireEffect2 = BattleParticles.createParticleEffect('SpriteFiredFlecks')
            
            fireEffect1.reparentTo(fireNode)
            fireEffect2.reparentTo(fireNode)
            fireEffect1.setPos(0, 0, zOffset)
            fireEffect2.setPos(0, 0, zOffset)
            fireEffect1.setScale(scale)
            fireEffect2.setScale(scale)
            # For CFO: particles spawn from fireNode and render at render level
            fireEffect1.start(parent=fireNode, renderParent=base.render)
            fireEffect2.start(parent=fireNode, renderParent=base.render)
            
            particles = [fireEffect1, fireEffect2]
        
        # No color tinting for now
        
        return {
            'node': fireNode,
            'particles': particles,
            'hadColorScale': hadColorScale,
            'originalColorScale': originalColorScale
        }
    
    def _createFrozenEffect(self, obj):
        """Create freeze/ice visual effect"""
        # Save original color scale before modifying
        hadColorScale = obj.hasColorScale()
        originalColorScale = obj.getColorScale() if hadColorScale else None
        
        # Apply blue tint to indicate frozen state
        obj.setColorScale(0.5, 0.7, 1.0, 1.0)
        
        return {
            'node': None,
            'particles': [],
            'hadColorScale': hadColorScale,
            'originalColorScale': originalColorScale
        }
    
    def _removeVisualEffect(self, objectId, effect):
        """Remove visual effects when status effect is removed"""
        if objectId not in self.activeEffectVisuals:
            return
        
        if effect not in self.activeEffectVisuals[objectId]:
            return
        
        visualData = self.activeEffectVisuals[objectId][effect]
        
        # Clean up particle effects
        if visualData.get('particles'):
            for particle in visualData['particles']:
                particle.cleanup()
        
        # Clean up the node
        if visualData.get('node'):
            visualData['node'].removeNode()
        
        # Restore original color scale
        obj = self.cr.getDo(objectId)
        if obj:
            if visualData.get('hadColorScale') and visualData.get('originalColorScale'):
                obj.setColorScale(visualData['originalColorScale'])
            else:
                obj.clearColorScale()
        
        del self.activeEffectVisuals[objectId][effect]
        
        # Clean up object entry if no more visual effects
        if not self.activeEffectVisuals[objectId]:
            del self.activeEffectVisuals[objectId]
    
    def cleanup(self):
        """Clean up all status effect texts and visuals when the system is destroyed"""
        # Clean up visual effects
        for objectId in list(self.activeEffectVisuals.keys()):
            for effect in list(self.activeEffectVisuals[objectId].keys()):
                self._removeVisualEffect(objectId, effect)
        self.activeEffectVisuals.clear()
        
        # Clean up text labels
        for objectId in list(self.activeEffectTexts.keys()):
            for effect in list(self.activeEffectTexts[objectId].keys()):
                effectText = self.activeEffectTexts[objectId][effect]
                if effectText:
                    effectText.destroy()
        self.activeEffectTexts.clear()

    def hasStatusEffect(self, objectId, statusEffect):
        return statusEffect in self.effectStacks.get(objectId, {})
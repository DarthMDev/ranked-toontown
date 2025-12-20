from toontown.minigame.statuseffects.StatusEffectGlobals import StatusEffect, STATUS_EFFECT_COLORS
from direct.gui.DirectLabel import DirectLabel
from panda3d.core import Point3, Point2, TextNode
from direct.interval.IntervalGlobal import Sequence, Wait, LerpColorScaleInterval, Func
from toontown.toonbase import ToontownGlobals
from direct.distributed.DistributedObject import DistributedObject
from direct.directnotify import DirectNotifyGlobal

# Import visual effect classes
from toontown.minigame.statuseffects.BurnedEffectVisual import BurnedEffectVisual
from toontown.minigame.statuseffects.DrenchedEffectVisual import DrenchedEffectVisual
from toontown.minigame.statuseffects.GroundedEffectVisual import GroundedEffectVisual

class DistributedStatusEffectSystem(DistributedObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('StatusEffectSystem')
    
    def __init__(self, cr):
        DistributedObject.__init__(self, cr)
        self.activeEffectTexts = {}  # objectId -> {statusEffect -> DirectLabel} (legacy, for unsupported effects)
        self.activeEffectVisuals = {}  # objectId -> {statusEffect -> StatusEffectVisualBase}
        self.effectStacks = {}  # objectId -> {statusEffect -> int}

    def _getVisualClassForEffect(self, effect: StatusEffect):
        """
        Get the visual effect class for a given status effect.
        
        Returns:
            The visual class, or None if no visual is implemented
        """
        visualMap = {
            StatusEffect.BURNED: BurnedEffectVisual,
            StatusEffect.DRENCHED: DrenchedEffectVisual,
            StatusEffect.GROUNDED: GroundedEffectVisual,
            # Add more as they're implemented:
            # StatusEffect.FROZEN: FrozenEffectVisual,
            # etc.
        }
        return visualMap.get(effect)
    
    def applyStatusEffect(self, objectId, statusEffect):
        effect = StatusEffect.fromAstron(statusEffect)
        if effect is None:
            return
        
        # Get the object from the distributed object cache
        obj = self.cr.getDo(objectId)
        if obj is None:
            self.notify.warning(f"Cannot apply effect {effect} - object {objectId} not found")
            return
        
        # Initialize tracking for this object if needed
        if objectId not in self.activeEffectTexts:
            self.activeEffectTexts[objectId] = {}
        if objectId not in self.activeEffectVisuals:
            self.activeEffectVisuals[objectId] = {}
        if objectId not in self.effectStacks:
            self.effectStacks[objectId] = {}

        # Update or initialize stack count
        if effect in self.effectStacks[objectId]:
            self.effectStacks[objectId][effect] += 1
        else:
            self.effectStacks[objectId][effect] = 1
        
        stackCount = self.effectStacks[objectId][effect]
        
        # Check if we have a proper visual implementation for this effect
        visualClass = self._getVisualClassForEffect(effect)
        
        if visualClass:
            # Use the proper particle/visual effect system
            if effect not in self.activeEffectVisuals[objectId]:
                # Create new visual effect
                try:
                    visual = visualClass(obj, self.cr)
                    visual.create()
                    visual.start()
                    self.activeEffectVisuals[objectId][effect] = visual
                    self.notify.info(f"Created visual effect for {effect.name} on object {objectId}")
                except Exception as e:
                    import traceback
                    self.notify.warning(f"Failed to create visual for {effect.name}: {e}")
                    self.notify.warning(traceback.format_exc())
                    # Don't fall back to text - just log the error
                    # Visual effects should work or be fixed, not have text fallbacks
            else:
                # Update existing visual with new stack count
                visual = self.activeEffectVisuals[objectId][effect]
                visual.updateStack(stackCount)
        else:
            # Fall back to legacy text-based system for effects without visual implementations
            if effect not in self.activeEffectTexts[objectId]:
                self._createLegacyTextEffect(obj, objectId, effect, stackCount)
            else:
                # Update text with stack count
                self.activeEffectTexts[objectId][effect].setText(
                    f'{effect.name} ({stackCount})' if stackCount > 1 else effect.name
                )
    
    def _createLegacyTextEffect(self, obj, objectId, effect, stackCount):
        """
        Create a text-based effect visual (legacy fallback).
        
        Args:
            obj: The object NodePath
            objectId: The object's doId
            effect: The StatusEffect enum
            stackCount: Number of stacks
        """
        # Get the color for this effect
        effectColor = STATUS_EFFECT_COLORS.get(effect, (1.0, 1.0, 1.0, 1.0))
        
        # Calculate height for positioning
        objHeight = 3.0  # Default
        try:
            bounds = obj.getTightBounds()
            if bounds:
                minPt, maxPt = bounds
                objHeight = maxPt.getZ() - minPt.getZ()
        except:
            if hasattr(obj, 'getHeight'):
                objHeight = obj.getHeight()
            elif hasattr(obj, 'height'):
                objHeight = obj.height
        
        # Calculate vertical offset based on existing effects
        numExistingEffects = len(self.activeEffectTexts[objectId]) + len(self.activeEffectVisuals[objectId])
        verticalOffset = objHeight + 2.0 + (numExistingEffects * 1.0)
        
        # Create text label
        text = f'{effect.name} ({stackCount})' if stackCount > 1 else effect.name
        effectText = DirectLabel(
            text=text,
            pos=(0, 0, verticalOffset),
            scale=1,
            text_fg=effectColor,
            text_shadow=(0, 0, 0, 0.5),
            parent=obj,
            text_align=TextNode.ACenter,
            relief=None
        )
        effectText.setBillboardPointEye()
        
        self.activeEffectTexts[objectId][effect] = effectText
        self.notify.info(f"Created legacy text effect for {effect.name} on object {objectId}")

    def removeStatusEffect(self, objectId, statusEffect):
        effect = StatusEffect.fromAstron(statusEffect)
        if effect is None:
            return
        
        if objectId not in self.effectStacks:
            return
        
        if effect not in self.effectStacks[objectId]:
            return
        
        # Decrement stack count
        self.effectStacks[objectId][effect] -= 1
        stackCount = self.effectStacks[objectId][effect]
        
        if stackCount == 0:
            # Remove effect completely
            
            # Gracefully clean up visual effect if it exists (let particles fade out)
            if objectId in self.activeEffectVisuals and effect in self.activeEffectVisuals[objectId]:
                visual = self.activeEffectVisuals[objectId][effect]
                try:
                    # Use graceful cleanup to let particles fade out naturally
                    if hasattr(visual, 'gracefulCleanup'):
                        visual.gracefulCleanup()
                    else:
                        # Fallback to regular cleanup if graceful cleanup not available
                        visual.cleanup()
                except Exception as e:
                    self.notify.warning(f"Error cleaning up visual for {effect.name}: {e}")
                del self.activeEffectVisuals[objectId][effect]
                
                if not self.activeEffectVisuals[objectId]:
                    del self.activeEffectVisuals[objectId]
            
            # Clean up text effect if it exists
            if objectId in self.activeEffectTexts and effect in self.activeEffectTexts[objectId]:
                effectText = self.activeEffectTexts[objectId][effect]
                effectText.destroy()
                del self.activeEffectTexts[objectId][effect]
                
                if not self.activeEffectTexts[objectId]:
                    del self.activeEffectTexts[objectId]
            
            # Remove from stack tracking
            del self.effectStacks[objectId][effect]
            if not self.effectStacks[objectId]:
                del self.effectStacks[objectId]
                
            self.notify.info(f"Removed {effect.name} from object {objectId}")
        else:
            # Update stack count
            
            # Update visual if it exists
            if objectId in self.activeEffectVisuals and effect in self.activeEffectVisuals[objectId]:
                visual = self.activeEffectVisuals[objectId][effect]
                visual.updateStack(stackCount)
            
            # Update text if it exists
            if objectId in self.activeEffectTexts and effect in self.activeEffectTexts[objectId]:
                text = f'{effect.name} ({stackCount})' if stackCount > 1 else effect.name
                self.activeEffectTexts[objectId][effect].setText(text)
        
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
            verticalOffset = objHeight + 2.0 + (i * 1.0)  # Match the spacing from applyStatusEffect
            effectText.setPos(0, 0, verticalOffset)
    
    def cleanup(self):
        """Clean up all status effects when the system is destroyed"""
        # Clean up all visual effects
        for objectId in list(self.activeEffectVisuals.keys()):
            for effect in list(self.activeEffectVisuals[objectId].keys()):
                try:
                    visual = self.activeEffectVisuals[objectId][effect]
                    visual.cleanup()
                except Exception as e:
                    self.notify.warning(f"Error cleaning up visual: {e}")
        self.activeEffectVisuals.clear()
        
        # Clean up all text effects
        for objectId in list(self.activeEffectTexts.keys()):
            for effect in list(self.activeEffectTexts[objectId].keys()):
                try:
                    effectText = self.activeEffectTexts[objectId][effect]
                    effectText.destroy()
                except Exception as e:
                    self.notify.warning(f"Error cleaning up text: {e}")
        self.activeEffectTexts.clear()
        
        # Clear stacks
        self.effectStacks.clear()

    def hasStatusEffect(self, objectId, statusEffect):
        return statusEffect in self.effectStacks.get(objectId, {})
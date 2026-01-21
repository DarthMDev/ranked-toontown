"""
StatusEffectManagerAI - Handles status effects on safes and boss.
"""

import random
from direct.task.TaskManagerGlobal import taskMgr
from toontown.minigame.utils.statuseffects.StatusEffectGlobals import SAFE_ALLOWED_EFFECTS


class StatusEffectManagerAI:
    """Manages status effects on safes and coordinates with boss status effects."""
    
    def __init__(self, game):
        self.game = game
        self.safeEffectTasks = set()  # Track safe effect tasks
    
    def startSafeEffectTask(self):
        """Start the task that periodically applies effects to safes"""
        taskName = self.game.uniqueName('safe-effects')
        taskMgr.remove(taskName)
        if hasattr(self.game, '_allTaskNames'):
            self.game._allTaskNames.add(taskName)
        taskMgr.add(self._applyRandomSafeEffects, taskName, delay=10.0)
    
    def _applyRandomSafeEffects(self, task=None):
        """Apply random status effects to safes periodically"""
        if not self.game.statusEffectSystem:
            return task.done
        
        for safe in self.game.safes:
            if not safe:
                continue
            
            # Skip the special helmet safe (index 0) - it should not receive elemental effects
            if safe.index == 0:
                continue
                
            safeDoId = safe.getDoId()
            hasEffect = self.game.statusEffectSystem.isObjectStatusEffected(safeDoId)
            
            # Debug logging
            if hasEffect:
                currentEffects = self.game.statusEffectSystem.getStatusEffects(safeDoId)
                self.game.notify.debug(f"Safe {safeDoId} already has effects: {currentEffects}, skipping")
            else:
                # 90% chance per safe to get an elemental effect
                if random.random() < 0.9:  # Always true for debugging
                    # Cancel any existing removal task for this safe first
                    existingTaskName = self.game.uniqueName(f'remove-effect-{safeDoId}')
                    taskMgr.remove(existingTaskName)
                    if existingTaskName in self.safeEffectTasks:
                        self.safeEffectTasks.remove(existingTaskName)
                    
                    statusEffect = random.choice(list(SAFE_ALLOWED_EFFECTS))
                    self.game.notify.debug(f"Applying {statusEffect} to safe {safeDoId}")
                    self.game.statusEffectSystem.b_applyStatusEffect(safeDoId, statusEffect)
                    # Store the safe's doId before creating the task
                    # Create task name
                    taskName = self.game.uniqueName(f'remove-effect-{safeDoId}')
                    # Remove the effect after 10 seconds
                    taskMgr.doMethodLater(
                        10.0, 
                        lambda task, doId=safeDoId, effect=statusEffect: self._removeSafeEffect(doId, effect) or task.done, 
                        taskName
                    )
                    # Track the task
                    self.safeEffectTasks.add(taskName)
        
        return task.again
    
    def cancelSafeEffectRemovalTask(self, safeDoId):
        """Cancel the scheduled removal task for a safe's effect (called when effect is removed early, e.g., when safe hits boss)"""
        taskName = self.game.uniqueName(f'remove-effect-{safeDoId}')
        taskMgr.remove(taskName)
        if taskName in self.safeEffectTasks:
            self.safeEffectTasks.remove(taskName)
    
    def _removeSafeEffect(self, doId, effect):
        """Safely remove a status effect from a safe, handling the case where the safe no longer exists"""
        if not hasattr(self.game, 'statusEffectSystem') or not self.game.statusEffectSystem:
            return True
            
        # Check if the safe still exists
        safe = self.game.air.doId2do.get(doId)
        if not safe:
            return True
        
        # Check if the effect still exists before trying to remove it
        if not self.game.statusEffectSystem.hasStatusEffect(doId, effect):
            self.game.notify.debug(f"Safe {doId} effect {effect} already removed, skipping")
            return True
            
        # Remove the effect
        self.game.notify.debug(f"Removing effect {effect} from safe {doId}")
        self.game.statusEffectSystem.b_removeStatusEffect(doId, effect)
        return True
    
    def clearAllSafeEffects(self):
        """Clear all status effects from safes"""
        if not self.game.statusEffectSystem:
            return
        
        for safe in self.game.safes:
            if safe:
                self.game.statusEffectSystem.removeAllStatusEffects(safe.doId)
    
    def cleanup(self):
        """Clean up all safe effect tasks"""
        for taskName in self.safeEffectTasks:
            taskMgr.remove(taskName)
        self.safeEffectTasks.clear()
        taskMgr.remove(self.game.uniqueName('safe-effects'))

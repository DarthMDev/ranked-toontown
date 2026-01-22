"""
CraneModifierManagerAI - Handles ruleset and modifier management for the crane game.
Inherits from the base ModifierManagerAI and uses CFORulesetModifierBase for crane-specific modifiers.
"""

import random
from toontown.minigame.craning import CraneGameGlobals
from toontown.minigame.utils.managers import ModifierManagerAI


class CraneModifierManagerAI(ModifierManagerAI):
    """
    Manages ruleset and modifier application/removal for the crane game.
    Extends the base modifier manager with crane-specific functionality like ruleset management.
    """
    
    def __init__(self, game):
        # Initialize base class - this sets up self.modifiers and self.desiredModifiers
        ModifierManagerAI.__init__(self, game)
        
        # Crane-specific properties
        self.rollModsOnStart = False
        self.numModsWanted = 5
        self.defaultModifiersInitialized = False  # Track if we've initialized default modifiers
    
    def setupRuleset(self):
        """Setup the ruleset with modifiers"""
        # Check if we have group data to restore first
        if hasattr(self.game, 'group') and self.game.group is not None:
            config = self.game.group.getMinigameConfig()
            rulesetStruct = config.getRuleset(self.game.minigameId)
            modifierStructs = config.getModifiers(self.game.minigameId)
            
            # If we have a saved ruleset, restore it
            if rulesetStruct is not None:
                self.setupRulesetFromStruct(rulesetStruct)
            else:
                # No saved ruleset - create fresh ruleset
                self.game.ruleset = CraneGameGlobals.CraneGameRuleset()
                self.modifiers.clear()
            
            # Apply modifiers from group config if they exist (even if no ruleset was saved)
            # This handles the case where modifiers were set in playground before minigame ran
            if modifierStructs:
                self.applyModifiersFromStructs(modifierStructs)
                # Save again to ensure it's up to date
                if hasattr(self.game, 'saveStateToGroup'):
                    self.game.saveStateToGroup()
                return
        
        # No group data - create fresh ruleset with defaults
        self.game.ruleset = CraneGameGlobals.CraneGameRuleset()
        self.modifiers.clear()
        modifiers = []
        for modifier in self.desiredModifiers:
            modifiers.append(modifier)
        # Should we randomize some modifiers?
        if self.rollModsOnStart:
            modifiers += self.rollRandomModifiers()
        
        # Default modifiers removed - start with 0 modifiers by default
        # Players can add modifiers manually if desired
        
        self.applyModifiers(modifiers, updateClient=True)
        
        if self.game.getBoss() is not None:
            self.game.getBoss().setRuleset(self.game.ruleset)
        
        # Save state to group after initial setup (so default modifiers are persisted)
        if hasattr(self.game, 'saveStateToGroup'):
            self.game.saveStateToGroup()
    
    def applyModifiers(self, modifiers, updateClient=False):
        """
        Call to update the ruleset with the modifiers active, note calling more than once can cause unexpected behavior
        if the ruleset doesn't fallback to an initial value, for example if a cfo hp increasing modifier is active and we
        call this multiply times, his hp will be 1500 * 1.5 * 1.5 * 1.5 etc etc
        
        Uses CFORulesetModifierBase (crane-specific) modifiers.
        """
        for modifier in modifiers:
            self.applyModifier(modifier, updateClient=False)
        if updateClient:
            self.d_setRawRuleset()
            self.d_setModifiers()
    
    def applyModifier(self, modifier, updateClient=False):
        """
        Apply a single modifier to the ruleset.
        Uses CFORulesetModifierBase (crane-specific) modifiers.
        """
        self.modifiers.append(modifier)
        
        # Apply modifier based on type
        if hasattr(modifier, 'apply'):
            # Check if it's a crane-specific modifier (applies to ruleset)
            if hasattr(CraneGameGlobals, 'CFORulesetModifierBase') and isinstance(modifier, CraneGameGlobals.CFORulesetModifierBase):
                modifier.apply(self.game.ruleset)
                self.game.ruleset.validate()
            else:
                # Generic modifier (applies to game)
                modifier.apply(self.game)
        
        if updateClient:
            self.d_setRawRuleset()
            self.d_setModifiers()
            # Save to group if available
            if hasattr(self.game, 'saveStateToGroup'):
                self.game.saveStateToGroup()
    
    def removeModifier(self, modifierClass):
        """Remove a modifier by class"""
        modifiers = list(self.modifiers)
        for mod in self.modifiers:
            if mod.__class__ == modifierClass:
                modifiers.remove(mod)
        for mod in list(self.desiredModifiers):
            if mod.__class__ == modifierClass:
                self.desiredModifiers.remove(mod)
        self.modifiers = modifiers
        self.d_setRawRuleset()
        self.d_setModifiers()
    
    def removeModifierByEnum(self, modifierEnum):
        """Remove a modifier by enum (used by client requests)"""
        removedMod = None
        
        # Remove from current modifiers
        for i, mod in enumerate(self.modifiers):
            if mod.MODIFIER_ENUM == modifierEnum:
                removedMod = self.modifiers.pop(i)
                break
        
        # Remove from desired modifiers so it doesn't come back on restart
        for i, mod in enumerate(self.desiredModifiers):
            if mod.MODIFIER_ENUM == modifierEnum:
                self.desiredModifiers.pop(i)
                break
        
        if removedMod:
            # Rebuild ruleset from scratch without the removed modifier (only if it was a crane-specific modifier)
            if hasattr(CraneGameGlobals, 'CFORulesetModifierBase') and isinstance(removedMod, CraneGameGlobals.CFORulesetModifierBase):
                self._rebuildRuleset()
            # For generic modifiers, just update clients
            else:
                self.d_setModifiers()
            # Save to group if available
            if hasattr(self.game, 'saveStateToGroup'):
                self.game.saveStateToGroup()
        else:
            self.game.notify.warning(f"Modifier {modifierEnum} not found to remove")
    
    def addModifier(self, modifierEnum, tier=1):
        """
        Handle request to add a modifier from the client.
        Supports both crane-specific and generic modifiers.
        """
        # Only allow the leader to add modifiers
        avId = self.game.air.getAvatarIdFromSender()
        if not self.game.hasHost() or avId != self.game.getHost():
            self.game.notify.warning(f"Non-leader {avId} attempted to add modifier")
            return
        
        # Check if modifier already exists
        for mod in self.modifiers:
            if mod.MODIFIER_ENUM == modifierEnum:
                self.game.notify.warning(f"Modifier {modifierEnum} already exists")
                return
        
        # Use crane-specific modifiers
        if modifierEnum in CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES:
            modifierClass = CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES[modifierEnum]
            modifier = modifierClass(tier)
        else:
            self.game.notify.warning(f"Unknown modifier enum: {modifierEnum}")
            return
        
        # Add to desired modifiers so it persists across game restarts
        self.desiredModifiers.append(modifier)
        
        self.applyModifier(modifier, updateClient=True)
        # saveStateToGroup is called inside applyModifier when updateClient=True
    
    def _rebuildRuleset(self):
        """Rebuild the ruleset from scratch with current modifiers"""
        # Reset to base ruleset
        self.game.ruleset = CraneGameGlobals.CraneGameRuleset()
        
        # Reapply all remaining modifiers
        for modifier in self.modifiers:
            # Only apply crane-specific modifiers to ruleset
            if hasattr(CraneGameGlobals, 'CFORulesetModifierBase') and isinstance(modifier, CraneGameGlobals.CFORulesetModifierBase):
                modifier.apply(self.game.ruleset)
            # Generic modifiers are applied to the game, not the ruleset
            else:
                modifier.apply(self.game)
        
        # Only validate if we have crane-specific modifiers
        hasCraneModifiers = any(hasattr(CraneGameGlobals, 'CFORulesetModifierBase') and isinstance(m, CraneGameGlobals.CFORulesetModifierBase) for m in self.modifiers)
        if hasCraneModifiers:
            self.game.ruleset.validate()
        
        # Update clients
        self.d_setRawRuleset()
        self.d_setModifiers()
        
        # Update boss if it exists
        if self.game.getBoss() is not None:
            self.game.getBoss().setRuleset(self.game.ruleset)
    
    def rollRandomModifiers(self):
        """Roll random modifiers based on configuration"""
        tierLeftBound = self.game.ruleset.MODIFIER_TIER_RANGE[0]
        tierRightBound = self.game.ruleset.MODIFIER_TIER_RANGE[1]
        pool: list[CraneGameGlobals.CFORulesetModifierBase] = [
            c(random.randint(tierLeftBound, tierRightBound)) 
            for c in CraneGameGlobals.NON_SPECIAL_MODIFIER_CLASSES
        ]
        
        alreadyApplied = [mod.MODIFIER_ENUM for mod in self.desiredModifiers]
        for choice in list(pool):
            if choice.MODIFIER_ENUM in alreadyApplied:
                pool.remove(choice)
        
        if len(pool) <= 0:
            return []
        
        random.shuffle(pool)
        
        modifiers = [pool.pop() for _ in range(self.numModsWanted)]
        
        # If we roll a % roll, go ahead and make this a special cfo
        # Doing this last also ensures any rules that the special mod needs to set override
        if random.randint(0, 99) < CraneGameGlobals.SPECIAL_MODIFIER_CHANCE:
            cls = random.choice(CraneGameGlobals.SPECIAL_MODIFIER_CLASSES)
            tier = random.randint(tierLeftBound, tierRightBound)
            mod_instance = cls(tier)
            modifiers.append(mod_instance)
        
        return modifiers
    
    def d_setRawRuleset(self):
        """Send raw ruleset to clients"""
        self.game.sendUpdate('setRawRuleset', [self.getRawRuleset()])
    
    def getRawRuleset(self):
        """Get raw ruleset struct for transmission"""
        return self.game.ruleset.asStruct()
    
    def setupRulesetFromStruct(self, rulesetStruct):
        """
        Restore ruleset from a struct (e.g., from group config).
        This is used when creating a minigame from group data.
        """
        self.game.ruleset = CraneGameGlobals.CraneGameRuleset.fromStruct(rulesetStruct)
        self.modifiers.clear()
        
        # Update boss if it exists
        if self.game.getBoss() is not None:
            self.game.getBoss().setRuleset(self.game.ruleset)
        
        # Update clients
        self.d_setRawRuleset()
    
    def applyModifiersFromStructs(self, modifierStructs):
        """
        Restore modifiers from structs (e.g., from group config).
        This is used when creating a minigame from group data.
        Supports both crane-specific and generic modifiers.
        """
        modifiers = []
        for modStruct in modifierStructs:
            modifierEnum = modStruct[0] if isinstance(modStruct, (list, tuple)) else modStruct
            
            # Deserialize as crane-specific modifier
            try:
                modifier = CraneGameGlobals.CFORulesetModifierBase.fromStruct(modStruct)
            except Exception as e:
                self.game.notify.warning(f"Failed to deserialize modifier {modStruct}: {e}")
                continue
            
            modifiers.append(modifier)
            # Also add to desired modifiers so they persist
            # Check by enum to avoid duplicates
            if not any(m.MODIFIER_ENUM == modifier.MODIFIER_ENUM for m in self.desiredModifiers):
                self.desiredModifiers.append(modifier)
        
        # Apply all modifiers (don't update client yet - that happens in setupRuleset)
        # We'll update client after everything is set up
        for modifier in modifiers:
            self.modifiers.append(modifier)
            # Apply crane-specific modifiers to ruleset
            modifier.apply(self.game.ruleset)
        
        # Validate ruleset
        self.game.ruleset.validate()
        
        # Mark that we've initialized defaults so they don't get added again
        if len(self.game.getParticipantsNotSpectating()) >= 2:
            self.defaultModifiersInitialized = True
        
        # Update clients
        self.d_setRawRuleset()
        self.d_setModifiers()

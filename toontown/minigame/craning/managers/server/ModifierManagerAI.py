"""
ModifierManagerAI - Handles ruleset and modifier management.
"""

import random
from toontown.minigame.craning import CraneGameGlobals


class ModifierManagerAI:
    """Manages ruleset and modifier application/removal."""
    
    def __init__(self, game):
        self.game = game
        self.modifiers = []  # A list of CFORulesetModifierBase instances
        self.desiredModifiers = []  # Modifiers added manually via commands or by the host during game settings. Will always ensure these are added every crane round.
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
            
            # If we have saved state, restore it instead of creating defaults
            if rulesetStruct is not None:
                self.setupRulesetFromStruct(rulesetStruct)
                if modifierStructs:
                    self.applyModifiersFromStructs(modifierStructs)
                # Save again to ensure it's up to date
                if hasattr(self.game, 'saveStateToGroup'):
                    self.game.saveStateToGroup()
                return
        
        # No saved state - create fresh ruleset with defaults
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
    
    def applyModifiers(self, modifiers: list[CraneGameGlobals.CFORulesetModifierBase], updateClient=False):
        """
        Call to update the ruleset with the modifiers active, note calling more than once can cause unexpected behavior
        if the ruleset doesn't fallback to an initial value, for example if a cfo hp increasing modifier is active and we
        call this multiply times, his hp will be 1500 * 1.5 * 1.5 * 1.5 etc etc
        """
        for modifier in modifiers:
            self.applyModifier(modifier, updateClient=False)
        if updateClient:
            self.d_setRawRuleset()
            self.d_setModifiers()
    
    def applyModifier(self, modifier: CraneGameGlobals.CFORulesetModifierBase, updateClient=False):
        """Apply a single modifier to the ruleset"""
        self.modifiers.append(modifier)
        modifier.apply(self.game.ruleset)
        self.game.ruleset.validate()
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
            # Rebuild ruleset from scratch without the removed modifier
            self._rebuildRuleset()
            # Save to group if available
            if hasattr(self.game, 'saveStateToGroup'):
                self.game.saveStateToGroup()
        else:
            self.game.notify.warning(f"Modifier {modifierEnum} not found to remove")
    
    def addModifier(self, modifierEnum, tier=1):
        """Handle request to add a modifier from the client"""
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
        
        # Get the modifier class and create instance
        if modifierEnum in CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES:
            modifierClass = CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES[modifierEnum]
            modifier = modifierClass(tier)
            
            # Add to desired modifiers so it persists across game restarts
            self.desiredModifiers.append(modifier)
            
            self.applyModifier(modifier, updateClient=True)
            # saveStateToGroup is called inside applyModifier when updateClient=True
        else:
            self.game.notify.warning(f"Unknown modifier enum: {modifierEnum}")
    
    def _rebuildRuleset(self):
        """Rebuild the ruleset from scratch with current modifiers"""
        # Reset to base ruleset
        self.game.ruleset = CraneGameGlobals.CraneGameRuleset()
        
        # Reapply all remaining modifiers
        for modifier in self.modifiers:
            modifier.apply(self.game.ruleset)
        
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
    
    def _getRawModifierList(self):
        """Get list of modifier structs for transmission"""
        mods = []
        for modifier in self.modifiers:
            mods.append(modifier.asStruct())
        return mods
    
    def d_setModifiers(self):
        """Send modifiers to clients"""
        self.game.sendUpdate('setModifiers', [self._getRawModifierList()])
    
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
        """
        modifiers = []
        for modStruct in modifierStructs:
            modifier = CraneGameGlobals.CFORulesetModifierBase.fromStruct(modStruct)
            modifiers.append(modifier)
            # Also add to desired modifiers so they persist
            # Check by enum to avoid duplicates
            if not any(m.MODIFIER_ENUM == modifier.MODIFIER_ENUM for m in self.desiredModifiers):
                self.desiredModifiers.append(modifier)
        
        # Apply all modifiers (don't update client yet - that happens in setupRuleset)
        # We'll update client after everything is set up
        for modifier in modifiers:
            self.modifiers.append(modifier)
            modifier.apply(self.game.ruleset)
        
        self.game.ruleset.validate()
        
        # Mark that we've initialized defaults so they don't get added again
        if len(self.game.getParticipantsNotSpectating()) >= 2:
            self.defaultModifiersInitialized = True
        
        # Update clients
        self.d_setRawRuleset()
        self.d_setModifiers()

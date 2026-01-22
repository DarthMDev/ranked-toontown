"""
ModifierManagerAI - Base modifier manager for all minigames.
Each minigame can have their own modifier manager that inherits from this.
"""


class ModifierManagerAI:
    """Base class for managing modifiers in any minigame."""
    
    def __init__(self, game):
        self.game = game
        self.modifiers = []  # A list of modifier instances (minigame-specific)
        self.desiredModifiers = []  # Modifiers added manually via commands or by the host during game settings
    
    def applyModifiers(self, modifiers, updateClient=False):
        """
        Apply multiple modifiers to the game.
        """
        for modifier in modifiers:
            self.applyModifier(modifier, updateClient=False)
        if updateClient:
            self.d_setModifiers()
            # Save to group if available
            if hasattr(self.game, 'saveStateToGroup'):
                self.game.saveStateToGroup()
    
    def applyModifier(self, modifier, updateClient=False):
        """Apply a single modifier to the game"""
        self.modifiers.append(modifier)
        modifier.apply(self.game)
        if updateClient:
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
            # Save to group if available
            if hasattr(self.game, 'saveStateToGroup'):
                self.game.saveStateToGroup()
            self.d_setModifiers()
        else:
            self.game.notify.warning(f"Modifier {modifierEnum} not found to remove")
    
    def addModifier(self, modifierEnum, tier=1):
        """
        Handle request to add a modifier from the client.
        Tries to find the appropriate ModifierBase for this minigame.
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
        
        # Try to find the ModifierBase for this minigame
        modifierBase = self._getModifierBaseForMinigame()
        if modifierBase and hasattr(modifierBase, 'MODIFIER_SUBCLASSES'):
            if modifierEnum in modifierBase.MODIFIER_SUBCLASSES:
                modifierClass = modifierBase.MODIFIER_SUBCLASSES[modifierEnum]
                modifier = modifierClass(tier)
                
                # Add to desired modifiers so it persists across game restarts
                self.desiredModifiers.append(modifier)
                
                self.applyModifier(modifier, updateClient=True)
                return
        
        self.game.notify.warning(f"Unknown modifier enum: {modifierEnum} for minigame {self.game.minigameId}")
    
    def _getModifierBaseForMinigame(self):
        """Get the ModifierBase class for this minigame"""
        from toontown.toonbase import ToontownGlobals
        
        minigameId = self.game.minigameId
        if minigameId == ToontownGlobals.CraneGameId:
            from toontown.minigame.craning import CraneGameGlobals
            return CraneGameGlobals.CFORulesetModifierBase
        elif minigameId == ToontownGlobals.PieGameId:
            from toontown.minigame.pie import PieGameGlobals
            return PieGameGlobals.PieGameModifierBase
        elif minigameId == ToontownGlobals.ScaleGameId:
            from toontown.minigame.scale import ScaleGameGlobals
            return ScaleGameGlobals.ScaleGameModifierBase
        elif minigameId == ToontownGlobals.SeltzerGameId:
            from toontown.minigame.seltzer import SeltzerGameGlobals
            return SeltzerGameGlobals.SeltzerGameModifierBase
        elif minigameId == ToontownGlobals.GolfGreenGameId:
            from toontown.minigame.golfgreen import GolfGreenGlobals
            return GolfGreenGlobals.GolfGreenGameModifierBase
        
        return None
    
    def _getRawModifierList(self):
        """Get list of modifier structs for transmission"""
        mods = []
        for modifier in self.modifiers:
            mods.append(modifier.asStruct())
        return mods
    
    def d_setModifiers(self):
        """Send modifiers to clients"""
        self.game.sendUpdate('setModifiers', [self._getRawModifierList()])
    
    def applyModifiersFromStructs(self, modifierStructs):
        """
        Restore modifiers from structs (e.g., from group config).
        This is used when creating a minigame from group data.
        Tries to find the appropriate ModifierBase for this minigame.
        """
        modifierBase = self._getModifierBaseForMinigame()
        if not modifierBase or not hasattr(modifierBase, 'fromStruct'):
            self.game.notify.warning(f"applyModifiersFromStructs: No ModifierBase found for minigame {self.game.minigameId}")
            return
        
        modifiers = []
        for modStruct in modifierStructs:
            try:
                modifier = modifierBase.fromStruct(modStruct)
                modifiers.append(modifier)
                # Also add to desired modifiers so they persist
                # Check by enum to avoid duplicates
                if not any(m.MODIFIER_ENUM == modifier.MODIFIER_ENUM for m in self.desiredModifiers):
                    self.desiredModifiers.append(modifier)
            except Exception as e:
                self.game.notify.warning(f"Failed to deserialize modifier {modStruct}: {e}")
        
        # Apply all modifiers
        for modifier in modifiers:
            self.modifiers.append(modifier)
            modifier.apply(self.game)
        
        # Update clients
        self.d_setModifiers()

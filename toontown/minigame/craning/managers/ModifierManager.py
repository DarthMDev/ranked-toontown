"""
ModifierManager - Handles client-side modifier UI and state.
"""

from toontown.minigame.craning import CraneGameGlobals


class ModifierManager:
    """Manages client-side modifier UI and state."""
    
    def __init__(self, game):
        self.game = game
        self.modifiers = []
        self.modifiersPanel = None
        self.modifiersPanelVisible = False
        self.modifiersButton = None
        self.currentModifiersList = None
        self.availableModifiersList = None
        self.modifierConfigDialog = None
    
    def setModifiers(self, mods):
        """Receive modifier updates from the server"""
        modsToSet = []  # A list of CFORulesetModifierBase subclass instances
        for modStruct in mods:
            modsToSet.append(CraneGameGlobals.CFORulesetModifierBase.fromStruct(modStruct))

        self.modifiers = modsToSet
        self.modifiers.sort(key=lambda m: m.MODIFIER_TYPE)
        
        # Update heat display if available
        if hasattr(self.game, 'heatDisplay'):
            self.game.heatDisplay.update(self.modifiers)
        
        # Update the modifiers panel if it's visible
        if hasattr(self.game, 'modifierPanelUI') and self.game.modifierPanelUI.modifiersPanelVisible:
            self.game.modifierPanelUI.updateLists()
    
    def _updateModifiersLists(self):
        """Update the modifiers lists with current and available modifiers"""
        # Delegate to UI class
        if hasattr(self.game, 'modifierPanelUI'):
            self.game.modifierPanelUI.updateLists()

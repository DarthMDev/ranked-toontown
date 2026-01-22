"""
GroupModifierPanelUI - Generic modifier panel UI for all minigames in the group interface.
Based on the crane game's ModifierPanelUI but works with the generic modifier system.
"""

from direct.directnotify import DirectNotifyGlobal
from direct.gui.DirectGui import DGG, DirectFrame, DirectLabel, DirectButton, DirectScrolledList
from direct.showbase.ShowBaseGlobal import aspect2d, base
from panda3d.core import TextNode, Vec4
from toontown.toonbase import ToontownGlobals
from toontown.minigame.craning import CraneGameGlobals


class GroupModifierPanelUI:
    """Manages the modifier panel UI for group minigame configuration."""
    
    Notify = DirectNotifyGlobal.directNotify.newCategory('GroupModifierPanelUI')
    
    def __init__(self, groupManager):
        self.groupManager = groupManager
        
        # UI elements
        self.modifiersPanel = None
        self.currentModifiersList = None
        self.availableModifiersList = None
        self.modifierConfigDialog = None
        self.modifiersPanelVisible = False
        
        # Current modifiers (loaded from group config)
        self.currentModifiers = []
    
    def createPanel(self):
        """Create the modifiers management panel"""
        if self.modifiersPanel is not None:
            return  # Already created
        
        # Create the main panel frame using proper dialog styling
        # Center it on screen - all child elements are positioned relative to this
        self.modifiersPanel = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(1.6, 1, 1.4),
            pos=(0, 0, 0),  # Centered - this is the key! All child elements are relative to this
            parent=aspect2d,
            sortOrder=DGG.NO_FADE_SORT_INDEX
        )
        
        # Title label
        titleLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Manage Modifiers",
            text_scale=0.08,
            text_pos=(0, 0.55),
            text_fg=(0.1, 0.1, 0.4, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Instructions label
        instructionsLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Add and remove modifiers for the game",
            text_scale=0.05,
            text_pos=(0, 0.45),
            text_fg=(0.3, 0.3, 0.3, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Load GUI assets for scroll list
        gui = base.loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        
        # Current modifiers section
        currentModsLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Current Modifiers:",
            text_scale=0.06,
            text_pos=(-0.75, 0.3),
            text_fg=(0.2, 0.2, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            text_align=TextNode.ALeft
        )
        
        # Create scrolled list for current modifiers
        self.currentModifiersList = DirectScrolledList(
            parent=self.modifiersPanel,
            relief=DGG.SUNKEN,
            frameColor=(0.85, 0.95, 1, 1),
            borderWidth=(0.01, 0.01),
            pos=(-0.35, 0, 0.2),
            frameSize=(-0.4, 0.2, -0.24, 0.0),
            numItemsVisible=4,
            forceHeight=0.06,
            itemFrame_frameSize=(-0.38, 0.38, -0.03, 0.03),
            itemFrame_pos=(0, 0, -0.032),
            itemFrame_relief=None,
            incButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            incButton_relief=None,
            incButton_scale=(0.3, 0.3, -1.1),
            incButton_pos=(0.15, 0, -0.26),
            incButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6),
            decButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            decButton_relief=None,
            decButton_scale=(0.3, 0.3, 1.1),
            decButton_pos=(0.15, 0, 0.24),
            decButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6)
        )
        
        # Available modifiers section
        availableModsLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Available Modifiers:",
            text_scale=0.06,
            text_pos=(0.1, 0.3),  # Fixed: was 0.25, should be 0.1 to match original
            text_fg=(0.2, 0.2, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            text_align=TextNode.ALeft
        )
        
        # Create scrolled list for available modifiers
        self.availableModifiersList = DirectScrolledList(
            parent=self.modifiersPanel,
            relief=DGG.SUNKEN,
            frameColor=(0.85, 0.95, 1, 1),
            borderWidth=(0.01, 0.01),
            pos=(0.5, 0, 0.2),  # Fixed: was 0.35, should be 0.5 to match original
            frameSize=(-0.4, 0.2, -0.24, 0.0),  # Fixed: was (-0.2, 0.4, ...), should be (-0.4, 0.2, ...) to match original
            numItemsVisible=4,
            forceHeight=0.06,
            itemFrame_frameSize=(-0.38, 0.38, -0.03, 0.03),
            itemFrame_pos=(0, 0, -0.032),
            itemFrame_relief=None,
            incButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            incButton_relief=None,
            incButton_scale=(0.3, 0.3, -1.1),
            incButton_pos=(0.15, 0, -0.26),
            incButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6),
            decButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            decButton_relief=None,
            decButton_scale=(0.3, 0.3, 1.1),
            decButton_pos=(0.15, 0, 0.24),
            decButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6)
        )
        
        # Close button
        buttons = base.loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        closeButtonImage = (buttons.find('**/CloseBtn_UP'), 
                          buttons.find('**/CloseBtn_DN'), 
                          buttons.find('**/CloseBtn_Rllvr'))
        
        closeButton = DirectButton(
            parent=self.modifiersPanel,
            relief=None,
            image=closeButtonImage,
            text="Close",
            text_scale=0.05,
            text_pos=(0, -0.1),
            pos=(0, 0, -0.5),
            command=self.hidePanel
        )
        
        # Clean up
        gui.removeNode()
        buttons.removeNode()
        
        # Load current modifiers from group config
        self.loadModifiersFromGroup()
        
        # Update lists
        self.updateLists()
    
    def loadModifiersFromGroup(self):
        """Load current modifiers from group config"""
        if not self.groupManager.isInGroup():
            self.currentModifiers = []
            return
        
        # Request modifiers from server
        minigameId = self.groupManager.minigameType
        self.groupManager.d_requestGetModifiers(minigameId)
        
        # Modifiers will be set via setModifiers callback
        # For now, keep current modifiers (they'll be updated when server responds)
    
    def saveModifiersToGroup(self):
        """Save current modifiers to group config"""
        if not self.groupManager.isInGroup():
            return
        
        # Only leader can save
        if self.groupManager.getLeader() != base.localAvatar.getDoId():
            return
        
        minigameId = self.groupManager.minigameType
        
        # Convert modifiers to structs (Astron will automatically convert to MinigameModifier[] struct array)
        modifierStructs = [mod.asStruct() for mod in self.currentModifiers]
        
        # Request server to save modifiers (Astron handles struct array serialization)
        self.groupManager.d_requestSetModifiers(minigameId, modifierStructs)
    
    def updateLists(self):
        """Update the current and available modifiers lists"""
        if not self.modifiersPanel:
            return
        
        # Clear existing items
        self.currentModifiersList.removeAllItems()
        self.availableModifiersList.removeAllItems()
        
        # Load button assets
        gui = base.loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        addButtonImage = (gui.find('**/Horiz_Arrow_UP'),
                         gui.find('**/Horiz_Arrow_DN'),
                         gui.find('**/Horiz_Arrow_Rllvr'),
                         gui.find('**/Horiz_Arrow_UP'))
        removeButtonImage = (gui.find('**/Horiz_Arrow_UP'),
                           gui.find('**/Horiz_Arrow_DN'),
                           gui.find('**/Horiz_Arrow_Rllvr'),
                           gui.find('**/Horiz_Arrow_UP'))
        
        # Populate current modifiers list
        for i, mod in enumerate(self.currentModifiers):
            itemFrame = DirectFrame(
                relief=None,
                frameSize=(-0.38, 0.38, -0.03, 0.03)
            )
            
            nameLabel = DirectLabel(
                parent=itemFrame,
                relief=None,
                text=mod.getName(),
                text_scale=0.025,
                text_pos=(-0.35, 0, 0),
                text_fg=mod.TITLE_COLOR,
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            removeButton = DirectButton(
                parent=itemFrame,
                relief=None,
                image=removeButtonImage,
                image_scale=(0.3, 1, 0.3),
                image_hpr=(0, 0, 180),
                pos=(0.17, 0, 0),
                command=self._onRemoveModifier,
                extraArgs=[i]
            )
            
            self.currentModifiersList.addItem(itemFrame)
        
        # Get available modifiers based on current minigame
        currentModEnums = [mod.MODIFIER_ENUM for mod in self.currentModifiers]
        availableModClasses = []
        
        minigameId = self.groupManager.minigameType
        
        # Get the appropriate ModifierBase for this minigame
        modifierBase = None
        if minigameId == ToontownGlobals.CraneGameId:
            modifierBase = CraneGameGlobals.CFORulesetModifierBase
        elif minigameId == ToontownGlobals.PieGameId:
            from toontown.minigame.pie import PieGameGlobals
            modifierBase = PieGameGlobals.PieGameModifierBase
        elif minigameId == ToontownGlobals.ScaleGameId:
            from toontown.minigame.scale import ScaleGameGlobals
            modifierBase = ScaleGameGlobals.ScaleGameModifierBase
        elif minigameId == ToontownGlobals.SeltzerGameId:
            from toontown.minigame.seltzer import SeltzerGameGlobals
            modifierBase = SeltzerGameGlobals.SeltzerGameModifierBase
        elif minigameId == ToontownGlobals.GolfGreenGameId:
            from toontown.minigame.golfgreen import GolfGreenGlobals
            modifierBase = GolfGreenGlobals.GolfGreenGameModifierBase
        
        # Add modifiers from the appropriate ModifierBase
        if modifierBase and hasattr(modifierBase, 'MODIFIER_SUBCLASSES'):
            for modEnum, modClass in modifierBase.MODIFIER_SUBCLASSES.items():
                if modEnum not in currentModEnums:
                    availableModClasses.append((modEnum, modClass, 'minigame'))
        
        # Sort by type
        availableModClasses.sort(key=lambda x: (x[1].MODIFIER_TYPE, x[0]))
        
        # Populate available modifiers list
        for modEnum, modClass, modType in availableModClasses:
            mod = modClass()  # Create instance for display
            
            itemFrame = DirectFrame(
                relief=None,
                frameSize=(-0.38, 0.38, -0.03, 0.03)
            )
            
            nameLabel = DirectLabel(
                parent=itemFrame,
                relief=None,
                text=mod.getName(),
                text_scale=0.025,
                text_pos=(-0.35, 0, 0),
                text_fg=mod.TITLE_COLOR,
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            addButton = DirectButton(
                parent=itemFrame,
                relief=None,
                image=addButtonImage,
                image_scale=(0.3, 1, 0.3),
                pos=(0.17, 0, 0),
                command=self._onAddModifier,
                extraArgs=[modEnum]  # Don't pass modType - determine it from minigame
            )
            
            self.availableModifiersList.addItem(itemFrame)
        
        gui.removeNode()
    
    def _onAddModifier(self, modifierEnum):
        """Handle adding a modifier"""
        # Only leader can add modifiers
        if self.groupManager.getLeader() != base.localAvatar.getDoId():
            return
        
        # Check if modifier needs configuration
        # For crane game, check if it's First to X Wins (enum 39) or other configurable modifiers
        minigameId = self.groupManager.minigameType
        needsConfig = False
        
        if minigameId == ToontownGlobals.CraneGameId:
            # Crane game: First to X Wins is enum 39, Timer Enabler is 27, etc.
            if modifierEnum == 39:  # ModifierFirstToXWins
                needsConfig = True
            elif modifierEnum == 27:  # ModifierTimerEnabler
                needsConfig = True
            elif modifierEnum in [2, 3]:  # HP modifiers
                needsConfig = True
            elif modifierEnum in [0, 1]:  # Combo modifiers
                needsConfig = True
            elif modifierEnum == 29:  # ModifierLaffDrain
                needsConfig = True
        else:
            # Other minigames: First to X Wins is enum 0
            if modifierEnum == 0:  # ModifierFirstToXWins
                needsConfig = True
        
        if needsConfig:
            self.showConfigDialog(modifierEnum)
        else:
            # Add with default tier
            self._addModifier(modifierEnum, tier=1)
    
    def _addModifier(self, modifierEnum, tier=1):
        """Actually add the modifier"""
        try:
            minigameId = self.groupManager.minigameType
            
            # Get the appropriate ModifierBase for this minigame
            modifierBase = None
            if minigameId == ToontownGlobals.CraneGameId:
                modifierBase = CraneGameGlobals.CFORulesetModifierBase
            elif minigameId == ToontownGlobals.PieGameId:
                from toontown.minigame.pie import PieGameGlobals
                modifierBase = PieGameGlobals.PieGameModifierBase
            elif minigameId == ToontownGlobals.ScaleGameId:
                from toontown.minigame.scale import ScaleGameGlobals
                modifierBase = ScaleGameGlobals.ScaleGameModifierBase
            elif minigameId == ToontownGlobals.SeltzerGameId:
                from toontown.minigame.seltzer import SeltzerGameGlobals
                modifierBase = SeltzerGameGlobals.SeltzerGameModifierBase
            elif minigameId == ToontownGlobals.GolfGreenGameId:
                from toontown.minigame.golfgreen import GolfGreenGlobals
                modifierBase = GolfGreenGlobals.GolfGreenGameModifierBase
            
            if modifierBase and hasattr(modifierBase, 'MODIFIER_SUBCLASSES'):
                modifierClass = modifierBase.MODIFIER_SUBCLASSES.get(modifierEnum)
                if modifierClass:
                    modifier = modifierClass(tier)
                    self.currentModifiers.append(modifier)
                    self.Notify.debug(f"Added modifier {modifier.getName()} (enum {modifierEnum}, tier {tier})")
                    # Update UI immediately for responsive feedback
                    self.updateLists()
                    # Then save to server (which will broadcast back to all clients)
                    self.saveModifiersToGroup()
        except Exception as e:
            print(f"Error adding modifier: {e}")
            import traceback
            traceback.print_exc()
    
    def _onRemoveModifier(self, index):
        """Handle removing a modifier"""
        # Only leader can remove modifiers
        if self.groupManager.getLeader() != base.localAvatar.getDoId():
            return
        
        if 0 <= index < len(self.currentModifiers):
            # Remove by index - but we need to be careful about the index
            # The index is from the UI list, which should match currentModifiers
            removed = self.currentModifiers.pop(index)
            self.Notify.debug(f"Removed modifier {removed.getName()} at index {index}")
            # Update UI immediately
            self.updateLists()
            # Then save to server
            self.saveModifiersToGroup()
    
    def showConfigDialog(self, modifierEnum):
        """Show configuration dialog for a modifier"""
        # Hide the modifiers panel temporarily
        if self.modifiersPanel:
            self.modifiersPanel.hide()
        
        minigameId = self.groupManager.minigameType
        
        # Get the appropriate ModifierBase for this minigame
        modifierBase = None
        if minigameId == ToontownGlobals.CraneGameId:
            modifierBase = CraneGameGlobals.CFORulesetModifierBase
        elif minigameId == ToontownGlobals.PieGameId:
            from toontown.minigame.pie import PieGameGlobals
            modifierBase = PieGameGlobals.PieGameModifierBase
        elif minigameId == ToontownGlobals.ScaleGameId:
            from toontown.minigame.scale import ScaleGameGlobals
            modifierBase = ScaleGameGlobals.ScaleGameModifierBase
        elif minigameId == ToontownGlobals.SeltzerGameId:
            from toontown.minigame.seltzer import SeltzerGameGlobals
            modifierBase = SeltzerGameGlobals.SeltzerGameModifierBase
        elif minigameId == ToontownGlobals.GolfGreenGameId:
            from toontown.minigame.golfgreen import GolfGreenGlobals
            modifierBase = GolfGreenGlobals.GolfGreenGameModifierBase
        
        if modifierBase and hasattr(modifierBase, 'MODIFIER_SUBCLASSES'):
            modifierClass = modifierBase.MODIFIER_SUBCLASSES.get(modifierEnum)
        else:
            modifierClass = None
        
        if not modifierClass:
            return
        
        sampleMod = modifierClass()
        
        # Create configuration dialog - make it wider for two-column layout
        self.modifierConfigDialog = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(1.8, 1, 1.4),  # Made wider for two columns
            pos=(0, 0, 0),
            parent=aspect2d,
            sortOrder=DGG.NO_FADE_SORT_INDEX + 1
        )
        
        # Title
        titleLabel = DirectLabel(
            parent=self.modifierConfigDialog,
            relief=None,
            text=f"Configure {sampleMod.getName()}",
            text_scale=0.07,
            text_pos=(0, 0.55),
            text_fg=sampleMod.TITLE_COLOR,
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Instructions
        instructionsLabel = DirectLabel(
            parent=self.modifierConfigDialog,
            relief=None,
            text="Choose the intensity/duration:",
            text_scale=0.05,
            text_pos=(0, 0.45),
            text_fg=(0.3, 0.3, 0.3, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Load button assets
        buttons = base.loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        buttonImage = (buttons.find('**/ChtBx_OKBtn_UP'), 
                      buttons.find('**/ChtBx_OKBtn_DN'), 
                      buttons.find('**/ChtBx_OKBtn_Rllvr'))
        cancelButtonImage = (buttons.find('**/CloseBtn_UP'), 
                          buttons.find('**/CloseBtn_DN'), 
                          buttons.find('**/CloseBtn_Rllvr'))
        
        # Create tier selection options based on modifier type
        self._createTierOptions(modifierEnum, modifierClass, buttonImage)
        
        # Cancel button
        cancelButton = DirectButton(
            parent=self.modifierConfigDialog,
            relief=None,
            image=cancelButtonImage,
            text="Cancel",
            text_scale=0.05,
            text_pos=(0, -0.1),
            pos=(0, 0, -0.5),
            command=self.cancelConfig
        )
        
        buttons.removeNode()
    
    def _createTierOptions(self, modifierEnum, modifierClass, buttonImage):
        """Create tier selection options with two-column layout"""
        minigameId = self.groupManager.minigameType
        
        # Special handling for different modifier types
        if minigameId == ToontownGlobals.CraneGameId:
            # Crane game specific modifiers
            if modifierEnum == 27:  # ModifierTimerEnabler (Margin Call)
                self._createTimeSelectionOptions(modifierEnum, buttonImage)
            elif modifierEnum == 39:  # ModifierFirstToXWins
                self._createFirstToXWinsOptions(modifierEnum, buttonImage)
            elif modifierEnum in [2, 3]:  # HP modifiers
                self._createPercentageOptions(modifierEnum, modifierClass, buttonImage, "HP")
            elif modifierEnum in [0, 1]:  # Combo modifiers
                self._createPercentageOptions(modifierEnum, modifierClass, buttonImage, "Combo Duration")
            elif modifierEnum == 29:  # ModifierLaffDrain (Leaky Laff)
                self._createLaffDrainOptions(modifierEnum, buttonImage)
            else:
                # Generic tier options (1-5)
                self._createGenericTierOptions(modifierEnum, modifierClass, buttonImage)
        else:
            # Other minigames: only First to X Wins (enum 0) needs config
            if modifierEnum == 0:  # ModifierFirstToXWins
                self._createFirstToXWinsOptions(modifierEnum, buttonImage)
            else:
                # Generic tier options (1-5)
                self._createGenericTierOptions(modifierEnum, modifierClass, buttonImage)
    
    def _createTimeSelectionOptions(self, modifierEnum, buttonImage):
        """Create time selection options for Margin Call modifier"""
        timeOptions = [
            (1, "1 minute"),
            (2, "2 minutes"), 
            (3, "3 minutes"),
            (5, "5 minutes"),
            (10, "10 minutes")
        ]
        
        startY = 0.3
        for i, (tier, label) in enumerate(timeOptions):
            currentY = startY - i * 0.08
            
            # Description label on the left
            descLabel = DirectLabel(
                parent=self.modifierConfigDialog,
                relief=None,
                text=label,
                text_scale=0.045,
                text_pos=(-0.35, currentY),
                text_fg=(0.2, 0.2, 0.2, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Selection button on the right
            selectButton = DirectButton(
                parent=self.modifierConfigDialog,
                relief=None,
                image=buttonImage,
                pos=(0.4, 0, currentY+0.015),
                scale=(0.7, 1, 0.7),
                command=self._onConfirmConfig,
                extraArgs=[modifierEnum, tier]
            )
    
    def _createFirstToXWinsOptions(self, modifierEnum, buttonImage):
        """Create First to X Wins selection options"""
        # Allow selecting from 1 to 10 wins
        winOptions = [
            (1, "First to 1 Win (BO1)"),
            (2, "First to 2 Wins (BO3)"),
            (3, "First to 3 Wins (BO5)"),
            (4, "First to 4 Wins (BO7)"),
            (5, "First to 5 Wins (BO9)")
        ]
        
        startY = 0.35
        for i, (wins, label) in enumerate(winOptions):
            currentY = startY - i * 0.07
            
            # Description label on the left
            descLabel = DirectLabel(
                parent=self.modifierConfigDialog,
                relief=None,
                text=label,
                text_scale=0.04,
                text_pos=(-0.35, currentY),
                text_fg=(0.2, 0.2, 0.2, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Selection button on the right
            selectButton = DirectButton(
                parent=self.modifierConfigDialog,
                relief=None,
                image=buttonImage,
                pos=(0.4, 0, currentY+0.015),
                scale=(0.7, 1, 0.7),
                command=self._onConfirmConfig,
                extraArgs=[modifierEnum, wins]
            )
    
    def _createPercentageOptions(self, modifierEnum, modifierClass, buttonImage, statName):
        """Create percentage-based tier options"""
        
        # Create sample modifiers to get percentage values
        tiers = [1, 2, 3, 4, 5]
        startY = 0.3
        
        for i, tier in enumerate(tiers):
            try:
                sampleMod = modifierClass(tier)
                currentY = startY - i * 0.08
                
                # Get the percentage or value for display
                if hasattr(sampleMod, '_perc_increase'):
                    value = sampleMod._perc_increase()
                    description = f"Tier {tier}: +{value}% {statName}"
                elif hasattr(sampleMod, '_perc_decrease'):
                    value = sampleMod._perc_decrease()
                    description = f"Tier {tier}: -{value}% {statName}"
                elif hasattr(sampleMod, '_duration'):
                    value = sampleMod._duration()
                    description = f"Tier {tier}: +{value}% {statName}"
                else:
                    description = f"Tier {tier}"
                
                # Description label on the left
                descLabel = DirectLabel(
                    parent=self.modifierConfigDialog,
                    relief=None,
                    text=description,
                    text_scale=0.04,
                    text_pos=(-0.4, currentY),
                    text_fg=(0.2, 0.2, 0.2, 1),
                    text_font=ToontownGlobals.getInterfaceFont(),
                    text_align=TextNode.ALeft
                )
                
                # Selection button on the right
                selectButton = DirectButton(
                    parent=self.modifierConfigDialog,
                    relief=None,
                    image=buttonImage,
                    pos=(0.4, 0, currentY+0.015),
                    scale=(0.7, 1, 0.7),
                    command=self._onConfirmConfig,
                    extraArgs=[modifierEnum, tier]
                )
            except:
                # Fallback for tiers that might not work
                break
    
    def _createLaffDrainOptions(self, modifierEnum, buttonImage):
        """Create laff drain rate selection options"""
        drainOptions = [
            (1, "Every 1.0 seconds"),
            (2, "Every 1.0 seconds"),
            (3, "Every 0.75 seconds"),
            (4, "Every 0.5 seconds"),
            (5, "Every 0.25 seconds"),
            (6, "Every 0.1 seconds")
        ]
        
        startY = 0.3
        for i, (tier, label) in enumerate(drainOptions):
            currentY = startY - i * 0.08
            description = f"Tier {tier}: {label}"
            
            # Description label on the left
            descLabel = DirectLabel(
                parent=self.modifierConfigDialog,
                relief=None,
                text=description,
                text_scale=0.04,
                text_pos=(-0.4, currentY),
                text_fg=(0.2, 0.2, 0.2, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Selection button on the right
            selectButton = DirectButton(
                parent=self.modifierConfigDialog,
                relief=None,
                image=buttonImage,
                pos=(0.4, 0, currentY+0.015),
                scale=(0.7, 1, 0.7),
                command=self._onConfirmConfig,
                extraArgs=[modifierEnum, tier]
            )
    
    def _createGenericTierOptions(self, modifierEnum, modifierClass, buttonImage):
        """Create generic tier options (1-5)"""
        tiers = [1, 2, 3, 4, 5]
        startY = 0.3
        
        for i, tier in enumerate(tiers):
            currentY = startY - i * 0.08
            
            # Description label
            descLabel = DirectLabel(
                parent=self.modifierConfigDialog,
                relief=None,
                text=f"Tier {tier}",
                text_scale=0.04,
                text_pos=(-0.35, currentY),
                text_fg=(0.2, 0.2, 0.2, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Selection button
            selectButton = DirectButton(
                parent=self.modifierConfigDialog,
                relief=None,
                image=buttonImage,
                pos=(0.4, 0, currentY+0.015),
                scale=(0.7, 1, 0.7),
                command=self._onConfirmConfig,
                extraArgs=[modifierEnum, tier]
            )
    
    def _onConfirmConfig(self, modifierEnum, tier):
        """Handle confirming modifier configuration"""
        self.cancelConfig()
        self._addModifier(modifierEnum, tier)
    
    def cancelConfig(self):
        """Cancel configuration dialog"""
        if self.modifierConfigDialog:
            self.modifierConfigDialog.destroy()
            self.modifierConfigDialog = None
        if self.modifiersPanel:
            self.modifiersPanel.show()
    
    def showPanel(self):
        """Show the modifiers panel"""
        if not self.modifiersPanel:
            self.createPanel()
        
        # Show panel first so setModifiers can update the UI when it receives data
        self.modifiersPanel.show()
        self.modifiersPanelVisible = True
        
        # Reload modifiers from group (this will trigger setModifiers callback)
        self.loadModifiersFromGroup()
        
        # Update lists with current data (in case modifiers were already loaded)
        self.updateLists()
    
    def hidePanel(self):
        """Hide the modifiers panel"""
        if self.modifiersPanel:
            self.modifiersPanel.hide()
        self.modifiersPanelVisible = False
    
    def destroy(self):
        """Clean up the panel"""
        if self.modifierConfigDialog:
            self.modifierConfigDialog.destroy()
            self.modifierConfigDialog = None
        if self.modifiersPanel:
            self.modifiersPanel.destroy()
            self.modifiersPanel = None
        self.currentModifiers = []

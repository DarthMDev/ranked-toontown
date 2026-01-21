"""
ModifierPanelUI - Handles all UI for the modifier management panel.
"""

from direct.gui.DirectGui import DGG, DirectFrame, DirectLabel, DirectButton, DirectScrolledList
from direct.showbase.ShowBaseGlobal import aspect2d, base
from panda3d.core import TextNode, Vec4
from toontown.toonbase import ToontownGlobals
from toontown.minigame.craning import CraneGameGlobals


class ModifierPanelUI:
    """Manages the modifier panel UI including panel, lists, and config dialogs."""
    
    def __init__(self, game, modifierManager):
        self.game = game
        self.modifierManager = modifierManager
        
        # UI elements
        self.modifiersPanel = None
        self.currentModifiersList = None
        self.availableModifiersList = None
        self.modifierConfigDialog = None
        self.modifiersPanelVisible = False
    
    def createPanel(self):
        """Create the modifiers management panel"""
        if self.modifiersPanel is not None:
            return  # Already created
        
        # Create the main panel frame using proper dialog styling
        self.modifiersPanel = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(1.6, 1, 1.4),
            pos=(0, 0, 0),
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
            # Scroll buttons using proper assets
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
            decButton_pos=(0.15, 0, 0.03),
            decButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6)
        )
        
        # Available modifiers section
        availableModsLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Available Modifiers:",
            text_scale=0.06,
            text_pos=(0.1, 0.3),
            text_fg=(0.2, 0.2, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            text_align=TextNode.ALeft
        )
        
        # Create scrolled list for available modifiers
        self.availableModifiersList = DirectScrolledList(
            parent=self.modifiersPanel,
            relief=DGG.SUNKEN,
            frameColor=(0.95, 0.85, 1, 1),
            borderWidth=(0.01, 0.01),
            pos=(0.5, 0, 0.2),
            frameSize=(-0.4, 0.2, -0.24, 0.0),
            numItemsVisible=4,
            forceHeight=0.06,
            itemFrame_frameSize=(-0.38, 0.38, -0.03, 0.03),
            itemFrame_pos=(0, 0, -0.032),
            itemFrame_relief=None,
            # Scroll buttons using proper assets
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
            decButton_pos=(0.15, 0, 0.03),
            decButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6)
        )
        
        # Load button assets
        buttons = base.loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        closeButtonImage = (buttons.find('**/CloseBtn_UP'), 
                          buttons.find('**/CloseBtn_DN'), 
                          buttons.find('**/CloseBtn_Rllvr'))
        
        # Close button using proper styling
        closeButton = DirectButton(
            parent=self.modifiersPanel,
            relief=None,
            image=closeButtonImage,
            text="Close",
            text_scale=0.05,
            text_pos=(0, -0.1),
            pos=(0, 0, -0.55),
            command=self.hide
        )
        
        # Clean up loaded models
        gui.removeNode()
        buttons.removeNode()
        
        # Populate the lists with current and available modifiers
        self.updateLists()
        
        # Initially hide the panel
        self.modifiersPanel.hide()
    
    def show(self):
        """Show the modifiers panel"""
        if self.modifiersPanel is None:
            self.createPanel()
        
        self.modifiersPanel.show()
        self.modifiersPanelVisible = True
    
    def hide(self):
        """Hide the modifiers panel"""
        if self.modifiersPanel is not None:
            self.modifiersPanel.hide()
        self.modifiersPanelVisible = False
    
    def updateLists(self):
        """Update the modifiers lists with current and available modifiers"""
        if self.currentModifiersList is None or self.availableModifiersList is None:
            return
            
        # Clear existing items
        self.currentModifiersList.removeAllItems()
        self.availableModifiersList.removeAllItems()
        
        # Load button assets for add/remove buttons
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
        for i, mod in enumerate(self.modifierManager.modifiers):
            itemFrame = DirectFrame(
                relief=None,
                frameSize=(-0.38, 0.38, -0.03, 0.03)
            )
            
            # Modifier name label
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
            
            # Remove button
            removeButton = DirectButton(
                parent=itemFrame,
                relief=None,
                image=removeButtonImage,
                image_scale=(0.3, 1, 0.3),
                image_hpr=(0, 0, 180),  # Rotate to make it a remove arrow
                pos=(0.17, 0, 0),
                command=self._onRemoveModifier,
                extraArgs=[i]
            )
            
            self.currentModifiersList.addItem(itemFrame)

        currentModEnums = [mod.MODIFIER_ENUM for mod in self.modifierManager.modifiers]
        availableModClasses = []
        
        # Get all modifier classes and filter out currently active ones
        for modEnum, modClass in CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES.items():
            if modEnum not in currentModEnums:
                availableModClasses.append(modClass)
        
        # Sort by type (Helpful, Hurtful, Special)
        availableModClasses.sort(key=lambda x: (x.MODIFIER_TYPE, x.MODIFIER_ENUM))
        
        # Populate available modifiers list
        for i, modClass in enumerate(availableModClasses):
            mod = modClass()  # Create instance for display
            
            itemFrame = DirectFrame(
                relief=None,
                frameSize=(-0.38, 0.38, -0.03, 0.03)
            )
            
            # Modifier name label
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
            
            # Add button
            addButton = DirectButton(
                parent=itemFrame,
                relief=None,
                image=addButtonImage,
                image_scale=(0.3, 1, 0.3),
                pos=(0.17, 0, 0),
                command=self._onAddModifier,
                extraArgs=[modClass.MODIFIER_ENUM]
            )
            
            self.availableModifiersList.addItem(itemFrame)
        
        # Clean up loaded model
        gui.removeNode()
    
    def showConfigDialog(self, modifierEnum):
        """Show configuration dialog for a modifier"""
        # Get the modifier class
        modifierClass = CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES.get(modifierEnum)
        if not modifierClass:
            return
        
        # Hide the modifiers panel temporarily
        if self.modifiersPanel:
            self.modifiersPanel.hide()
        
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
        
        # Create a sample modifier to get information
        sampleMod = modifierClass()
        
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
        
        # Special handling for different modifier types
        if modifierEnum == 27:  # ModifierTimerEnabler (Margin Call)
            self._createTimeSelectionOptions(modifierEnum, buttonImage)
        elif modifierEnum in [2, 3]:  # HP modifiers
            self._createPercentageOptions(modifierEnum, modifierClass, buttonImage, "HP")
        elif modifierEnum in [0, 1]:  # Combo modifiers
            self._createPercentageOptions(modifierEnum, modifierClass, buttonImage, "Combo Duration")
        elif modifierEnum == 29:  # ModifierLaffDrain (Leaky Laff)
            self._createLaffDrainOptions(modifierEnum, buttonImage)
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
        """Create generic tier 1-5 options with descriptions"""
        tiers = [1, 2, 3, 4, 5]
        startY = 0.3
        
        for i, tier in enumerate(tiers):
            currentY = startY - i * 0.08
            
            # Try to get a meaningful description
            try:
                sampleMod = modifierClass(tier)
                if hasattr(sampleMod, '_perc_increase'):
                    value = sampleMod._perc_increase()
                    description = f"Tier {tier}: +{value}% effect"
                elif hasattr(sampleMod, '_perc_decrease'):
                    value = sampleMod._perc_decrease()
                    description = f"Tier {tier}: -{value}% effect"
                elif hasattr(sampleMod, 'getDescription'):
                    # Get the description and try to extract meaningful info
                    desc = sampleMod.getDescription()
                    description = f"Tier {tier}: {sampleMod.getName()}"
                else:
                    description = f"Tier {tier}: Standard intensity"
            except:
                description = f"Tier {tier}: Standard intensity"
            
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
    
    def _onConfirmConfig(self, modifierEnum, tier):
        """Handle confirm button click in config dialog"""
        # Clean up the config dialog
        self.cancelConfig()
        
        # Add the modifier with the selected tier
        self.game.sendUpdate('addModifier', [modifierEnum, tier])
    
    def _onAddModifier(self, modifierEnum):
        """Handle add modifier button click"""
        if self.game.isLocalToonHost():
            # Check if this modifier has configurable parameters
            if self.modifierHasParameters(modifierEnum):
                self.showConfigDialog(modifierEnum)
            else:
                # Add directly with default tier 1
                self.game.sendUpdate('addModifier', [modifierEnum, 1])
    
    def _onRemoveModifier(self, modifierIndex):
        """Handle remove modifier button click"""
        if self.game.isLocalToonHost() and modifierIndex < len(self.modifierManager.modifiers):
            modifierEnum = self.modifierManager.modifiers[modifierIndex].MODIFIER_ENUM
            self.game.sendUpdate('removeModifier', [modifierEnum])
    
    def cancelConfig(self):
        """Cancel modifier configuration"""
        if self.modifierConfigDialog:
            self.modifierConfigDialog.destroy()
            self.modifierConfigDialog = None
        
        # Show the modifiers panel again
        if self.modifiersPanel and self.modifiersPanelVisible:
            self.modifiersPanel.show()
    
    def cleanup(self):
        """Clean up all UI elements"""
        if self.modifierConfigDialog:
            self.modifierConfigDialog.destroy()
            self.modifierConfigDialog = None
        
        if self.modifiersPanel:
            self.modifiersPanel.destroy()
            self.modifiersPanel = None
            self.currentModifiersList = None
            self.availableModifiersList = None
        
        self.modifiersPanelVisible = False
    
    def modifierHasParameters(self, modifierEnum):
        """Check if a modifier has configurable parameters"""
        # Get the modifier class
        modifierClass = CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES.get(modifierEnum)
        if not modifierClass:
            return False
        
        # Check some common modifiers that have meaningful tier differences
        tieredModifiers = [
            27,  # ModifierTimerEnabler (Margin Call)
            2,   # ModifierCFOHPIncreaser (Financial Aid)
            3,   # ModifierCFOHPDecreaser (Budget Cuts)
            0,   # ModifierComboExtender (Chains of Finesse)
            1,   # ModifierComboShortener (Chain Locker)
            4,   # ModifierDesafeImpactIncreaser (Strong/Tough/Reinforced Safes)
            9,   # ModifierGoonDamageInflictIncreaser (Goon damage)
            10,  # ModifierSafeDamageInflictIncreaser (Safe damage)
            11,  # ModifierGoonSpeedIncreaser (Goon speed)
            12,  # ModifierGoonCapIncreaser (Goon cap)
            16,  # ModifierTreasureHealDecreaser (Treasure heal decrease)
            17,  # ModifierTreasureRNG (Treasure drop chance)
            18,  # ModifierTreasureCapDecreaser (Treasure cap)
            19,  # ModifierUberBonusIncreaser (Uber bonus)
            29,  # ModifierLaffDrain (Leaky Laff)
        ]
        
        return modifierEnum in tieredModifiers

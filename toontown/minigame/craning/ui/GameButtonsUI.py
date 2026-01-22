"""
GameButtonsUI - Handles play button, modifiers button, and best-of button.
"""

from direct.gui.DirectGui import DirectButton
from direct.showbase.ShowBaseGlobal import base


class GameButtonsUI:
    """Manages game control buttons: play and modifiers."""
    
    def __init__(self, game, roundManager, modifierPanelUI):
        self.game = game
        self.roundManager = roundManager
        self.modifierPanelUI = modifierPanelUI
        
        # UI elements
        self.playButton = None
        self.modifiersButton = None
    
    def createButtons(self, rulesDoneEvent):
        """Create all game buttons as part of rules panel generation"""
        btnGeom = base.loader.loadModel('phase_3/models/gui/quit_button')
        
        # Create play button next to settings
        self.playButton = DirectButton(
            parent=base.a2dTopLeft,
            relief=None,
            text='Play',
            text_scale=0.055,
            text_pos=(0, -0.02),
            geom=(btnGeom.find('**/QuitBtn_UP'),
                  btnGeom.find('**/QuitBtn_DN'),
                  btnGeom.find('**/QuitBtn_RLVR')),
            geom_scale=(0.7, 1, 1),
            pos=(0.7, 0, -0.2),
            command=self._onPlayButton
        )
        self.playButton.hide()  # Play button starts hidden
        
        # Create modifiers button next to play button
        self.modifiersButton = DirectButton(
            parent=base.a2dTopLeft,
            relief=None,
            text='Modifiers',
            text_scale=0.055,
            text_pos=(0, -0.02),
            geom=(btnGeom.find('**/QuitBtn_UP'),
                  btnGeom.find('**/QuitBtn_DN'),
                  btnGeom.find('**/QuitBtn_RLVR')),
            geom_scale=(0.7, 1, 1),
            pos=(1, 0, -0.2),
            command=self._onModifiersButton
        )
        self.modifiersButton.hide()  # Modifiers button starts hidden
        
        # Best Of button removed - now handled by First to X Wins modifier
        self.bestOfButton = None
        btnGeom.removeNode()
    
    def _onPlayButton(self):
        """Handle play button click"""
        # Clean up the ready timeout timer when play is pressed
        if hasattr(self.game, '_destroyReadyTimeoutTimer'):
            self.game._destroyReadyTimeoutTimer()
        messenger.send(self.game.rulesDoneEvent)
    
    def _onModifiersButton(self):
        """Handle modifiers button click - toggle modifiers panel"""
        if self.modifierPanelUI.modifiersPanelVisible:
            self.modifierPanelUI.hide()
        else:
            self.modifierPanelUI.show()
        # Sync for backward compatibility
        if hasattr(self.game, '_syncModifierPanelState'):
            self.game._syncModifierPanelState()
    
    # Best Of button removed - now handled by First to X Wins modifier
    def updateBestOfButton(self, value):
        """Deprecated: Best Of is now handled by First to X Wins modifier"""
        pass
    
    def showButtons(self):
        """Show buttons based on game state"""
        # Show the play button for all players
        if self.playButton:
            self.playButton.show()
        
        # Only show the modifiers button for the leader
        if self.game.isLocalToonHost():
            if self.modifiersButton:
                self.modifiersButton.show()
    
    def cleanup(self):
        """Clean up all buttons"""
        if self.playButton:
            self.playButton.destroy()
            self.playButton = None
        if self.modifiersButton:
            self.modifiersButton.destroy()
            self.modifiersButton = None
        # Best Of button removed

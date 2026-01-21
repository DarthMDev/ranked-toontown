"""
GameButtonsUI - Handles play button, modifiers button, and best-of button.
"""

from direct.gui.DirectGui import DirectButton
from direct.showbase.ShowBaseGlobal import base


class GameButtonsUI:
    """Manages game control buttons: play, modifiers, and best-of."""
    
    def __init__(self, game, roundManager, modifierPanelUI):
        self.game = game
        self.roundManager = roundManager
        self.modifierPanelUI = modifierPanelUI
        
        # UI elements
        self.playButton = None
        self.modifiersButton = None
        self.bestOfButton = None
    
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
        
        # Create best of button next to modifiers button
        self.bestOfButton = DirectButton(
            parent=base.a2dTopLeft,
            relief=None,
            text=f'Best of {self.roundManager.bestOfValue}',
            text_scale=0.055,
            text_pos=(0, -0.02),
            geom=(btnGeom.find('**/QuitBtn_UP'),
                  btnGeom.find('**/QuitBtn_DN'),
                  btnGeom.find('**/QuitBtn_RLVR')),
            geom_scale=(0.7, 1, 1),
            pos=(1.3, 0, -0.2),
            command=self._onBestOfButton
        )
        self.bestOfButton.hide()  # Best of button starts hidden
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
    
    def _onBestOfButton(self):
        """Handle best-of button click - cycle through values"""
        # Cycle through Best of 1, 3, 5, 7
        currentValue = self.roundManager.bestOfValue
        if currentValue == 1:
            newValue = 3
        elif currentValue == 3:
            newValue = 5
        elif currentValue == 5:
            newValue = 7
        else:
            newValue = 1
        
        # Update button text
        if self.bestOfButton:
            self.bestOfButton['text'] = f'Best of {newValue}'
        
        # Update manager state
        self.roundManager.bestOfValue = newValue
        
        # Send update to server if we're the leader
        if self.game.isLocalToonHost():
            self.game.sendUpdate('setBestOf', [newValue])
        
        # Sync for backward compatibility
        if hasattr(self.game, 'bestOfValue'):
            self.game.bestOfValue = newValue
    
    def updateBestOfButton(self, value):
        """Update best-of button text when value changes from server"""
        if self.bestOfButton:
            self.bestOfButton['text'] = f'Best of {value}'
    
    def showButtons(self):
        """Show buttons based on game state"""
        # Show the play button for all players
        if self.playButton:
            self.playButton.show()
        
        # Only show the modifiers and best-of buttons for the leader
        if self.game.isLocalToonHost():
            if self.modifiersButton:
                self.modifiersButton.show()
            if self.bestOfButton:
                self.bestOfButton.show()
    
    def cleanup(self):
        """Clean up all buttons"""
        if self.playButton:
            self.playButton.destroy()
            self.playButton = None
        if self.modifiersButton:
            self.modifiersButton.destroy()
            self.modifiersButton = None
        if self.bestOfButton:
            self.bestOfButton.destroy()
            self.bestOfButton = None

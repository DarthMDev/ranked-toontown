"""
ForfeitRestartManager - Handles client-side forfeit and restart UI.
"""


class ForfeitRestartManager:
    """Manages client-side forfeit and restart consent dialogs."""
    
    def __init__(self, game):
        self.game = game
        self.pendingForfeitRequester = None  # avId of player who requested forfeit
        self.forfeitConsents = set()  # Set of avIds who have consented
        
        self.pendingRestartRequester = None  # avId of player who requested restart
        self.restartConsents = set()  # Set of avIds who have consented
        # Dialogs are managed by ForfeitRestartDialogsUI, not stored here
    
    def setRequestForfeit(self, requesterAvId):
        """Receive forfeit request from server"""
        self.pendingForfeitRequester = requesterAvId
        self.forfeitConsents.clear()
        self.forfeitConsents.add(requesterAvId)  # Requester automatically consents
        
        # Show dialog via UI class
        if hasattr(self.game, 'forfeitRestartDialogsUI'):
            self.game.forfeitRestartDialogsUI.showForfeitDialog(requesterAvId)
    
    def setUpdateForfeitConsents(self, consentAvIds):
        """Update forfeit consent status"""
        self.forfeitConsents = set(consentAvIds)
        # Update dialog via UI class
        if hasattr(self.game, 'forfeitRestartDialogsUI'):
            self.game.forfeitRestartDialogsUI.updateForfeitConsents(list(consentAvIds))
    
    def setCancelForfeit(self):
        """Cancel forfeit request"""
        self.pendingForfeitRequester = None
        self.forfeitConsents.clear()
        # Clean up dialogs via UI class
        if hasattr(self.game, 'forfeitRestartDialogsUI'):
            self.game.forfeitRestartDialogsUI._cleanupForfeitDialogs()
    
    def setRequestRestart(self, requesterAvId):
        """Receive restart request from server"""
        self.pendingRestartRequester = requesterAvId
        self.restartConsents.clear()
        self.restartConsents.add(requesterAvId)  # Requester automatically consents
        
        # Show dialog via UI class
        if hasattr(self.game, 'forfeitRestartDialogsUI'):
            self.game.forfeitRestartDialogsUI.showRestartDialog(requesterAvId)
    
    def setUpdateRestartConsents(self, consentAvIds):
        """Update restart consent status"""
        self.restartConsents = set(consentAvIds)
        # Update dialog via UI class
        if hasattr(self.game, 'forfeitRestartDialogsUI'):
            self.game.forfeitRestartDialogsUI.updateRestartConsents(list(consentAvIds))
    
    def setCancelRestart(self):
        """Cancel restart request"""
        self.pendingRestartRequester = None
        self.restartConsents.clear()
        # Clean up dialogs via UI class
        if hasattr(self.game, 'forfeitRestartDialogsUI'):
            self.game.forfeitRestartDialogsUI._cleanupRestartDialogs()
    
    # Dialog creation and management now handled by ForfeitRestartDialogsUI
    # Old placeholder methods removed - see ForfeitRestartDialogsUI class

"""
ForfeitRestartManagerAI - Handles forfeit and restart consent systems.
"""

from toontown.minigame.craning import CraneGameGlobals


class ForfeitRestartManagerAI:
    """Manages forfeit and restart consent systems."""
    
    def __init__(self, game):
        self.game = game
        self.pendingForfeitRequest = None  # avId of player who requested forfeit, or None if no pending request
        self.forfeitConsents = set()  # Set of avIds who have consented to forfeit
        self.pendingRestartRequest = None  # avId of player who requested restart, or None if no pending request
        self.restartConsents = set()  # Set of avIds who have consented to restart
    
    # Forfeit methods
    def requestForfeit(self):
        """Handle forfeit request from a player"""
        avId = self.game.air.getAvatarIdFromSender()
        
        # Validate player is in the game and not spectating
        if avId not in self.game.getParticipantIdsNotSpectating():
            self.game.notify.warning(f"Player {avId} tried to request forfeit but is not a participant")
            return
        
        # If there's already a pending request, cancel it first
        if self.pendingForfeitRequest is not None:
            self.cancelForfeitRequest()
        
        # Start a new forfeit request
        self.pendingForfeitRequest = avId
        self.forfeitConsents.clear()
        self.forfeitConsents.add(avId)  # Requester automatically consents
        
        # Send forfeit request to all players
        self.d_requestForfeit(avId)
    
    def confirmForfeit(self):
        """Handle forfeit confirmation from a player"""
        avId = self.game.air.getAvatarIdFromSender()
        
        # Validate there's a pending request
        if self.pendingForfeitRequest is None:
            self.game.notify.warning(f"Player {avId} tried to confirm forfeit but there's no pending request")
            return
        
        # Validate player is in the game and not spectating
        if avId not in self.game.getParticipantIdsNotSpectating():
            self.game.notify.warning(f"Player {avId} tried to confirm forfeit but is not a participant")
            return
        
        # Add consent
        self.forfeitConsents.add(avId)
        
        # Check if all players have consented
        participants = self.game.getParticipantIdsNotSpectating()
        if len(self.forfeitConsents) >= len(participants):
            # All players have consented, proceed with forfeit
            self.executeForfeit(self.pendingForfeitRequest)
        else:
            # Update clients with current consent status
            self.d_updateForfeitConsents(list(self.forfeitConsents))
    
    def rejectForfeit(self):
        """Handle forfeit rejection from a player - cancels the forfeit immediately"""
        avId = self.game.air.getAvatarIdFromSender()
        
        # Validate there's a pending request
        if self.pendingForfeitRequest is None:
            self.game.notify.warning(f"Player {avId} tried to reject forfeit but there's no pending request")
            return
        
        # Validate player is in the game and not spectating
        if avId not in self.game.getParticipantIdsNotSpectating():
            self.game.notify.warning(f"Player {avId} tried to reject forfeit but is not a participant")
            return
        
        # Rejection cancels the forfeit immediately
        self.pendingForfeitRequest = None
        self.forfeitConsents.clear()
        self.d_cancelForfeit()
    
    def cancelForfeitRequest(self):
        """Cancel the current forfeit request (called from client)"""
        avId = self.game.air.getAvatarIdFromSender()
        
        # Only the requester can cancel
        if self.pendingForfeitRequest != avId:
            self.game.notify.warning(f"Player {avId} tried to cancel forfeit but is not the requester")
            return
        
        if self.pendingForfeitRequest is not None:
            self.pendingForfeitRequest = None
            self.forfeitConsents.clear()
            self.d_cancelForfeit()
    
    def executeForfeit(self, forfeiterAvId):
        """Execute the forfeit - put the requester in last place"""
        # Get current round from RoundManager if available
        currentRound = 1
        if hasattr(self.game, 'roundManager'):
            currentRound = self.game.roundManager.currentRound
        
        # Forfeit: Set the forfeiter's score to ensure they come in last place
        context = self.game.getScoringContext()
        _round = context.get_round(currentRound)
        score = _round.get_score(forfeiterAvId)
        num_players = len(self.game.getParticipantsNotSpectating())
        
        if num_players == 1:
            # Single player game - just subtract their score to put them at 0 or negative
            # No need to give bonus points since they're the only player
            if hasattr(self.game, 'scoreManager'):
                self.game.scoreManager.addScore(
                    forfeiterAvId, 
                    -score, 
                    reason=CraneGameGlobals.ScoreReason.FORFEIT
                )
        else:
            # Multi-player game - ensure all other participants have points so forfeiter is last
            for toon in self.game.getParticipantsNotSpectating():
                if toon.getDoId() != forfeiterAvId:
                    if hasattr(self.game, 'scoreManager'):
                        self.game.scoreManager.addScore(
                            toon.getDoId(), 
                            2000, 
                            reason=CraneGameGlobals.ScoreReason.KILLING_BLOW
                        )
            
            if hasattr(self.game, 'scoreManager'):
                self.game.scoreManager.addScore(
                    forfeiterAvId, 
                    -score, 
                    reason=CraneGameGlobals.ScoreReason.FORFEIT
                )
        
        # Clear forfeit request state
        self.pendingForfeitRequest = None
        self.forfeitConsents.clear()
        
        # Notify clients to clean up forfeit dialogs (without showing cancellation message)
        self.d_cleanupForfeitDialogs()
        
        # End the game
        self.game.gameFSM.request('victory')
    
    def d_requestForfeit(self, requesterAvId):
        """Send forfeit request to all clients"""
        self.game.sendUpdate('setRequestForfeit', [requesterAvId])
    
    def d_updateForfeitConsents(self, consentAvIds):
        """Update clients with current consent status"""
        self.game.sendUpdate('setUpdateForfeitConsents', [consentAvIds])
    
    def d_cancelForfeit(self):
        """Notify clients that forfeit request was cancelled"""
        self.game.sendUpdate('setCancelForfeit', [])
    
    def d_cleanupForfeitDialogs(self):
        """Clean up forfeit dialogs without showing cancellation message (used when forfeit is executed)"""
        self.game.sendUpdate('setCleanupForfeitDialogs', [])
    
    # Restart methods
    def requestRestart(self):
        """Handle restart request from a player"""
        avId = self.game.air.getAvatarIdFromSender()
        
        # Validate player is in the game and not spectating
        if avId not in self.game.getParticipantIdsNotSpectating():
            self.game.notify.warning(f"Player {avId} tried to request restart but is not a participant")
            return
        
        # If there's already a pending request, cancel it first
        if self.pendingRestartRequest is not None:
            self.cancelRestartRequest()
        
        # Start a new restart request
        self.pendingRestartRequest = avId
        self.restartConsents.clear()
        self.restartConsents.add(avId)  # Requester automatically consents
        
        # Send restart request to all players
        self.d_requestRestart(avId)
    
    def confirmRestart(self):
        """Handle restart confirmation from a player"""
        avId = self.game.air.getAvatarIdFromSender()
        
        # Validate there's a pending request
        if self.pendingRestartRequest is None:
            self.game.notify.warning(f"Player {avId} tried to confirm restart but there's no pending request")
            return
        
        # Validate player is in the game and not spectating
        if avId not in self.game.getParticipantIdsNotSpectating():
            self.game.notify.warning(f"Player {avId} tried to confirm restart but is not a participant")
            return
        
        # Add consent
        self.restartConsents.add(avId)
        
        # Check if all players have consented
        participants = self.game.getParticipantIdsNotSpectating()
        if len(self.restartConsents) >= len(participants):
            # All players have consented, proceed with restart
            self.executeRestart(self.pendingRestartRequest)
        else:
            # Update clients with current consent status
            self.d_updateRestartConsents(list(self.restartConsents))
    
    def rejectRestart(self):
        """Handle restart rejection from a player - cancels the restart immediately"""
        avId = self.game.air.getAvatarIdFromSender()
        
        # Validate there's a pending request
        if self.pendingRestartRequest is None:
            self.game.notify.warning(f"Player {avId} tried to reject restart but there's no pending request")
            return
        
        # Validate player is in the game and not spectating
        if avId not in self.game.getParticipantIdsNotSpectating():
            self.game.notify.warning(f"Player {avId} tried to reject restart but is not a participant")
            return
        
        # Rejection cancels the restart immediately
        self.pendingRestartRequest = None
        self.restartConsents.clear()
        self.d_cancelRestart()
    
    def cancelRestartRequest(self):
        """Cancel the current restart request (called from client)"""
        avId = self.game.air.getAvatarIdFromSender()
        
        # Only the requester can cancel
        if self.pendingRestartRequest != avId:
            self.game.notify.warning(f"Player {avId} tried to cancel restart but is not the requester")
            return
        
        if self.pendingRestartRequest is not None:
            self.pendingRestartRequest = None
            self.restartConsents.clear()
            self.d_cancelRestart()
    
    def executeRestart(self, requesterAvId):
        """Execute the restart - transition to cleanup then prepare"""
        # Clear restart request state
        self.pendingRestartRequest = None
        self.restartConsents.clear()
        
        # Notify clients to clean up restart dialogs (without showing cancellation message)
        self.d_cleanupRestartDialogs()
        
        # Restart the game
        self.game.gameFSM.request("cleanup")
        self.game.gameFSM.request('prepare')
    
    def d_requestRestart(self, requesterAvId):
        """Send restart request to all clients"""
        self.game.sendUpdate('setRequestRestart', [requesterAvId])
    
    def d_updateRestartConsents(self, consentAvIds):
        """Update clients with current consent status"""
        self.game.sendUpdate('setUpdateRestartConsents', [consentAvIds])
    
    def d_cancelRestart(self):
        """Notify clients that restart request was cancelled"""
        self.game.sendUpdate('setCancelRestart', [])
    
    def d_cleanupRestartDialogs(self):
        """Clean up restart dialogs without showing cancellation message (used when restart is executed)"""
        self.game.sendUpdate('setCleanupRestartDialogs', [])
    
    def reset(self):
        """Reset forfeit/restart state (called when exiting play)"""
        self.pendingForfeitRequest = None
        self.forfeitConsents.clear()
        self.pendingRestartRequest = None
        self.restartConsents.clear()

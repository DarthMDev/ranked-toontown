"""
ForfeitRestartDialogsUI - Handles forfeit and restart dialog creation and management.
"""

from direct.gui.DirectGui import DGG
from direct.interval.IntervalGlobal import Sequence, LerpScaleInterval
from toontown.toontowngui import ToonHeadDialog
from toontown.toontowngui import TTDialog
from otp.otpbase import OTPLocalizer


class ForfeitRestartDialogsUI:
    """Manages forfeit and restart consent dialogs."""
    
    def __init__(self, game, forfeitRestartManager):
        self.game = game
        self.forfeitRestartManager = forfeitRestartManager
        
        # Dialog references
        self.forfeitDialog = None
        self.forfeitRequesterDialog = None
        self.restartDialog = None
        self.restartRequesterDialog = None
    
    def showForfeitDialog(self, requesterAvId):
        """Show forfeit dialog based on whether this is the requester"""
        requesterToon = self.game.cr.getDo(requesterAvId)
        if not requesterToon:
            self.game.notify.warning(f"Could not find requester toon {requesterAvId}")
            return
        
        requesterName = requesterToon.getName()
        requesterDNA = requesterToon.getStyle()
        
        # Clean up any existing dialogs
        self._cleanupForfeitDialogs()
        
        # Check if local player is a spectator - don't show dialog to spectators
        if base.localAvatar.doId in self.game.getSpectators():
            self.game.notify.info(f"Forfeit requested by {requesterName} (spectator, no dialog shown)")
            return
        
        if requesterAvId == base.localAvatar.doId:
            # Requester sees status dialog with cancel button
            participants = self.game.getParticipantIdsNotSpectating()
            numNeeded = len(participants)
            message = f"Forfeit requested!\n\n"
            message += f"Waiting for {numNeeded - 1} other player(s) to confirm."
            
            # Create dialog with desired scale
            desiredScale = 0.4
            self.forfeitRequesterDialog = ToonHeadDialog.ToonHeadDialog(
                dna=requesterDNA,
                text=message,
                style=TTDialog.CancelOnly,
                buttonTextList=[OTPLocalizer.GuildInviterCancel],
                command=self._onForfeitRequesterDialog,
                image_color=(1.0, 0.89, 0.77, 1.0),
                geom_scale=0.2,
                geom_pos=(-0.1, 0, -0.025),
                pad=(0.075, 0.075),
                topPad=0,
                midPad=0,
                pos=(0.45, 0, 0.75),
                scale=desiredScale
            )
            # Override default animation
            self.forfeitRequesterDialog.setScale(0.01)
            customAnim = Sequence(
                LerpScaleInterval(self.forfeitRequesterDialog, 0.2, desiredScale * 1.1, 0.01, blendType='easeInOut'),
                LerpScaleInterval(self.forfeitRequesterDialog, 0.09, desiredScale, blendType='easeInOut')
            )
            customAnim.start()
            self.forfeitRequesterDialog.show()
        else:
            # Other players see confirmation dialog
            message = f"{requesterName} has requested to FORFEIT the match.\n\n"
            
            # Create dialog with desired scale
            desiredScale = 0.5
            self.forfeitDialog = ToonHeadDialog.ToonHeadDialog(
                dna=requesterDNA,
                text=message,
                style=TTDialog.TwoChoice,
                buttonTextList=[OTPLocalizer.FriendInviteeOK, OTPLocalizer.FriendInviteeNo],
                command=self._onForfeitDialog,
                image_color=(1.0, 0.89, 0.77, 1.0),
                geom_scale=0.2,
                geom_pos=(-0.1, 0, -0.025),
                pad=(0.075, 0.075),
                topPad=0,
                midPad=0,
                pos=(0.45, 0, 0.75),
                scale=desiredScale
            )
            # Override default animation
            self.forfeitDialog.setScale(0.01)
            customAnim = Sequence(
                LerpScaleInterval(self.forfeitDialog, 0.2, desiredScale * 1.1, 0.01, blendType='easeInOut'),
                LerpScaleInterval(self.forfeitDialog, 0.09, desiredScale, blendType='easeInOut')
            )
            customAnim.start()
            self.forfeitDialog.show()
        
        self.game.notify.info(f"Forfeit requested by {requesterName}")
    
    def updateForfeitConsents(self, consentAvIds):
        """Update forfeit dialog text based on consent progress"""
        participants = self.game.getParticipantIdsNotSpectating()
        numConsented = len(consentAvIds)
        numNeeded = len(participants)
        
        if numConsented < numNeeded:
            # Update requester dialog to show progress
            if self.forfeitRequesterDialog and not self.forfeitRequesterDialog.isEmpty():
                requesterToon = self.game.cr.getDo(self.forfeitRestartManager.pendingForfeitRequester)
                requesterDNA = requesterToon.getStyle() if requesterToon else None
                if requesterDNA:
                    message = f"Forfeit requested!\n\n"
                    message += f"Progress: {numConsented}/{numNeeded} players confirmed."
                    self.forfeitRequesterDialog['text'] = message
            
            # Update non-requester dialog to show progress
            if self.forfeitDialog and not self.forfeitDialog.isEmpty():
                requesterToon = self.game.cr.getDo(self.forfeitRestartManager.pendingForfeitRequester)
                requesterName = requesterToon.getName() if requesterToon else "Unknown"
                message = f"{requesterName} has requested to FORFEIT the match.\n\n"
                message += f"Progress: {numConsented}/{numNeeded} players confirmed"
                self.forfeitDialog['text'] = message
    
    def _onForfeitDialog(self, value):
        """Handle forfeit dialog button click (for non-requesters)"""
        self._cleanupForfeitDialogs()
        
        if value == DGG.DIALOG_OK:  # OK/Yes button
            self.game.sendUpdate('confirmForfeit', [])
        else:  # No button - reject the forfeit
            self.game.sendUpdate('rejectForfeit', [])
    
    def _onForfeitRequesterDialog(self, value):
        """Handle forfeit requester dialog button click (cancel button)"""
        self._cleanupForfeitDialogs()
        
        # Cancel button was clicked - send cancel request to server
        self.game.sendUpdate('cancelForfeitRequest', [])
    
    def showRestartDialog(self, requesterAvId):
        """Show restart dialog based on whether this is the requester"""
        requesterToon = self.game.cr.getDo(requesterAvId)
        if not requesterToon:
            self.game.notify.warning(f"Could not find requester toon {requesterAvId}")
            return
        
        requesterName = requesterToon.getName()
        requesterDNA = requesterToon.getStyle()
        
        # Clean up any existing dialogs
        self._cleanupRestartDialogs()
        
        # Check if local player is a spectator - don't show dialog to spectators
        if base.localAvatar.doId in self.game.getSpectators():
            self.game.notify.info(f"Restart requested by {requesterName} (spectator, no dialog shown)")
            return
        
        if requesterAvId == base.localAvatar.doId:
            # Requester sees status dialog with cancel button
            participants = self.game.getParticipantIdsNotSpectating()
            numNeeded = len(participants)
            message = f"Restart requested!\n\n"
            message += f"Waiting for {numNeeded - 1} other player(s) to confirm."
            
            # Create dialog with desired scale
            desiredScale = 0.4
            self.restartRequesterDialog = ToonHeadDialog.ToonHeadDialog(
                dna=requesterDNA,
                text=message,
                style=TTDialog.CancelOnly,
                buttonTextList=[OTPLocalizer.GuildInviterCancel],
                command=self._onRestartRequesterDialog,
                image_color=(1.0, 0.89, 0.77, 1.0),
                geom_scale=0.2,
                geom_pos=(-0.1, 0, -0.025),
                pad=(0.075, 0.075),
                topPad=0,
                midPad=0,
                pos=(0.45, 0, 0.75),
                scale=desiredScale
            )
            # Override default animation
            self.restartRequesterDialog.setScale(0.01)
            customAnim = Sequence(
                LerpScaleInterval(self.restartRequesterDialog, 0.2, desiredScale * 1.1, 0.01, blendType='easeInOut'),
                LerpScaleInterval(self.restartRequesterDialog, 0.09, desiredScale, blendType='easeInOut')
            )
            customAnim.start()
            self.restartRequesterDialog.show()
        else:
            # Other players see confirmation dialog
            message = f"{requesterName} has requested to restart the match.\n\n"
            
            # Create dialog with desired scale
            desiredScale = 0.5
            self.restartDialog = ToonHeadDialog.ToonHeadDialog(
                dna=requesterDNA,
                text=message,
                style=TTDialog.TwoChoice,
                buttonTextList=[OTPLocalizer.FriendInviteeOK, OTPLocalizer.FriendInviteeNo],
                command=self._onRestartDialog,
                image_color=(1.0, 0.89, 0.77, 1.0),
                geom_scale=0.2,
                geom_pos=(-0.1, 0, -0.025),
                pad=(0.075, 0.075),
                topPad=0,
                midPad=0,
                pos=(0.45, 0, 0.75),
                scale=desiredScale
            )
            # Override default animation
            self.restartDialog.setScale(0.01)
            customAnim = Sequence(
                LerpScaleInterval(self.restartDialog, 0.2, desiredScale * 1.1, 0.01, blendType='easeInOut'),
                LerpScaleInterval(self.restartDialog, 0.09, desiredScale, blendType='easeInOut')
            )
            customAnim.start()
            self.restartDialog.show()
        
        self.game.notify.info(f"Restart requested by {requesterName}")
    
    def updateRestartConsents(self, consentAvIds):
        """Update restart dialog text based on consent progress"""
        participants = self.game.getParticipantIdsNotSpectating()
        numConsented = len(consentAvIds)
        numNeeded = len(participants)
        
        if numConsented < numNeeded:
            # Update requester dialog to show progress
            if self.restartRequesterDialog and not self.restartRequesterDialog.isEmpty():
                requesterToon = self.game.cr.getDo(self.forfeitRestartManager.pendingRestartRequester)
                requesterDNA = requesterToon.getStyle() if requesterToon else None
                if requesterDNA:
                    message = f"Restart requested!\n\n"
                    message += f"Progress: {numConsented}/{numNeeded} players confirmed."
                    self.restartRequesterDialog['text'] = message
            
            # Update non-requester dialog to show progress
            if self.restartDialog and not self.restartDialog.isEmpty():
                requesterToon = self.game.cr.getDo(self.forfeitRestartManager.pendingRestartRequester)
                requesterName = requesterToon.getName() if requesterToon else "Unknown"
                message = f"{requesterName} has requested to restart the match.\n\n"
                message += f"Progress: {numConsented}/{numNeeded} players confirmed"
                self.restartDialog['text'] = message
    
    def _onRestartDialog(self, value):
        """Handle restart dialog button click (for non-requesters)"""
        self._cleanupRestartDialogs()
        
        if value == DGG.DIALOG_OK:  # OK/Yes button
            self.game.sendUpdate('confirmRestart', [])
        else:  # No button - reject the restart
            self.game.sendUpdate('rejectRestart', [])
    
    def _onRestartRequesterDialog(self, value):
        """Handle restart requester dialog button click (cancel button)"""
        self._cleanupRestartDialogs()
        
        # Cancel button was clicked - send cancel request to server
        self.game.sendUpdate('cancelRestartRequest', [])
    
    def _cleanupForfeitDialogs(self):
        """Clean up forfeit dialogs"""
        if self.forfeitDialog:
            self.forfeitDialog.cleanup()
            self.forfeitDialog = None
        if self.forfeitRequesterDialog:
            self.forfeitRequesterDialog.cleanup()
            self.forfeitRequesterDialog = None
    
    def _cleanupRestartDialogs(self):
        """Clean up restart dialogs"""
        if self.restartDialog:
            self.restartDialog.cleanup()
            self.restartDialog = None
        if self.restartRequesterDialog:
            self.restartRequesterDialog.cleanup()
            self.restartRequesterDialog = None
    
    def cleanup(self):
        """Clean up all dialogs"""
        self._cleanupForfeitDialogs()
        self._cleanupRestartDialogs()

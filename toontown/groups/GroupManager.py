from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal
from direct.gui.DirectLabel import DirectLabel

from libotp.nametag.WhisperGlobals import WhisperType
from toontown.groups import GroupGlobals
from toontown.groups.GroupBase import GroupBase
from toontown.groups.GroupInterface import GroupInterface
from toontown.groups.GroupMemberStruct import GroupMemberStruct
from toontown.minigame.DistributedMinigame import DistributedMinigame
from toontown.safezone import Playground
from toontown.toon.GroupInvitee import GroupInvitee
from toontown.toonbase import ToontownGlobals


class GroupManager(DistributedObjectGlobal, GroupBase):
    """
    An instance on the client that is responsible for managing separate groups.
    A "group" can be thought of as a "party" on other games, or even a "lobby".

    Toons will be in a group with other toons while a leader/host sets up game rules and eventually
    sends the entire group into some instance. (In our case, the trolley with specific settings.)

    This class is responsible for communicating with the server's version of the group manager,
    and will tell our local client which group we are in.
    
    This is a GLOBAL object, so it can send group state to clients regardless of what zone they're in.
    """

    Notify = DirectNotifyGlobal.directNotify.newCategory('GroupManager')

    def __init__(self, cr):
        DistributedObjectGlobal.__init__(self, cr)
        GroupBase.__init__(self, GroupBase.NoLeader)

        # Group state
        self.groupId: int = GroupBase.NoGroup  # The ID of the current group (for reference, not a DO)
        self.minigameType: int = ToontownGlobals.CraneGameId
        
        # UI elements
        self.interface: GroupInterface | None = None
        self.going_text: DirectLabel | None = None
        self.modifiersButton = None  # Modifiers button at top left of screen
        
        # Other state
        self.currentInvite: GroupInvitee | None = None
        self.ready_task = None  # A task that checks the state of our toon every so often. Helps with making sure we are properly ready.

        self.Notify.setDebug(True)

    def generate(self):
        """
        When a group manager comes into existence, we essentially just need to create a way to
        reference this object globally across the game so that our toon panels know to display
        an invite button.
        """
        super().generate()
        self.Notify.info("Starting up...")
        self.ready_task = taskMgr.add(self.__readyCheck, self.uniqueName('readycheck'))
        # Listen for place changes to update interface visibility
        self.accept('playGameSetPlace', self.__onPlaceChanged)
        # Track minigame objects to detect when we join/leave
        self._trackedMinigames = set()
        # Hook into DistributedMinigame.setParticipants to detect when we join (only once)
        if not hasattr(DistributedMinigame, '_groupManagerHooked'):
            self.__hookMinigameSetParticipants()
            DistributedMinigame._groupManagerHooked = True

    def delete(self):
        """
        When this group manager deletes, we need to make sure that we leave our current group.
        """
        super().delete()
        self.Notify.info("Shutting down...")
        self.ignore('playGameSetPlace')
        if hasattr(base, 'localAvatar') and base.localAvatar:
            base.localAvatar.setGroupManager(None)
        self.destroyCurrentInvitePanel()
        self.__deleteInterface()
        taskMgr.remove(self.uniqueName('readycheck'))
        self._trackedMinigames.clear()

    def destroyCurrentInvitePanel(self):
        if self.currentInvite is not None:
            self.currentInvite.cleanup()
            self.currentInvite = None

    def isInGroup(self) -> bool:
        """
        Returns True if the local toon is currently in a group.
        """
        if not hasattr(base, 'localAvatar') or base.localAvatar is None:
            return False
        return self.groupId != GroupBase.NoGroup and base.localAvatar.getDoId() in self.getMemberIds()

    def __readyCheck(self, task):
        task.delayTime = 5

        # If we are in a group, then tell the server we are ready. Continuously do this while we are ready to keep us in sync.
        if self.isInGroup():
            if base.cr.playGame.getPlace() is not None and base.cr.playGame.getPlace().getState() == 'walk':
                self.updateStatus(GroupGlobals.STATUS_READY)

        return task.again

    """
    Methods called from the codebase.
    """

    def attemptKick(self, avId: int):
        """
        Attempt to kick this toon from the boarding group we are currently in.
        """
        if not self.isInGroup():
            return
        
        if not hasattr(base, 'localAvatar') or base.localAvatar is None:
            return

        # Are we the leader of our group and not trying to kick ourselves?
        if base.localAvatar.getDoId() != avId and self.getLeader() != base.localAvatar.doId:
            return

        self.d_requestKick(avId)

    def attemptInvite(self, avId: int):
        """
        Attempt to add this toon to the group we are currently in.
        """
        self.Notify.debug(f"Attempting to invite {avId}")
        self.d_invitePlayer(avId)

    def attemptPromote(self, avId: int):
        self.Notify.debug(f"Attempting to promote {avId}")
        self.d_promote(avId)

    def attemptSwitch(self, avId: int):
        self.Notify.debug(f"Attempting to switch {avId}")
        self.d_requestTeamSwap(avId)

    def attemptStart(self):
        self.Notify.debug(f"Attempting to start the group")
        if self.isInGroup():
            self.d_requestStart()

    def requestGameSwitch(self, minigameId: int):
        self.Notify.debug(f"Attempting to switch the game to {minigameId}")
        if self.isInGroup() and hasattr(base, 'localAvatar') and base.localAvatar and self.getLeader() == base.localAvatar.getDoId():
            self.d_requestMinigameSwitch(minigameId)

    def updateStatus(self, code: int):

        self.Notify.debug(f"Updating local av status to {code} for current group")

        # Don't send codes unless they are ready/unready codes.
        if code not in (GroupGlobals.STATUS_UNREADY, GroupGlobals.STATUS_READY):
            return

        # If we are the leader we don't need to update the ID. We are in charge of starting the group anyway.
        if self.isInGroup() and hasattr(base, 'localAvatar') and base.localAvatar and self.getLeader() == base.localAvatar.getDoId():
            return

        # Only update if we're actually in a group
        if not self.isInGroup():
            return

        self.d_setStatus(code)

    """
    Astron Methods
    """

    def d_respondToInvite(self, inviter: int, decision: bool):
        self.sendUpdate("inviteResponse", [inviter, decision])

    def d_invitePlayer(self, avId: int):
        self.sendUpdate('invitePlayer', [avId])

    def d_requestKick(self, avId: int):
        self.sendUpdate('requestKick', [avId])

    def d_promote(self, avId: int):
        self.sendUpdate('requestPromote', [avId])

    def d_requestTeamSwap(self, avId: int):
        self.sendUpdate('requestTeamSwap', [avId])

    def d_requestStart(self):
        self.sendUpdate('requestStart')

    def d_setStatus(self, code):
        self.sendUpdate('updateStatus', [code])

    def d_requestMinigameSwitch(self, minigameId: int):
        self.sendUpdate('requestMinigameSwitch', [minigameId])
    
    def d_requestSetModifiers(self, minigameId: int, modifierBlob: bytes):
        """Request server to set modifiers for a minigame"""
        self.sendUpdate("requestSetModifiers", [minigameId, modifierBlob])
    
    def d_requestGetModifiers(self, minigameId: int):
        """Request server to get current modifiers for a minigame"""
        self.sendUpdate("requestGetModifiers", [minigameId])
    
    def d_requestGroupDebug(self):
        """Request group debug data from AI"""
        self.sendUpdate('requestGroupDebug', [])
    
    def __onModifiersClicked(self):
        """
        Called when the modifiers button is clicked.
        """
        # Only leader can configure modifiers
        if not self.isInGroup() or not hasattr(base, 'localAvatar') or base.localAvatar is None or self.getLeader() != base.localAvatar.getDoId():
            return
        
        # Show the modifier panel
        if not hasattr(self, 'modifierPanelUI'):
            from toontown.groups.GroupModifierPanelUI import GroupModifierPanelUI
            self.modifierPanelUI = GroupModifierPanelUI(self)
        
        self.modifierPanelUI.showPanel()
    
    def __updateModifiersButtonVisibility(self):
        """Update modifiers button visibility based on leadership and group membership"""
        if self.modifiersButton is not None:
            isLeader = self.isInGroup() and hasattr(base, 'localAvatar') and base.localAvatar and self.getLeader() == base.localAvatar.getDoId()
            if isLeader:
                self.modifiersButton.show()
            else:
                self.modifiersButton.hide()
    
    def setMinigameZone(self, minigameZone, minigameGameId):
        """
        Called from the AI when the group is being sent to a minigame.
        """
        self.Notify.debug(f"setMinigameZone: Called with zone={minigameZone}, gameId={minigameGameId}")
        
        playground = base.cr.playGame.getPlace()
        if playground is None:
            return

        # First, freeze the toon. We need to prevent softlocks.
        playground.setState('stopped')

        def __updateText(i):
            if i <= 0:
                if self.going_text:
                    self.going_text['text'] = 'Have fun!'
                    self.going_text['text_fg'] = (.15, .9, .15, 1)
                return

            if self.going_text:
                self.going_text['text'] = f"Leaving in {i}..."
                self.going_text['text_fg'] = (.6, .6, .6, 1)
            taskMgr.remove(self.uniqueName('teleportToMinigameTextUpdate'))
            taskMgr.doMethodLater(1, __updateText, self.uniqueName('teleportToMinigameTextUpdate'), extraArgs=[i-1])

        def __teleportToMinigame(_=None):
            doneStatus = {
                'loader': 'minigame',
                'where': 'minigame',
                'hoodId': playground.loader.hood.id,
                'zoneId': minigameZone,
                'shardId': None,
                'minigameId': minigameGameId,
                'avId': None,
            }
            playground.doneStatus = doneStatus
            playground.fsm.forceTransition('teleportOut', [doneStatus])

        # Next, in 3 seconds we should teleport to where we need to go.
        taskMgr.doMethodLater(3, __teleportToMinigame, self.uniqueName('teleportToMinigame'))
        __updateText(3)
    
    def setMinigameType(self, minigameType):
        """
        Called from the AI when the minigame type changes.
        This is a direct update method (separate from setGroupState).
        """
        oldType = getattr(self, 'minigameType', None)
        self.Notify.debug(f"setMinigameType: Called with minigameType={minigameType} (old: {oldType})")
        self.minigameType = minigameType
        # Always send the event to ensure UI updates
        messenger.send('group-minigame-updated')
    
    def setModifiers(self, minigameId: int, modifierStructs: list):
        """
        Called from the AI when modifiers are received.
        Updates the modifier panel UI data, regardless of whether the panel is visible.
        This ensures modifiers persist when the panel is reopened.
        modifierStructs is a list of [enum, tier] lists from Astron's MinigameModifier[] struct array.
        """
        # modifierStructs is already deserialized by Astron from MinigameModifier[] struct array
        
        # Use the minigameId parameter, not self.minigameType (which might be different)
        actualMinigameId = minigameId if minigameId in ToontownGlobals.ValidMinigameIds else self.minigameType
        
        # Always update modifier panel data, even if panel isn't visible
        # This ensures modifiers persist when the panel is reopened
        if not hasattr(self, 'modifierPanelUI'):
            return
        
        # Update the modifier panel with received modifiers
        self.modifierPanelUI.currentModifiers = []
        
        # Get the appropriate ModifierBase for this minigame
        modifierBase = None
        if actualMinigameId == ToontownGlobals.CraneGameId:
            from toontown.minigame.craning import CraneGameGlobals
            modifierBase = CraneGameGlobals.CFORulesetModifierBase
        elif actualMinigameId == ToontownGlobals.PieGameId:
            from toontown.minigame.pie import PieGameGlobals
            modifierBase = PieGameGlobals.PieGameModifierBase
        elif actualMinigameId == ToontownGlobals.ScaleGameId:
            from toontown.minigame.scale import ScaleGameGlobals
            modifierBase = ScaleGameGlobals.ScaleGameModifierBase
        elif actualMinigameId == ToontownGlobals.SeltzerGameId:
            from toontown.minigame.seltzer import SeltzerGameGlobals
            modifierBase = SeltzerGameGlobals.SeltzerGameModifierBase
        elif actualMinigameId == ToontownGlobals.GolfGreenGameId:
            from toontown.minigame.golfgreen import GolfGreenGlobals
            modifierBase = GolfGreenGlobals.GolfGreenGameModifierBase
        
        for modStruct in modifierStructs:
            try:
                if modifierBase and hasattr(modifierBase, 'fromStruct'):
                    modifier = modifierBase.fromStruct(modStruct)
                    self.modifierPanelUI.currentModifiers.append(modifier)
            except Exception as e:
                self.Notify.warning(f"Failed to deserialize modifier {modStruct}: {e}")
        
        # Only update the UI if the panel is currently visible
        if self.modifierPanelUI.modifiersPanelVisible:
            self.modifierPanelUI.updateLists()

    def setGroupState(self, groupId: int, members: list[list[int, int, int, bool]], capacity: int, minigameType: int):
        """
        Called from the AI when group state changes. This updates our local group state.
        """
        self.Notify.debug(f"setGroupState: Called with groupId={groupId}, members={len(members)}, capacity={capacity}, minigameType={minigameType}")
        
        # If groupId is NoGroup, we're leaving the group
        if groupId == GroupBase.NoGroup:
            self.Notify.debug(f"setGroupState: Leaving group, cleaning up")
            self.leaveGroup()
            return
        
        # Update modifiers button visibility
        self.__updateModifiersButtonVisibility()
        
        # Check if minigame type changed (before updating it)
        minigameTypeChanged = hasattr(self, 'minigameType') and self.minigameType != minigameType
        
        # Update group ID and minigame type
        self.groupId = groupId
        oldMinigameType = getattr(self, 'minigameType', None)
        self.minigameType = minigameType
        
        # Format members
        formattedMembers: list[GroupMemberStruct] = []
        leader = None
        for entry in members:
            member = GroupMemberStruct.from_struct(entry)
            if member.leader:
                leader = member
            formattedMembers.append(member)
        
        # Update group state
        super().setMembers(formattedMembers)
        self.setLeader(leader.avId if leader is not None else GroupBase.NoLeader)
        self.setCapacity(capacity)
        
        self.Notify.debug(f"setGroupState: Updated group state. Members: {self.getMemberIds()}, Leader: {self.getLeader()}, Minigame: {minigameType}")
        
        # Notify interface if minigame type changed
        # Always send the event to ensure UI updates, even if we think it didn't change
        # (sometimes the check might fail due to timing)
        if minigameTypeChanged or oldMinigameType is None:
            self.Notify.debug(f"setGroupState: Minigame type changed from {oldMinigameType} to {minigameType}, sending update event")
            messenger.send('group-minigame-updated')
        else:
            # Even if we think it didn't change, send the event anyway to ensure UI is in sync
            # This handles edge cases where the check might have failed
            self.Notify.debug(f"setGroupState: Minigame type appears unchanged ({minigameType}), but sending update event to ensure UI sync")
            messenger.send('group-minigame-updated')
        
        # Render the UI (this will also update the minigame label if interface exists)
        self.render()
        
        # Also directly update the minigame label if interface exists (backup to event system)
        # Note: __updateMinigameLabel is name-mangled, so we need to use the mangled name
        if hasattr(self, 'interface') and self.interface is not None:
            try:
                updateMethod = getattr(self.interface, '_GroupInterface__updateMinigameLabel', None)
                if updateMethod is not None:
                    updateMethod()
            except (AttributeError, TypeError):
                pass
    
    def leaveGroup(self):
        """
        Called when leaving a group. Cleans up UI and resets state.
        """
        self.Notify.debug(f"leaveGroup: Leaving group {self.groupId}")
        self.groupId = GroupBase.NoGroup
        self.setMembers([])
        self.setLeader(GroupBase.NoLeader)
        self.__deleteInterface()
    
    def __isInMinigame(self) -> bool:
        """
        Checks if the local avatar is currently in a minigame by looking for
        DistributedMinigame objects that include the local avatar in their participant list.
        This is only called when render() is invoked or place changes, not periodically.
        """
        if not hasattr(base, 'localAvatar') or base.localAvatar is None:
            return False
        
        localAvId = base.localAvatar.getDoId()
        
        # Check tracked minigames first (ones we know about)
        for minigame in list(self._trackedMinigames):
            if minigame not in self.cr.doId2do.values():
                # Minigame was deleted, remove from tracking
                self._trackedMinigames.discard(minigame)
                continue
            if hasattr(minigame, 'avIdList') and localAvId in minigame.avIdList:
                return True
        
        # Also check all distributed objects for any minigames we might have missed
        for do in list(self.cr.doId2do.values()):
            if isinstance(do, DistributedMinigame):
                self._trackedMinigames.add(do)
                if hasattr(do, 'avIdList') and localAvId in do.avIdList:
                    return True
        
        return False
    
    def render(self):
        """
        Renders the group UI if we're in a group and the local toon is a member.
        Only shows the interface when in a playground, not during minigames.
        """
        self.Notify.debug(f"render: Called. groupId={self.groupId}, isInGroup={self.isInGroup()}, members={self.getMemberIds()}")
        
        # No need to render if we're not in a group or local toon isn't a member
        if not self.isInGroup():
            self.Notify.debug(f"render: Not in group, deleting interface")
            self.__deleteInterface()
            return
        
        # Hide interface if we're in a minigame
        if self.__isInMinigame():
            self.Notify.debug(f"render: In minigame, hiding interface")
            self.__deleteInterface()
            return
        
        # Only show interface in playgrounds
        place = base.cr.playGame.getPlace()
        isInPlayground = place is not None and isinstance(place, Playground.Playground)
        
        if not isInPlayground:
            self.Notify.debug(f"render: Not in playground, hiding interface")
            self.__deleteInterface()
            return
        
        # Create interface if it doesn't exist
        if self.interface is None:
            self.Notify.debug(f"render: Creating new interface")
            self.__makeNewInterface()
        
        # Safety check: ensure interface is valid before updating
        if self.interface is None or not hasattr(self.interface, 'updateMembers'):
            self.Notify.debug(f"render: Interface not ready, skipping update")
            return
        
        # Explicitly show the interface to ensure it's visible
        # This is important during rapid transitions (e.g., instaLeave from purchase manager)
        if hasattr(self.interface, 'show'):
            self.interface.show()
        
        # Update interface with current members
        self.Notify.debug(f"render: Updating interface with {len(self.getMembers())} members")
        try:
            self.interface.updateMembers(self.getMembers())
            # Also update minigame button label to ensure it's in sync
            # Note: __updateMinigameLabel is name-mangled, so we need to use the mangled name
            # The event system should handle it, but we call it directly as backup
            try:
                # Access the name-mangled method directly
                updateMethod = getattr(self.interface, '_GroupInterface__updateMinigameLabel', None)
                if updateMethod is not None:
                    updateMethod()
            except (AttributeError, TypeError):
                # Method doesn't exist or can't be called, that's okay - event system should handle it
                pass
        except (IndexError, AttributeError) as e:
            self.Notify.warning(f"render: Error updating interface members: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            self.Notify.error(f"render: Unexpected error updating interface: {e}")
            import traceback
            traceback.print_exc()
            # If update fails, try to recreate the interface
            self.__deleteInterface()
            if self.isInGroup():
                self.__makeNewInterface()
        # Update modifiers button visibility when members change
        self.__updateModifiersButtonVisibility()
    
    def __hookMinigameSetParticipants(self):
        """
        Hooks into DistributedMinigame.setParticipants to detect when the local avatar joins a minigame.
        This allows us to hide the interface immediately when joining, without periodic checks.
        """
        originalSetParticipants = DistributedMinigame.setParticipants
        
        def hookedSetParticipants(self_minigame, avIds):
            # Call the original method
            result = originalSetParticipants(self_minigame, avIds)
            
            # Check if local avatar is in the participants
            if hasattr(base, 'localAvatar') and base.localAvatar:
                localAvId = base.localAvatar.getDoId()
                if localAvId in avIds:
                    # Track this minigame
                    if hasattr(base.cr, 'groupManager') and base.cr.groupManager:
                        base.cr.groupManager._trackedMinigames.add(self_minigame)
                        # Hide interface if we're in a group
                        if base.cr.groupManager.isInGroup():
                            base.cr.groupManager.render()
            
            return result
        
        # Replace the method
        DistributedMinigame.setParticipants = hookedSetParticipants
    
    def __onPlaceChanged(self):
        """
        Called when the place changes. Re-renders the interface if we're in a group.
        This ensures the interface is shown/hidden when entering/exiting minigames or playgrounds.
        """
        # When entering a playground, request group state refresh to ensure we have the latest data
        place = base.cr.playGame.getPlace()
        isInPlayground = place is not None and isinstance(place, Playground.Playground)
        
        if isInPlayground and self.isInGroup():
            # Request group state refresh to ensure we have the latest data
            # This handles cases where we return from purchase manager and state might be stale
            self.Notify.debug(f"__onPlaceChanged: Entered playground, requesting group state refresh")
            # The server should automatically send group state when status is updated,
            # but we'll also trigger render after a short delay to ensure state is received
            # Use a longer delay for instaLeave cases to ensure place is fully initialized
            taskMgr.doMethodLater(0.2, self.__delayedRender, self.uniqueName('delayedRender'))
        
        if self.isInGroup():
            # Also render immediately, but the delayed render will catch cases where
            # the place isn't fully initialized yet (e.g., instaLeave transitions)
            self.render()
    
    def __delayedRender(self, task):
        """Delayed render to ensure group state has been received and place is fully initialized"""
        if self.isInGroup():
            place = base.cr.playGame.getPlace()
            isInPlayground = place is not None and isinstance(place, Playground.Playground)
            if isInPlayground:
                self.Notify.debug(f"__delayedRender: Rendering interface after state refresh (place fully initialized)")
                self.render()
            else:
                # Place still not ready, try again after a short delay
                # Only retry a few times to avoid infinite loops
                retryCount = getattr(task, 'retryCount', 0)
                if retryCount < 5:  # Try up to 5 times (0.5 seconds total)
                    self.Notify.debug(f"__delayedRender: Place not ready yet, retrying in 0.1s (attempt {retryCount + 1}/5)")
                    newTask = taskMgr.doMethodLater(0.1, self.__delayedRender, self.uniqueName('delayedRender'))
                    newTask.retryCount = retryCount + 1
                    return task.done
                else:
                    self.Notify.warning(f"__delayedRender: Place not ready after 5 attempts, giving up")
        return task.done
    
    def __makeNewInterface(self):
        """
        Creates a new GroupInterface. This is a client-side only UI element.
        """
        self.Notify.debug(f"__makeNewInterface: Creating new GroupInterface")
        self.__deleteInterface()
        try:
            # Create a simple wrapper object for the interface
            # The interface expects something with getLeader(), getMembers(), minigameType
            self.interface = GroupInterface(self)
            self.going_text = DirectLabel(parent=base.a2dBottomCenter, pos=(0, 0, .3), text='', textMayChange=1, text_scale=.15,
                        text_shadow=(0, 0, 0, 1), text_fg=(.15, .9, .15, 1), text_font=ToontownGlobals.getCompetitionFont())
            
            # Debug button for group data - positioned in top right (same as minigame and purchase manager)
            from direct.gui.DirectButton import DirectButton
            from direct.gui.DirectGui import DGG
            self.debugGroupButton = DirectButton(
                parent=base.a2dTopRight,
                pos=(-0.15, 0, -0.1),
                scale=0.06,
                text='Debug Group',
                text_scale=0.5,
                text_fg=(1, 1, 1, 1),
                text_shadow=(0, 0, 0, 1),
                frameColor=(0.2, 0.2, 0.2, 0.8),
                relief=DGG.RAISED,
                command=self.requestGroupDebug
            )
            
            # Modifiers button - positioned at top left of screen, outside group interface
            # Only visible to the leader
            model = loader.loadModel(GroupInterface.GUI_MODEL_PATH)
            selectGameTexture = model.find('**/button-selectgame')
            uiFont2 = loader.loadFont('phase_3/models/fonts/Vipnagorgialla-Bd-It.otf')
            from toontown.ui.UIHelpers import px_to_scale
            self.modifiersButton = DirectButton(
                parent=base.a2dTopLeft,
                text='Modifiers',
                text_font=uiFont2,
                text_fg=(1, 1, 1, 1),
                text_shadow=(0, 0, 0, 1),
                text_scale=(0.06, 0.06, 1),  # Smaller text
                text_pos=(-0.018, -0.02, 0),
                image_scale=px_to_scale(200, 50),  # Smaller button
                pos=(0.3, 0, -0.08),  # More to the right, slightly smaller offset
                relief=None,
                image=selectGameTexture,
                command=self.__onModifiersClicked
            )
            model.removeNode()
            self.__updateModifiersButtonVisibility()
            
            # Explicitly show the interface to ensure it's visible
            # This is important during rapid transitions (e.g., instaLeave from purchase manager)
            if hasattr(self.interface, 'show'):
                self.interface.show()
            
            self.Notify.debug(f"__makeNewInterface: Interface created successfully")
        except Exception as e:
            self.Notify.error(f"__makeNewInterface: Failed to create interface: {e}")
            import traceback
            traceback.print_exc()
    
    def __deleteInterface(self):
        """
        Deletes the group interface UI.
        """
        if self.interface is not None:
            self.interface.destroy()
            self.interface = None
        
        # Clean up modifier panel UI if it exists
        if hasattr(self, 'modifierPanelUI'):
            self.modifierPanelUI.destroy()
            del self.modifierPanelUI
        if self.going_text is not None:
            self.going_text.destroy()
            self.going_text = None
        if hasattr(self, 'debugGroupButton') and self.debugGroupButton is not None:
            self.debugGroupButton.destroy()
            self.debugGroupButton = None
        if self.modifiersButton is not None:
            self.modifiersButton.destroy()
            self.modifiersButton = None

    def sendInvite(self, sender: int, groupId: int):

        inviter = self.cr.getDo(sender)
        if inviter is None:
            return

        self.destroyCurrentInvitePanel()

        # Get leader ID - if we're in the group, use our leader, otherwise use sender
        leaderId = sender
        if self.isInGroup() and self.groupId == groupId:
            leaderId = self.getLeader()

        self.currentInvite = GroupInvitee()
        self.currentInvite.make(inviter, leaderId)
    
    def getCurrentGroup(self):
        """
        DEPRECATED: For backwards compatibility. Returns self if in a group, None otherwise.
        Use isInGroup() and direct GroupBase methods instead.
        """
        return self if self.isInGroup() else None
    
    def requestGroupDebug(self):
        """
        Request group debug data to be printed on both client and AI.
        This can be called from anywhere (GroupInterface, Purchase Manager, etc.)
        """
        if not self.isInGroup():
            self.Notify.info('Not in a group - cannot show debug data')
            return
        
        # Print client-side data
        self.Notify.info('\n' + '=' * 80)
        self.Notify.info('CLIENT GROUP DEBUG DATA')
        self.Notify.info('=' * 80)
        
        from toontown.toonbase import ToontownGlobals
        from toontown.groups import GroupGlobals
        
        # Basic Group Info
        self.Notify.info('\nBASIC GROUP INFO')
        self.Notify.info('  Group ID: %s' % self.groupId)
        self.Notify.info('  In Group: %s' % ('Yes' if self.isInGroup() else 'No'))
        self.Notify.info('  Leader: %s' % self.getLeader())
        self.Notify.info('  Capacity: %s / %s' % (self.getMemberCount(), self.getCapacity()))
        
        # Minigame Info
        minigameName = ToontownGlobals.MinigameId2Name.get(self.minigameType, f'Unknown ({self.minigameType})')
        self.Notify.info('\nMINIGAME INFO')
        self.Notify.info('  Type: %s (ID: %s)' % (minigameName, self.minigameType))
        
        # Members
        members = self.getMembers()
        self.Notify.info('\nMEMBERS (%s)' % len(members))
        if not members:
            self.Notify.info('  (No members)')
        else:
            for i, member in enumerate(members, 1):
                teamStr = 'Spectator' if member.team == GroupGlobals.TEAM_SPECTATOR else 'Participant'
                statusStr = {GroupGlobals.STATUS_LEADER: 'Leader', 
                            GroupGlobals.STATUS_READY: 'Ready',
                            GroupGlobals.STATUS_UNREADY: 'Not Ready'}.get(member.status, f'Status {member.status}')
                leaderStr = ' (Leader)' if member.leader else ''
                self.Notify.info('  %s. avId: %s - %s, %s%s' % (i, member.avId, teamStr, statusStr, leaderStr))
        
        self.Notify.info('\n' + '=' * 80)
        self.Notify.info('(See AI-side output for full minigame config details)')
        self.Notify.info('=' * 80 + '\n')
        
        # Request AI-side debug data
        # First try to use GroupManager's direct method
        self.d_requestGroupDebug()
        
        # Also try minigame's requestGroupDebug if available (for when in minigame)
        if hasattr(base.cr, 'playGame') and base.cr.playGame.getPlace():
            place = base.cr.playGame.getPlace()
            if hasattr(place, 'fsm') and hasattr(place.fsm, 'getCurrentState'):
                state = place.fsm.getCurrentState()
                if state and hasattr(state, 'minigame'):
                    minigame = state.minigame
                    if minigame and hasattr(minigame, 'sendUpdate'):
                        minigame.sendUpdate('requestGroupDebug', [])
                        return
        
        # If not in minigame, try to find any minigame object
        for do in list(base.cr.doId2do.values()):
            if hasattr(do, '__class__') and 'Minigame' in do.__class__.__name__:
                if hasattr(do, 'sendUpdate') and hasattr(do, 'requestGroupDebug'):
                    do.sendUpdate('requestGroupDebug', [])
                    return

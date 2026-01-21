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
        if self.isInGroup() and self.getLeader() == base.localAvatar.getDoId():
            self.d_requestMinigameSwitch(minigameId)

    def updateStatus(self, code: int):

        self.Notify.debug(f"Updating local av status to {code} for current group")

        # Don't send codes unless they are ready/unready codes.
        if code not in (GroupGlobals.STATUS_UNREADY, GroupGlobals.STATUS_READY):
            return

        # If we are the leader we don't need to update the ID. We are in charge of starting the group anyway.
        if self.isInGroup() and self.getLeader() == base.localAvatar.getDoId():
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
    
    def d_requestGroupDebug(self):
        """Request group debug data from AI"""
        self.sendUpdate('requestGroupDebug', [])
    
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
        """
        self.Notify.debug(f"setMinigameType: Called with minigameType={minigameType}")
        self.minigameType = minigameType
        messenger.send('group-minigame-updated')

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
        
        # Check if minigame type changed
        minigameTypeChanged = hasattr(self, 'minigameType') and self.minigameType != minigameType
        
        # Update group ID
        self.groupId = groupId
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
        
        self.Notify.debug(f"setGroupState: Updated group state. Members: {self.getMemberIds()}, Leader: {self.getLeader()}")
        
        # Notify interface if minigame type changed
        if minigameTypeChanged:
            messenger.send('group-minigame-updated')
        
        # Render the UI
        self.render()
    
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
        
        # Update interface with current members
        self.Notify.debug(f"render: Updating interface with {len(self.getMembers())} members")
        self.interface.updateMembers(self.getMembers())
    
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
        if self.isInGroup():
            self.render()
    
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
        if self.going_text is not None:
            self.going_text.destroy()
            self.going_text = None
        if hasattr(self, 'debugGroupButton') and self.debugGroupButton is not None:
            self.debugGroupButton.destroy()
            self.debugGroupButton = None

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

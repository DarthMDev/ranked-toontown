from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.distributed.DistributedObjectGlobalAI import DistributedObjectGlobalAI

from toontown.groups import GroupGlobals
from toontown.groups.Group import Group
from toontown.groups.GroupMemberStruct import GroupMemberStruct
from toontown.groups.GroupOperationResult import GroupOperationResult
from toontown.groups.GroupBase import GroupBase
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.toonbase import ToontownGlobals


class GroupManagerAI(DistributedObjectGlobalAI):
    """
    An instance on the district that is responsible for managing separate groups.
    A "group" can be thought of as a "party" on other games, or even a "lobby".

    Toons will be in a group with other toons while a leader/host sets up game rules and eventually
    sends the entire group into some instance. (In our case, the trolley with specific settings.)

    This class is responsible for creating, destroying, and managing groups.
    Only one of these instances should exist per zone, or this could even be a singleton global object.
    """

    Notify = DirectNotifyGlobal.directNotify.newCategory('GroupManagerAI')

    def __init__(self, air):
        super().__init__(air)
        self.groups: list[Group] = []

    def generate(self):
        super().generate()
        self.Notify.setDebug(True)
        self.Notify.info("Starting up...")
        self.accept('avatarExited', self.__handleUnexpectedExit)

    def delete(self):
        DistributedObjectAI.delete(self)
        self.Notify.info("Shutting down...")
        self.ignore('avatarExited')

        for group in self.groups:
            group.delete()

        self.groups.clear()

    def getGroup(self, toon: DistributedToonAI) -> Group | None:
        """
        Gets the current group this toon is in. Returns None if this toon is not in the group.
        """
        for group in self.groups:
            if toon.getDoId() in group.getMemberIds():
                return group

        return None

    def createGroup(self, leader: DistributedToonAI) -> Group:
        """
        Creates a new group on the toon. Returns the new group.
        If this toon is already in a group, the old one will be returned.
        This toon cannot be in two different groups.
        """

        group = self.getGroup(leader)
        if group is not None:
            self.Notify.debug(f"createGroup: Leader {leader.getDoId()} already in group")
            return group

        # Create a new group! (Not a distributed object, just a GroupBase instance)
        self.Notify.debug(f"createGroup: Creating new group for leader {leader.getDoId()}")
        group = Group(self.air, leader)
        self.groups.append(group)
        
        # Generate a unique group ID for reference (not a DO ID)
        group.groupId = self.air.allocateChannel()
        self.Notify.debug(f"createGroup: Created group with ID {group.groupId}")

        # Setup the required state.
        members = group.getMembers()
        self.Notify.debug(f"createGroup: Group {group.groupId} has {len(members)} members: {[m.avId for m in members]}")
        group.b_setCapacity(group.DefaultCapacity)
        
        # Send group state to the leader through the global GroupManager
        self.Notify.debug(f"createGroup: Sending group state to {leader.getDoId()} for group {group.groupId}")
        self.d_setGroupState(leader.getDoId(), group.groupId, members, group.getCapacity(), group.desiredMinigame)
        return group

    def deleteGroup(self, group: Group):
        """
        Deletes a group and notifies all members.
        """
        # Notify all members that they're leaving the group
        for avId in group.getMemberIds():
            self.d_setGroupState(avId, GroupBase.NoGroup, [], 0, 0)
        
        if group in self.groups:
            self.groups.remove(group)

    def __handleUnexpectedExit(self, toon):
        group = self.getGroup(toon)
        if group is None:
            return

        removed = group.removeMember(toon.getDoId())
        group.b_setMembers(group.getMembers())
        if removed:
            group.announce(f"{toon.getName()} has logged out. Removing them from the group.")
            if len(group.getMembers()) == 0:
                self.deleteGroup(group)

    def __canJoinGroup(self, inviter: int, recipient: int) -> GroupOperationResult:

        # Do both toons exist?
        inviterToon = self.air.getDo(inviter)
        recipientToon = self.air.getDo(recipient)
        if None in (inviterToon, recipientToon):
            return GroupOperationResult.NONEXISTENT_TOON

        # Are we queueing?
        if self.air.matchmaker.isPlayerInQueue(inviterToon):
            return GroupOperationResult.SELF_QUEUE

        # First case, is this the same person?
        if inviter == recipient:
            return GroupOperationResult.IS_SAME_PERSON

        # Is the recipient queueing?
        if self.air.matchmaker.isPlayerInQueue(recipientToon):
            return GroupOperationResult.IN_QUEUE

        # Grab the groups of both members.
        inviterGroup = self.getGroup(inviterToon)
        recipientGroup = self.getGroup(recipientToon)

        # Are both toons not in a group?
        if inviterGroup is None and recipientGroup is None:
            return GroupOperationResult.SUCCESS_BOTH_GROUPLESS

        # Are both toons in the same group already?
        if inviterGroup is recipientGroup:
            return GroupOperationResult.ALREADY_PRESENT

        # Now that we know that the groups are two separate values, is the recipient in a different group?
        if recipientGroup is not None and inviterGroup is not recipientGroup:
            return GroupOperationResult.ALREADY_IN_GROUP

        # Is the group full?
        if inviterGroup.isFull():
            return GroupOperationResult.GROUP_FULL

        # Is the group on cooldown from starting?
        if inviterGroup.onCooldown():
            return GroupOperationResult.GROUP_STARTING

        # Ran through all the conditions. This should be a success.
        return GroupOperationResult.SUCCESS


    """
    Astron Methods (Outgoing)
    """

    def d_setGroupState(self, avId: int, groupId: int, members: list[GroupMemberStruct], capacity: int, minigameType: int):
        """
        Sends the complete group state to a client through the global GroupManager.
        """
        self.Notify.debug(f"d_setGroupState: Sending group state to avatar {avId} for group {groupId} with {len(members)} members")
        memberStructs = [m.to_struct() for m in members]
        self.sendUpdateToAvatarId(avId, "setGroupState", [groupId, memberStructs, capacity, minigameType])
    
    def d_setMinigameZone(self, avId: int, zoneId: int, gameId: int):
        """
        Sends minigame zone information to a client through the global GroupManager.
        """
        self.Notify.debug(f"d_setMinigameZone: Sending minigame zone to avatar {avId}: zone={zoneId}, gameId={gameId}")
        self.sendUpdateToAvatarId(avId, "setMinigameZone", [zoneId, gameId])
    
    def d_setCurrentGroup(self, avId: int, groupId: int):
        """
        DEPRECATED: Use d_setGroupState instead. Kept for backwards compatibility.
        """
        self.Notify.debug(f"d_setCurrentGroup: DEPRECATED - Sending setCurrentGroup to avatar {avId} for group {groupId}")
        self.sendUpdateToAvatarId(avId, "setCurrentGroup", [groupId])

    """
    Astron Methods (Incoming)
    """
    def requestKick(self, toKickId: int):

        leaderId: int = self.air.getAvatarIdFromSender()
        leader = self.air.getDo(leaderId)
        if leader is None:
            return

        # Is the leader in a group?
        group = self.getGroup(leader)
        if group is None:
            return

        # Is the leader in the same group as the other toon?
        if toKickId not in group.getMemberIds():
            return

        # Is the leader actually a leader? Only check this if the person is not kicking themselves.
        if leaderId != toKickId and group.getLeader() != leader.getDoId():
            return

        if group.onCooldown():
            return

        if toKickId == leaderId:
            group.announce(f"{leader.getName()} has chose to leave the group.")
        else:
            name = toKickId
            if self.air.getDo(toKickId) is not None:
                name = self.air.getDo(toKickId).getName()
            group.announce(f"{leader.getName()} has kicked {name} from the group.")

        # This is a valid operation.
        group.removeMember(toKickId)
        
        # Notify the kicked member they're leaving the group
        self.d_setGroupState(toKickId, GroupBase.NoGroup, [], 0, 0)
        
        # Update remaining members
        if len(group.getMembers()) > 0:
            group.b_setMembers(group.getMembers())
        else:
            # Group is empty, delete it
            self.deleteGroup(group)

    def invitePlayer(self, toInviteId: int):

        inviterId: int = self.air.getAvatarIdFromSender()

        # What would happen if we attempted to add this toon to the group?
        result = self.__canJoinGroup(inviterId, toInviteId)
        inviter = self.air.getDo(inviterId)
        otherToon = self.air.getDo(toInviteId)

        match result:

            # Is this invite allowed to go through?
            case GroupOperationResult.SUCCESS | GroupOperationResult.SUCCESS_BOTH_GROUPLESS:
                group = self.getGroup(inviter)
                self.sendUpdateToAvatarId(toInviteId, "sendInvite", [inviterId, group.groupId if group is not None else 0])
                if group is not None:
                    group.announce(f"{inviter.getName()} has invited {otherToon.getName()}.")
                else:
                    inviter.d_setSystemMessage(0, f"Asking {otherToon.getName()} if they want to start a group with you!")

            # Is this toon inviting themselves?
            case GroupOperationResult.IS_SAME_PERSON:
                self.Notify.debug(f"invitePlayer: Toon {inviterId} is inviting themselves (IS_SAME_PERSON)")
                group = self.getGroup(inviter)
                # If this toon is in a group it would not make sense to invite them.
                if group is not None:
                    self.Notify.debug(f"invitePlayer: Toon {inviterId} already in group {group.groupId}")
                    inviter.d_setSystemMessage(0, f"You are already in a group. Why are you inviting yourself?")
                    return

                # This is valid! Start a group with ourselves...
                self.Notify.debug(f"invitePlayer: Creating new group for toon {inviterId}")
                group = self.createGroup(inviter)
                self.Notify.debug(f"invitePlayer: Created group {group.groupId}, sending group state to {inviterId}")
                self.d_setGroupState(inviterId, group.groupId, group.getMembers(), group.getCapacity(), group.desiredMinigame)
                group.announce(f"Started a new group!")

            # Failed?
            case _:
                group = self.getGroup(inviter)
                if group is not None:
                    group.announce(f"{inviter.getName()} tried to invite {otherToon.getName()} but {result.value}.")
                else:
                    inviter.d_setSystemMessage(0, f"Can't invite this toon to a group because {result.value}.")

    def inviteResponse(self, inviterId: int, decision: bool):

        inviter = self.air.getDo(inviterId)
        if inviter is None:
            return

        deciderId: int = self.air.getAvatarIdFromSender()
        invited = self.air.getDo(deciderId)
        if invited is None:
            return

        group = self.getGroup(inviter)

        # Have they declined the invite?
        if not decision:
            msg = f"{invited.getName()} has declined the invite."
            if group is not None:
                group.announce(msg)
            else:
                inviter.d_setSystemMessage(0, msg)
            return

        # They accepted. Can they join?
        result = self.__canJoinGroup(inviterId, deciderId)
        match result:

            # Both toons groupless?
            case GroupOperationResult.SUCCESS_BOTH_GROUPLESS:
                group = self.createGroup(inviter)
                group.addMember(invited.getDoId())
                group.b_setMembers(group.getMembers())
                # State already broadcast by b_setMembers, but also send to the new member
                self.d_setGroupState(deciderId, group.groupId, group.getMembers(), group.getCapacity(), group.desiredMinigame)
                group.announce(f"{inviter.getName()} has started a group with {invited.getName()}")

            # Normal invite to a group?
            case GroupOperationResult.SUCCESS:
                group = self.getGroup(inviter)
                group.addMember(deciderId)
                group.b_setMembers(group.getMembers())
                # State already broadcast by b_setMembers, but also send to the new member
                self.d_setGroupState(deciderId, group.groupId, group.getMembers(), group.getCapacity(), group.desiredMinigame)
                group.announce(f"{invited.getName()} has joined the group!")

            # Failed?
            case _:
                group = self.getGroup(inviter)
                if group is not None:
                    group.announce(f"{invited.getName()} tried to join the group but {result.value}.")

    def requestPromote(self, toPromoteId: int):

        leaderId: int = self.air.getAvatarIdFromSender()
        leader = self.air.getDo(leaderId)
        if leader is None:
            return

        toPromote = self.air.getDo(toPromoteId)
        if toPromote is None:
            return

        # Are the two users in the same group?
        leadersGroup = self.getGroup(leader)
        if leadersGroup is None or toPromoteId not in leadersGroup.getMemberIds():
            return

        # Is the leader actually the leader?
        if leadersGroup.getLeader() != leaderId:
            return

        if leadersGroup.onCooldown():
            return

        # This is a valid operation. Swap the two members places and update their statuses and leader variable.
        memberIds = leadersGroup.getMemberIds()
        members = leadersGroup.getMembers()
        oldToPromoteIndex = memberIds.index(toPromoteId)
        oldLeaderIndex = memberIds.index(leaderId)
        oldLeader = members[oldLeaderIndex]
        newLeader = members[oldToPromoteIndex]
        newLeader.status = GroupGlobals.STATUS_LEADER
        newLeader.leader = True
        oldLeader.status = GroupGlobals.STATUS_READY
        oldLeader.leader = False
        members[oldLeaderIndex] = newLeader
        members[oldToPromoteIndex] = oldLeader
        leadersGroup.setLeader(toPromoteId)
        leadersGroup.b_setMembers(members)
        leadersGroup.announce(f"{leader.getName()} has promoted {toPromote.getName()} to the group leader!")

    def requestTeamSwap(self, avId: int):

        requester: int = self.air.getAvatarIdFromSender()
        leader = self.air.getDo(requester)
        if leader is None:
            return

        toSwap = self.air.getDo(avId)
        if toSwap is None:
            return

        # Are the two users in the same group?
        leadersGroup = self.getGroup(leader)
        if leadersGroup is None or avId not in leadersGroup.getMemberIds():
            return

        # We can only allow this operation if the user is the leader or they are acting on themselves.
        selfSwap = avId == requester
        isLeader = leadersGroup.getLeader() == requester
        if not (selfSwap or isLeader):
            return

        if leadersGroup.onCooldown():
            return

        # Allow this operation.
        teamCycle = (GroupGlobals.TEAM_SPECTATOR, GroupGlobals.TEAM_FFA)
        memberIndex = leadersGroup.getMemberIds().index(avId)
        oldTeam = leadersGroup.members[memberIndex].team
        oldTeamIndex = teamCycle.index(oldTeam)
        newTeamIndex = oldTeamIndex + 1
        if newTeamIndex >= len(teamCycle):
            newTeamIndex = 0
        leadersGroup.members[memberIndex].team = teamCycle[newTeamIndex]

        leadersGroup.b_setMembers(leadersGroup.getMembers())

    def requestStart(self):
        requesterId = self.air.getAvatarIdFromSender()
        requester = self.air.getDo(requesterId)
        if requester is None:
            return

        group = self.getGroup(requester)
        if group is None:
            return

        # Is this the group leader?
        if group.getLeader() != requesterId:
            return

        # Is everyone ready?
        notReady = group.getNumPlayersNotReady()
        if notReady > 0:
            group.announce(f"{requester.getName()} wants to start the activity but {notReady} toon{'s' if notReady > 1 else ''} {'are' if notReady > 1 else 'is'} not ready!")
            return

        if len(group.getSpectators()) >= len(group.getMembers()):
            group.announce(f"{requester.getName()} wants to start the activity but everyone is spectating!")
            return

        group.startActivity()

    def updateStatus(self, code):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.getDo(avId)
        if av is None:
            return

        group = self.getGroup(av)
        if group is None:
            return

        # Don't update statuses unless they are ready/unready codes.
        if code not in (GroupGlobals.STATUS_UNREADY, GroupGlobals.STATUS_READY):
            return

        # Don't update the status if it's the leader. It doesn't matter.
        if avId == group.getLeader():
            return

        # Update the status and re update the members.
        member = group.getMember(avId)
        shouldUpdate = member.status != code
        member.status = code

        if shouldUpdate:
            group.b_setMembers(group.getMembers())

    def requestMinigameSwitch(self, minigameId: int):

        requesterId = self.air.getAvatarIdFromSender()
        requester = self.air.getDo(requesterId)
        if requester is None:
            return

        group = self.getGroup(requester)
        if group is None:
            return

        # Is this the group leader?
        if group.getLeader() != requesterId:
            return

        # Valid minigame?
        if minigameId not in ToontownGlobals.ValidMinigameIds:
            return

        # Already starting?
        if group.onCooldown():
            return

        group.b_setMinigameType(minigameId)
        group.announce(f"{requester.getName()} has changed to the {ToontownGlobals.MinigameId2Name.get(minigameId)} game!")
    
    def requestGroupDebug(self):
        """
        Called from client to request group debug data to be printed on AI.
        This allows debug to be requested from playground, purchase manager, or minigame.
        """
        avId = self.air.getAvatarIdFromSender()
        toon = self.air.getDo(avId)
        if toon is None:
            self.Notify.info('Avatar %s not found for group debug request!' % avId)
            return
        
        group = self.getGroup(toon)
        if group is None:
            self.Notify.info('Avatar %s (%s) is not in any group' % (avId, toon.getName()))
            self.Notify.info('Total groups: %s' % len(self.groups))
            if self.groups:
                for idx, g in enumerate(self.groups, 1):
                    leader = self.air.getDo(g.getLeader())
                    leaderName = leader.getName() if leader else 'Unknown'
                    self.Notify.info('  Group %s: groupId=%s, leader=%s (%s), members=%s' % 
                                   (idx, g.groupId, leaderName, g.getLeader(), len(g.getMemberIds())))
            return
        
        # Use the same debug output as DistributedMinigameAI
        from toontown.toonbase import ToontownGlobals
        from toontown.groups import GroupGlobals
        
        self.Notify.info('\n' + '=' * 80)
        self.Notify.info('AI GROUP DEBUG DATA (requested by avatar %s - %s)' % (avId, toon.getName()))
        self.Notify.info('=' * 80)
        
        # Basic Group Info
        self.Notify.info('\nBASIC GROUP INFO')
        self.Notify.info('  Group ID: %s' % group.groupId)
        leader = self.air.getDo(group.getLeader())
        leaderName = leader.getName() if leader else 'Unknown'
        self.Notify.info('  Leader: %s (%s)' % (leaderName, group.getLeader()))
        self.Notify.info('  Capacity: %s / %s' % (group.getMemberCount(), group.getCapacity()))
        self.Notify.info('  On Cooldown: %s' % ('Yes' if group.onCooldown() else 'No'))
        
        # Members
        members = group.getMembers()
        participants = [m for m in members if m.team != GroupGlobals.TEAM_SPECTATOR]
        spectators = [m for m in members if m.team == GroupGlobals.TEAM_SPECTATOR]
        
        self.Notify.info('\nMEMBERS (%s total)' % len(members))
        self.Notify.info('  Participants: %s' % len(participants))
        self.Notify.info('  Spectators: %s' % len(spectators))
        
        if members:
            for i, member in enumerate(members, 1):
                toon = self.air.getDo(member.avId)
                toonName = toon.getName() if toon else 'Unknown'
                teamStr = 'Spectator' if member.team == GroupGlobals.TEAM_SPECTATOR else 'Participant'
                statusStr = {GroupGlobals.STATUS_LEADER: 'Leader', 
                            GroupGlobals.STATUS_READY: 'Ready',
                            GroupGlobals.STATUS_UNREADY: 'Not Ready'}.get(member.status, f'Status {member.status}')
                self.Notify.info('    %s. %s (%s) - %s, %s' % (i, toonName, member.avId, teamStr, statusStr))
        
        # Minigame Config
        config = group.getMinigameConfig()
        minigameName = ToontownGlobals.MinigameId2Name.get(config.minigameId, f'Unknown ({config.minigameId})')
        
        self.Notify.info('\nMINIGAME CONFIG')
        self.Notify.info('  Minigame: %s (ID: %s)' % (minigameName, config.minigameId))
        self.Notify.info('  Trolley Zone: %s' % config.trolleyZone)
        host = self.air.getDo(config.hostId) if config.hostId else None
        hostName = host.getName() if host else 'Unknown'
        self.Notify.info('  Host: %s (%s)' % (hostName, config.hostId))
        self.Notify.info('  Desired Minigame (legacy): %s' % group.desiredMinigame)
        
        # Ruleset Data
        rulesetStruct = config.getRuleset(config.minigameId)
        if rulesetStruct is not None:
            self.Notify.info('\nRULESET DATA')
            if config.minigameId == ToontownGlobals.CraneGameId:
                try:
                    from toontown.minigame.craning import CraneGameGlobals
                    ruleset = CraneGameGlobals.CraneGameRuleset.fromStruct(rulesetStruct)
                    self.Notify.info('  CFO Max HP: %s' % ruleset.CFO_MAX_HP)
                    self.Notify.info('  Timer Mode: %s' % ('Yes' if ruleset.TIMER_MODE else 'No'))
                    if ruleset.TIMER_MODE:
                        self.Notify.info('  Timer Limit: %s seconds' % ruleset.TIMER_MODE_TIME_LIMIT)
                    self.Notify.info('  Side Cranes: %s' % ('Yes' if ruleset.WANT_SIDECRANES else 'No'))
                    self.Notify.info('  Drones: %s' % ('Yes' if ruleset.WANT_DRONES else 'No'))
                    self.Notify.info('  Back Wall: %s' % ('Yes' if ruleset.WANT_BACKWALL else 'No'))
                    self.Notify.info('  Remove Impact Cap: %s' % ('Yes' if ruleset.REMOVE_IMPACT_CAP else 'No'))
                except Exception as e:
                    self.Notify.info('  (Error deserializing ruleset: %s)' % e)
                    self.Notify.info('  Raw struct length: %s' % len(rulesetStruct))
            else:
                self.Notify.info('  (Ruleset data present but format unknown for this minigame)')
                self.Notify.info('  Raw struct length: %s' % len(rulesetStruct))
        else:
            self.Notify.info('\nRULESET DATA: None (using defaults)')
        
        # Modifiers Data
        modifierStructs = config.getModifiers(config.minigameId)
        if modifierStructs:
            self.Notify.info('\nMODIFIERS (%s)' % len(modifierStructs))
            if config.minigameId == ToontownGlobals.CraneGameId:
                try:
                    from toontown.minigame.craning import CraneGameGlobals
                    for i, modStruct in enumerate(modifierStructs, 1):
                        modifier = CraneGameGlobals.CFORulesetModifierBase.fromStruct(modStruct)
                        tierStr = ' (Tier %s)' % modifier.tier if modifier.tier > 1 else ''
                        self.Notify.info('    %s. %s%s' % (i, modifier.getName(), tierStr))
                except Exception as e:
                    self.Notify.info('  (Error deserializing modifiers: %s)' % e)
                    for i, modStruct in enumerate(modifierStructs, 1):
                        self.Notify.info('    %s. Raw struct: %s' % (i, modStruct))
            else:
                self.Notify.info('  (Modifiers present but format unknown for this minigame)')
                for i, modStruct in enumerate(modifierStructs, 1):
                    self.Notify.info('    %s. Raw struct: %s' % (i, modStruct))
        else:
            self.Notify.info('\nMODIFIERS: None')
        
        # Extra Config
        extraConfig = config.getExtraConfig(config.minigameId)
        if extraConfig:
            self.Notify.info('\nEXTRA CONFIG')
            for key, value in extraConfig.items():
                self.Notify.info('  %s: %s' % (key, value))
        else:
            self.Notify.info('\nEXTRA CONFIG: None')
        
        # Stored data for other minigames
        otherMinigames = set(config.rulesetData.keys()) | set(config.modifiersData.keys()) | set(config.extraConfig.keys())
        otherMinigames.discard(config.minigameId)
        if otherMinigames:
            self.Notify.info('\nSTORED DATA FOR OTHER MINIGAMES')
            for mgId in otherMinigames:
                mgName = ToontownGlobals.MinigameId2Name.get(mgId, f'Unknown ({mgId})')
                hasRuleset = mgId in config.rulesetData
                hasModifiers = mgId in config.modifiersData and len(config.modifiersData[mgId]) > 0
                hasExtra = mgId in config.extraConfig and len(config.extraConfig[mgId]) > 0
                flags = []
                if hasRuleset:
                    flags.append('Ruleset')
                if hasModifiers:
                    flags.append('%s Modifiers' % len(config.modifiersData[mgId]))
                if hasExtra:
                    flags.append('Extra Config')
                self.Notify.info('  %s (ID: %s): %s' % (mgName, mgId, ', '.join(flags) if flags else 'No data'))
        
        # Group Manager Stats
        self.Notify.info('\nGROUP MANAGER STATS')
        self.Notify.info('  Total groups: %s' % len(self.groups))
        
        self.Notify.info('\n' + '=' * 80 + '\n')
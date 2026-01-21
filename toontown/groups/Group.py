import time

from toontown.groups import GroupGlobals
from toontown.groups.GroupBase import GroupBase
from toontown.groups.GroupMemberStruct import GroupMemberStruct
from toontown.groups.GroupMinigameConfig import GroupMinigameConfig
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.toonbase import ToontownGlobals


class Group(GroupBase):
    """
    Represents a group on the AI side. This is NOT a distributed object.
    Group state is sent to clients through the global GroupManagerAI.
    """

    def __init__(self, air, leader: DistributedToonAI):
        GroupBase.__init__(self, leader.getDoId())
        self.air = air
        self.groupId = 0  # Will be set when group is created
        self.activityStartCooldown = 0
        
        # Initialize minigame config with default values
        leaderZone = leader.zoneId if leader else 0
        self.minigameConfig = GroupMinigameConfig(
            minigameId=ToontownGlobals.CraneGameId,
            trolleyZone=leaderZone,
            hostId=leader.getDoId()
        )
        
        # Backward compatibility - keep desiredMinigame for now
        self.desiredMinigame = ToontownGlobals.CraneGameId

    def getToons(self):
        """
        Returns a list of DistributedToonAI instances in this group.
        """
        dos = []
        for doId in self.getMemberIds():
            toon = self.air.getDo(doId)
            if toon is None:
                continue

            dos.append(toon)

        return dos

    def getSpectators(self) -> list[int]:
        return [member.avId for member in self.getMembers() if member.team == GroupGlobals.TEAM_SPECTATOR]

    def announce(self, message: str) -> None:
        """
        Announces a message to all members in the group.
        """
        for avId in self.getMemberIds():
            toon = self.air.getDo(avId)
            if toon:
                toon.d_setSystemMessage(0, message)

    def onCooldown(self) -> bool:
        if self.activityStartCooldown > time.time():
            return True
        return False

    def startActivity(self) -> None:

        if self.onCooldown():
            return

        self.announce("Activity starting...")
        self.activityStartCooldown = time.time() + 6
        
        # Update config with current leader zone (in case leader changed zones)
        leader = self.air.getDo(self.getLeader())
        if leader:
            self.minigameConfig.updateTrolleyZone(leader.zoneId)
            self.minigameConfig.updateHostId(self.getLeader())
        
        # Update minigame ID in config
        self.minigameConfig.updateMinigameId(self.desiredMinigame)
        
        # Create minigame - it will fetch all data from group
        minigame = self.air.minigameMgr.createMinigameFromGroup(self)
        self.d_setMinigameZone(minigame)

    """
    Methods to update group state and notify clients through GroupManagerAI
    """

    def b_setMembers(self, members: list[GroupMemberStruct]):
        """
        Updates members and sends state to all group members through GroupManagerAI.
        """
        self.setMembers(members)
        self.broadcastGroupState()

    def b_setCapacity(self, capacity: int):
        """
        Updates capacity and sends state to all group members through GroupManagerAI.
        """
        self.setCapacity(capacity)
        self.broadcastGroupState()

    def broadcastGroupState(self):
        """
        Sends the current group state to all members through the global GroupManagerAI.
        """
        if not hasattr(self, 'groupId') or self.groupId == 0:
            return
        
        groupManager = self.air.groupManager
        if groupManager is None:
            return
        
        for avId in self.getMemberIds():
            groupManager.d_setGroupState(avId, self.groupId, self.getMembers(), self.getCapacity(), self.desiredMinigame)

    def d_setMinigameZone(self, minigame):
        """
        Forces all members to teleport to a newly created minigame.
        Sends through GroupManagerAI.
        """
        groupManager = self.air.groupManager
        if groupManager is None:
            return
        
        for avId in self.getMemberIds():
            groupManager.d_setMinigameZone(avId, minigame.zone, minigame.gameId)

    def getNumPlayersNotReady(self) -> int:
        notReady = 0
        for member in self.getMembers():
            if member.status == GroupGlobals.STATUS_UNREADY:
                notReady += 1
        return notReady

    def b_setMinigameType(self, minigameId):
        """
        Updates minigame type and broadcasts to all members.
        """
        self.desiredMinigame = minigameId
        self.minigameConfig.updateMinigameId(minigameId)
        self.broadcastGroupState()
    
    def getMinigameConfig(self) -> GroupMinigameConfig:
        """
        Get the minigame configuration for this group.
        """
        return self.minigameConfig
    
    def setMinigameRuleset(self, minigameId, rulesetStruct):
        """
        Store ruleset data for a minigame in the group config.
        This persists across minigame sessions.
        """
        self.minigameConfig.setRuleset(minigameId, rulesetStruct)
    
    def setMinigameModifiers(self, minigameId, modifierStructs):
        """
        Store modifier data for a minigame in the group config.
        This persists across minigame sessions.
        """
        self.minigameConfig.setModifiers(minigameId, modifierStructs)

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObject import DistributedObject
from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal

from toontown.groups import GroupGlobals
from toontown.groups.DistributedGroup import DistributedGroup
from toontown.groups.GroupBase import GroupBase
from toontown.toon.GroupInvitee import GroupInvitee


class GroupManager(DistributedObjectGlobal):
    """
    An instance on the client that is responsible for managing separate groups.
    A "group" can be thought of as a "party" on other games, or even a "lobby".

    Toons will be in a group with other toons while a leader/host sets up game rules and eventually
    sends the entire group into some instance. (In our case, the trolley with specific settings.)

    This class is responsible for communicating with the server's version of the group manager,
    and will tell our local client which group we are in.
    """

    Notify = DirectNotifyGlobal.directNotify.newCategory('GroupManager')

    def __init__(self, cr):
        super().__init__(cr)

        # The current group that our client is currently in.
        # Once we are in a group, we can actually properly render it.
        self.currentGroup: DistributedGroup | None = None
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

    def delete(self):
        """
        When this group manager deletes, we need to make sure that we leave our current group.
        """
        super().delete()
        self.Notify.info("Shutting down...")
        base.localAvatar.setGroupManager(None)
        self.destroyCurrentInvitePanel()
        taskMgr.remove(self.uniqueName('readycheck'))

    def destroyCurrentInvitePanel(self):
        if self.currentInvite is not None:
            self.currentInvite.cleanup()
            self.currentInvite = None

    def findGroupById(self, groupId: int) -> DistributedGroup | None:
        """
        Attempts to find the group in the client repository. Returns None if no such group exists.
        """
        if groupId == GroupBase.NoGroup:
            return None

        return self.cr.getDo(groupId)

    def __readyCheck(self, task):
        task.delayTime = 5

        # If we are in a group, then tell the server we are ready. Continuously do this while we are ready to keep us in sync.
        if self.getCurrentGroup() is not None:
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
        if self.getCurrentGroup() is None:
            return

        # Are we the leader of our group and not trying to kick ourselves?
        if base.localAvatar.getDoId() != avId and self.getCurrentGroup().getLeader() != base.localAvatar.doId:
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
        if self.getCurrentGroup() is not None:
            self.d_requestStart()

    def requestGameSwitch(self, minigameId: int):
        self.Notify.debug(f"Attempting to switch the game to {minigameId}")
        if self.getCurrentGroup() is not None and self.getCurrentGroup().getLeader() == base.localAvatar.getDoId():
            self.d_requestMinigameSwitch(minigameId)

    def updateStatus(self, code: int):

        self.Notify.debug(f"Updating local av status to {code} for current group")

        # Don't send codes unless they are ready/unready codes.
        if code not in (GroupGlobals.STATUS_UNREADY, GroupGlobals.STATUS_READY):
            return

        # If we are the leader we don't need to update the ID. We are in charge of starting the group anyway.
        if self.getCurrentGroup() is not None and self.getCurrentGroup().getLeader() == base.localAvatar.getDoId():
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

    def setCurrentGroup(self, groupId: int):
        """
        Called from the AI when we are assigned to be in a new group.
        """

        # Cleanup the old group.
        if self.currentGroup is not None:
            self.currentGroup.cleanup()

        # Update to the new group.
        self.currentGroup = self.findGroupById(groupId)
        if self.currentGroup is None:
            return

        self.currentGroup.render()

    def getCurrentGroup(self) -> DistributedGroup | None:
        return self.currentGroup

    def sendInvite(self, sender: int, groupId: int):

        inviter = self.cr.getDo(sender)
        if inviter is None:
            return

        self.destroyCurrentInvitePanel()

        group = self.cr.getDo(groupId)

        self.currentInvite = GroupInvitee()
        self.currentInvite.make(group, inviter, sender if group is None else group.getLeader())

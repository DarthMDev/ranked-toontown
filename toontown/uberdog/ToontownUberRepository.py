from direct.directnotify import DirectNotifyGlobal

from otp.distributed.DistributedDirectoryAI import DistributedDirectoryAI
from otp.distributed.OtpDoGlobals import *
from toontown.distributed.ToontownInternalRepository import ToontownInternalRepository
from toontown.groups.GroupManagerUD import GroupManagerUD
from toontown.matchmaking.LeaderboardManagerUD import LeaderboardManagerUD
from toontown.api.ApiManagerUD import ApiManagerUD


class ToontownUberRepository(ToontownInternalRepository):
    notify = DirectNotifyGlobal.directNotify.newCategory('ToontownUberRepository')

    def __init__(self, baseChannel, serverId):
        ToontownInternalRepository.__init__(self, baseChannel, serverId, dcSuffix='UD')
        self.gameServicesManager = None
        self.onlinePlayerManager = None
        self.leaderboardManager: LeaderboardManagerUD | None = None
        self.chatManager = None

        self.apiManager: ApiManagerUD | None = None

        self.groupManager: GroupManagerUD | None = None

    def handleConnected(self):
        ToontownInternalRepository.handleConnected(self)

        rootObj = DistributedDirectoryAI(self)
        rootObj.generateWithRequiredAndId(self.getGameDoId(), 0, 0)

        self.createGlobals()

        self.notify.info('Done.')

    def createGlobals(self):
        self.gameServicesManager = self.generateGlobalObject(OTP_DO_ID_TOONTOWN_GAME_SERVICES_MANAGER,
                                                             'TTGameServicesManager')
        self.onlinePlayerManager = self.generateGlobalObject(OTP_DO_ID_ONLINE_PLAYER_MANAGER, 'OnlinePlayerManager')
        self.leaderboardManager = self.generateGlobalObject(OTP_DO_ID_LEADERBOARD_MANAGER, 'LeaderboardManager')
        self.chatManager = self.generateGlobalObject(OTP_DO_ID_CHAT_MANAGER, 'TTOffChatManager')
        self.apiManager = self.generateGlobalObject(OTP_DO_ID_API_MANAGER, 'ApiManager')

        self.groupManager = self.generateGlobalObject(OTP_DO_ID_GROUP_MANAGER, "GroupManager")

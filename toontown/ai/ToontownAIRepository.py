import time
from typing import Dict

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.PyDatagram import *
from panda3d.core import *
from toontown.dna.DNAParser import loadDNAFileAI, DNAStorage, DNAGroup

from otp.ai.AIZoneData import AIZoneDataStore
from otp.ai.TimeManagerAI import TimeManagerAI
from otp.distributed.OtpDoGlobals import *
from otp.friends.FriendManagerAI import FriendManagerAI
from otp.otpbase import OTPGlobals
from toontown.ai.DistributedPolarPlaceEffectMgrAI import DistributedPolarPlaceEffectMgrAI
from toontown.ai.DistributedResistanceEmoteMgrAI import DistributedResistanceEmoteMgrAI
from toontown.ai.HolidayManagerAI import HolidayManagerAI
from toontown.ai.NewsManagerAI import NewsManagerAI
from toontown.archipelago.distributed.DistributedArchipelagoManagerAI import DistributedArchipelagoManagerAI
from toontown.building.DistributedTrophyMgrAI import DistributedTrophyMgrAI

from toontown.coghq.PromotionManagerAI import PromotionManagerAI
from toontown.distributed.ToontownDistrictAI import ToontownDistrictAI
from toontown.distributed.ToontownDistrictStatsAI import ToontownDistrictStatsAI
from toontown.distributed.ToontownInternalRepository import ToontownInternalRepository
from toontown.fishing.FishManagerAI import FishManagerAI
from toontown.groups.GroupManagerAI import GroupManagerAI
from toontown.hood import ZoneUtil
from toontown.hood.TTHoodDataAI import TTHoodDataAI
from toontown.matchmaking.DistributedMatchmakerAI import DistributedMatchmakerAI
from toontown.matchmaking.LeaderboardManagerAI import LeaderboardManagerAI
from toontown.minigame.MinigameCreatorAI import MinigameCreatorAI
from toontown.parties.ToontownTimeManager import ToontownTimeManager
from toontown.pets.PetManagerAI import PetManagerAI
from toontown.quest.QuestManagerAI import QuestManagerAI
from toontown.safezone.SafeZoneManagerAI import SafeZoneManagerAI
from toontown.shtiker.CogPageManagerAI import CogPageManagerAI
from toontown.spellbook.TTOffMagicWordManagerAI import TTOffMagicWordManagerAI
from toontown.suit.SuitInvasionManagerAI import SuitInvasionManagerAI
from toontown.toon import NPCToons
from toontown.toonbase import ToontownGlobals
from toontown.uberdog.DistributedInGameNewsMgrAI import DistributedInGameNewsMgrAI
from toontown.api.ApiManagerAI import ApiManagerAI


class ToontownAIRepository(ToontownInternalRepository):
    notify = DirectNotifyGlobal.directNotify.newCategory('ToontownAIRepository')

    def __init__(self, baseChannel, serverId, districtName):
        ToontownInternalRepository.__init__(self, baseChannel, serverId, dcSuffix='AI')
        self.districtName = districtName
        self.doLiveUpdates = self.config.GetBool('want-live-updates', True)
        # self.wantCogdominiums = self.config.GetBool('want-cogdominiums', True)
        self.wantEmblems = self.config.GetBool('want-emblems', True)
        self.useAllMinigames = self.config.GetBool('want-all-minigames', True)
        self.districtId = None
        self.district = None
        self.districtStats = None
        self.timeManager = None
        self.newsManager = None
        self.holidayManager = None
        self.welcomeValleyManager = None
        self.zoneDataStore = None
        self.inGameNewsMgr = None
        self.trophyMgr = None
        self.petMgr = None
        self.dnaStoreMap = {}
        self.dnaDataMap = {}
        self.zoneTable = {}
        self.hoods = []
        self.buildingManagers = {}
        self.suitPlanners = {}
        self.suitInvasionManager = None
        self.zoneAllocator = None
        self.minigameMgr = None
        self.zoneId2owner = {}
        self.questManager = None
        self.cogPageManager = None
        self.fishManager = None
        self.factoryMgr = None
        self.mintMgr = None
        self.lawMgr = None
        self.countryClubMgr = None
        self.promotionMgr = None
        self.safeZoneManager = None
        self.polarPlaceEffectMgr = None
        self.resistanceEmoteMgr = None
        self.tutorialManager = None
        self.friendManager = None
        self.toontownTimeManager = None
        self.magicWordManager = None
        self.leaderboardManager: LeaderboardManagerAI | None = None
        self.apiManager: ApiManagerAI | None = None
        self.groupManager: GroupManagerAI | None = None
        self.matchmaker: DistributedMatchmakerAI | None = None
        self.archipelagoManager = None
        self.defaultAccessLevel = OTPGlobals.accessLevelValues.get('TTOFF_DEVELOPER')

        # AP stuff

        # Keeps track of toon IDs and maps them to last successful connection information so they can fast !connect
        # When relogging
        self.archipelagoConnectionCache: Dict[int, tuple] = {}

    def getTrackClsends(self):
        return False

    def handleConnected(self):
        ToontownInternalRepository.handleConnected(self)

        # Generate our district...
        self.districtId = self.allocateChannel()
        self.notify.info('Creating district (%d)...' % self.districtId)
        self.district = ToontownDistrictAI(self)
        self.district.setName(self.districtName)
        self.district.generateWithRequiredAndId(self.districtId, self.getGameDoId(), OTP_ZONE_ID_MANAGEMENT)

        # Claim ownership of that district...
        self.notify.info('Claiming ownership of district (%d)...' % self.districtId)
        datagram = PyDatagram()
        datagram.addServerHeader(self.districtId, self.ourChannel, STATESERVER_OBJECT_SET_AI)
        datagram.addChannel(self.ourChannel)
        self.send(datagram)

        # Create our local objects.
        self.notify.info('Creating local objects...')
        self.createLocals()

        # Create our global objects.
        self.notify.info('Creating global objects...')
        self.createGlobals()

        # Create our zones.
        self.notify.info('Creating zones (Playgrounds and Cog HQs)...')
        self.createZones()

        # Make our district available, and we're done.
        self.notify.info('Making district available...')
        self.district.b_setAvailable(1)
        self.notify.info('District is now ready. Have fun in Toontown Ranked!')

    def createLocals(self):
        """
        Creates "local" objects.
        """

        # Create our holiday manager...
        self.holidayManager = HolidayManagerAI(self)

        # Create our zone data store...
        self.zoneDataStore = AIZoneDataStore()

        # Create our pet manager...
        self.petMgr = PetManagerAI(self)

        # Create our suit invasion manager...
        self.suitInvasionManager = SuitInvasionManagerAI(self)

        # Create our zone allocator...
        self.zoneAllocator = UniqueIdAllocator(ToontownGlobals.DynamicZonesBegin, ToontownGlobals.DynamicZonesEnd)

        # Create our minigame manager...
        self.minigameMgr = MinigameCreatorAI(self)

        # Create our quest manager...
        self.questManager = QuestManagerAI(self)

        # Create our Cog page manager...
        self.cogPageManager = CogPageManagerAI(self)

        # Create our fish manager...
        self.fishManager = FishManagerAI(self)

        # Create our promotion manager...
        self.promotionMgr = PromotionManagerAI(self)

        # Create our Toontown time manager...
        self.toontownTimeManager = ToontownTimeManager(serverTimeUponLogin=int(time.time()),
                                                       globalClockRealTimeUponLogin=globalClock.getRealTime())

    def createGlobals(self):
        """
        Creates "global" objects.
        """

        # Generate our district stats...
        districtStatsId = self.allocateChannel()
        self.notify.info('Creating district stats AI (%d)...' % districtStatsId)
        self.districtStats = ToontownDistrictStatsAI(self)
        self.districtStats.settoontownDistrictId(self.districtId)
        self.districtStats.generateWithRequiredAndId(districtStatsId, self.getGameDoId(), OTP_ZONE_ID_DISTRICTS)

        # Generate our time manager...
        self.timeManager = TimeManagerAI(self)
        self.timeManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our news manager...
        self.newsManager = NewsManagerAI(self)
        self.newsManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our Welcome Valley manager...
        # self.welcomeValleyManager = WelcomeValleyManagerAI(self)
        # self.welcomeValleyManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our in-game news manager...
        self.inGameNewsMgr = DistributedInGameNewsMgrAI(self)
        self.inGameNewsMgr.setLatestIssueStr('2013-08-22 23:49:46')
        self.inGameNewsMgr.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our trophy manager...
        self.trophyMgr = DistributedTrophyMgrAI(self)
        self.trophyMgr.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our safezone manager...
        self.safeZoneManager = SafeZoneManagerAI(self)
        self.safeZoneManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our Polar Place effect manager...
        self.polarPlaceEffectMgr = DistributedPolarPlaceEffectMgrAI(self)
        self.polarPlaceEffectMgr.generateWithRequired(3821)

        # Generate our resistance emote manager...
        self.resistanceEmoteMgr = DistributedResistanceEmoteMgrAI(self)
        self.resistanceEmoteMgr.generateWithRequired(9720)

        # Generate our friend manager...
        self.friendManager = FriendManagerAI(self)
        self.friendManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our Magic Word manager...
        self.magicWordManager = TTOffMagicWordManagerAI(self)
        self.magicWordManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our AP Manager...
        self.archipelagoManager = DistributedArchipelagoManagerAI(self)
        self.archipelagoManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our leaderboard manager...
        self.leaderboardManager = self.generateGlobalObject(OTP_DO_ID_LEADERBOARD_MANAGER,
                                                         'LeaderboardManager')



        # Generate our API manager...
        self.apiManager = self.generateGlobalObject(OTP_DO_ID_API_MANAGER,
                                                         'ApiManager')
        self.groupManager = self.generateGlobalObject(OTP_DO_ID_GROUP_MANAGER,
                                                         'GroupManager')
        self.matchmaker = self.generateGlobalObject(OTP_DO_ID_MATCHMAKER, 'DistributedMatchmaker')


    def createHood(self, hoodCtr, zoneId):
        self.dnaStoreMap[zoneId] = DNAStorage()
        self.dnaDataMap[zoneId] = loadDNAFileAI(self.dnaStoreMap[zoneId], self.genDNAFileName(zoneId))

        hood = hoodCtr(self, zoneId)
        hood.startup()
        self.hoods.append(hood)

    def createZones(self):
        # First, generate our zone2NpcDict...
        NPCToons.generateZone2NpcDict()

        # Toontown Central
        self.zoneTable[ToontownGlobals.ToontownCentral] = (
            (ToontownGlobals.ToontownCentral, 1, 0)
        )
        self.createHood(TTHoodDataAI, ToontownGlobals.ToontownCentral)

    def incrementPopulation(self):
        self.districtStats.b_setAvatarCount(self.districtStats.getAvatarCount() + 1)
        self.apiManager.d_postDistrictStats()

    def decrementPopulation(self):
        self.districtStats.b_setAvatarCount(self.districtStats.getAvatarCount() - 1)
        self.apiManager.d_postDistrictStats()

    def getAvatarExitEvent(self, avId):
        return 'distObjDelete-%d' % avId

    def getZoneDataStore(self):
        return self.zoneDataStore

    def genDNAFileName(self, zoneId):
        zoneId = ZoneUtil.getCanonicalZoneId(zoneId)
        hoodId = ZoneUtil.getCanonicalHoodId(zoneId)
        hood = ToontownGlobals.dnaMap[hoodId]
        if hoodId == zoneId:
            zoneId = 'sz'
            phase = ToontownGlobals.phaseMap[hoodId]
        else:
            phase = ToontownGlobals.streetPhaseMap[hoodId]

        if 'outdoor_zone' in hood or 'golf_zone' in hood:
            phase = '6'

        return 'phase_%s/dna/%s_%s.dna' % (phase, hood, zoneId)

    def findFishingPonds(self, dnaData, zoneId, area):
        fishingPonds = []
        fishingPondGroups = []
        if isinstance(dnaData, DNAGroup.DNAGroup) and ('fishing_pond' in dnaData.getName()):
            fishingPondGroups.append(dnaData)
            pond = self.fishManager.generatePond(area, zoneId)
            fishingPonds.append(pond)

        for i in range(dnaData.getNumChildren()):
            foundFishingPonds, foundFishingPondGroups = self.findFishingPonds(dnaData.at(i), zoneId, area)
            fishingPonds.extend(foundFishingPonds)
            fishingPondGroups.extend(foundFishingPondGroups)

        return fishingPonds, fishingPondGroups

    def findFishingSpots(self, dnaData, fishingPond):
        fishingSpots = []
        if isinstance(dnaData, DNAGroup.DNAGroup) and ('fishing_spot' in dnaData.getName()):
            spot = self.fishManager.generateSpots(dnaData, fishingPond)
            fishingSpots.append(spot)

        for i in range(dnaData.getNumChildren()):
            foundFishingSpots = self.findFishingSpots(dnaData.at(i), fishingPond)
            fishingSpots.extend(foundFishingSpots)

        return fishingSpots

    def loadDNAFileAI(self, dnaStore, dnaFileName):
        return loadDNAFileAI(dnaStore, dnaFileName)

    def allocateZone(self, owner=None):
        zoneId = self.zoneAllocator.allocate()
        if owner:
            self.zoneId2owner[zoneId] = owner

        return zoneId

    def deallocateZone(self, zone):
        if self.zoneId2owner.get(zone):
            del self.zoneId2owner[zone]

        self.zoneAllocator.free(zone)

    def trueUniqueName(self, idString):
        return self.uniqueName(idString)

    def getAvatarDisconnectReason(self, avId):
        return self.timeManager.avId2disconnectcode.get(avId, ToontownGlobals.DisconnectUnknown)

    def lookupDNAFileName(self, dnaFile):
        searchPath = DSearchPath()
        searchPath.appendDirectory(Filename('/phase_3.5/dna'))
        searchPath.appendDirectory(Filename('/phase_4/dna'))
        searchPath.appendDirectory(Filename('/phase_5/dna'))
        searchPath.appendDirectory(Filename('/phase_5.5/dna'))
        searchPath.appendDirectory(Filename('/phase_6/dna'))
        searchPath.appendDirectory(Filename('/phase_8/dna'))
        searchPath.appendDirectory(Filename('/phase_9/dna'))
        searchPath.appendDirectory(Filename('/phase_10/dna'))
        searchPath.appendDirectory(Filename('/phase_11/dna'))
        searchPath.appendDirectory(Filename('/phase_12/dna'))
        searchPath.appendDirectory(Filename('/phase_13/dna'))
        filename = Filename(dnaFile)
        found = vfs.resolveFilename(filename, searchPath)
        if not found:
            self.notify.warning('lookupDNAFileName - %s not found on:' % dnaFile)
            print(searchPath)
        else:
            return filename.getFullpath()

    def findLeaderBoards(self, dnaData, zoneId):
        return [] # TODO
        '''
        leaderboards = []
        if 'leaderBoard' in dnaData.getName():
            x, y, z = dnaData.getPos()
            h, p, r = dnaData.getHpr()
            leaderboard = DistributedLeaderBoardAI(self, dnaData.getName(), x, y, z, h, p, r)
            leaderboard.generateWithRequired(zoneId)
            leaderboards.append(leaderboard)

        for i in range(dnaData.getNumChildren()):
            foundLeaderBoards = self.findLeaderBoards(dnaData.at(i), zoneId)
            leaderboards.extend(foundLeaderBoards)

        return leaderboards
        '''

    def cacheArchipelagoConnectInformation(self, avId, slotName, address):
        self.archipelagoConnectionCache[avId] = (slotName, address)

    def getCachedArchipelagoConnectionInformation(self, avId):
        return self.archipelagoConnectionCache.get(avId, (None, None))


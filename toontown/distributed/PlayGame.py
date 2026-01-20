from panda3d.core import *
from toontown.dna.DNAParser import DNAStorage
from toontown.toonbase.ToonBaseGlobal import *
from direct.directnotify import DirectNotifyGlobal
from direct.fsm import StateData
from direct.fsm import ClassicFSM, State
from direct.fsm import State
from direct.task.Task import Task
from .ToontownMsgTypes import *
from toontown.toonbase import ToontownGlobals
from toontown.hood import TTHood
from toontown.hood import QuietZoneState
from toontown.hood import ZoneUtil
from toontown.toonbase import TTLocalizer

class PlayGame(StateData.StateData):
    notify = DirectNotifyGlobal.directNotify.newCategory('PlayGame')
    Hood2ClassDict = {ToontownGlobals.ToontownCentral: TTHood.TTHood}
    Hood2StateDict = {ToontownGlobals.ToontownCentral: 'TTHood'}

    def __init__(self, parentFSM, doneEvent):
        StateData.StateData.__init__(self, doneEvent)
        self.place = None
        self.fsm = ClassicFSM.ClassicFSM('PlayGame', [State.State('start', self.enterStart, self.exitStart, ['quietZone']),
         State.State('quietZone', self.enterQuietZone, self.exitQuietZone, ['TTHood']),
         State.State('TTHood', self.enterTTHood, self.exitTTHood, ['quietZone'])], 'start', 'start')
        self.fsm.enterInitialState()
        self.parentFSM = parentFSM
        self.parentFSM.getStateNamed('playGame').addChild(self.fsm)
        self.hoodDoneEvent = 'hoodDone'
        self.hood = None
        self.quietZoneDoneEvent = uniqueName('quietZoneDone')
        self.quietZoneStateData = None
        return

    def enter(self, hoodId, zoneId, avId):
        # Always spawn in Toontown Central
        # todo: preferred playground setting?
        hoodId = ToontownGlobals.ToontownCentral
        zoneId = ToontownGlobals.ToontownCentral
        if hoodId == ToontownGlobals.Tutorial:
            loaderName = 'townLoader'
            whereName = 'toonInterior'
        else:
            loaderName = ZoneUtil.getLoaderName(zoneId)
            whereName = ZoneUtil.getToonWhereName(zoneId)
        self.fsm.request('quietZone', [{'loader': loaderName,
          'where': whereName,
          'how': 'teleportIn',
          'hoodId': hoodId,
          'zoneId': zoneId,
          'shardId': None,
          'avId': avId}])
        return

    def exit(self):
        if base.placeBeforeObjects and self.quietZoneStateData:
            self.quietZoneStateData.exit()
            self.quietZoneStateData.unload()
            self.quietZoneStateData = None
        self.ignore(self.quietZoneDoneEvent)
        return

    def load(self):
        pass

    def loadDnaStoreTutorial(self):
        self.dnaStore = DNAStorage()
        loader.loadDNAFile(self.dnaStore, 'phase_3.5/dna/storage_tutorial.dna')
        loader.loadDNAFile(self.dnaStore, 'phase_3.5/dna/storage_interior.dna')

    def loadDnaStore(self):
        if not hasattr(self, 'dnaStore'):
            self.dnaStore = DNAStorage()
            loader.loadDNAFile(self.dnaStore, 'phase_4/dna/storage.dna')
            self.dnaStore.storeFont('humanist', ToontownGlobals.getInterfaceFont())
            self.dnaStore.storeFont('mickey', ToontownGlobals.getSignFont())
            self.dnaStore.storeFont('suit', ToontownGlobals.getSuitFont())
            loader.loadDNAFile(self.dnaStore, 'phase_3.5/dna/storage_interior.dna')

    def unloadDnaStore(self):
        if hasattr(self, 'dnaStore'):
            self.dnaStore.resetNodes()
            self.dnaStore.resetTextures()
            self.dnaStore.resetSuitBlocks()
            del self.dnaStore
            ModelPool.garbageCollect()
            TexturePool.garbageCollect()

    def unload(self):
        self.unloadDnaStore()
        if self.hood:
            self.notify.info('Aggressively cleaning up hood: %s' % self.hood)
            self.hood.exit()
            self.hood.unload()
            self.hood = None
        return

    def enterStart(self):
        pass

    def exitStart(self):
        pass

    def handleHoodDone(self):
        doneStatus = self.hood.getDoneStatus()
        shardId = doneStatus['shardId']
        if shardId != None:
            self.doneStatus = doneStatus
            messenger.send(self.doneEvent)
            base.transitions.fadeOut(0)
            return
        how = doneStatus['how']
        if how in ['tunnelIn',
         'teleportIn',
         'doorIn',
         'elevatorIn']:
            self.fsm.request('quietZone', [doneStatus])
        else:
            self.notify.error('Exited hood with unexpected mode %s' % how)
        return

    def _destroyHood(self):
        self.ignore(self.hoodDoneEvent)
        self.hood.exit()
        self.hood.unload()
        self.hood = None
        base.cr.cache.flush()
        return

    def enterQuietZone(self, requestStatus):
        self.acceptOnce(self.quietZoneDoneEvent, self.handleQuietZoneDone)
        self.quietZoneStateData = QuietZoneState.QuietZoneState(self.quietZoneDoneEvent)
        self._quietZoneLeftEvent = self.quietZoneStateData.getQuietZoneLeftEvent()
        if base.placeBeforeObjects:
            self.acceptOnce(self._quietZoneLeftEvent, self.handleLeftQuietZone)
        self._enterWaitForSetZoneResponseMsg = self.quietZoneStateData.getEnterWaitForSetZoneResponseMsg()
        self.acceptOnce(self._enterWaitForSetZoneResponseMsg, self.handleWaitForSetZoneResponse)
        self.quietZoneStateData.load()
        self.quietZoneStateData.enter(requestStatus)

    def exitQuietZone(self):
        self.ignore(self._quietZoneLeftEvent)
        self.ignore(self._enterWaitForSetZoneResponseMsg)
        if not base.placeBeforeObjects:
            self.ignore(self.quietZoneDoneEvent)
            self.quietZoneStateData.exit()
            self.quietZoneStateData.unload()
            self.quietZoneStateData = None
        return

    def handleWaitForSetZoneResponse(self, requestStatus):
        hoodId = requestStatus['hoodId']
        canonicalHoodId = ZoneUtil.getCanonicalZoneId(hoodId)
        toHoodPhrase = ToontownGlobals.hoodNameMap[canonicalHoodId][0]
        hoodName = ToontownGlobals.hoodNameMap[canonicalHoodId][-1]
        zoneId = requestStatus['zoneId']
        loaderName = requestStatus['loader']
        avId = requestStatus.get('avId', -1)
        ownerId = requestStatus.get('ownerId', avId)
        if base.config.GetBool('want-qa-regression', 0):
            self.notify.info('QA-REGRESSION: NEIGHBORHOODS: Visit %s' % hoodName)
        count = ToontownGlobals.hoodCountMap[canonicalHoodId]
        if loaderName == 'safeZoneLoader':
            count += ToontownGlobals.safeZoneCountMap[canonicalHoodId]
        elif loaderName == 'townLoader':
            count += ToontownGlobals.townCountMap[canonicalHoodId]
        if not loader.inBulkBlock:
            if ZoneUtil.isCogHQZone(zoneId):
                loader.loadingScreen.title['text_font'] = ToontownGlobals.getSuitFont()
                loader.beginBulkLoad('hood', TTLocalizer.HeadingToHood % {'to': toHoodPhrase,
                 'hood': hoodName}, count, 1, TTLocalizer.TIP_COGHQ)
            elif ZoneUtil.isGoofySpeedwayZone(zoneId):
                loader.loadingScreen.title['text_font'] = ToontownGlobals.getInterfaceFont()
                loader.beginBulkLoad('hood', TTLocalizer.HeadingToHood % {'to': toHoodPhrase,
                 'hood': hoodName}, count, 1, TTLocalizer.TIP_KARTING)
            else:
                loader.loadingScreen.title['text_font'] = ToontownGlobals.getInterfaceFont()
                loader.beginBulkLoad('hood', TTLocalizer.HeadingToHood % {'to': toHoodPhrase,
                 'hood': hoodName}, count, 1, TTLocalizer.TIP_GENERAL)
        if hoodId == ToontownGlobals.Tutorial:
            self.loadDnaStoreTutorial()
        else:
            self.loadDnaStore()
        hoodClass = self.getHoodClassByNumber(canonicalHoodId)
        self.hood = hoodClass(self.fsm, self.hoodDoneEvent, self.dnaStore, hoodId)
        self.hood.load()
        self.hood.loadLoader(requestStatus)
        if not base.placeBeforeObjects:
            loader.endBulkLoad('hood')
        return

    def handleLeftQuietZone(self):
        status = self.quietZoneStateData.getRequestStatus()
        hoodId = ZoneUtil.getCanonicalZoneId(status['hoodId'])
        hoodState = self.getHoodStateByNumber(hoodId)
        self.fsm.request(hoodState, [status])

    def handleQuietZoneDone(self):
        if base.placeBeforeObjects:
            self.quietZoneStateData.exit()
            self.quietZoneStateData.unload()
            self.quietZoneStateData = None
            loader.endBulkLoad('hood')
        else:
            self.handleLeftQuietZone()
        return

    def enterTTHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitTTHood(self):
        self._destroyHood()

    def enterDDHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitDDHood(self):
        self._destroyHood()

    def enterMMHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitMMHood(self):
        self._destroyHood()

    def enterBRHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitBRHood(self):
        self._destroyHood()

    def enterDGHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitDGHood(self):
        self._destroyHood()

    def enterDLHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitDLHood(self):
        self._destroyHood()

    def enterGSHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitGSHood(self):
        self._destroyHood()

    def enterOZHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitOZHood(self):
        self._destroyHood()

    def enterGZHood(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitGZHood(self):
        self._destroyHood()

    def enterSellbotHQ(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitSellbotHQ(self):
        self._destroyHood()

    def enterCashbotHQ(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitCashbotHQ(self):
        self._destroyHood()

    def enterLawbotHQ(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitLawbotHQ(self):
        self._destroyHood()

    def enterBossbotHQ(self, requestStatus):
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        self.hood.enter(requestStatus)

    def exitBossbotHQ(self):
        self._destroyHood()

    def enterTutorialHood(self, requestStatus):
        messenger.send('toonArrivedTutorial')
        self.accept(self.hoodDoneEvent, self.handleHoodDone)
        base.localAvatar.book.obscureButton(1)
        base.localAvatar.book.setSafeMode(1)
        base.localAvatar.laffMeter.obscure(1)
        base.localAvatar.chatMgr.obscure(1, 1)
        base.localAvatar.obscureFriendsListButton(1)
        requestStatus['how'] = 'tutorial'
        if base.config.GetString('language', 'english') == 'japanese':
            musicVolume = base.config.GetFloat('tutorial-music-volume', 0.5)
            requestStatus['musicVolume'] = musicVolume
        self.hood.enter(requestStatus)

    def exitTutorialHood(self):
        self.unloadDnaStore()
        self._destroyHood()
        base.localAvatar.book.obscureButton(0)
        base.localAvatar.book.setSafeMode(0)
        base.localAvatar.laffMeter.obscure(0)
        base.localAvatar.chatMgr.obscure(0, 0)
        base.localAvatar.obscureFriendsListButton(-1)

    def getCatalogCodes(self, category):
        numCodes = self.dnaStore.getNumCatalogCodes(category)
        codes = []
        for i in range(numCodes):
            codes.append(self.dnaStore.getCatalogCode(category, i))

        return codes

    def getNodePathList(self, catalogGroup):
        result = []
        codes = self.getCatalogCodes(catalogGroup)
        for code in codes:
            np = self.dnaStore.findNode(code)
            result.append(np)

        return result

    def getNodePathDict(self, catalogGroup):
        result = {}
        codes = self.getCatalogCodes(catalogGroup)
        for code in codes:
            np = self.dnaStore.findNode(code)
            result[code] = np

        return result

    def getHoodClassByNumber(self, hoodNumber):
        return self.Hood2ClassDict[hoodNumber]

    def getHoodStateByNumber(self, hoodNumber):
        return self.Hood2StateDict[hoodNumber]

    def setPlace(self, place):
        self.place = place
        if self.place:
            messenger.send('playGameSetPlace')

    def getPlace(self):
        return self.place

    def getPlaceId(self):
        if self.hood:
            return self.hood.hoodId
        else:
            return None
        return None

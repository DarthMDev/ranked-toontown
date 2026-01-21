from otp.ai.AIBaseGlobal import *
from direct.distributed.ClockDelta import *
import types
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from direct.distributed import DistributedObjectAI
from direct.fsm import State
from direct.fsm import ClassicFSM, State
from toontown.toonbase.ToontownGlobals import ToonHall
from . import DistributedToonInteriorAI, DistributedToonHallInteriorAI, DistributedDoorAI, DoorTypes, DistributedKnockKnockDoorAI, FADoorCodes
from toontown.hood import ZoneUtil
import random, time

class DistributedBuildingAI(DistributedObjectAI.DistributedObjectAI):
    FieldOfficeNumFloors = 1

    def __init__(self, air, blockNumber, zoneId, trophyMgr):
        DistributedObjectAI.DistributedObjectAI.__init__(self, air)
        self.block = blockNumber
        self.zoneId = zoneId
        self.canonicalZoneId = ZoneUtil.getCanonicalZoneId(zoneId)
        self.trophyMgr = trophyMgr
        self.victorResponses = None
        self.fsm = ClassicFSM.ClassicFSM(
            'DistributedBuildingAI', [
                State.State('off', self.enterOff, self.exitOff, ['waitForVictors', 'toon']),
                State.State('waitForVictors', self.enterWaitForVictors, self.exitWaitForVictors, ['becomingToon']),
                State.State('toon', self.enterToon, self.exitToon, ['clearOutToonInterior']),
            ],
         'off',
         'off'
         )
        self.fsm.enterInitialState()
        self.track = 'c'
        self.difficulty = 1
        self.numFloors = 0
        self.savedBy = []
        self.becameSuitTime = 0
        self.frontDoorPoint = None
        self.suitPlannerExt = None
        self.fSkipElevatorOpening = False
        return

    def cleanup(self):
        if self.isDeleted():
            return
        self.fsm.requestFinalState()
        if hasattr(self, 'interior'):
            self.interior.requestDelete()
            del self.interior
        if hasattr(self, 'door'):
            self.door.requestDelete()
            del self.door
            self.insideDoor.requestDelete()
            del self.insideDoor
            self.knockKnock.requestDelete()
            del self.knockKnock
        if hasattr(self, 'elevator'):
            self.elevator.requestDelete()
            del self.elevator
        self.requestDelete()

    def delete(self):
        taskMgr.remove(self.taskName('suitbldg-time-out'))
        taskMgr.remove(self.taskName(str(self.block) + '_becomingToon-timer'))
        taskMgr.remove(self.taskName(str(self.block) + '_becomingSuit-timer'))
        DistributedObjectAI.DistributedObjectAI.delete(self)
        del self.fsm

    def getJsonData(self):

        jsonData = {
            'state': str(self.fsm.getCurrentState().getName()),
            'block': int(self.block),
            'track': str(self.track),
            'difficulty': int(self.difficulty),
            'numFloors': int(self.numFloors),
            'savedBy': self.savedBy,   # List of lists [ ('toon 1', (toondnathing1, 2, 3), someattribute), (...) ]
            'becameSuitTime': float(self.becameSuitTime)
        }

        return jsonData

    def toonTakeOver(self):
        isCogdo = 'cogdo' in self.fsm.getCurrentState().getName().lower()
        takenOver = True
        if isCogdo:
            if self.buildingDefeated:
                self.fsm.request('becomingToonFromCogdo')
            else:
                self.fsm.request('becomingCogdoFromCogdo')
                takenOver = False
        else:
            self.fsm.request('becomingToon')
        if takenOver and self.suitPlannerExt:
            self.suitPlannerExt.recycleBuilding(isCogdo)
        if hasattr(self, 'interior'):
            self.interior.requestDelete()
            del self.interior

    def getFrontDoorPoint(self):
        return self.frontDoorPoint

    def setFrontDoorPoint(self, point):
        self.frontDoorPoint = point

    def getBlock(self):
        dummy, interiorZoneId = self.getExteriorAndInteriorZoneId()
        return [
         self.block, interiorZoneId]

    def getSuitData(self):
        return [
         ord(self.track), self.difficulty, self.numFloors]

    def getState(self):
        return [
         self.fsm.getCurrentState().getName(), globalClockDelta.getRealNetworkTime()]

    def setState(self, state, timestamp=0):
        self.fsm.request(state)

    def isToonBlock(self):
        state = self.fsm.getCurrentState().getName()
        return state in ('toon', 'becomingToon', 'becomingToonFromCogdo')

    def getExteriorAndInteriorZoneId(self):
        blockNumber = self.block
        dnaStore = self.air.dnaStoreMap[self.canonicalZoneId]
        zoneId = dnaStore.getZoneFromBlockNumber(blockNumber)
        zoneId = ZoneUtil.getTrueZoneId(zoneId, self.zoneId)
        interiorZoneId = zoneId - zoneId % 100 + 500 + blockNumber
        return (
         zoneId, interiorZoneId)

    def d_setState(self, state):
        self.sendUpdate('setState', [state, globalClockDelta.getRealNetworkTime()])

    def b_setVictorList(self, victorList):
        self.setVictorList(victorList)
        self.d_setVictorList(victorList)

    def d_setVictorList(self, victorList):
        self.sendUpdate('setVictorList', [victorList])

    def setVictorList(self, victorList):
        self.victorList = victorList

    def findVictorIndex(self, avId):
        for i in range(len(self.victorList)):
            if self.victorList[i] == avId:
                return i

        return None

    def recordVictorResponse(self, avId):
        index = self.findVictorIndex(avId)
        if index == None:
            self.air.writeServerEvent('suspicious', avId, 'DistributedBuildingAI.setVictorReady from toon not in %s.' % self.victorList)
            return
        self.victorResponses[index] = avId
        return

    def allVictorsResponded(self):
        if self.victorResponses == self.victorList:
            return 1
        else:
            return 0

    def setVictorReady(self):
        avId = self.air.getAvatarIdFromSender()
        if self.victorResponses == None:
            self.air.writeServerEvent('suspicious', avId, 'DistributedBuildingAI.setVictorReady in state %s.' % self.fsm.getCurrentState().getName())
            return
        event = self.air.getAvatarExitEvent(avId)
        self.ignore(event)
        if self.allVictorsResponded():
            return
        self.recordVictorResponse(avId)
        if self.allVictorsResponded():
            self.toonTakeOver()
        return

    def setVictorExited(self, avId):
        print('victor %d exited unexpectedly for bldg %d' % (avId, self.doId))
        self.recordVictorResponse(avId)
        if self.allVictorsResponded():
            self.toonTakeOver()

    def victorsTimedOutTask(self, task):
        if self.allVictorsResponded():
            return
        if hasattr(self, 'interior'):
            self.notify.info('victorsTimedOutTask: ejecting players by deleting interior.')
            self.interior.requestDelete()
            del self.interior
            task.delayTime = 15.0
            return task.again
        self.notify.info('victorsTimedOutTask: suspicious players remaining, advancing state.')
        for i in range(len(self.victorList)):
            if self.victorList[i] and self.victorResponses[i] == 0:
                self.air.writeServerEvent('suspicious', self.victorList[i], 'DistributedBuildingAI toon client refused to leave building.')
                self.recordVictorResponse(self.victorList[i])
                event = self.air.getAvatarExitEvent(self.victorList[i])
                self.ignore(event)

        self.toonTakeOver()
        return Task.done

    def enterOff(self):
        pass

    def exitOff(self):
        pass

    def getToon(self, toonId):
        if toonId in self.air.doId2do:
            return self.air.doId2do[toonId]
        else:
            self.notify.warning('getToon() - toon: %d not in repository!' % toonId)
        return None

    def updateSavedBy(self, savedBy):

        # Allow us to pass in None as a param
        if savedBy is None:
            savedBy = []

        # Remove old trophy count if it exists
        if self.savedBy:
            for avId, _, _, _ in self.savedBy:
                if not ZoneUtil.isWelcomeValley(self.zoneId):
                    self.trophyMgr.removeTrophy(avId, self.numFloors)

        # Set the new saved by
        self.savedBy = savedBy

        # Nobody saved this building womp womp
        if self.savedBy is None:
            return

        # Loop through all the avs and update their trophies
        for avId, name, _, _ in self.savedBy:
            if not ZoneUtil.isWelcomeValley(self.zoneId):
                self.trophyMgr.addTrophy(avId, name, self.numFloors)

    def enterWaitForVictors(self, victorList, savedBy):
        activeToons = []
        for t in victorList:
            toon = None
            if t:
                toon = self.getToon(t)
            if toon != None:
                activeToons.append(toon)

        for t in victorList:
            toon = None
            if t:
                toon = self.getToon(t)
                self.air.writeServerEvent('buildingDefeated', t, '%s|%s|%s|%s' % (self.track, self.numFloors, self.zoneId, victorList))
            if toon != None:
                self.air.questManager.toonKilledBuilding(toon, self.track, self.difficulty, self.numFloors, self.zoneId, activeToons)

        for i in range(0, 4):
            victor = victorList[i]
            if victor == None or victor not in self.air.doId2do:
                victorList[i] = 0
            else:
                event = self.air.getAvatarExitEvent(victor)
                self.accept(event, self.setVictorExited, extraArgs=[victor])

        self.b_setVictorList(victorList)
        self.updateSavedBy(savedBy)
        self.victorResponses = [
         0, 0, 0, 0]
        self.d_setState('waitForVictors')
        return

    def exitWaitForVictors(self):
        self.victorResponses = None
        for victor in self.victorList:
            event = simbase.air.getAvatarExitEvent(victor)
            self.ignore(event)

        return

    def enterWaitForVictorsFromCogdo(self, victorList, savedBy):
        activeToons = []
        for t in victorList:
            toon = None
            if t:
                toon = self.getToon(t)
            if toon != None:
                activeToons.append(toon)

        self.buildingDefeated = len(savedBy) > 0
        if self.buildingDefeated:
            for t in victorList:
                toon = None
                if t:
                    toon = self.getToon(t)
                    self.air.writeServerEvent('buildingDefeated', t, '%s|%s|%s|%s' % (self.track, self.numFloors, self.zoneId, victorList))
                if toon != None:
                    self.air.questManager.toonKilledCogdo(toon, self.difficulty, self.numFloors, self.zoneId, activeToons)

        for i in range(0, 4):
            victor = victorList[i]
            if victor == None or victor not in self.air.doId2do:
                victorList[i] = 0
            else:
                event = self.air.getAvatarExitEvent(victor)
                self.accept(event, self.setVictorExited, extraArgs=[victor])

        self.b_setVictorList(victorList)
        self.updateSavedBy(savedBy)
        self.victorResponses = [
         0, 0, 0, 0]
        taskMgr.doMethodLater(30, self.victorsTimedOutTask, self.taskName(str(self.block) + '_waitForVictors-timer'))
        self.d_setState('waitForVictorsFromCogdo')
        return

    def exitWaitForVictorsFromCogdo(self):
        taskMgr.remove(self.taskName(str(self.block) + '_waitForVictors-timer'))
        self.victorResponses = None
        for victor in self.victorList:
            event = simbase.air.getAvatarExitEvent(victor)
            self.ignore(event)

        return

    def enterToon(self):
        self.d_setState('toon')
        exteriorZoneId, interiorZoneId = self.getExteriorAndInteriorZoneId()
        if simbase.config.GetBool('want-new-toonhall', 1) and ZoneUtil.getCanonicalZoneId(interiorZoneId) == ToonHall:
            self.interior = DistributedToonHallInteriorAI.DistributedToonHallInteriorAI(self.block, self.air, interiorZoneId, self)
        else:
            self.interior = DistributedToonInteriorAI.DistributedToonInteriorAI(self.block, self.air, interiorZoneId, self)
        self.interior.generateWithRequired(interiorZoneId)
        door = self.createExteriorDoor()
        insideDoor = DistributedDoorAI.DistributedDoorAI(self.air, self.block, DoorTypes.INT_STANDARD)
        door.setOtherDoor(insideDoor)
        insideDoor.setOtherDoor(door)
        door.zoneId = exteriorZoneId
        insideDoor.zoneId = interiorZoneId
        door.generateWithRequired(exteriorZoneId)
        insideDoor.generateWithRequired(interiorZoneId)
        self.door = door
        self.insideDoor = insideDoor
        self.becameSuitTime = 0
        self.knockKnock = DistributedKnockKnockDoorAI.DistributedKnockKnockDoorAI(self.air, self.block)
        self.knockKnock.generateWithRequired(exteriorZoneId)
        self.air.writeServerEvent('building-toon', self.doId, '%s|%s' % (self.zoneId, self.block))

    def createExteriorDoor(self):
        result = DistributedDoorAI.DistributedDoorAI(self.air, self.block, DoorTypes.EXT_STANDARD)
        return result

    def exitToon(self):
        self.door.setDoorLock(FADoorCodes.BUILDING_TAKEOVER)
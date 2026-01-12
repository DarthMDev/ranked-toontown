import math
import uuid
from typing import List, Tuple, Union, Any

from otp.ai.AIBaseGlobal import *
from otp.otpbase import OTPGlobals
from . import ToonDNA
from toontown.suit import SuitDNA
from . import InventoryBase
from . import Experience
from otp.avatar import DistributedAvatarAI
from otp.avatar import DistributedPlayerAI
from direct.distributed import DistributedSmoothNodeAI
from toontown.toonbase import ToontownGlobals
from toontown.quest import Quests
from toontown.toonbase import ToontownBattleGlobals
from toontown.battle import SuitBattleGlobals
from direct.task import Task
from toontown.catalog import CatalogItemList
from toontown.catalog import CatalogItem
from direct.distributed.ClockDelta import *
from toontown.fishing import FishCollection, FishTank, FishGlobals
from .NPCToons import isZoneProtected
from toontown.coghq import CogDisguiseGlobals
import random
import re
from toontown.chat import ResistanceChat
from toontown.racing import RaceGlobals
from toontown.hood import ZoneUtil
from toontown.toon import NPCToons
from toontown.golf import GolfGlobals
from toontown.parties import PartyGlobals
from toontown.parties.PartyInfo import PartyInfoAI
from toontown.parties.InviteInfo import InviteInfoBase
from toontown.parties.PartyReplyInfo import PartyReplyInfoBase
from toontown.parties.PartyGlobals import InviteStatus
from toontown.toonbase import ToontownAccessAI
from toontown.catalog import CatalogAccessoryItem
from . import ModuleListAI

from ..archipelago.definitions.death_reason import DeathReason
from ..matchmaking.player_skill_profile import PlayerSkillProfile, STARTING_MMR

class DistributedToonAI(DistributedPlayerAI.DistributedPlayerAI, DistributedSmoothNodeAI.DistributedSmoothNodeAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedToonAI')
    maxCallsPerNPC = 100
    partTypeIds = {ToontownGlobals.FT_FullSuit: (CogDisguiseGlobals.leftLegIndex,
                                                 CogDisguiseGlobals.rightLegIndex,
                                                 CogDisguiseGlobals.torsoIndex,
                                                 CogDisguiseGlobals.leftArmIndex,
                                                 CogDisguiseGlobals.rightArmIndex),
                   ToontownGlobals.FT_Leg: (CogDisguiseGlobals.leftLegIndex, CogDisguiseGlobals.rightLegIndex),
                   ToontownGlobals.FT_Arm: (CogDisguiseGlobals.leftArmIndex, CogDisguiseGlobals.rightArmIndex),
                   ToontownGlobals.FT_Torso: (CogDisguiseGlobals.torsoIndex,)}
    lastFlagAvTime = globalClock.getFrameTime()
    flagCounts = {}
    WantTpTrack = simbase.config.GetBool('want-tptrack', False)
    WantOldGMNameBan = simbase.config.GetBool('want-old-gm-name-ban', 1)

    def __init__(self, air):
        DistributedPlayerAI.DistributedPlayerAI.__init__(self, air)
        DistributedSmoothNodeAI.DistributedSmoothNodeAI.__init__(self, air)
        self.air = air
        self.dna = ToonDNA.ToonDNA()
        self.inventory = None
        self.fishCollection = None
        self.fishTank = None
        self.experience = None
        self.quests = []
        self.cogs = []
        self.cogCounts = []
        self.clothesTopsList = []
        self.clothesBottomsList = []
        self.hatList = []
        self.glassesList = []
        self.backpackList = []
        self.shoesList = []
        self.hat = (0, 0, 0)
        self.glasses = (0, 0, 0)
        self.backpack = (0, 0, 0)
        self.shoes = (0, 0, 0)
        self.cogTypes = [0,
                         0,
                         0,
                         0]
        self.cogLevel = [0,
                         0,
                         0,
                         0]
        self.cogRadar = [0,
                         0,
                         0,
                         0]
        self.cogIndex = -1
        self.sosPageFlag = 0
        self.buildingRadar = [0,
                              0,
                              0,
                              0]
        self.fishingRod = 0
        self.fishingTrophies = []
        self.trackArray = []
        self.emoteAccess = [0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0]
        self.maxBankMoney = ToontownGlobals.DefaultMaxBankMoney
        self.gardenSpecials = []
        self.houseId = 0
        self.posIndex = 0
        self.savedCheesyEffect = ToontownGlobals.CENormal
        self.savedCheesyHoodId = 0
        self.savedCheesyExpireTime = 0
        self.ghostMode = 0
        self.immortalMode = 0
        self.numPies = 0
        self.pieType = 0
        self.effectHandler = None
        self._isGM = False
        self._gmType = None
        self.hpOwnedByBattle = 0
        if simbase.wantBingo:
            self.bingoCheat = False
        self.customMessages = []
        self.droneSetup = [0, 1, 2]  # Default: Laser, Heal, Explodey
        self.catalogNotify = ToontownGlobals.NoItems
        self.mailboxNotify = ToontownGlobals.NoItems
        self.catalogScheduleCurrentWeek = 0
        self.catalogScheduleNextTime = 0
        self.monthlyCatalog = CatalogItemList.CatalogItemList()
        self.weeklyCatalog = CatalogItemList.CatalogItemList()
        self.backCatalog = CatalogItemList.CatalogItemList()
        self.onOrder = CatalogItemList.CatalogItemList(store=CatalogItem.Customization | CatalogItem.DeliveryDate)
        self.onGiftOrder = CatalogItemList.CatalogItemList(store=CatalogItem.Customization | CatalogItem.DeliveryDate)
        self.mailboxContents = CatalogItemList.CatalogItemList(store=CatalogItem.Customization)
        self.awardMailboxContents = CatalogItemList.CatalogItemList(store=CatalogItem.Customization)
        self.onAwardOrder = CatalogItemList.CatalogItemList(store=CatalogItem.Customization | CatalogItem.DeliveryDate)
        self.kart = None
        self.setBattleId(0)
        self.gardenStarted = False
        self.shovel = 0
        self.shovelSkill = 0
        self.wateringCan = 0
        self.wateringCanSkill = 0
        self.golfHoleBest = None
        self.golfCourseBest = None
        self.unlimitedSwing = False
        self.previousAccess = None
        self.numMailItems = 0
        self.simpleMailNotify = ToontownGlobals.NoItems
        self.inviteMailNotify = ToontownGlobals.NoItems
        self.invites = []
        self.hostedParties = []
        self.partiesInvitedTo = []
        self.partyReplyInfoBases = []
        self.modulelist = ModuleListAI.ModuleList()
        self.unlimitedGags = False
        self.instaKill = False
        self.instantDelivery = False
        self.alwaysHitSuits = False

        self._skillProfiles: dict[str, PlayerSkillProfile] = {}

        # Archipelago Stuff
        self.__uuid = None # UUID used to ensure we don't reply to our own packets.
        self._lastSeedName = "" # The previous room connected to, using ap's seed_name to validate. Might overlap if multiple rooms started from the same seed.
        self.seed = random.randint(1, 2**32)  # Seed to use for various rng elements
        self.baseGagSkillMultiplier = 1  # Multiplicative stacking gag xp multiplier to consider
        self.receivedItems: List[Tuple[int, int]] = []  # List of AP items received so far, [(index, itemid), (index, itemid)]
        self.checkedLocations: List[int] = []  # List of AP checks we have completed
        self.hintPoints = 0  # How many hint points the player has
        self.hintCostPercentage = 0 # How many points to hint an item, in % of checks.
        self.totalChecks = 0 # How many checks are there in total, calculates exact cost for display for client.
        self.damageMultiplier = 100
        self.overflowMod = 100
        self.deathReason: DeathReason = DeathReason.UNKNOWN
        self.slotData = {}  # set in connected_packet.py

    def generate(self):
        DistributedPlayerAI.DistributedPlayerAI.generate(self)
        DistributedSmoothNodeAI.DistributedSmoothNodeAI.generate(self)

    def announceGenerate(self):
        DistributedPlayerAI.DistributedPlayerAI.announceGenerate(self)
        DistributedSmoothNodeAI.DistributedSmoothNodeAI.announceGenerate(self)
        if self.isPlayerControlled():
            self.doLoginChecks()
            if self.WantOldGMNameBan:
                self._checkOldGMName()
            messenger.send('avatarEntered', [self])

        if hasattr(self, 'gameAccess') and self.gameAccess != 2:
            if self.hat[0] != 0:
                self.replaceItemInAccessoriesList(ToonDNA.HAT, 0, 0, 0, self.hat[0], self.hat[1], self.hat[2])
                self.b_setHatList(self.hatList)
                self.b_setHat(0, 0, 0)
            if self.glasses[0] != 0:
                self.replaceItemInAccessoriesList(ToonDNA.GLASSES, 0, 0, 0, self.glasses[0], self.glasses[1],
                                                  self.glasses[2])
                self.b_setGlassesList(self.glassesList)
                self.b_setGlasses(0, 0, 0)
            if self.backpack[0] != 0:
                self.replaceItemInAccessoriesList(ToonDNA.BACKPACK, 0, 0, 0, self.backpack[0], self.backpack[1],
                                                  self.backpack[2])
                self.b_setBackpackList(self.backpackList)
                self.b_setBackpack(0, 0, 0)
            if self.shoes[0] != 0:
                self.replaceItemInAccessoriesList(ToonDNA.SHOES, 0, 0, 0, self.shoes[0], self.shoes[1], self.shoes[2])
                self.b_setShoesList(self.shoesList)
                self.b_setShoes(0, 0, 0)
        from toontown.toon.DistributedNPCToonBaseAI import DistributedNPCToonBaseAI
        if not isinstance(self, DistributedNPCToonBaseAI):
            self.sendUpdate('setDefaultShard', [self.air.districtId])

    def doLoginChecks(self):
        if self.hp <= 0:
            self.b_setHp(1)

        # We need all toons to be friends with other toons.
        # So upon login, we make sure we're friends with other online toons!
        for toon in self.air.doFindAllInstances(DistributedToonAI):
            if not toon.isPlayerControlled() or toon is self:
                continue

            # Add the remote toon to our friends list.
            self.extendFriendsList(toon.getDoId(), 0)

            # Add ourselves to the remote toons friends list and update them.
            toon.extendFriendsList(self.getDoId(), 0)
            toon.d_setFriendsList(toon.getFriendsList())

        # Finally update the client with our new friends list.
        self.d_setFriendsList(self.getFriendsList())

    def setLocation(self, parentId, zoneId):
        DistributedPlayerAI.DistributedPlayerAI.setLocation(self, parentId, zoneId)
        from toontown.toon.DistributedNPCToonBaseAI import DistributedNPCToonBaseAI
        if isinstance(self, DistributedNPCToonBaseAI):
            return

        if not (100 <= zoneId < ToontownGlobals.DynamicZonesBegin):
            return

        hood = ZoneUtil.getHoodId(zoneId)
        self.sendUpdate('setLastHood', [hood])
        self.b_setDefaultZone(hood)
        self.addHoodVisited(hood)

        # if zoneId == ToontownGlobals.GoofySpeedway:
        #     self.addTeleportAccess(ToontownGlobals.GoofySpeedway)

    def sendDeleteEvent(self):
        DistributedAvatarAI.DistributedAvatarAI.sendDeleteEvent(self)

    def delete(self):
        self.notify.debug('----Deleting DistributedToonAI %d ' % self.doId)
        if self.isPlayerControlled():
            messenger.send('avatarExited', [self])
        taskName = self.uniqueName('cheesy-expires')
        taskMgr.remove(taskName)
        taskName = self.uniqueName('next-catalog')
        taskMgr.remove(taskName)
        taskName = self.uniqueName('next-delivery')
        taskMgr.remove(taskName)
        taskName = self.uniqueName('next-award-delivery')
        taskMgr.remove(taskName)
        taskName = 'next-bothDelivery-%s' % self.doId
        taskMgr.remove(taskName)
        self.stopToonUp()
        del self.dna
        if self.inventory:
            self.inventory.unload()
        del self.inventory
        del self.experience
        del self.kart
        self._sendExitServerEvent()
        DistributedSmoothNodeAI.DistributedSmoothNodeAI.delete(self)
        DistributedPlayerAI.DistributedPlayerAI.delete(self)

    def deleteDummy(self):
        self.notify.debug('----deleteDummy DistributedToonAI %d ' % self.doId)
        if self.inventory:
            self.inventory.unload()
        del self.inventory
        self.experience = None
        taskName = self.uniqueName('next-catalog')
        taskMgr.remove(taskName)
        return

    def ban(self, comment):
        simbase.air.banManager.ban(self.doId, self.DISLid, comment)

    def disconnect(self):
        self.requestDelete()

    def patchDelete(self):
        del self.dna
        if self.inventory:
            self.inventory.unload()
        del self.inventory
        del self.experience
        self.doNotDeallocateChannel = True
        self.zoneId = None
        DistributedSmoothNodeAI.DistributedSmoothNodeAI.delete(self)
        DistributedPlayerAI.DistributedPlayerAI.delete(self)
        return

    def handleLogicalZoneChange(self, newZoneId, oldZoneId):
        DistributedAvatarAI.DistributedAvatarAI.handleLogicalZoneChange(self, newZoneId, oldZoneId)
        if self.isPlayerControlled() and self.WantTpTrack:
            messenger.send(self.staticGetLogicalZoneChangeAllEvent(), [newZoneId, oldZoneId, self])
        if self.cogIndex != -1 and not ToontownAccessAI.canWearSuit(self.doId, newZoneId):
            if simbase.config.GetBool('cogsuit-hack-prevent', False):
                self.b_setCogIndex(-1)
            if not simbase.air.cogSuitMessageSent:
                self.notify.warning('%s handleLogicalZoneChange as a suit: %s' % (self.doId, self.cogIndex))
                self.air.writeServerEvent('suspicious', self.doId,
                                          'Toon wearing a cog suit with index: %s in a zone they are not allowed to in. Zone: %s' % (
                                          self.cogIndex, newZoneId))
                simbase.air.cogSuitMessageSent = True
                if simbase.config.GetBool('want-ban-wrong-suit-place', False):
                    commentStr = 'Toon %s wearing a suit in a zone they are not allowed to in. Zone: %s' % (
                    self.doId, newZoneId)
                    dislId = self.DISLid
                    simbase.air.banManager.ban(self.doId, dislId, commentStr)

    def announceZoneChange(self, newZoneId, oldZoneId):
        # self.air.welcomeValleyManager.toonSetZone(self.doId, newZoneId)
        broadcastZones = [oldZoneId, newZoneId]
        if self.isInEstate() or self.wasInEstate():
            broadcastZones = union(broadcastZones, self.estateZones)

    def checkAccessorySanity(self, accessoryType, idx, textureIdx, colorIdx):
        if idx == 0 and textureIdx == 0 and colorIdx == 0:
            return 1
        if accessoryType == ToonDNA.HAT:
            stylesDict = ToonDNA.HatStyles
            accessoryTypeStr = 'Hat'
        elif accessoryType == ToonDNA.GLASSES:
            stylesDict = ToonDNA.GlassesStyles
            accessoryTypeStr = 'Glasses'
        elif accessoryType == ToonDNA.BACKPACK:
            stylesDict = ToonDNA.BackpackStyles
            accessoryTypeStr = 'Backpack'
        elif accessoryType == ToonDNA.SHOES:
            stylesDict = ToonDNA.ShoesStyles
            accessoryTypeStr = 'Shoes'
        else:
            return 0
        try:
            styleStr = stylesDict.keys()[stylesDict.values().index([idx, textureIdx, colorIdx])]
            accessoryItemId = 0
            for itemId in CatalogAccessoryItem.AccessoryTypes.keys():
                if styleStr == CatalogAccessoryItem.AccessoryTypes[itemId][CatalogAccessoryItem.ATString]:
                    accessoryItemId = itemId
                    break

            if accessoryItemId == 0:
                self.air.writeServerEvent('suspicious', self.doId,
                                          'Toon tried to wear invalid %s %d %d %d' % (accessoryTypeStr,
                                                                                      idx,
                                                                                      textureIdx,
                                                                                      colorIdx))
                return 0
            if not simbase.config.GetBool('want-check-accessory-sanity', False):
                return 1
            accessoryItem = CatalogAccessoryItem.CatalogAccessoryItem(accessoryItemId)
            result = self.air.catalogManager.isItemReleased(accessoryItem)
            if result == 0:
                self.air.writeServerEvent('suspicious', self.doId,
                                          'Toon wore unreleased accessoryItem %d' % accessoryItemId)
            return result
        except:
            self.air.writeServerEvent('suspicious', self.doId,
                                      'Toon tried to wear invalid %s %d %d %d' % (accessoryTypeStr,
                                                                                  idx,
                                                                                  textureIdx,
                                                                                  colorIdx))
            return 0

    def b_setHat(self, idx, textureIdx, colorIdx):
        self.d_setHat(idx, textureIdx, colorIdx)
        self.setHat(idx, textureIdx, colorIdx)

    def d_setHat(self, idx, textureIdx, colorIdx):
        if not self.checkAccessorySanity(ToonDNA.HAT, idx, textureIdx, colorIdx):
            pass
        self.sendUpdate('setHat', [idx, textureIdx, colorIdx])

    def setHat(self, idx, textureIdx, colorIdx):
        if not self.checkAccessorySanity(ToonDNA.HAT, idx, textureIdx, colorIdx):
            pass
        self.hat = (idx, textureIdx, colorIdx)

    def getHat(self):
        return self.hat

    def b_setGlasses(self, idx, textureIdx, colorIdx):
        self.d_setGlasses(idx, textureIdx, colorIdx)
        self.setGlasses(idx, textureIdx, colorIdx)

    def d_setGlasses(self, idx, textureIdx, colorIdx):
        if not self.checkAccessorySanity(ToonDNA.GLASSES, idx, textureIdx, colorIdx):
            pass
        self.sendUpdate('setGlasses', [idx, textureIdx, colorIdx])

    def setGlasses(self, idx, textureIdx, colorIdx):
        if not self.checkAccessorySanity(ToonDNA.GLASSES, idx, textureIdx, colorIdx):
            pass
        self.glasses = (idx, textureIdx, colorIdx)

    def getGlasses(self):
        return self.glasses

    def b_setBackpack(self, idx, textureIdx, colorIdx):
        self.d_setBackpack(idx, textureIdx, colorIdx)
        self.setBackpack(idx, textureIdx, colorIdx)

    def d_setBackpack(self, idx, textureIdx, colorIdx):
        if not self.checkAccessorySanity(ToonDNA.BACKPACK, idx, textureIdx, colorIdx):
            pass
        self.sendUpdate('setBackpack', [idx, textureIdx, colorIdx])

    def setBackpack(self, idx, textureIdx, colorIdx):
        if not self.checkAccessorySanity(ToonDNA.BACKPACK, idx, textureIdx, colorIdx):
            pass
        self.backpack = (idx, textureIdx, colorIdx)

    def getBackpack(self):
        return self.backpack

    def b_setShoes(self, idx, textureIdx, colorIdx):
        self.d_setShoes(idx, textureIdx, colorIdx)
        self.setShoes(idx, textureIdx, colorIdx)

    def d_setShoes(self, idx, textureIdx, colorIdx):
        if not self.checkAccessorySanity(ToonDNA.SHOES, idx, textureIdx, colorIdx):
            pass
        self.sendUpdate('setShoes', [idx, textureIdx, colorIdx])

    def setShoes(self, idx, textureIdx, colorIdx):
        if not self.checkAccessorySanity(ToonDNA.SHOES, idx, textureIdx, colorIdx):
            pass
        self.shoes = (idx, textureIdx, colorIdx)

    def getShoes(self):
        return self.shoes

    def b_setDNAString(self, string):
        self.d_setDNAString(string)
        self.setDNAString(string)

    def d_setDNAString(self, string):
        self.sendUpdate('setDNAString', [string])

    def setDNAString(self, string):
        self.dna.makeFromNetString(string)
        if simbase.config.GetBool('adjust-dna', True) and self.verifyDNA() == False:
            logStr = 'AvatarHackWarning! invalid dna colors for %s old: %s new: %s' % (
            self.doId, str(ToonDNA.ToonDNA(string).asTuple()), str(self.dna.asTuple()))
            self.notify.warning(logStr)
            self.air.writeServerEvent('suspicious', self.doId, logStr)

    def verifyDNA(self):
        changed = False
        if self.isPlayerControlled():
            allowedColors = []
            if self.dna.gender == 'm':
                allowedColors = ToonDNA.defaultBoyColorList + [26]
            else:
                allowedColors = ToonDNA.defaultGirlColorList + [26]
            if self.dna.legColor not in allowedColors:
                self.dna.legColor = allowedColors[0]
                changed = True
            if self.dna.armColor not in allowedColors:
                self.dna.armColor = allowedColors[0]
                changed = True
            if self.dna.headColor not in allowedColors:
                self.dna.headColor = allowedColors[0]
                changed = True
            if changed:
                self.d_setDNAString(self.dna.makeNetString())
        return not changed

    def getDNAString(self):
        return self.dna.makeNetString()

    def getStyle(self):
        return self.dna

    def b_setExperience(self, experience):
        self.d_setExperience(experience)
        self.setExperience(experience)

    def d_setExperience(self, experience):
        self.sendUpdate('setExperience', [experience])

    def setExperience(self, experience):
        self.experience = Experience.Experience(experience, self)

    def getExperience(self):
        return self.experience.getCurrentExperience()

    def b_setInventory(self, inventory):
        self.setInventory(inventory)
        self.d_setInventory(self.getInventory())

    def d_setInventory(self, inventory):
        self.sendUpdate('setInventory', [inventory])

    def setInventory(self, inventoryNetString):
        if self.inventory:
            self.inventory.updateInvString(inventoryNetString)
        else:
            self.inventory = InventoryBase.InventoryBase(self, inventoryNetString)
        emptyInv = InventoryBase.InventoryBase(self)
        emptyString = emptyInv.makeNetString()
        lengthMatch = len(inventoryNetString) - len(emptyString)
        if lengthMatch != 0:
            if len(inventoryNetString) == 42:
                oldTracks = 7
                oldLevels = 6
            elif len(inventoryNetString) == 49:
                oldTracks = 7
                oldLevels = 7
            else:
                oldTracks = 0
                oldLevels = 0
            if oldTracks == 0 and oldLevels == 0:
                self.notify.warning('reseting invalid inventory to MAX on toon: %s' % self.doId)
                self.inventory.maxInventory(clearFirst=True)
            else:
                newInventory = InventoryBase.InventoryBase(self)
                oldList = emptyInv.makeFromNetStringForceSize(inventoryNetString, oldTracks, oldLevels)
                for indexTrack in range(0, oldTracks):
                    for indexGag in range(0, oldLevels):
                        newInventory.addItems(indexTrack, indexGag, oldList[indexTrack][indexGag])

                self.inventory.unload()
                self.inventory = newInventory
            self.d_setInventory(self.getInventory())

    def getInventory(self):
        return self.inventory.makeNetString()

    # Called for doing "cheaty" restocks (mainly for ~unlimitedgags command)
    # Refills inventory using the "ALL" fill mode.
    def doRestock(self):
        self.inventory.maxInventory(mode=InventoryBase.InventoryBase.FillMode.ALL, clearFirst=True)
        self.d_setInventory(self.inventory.makeNetString())

    def setDefaultShard(self, shard):
        self.defaultShard = shard
        self.notify.debug('setting default shard to %s' % shard)

    def getDefaultShard(self):
        return self.defaultShard

    def setDefaultZone(self, zone):
        self.defaultZone = zone
        self.notify.debug('setting default zone to %s' % zone)

    def d_setDefaultZone(self, zone):
        self.sendUpdate('setDefaultZone', [zone])

    def b_setDefaultZone(self, zone):
        self.setDefaultZone(zone)
        self.d_setDefaultZone(zone)

    def getDefaultZone(self):
        return self.defaultZone

    def setShtickerBook(self, string):
        self.notify.debug('setting shticker book to %s' % string)

    def getShtickerBook(self):
        return ''

    def d_setFriendsList(self, friendsList):
        self.sendUpdate('setFriendsList', [friendsList])
        return None

    def setFriendsList(self, friendsList):
        self.notify.debug('setting friends list to %s' % self.friendsList)
        self.friendsList = friendsList
        if friendsList:
            friendId = friendsList[-1]
            otherAv = self.air.doId2do.get(friendId)
            self.air.questManager.toonMadeFriend(self, otherAv)

    def getFriendsList(self):
        return self.friendsList

    def extendFriendsList(self, friendId, friendCode):
        for i in range(len(self.friendsList)):
            friendPair = self.friendsList[i]
            if friendPair[0] == friendId:
                self.friendsList[i] = (friendId, friendCode)
                return

        self.friendsList.append((friendId, friendCode))

    def getBattleId(self):
        if self.battleId >= 0:
            return self.battleId
        else:
            return 0

    def isBattling(self) -> bool:
        return self.getBattleId() > 0

    def b_setBattleId(self, battleId):
        self.setBattleId(battleId)
        self.d_setBattleId(battleId)

    def d_setBattleId(self, battleId):
        if self.battleId >= 0:
            self.sendUpdate('setBattleId', [battleId])
        else:
            self.sendUpdate('setBattleId', [0])

    def setBattleId(self, battleId):
        self.battleId = battleId

    def d_setMaxAccessories(self, max):
        self.sendUpdate('setMaxAccessories', [self.maxAccessories])

    def setMaxAccessories(self, max):
        self.maxAccessories = max

    def b_setMaxAccessories(self, max):
        self.setMaxAccessories(max)
        self.d_setMaxAccessories(max)

    def getMaxAccessories(self):
        return self.maxAccessories

    def isTrunkFull(self, extraAccessories=0):
        numAccessories = (len(self.hatList) + len(self.glassesList) + len(self.backpackList) + len(self.shoesList)) / 3
        return numAccessories + extraAccessories >= self.maxAccessories

    def d_setHatList(self, clothesList):
        self.sendUpdate('setHatList', [clothesList])
        return None

    def setHatList(self, clothesList):
        self.hatList = clothesList

    def b_setHatList(self, clothesList):
        self.setHatList(clothesList)
        self.d_setHatList(clothesList)

    def getHatList(self):
        return self.hatList

    def d_setGlassesList(self, clothesList):
        self.sendUpdate('setGlassesList', [clothesList])
        return None

    def setGlassesList(self, clothesList):
        self.glassesList = clothesList

    def b_setGlassesList(self, clothesList):
        self.setGlassesList(clothesList)
        self.d_setGlassesList(clothesList)

    def getGlassesList(self):
        return self.glassesList

    def d_setBackpackList(self, clothesList):
        self.sendUpdate('setBackpackList', [clothesList])
        return None

    def setBackpackList(self, clothesList):
        self.backpackList = clothesList

    def b_setBackpackList(self, clothesList):
        self.setBackpackList(clothesList)
        self.d_setBackpackList(clothesList)

    def getBackpackList(self):
        return self.backpackList

    def d_setShoesList(self, clothesList):
        self.sendUpdate('setShoesList', [clothesList])
        return None

    def setShoesList(self, clothesList):
        self.shoesList = clothesList

    def b_setShoesList(self, clothesList):
        self.setShoesList(clothesList)
        self.d_setShoesList(clothesList)

    def b_setMuzzle(self, muzzle):
        self.setMuzzle = muzzle

    def b_setEyes(self, eyes):
        self.setEyes = type

    def getShoesList(self):
        return self.shoesList

    def addToAccessoriesList(self, accessoryType, geomIdx, texIdx, colorIdx):
        if self.isTrunkFull():
            return 0
        if accessoryType == ToonDNA.HAT:
            itemList = self.hatList
        elif accessoryType == ToonDNA.GLASSES:
            itemList = self.glassesList
        elif accessoryType == ToonDNA.BACKPACK:
            itemList = self.backpackList
        elif accessoryType == ToonDNA.SHOES:
            itemList = self.shoesList
        else:
            return 0
        index = 0
        for i in range(0, len(itemList), 3):
            if itemList[i] == geomIdx and itemList[i + 1] == texIdx and itemList[i + 2] == colorIdx:
                return 0

        if accessoryType == ToonDNA.HAT:
            self.hatList.append(geomIdx)
            self.hatList.append(texIdx)
            self.hatList.append(colorIdx)
        elif accessoryType == ToonDNA.GLASSES:
            self.glassesList.append(geomIdx)
            self.glassesList.append(texIdx)
            self.glassesList.append(colorIdx)
        elif accessoryType == ToonDNA.BACKPACK:
            self.backpackList.append(geomIdx)
            self.backpackList.append(texIdx)
            self.backpackList.append(colorIdx)
        elif accessoryType == ToonDNA.SHOES:
            self.shoesList.append(geomIdx)
            self.shoesList.append(texIdx)
            self.shoesList.append(colorIdx)
        return 1

    def replaceItemInAccessoriesList(self, accessoryType, geomIdxA, texIdxA, colorIdxA, geomIdxB, texIdxB, colorIdxB):
        if accessoryType == ToonDNA.HAT:
            itemList = self.hatList
        elif accessoryType == ToonDNA.GLASSES:
            itemList = self.glassesList
        elif accessoryType == ToonDNA.BACKPACK:
            itemList = self.backpackList
        elif accessoryType == ToonDNA.SHOES:
            itemList = self.shoesList
        else:
            return 0
        index = 0
        for i in range(0, len(itemList), 3):
            if itemList[i] == geomIdxA and itemList[i + 1] == texIdxA and itemList[i + 2] == colorIdxA:
                if accessoryType == ToonDNA.HAT:
                    self.hatList[i] = geomIdxB
                    self.hatList[i + 1] = texIdxB
                    self.hatList[i + 2] = colorIdxB
                elif accessoryType == ToonDNA.GLASSES:
                    self.glassesList[i] = geomIdxB
                    self.glassesList[i + 1] = texIdxB
                    self.glassesList[i + 2] = colorIdxB
                elif accessoryType == ToonDNA.BACKPACK:
                    self.backpackList[i] = geomIdxB
                    self.backpackList[i + 1] = texIdxB
                    self.backpackList[i + 2] = colorIdxB
                else:
                    self.shoesList[i] = geomIdxB
                    self.shoesList[i + 1] = texIdxB
                    self.shoesList[i + 2] = colorIdxB
                return 1

        return 0

    def hasAccessory(self, accessoryType, geomIdx, texIdx, colorIdx):
        if accessoryType == ToonDNA.HAT:
            itemList = self.hatList
            cur = self.hat
        elif accessoryType == ToonDNA.GLASSES:
            itemList = self.glassesList
            cur = self.glasses
        elif accessoryType == ToonDNA.BACKPACK:
            itemList = self.backpackList
            cur = self.backpack
        elif accessoryType == ToonDNA.SHOES:
            itemList = self.shoesList
            cur = self.shoes
        else:
            raise 'invalid accessory type %s' % accessoryType
        if cur == (geomIdx, texIdx, colorIdx):
            return True
        for i in range(0, len(itemList), 3):
            if itemList[i] == geomIdx and itemList[i + 1] == texIdx and itemList[i + 2] == colorIdx:
                return True

        return False

    def isValidAccessorySetting(self, accessoryType, geomIdx, texIdx, colorIdx):
        if not geomIdx and not texIdx and not colorIdx:
            return True
        return self.hasAccessory(accessoryType, geomIdx, texIdx, colorIdx)

    def removeItemInAccessoriesList(self, accessoryType, geomIdx, texIdx, colorIdx):
        if accessoryType == ToonDNA.HAT:
            itemList = self.hatList
        elif accessoryType == ToonDNA.GLASSES:
            itemList = self.glassesList
        elif accessoryType == ToonDNA.BACKPACK:
            itemList = self.backpackList
        elif accessoryType == ToonDNA.SHOES:
            itemList = self.shoesList
        else:
            return 0
        listLen = len(itemList)
        if listLen < 3:
            self.notify.warning('Accessory list is not long enough to delete anything')
            return 0
        index = 0
        for i in range(0, len(itemList), 3):
            if itemList[i] == geomIdx and itemList[i + 1] == texIdx and itemList[i + 2] == colorIdx:
                itemList = itemList[0:i] + itemList[i + 3:listLen]
                if accessoryType == ToonDNA.HAT:
                    self.hatList = itemList[:]
                    styles = ToonDNA.HatStyles
                    descDict = TTLocalizer.HatStylesDescriptions
                elif accessoryType == ToonDNA.GLASSES:
                    self.glassesList = itemList[:]
                    styles = ToonDNA.GlassesStyles
                    descDict = TTLocalizer.GlassesStylesDescriptions
                elif accessoryType == ToonDNA.BACKPACK:
                    self.backpackList = itemList[:]
                    styles = ToonDNA.BackpackStyles
                    descDict = TTLocalizer.BackpackStylesDescriptions
                elif accessoryType == ToonDNA.SHOES:
                    self.shoesList = itemList[:]
                    styles = ToonDNA.ShoesStyles
                    descDict = TTLocalizer.ShoesStylesDescriptions
                styleName = 'none'
                for style in styles.items():
                    if style[1] == [geomIdx, texIdx, colorIdx]:
                        styleName = style[0]
                        break

                if styleName == 'none' or styleName not in descDict:
                    self.air.writeServerEvent('suspicious', self.doId,
                                              ' tried to remove wrong accessory code %d %d %d' % (
                                              geomIdx, texIdx, colorIdx))
                else:
                    self.air.writeServerEvent('accessory', self.doId, ' removed accessory %s' % descDict[styleName])
                return 1

        return 0

    def d_setMaxClothes(self, max):
        self.sendUpdate('setMaxClothes', [self.maxClothes])

    def setMaxClothes(self, max):
        self.maxClothes = max

    def b_setMaxClothes(self, max):
        self.setMaxClothes(max)
        self.d_setMaxClothes(max)

    def getMaxClothes(self):
        return self.maxClothes

    def isClosetFull(self, extraClothes=0):
        numClothes = len(self.clothesTopsList) / 4 + len(self.clothesBottomsList) / 2
        return numClothes + extraClothes >= self.maxClothes

    def d_setClothesTopsList(self, clothesList):
        self.sendUpdate('setClothesTopsList', [clothesList])
        return None

    def setClothesTopsList(self, clothesList):
        self.clothesTopsList = clothesList

    def b_setClothesTopsList(self, clothesList):
        self.setClothesTopsList(clothesList)
        self.d_setClothesTopsList(clothesList)

    def getClothesTopsList(self):
        return self.clothesTopsList

    def addToClothesTopsList(self, topTex, topTexColor, sleeveTex, sleeveTexColor):
        if self.isClosetFull():
            return 0
        index = 0
        for i in range(0, len(self.clothesTopsList), 4):
            if self.clothesTopsList[i] == topTex and self.clothesTopsList[i + 1] == topTexColor and \
                    self.clothesTopsList[i + 2] == sleeveTex and self.clothesTopsList[i + 3] == sleeveTexColor:
                return 0

        self.clothesTopsList.append(topTex)
        self.clothesTopsList.append(topTexColor)
        self.clothesTopsList.append(sleeveTex)
        self.clothesTopsList.append(sleeveTexColor)
        return 1

    def replaceItemInClothesTopsList(self, topTexA, topTexColorA, sleeveTexA, sleeveTexColorA, topTexB, topTexColorB,
                                     sleeveTexB, sleeveTexColorB):
        index = 0
        for i in range(0, len(self.clothesTopsList), 4):
            if self.clothesTopsList[i] == topTexA and self.clothesTopsList[i + 1] == topTexColorA and \
                    self.clothesTopsList[i + 2] == sleeveTexA and self.clothesTopsList[i + 3] == sleeveTexColorA:
                self.clothesTopsList[i] = topTexB
                self.clothesTopsList[i + 1] = topTexColorB
                self.clothesTopsList[i + 2] = sleeveTexB
                self.clothesTopsList[i + 3] = sleeveTexColorB
                return 1

        return 0

    def removeItemInClothesTopsList(self, topTex, topTexColor, sleeveTex, sleeveTexColor):
        listLen = len(self.clothesTopsList)
        if listLen < 4:
            self.notify.warning('Clothes top list is not long enough to delete anything')
            return 0
        index = 0
        for i in range(0, listLen, 4):
            if self.clothesTopsList[i] == topTex and self.clothesTopsList[i + 1] == topTexColor and \
                    self.clothesTopsList[i + 2] == sleeveTex and self.clothesTopsList[i + 3] == sleeveTexColor:
                self.clothesTopsList = self.clothesTopsList[0:i] + self.clothesTopsList[i + 4:listLen]
                return 1

        return 0

    def d_setClothesBottomsList(self, clothesList):
        self.sendUpdate('setClothesBottomsList', [clothesList])
        return None

    def setClothesBottomsList(self, clothesList):
        self.clothesBottomsList = clothesList

    def b_setClothesBottomsList(self, clothesList):
        self.setClothesBottomsList(clothesList)
        self.d_setClothesBottomsList(clothesList)

    def getClothesBottomsList(self):
        return self.clothesBottomsList

    def addToClothesBottomsList(self, botTex, botTexColor):
        if self.isClosetFull():
            self.notify.warning('clothes bottoms list is full')
            return 0
        index = 0
        for i in range(0, len(self.clothesBottomsList), 2):
            if self.clothesBottomsList[i] == botTex and self.clothesBottomsList[i + 1] == botTexColor:
                return 0

        self.clothesBottomsList.append(botTex)
        self.clothesBottomsList.append(botTexColor)
        return 1

    def replaceItemInClothesBottomsList(self, botTexA, botTexColorA, botTexB, botTexColorB):
        index = 0
        for i in range(0, len(self.clothesBottomsList), 2):
            if self.clothesBottomsList[i] == botTexA and self.clothesBottomsList[i + 1] == botTexColorA:
                self.clothesBottomsList[i] = botTexB
                self.clothesBottomsList[i + 1] = botTexColorB
                return 1

        return 0

    def removeItemInClothesBottomsList(self, botTex, botTexColor):
        listLen = len(self.clothesBottomsList)
        if listLen < 2:
            self.notify.warning('Clothes bottoms list is not long enough to delete anything')
            return 0
        index = 0
        for i in range(0, len(self.clothesBottomsList), 2):
            if self.clothesBottomsList[i] == botTex and self.clothesBottomsList[i + 1] == botTexColor:
                self.clothesBottomsList = self.clothesBottomsList[0:i] + self.clothesBottomsList[i + 2:listLen]
                return 1

        return 0

    def d_catalogGenClothes(self):
        self.sendUpdate('catalogGenClothes', [self.doId])

    def d_catalogGenAccessories(self):
        self.sendUpdate('catalogGenAccessories', [self.doId])

    def takeDamage(self, hpLost, quietly=0, sendTotal=1):
        if not self.immortalMode:
            if not quietly:
                self.sendUpdate('takeDamage', [hpLost])
            if hpLost > 0 and self.hp > 0:
                self.hp -= hpLost
                if self.hp <= 0:
                    messenger.send(self.getGoneSadMessage())
        if not self.hpOwnedByBattle:
            self.hp = min(self.hp, self.maxHp)
            if sendTotal:
                self.d_setHp(self.hp)

    @staticmethod
    def getGoneSadMessageForAvId(avId):
        return 'goneSad-%s' % avId

    def getGoneSadMessage(self):
        return self.getGoneSadMessageForAvId(self.doId)

    def setHp(self, hp):
        DistributedPlayerAI.DistributedPlayerAI.setHp(self, hp)
        if hp <= 0:
            messenger.send(self.getGoneSadMessage())

    def b_setTutorialAck(self, tutorialAck):
        self.d_setTutorialAck(tutorialAck)
        self.setTutorialAck(tutorialAck)

    def d_setTutorialAck(self, tutorialAck):
        self.sendUpdate('setTutorialAck', [tutorialAck])

    def setTutorialAck(self, tutorialAck):
        self.tutorialAck = tutorialAck

    def getTutorialAck(self):
        return self.tutorialAck

    def d_setEarnedExperience(self, earnedExp):
        self.sendUpdate('setEarnedExperience', [earnedExp])

    def setInterface(self, string):
        self.notify.debug('setting interface to %s' % string)

    def getInterface(self):
        return ''

    def setZonesVisited(self, hoods):
        self.safeZonesVisited = hoods
        self.notify.debug('setting safe zone list to %s' % self.safeZonesVisited)

    def getZonesVisited(self):
        return self.safeZonesVisited

    def setHoodsVisited(self, hoods):
        self.hoodsVisited = hoods
        self.notify.debug('setting hood zone list to %s' % self.hoodsVisited)

    def getHoodsVisited(self):
        return self.hoodsVisited

    def setLastHood(self, hood):
        self.lastHood = hood

    def getLastHood(self):
        return self.lastHood

    def b_setAnimState(self, animName, animMultiplier):
        self.setAnimState(animName, animMultiplier)
        self.d_setAnimState(animName, animMultiplier)

    def d_setAnimState(self, animName, animMultiplier):
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('setAnimState', [animName, animMultiplier, timestamp])

    def setAnimState(self, animName, animMultiplier, timestamp=0):
        if animName not in ToontownGlobals.ToonAnimStates:
            desc = 'tried to set invalid animState: %s' % (animName,)
            if config.GetBool('want-ban-animstate', 1):
                simbase.air.banManager.ban(self.doId, self.DISLid, desc)
            else:
                self.air.writeServerEvent('suspicious', self.doId, desc)
            return
        self.animName = animName
        self.animMultiplier = animMultiplier

    def b_setCogCount(self, cogCountList):
        self.setCogCount(cogCountList)
        self.d_setCogCount(cogCountList)

    def setCogCount(self, cogCountList):
        self.notify.debug('setting cogCounts to %s' % cogCountList)
        self.cogCounts = cogCountList

    def d_setCogCount(self, cogCountList):
        self.sendUpdate('setCogCount', [cogCountList])

    def getCogCount(self):
        return self.cogCounts

    def b_setCogTypes(self, types):
        self.setCogTypes(types)
        self.d_setCogTypes(types)

    def setCogTypes(self, types):
        if not types:
            self.notify.warning('cogTypes set to bad value: %s. Resetting to [0,0,0,0]' % types)
            self.cogTypes = [0, 0, 0, 0]
            return

        self.cogTypes = types

    def d_setCogTypes(self, types):
        self.sendUpdate('setCogTypes', [types])

    def getCogTypes(self):
        return self.cogTypes

    def b_setCogLevels(self, levels):
        self.setCogLevels(levels)
        self.d_setCogLevels(levels)

    def setCogLevels(self, levels):
        if not levels:
            self.notify.warning('cogLevels set to bad value: %s. Resetting to [0,0,0,0]' % levels)
            self.cogLevels = [0, 0, 0, 0]
            return

        self.cogLevels = levels

    def d_setCogLevels(self, levels):
        self.sendUpdate('setCogLevels', [levels])

    def getCogLevels(self):
        return self.cogLevels

    def incCogLevel(self, dept):
        newLevel = self.cogLevels[dept] + 1
        cogTypeStr = SuitDNA.suitHeadTypes[self.cogTypes[dept]]
        lastCog = self.cogTypes[dept] >= SuitDNA.suitsPerDept - 1
        if not lastCog:
            maxLevel = SuitBattleGlobals.getSuitAttributes(cogTypeStr).tier + 4
        else:
            maxLevel = ToontownGlobals.MaxCogSuitLevel
        if newLevel > maxLevel:
            if not lastCog:
                self.cogTypes[dept] += 1
                self.d_setCogTypes(self.cogTypes)
                cogTypeStr = SuitDNA.suitHeadTypes[self.cogTypes[dept]]
                self.cogLevels[dept] = SuitBattleGlobals.getSuitAttributes(cogTypeStr).tier
                self.d_setCogLevels(self.cogLevels)
        else:
            self.cogLevels[dept] += 1
            self.d_setCogLevels(self.cogLevels)
            # if lastCog:
            #     if self.cogLevels[dept] in ToontownGlobals.CogSuitHPLevels:
            #         maxHp = self.getMaxHp()
            #         maxHp = min(ToontownGlobals.MaxHpLimit, maxHp + 1)
            #         self.b_setMaxHp(maxHp)
            #         self.toonUp(maxHp)
        self.air.writeServerEvent('cogSuit', self.doId, '%s|%s|%s' % (dept, self.cogTypes[dept], self.cogLevels[dept]))

    def getNumPromotions(self, dept):
        if dept not in SuitDNA.suitDepts:
            self.notify.warning('getNumPromotions: Invalid parameter dept=%s' % dept)
            return 0
        deptIndex = SuitDNA.suitDepts.index(dept)
        cogType = self.cogTypes[deptIndex]
        cogTypeStr = SuitDNA.suitHeadTypes[cogType]
        lowestCogLevel = SuitBattleGlobals.getSuitAttributes(cogTypeStr).tier
        multiple = 5 * cogType
        additional = self.cogLevels[deptIndex] - lowestCogLevel
        numPromotions = multiple + additional
        return numPromotions

    def b_promote(self, dept):
        self.promote(dept)
        self.d_promote(dept)

    def promote(self, dept):
        self.incCogLevel(dept)

    def d_promote(self, dept):
        pass

    def b_setCogIndex(self, index):
        self.setCogIndex(index)
        if simbase.config.GetBool('cogsuit-hack-prevent', False):
            self.d_setCogIndex(self.cogIndex)
        else:
            self.d_setCogIndex(index)

    def setCogIndex(self, index):
        if index != -1 and not ToontownAccessAI.canWearSuit(self.doId, self.zoneId):
            if not simbase.air.cogSuitMessageSent:
                self.notify.warning('%s setCogIndex invalid: %s' % (self.doId, index))
                if simbase.config.GetBool('want-ban-wrong-suit-place', False):
                    commentStr = 'Toon %s trying to set cog index to %s in Zone: %s' % (self.doId, index, self.zoneId)
                    simbase.air.banManager.ban(self.doId, self.DISLid, commentStr)
        else:
            self.cogIndex = index

    def d_setCogIndex(self, index):
        self.sendUpdate('setCogIndex', [index])

    def getCogIndex(self):
        return self.cogIndex

    def b_setSosPageFlag(self, flag):
        self.setSosPageFlag(flag)
        self.d_setSosPageFlag(flag)

    def setSosPageFlag(self, flag):
        self.sosPageFlag = flag

    def d_setSosPageFlag(self, flag):
        self.sendUpdate('setSosPageFlag', [flag])

    def getSosPageFlag(self):
        return self.sosPageFlag

    def b_setFishCollection(self, genusList, speciesList, weightList):
        self.setFishCollection(genusList, speciesList, weightList)
        self.d_setFishCollection(genusList, speciesList, weightList)

    def d_setFishCollection(self, genusList, speciesList, weightList):
        self.sendUpdate('setFishCollection', [genusList, speciesList, weightList])

    def setFishCollection(self, genusList, speciesList, weightList):
        self.fishCollection = FishCollection.FishCollection()
        self.fishCollection.makeFromNetLists(genusList, speciesList, weightList)

    def getFishCollection(self):
        return self.fishCollection.getNetLists()

    def b_setMaxFishTank(self, maxTank):
        self.d_setMaxFishTank(maxTank)
        self.setMaxFishTank(maxTank)

    def d_setMaxFishTank(self, maxTank):
        self.sendUpdate('setMaxFishTank', [maxTank])

    def setMaxFishTank(self, maxTank):
        self.maxFishTank = maxTank

    def getMaxFishTank(self):
        return self.maxFishTank

    def b_setFishTank(self, genusList, speciesList, weightList):
        self.setFishTank(genusList, speciesList, weightList)
        self.d_setFishTank(genusList, speciesList, weightList)

    def d_setFishTank(self, genusList, speciesList, weightList):
        self.sendUpdate('setFishTank', [genusList, speciesList, weightList])

    def setFishTank(self, genusList, speciesList, weightList):
        self.fishTank = FishTank.FishTank()
        self.fishTank.makeFromNetLists(genusList, speciesList, weightList)

    def getFishTank(self):
        return self.fishTank.getNetLists()

    def addFishToTank(self, fish):
        numFish = len(self.fishTank)
        if numFish >= self.maxFishTank:
            self.notify.warning('addFishToTank: cannot add fish, tank is full')
            return 0
        elif self.fishTank.addFish(fish):
            self.d_setFishTank(*self.fishTank.getNetLists())
            return 1
        else:
            self.notify.warning('addFishToTank: addFish failed')
            return 0

    def removeFishFromTankAtIndex(self, index):
        if self.fishTank.removeFishAtIndex(index):
            self.d_setFishTank(*self.fishTank.getNetLists())
            return 1
        else:
            self.notify.warning('removeFishFromTank: cannot find fish')
            return 0

    def b_setFishingRod(self, rodId):
        self.d_setFishingRod(rodId)
        self.setFishingRod(rodId)

    def d_setFishingRod(self, rodId):
        self.sendUpdate('setFishingRod', [rodId])

    def setFishingRod(self, rodId):
        self.fishingRod = rodId

    def getFishingRod(self):
        return self.fishingRod

    def b_setFishingTrophies(self, trophyList):
        self.setFishingTrophies(trophyList)
        self.d_setFishingTrophies(trophyList)

    def setFishingTrophies(self, trophyList):
        self.notify.debug('setting fishingTrophies to %s' % trophyList)
        self.fishingTrophies = trophyList

    def d_setFishingTrophies(self, trophyList):
        self.sendUpdate('setFishingTrophies', [trophyList])

    def getFishingTrophies(self):
        return self.fishingTrophies

    def b_setQuests(self, questList):
        flattenedQuests = []
        for quest in questList:
            flattenedQuests.extend(quest)

        self.setQuests(flattenedQuests)
        self.d_setQuests(flattenedQuests)

    def d_setQuests(self, flattenedQuests):
        self.sendUpdate('setQuests', [flattenedQuests])

    def setQuests(self, flattenedQuests):
        self.notify.debug('setting quests to %s' % flattenedQuests)
        questList = []
        questLen = 5
        for i in range(0, len(flattenedQuests), questLen):
            questList.append(flattenedQuests[i:i + questLen])

        self.quests = questList

    def getQuests(self):
        flattenedQuests = []
        for quest in self.quests:
            flattenedQuests.extend(quest)

        return flattenedQuests

    def getQuest(self, questId, visitNpcId=None, rewardId=None):
        for quest in self.quests:
            if quest[0] != questId:
                continue
            if visitNpcId != None:
                if visitNpcId != quest[1] and visitNpcId != quest[2]:
                    continue
            if rewardId != None:
                if rewardId != quest[3]:
                    continue
            return quest

        return

    def hasQuest(self, questId, visitNpcId=None, rewardId=None):
        if self.getQuest(questId, visitNpcId=visitNpcId, rewardId=rewardId) == None:
            return False
        else:
            return True
        return

    def removeQuest(self, id, visitNpcId=None):
        index = -1
        for i in range(len(self.quests)):
            if self.quests[i][0] == id:
                if visitNpcId:
                    otherId = self.quests[i][2]
                    if visitNpcId == otherId:
                        index = i
                        break
                else:
                    index = i
                    break

        if index >= 0:
            del self.quests[i]
            self.b_setQuests(self.quests)
            return 1
        else:
            return 0

    def addQuest(self, quest, finalReward, recordHistory=1):
        self.quests.append(quest)
        self.b_setQuests(self.quests)
        if recordHistory:
            if quest[0] != Quests.VISIT_QUEST_ID:
                newQuestHistory = self.questHistory + [quest[0]]
                while newQuestHistory.count(Quests.VISIT_QUEST_ID) != 0:
                    newQuestHistory.remove(Quests.VISIT_QUEST_ID)

                self.b_setQuestHistory(newQuestHistory)
                if finalReward:
                    newRewardHistory = self.rewardHistory + [finalReward]
                    self.b_setRewardHistory(self.rewardTier, newRewardHistory)

    def removeAllTracesOfQuest(self, questId, rewardId):
        self.notify.debug('removeAllTracesOfQuest: questId: %s rewardId: %s' % (questId, rewardId))
        self.notify.debug('removeAllTracesOfQuest: quests before: %s' % self.quests)
        removedQuest = self.removeQuest(questId)
        self.notify.debug('removeAllTracesOfQuest: quests after: %s' % self.quests)
        self.notify.debug('removeAllTracesOfQuest: questHistory before: %s' % self.questHistory)
        removedQuestHistory = self.removeQuestFromHistory(questId)
        self.notify.debug('removeAllTracesOfQuest: questHistory after: %s' % self.questHistory)
        self.notify.debug('removeAllTracesOfQuest: reward history before: %s' % self.rewardHistory)
        removedRewardHistory = self.removeRewardFromHistory(rewardId)
        self.notify.debug('removeAllTracesOfQuest: reward history after: %s' % self.rewardHistory)
        return (removedQuest, removedQuestHistory, removedRewardHistory)

    def requestDeleteQuest(self, questDesc):
        if len(questDesc) != 5:
            self.air.writeServerEvent('suspicious', self.doId,
                                      'Toon tried to delete invalid questDesc %s' % str(questDesc))
            self.notify.warning('%s.requestDeleteQuest(%s) -- questDesc has incorrect params' % (self, str(questDesc)))
            return
        questId = questDesc[0]
        rewardId = questDesc[3]
        if not self.hasQuest(questId, rewardId=rewardId):
            self.air.writeServerEvent('suspicious', self.doId,
                                      "Toon tried to delete quest they don't have %s" % str(questDesc))
            self.notify.warning("%s.requestDeleteQuest(%s) -- Toon doesn't have that quest" % (self, str(questDesc)))
            return
        if not Quests.isQuestJustForFun(questId, rewardId):
            self.air.writeServerEvent('suspicious', self.doId,
                                      'Toon tried to delete non-Just For Fun quest %s' % str(questDesc))
            self.notify.warning(
                '%s.requestDeleteQuest(%s) -- Tried to cancel non-Just For Fun quest' % (self, str(questDesc)))
            return
        removedStatus = self.removeAllTracesOfQuest(questId, rewardId)
        if 0 in removedStatus:
            self.notify.warning('%s.requestDeleteQuest(%s) -- Failed to remove quest, status=%s' % (
            self, str(questDesc), removedStatus))

    def b_setQuestCarryLimit(self, limit):
        self.setQuestCarryLimit(limit)
        self.d_setQuestCarryLimit(limit)

    def d_setQuestCarryLimit(self, limit):
        self.sendUpdate('setQuestCarryLimit', [limit])

    def setQuestCarryLimit(self, limit):
        self.notify.debug('setting questCarryLimit to %s' % limit)
        self.questCarryLimit = limit

    def getQuestCarryLimit(self):
        return self.questCarryLimit

    def b_setMaxCarry(self, maxCarry):
        self.setMaxCarry(maxCarry)
        self.d_setMaxCarry(maxCarry)

    def d_setMaxCarry(self, maxCarry):
        self.sendUpdate('setMaxCarry', [maxCarry])

    def setMaxCarry(self, maxCarry):
        self.maxCarry = maxCarry

    def getMaxCarry(self):
        return self.maxCarry

    def b_setCheesyEffect(self, effect, hoodId, expireTime):
        self.setCheesyEffect(effect, hoodId, expireTime)
        self.d_setCheesyEffect(effect, hoodId, expireTime)

    def d_setCheesyEffect(self, effect, hoodId, expireTime):
        self.sendUpdate('setCheesyEffect', [effect, hoodId, expireTime])

    def setCheesyEffect(self, effect, hoodId, expireTime):
        if simbase.air.holidayManager and ToontownGlobals.WINTER_CAROLING not in simbase.air.holidayManager.currentHolidays and ToontownGlobals.WACKY_WINTER_CAROLING not in simbase.air.holidayManager.currentHolidays and effect == ToontownGlobals.CESnowMan:
            self.b_setCheesyEffect(ToontownGlobals.CENormal, hoodId, expireTime)
            return
        self.savedCheesyEffect = effect
        self.savedCheesyHoodId = hoodId
        self.savedCheesyExpireTime = expireTime
        if self.air.doLiveUpdates:
            taskName = self.uniqueName('cheesy-expires')
            taskMgr.remove(taskName)
            if effect != ToontownGlobals.CENormal:
                duration = expireTime * 60 - time.time()
                if duration > 0:
                    taskMgr.doMethodLater(duration, self.__undoCheesyEffect, taskName)
                else:
                    self.__undoCheesyEffect(None)
        return

    def getCheesyEffect(self):
        return (self.savedCheesyEffect, self.savedCheesyHoodId, self.savedCheesyExpireTime)

    def __undoCheesyEffect(self, task):
        self.b_setCheesyEffect(ToontownGlobals.CENormal, 0, 0)
        return Task.cont

    def playSound(self, sound):
        self.sendUpdate('playSound', [sound])

    def b_setTrackAccess(self, trackArray):
        self.setTrackAccess(trackArray)
        self.d_setTrackAccess(trackArray)

    def d_setTrackAccess(self, trackArray):
        self.sendUpdate('setTrackAccess', [trackArray])

    def setTrackAccess(self, trackArray):
        self.trackArray = trackArray

    def getTrackAccess(self):
        return self.trackArray

    def addTrackAccess(self, track, level=ToontownBattleGlobals.UBER_GAG_LEVEL_INDEX):
        self.setTrackAccessLevel(track, level)

    def removeTrackAccess(self, track):
        self.trackArray[track] = 0
        self.experience.fixTrackAccessLimits()
        self.b_setExperience(self.experience.getCurrentExperience())
        self.b_setTrackAccess(self.trackArray)

    def hasTrackAccess(self, track):
        if self.trackArray and track < len(self.trackArray):
            return self.trackArray[track]
        else:
            return 0

    # What level gags are we allowed to learn for this track
    def getTrackAccessLevel(self, track):
        if not self.trackArray:
            return 0

        if track >= len(self.trackArray):
            return 0

        return self.trackArray[track]

    # What level gags do we want to allow for learning gags in this track
    # 0 will revoke access to the track, 1-7 will allow us to learn level 1-7 gags respectively, 8+ functions the same as 7
    def setTrackAccessLevel(self, track, level):
        if not self.trackArray:
            return 0

        if track >= len(self.trackArray):
            return 0

        self.trackArray[track] = level
        self.experience.fixTrackAccessLimits()
        self.b_setExperience(self.experience.getCurrentExperience())
        self.b_setTrackAccess(self.trackArray)

    def b_setTrackProgress(self, trackId, progress):
        self.setTrackProgress(trackId, progress)
        self.d_setTrackProgress(trackId, progress)

    def d_setTrackProgress(self, trackId, progress):
        self.sendUpdate('setTrackProgress', [trackId, progress])

    def setTrackProgress(self, trackId, progress):
        self.trackProgressId = trackId
        self.trackProgress = progress

    def addTrackProgress(self, trackId, progressIndex):
        if self.trackProgressId != trackId:
            self.notify.warning('tried to update progress on a track toon is not training')
        newProgress = self.trackProgress | 1 << progressIndex - 1
        self.b_setTrackProgress(self.trackProgressId, newProgress)

    def clearTrackProgress(self):
        self.b_setTrackProgress(-1, 0)

    def getTrackProgress(self):
        return [self.trackProgressId, self.trackProgress]

    def b_setHoodsVisited(self, hoodsVisitedArray):
        self.hoodsVisited = hoodsVisitedArray
        self.d_setHoodsVisited(hoodsVisitedArray)

    def d_setHoodsVisited(self, hoodsVisitedArray):
        self.sendUpdate('setHoodsVisited', [hoodsVisitedArray])

    def addHoodVisited(self, hoodId):
        hoods = self.getHoodsVisited()
        if hoodId in hoods:
            return

        hoods.append(hoodId)
        self.b_setHoodsVisited(hoods)

    def b_setTeleportAccess(self, teleportZoneArray):
        self.setTeleportAccess(teleportZoneArray)
        self.d_setTeleportAccess(teleportZoneArray)

    def d_setTeleportAccess(self, teleportZoneArray):
        self.sendUpdate('setTeleportAccess', [teleportZoneArray])

    def setTeleportAccess(self, teleportZoneArray):
        self.teleportZoneArray = teleportZoneArray

    def getTeleportAccess(self):
        return self.teleportZoneArray

    def hasTeleportAccess(self, zoneId):
        return zoneId in self.teleportZoneArray

    def addTeleportAccess(self, zoneId):

        # Do not discover this zone immediately if we are given teleport access
        # self.addHoodVisited(zoneId)

        if zoneId not in self.teleportZoneArray:
            self.teleportZoneArray.append(zoneId)
            self.b_setTeleportAccess(self.teleportZoneArray)

    def removeTeleportAccess(self, zoneId):
        if zoneId in self.teleportZoneArray:
            self.teleportZoneArray.remove(zoneId)
            self.b_setTeleportAccess(self.teleportZoneArray)

    def checkTeleportAccess(self, zoneId):
        if zoneId not in self.getTeleportAccess():
            simbase.air.writeServerEvent('suspicious', self.doId,
                                         'Toon teleporting to zone %s they do not have access to.' % zoneId)
            if simbase.config.GetBool('want-ban-teleport', False):
                commentStr = 'Toon %s teleporting to a zone %s they do not have access to' % (self.doId, zoneId)
                simbase.air.banManager.ban(self.doId, self.DISLid, commentStr)

    def b_setQuestHistory(self, questList):
        self.setQuestHistory(questList)
        self.d_setQuestHistory(questList)

    def d_setQuestHistory(self, questList):
        self.sendUpdate('setQuestHistory', [questList])

    def setQuestHistory(self, questList):
        self.notify.debug('setting quest history to %s' % questList)
        self.questHistory = questList

    def getQuestHistory(self):
        return self.questHistory

    def removeQuestFromHistory(self, questId):
        if questId in self.questHistory:
            self.questHistory.remove(questId)
            self.d_setQuestHistory(self.questHistory)
            return 1
        else:
            return 0

    def removeRewardFromHistory(self, rewardId):
        rewardTier, rewardHistory = self.getRewardHistory()
        if rewardId in rewardHistory:
            rewardHistory.remove(rewardId)
            self.b_setRewardHistory(rewardTier, rewardHistory)
            return 1
        else:
            return 0

    def b_setRewardHistory(self, tier, rewardList):
        self.setRewardHistory(tier, rewardList)
        self.d_setRewardHistory(tier, rewardList)

    def d_setRewardHistory(self, tier, rewardList):
        self.sendUpdate('setRewardHistory', [tier, rewardList])

    def setRewardHistory(self, tier, rewardList):
        self.air.writeServerEvent('questTier', self.getDoId(), str(tier))
        self.notify.debug('setting reward history to tier %s, %s' % (tier, rewardList))
        self.rewardTier = tier
        self.rewardHistory = rewardList

    def getRewardHistory(self):
        return (self.rewardTier, self.rewardHistory)

    def getRewardTier(self):
        return self.rewardTier

    def b_setEmoteAccess(self, bits):
        self.setEmoteAccess(bits)
        self.d_setEmoteAccess(bits)

    def d_setEmoteAccess(self, bits):
        self.sendUpdate('setEmoteAccess', [bits])

    def setEmoteAccess(self, bits):
        if len(bits) == 20:
            bits.extend([0,
                         0,
                         0,
                         0,
                         0])
            self.b_setEmoteAccess(bits)
        elif len(bits) != len(self.emoteAccess):
            self.notify.warning('New emote access list must be the same size as the old one.')
            return
        self.emoteAccess = bits

    def getEmoteAccess(self):
        return self.emoteAccess

    def setEmoteAccessId(self, id, bit):
        self.emoteAccess[id] = bit
        self.d_setEmoteAccess(self.emoteAccess)

    def d_playEmote(self, emoteIndex: int, animMultiplier: float = 1.0, timestamp=None):
        if timestamp is None:
            timestamp = globalClockDelta.getRealNetworkTime()

        self.sendUpdate('playEmote', [emoteIndex, animMultiplier, timestamp])

    def b_setHouseId(self, id):
        self.setHouseId(id)
        self.d_setHouseId(id)

    def d_setHouseId(self, id):
        self.sendUpdate('setHouseId', [id])

    def setHouseId(self, id):
        self.houseId = id

    def getHouseId(self):
        return self.houseId

    def setPosIndex(self, index):
        self.posIndex = index

    def getPosIndex(self):
        return self.posIndex

    def b_setCustomMessages(self, customMessages):
        self.d_setCustomMessages(customMessages)
        self.setCustomMessages(customMessages)

    def d_setCustomMessages(self, customMessages):
        self.sendUpdate('setCustomMessages', [customMessages])

    def setCustomMessages(self, customMessages):
        self.customMessages = customMessages

    def getCustomMessages(self):
        return self.customMessages

    def b_setDroneSetup(self, droneSetup):
        self.d_setDroneSetup(droneSetup)
        self.setDroneSetup(droneSetup)

    def d_setDroneSetup(self, droneSetup):
        self.sendUpdate('setDroneSetup', [droneSetup])

    def setDroneSetup(self, droneSetup):
        # Ensure we have exactly 3 slots
        if len(droneSetup) != 3:
            self.notify.warning(f'Invalid droneSetup length {len(droneSetup)}, expected 3')
            droneSetup = [0, 1, 2]  # Default fallback
        self.droneSetup = droneSetup

    def getDroneSetup(self):
        return self.droneSetup

    def b_setResistanceMessages(self, resistanceMessages):
        self.d_setResistanceMessages(resistanceMessages)
        self.setResistanceMessages(resistanceMessages)

    def d_setResistanceMessages(self, resistanceMessages):
        self.sendUpdate('setResistanceMessages', [resistanceMessages])

    def setResistanceMessages(self, resistanceMessages):
        self.resistanceMessages = resistanceMessages

    def getResistanceMessages(self):
        return self.resistanceMessages

    def addResistanceMessage(self, textId):
        msgs = self.getResistanceMessages()
        for i in range(len(msgs)):
            if msgs[i][0] == textId:
                msgs[i][1] += 1
                self.b_setResistanceMessages(msgs)
                return

        msgs.append([textId, 1])
        self.b_setResistanceMessages(msgs)

    def removeResistanceMessage(self, textId):
        msgs = self.getResistanceMessages()
        for i in range(len(msgs)):
            if msgs[i][0] == textId:
                msgs[i][1] -= 1
                if msgs[i][1] <= 0:
                    del msgs[i]
                self.b_setResistanceMessages(msgs)
                return 1

        self.notify.warning("Toon %s doesn't have resistance message %s" % (self.doId, textId))
        return 0

    def restockAllResistanceMessages(self, charges=1):
        from toontown.chat import ResistanceChat
        msgs = []
        for menuIndex in ResistanceChat.resistanceMenu:
            for itemIndex in ResistanceChat.getItems(menuIndex):
                textId = ResistanceChat.encodeId(menuIndex, itemIndex)
                msgs.append([textId, charges])

        self.b_setResistanceMessages(msgs)

    def b_setGhostMode(self, flag):
        self.setGhostMode(flag)
        self.d_setGhostMode(flag)

    def d_setGhostMode(self, flag):
        self.sendUpdate('setGhostMode', [flag])

    def setGhostMode(self, flag):
        self.ghostMode = flag

    def b_setImmortalMode(self, flag):
        self.setImmortalMode(flag)
        self.d_setImmortalMode(flag)

    def d_setImmortalMode(self, flag):
        self.sendUpdate('setImmortalMode', [flag])

    def setImmortalMode(self, flag):
        self.immortalMode = flag

    def getImmortalMode(self):
        return self.immortalMode

    def b_setSpeedChatStyleIndex(self, index):
        self.setSpeedChatStyleIndex(index)
        self.d_setSpeedChatStyleIndex(index)

    def d_setSpeedChatStyleIndex(self, index):
        self.sendUpdate('setSpeedChatStyleIndex', [index])

    def setSpeedChatStyleIndex(self, index):
        self.speedChatStyleIndex = index

    def getSpeedChatStyleIndex(self):
        return self.speedChatStyleIndex

    def b_setMaxMoney(self, maxMoney):
        self.d_setMaxMoney(maxMoney)
        self.setMaxMoney(maxMoney)

    def d_setMaxMoney(self, maxMoney):
        self.sendUpdate('setMaxMoney', [maxMoney])

    def setMaxMoney(self, maxMoney):
        self.maxMoney = maxMoney

    def getMaxMoney(self):
        return self.maxMoney

    def addMoney(self, deltaMoney):
        money = deltaMoney + self.money
        pocketMoney = min(money, self.maxMoney)

    def takeMoney(self, deltaMoney, bUseBank=False):
        totalMoney = self.money
        if deltaMoney > totalMoney:
            self.notify.warning('Not enough money! AvId: %s Has:%s Charged:%s' % (self.doId, totalMoney, deltaMoney))
            return False
        self.b_setMoney(self.money - deltaMoney)
        return True

    def b_setMoney(self, money):
        if bboard.get('autoRich-%s' % self.doId, False):
            money = self.getMaxMoney()
        self.setMoney(money)
        self.d_setMoney(money)

    def d_setMoney(self, money):
        self.sendUpdate('setMoney', [money])

    def setMoney(self, money):
        if money < 0:
            money = 0
        elif money > self.getMaxMoney():
            money = self.getMaxMoney()
        self.money = money

    def getMoney(self):
        return self.money

    def getTotalMoney(self):
        return self.money # Bank is unused, leave it out of any purchase calculations.

    def b_setMaxBankMoney(self, maxMoney):
        self.d_setMaxBankMoney(maxMoney)
        self.setMaxBankMoney(maxMoney)

    def d_setMaxBankMoney(self, maxMoney):
        self.sendUpdate('setMaxBankMoney', [maxMoney])

    def setMaxBankMoney(self, maxMoney):
        self.maxBankMoney = maxMoney

    def getMaxBankMoney(self):
        return self.maxBankMoney

    def b_setBankMoney(self, money):
        bankMoney = min(money, self.maxBankMoney)
        self.setBankMoney(bankMoney)
        self.d_setBankMoney(bankMoney)

    def d_setBankMoney(self, money):
        self.sendUpdate('setBankMoney', [money])

    def setBankMoney(self, money):
        self.bankMoney = money

    def getBankMoney(self):
        return self.bankMoney

    def tossPie(self, x, y, z, h, p, r, sequence, power, timestamp32):
        if not self.validate(self.doId, self.numPies > 0, 'tossPie with no pies available'):
            return
        if self.numPies != ToontownGlobals.FullPies:
            self.b_setNumPies(self.numPies - 1)

    def b_setNumPies(self, numPies):
        self.setNumPies(numPies)
        self.d_setNumPies(numPies)

    def d_setNumPies(self, numPies):
        self.sendUpdate('setNumPies', [numPies])

    def setNumPies(self, numPies):
        self.numPies = numPies

    def b_setPieType(self, pieType):
        self.setPieType(pieType)
        self.d_setPieType(pieType)

    def d_setPieType(self, pieType):
        self.sendUpdate('setPieType', [pieType])

    def setPieType(self, pieType):
        self.pieType = pieType

    def d_setTrophyScore(self, score):
        self.sendUpdate('setTrophyScore', [score])

    def stopToonUp(self):
        taskMgr.remove(self.uniqueName('safeZoneToonUp'))
        self.ignore(self.air.getAvatarExitEvent(self.getDoId()))

    def startToonUp(self, healFrequency):
        self.stopToonUp()
        self.healFrequency = healFrequency
        self.__waitForNextToonUp()

    def __waitForNextToonUp(self):
        taskMgr.doMethodLater(self.healFrequency, self.toonUpTask, self.uniqueName('safeZoneToonUp'))

    def __getPassiveToonupAmount(self):
        return math.ceil(self.getMaxHp() * ToontownGlobals.PassiveHealPercentage)

    def toonUpTask(self, task):
        self.toonUp(self.__getPassiveToonupAmount())
        self.__waitForNextToonUp()
        return Task.done

    def toonUp(self, hpGained: int, quietly=False, sendTotal=True):

        # We should always work with ints when modifying avatar HP, if we were given a float fix it
        if isinstance(hpGained, float):
            self.notify.debug(f"Tried to heal {self.getName()} with invalid type float ({hpGained}), rounding up to an integer")
            hpGained = int(math.ceil(hpGained))

        # We cannot toon up for negative healing, if this happens skip
        if hpGained <= 0:
            self.notify.debug(f"Tried to heal {self.getName()} for non-positive integer: {hpGained}, cancelling...")
            return

        # Since we are healing, make sure our hp is not negative to apply proper healing
        if self.getHp() < 0:
            self.hp = 0  # Raw dog the hp attribute set here to skip sending an event

        # Apply the healing but make sure we do not overheal
        oldHp = self.getHp()
        newHp = oldHp + hpGained
        newHp = min(self.getMaxHp(), newHp)
        self.setHp(newHp)
        actualHpGained = newHp - oldHp

        # If we want to broadcast this toonup...
        if not quietly and actualHpGained > 0:
            self.sendUpdate('toonUp', [actualHpGained])

        # Only sync the toons HP if they are not currently watching a battle movie.
        if sendTotal and not self.hpOwnedByBattle:
            self.d_setHp(self.getHp())

    def isToonedUp(self):
        return self.hp >= self.maxHp

    def makeBlackCat(self):
        if self.dna.getAnimal() != 'cat':
            return 'not a cat'
        self.air.writeServerEvent('blackCat', self.doId, '')
        newDna = ToonDNA.ToonDNA()
        newDna.makeFromNetString(self.dna.makeNetString())
        black = 26
        newDna.updateToonProperties(armColor=black, legColor=black, headColor=black)
        self.b_setDNAString(newDna.makeNetString())
        return None

    def b_announceBingo(self):
        self.d_announceBingo()
        self.announceBingo()

    def d_announceBingo(self):
        self.sendUpdate('announceBingo', [])

    def announceBingo(self):
        pass

    def incrementPopulation(self):
        if self.isPlayerControlled():
            DistributedPlayerAI.DistributedPlayerAI.incrementPopulation(self)

    def decrementPopulation(self):
        if self.isPlayerControlled():
            DistributedPlayerAI.DistributedPlayerAI.decrementPopulation(self)

    if __dev__:

        def _logGarbage(self):
            if self.isPlayerControlled():
                DistributedPlayerAI.DistributedPlayerAI._logGarbage(self)

    def reqSCResistance(self, msgIndex, nearbyPlayers):
        self.d_setSCResistance(msgIndex, nearbyPlayers)

    def d_setSCResistance(self, msgIndex, nearbyPlayers):

        # If this toon tried to request a unite but is battling, don't do anything.
        if self.isBattling():
            return

        if not ResistanceChat.validateId(msgIndex):
            self.air.writeServerEvent('suspicious', self.doId, 'said resistance %s, which is invalid.' % msgIndex)
            return
        if not self.removeResistanceMessage(msgIndex):
            self.air.writeServerEvent('suspicious', self.doId, 'said resistance %s, but does not have it.' % msgIndex)
            return
        if hasattr(self, 'autoResistanceRestock') and self.autoResistanceRestock:
            self.restockAllResistanceMessages(1)
        affectedPlayers = []
        for toonId in nearbyPlayers:
            toon = self.air.doId2do.get(toonId)
            if not toon:
                self.notify.warning('%s said resistance %s for %s; not on server' % (self.doId, msgIndex, toonId))
            elif toon.__class__ != DistributedToonAI:
                self.air.writeServerEvent('suspicious', self.doId, 'said resistance %s for %s; object of type %s' % (
                msgIndex, toonId, toon.__class__.__name__))
            elif toonId in affectedPlayers:
                self.air.writeServerEvent('suspicious', self.doId,
                                          'said resistance %s for %s twice in same message.' % (msgIndex, toonId))
            else:
                toon.doResistanceEffect(msgIndex)
                affectedPlayers.append(toonId)

        if len(affectedPlayers) > 50:
            self.air.writeServerEvent('suspicious', self.doId,
                                      'said resistance %s for %s toons.' % (msgIndex, len(affectedPlayers)))
            self.notify.warning('%s said resistance %s for %s toons: %s' % (self.doId,
                                                                            msgIndex,
                                                                            len(affectedPlayers),
                                                                            affectedPlayers))
        self.sendUpdate('setSCResistance', [msgIndex, affectedPlayers])
        type = ResistanceChat.getMenuName(msgIndex)
        value = ResistanceChat.getItemValue(msgIndex)
        self.air.writeServerEvent('resistanceChat', self.zoneId, '%s|%s|%s|%s' % (self.doId,
                                                                                  type,
                                                                                  value,
                                                                                  affectedPlayers))

    def doResistanceEffect(self, msgIndex):

        # If we are in a battle, a unite can never affect us.
        if self.isBattling():
            return

        msgType, itemIndex = ResistanceChat.decodeId(msgIndex)
        msgValue = ResistanceChat.getItemValue(msgIndex)
        if msgType == ResistanceChat.RESISTANCE_TOONUP:
            if msgValue == -1:
                self.toonUp(self.maxHp)
            else:
                self.toonUp(msgValue)
            self.notify.debug('Toon-up for ' + self.name)
        elif msgType == ResistanceChat.RESISTANCE_RESTOCK:
            self.inventory.maxInventory(mode=InventoryBase.InventoryBase.FillMode.POWER, maxGagLevel=msgValue)
            self.d_setInventory(self.inventory.makeNetString())
            self.notify.debug('Restock for ' + self.name)
        elif msgType == ResistanceChat.RESISTANCE_MONEY:
            if msgValue == -1:
                self.addMoney(999999)
            else:
                self.addMoney(msgValue)
            self.notify.debug('Money for ' + self.name)

    def squish(self, damage):
        self.takeDamage(damage)

    def takeOutKart(self, zoneId=None):
        if not self.kart:
            from toontown.racing import DistributedVehicleAI
            self.kart = DistributedVehicleAI.DistributedVehicleAI(self.air, self.doId)
            if zoneId:
                self.kart.generateWithRequired(zoneId)
            else:
                self.kart.generateWithRequired(self.zoneId)
            self.kart.start()

    def reqCogSummons(self, type, suitIndex):
        if type not in ('single', 'building', 'invasion'):
            self.air.writeServerEvent('suspicious', self.doId, 'invalid cog summons type: %s' % type)
            self.sendUpdate('cogSummonsResponse', ['fail', suitIndex, 0])
            return
        if suitIndex >= len(SuitDNA.suitHeadTypes):
            self.air.writeServerEvent('suspicious', self.doId, 'invalid suitIndex: %s' % suitIndex)
            self.sendUpdate('cogSummonsResponse', ['fail', suitIndex, 0])
            return
        if not self.hasCogSummons(suitIndex, type):
            self.air.writeServerEvent('suspicious', self.doId, 'bogus cog summons')
            self.sendUpdate('cogSummonsResponse', ['fail', suitIndex, 0])
            return
        if ZoneUtil.isWelcomeValley(self.zoneId):
            self.sendUpdate('cogSummonsResponse', ['fail', suitIndex, 0])
            return
        returnCode = None
        if type == 'single':
            returnCode = self.doSummonSingleCog(suitIndex)
        elif type == 'building':
            returnCode = self.doBuildingTakeover(suitIndex)
        elif type == 'invasion':
            returnCode = self.doCogInvasion(suitIndex)
        if returnCode:
            if returnCode[0] == 'success':
                self.air.writeServerEvent('cogSummoned', self.doId, '%s|%s|%s' % (type, suitIndex, self.zoneId))
                self.removeCogSummonsEarned(suitIndex, type)
            self.sendUpdate('cogSummonsResponse', returnCode)
        return

    def doSummonSingleCog(self, suitIndex):
        if suitIndex >= len(SuitDNA.suitHeadTypes):
            self.notify.warning('Bad suit index: %s' % suitIndex)
            return ['badIndex', suitIndex, 0]
        suitName = SuitDNA.suitHeadTypes[suitIndex]
        streetId = ZoneUtil.getBranchZone(self.zoneId)
        if streetId not in self.air.suitPlanners:
            return ['badlocation', suitIndex, 0]
        sp = self.air.suitPlanners[streetId]
        map = sp.getZoneIdToPointMap()
        zones = [self.zoneId, self.zoneId - 1, self.zoneId + 1]
        for zoneId in zones:
            if zoneId in map:
                points = map[zoneId][:]
                suit = sp.createNewSuit([], points, suitName=suitName)
                if suit:
                    return ['success', suitIndex, 0]

        return ['badlocation', suitIndex, 0]

    def doBuildingTakeover(self, suitIndex):
        streetId = ZoneUtil.getBranchZone(self.zoneId)
        if streetId not in self.air.suitPlanners:
            self.notify.warning('Street %d is not known.' % streetId)
            return ['badlocation', suitIndex, 0]
        sp = self.air.suitPlanners[streetId]
        bm = sp.buildingMgr
        building = self.findClosestDoor()
        if building == None:
            return ['badlocation', suitIndex, 0]
        level = None
        if suitIndex >= len(SuitDNA.suitHeadTypes):
            self.notify.warning('Bad suit index: %s' % suitIndex)
            return ['badIndex', suitIndex, 0]
        suitName = SuitDNA.suitHeadTypes[suitIndex]
        track = SuitDNA.getSuitDept(suitName)
        type = SuitDNA.getSuitType(suitName)
        level, type, track = sp.pickLevelTypeAndTrack(None, type, track)
        building.suitTakeOver(track, level, None)
        self.notify.warning('cogTakeOver %s %s %d %d' % (track,
                                                         level,
                                                         building.block,
                                                         self.zoneId))
        return ['success', suitIndex, building.doId]

    def doCogInvasion(self, suitIndex):
        invMgr = self.air.suitInvasionManager
        if invMgr.getInvading():
            returnCode = 'busy'
        else:
            if suitIndex >= len(SuitDNA.suitHeadTypes):
                self.notify.warning('Bad suit index: %s' % suitIndex)
                return ['badIndex', suitIndex, 0]
            cogType = SuitDNA.suitHeadTypes[suitIndex]
            numCogs = 1000
            if invMgr.startInvasion(cogType, numCogs, False):
                returnCode = 'success'
            else:
                returnCode = 'fail'
        return [returnCode, suitIndex, 0]

    def findClosestDoor(self):
        zoneId = self.zoneId
        streetId = ZoneUtil.getBranchZone(zoneId)
        sp = self.air.suitPlanners[streetId]
        if not sp:
            return None
        bm = sp.buildingMgr
        if not bm:
            return None
        zones = [zoneId,
                 zoneId - 1,
                 zoneId + 1,
                 zoneId - 2,
                 zoneId + 2]
        for zone in zones:
            for i in bm.getToonBlocks():
                building = bm.getBuilding(i)
                extZoneId, intZoneId = building.getExteriorAndInteriorZoneId()
                if not NPCToons.isZoneProtected(intZoneId):
                    if hasattr(building, 'door'):
                        if building.door.zoneId == zone:
                            return building

        return None

    def b_setTrackBonusLevel(self, trackBonusLevelArray):
        self.setTrackBonusLevel(trackBonusLevelArray)
        self.d_setTrackBonusLevel(trackBonusLevelArray)

    def d_setTrackBonusLevel(self, trackBonusLevelArray):
        self.sendUpdate('setTrackBonusLevel', [trackBonusLevelArray])

    def setTrackBonusLevel(self, trackBonusLevelArray):
        self.trackBonusLevel = trackBonusLevelArray

    def getTrackBonusLevel(self, track=None):
        if track == None:
            return self.trackBonusLevel
        else:
            return self.trackBonusLevel[track]
        return

    def checkGagBonus(self, track, level):
        trackBonus = self.getTrackBonusLevel(track)
        return trackBonus >= level

    def reqUseSpecial(self, special):
        response = self.tryToUseSpecial(special)
        self.sendUpdate('useSpecialResponse', [response])

    def tryToUseSpecial(self, special):
        estateOwnerDoId = simbase.air.estateMgr.zone2owner.get(self.zoneId)
        response = 'badlocation'
        doIHaveThisSpecial = False
        for curSpecial in self.gardenSpecials:
            if curSpecial[0] == special and curSpecial[1] > 0:
                doIHaveThisSpecial = True
                break

        if not doIHaveThisSpecial:
            return response
        if not self.doId == estateOwnerDoId:
            self.notify.warning("how did this happen, planting an item you don't own")
            return response
        if estateOwnerDoId:
            estate = simbase.air.estateMgr.estate.get(estateOwnerDoId)
            if estate and hasattr(estate, 'avIdList'):
                ownerIndex = estate.avIdList.index(estateOwnerDoId)
                if ownerIndex >= 0:
                    estate.doEpochNow(onlyForThisToonIndex=ownerIndex)
                    self.removeGardenItem(special, 1)
                    response = 'success'
                    self.air.writeServerEvent('garden_fertilizer', self.doId, '')
        return response

    def setGardenStarted(self, bStarted):
        self.gardenStarted = bStarted

    def d_setGardenStarted(self, bStarted):
        self.sendUpdate('setGardenStarted', [bStarted])

    def b_setGardenStarted(self, bStarted):
        self.setGardenStarted(bStarted)
        self.d_setGardenStarted(bStarted)

    def getGardenStarted(self):
        return self.gardenStarted

    def logSuspiciousEvent(self, eventName):
        senderId = self.air.getAvatarIdFromSender()
        eventStr = 'senderId=%s ' % senderId
        eventStr += eventName
        strSearch = re.compile('AvatarHackWarning! nodename')
        if strSearch.search(eventName, 0, 100):
            self.air.district.recordSuspiciousEventData(len(eventStr))
        self.air.writeServerEvent('suspicious', self.doId, eventStr)
        if simbase.config.GetBool('want-ban-setSCSinging', True):
            if 'invalid msgIndex in setSCSinging:' in eventName:
                if senderId == self.doId:
                    commentStr = 'Toon %s trying to call setSCSinging' % self.doId
                    simbase.air.banManager.ban(self.doId, self.DISLid, commentStr)
                else:
                    self.notify.warning(
                        'logSuspiciousEvent event=%s senderId=%s != self.doId=%s' % (eventName, senderId, self.doId))
        if simbase.config.GetBool('want-ban-setAnimState', True):
            if eventName.startswith('setAnimState: '):
                if senderId == self.doId:
                    commentStr = 'Toon %s trying to call setAnimState' % self.doId
                    simbase.air.banManager.ban(self.doId, self.DISLid, commentStr)
                else:
                    self.notify.warning(
                        'logSuspiciousEvent event=%s senderId=%s != self.doId=%s' % (eventName, senderId, self.doId))

    def getGolfTrophies(self):
        return self.golfTrophies

    def getGolfCups(self):
        return self.golfCups

    def b_setGolfHoleBest(self, holeBest):
        self.setGolfHoleBest(holeBest)
        self.d_setGolfHoleBest(holeBest)

    def d_setGolfHoleBest(self, holeBest):
        packed = GolfGlobals.packGolfHoleBest(holeBest)
        self.sendUpdate('setPackedGolfHoleBest', [packed])

    def setGolfHoleBest(self, holeBest):
        self.golfHoleBest = holeBest

    def getGolfHoleBest(self):
        return self.golfHoleBest

    def getPackedGolfHoleBest(self):
        packed = GolfGlobals.packGolfHoleBest(self.golfHoleBest)
        return packed

    def setPackedGolfHoleBest(self, packedHoleBest):
        unpacked = GolfGlobals.unpackGolfHoleBest(packedHoleBest)
        self.setGolfHoleBest(unpacked)

    def b_setGolfCourseBest(self, courseBest):
        self.setGolfCourseBest(courseBest)
        self.d_setGolfCourseBest(courseBest)

    def d_setGolfCourseBest(self, courseBest):
        self.sendUpdate('setGolfCourseBest', [courseBest])

    def setGolfCourseBest(self, courseBest):
        self.golfCourseBest = courseBest

    def getGolfCourseBest(self):
        return self.golfCourseBest

    def setUnlimitedSwing(self, unlimitedSwing):
        self.unlimitedSwing = unlimitedSwing

    def getUnlimitedSwing(self):
        return self.unlimitedSwing

    def b_setUnlimitedSwing(self, unlimitedSwing):
        self.setUnlimitedSwing(unlimitedSwing)
        self.d_setUnlimitedSwing(unlimitedSwing)

    def d_setUnlimitedSwing(self, unlimitedSwing):
        self.sendUpdate('setUnlimitedSwing', [unlimitedSwing])

    def b_setPinkSlips(self, pinkSlips):
        self.d_setPinkSlips(pinkSlips)
        self.setPinkSlips(pinkSlips)

    def d_setPinkSlips(self, pinkSlips):
        self.sendUpdate('setPinkSlips', [pinkSlips])

    def setPinkSlips(self, pinkSlips):
        self.pinkSlips = pinkSlips

    def getPinkSlips(self):
        return self.pinkSlips

    def addPinkSlips(self, amountToAdd):
        pinkSlips = min(self.pinkSlips + amountToAdd, 255)
        self.b_setPinkSlips(pinkSlips)

    def removePinkSlips(self, amount):
        if hasattr(self, 'autoRestockPinkSlips') and self.autoRestockPinkSlips:
            amount = 0
        pinkSlips = max(self.pinkSlips - amount, 0)
        self.b_setPinkSlips(pinkSlips)

    def setPreviousAccess(self, access):
        self.previousAccess = access

    def b_setAccess(self, access):
        self.setAccess(access)
        self.d_setAccess(access)

    def d_setAccess(self, access):
        self.sendUpdate('setAccess', [access])

    def setAccess(self, access):
        paidStatus = simbase.config.GetString('force-paid-status', 'none')
        if paidStatus == 'unpaid':
            access = 1
        print('Setting Access %s' % access)
        if access == OTPGlobals.AccessInvalid:
            if not __dev__:
                self.air.writeServerEvent('Setting Access', self.doId,
                                          'setAccess not being sent by the OTP Server, changing access to unpaid')
                access = OTPGlobals.AccessVelvetRope
            elif __dev__:
                access = OTPGlobals.AccessFull
        self.setGameAccess(access)

    def setGameAccess(self, access):
        self.gameAccess = access

    def getGameAccess(self):
        return self.gameAccess

    def b_setNametagStyle(self, nametagStyle):
        self.d_setNametagStyle(nametagStyle)
        self.setNametagStyle(nametagStyle)

    def d_setNametagStyle(self, nametagStyle):
        self.sendUpdate('setNametagStyle', [nametagStyle])

    def setNametagStyle(self, nametagStyle):
        self.nametagStyle = nametagStyle

    def getNametagStyle(self):
        return self.nametagStyle

    def logMessage(self, message):
        avId = self.air.getAvatarIdFromSender()
        if __dev__:
            print('CLIENT LOG MESSAGE %s %s' % (avId, message))
        try:
            self.air.writeServerEvent('clientLog', avId, message)
        except:
            self.air.writeServerEvent('suspicious', avId, 'client sent us a clientLog that caused an exception')

    def b_setMail(self, mail):
        self.d_setMail(mail)
        self.setMail(mail)

    def d_setMail(self, mail):
        self.sendUpdate('setMail', [mail])

    def setMail(self, mail):
        self.mail = mail

    def setNumMailItems(self, numMailItems):
        self.numMailItems = numMailItems

    def setSimpleMailNotify(self, simpleMailNotify):
        self.simpleMailNotify = simpleMailNotify

    def setInviteMailNotify(self, inviteMailNotify):
        self.inviteMailNotify = inviteMailNotify

    def findClosestSuitDoor(self):
        zoneId = self.zoneId
        streetId = ZoneUtil.getBranchZone(zoneId)
        sp = self.air.suitPlanners[streetId]
        if not sp:
            return None
        bm = sp.buildingMgr
        if not bm:
            return None
        zones = [zoneId,
                 zoneId - 1,
                 zoneId + 1,
                 zoneId - 2,
                 zoneId + 2]
        for zone in zones:
            for i in bm.getSuitBlocks():
                building = bm.getBuilding(i)
                extZoneId, intZoneId = building.getExteriorAndInteriorZoneId()
                if not isZoneProtected(intZoneId):
                    if hasattr(building, 'elevator'):
                        if building.elevator.zoneId == zone:
                            return building

        return None

    def doBuildingFree(self):
        streetId = ZoneUtil.getBranchZone(self.zoneId)
        if streetId not in self.air.suitPlanners:
            self.notify.warning('Street %d is not known.' % streetId)
            return ['badlocation', 0]
        building = self.findClosestSuitDoor()
        if building is None:
            return ['badlocation', 0]
        if hasattr(building, 'elevator'):
            if building.elevator.getState() == "waitEmpty":
                building.buildingDefeated = 1
                building.toonTakeOver()
                return ['success', 0]
            else:
                return ['busy', 0]
        return ['fail', 0]

    def setInvites(self, invites):
        self.invites = []
        for i in range(len(invites)):
            oneInvite = invites[i]
            newInvite = InviteInfoBase(*oneInvite)
            self.invites.append(newInvite)

    def updateInviteMailNotify(self):
        invitesInMailbox = self.getInvitesToShowInMailbox()
        newInvites = 0
        readButNotRepliedInvites = 0
        for invite in invitesInMailbox:
            if invite.status == PartyGlobals.InviteStatus.NotRead:
                newInvites += 1
            elif invite.status == PartyGlobals.InviteStatus.ReadButNotReplied:
                readButNotRepliedInvites += 1
            if __dev__:
                partyInfo = self.getOnePartyInvitedTo(invite.partyId)
                if not partyInfo:
                    self.notify.error('party info not found in partiesInvtedTo, partyId = %s' % str(invite.partyId))

        if newInvites:
            self.setInviteMailNotify(ToontownGlobals.NewItems)
        elif readButNotRepliedInvites:
            self.setInviteMailNotify(ToontownGlobals.OldItems)
        else:
            self.setInviteMailNotify(ToontownGlobals.NoItems)

    def getNumNonResponseInvites(self):
        count = 0
        for i in range(len(self.invites)):
            if self.invites[i].status == InviteStatus.NotRead or self.invites[
                i].status == InviteStatus.ReadButNotReplied:
                count += 1

        return count

    def getInvitesToShowInMailbox(self):
        result = []
        for invite in self.invites:
            appendInvite = True
            if invite.status == InviteStatus.Accepted or invite.status == InviteStatus.Rejected:
                appendInvite = False
            if appendInvite:
                partyInfo = self.getOnePartyInvitedTo(invite.partyId)
                if not partyInfo:
                    appendInvite = False
                if appendInvite:
                    if partyInfo.status == PartyGlobals.PartyStatus.Cancelled:
                        appendInvite = False
                if appendInvite:
                    endDate = partyInfo.endTime.date()
                    curDate = simbase.air.toontownTimeManager.getCurServerDateTime().date()
                    if endDate < curDate:
                        appendInvite = False
            if appendInvite:
                result.append(invite)

        return result

    def getNumInvitesToShowInMailbox(self):
        result = len(self.getInvitesToShowInMailbox())
        return result

    def setHostedParties(self, hostedParties):
        self.hostedParties = []
        for i in range(len(hostedParties)):
            hostedInfo = hostedParties[i]
            newParty = PartyInfoAI(*hostedInfo)
            self.hostedParties.append(newParty)

    def setPartiesInvitedTo(self, partiesInvitedTo):
        self.partiesInvitedTo = []
        for i in range(len(partiesInvitedTo)):
            partyInfo = partiesInvitedTo[i]
            newParty = PartyInfoAI(*partyInfo)
            self.partiesInvitedTo.append(newParty)

        self.updateInviteMailNotify()
        self.checkMailboxFullIndicator()

    def getOnePartyInvitedTo(self, partyId):
        result = None
        for i in range(len(self.partiesInvitedTo)):
            partyInfo = self.partiesInvitedTo[i]
            if partyInfo.partyId == partyId:
                result = partyInfo
                break

        return result

    def setPartyReplyInfoBases(self, replies):
        self.partyReplyInfoBases = []
        for i in range(len(replies)):
            partyReply = replies[i]
            repliesForOneParty = PartyReplyInfoBase(*partyReply)
            self.partyReplyInfoBases.append(repliesForOneParty)

    def updateInvite(self, inviteKey, newStatus):
        for invite in self.invites:
            if invite.inviteKey == inviteKey:
                invite.status = newStatus
                self.updateInviteMailNotify()
                self.checkMailboxFullIndicator()
                break

    def updateReply(self, partyId, inviteeId, newStatus):
        for partyReply in self.partyReplyInfoBases:
            if partyReply.partyId == partyId:
                for reply in partyReply.replies:
                    if reply.inviteeId == inviteeId:
                        reply.inviteeId = newStatus
                        break

    def canPlanParty(self):
        nonCancelledPartiesInTheFuture = 0
        for partyInfo in self.hostedParties:
            if partyInfo.status not in (PartyGlobals.PartyStatus.Cancelled, PartyGlobals.PartyStatus.Finished,
                                        PartyGlobals.PartyStatus.NeverStarted):
                nonCancelledPartiesInTheFuture += 1
                if nonCancelledPartiesInTheFuture >= PartyGlobals.MaxHostedPartiesPerToon:
                    break

        result = nonCancelledPartiesInTheFuture < PartyGlobals.MaxHostedPartiesPerToon
        return result

    def setPartyCanStart(self, partyId):
        self.notify.debug('setPartyCanStart called passing in partyId=%s' % partyId)
        found = False
        for partyInfo in self.hostedParties:
            if partyInfo.partyId == partyId:
                partyInfo.status = PartyGlobals.PartyStatus.CanStart
                found = True
                break

        if not found:
            self.notify.warning("setPartyCanStart can't find partyId %s" % partyId)

    def setPartyStatus(self, partyId, newStatus):
        self.notify.debug('setPartyStatus  called passing in partyId=%s newStauts=%d' % (partyId, newStatus))
        found = False
        for partyInfo in self.hostedParties:
            if partyInfo.partyId == partyId:
                partyInfo.status = newStatus
                found = True
                break

        info = self.getOnePartyInvitedTo(partyId)
        if info:
            found = True
            info.status = newStatus
        if not found:
            self.notify.warning("setPartyCanStart can't find hosted or invitedTO partyId %s" % partyId)

    def b_setAwardMailboxContents(self, awardMailboxContents):
        self.setAwardMailboxContents(awardMailboxContents)
        self.d_setAwardMailboxContents(awardMailboxContents)

    def d_setAwardMailboxContents(self, awardMailboxContents):
        self.sendUpdate('setAwardMailboxContents', [awardMailboxContents.getBlob(store=CatalogItem.Customization)])

    def setAwardMailboxContents(self, awardMailboxContents):
        self.notify.debug('Setting awardMailboxContents to %s.' % awardMailboxContents)
        self.awardMailboxContents = CatalogItemList.CatalogItemList(awardMailboxContents,
                                                                    store=CatalogItem.Customization)
        self.notify.debug('awardMailboxContents is %s.' % self.awardMailboxContents)
        if len(awardMailboxContents) == 0:
            self.b_setAwardNotify(ToontownGlobals.NoItems)
        self.checkMailboxFullIndicator()

    def getAwardMailboxContents(self):
        return self.awardMailboxContents.getBlob(store=CatalogItem.Customization)

    def b_setAwardSchedule(self, onOrder, doUpdateLater=True):
        self.setAwardSchedule(onOrder, doUpdateLater)
        self.d_setAwardSchedule(onOrder)

    def d_setAwardSchedule(self, onOrder):
        self.sendUpdate('setAwardSchedule',
                        [onOrder.getBlob(store=CatalogItem.Customization | CatalogItem.DeliveryDate)])

    def setAwardSchedule(self, onAwardOrder, doUpdateLater=True):
        self.onAwardOrder = CatalogItemList.CatalogItemList(onAwardOrder,
                                                            store=CatalogItem.Customization | CatalogItem.DeliveryDate)
        if hasattr(self, 'name'):
            if doUpdateLater and self.air.doLiveUpdates and hasattr(self, 'air'):
                taskName = self.uniqueName('next-award-delivery')
                taskMgr.remove(taskName)
                now = int(time.time() / 60 + 0.5)
                nextItem = None
                nextTime = self.onAwardOrder.getNextDeliveryDate()
                nextItem = self.onAwardOrder.getNextDeliveryItem()
                if nextItem != None:
                    pass
                if nextTime != None:
                    duration = max(10.0, nextTime * 60 - time.time())
                    taskMgr.doMethodLater(duration, self.__deliverAwardPurchase, taskName)
        return

    def __deliverAwardPurchase(self, task):
        now = int(time.time() / 60 + 0.5)
        delivered, remaining = self.onAwardOrder.extractDeliveryItems(now)
        self.notify.info('Award Delivery for %s: %s.' % (self.doId, delivered))
        self.b_setAwardMailboxContents(self.awardMailboxContents + delivered)
        self.b_setAwardSchedule(remaining)
        if delivered:
            self.b_setAwardNotify(ToontownGlobals.NewItems)
        return Task.done

    def b_setAwardNotify(self, awardMailboxNotify):
        self.setAwardNotify(awardMailboxNotify)
        self.d_setAwardNotify(awardMailboxNotify)

    def d_setAwardNotify(self, awardMailboxNotify):
        self.sendUpdate('setAwardNotify', [awardMailboxNotify])

    def setAwardNotify(self, awardNotify):
        self.awardNotify = awardNotify

    def b_setGM(self, type):
        self.sendUpdate('setGM', [type])
        self.setGM(type)

    def setGM(self, type):
        wasGM = self._isGM
        formerType = self._gmType
        self._isGM = type != 0
        self._gmType = None
        if self._isGM:
            self._gmType = type - 1
            MaxGMType = len(TTLocalizer.GM_NAMES) - 1
            if self._gmType > MaxGMType:
                self.notify.warning('toon %s has invalid GM type: %s' % (self.doId, self._gmType))
                self._gmType = MaxGMType
        # self._updateGMName(formerType) - looks much better without this to be honest
        return

    def isGM(self):
        return self._isGM

    def d_setRun(self):
        self.sendUpdate('setRun', [])

    def _nameIsPrefixed(self, prefix):
        if len(self.name) > len(prefix):
            if self.name[:len(prefix)] == prefix:
                return True
        return False

    def _updateGMName(self, formerType=None):
        if formerType is None:
            formerType = self._gmType
        name = self.name
        if formerType is not None:
            gmPrefix = TTLocalizer.GM_NAMES[formerType] + ' '
            if self._nameIsPrefixed(gmPrefix):
                name = self.name[len(gmPrefix):]
        if self._isGM:
            gmPrefix = TTLocalizer.GM_NAMES[self._gmType] + ' '
            newName = gmPrefix + name
        else:
            newName = name
        if self.name != newName:
            self.b_setName(newName)
        return

    def setName(self, name):
        DistributedPlayerAI.DistributedPlayerAI.setName(self, name)
        if self.WantOldGMNameBan:
            if self.isGenerated():
                self._checkOldGMName()
        self._updateGMName()

    def _checkOldGMName(self):
        if '$' in set(self.name):
            if config.GetBool('want-ban-old-gm-name', 0):
                self.ban('invalid name: %s' % self.name)
            else:
                self.air.writeServerEvent('suspicious', self.doId, '$ found in toon name')

    def setModuleInfo(self, info):
        avId = self.air.getAvatarIdFromSender()
        key = 'outrageous'
        self.moduleWhitelist = self.modulelist.loadWhitelistFile()
        self.moduleBlacklist = self.modulelist.loadBlacklistFile()
        for obfuscatedModule in info:
            module = ''
            p = 0
            for ch in obfuscatedModule:
                ic = ord(ch) ^ ord(key[p])
                p += 1
                if p >= len(key):
                    p = 0
                module += chr(ic)

            if module not in self.moduleWhitelist:
                if module in self.moduleBlacklist:
                    self.air.writeServerEvent('suspicious', avId, 'Black List module %s loaded into process.' % module)
                    if simbase.config.GetBool('want-ban-blacklist-module', False):
                        commentStr = 'User has blacklist module: %s attached to their game process' % module
                        dislId = self.DISLid
                        simbase.air.banManager.ban(self.doId, dislId, commentStr)
                else:
                    self.air.writeServerEvent('suspicious', avId, 'Unknown module %s loaded into process.' % module)

    def teleportResponseToAI(self, toAvId, available, shardId, hoodId, zoneId, fromAvId):
        if not self.WantTpTrack:
            return
        senderId = self.air.getAvatarIdFromSender()
        if toAvId != self.doId:
            self.air.writeServerEvent('suspicious', self.doId, 'toAvId=%d is not equal to self.doId' % toAvId)
            return
        if available != 1:
            self.air.writeServerEvent('suspicious', self.doId, 'invalid availableValue=%d' % available)
            return
        if fromAvId == 0:
            return
        self.air.teleportRegistrar.registerValidTeleport(toAvId, available, shardId, hoodId, zoneId, fromAvId)
        dg = self.dclass.aiFormatUpdate('teleportResponse', fromAvId, fromAvId, self.doId, [toAvId,
                                                                                            available,
                                                                                            shardId,
                                                                                            hoodId,
                                                                                            zoneId])
        self.air.send(dg)

    @staticmethod
    def staticGetLogicalZoneChangeAllEvent():
        return 'DOLogicalChangeZone-all'

    def b_setUnlimitedGags(self, flag):
        self.setUnlimitedGags(flag)
        self.d_setUnlimitedGags(flag)

    def d_setUnlimitedGags(self, flag):
        self.sendUpdate('setUnlimitedGags', [flag])

    def setUnlimitedGags(self, flag):
        self.unlimitedGags = flag

    def getUnlimitedGags(self):
        return self.unlimitedGags

    def b_setInstaKill(self, flag):
        self.setInstaKill(flag)
        self.d_setInstaKill(flag)

    def d_setInstaKill(self, flag):
        self.sendUpdate('setInstaKill', [flag])

    def setInstaKill(self, flag):
        self.instaKill = flag

    def getInstaKill(self):
        return self.instaKill

    def setAlwaysHitSuits(self, alwaysHitSuits):
        self.alwaysHitSuits = alwaysHitSuits

    def getAlwaysHitSuits(self):
        return self.alwaysHitSuits

    def d_doTeleport(self, hood):
        self.sendUpdateToAvatarId(self.doId, 'doTeleport', [hood])

    # Can be called either from the AI directly or via an astron update from the client.
    # When we are given a string, we know that it is from the client so we need to make sure
    # they didn't send us garbage.
    #
    # When setting death reasons, always make sure to set it BEFORE the damage is taken.
    def setDeathReason(self, reason: Union[DeathReason, str]):

        if isinstance(reason, str):
            reasonEnum = DeathReason.from_astron(reason)
            # Was this update garbage?
            if reasonEnum is None:
                return

            # Valid reason from client
            reason = reasonEnum

        self.deathReason = reason

    def getDeathReason(self) -> DeathReason:
        return self.deathReason

    def getSkillProfile(self, key: str) -> PlayerSkillProfile | None:
        return self._skillProfiles.get(key, None)

    def getOrCreateSkillProfile(self, key: str) -> PlayerSkillProfile:

        # Attempt to return an existing profile.
        profile = self._skillProfiles.get(key, None)
        if profile is not None:
            return profile

        # Create a new default profile.
        profile = PlayerSkillProfile.create_fresh(self.getDoId(), key)
        self.addSkillProfile(profile)
        return profile

    def addSkillProfile(self, profile: PlayerSkillProfile):
        self._skillProfiles[profile.key] = profile

    def removeSkillProfile(self, key: str):
        if key in self._skillProfiles:
            del self._skillProfiles[key]

    def getSkillProfiles(self) -> list[PlayerSkillProfile]:
        return list(self._skillProfiles.values())

    def setSkillProfiles(self, profiles: list[tuple | list]):
        self._skillProfiles.clear()
        for profile in profiles:
            formatted = PlayerSkillProfile.from_astron(profile)
            self._skillProfiles[formatted.key] = formatted

    def d_setSkillProfiles(self, profiles: list[PlayerSkillProfile]):
        self.sendUpdate('setSkillProfiles', [[profile.to_astron() for profile in profiles]])

    def d_syncSkillProfiles(self):
        self.sendUpdate('setSkillProfiles', [[profile.to_astron() for profile in self.getSkillProfiles()]])

    def b_setSkillProfiles(self, profiles: list[PlayerSkillProfile]):
        self.setSkillProfiles([p.to_astron() for p in profiles])
        self.d_setSkillProfiles(profiles)

    # Magic word stuff
    def setMagicDNA(self, dnaString):
        self.b_setDNAString(dnaString)
        self.d_setSystemMessage(0, "Updated your DNA!")

    def setMagicBodyAccessories(self, backpack, backpackTex, shoes, shoesTex):
        self.b_setBackpack(backpack, backpackTex, 0)
        self.b_setShoes(shoes, shoesTex, 0)
        self.d_setSystemMessage(0, "Updated your Accessories!")
    
    def setMagicHeadAccessories(self, hat, hatTex, glasses, glassesTex):
        self.b_setHat(hat, hatTex, 0)
        self.b_setGlasses(glasses, glassesTex, 0)
        self.d_setSystemMessage(0, "Updated your Accessories!")

    def getNametagStyle(self):
        return self.nametagStyle

    def requestNametagStyle(self, nametagStyle):
        """Handle client request to change nametag style"""
        # Validate the nametag style value
        if not isinstance(nametagStyle, int) or nametagStyle < 0 or nametagStyle > 255:
            self.air.writeServerEvent('suspicious', self.doId,
                                      'Toon tried to set invalid nametagStyle %s' % str(nametagStyle))
            self.notify.warning('%s.requestNametagStyle(%s) -- invalid nametagStyle value' % (self, nametagStyle))
            return
        
        # Apply the nametag style change
        self.b_setNametagStyle(nametagStyle)
        self.notify.info('%s.requestNametagStyle(%s) -- nametag style changed' % (self, nametagStyle))

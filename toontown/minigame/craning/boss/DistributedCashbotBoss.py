from direct.directnotify import DirectNotifyGlobal
from direct.interval.IntervalGlobal import *
from panda3d.core import *
from panda3d.direct import *

from libotp import *
from toontown.minigame.craning import CraneGameGlobals
from toontown.toonbase import TTLocalizer
from toontown.toonbase import ToontownGlobals
from toontown.suit import SuitDNA
from toontown.minigame.utils.boss.DistributedBossCog import DistributedBossCog

TTL = TTLocalizer
from toontown.minigame.utils.boss import BossHealthBar


class DistributedCashbotBoss(DistributedBossCog):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotBoss')

    def __init__(self, cr):
        super().__init__(cr)
        self.ruleset = CraneGameGlobals.CraneGameRuleset()  # Setup a default ruleset as a fallback
        self.modifiers = []
        self.warningSfx = None
        # By "heldObject", we mean the safe he's currently wearing as
        # a helmet, if any.  It's called a heldObject because this is
        # the way the cranes refer to the same thing, and we use the
        # same interface to manage this.
        self.heldObject = None

        self.latency = 0.5  # default latency for updating object posHpr
        self.stunEndTime = 0
        self.myHits = []
        self.tempHp = self.ruleset.CFO_MAX_HP
        self.processingHp = False
        self.lastLocalHit = 0
        return

    def announceGenerate(self):
        super().announceGenerate()

        # at this point all our attribs have been filled in.
        self.setName(TTLocalizer.CashbotBossName)
        nameInfo = TTLocalizer.BossCogNameWithDept % {'name': self._name,
                                                      'dept': SuitDNA.getDeptFullname(self.style.dept)}
        self.setDisplayName(nameInfo)

        # Our goal in this battle is to drop stuff on the CFO's head.
        # For this, we need a target.
        target = CollisionSphere(2, 0, 0, 3)
        targetNode = CollisionNode('headTarget')
        targetNode.addSolid(target)
        # CFO head can be hit by both regular pies and TNT pies
        targetNode.setCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.TNTBitmask)
        self.headTarget = self.neck.attachNewNode(targetNode)
        # Set pieCode tag so pies know to hit the CFO
        self.headTarget.setTag('pieCode', str(ToontownGlobals.PieCodeBossCog))
        print('[CFO Client] headTarget created with pieCode=%s, tag=%s' % (ToontownGlobals.PieCodeBossCog, self.headTarget.getTag('pieCode')))
        # self.headTarget.show()

        # And he gets a big bubble around his torso, just to keep
        # things from falling through him.  It's a big sphere so
        # things will tend to roll off him instead of landing on him.
        shield = CollisionSphere(0, 0, 0.8, 7)
        shieldNode = CollisionNode('shield')
        shieldNode.addSolid(shield)
        # CFO body can be hit by both regular pies and TNT pies
        shieldNode.setCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.TNTBitmask)
        self.pelvis.attachNewNode(shieldNode)

        self.eyes = loader.loadModel('phase_10/models/cogHQ/CashBotBossEyes.bam')

        # Get the eyes ready for putting outside the helmet.
        self.eyes.setPosHprScale(4.5, 0, -2.5, 90, 90, 0, 0.4, 0.4, 0.4)
        self.eyes.reparentTo(self.neck)
        self.eyes.hide()

    def delete(self):
        super().delete()
        self.ruleset = None

    def getBossMaxDamage(self):
        return self.ruleset.CFO_MAX_HP

    def setModifiers(self, mods):
        modsToSet = []  # A list of CFORulesetModifierBase subclass instances
        for modStruct in mods:
            modsToSet.append(CraneGameGlobals.CFORulesetModifierBase.fromStruct(modStruct))

        self.modifiers = modsToSet
        self.modifiers.sort(key=lambda m: m.MODIFIER_TYPE)

    def setBossDamage(self, bossDamage, avId=0, objId=0, isGoon=False, isDOT=False):

        if avId != base.localAvatar.doId or isGoon or (objId not in self.myHits):
            if bossDamage > self.bossDamage:
                delta = bossDamage - self.bossDamage
                
                if not isDOT:
                    self.flashRed()

                # Animate the hit if the CFO should flinch
                if self.ruleset.CFO_FLINCHES_ON_HIT and not isDOT:
                    self.doAnimate('hit', now=1)

                self.showHpText(-delta, scale=5)
            elif bossDamage == self.bossDamage and not isDOT and not isGoon and avId != 0:
                # Handle 0-damage hits (like pies) - still trigger flinch if CFO should flinch
                # This allows pies to trigger flinch animation even though they do 0 damage
                # Only trigger if avId is non-zero (actual hit, not a damage reset)
                if self.ruleset.CFO_FLINCHES_ON_HIT:
                    self.flashRed()
                    self.doAnimate('hit', now=1)

        if objId in self.myHits:
            self.myHits.remove(objId)

        self.bossDamage = bossDamage
        self.updateHealthBar()
        self.bossHealthBar.update(self.ruleset.CFO_MAX_HP - bossDamage, self.ruleset.CFO_MAX_HP)
        self.processingHp = False
        self.tempHp = self.ruleset.CFO_MAX_HP - self.bossDamage

    def prepareBossForBattle(self):
        if self.bossHealthBar:
            self.bossHealthBar.cleanup()
            self.bossHealthBar = BossHealthBar.BossHealthBar(self.style.dept)

        self.cleanupIntervals()

        self.clearChat()
        self.reparentTo(render)

        self.setPosHpr(*ToontownGlobals.CashbotBossBattleThreePosHpr)

        self.happy = 1
        self.raised = 1
        self.forward = 1
        self.doAnimate()

        self.generateHealthBar()
        self.updateHealthBar()

        # Display Health Bar
        self.bossHealthBar.initialize(self.ruleset.CFO_MAX_HP - self.bossDamage, self.ruleset.CFO_MAX_HP)
        if self.ruleset.CFO_MAX_HP > 999_999 and self.ruleset.TIMER_MODE:
            self.bossHealthBar.hide()
        
        # Accept pie hit events
        self.accept('pieSplat', self.__pieSplat)
        self.accept('localPieSplat', self.__localPieSplat)

    def cleanupBossBattle(self):
        self.cleanupIntervals()
        self.stopAnimate()
        self.cleanupAttacks()
        self.setDizzy(0)
        self.removeHealthBar()
        
        # Ignore pie hit events
        self.ignore('pieSplat')
        self.ignore('localPieSplat')
    
    def cleanupAttacks(self):
        """Clean up any ongoing gear attacks"""
        # Remove all gear root nodes that might still be attached
        if hasattr(self, 'rotateNode') and self.rotateNode:
            for child in self.rotateNode.getChildren():
                # Check if this is a gear root node from an attack
                if 'gearRoot' in child.getName():
                    # Clean up any detach tasks for this gear root
                    taskMgr.remove('detach-%s' % child.getName())
                    # Clean up any child node detach tasks
                    for grandchild in child.getChildren():
                        taskMgr.remove('detach-%s-%s' % (child.getName(), grandchild.getName()))
                    # Remove the node itself
                    child.removeNode()

    def saySomething(self, chatString):
        intervalName = 'CFOTaunt'
        seq = Sequence(name=intervalName)
        seq.append(Func(self.setChatAbsolute, chatString, CFSpeech))
        seq.append(Wait(4.0))
        seq.append(Func(self.clearChat))
        oldSeq = self.activeIntervals.get(intervalName)
        if oldSeq:
            oldSeq.finish()
        seq.start()
        self.storeInterval(seq, intervalName)

    def setAttackCode(self, attackCode, avId=0, delayTime=0):
        # Clean up ongoing attacks when interrupted (stunned, flinching, or no attack)
        if attackCode in (ToontownGlobals.BossCogDizzy, ToontownGlobals.BossCogDizzyNow, ToontownGlobals.BossCogNoAttack):
            self.cleanupAttacks()
        
        super().setAttackCode(attackCode, avId)

        if attackCode == ToontownGlobals.BossCogAreaAttack:
            self.saySomething(TTLocalizer.CashbotBossAreaAttackTaunt)
            base.playSfx(self.warningSfx)

        if attackCode in (ToontownGlobals.BossCogDizzy, ToontownGlobals.BossCogDizzyNow):
            self.stunEndTime = globalClock.getFrameTime() + delayTime
        else:
            self.stunEndTime = 0

    def localToonDied(self):
        super().localToonDied()
        self.localToonIsSafe = 1

    def grabObject(self, obj):
        # Grab a safe and put it on as a helmet.  This method mirrors
        # a similar method on DistributedCashbotCrane.py; it goes
        # through the same API as a crane picking up a safe.

        # This is only called by DistributedCashbotObject.enterGrabbed().
        obj.wrtReparentTo(self.neck)
        obj.hideShadows()
        obj.stashCollisions()
        if obj.lerpInterval:
            obj.lerpInterval.finish()
        obj.lerpInterval = Parallel(obj.posInterval(ToontownGlobals.CashbotBossToMagnetTime, Point3(-1, 0, 0.2)),
                                    obj.quatInterval(ToontownGlobals.CashbotBossToMagnetTime, VBase3(0, -90, 90)),
                                    Sequence(Wait(ToontownGlobals.CashbotBossToMagnetTime), ShowInterval(self.eyes)),
                                    obj.toMagnetSoundInterval)
        obj.lerpInterval.start()
        self.heldObject = obj

    def dropObject(self, obj):
        # Drop a helmet on the ground.

        # This is only called by DistributedCashbotObject.exitGrabbed().
        assert self.heldObject == obj

        if obj.lerpInterval:
            obj.lerpInterval.finish()
            obj.lerpInterval = None

        obj = self.heldObject
        obj.wrtReparentTo(render)
        obj.setHpr(obj.getH(), 0, 0)
        self.eyes.hide()

        # Actually, we shouldn't reveal the shadows until it
        # reaches the ground again.  This will do for now.
        obj.showShadows()
        obj.unstashCollisions()

        self.heldObject = None

    def setRuleset(self, ruleset):
        self.ruleset = ruleset
        self.bossHealthBar.update(self.ruleset.CFO_MAX_HP - self.bossDamage, self.ruleset.CFO_MAX_HP)
    
    def setAnimationSpeed(self, speed):
        """Set the animation playback speed for all boss animations"""
        # Store the speed for future animations
        if not hasattr(self, 'animationSpeed'):
            self.animationSpeed = 1.0
        self.animationSpeed = speed
        
        # Apply speed to current animation if one is playing
        if hasattr(self, 'currentAnimIval') and self.currentAnimIval:
            # Modify the playback rate of the current animation interval
            self.currentAnimIval.setPlayRate(speed)
    
    def getAnim(self, anim):
        """Override to apply animation speed to all animations"""
        # Get the normal animation interval
        ival = super().getAnim(anim)
        
        # Apply current animation speed if we have one
        if hasattr(self, 'animationSpeed') and self.animationSpeed != 1.0:
            self._applySpeedToInterval(ival)
        
        return ival
    
    def getAngryActorInterval(self, animName, **kw):
        """Override to apply animation speed to angry animations"""
        # Apply current animation speed to the keyword arguments
        if hasattr(self, 'animationSpeed') and self.animationSpeed != 1.0:
            kw['playRate'] = kw.get('playRate', 1.0) * self.animationSpeed
        
        # Call the parent method with modified kwargs
        return super().getAngryActorInterval(animName, **kw)
    
    def _applySpeedToInterval(self, ival):
        """Recursively apply animation speed to all ActorIntervals in a complex interval"""
        from direct.interval.ActorInterval import ActorInterval
        from direct.interval.MetaInterval import Sequence, Parallel
        
        if isinstance(ival, ActorInterval):
            # Apply speed directly to ActorInterval
            ival.setPlayRate(self.animationSpeed)
        elif isinstance(ival, (Sequence, Parallel)):
            # Access child intervals using the ivals attribute
            if hasattr(ival, 'ivals') and ival.ivals:
                for child in ival.ivals:
                    self._applySpeedToInterval(child)
    
    def setFrozenState(self, frozen):
        """Set the frozen state - completely freeze or unfreeze animations"""
        if not hasattr(self, 'isFrozen'):
            self.isFrozen = False
        
        if frozen and not self.isFrozen:
            # Freeze the boss
            self.isFrozen = True
            
            # Pause the current animation at its current frame
            if hasattr(self, 'currentAnimIval') and self.currentAnimIval:
                # Get the current time and pause the animation there
                currentT = self.currentAnimIval.getT()
                self.currentAnimIval.pause()
                self.frozenAnimTime = currentT
            # Boss is now frozen
            
        elif not frozen and self.isFrozen:
            # Unfreeze the boss
            self.isFrozen = False
            
            # Resume or restart animations
            if hasattr(self, 'currentAnimIval') and self.currentAnimIval:
                # Try to resume from where we left off
                if hasattr(self, 'frozenAnimTime'):
                    self.currentAnimIval.setT(self.frozenAnimTime)
                    delattr(self, 'frozenAnimTime')
                self.currentAnimIval.resume()
            
            # Clear frozen state
    
    def doAnimate(self, anim=None, now=0, queueNeutral=1, raised=None, forward=None, happy=None):
        """Override to prevent animations when frozen"""
        # If frozen, don't start new animations unless it's an 'unfreeze' command
        if hasattr(self, 'isFrozen') and self.isFrozen:
            return
        
        # Normal animation behavior when not frozen
        return super().doAnimate(anim, now, queueNeutral, raised, forward, happy)
    
    def doDirectedAttack(self, avId, attackCode):
        """Gear throw attack with adjustable speed and distance"""
        from direct.showbase import PythonUtil
        from direct.task import Task
        from panda3d.core import BoundingSphere
        import random
        
        toon = base.cr.doId2do.get(avId)
        if toon:
            # Gear throw parameters - adjust these to control speed/distance
            USE_FIXED_DISTANCE = False  # If True, uses fixedDistance; if False, uses actual toon distance
            fixedDistance = 50  # Fixed distance (original base class behavior)
            referenceDistance = 50  # Reference distance for speed calculation
            referenceTravelTime = 1.0  # Time to travel referenceDistance (speed = referenceDistance / referenceTravelTime)
            gearDelay = 0.15  # Delay between each gear launch
            
            # Calculate throw distance
            if USE_FIXED_DISTANCE:
                throwDistance = fixedDistance
            else:
                throwDistance = toon.getDistance(self)
            
            # Calculate travel time to maintain same speed as reference distance
            travelTime = (throwDistance / referenceDistance) * referenceTravelTime
            
            gearRoot = self.rotateNode.attachNewNode('gearRoot-atk%d' % globalClock.getFrameTime())
            gearRoot.setZ(10)
            gearRoot.setTag('attackCode', str(attackCode))
            gearModel = self.getGearFrisbee()
            gearModel.setScale(0.2)
            gearRoot.headsUp(toon)
            toToonH = PythonUtil.fitDestAngle2Src(0, gearRoot.getH() + 180)
            gearRoot.lookAt(toon)
            neutral = 'Fb_neutral'
            if not self.twoFaced:
                neutral = 'Ff_neutral'
            gearTrack = Parallel()
            
            for i in range(4):
                nodeName = '%s-%s' % (str(i), globalClock.getFrameTime())
                node = gearRoot.attachNewNode(nodeName)
                node.hide()
                node.setPos(0, 5.85, 4.0)
                gear = gearModel.instanceTo(node)
                x = random.uniform(-5, 5)
                z = random.uniform(-3, 3)
                h = random.uniform(-720, 720)
                if i == 2:
                    x = 0
                    z = 0

                def detachNode(node):
                    if not node.isEmpty():
                        node.detachNode()
                    return Task.done

                def detachNodeLater(node=node, distance=throwDistance):
                    if node.isEmpty():
                        return
                    center = node.node().getBounds().getCenter()
                    node.node().setBounds(BoundingSphere(center, distance * 1.5))
                    node.node().setFinal(1)
                    self.doMethodLater(0.005, detachNode, 'detach-%s-%s' % (gearRoot.getName(), node.getName()),
                                       extraArgs=[node])

                gearTrack.append(Sequence(Wait(i * gearDelay), Func(node.show),
                                          Parallel(node.posInterval(travelTime, Point3(x, throwDistance, z), fluid=1),
                                                   node.hprInterval(travelTime, VBase3(h, 0, 0), fluid=1)),
                                          Func(detachNodeLater)))

            if not self.raised:
                neutral1Anim = self.getAnim('down2Up')
                self.raised = 1
            else:
                neutral1Anim = ActorInterval(self, neutral, startFrame=48)
            throwAnim = self.getAnim('throw')
            neutral2Anim = ActorInterval(self, neutral)
            extraAnim = Sequence()
            if attackCode == ToontownGlobals.BossCogSlowDirectedAttack:
                extraAnim = ActorInterval(self, neutral)

            def detachGearRoot(task, gearRoot=gearRoot):
                if not gearRoot.isEmpty():
                    gearRoot.detachNode()
                return task.done

            def detachGearRootLater(gearRoot=gearRoot):
                if gearRoot.isEmpty():
                    return
                self.doMethodLater(0.01, detachGearRoot, 'detach-%s' % gearRoot.getName())

            seq = Sequence(ParallelEndTogether(self.pelvis.hprInterval(1, VBase3(toToonH, 0, 0)), neutral1Anim),
                           extraAnim, Parallel(Sequence(Wait(0.19), gearTrack, Func(detachGearRootLater),
                                                        self.pelvis.hprInterval(0.2, VBase3(0, 0, 0))),
                                               Sequence(throwAnim, neutral2Anim)))
            self.doAnimate(seq, now=1, raised=1)
    
    def __pieSplat(self, toon, pieCode):
        """Handle pie splat event from other toons"""
        if pieCode == ToontownGlobals.PieCodeBossCog:
            # Pie hit the CFO's head - just send update to server
            # The flinch will be triggered by setBossDamage when server confirms
            pass
    
    def __localPieSplat(self, pieCode, entry):
        """Handle local pie splat event (when local toon throws pie)"""
        print('[CFO Client] __localPieSplat: pieCode=%s' % pieCode)
        if pieCode == ToontownGlobals.PieCodeBossCog:
            print('[CFO Client] Pie hit CFO head!')
            # Local toon's pie hit the CFO's head
            # Get the pie type to determine if it's TNT
            pieType = localAvatar.pieType if hasattr(localAvatar, 'pieType') else 0
            # Send update to AI to process stun and damage
            # The flinch will be triggered by setBossDamage when server confirms
            print('[CFO Client] Sending d_pieHitBoss to AI with pieType=%s' % pieType)
            self.d_pieHitBoss(pieType)
        else:
            print('[CFO Client] pieCode mismatch: got %s, expected %s' % (pieCode, ToontownGlobals.PieCodeBossCog))
    
    def d_pieHitBoss(self, pieType):
        """Send update to AI that a pie hit the CFO"""
        self.sendUpdate('pieHitBoss', [pieType])
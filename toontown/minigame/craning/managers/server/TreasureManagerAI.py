"""
TreasureManagerAI - Handles treasure creation, recycling, and deletion.
"""

import math
import random
from direct.task.TaskManagerGlobal import taskMgr
from otp.otpbase.PythonUtil import clamp
from panda3d.core import Vec3, Point3
from toontown.minigame.craning.objects.DistributedCashbotTreasureAI import DistributedCashbotTreasureAI


class TreasureManagerAI:
    """Manages treasure objects: creation, recycling, and deletion."""
    
    def __init__(self, game):
        self.game = game
        self.treasures = {}
        self.grabbingTreasures = {}
        self.recycledTreasures = []
    
    def grabAttempt(self, avId, treasureId):
        """
        A toon wants to grab a certain treasure. Validates the treasure is valid to grab
        """
        # First, try to see if we can find the treasure that was grabbed.
        treasure = self.treasures.get(treasureId)
        if treasure is None:
            return
        
        # Now get the toon that wants to grab it.
        toon = self.game.air.getDo(avId)
        if toon is None:
            return
        
        # Are they allowed to take this treasure?
        if not treasure.validAvatar(toon):
            treasure.d_setReject()
            return
        
        del self.treasures[treasureId]
        treasure.d_setGrab(avId)  # Todo a lot of logic is in this method call. This is such bad design and should prob be refactored.
        self.grabbingTreasures[treasureId] = treasure
        
        # Wait a few seconds for the animation to play, then
        # recycle the treasure.
        taskMgr.doMethodLater(
            5, 
            self._recycleTreasure, 
            treasure.uniqueName('recycleTreasure'), 
            extraArgs=[treasure]
        )
    
    def _recycleTreasure(self, treasure):
        """Internal method to recycle a treasure after it's been grabbed"""
        if treasure.doId in self.grabbingTreasures:
            del self.grabbingTreasures[treasure.doId]
            self.recycledTreasures.append(treasure)
    
    def deleteAllTreasures(self):
        """Delete all treasures (active, grabbing, and recycled)"""
        for treasure in self.treasures.values():
            treasure.requestDelete()
        
        self.treasures = {}
        for treasure in self.grabbingTreasures.values():
            taskMgr.remove(treasure.uniqueName('recycleTreasure'))
            treasure.requestDelete()
        
        self.grabbingTreasures = {}
        for treasure in self.recycledTreasures:
            treasure.requestDelete()
        
        self.recycledTreasures = []
    
    def makeTreasure(self, goon):
        """
        Places a treasure, as pooped out by the given goon.  We
        place the treasure at the goon's current position, or at
        least at the beginning of its current path.  Actually, we
        ignore Z, and always place the treasure at Z == 0,
        presumably the ground.
        """
        # Too many treasures on the field?
        if len(self.treasures) >= self.game.ruleset.MAX_TREASURE_AMOUNT:
            return
        
        # Drop chance?
        if self.game.ruleset.GOON_TREASURE_DROP_CHANCE < 1.0:
            if random.random() > self.game.ruleset.GOON_TREASURE_DROP_CHANCE:
                return
        
        # The BossCog acts like a treasure planner as far as the
        # treasure is concerned.
        pos = goon.getPos(self.game.boss)
        
        # The treasure pops out and lands somewhere nearby.  Let's
        # start by choosing a point on a ring around the boss, based
        # on our current angle to the boss.
        v = Vec3(pos[0], pos[1], 0.0)
        if not v.normalize():
            v = Vec3(1, 0, 0)
        v = v * 27
        
        # Then perterb that point by a distance in some random
        # direction.
        angle = random.uniform(0.0, 2.0 * math.pi)
        radius = 10
        dx = radius * math.cos(angle)
        dy = radius * math.sin(angle)
        
        fpos = self.game.scene.getRelativePoint(self.game.boss, Point3(v[0] + dx, v[1] + dy, 0))
        
        # Find an index based on the goon strength we should use
        treasureHealIndex = 1.0 * (goon.strength - self.game.ruleset.MIN_GOON_DAMAGE) / (
                    self.game.ruleset.MAX_GOON_DAMAGE - self.game.ruleset.MIN_GOON_DAMAGE)
        treasureHealIndex *= len(self.game.ruleset.GOON_HEALS)
        treasureHealIndex = int(clamp(treasureHealIndex, 0, len(self.game.ruleset.GOON_HEALS) - 1))
        healAmount = self.game.ruleset.GOON_HEALS[treasureHealIndex]
        availStyles = self.game.ruleset.TREASURE_STYLES[treasureHealIndex]
        style = random.choice(availStyles)
        
        if self.recycledTreasures:
            # Reuse a previous treasure object
            treasure = self.recycledTreasures.pop(0)
            treasure.d_setGrab(0)
            treasure.b_setGoonId(goon.doId)
            treasure.b_setStyle(style)
            treasure.b_setPosition(pos[0], pos[1], 0)
            treasure.b_setFinalPosition(fpos[0], fpos[1], 0)
        else:
            # Create a new treasure object
            treasure = DistributedCashbotTreasureAI(
                self.game.air, 
                self.game, 
                goon, 
                style, 
                fpos[0], 
                fpos[1], 
                0
            )
            treasure.generateWithRequired(self.game.zoneId)
        treasure.healAmount = healAmount
        self.treasures[treasure.doId] = treasure

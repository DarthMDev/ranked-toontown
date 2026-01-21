from toontown.minigame.craning.objects import DistributedCashbotCraneAI
from direct.fsm import FSM

class DistributedCashbotHeavyCraneAI(DistributedCashbotCraneAI.DistributedCashbotCraneAI, FSM.FSM):

    def __init__(self, air, boss, index):
        DistributedCashbotCraneAI.DistributedCashbotCraneAI.__init__(self, air, boss, index)
        FSM.FSM.__init__(self, 'DistributedCashbotHeavyCraneAI')

    def getName(self):
        return 'HeavyCrane-%s' % self.index

    def getDamageMultiplier(self):
        return self.boss.ruleset.HEAVY_CRANE_DAMAGE_MULTIPLIER

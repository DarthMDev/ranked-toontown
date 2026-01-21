from toontown.minigame.craning.objects import DistributedCashbotCraneAI
from direct.fsm import FSM

class DistributedCashbotSideCraneAI(DistributedCashbotCraneAI.DistributedCashbotCraneAI, FSM.FSM):

    def __init__(self, air, boss, index):
        DistributedCashbotCraneAI.DistributedCashbotCraneAI.__init__(self, air, boss, index)
        FSM.FSM.__init__(self, 'DistributedCashbotSideCraneAI')

    def getName(self):
        return 'SideCrane-%s' % self.index

    def getPointsForStun(self):
        return self.boss.ruleset.POINTS_SIDESTUN

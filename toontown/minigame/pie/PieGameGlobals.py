# A file to put all pie game settings in one place for easy adjustment
from panda3d.core import *
from toontown.coghq import DistributedHealBarrelAI
from toontown.coghq import DistributedGagBarrelAI

# Game Constants
PREPARE_DELAY = 5
PREPARE_LATENCY_FACTOR = 0.25  # Add a small buffer for latency and showing the "GO!" text

# Colors of the countdown number right before a pie round starts.
RED_COUNTDOWN_COLOR = (.65, .2, .2, 1)
ORANGE_COUNTDOWN_COLOR = (.65, .45, .2, 1)
YELLOW_COUNTDOWN_COLOR = (.65, .65, .2, 1)
GREEN_COUNTDOWN_COLOR = (.2, .65, .2, 1)

# Pie damage and toonup values
PieToonup = 1
PieToonupNerfed = 2
PieDamageMult = 5.0
PieDamageMultNerfed = 5.0
AttackMult = 1.0
AttackMultNerfed = 0.5
HitCountDamage = 35
HitCountDamageNerfed = 50

# Barrel definitions
BarrelDefs = {
    8000: {
        'type': DistributedHealBarrelAI.DistributedHealBarrelAI,
        'pos': Point3(15, 23, 0),
        'hpr': Vec3(-45, 0, 0),
        'rewardPerGrab': 50,
        'rewardPerGrabMax': 0
    },
    8001: {
        'type': DistributedGagBarrelAI.DistributedGagBarrelAI,
        'pos': Point3(15, -23, 0),
        'hpr': Vec3(-135, 0, 0),
        'gagLevel': 3,
        'gagLevelMax': 0,
        'gagTrack': 3,
        'rewardPerGrab': 10,
        'rewardPerGrabMax': 0
    },
    8002: {
        'type': DistributedGagBarrelAI.DistributedGagBarrelAI,
        'pos': Point3(21, 20, 0),
        'hpr': Vec3(-45, 0, 0),
        'gagLevel': 3,
        'gagLevelMax': 0,
        'gagTrack': 4,
        'rewardPerGrab': 10,
        'rewardPerGrabMax': 0
    },
    8003: {
        'type': DistributedGagBarrelAI.DistributedGagBarrelAI,
        'pos': Point3(21, -20, 0),
        'hpr': Vec3(-135, 0, 0),
        'gagLevel': 3,
        'gagLevelMax': 0,
        'gagTrack': 5,
        'rewardPerGrab': 10,
        'rewardPerGrabMax': 0
    }
}

def setBarrelAttr(barrel, entId):
    """Set barrel attributes from BarrelDefs"""
    for defAttr, defValue in BarrelDefs[entId].items():
        setattr(barrel, defAttr, defValue)

# Barrel positions
BarrelsStartPos = (0, -36, -8)
BarrelsFinalPos = (0, -36, 0)

# Text to display in popup text for misc point gains
LOW_LAFF = "UBER BONUS"  # Text to display alongside a low laff bonus
STUN = "STUN!"
PENALTY_GO_SAD = "DIED!"

# Ruleset
# Instance attached to pie game instances, so we can easily modify stuff dynamically
class PieGameRuleset:
    """Ruleset for the pie game. Can be extended with modifiers in the future."""
    
    def __init__(self):
        # Enable for debugging
        self.GENERAL_DEBUG = False
        
        self.TIMER_MODE = False  # When true, the game is timed and ends when time is up
        self.TIMER_MODE_TIME_LIMIT = 60 * 5  # How many seconds do we give if TIMER_MODE is active?
        
        # Pie settings
        self.PIE_DAMAGE_MULT = 5.0
        self.PIE_TOONUP = 1
        self.ATTACK_MULT = 1.0
        self.HIT_COUNT_DAMAGE = 35
        
        # Boss settings (if applicable)
        self.BOSS_MAX_HP = 1000  # Default boss HP
        self.BOSS_STUN_THRESHOLD = 24
        
        # TOON SETTINGS
        self.FORCE_MAX_LAFF = False  # Should we force a laff limit for this round?
        self.FORCE_MAX_LAFF_AMOUNT = 100
        self.HEAL_TOONS_ON_START = False  # Should we set all toons to full laff when starting?
        
        self.WANT_LOW_LAFF_BONUS = True  # Should we award toons with low laff bonus points?
        self.LOW_LAFF_BONUS = 0.1  # How much will the bonus be worth? i.e. .1 = 10% bonus
        self.LOW_LAFF_BONUS_THRESHOLD = 25  # How much laff or less for low laff bonus?
        self.LOW_LAFF_BONUS_INCLUDE_PENALTIES = True  # Should penalties also be increased?
        
        # POINTS SETTINGS
        self.POINTS_STUN = 25  # Points per stun
        self.POINTS_PENALTY_GO_SAD = -50  # Point deduction for dying
        
        # COMBO SETTINGS
        self.WANT_COMBO_BONUS = False
        self.COMBO_DURATION = 2.0  # How long should combos last?
    
    def validate(self):
        """Call to make sure certain attributes are within certain bounds"""
        pass
    
    def asStruct(self):
        """Sends an astron friendly array over, ONLY STUFF THE CLIENT NEEDS TO KNOW GOES HERE"""
        return [
            self.TIMER_MODE,
            self.TIMER_MODE_TIME_LIMIT,
            self.PIE_DAMAGE_MULT,
            self.BOSS_MAX_HP,
            self.WANT_LOW_LAFF_BONUS,
            self.LOW_LAFF_BONUS,
            self.LOW_LAFF_BONUS_THRESHOLD,
            self.LOW_LAFF_BONUS_INCLUDE_PENALTIES,
            self.POINTS_STUN,
            self.POINTS_PENALTY_GO_SAD,
            self.COMBO_DURATION
        ]
    
    @classmethod
    def fromStruct(cls, attrs):
        """Restore ruleset from a struct"""
        rulesetInstance = cls()
        
        if len(attrs) >= 11:
            rulesetInstance.TIMER_MODE = attrs[0]
            rulesetInstance.TIMER_MODE_TIME_LIMIT = attrs[1]
            rulesetInstance.PIE_DAMAGE_MULT = attrs[2]
            rulesetInstance.BOSS_MAX_HP = attrs[3]
            rulesetInstance.WANT_LOW_LAFF_BONUS = attrs[4]
            rulesetInstance.LOW_LAFF_BONUS = attrs[5]
            rulesetInstance.LOW_LAFF_BONUS_THRESHOLD = attrs[6]
            rulesetInstance.LOW_LAFF_BONUS_INCLUDE_PENALTIES = attrs[7]
            rulesetInstance.POINTS_STUN = attrs[8]
            rulesetInstance.POINTS_PENALTY_GO_SAD = attrs[9]
            rulesetInstance.COMBO_DURATION = attrs[10]
        
        return rulesetInstance
    
    def __str__(self):
        return repr(self.__dict__)


# Modifier Base Class
# Instance attached to pie game instances, so we can easily modify stuff dynamically
class PieGameModifierBase(object):
    """Base class for all pie game modifiers."""
    
    # This should be overridden by subclasses, used so that the client knows which class to use when instantiating modifiers
    MODIFIER_ENUM = -1
    
    # This should also be overridden, use to define what type of modifier this is
    UNDEFINED = -1
    SPECIAL = 0
    HELPFUL = 1
    HURTFUL = 2
    MODIFIER_TYPE = UNDEFINED
    
    # Maps the above modifier enums to the classes that extend this one
    MODIFIER_SUBCLASSES = {}
    
    # Some colors to use for titles and percentages etc
    DARK_RED = (230.0 / 255.0, 20 / 255.0, 20 / 255.0, 1)
    RED = (255.0 / 255.0, 85.0 / 255.0, 85.0 / 255.0, 1)
    
    DARK_GREEN = (0, 180 / 255.0, 0, 1)
    GREEN = (85.0 / 255.0, 255.0 / 255.0, 85.0 / 255.0, 1)
    
    DARK_PURPLE = (170.0 / 255.0, 0, 170.0 / 255.0, 1)
    PURPLE = (255.0 / 255.0, 85.0 / 255.0, 255.0 / 255.0, 1)
    
    DARK_CYAN = (0, 0, 170.0 / 255.0, 1)
    CYAN = (85.0 / 255.0, 255.0 / 255.0, 255.0 / 255.0, 1)
    
    # The color that should be used for the title of this modifier
    TITLE_COLOR = DARK_GREEN
    # The color of the alternate color in the description
    DESCRIPTION_COLOR = GREEN
    
    # Tier represents modifiers that have multiple tiers to them
    def __init__(self, tier=1):
        self.tier = tier
    
    # Copied from google bc cba
    @staticmethod
    def numToRoman(n):
        NUM = [1, 4, 5, 9, 10, 40, 50, 90, 100, 400, 500, 900, 1000]
        SYM = ["I", "IV", "V", "IX", "X", "XL", "L", "XC", "C", "CD", "D", "CM", "M"]
        i = 12
        
        romanString = ''
        
        while n:
            div = n // NUM[i]
            n %= NUM[i]
            
            while div:
                romanString += SYM[i]
                div -= 1
            i -= 1
        return romanString
    
    # lazy method to translate ints to percentages since i think percents are cleaner to display
    @staticmethod
    def additivePercent(n):
        return 1.0 + n / 100.0
    
    # lazy method to translate ints to percentages since i think percents are cleaner to display
    @staticmethod
    def subtractivePercent(n):
        return 1.0 - n / 100.0
    
    # The name of this modifier to display to the client
    def getName(self):
        raise NotImplementedError('Please override the getName method from the parent class!')
    
    # The description of this modifier to display to the client
    def getDescription(self):
        raise NotImplementedError('Please override the getDescription method from the parent class!')
    
    # Returns an integer to change the total 'heat' of the game based on this modifier
    # Heat is an arbitrary measurement of difficulty
    def getHeat(self):
        raise NotImplementedError("Please override the getHeat method from the parent class!")
    
    # This method is called to apply this modifier's effect to the game
    def apply(self, game):
        """
        Apply this modifier's effect to the game.
        Override this method to implement modifier-specific behavior.
        """
        pass
    
    # Used to send to the client in an astron friendly way
    def asStruct(self):
        return [
            self.MODIFIER_ENUM,
            self.tier
        ]
    
    # Used to construct modifier instances when received from astron using the asStruct method
    @classmethod
    def fromStruct(cls, attrs):
        # Extract the info from the list
        modifierEnum, tier = attrs
        # Check if the enum isn't garbage
        if modifierEnum not in cls.MODIFIER_SUBCLASSES:
            raise Exception('Invalid modifier %s given from astron' % modifierEnum)
        
        # Extract the registered constructor and instantiate a modifier instance
        cls_constructor = cls.MODIFIER_SUBCLASSES[modifierEnum]
        modifier = cls_constructor(tier)
        return modifier


# Modifiers
class ModifierFirstToXWins(PieGameModifierBase):
    """First to X Wins modifier for the pie game."""
    
    MODIFIER_ENUM = 0
    MODIFIER_TYPE = PieGameModifierBase.SPECIAL
    
    TITLE_COLOR = PieGameModifierBase.DARK_PURPLE
    DESCRIPTION_COLOR = PieGameModifierBase.PURPLE
    
    def getName(self):
        return f'First to {self.tier} Win{"s" if self.tier > 1 else ""}'
    
    def getDescription(self):
        return 'Match continues until a player wins %(color_start)s' + str(self.tier) + ' round%(color_end)s'
    
    def getHeat(self):
        return 0  # Neutral modifier, doesn't affect difficulty
    
    def apply(self, game):
        # This modifier doesn't modify the game state directly
        # Instead, it's read by RoundManagerAI to determine match format
        # The tier represents the number of wins needed
        pass


# Register all modifier subclasses
for subclass in PieGameModifierBase.__subclasses__():
    if hasattr(subclass, 'MODIFIER_ENUM') and subclass.MODIFIER_ENUM != -1:
        PieGameModifierBase.MODIFIER_SUBCLASSES[subclass.MODIFIER_ENUM] = subclass

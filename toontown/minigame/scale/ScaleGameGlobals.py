# A file to put all scale game settings in one place for easy adjustment
LOW_LAFF_BONUS_TEXT = "UBER BONUS"  # Text to display alongside a low laff bonus

# Text to display in popup text for misc point gains
STUN_TEXT = "STUN!"
PENALTY_GO_SAD_TEXT = "DIED!"

# Game Constants
PREPARE_DELAY = 5
PREPARE_LATENCY_FACTOR = 0.25  # Add a small buffer for latency and showing the "GO!" text

# Colors of the countdown number right before a scale round starts.
RED_COUNTDOWN_COLOR = (.65, .2, .2, 1)
ORANGE_COUNTDOWN_COLOR = (.65, .45, .2, 1)
YELLOW_COUNTDOWN_COLOR = (.65, .65, .2, 1)
GREEN_COUNTDOWN_COLOR = (.2, .65, .2, 1)

# Ruleset
# Instance attached to scale game instances, so we can easily modify stuff dynamically
class ScaleGameRuleset:
    """Ruleset for the scale game. Can be extended with modifiers in the future."""
    
    def __init__(self):
        # Enable for debugging
        self.GENERAL_DEBUG = False
        
        self.TIMER_MODE = False  # When true, the cj is timed and ends when time is up, when false, acts as a stopwatch
        self.TIMER_MODE_TIME_LIMIT = 60  # How many seconds do we give the CJ scale round if TIMER_MODE is active?
        
        self.CJ_MAX_HP = 2700  # How much HP should the CJ have?
        
        # Difficulty settings
        self.AMMO_COUNT = 22
        self.NUM_GAVELS = 8
        self.NUM_LAWYERS = 10
        self.HEAL_AMOUNT = 4
        self.JURORS_SEATED = 12
        
        # TOON SETTINGS
        self.FORCE_MAX_LAFF = True  # Should we force a laff limit for this scale round?
        self.FORCE_MAX_LAFF_AMOUNT = 100  # The laff that we are going to force all toons participating to have
        self.HEAL_TOONS_ON_START = True  # Should we set all toons to full laff when starting the round?
        
        self.WANT_LOW_LAFF_BONUS = True  # Should we award toons with low laff bonus points?
        self.LOW_LAFF_BONUS = 0.1  # How much will the bonus be worth? i.e. .1 = 10% bonus for ALL points
        self.LOW_LAFF_BONUS_THRESHOLD = 25  # How much laff or less should a toon have to be considered for a low laff bonus?
        self.LOW_LAFF_BONUS_INCLUDE_PENALTIES = True  # Should penalties also be increased when low on laff?
        
        # note: When REVIVE_TOONS_UPON_DEATH is True, the only fail condition is if we run out of time
        self.RESTART_SCALE_ROUND_ON_FAIL = False  # Should we restart the scale round if all toons die?
        self.REVIVE_TOONS_UPON_DEATH = True  # Should we revive a toon that dies after a certain amount of time? (essentially a stun)
        self.REVIVE_TOONS_TIME = 20  # Time in seconds to revive a toon after death
        self.REVIVE_TOONS_LAFF_PERCENTAGE = 0.50  # How much laff should we give back to the toon when revived?
        
        # POINTS SETTINGS
        self.POINTS_STUN = 25  # Points per stun
        self.POINTS_PENALTY_GO_SAD = -50  # Point deduction for dying (can happen multiple times if revive setting is on)
        
        # COMBO SETTINGS
        self.WANT_COMBO_BONUS = False
        self.COMBO_DURATION = 2.0  # How long should combos last?
    
    # Call to make sure certain attributes are within certain bounds, for example dont make required impacts > 100%
    def validate(self):
        pass
    
    # Sends an astron friendly array over, ONLY STUFF THE CLIENT NEEDS TO KNOW GOES HERE
    # ANY TIME YOU MAKE A NEW ATTRIBUTE IN THE INIT ABOVE, MAKE SURE TO ADD
    # THE ATTRIBUTE INTO THIS LIST BELOW, AND A PARAMETER FOR IT IN THE DC FILE IN THE ScaleGameRuleset STRUCT
    def asStruct(self):
        return [
            self.TIMER_MODE,
            self.TIMER_MODE_TIME_LIMIT,
            self.CJ_MAX_HP,
            self.WANT_LOW_LAFF_BONUS,
            self.LOW_LAFF_BONUS,
            self.LOW_LAFF_BONUS_THRESHOLD,
            self.LOW_LAFF_BONUS_INCLUDE_PENALTIES,
            self.REVIVE_TOONS_UPON_DEATH,
            self.REVIVE_TOONS_TIME,
            self.POINTS_STUN,
            self.POINTS_PENALTY_GO_SAD,
            self.COMBO_DURATION
        ]
    
    @classmethod
    def fromStruct(cls, attrs):
        rulesetInstance = cls()
        
        if len(attrs) >= 12:
            rulesetInstance.TIMER_MODE = attrs[0]
            rulesetInstance.TIMER_MODE_TIME_LIMIT = attrs[1]
            rulesetInstance.CJ_MAX_HP = attrs[2]
            rulesetInstance.WANT_LOW_LAFF_BONUS = attrs[3]
            rulesetInstance.LOW_LAFF_BONUS = attrs[4]
            rulesetInstance.LOW_LAFF_BONUS_THRESHOLD = attrs[5]
            rulesetInstance.LOW_LAFF_BONUS_INCLUDE_PENALTIES = attrs[6]
            rulesetInstance.REVIVE_TOONS_UPON_DEATH = attrs[7]
            rulesetInstance.REVIVE_TOONS_TIME = attrs[8]
            rulesetInstance.POINTS_STUN = attrs[9]
            rulesetInstance.POINTS_PENALTY_GO_SAD = attrs[10]
            rulesetInstance.COMBO_DURATION = attrs[11]
        
        return rulesetInstance
    
    def __str__(self):
        return repr(self.__dict__)


# Modifier Base Class
# Instance attached to scale game instances, so we can easily modify stuff dynamically
class ScaleGameModifierBase(object):
    """Base class for all scale game modifiers."""
    
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
class ModifierFirstToXWins(ScaleGameModifierBase):
    """First to X Wins modifier for the scale game."""
    
    MODIFIER_ENUM = 0
    MODIFIER_TYPE = ScaleGameModifierBase.SPECIAL
    
    TITLE_COLOR = ScaleGameModifierBase.DARK_PURPLE
    DESCRIPTION_COLOR = ScaleGameModifierBase.PURPLE
    
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
for subclass in ScaleGameModifierBase.__subclasses__():
    if hasattr(subclass, 'MODIFIER_ENUM') and subclass.MODIFIER_ENUM != -1:
        ScaleGameModifierBase.MODIFIER_SUBCLASSES[subclass.MODIFIER_ENUM] = subclass

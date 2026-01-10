from openskill.models import PlackettLuce, PlackettLuceRating

from toontown.matchmaking.zero_sum_elo_model import ZeroSumEloModel, ZeroSumEloRating

# The starting hidden MMR for a player to default to when they are new. Used for skill based matchmaking.
STARTING_MMR = 1000

# The starting SR for a player to default to if they are new. Purely used for rank display.
STARTING_RATING = STARTING_MMR - 400
# The starting uncertainty rating for a player to default to if they are new. Should be default rating / 3.
STARTING_UNCERTAINTY = STARTING_MMR / 3

# The base SR rate for winning and losing. Modified based on the context of the game using this as a base.
BASE_SR_CHANGE = 20

# Define the model you want to use here.
# You can view the different models available here: https://openskill.me/en/stable/manual.html#picking-models
# You can also customize the inner workings on skill estimation, but the defaults are probably fine.
MODEL_CLASS = PlackettLuce
MODEL = MODEL_CLASS()
RATING_CLASS = PlackettLuceRating  # Update this to be whatever rating classes MODEL will return

# A custom model to use specifically for 1v1 matches. 1v1s use a zero-sum ELO system for hidden MMR.
ZERO_SUM_MODEL = ZeroSumEloModel(k_factor=50, max_elo_discrepancy=500)
ZERO_SUM_RATING_CLASS = ZeroSumEloRating
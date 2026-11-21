"""Shared constants. Owned by S0. Change only via the integrator."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "csv"
OUT_DIR = ROOT / "outputs"

WH_ID = "WH-KOL"
ACCESSORY_GROUP = "Accessories (Safa/Mala/Stole)"
ACCESSORY_CATS = {"Safa", "Mala", "Stole"}

# lead_times.csv, mapped by zone / city (route column is a sentence)
LEAD_WH = {"East": 3, "North": 4, "South": 6}   # WH-KOL -> store (and store -> WH pull-back)
LEAD_S2S_SAME_CITY = 2
LEAD_S2S_SAME_ZONE = 4
LEAD_S2S_OTHER_ZONE = 7

# rules.csv
DONOR_MIN_COVER_DAYS = 30          # style-level cover the giving store must keep
APPROVAL_MRP_THRESHOLD = 100_000   # a move group worth more than this at MRP needs human approval
S_PLUS_PLUS = "S++"

# planning
VELOCITY_WINDOW_DAYS = 84          # = 12 weeks of stock_weekly
REVIEW_DAYS = 7
SAFETY_DAYS = 7
AGEING_DAYS_CORE = 180
AGEING_DAYS_FASHION = 90
LIFT_MIN, LIFT_MAX = 1.0, 3.5
SEASON_END = "2026-12-12"          # last wedding date in the calendar for 2026
CHAIN_DAILY_SANITY = (300, 450)    # expected chain forecast units/day for the next 30 days

MOVE_TYPES = ("WH_TO_STORE", "STORE_TO_STORE", "PULL_BACK")
PROBLEM_KINDS = ("CAPACITY", "OVERSTOCK", "UNDERSTOCK", "SCARCITY", "NEW_LAUNCH",
                 "MIN_DISPLAY", "AGEING", "SOLD_OUT_CONSOLIDATION")
FLAG_KINDS = ("DATA_QUALITY", "REORDER", "DEAD_STOCK", "NEW_STORE", "CAPACITY")

"""Static catalog for the synthetic data generator.

Real advertiser brands (top TV/streaming spenders) and, where a campaign is
widely recognizable, real-ish creative concepts. All delivery and performance
numbers produced from this catalog are synthetic.
"""

# (name, category) — the first 100 are used.
ADVERTISERS = [
    # Insurance
    ("GEICO", "Insurance"), ("Progressive", "Insurance"), ("State Farm", "Insurance"),
    ("Allstate", "Insurance"), ("Liberty Mutual", "Insurance"),
    # QSR / restaurants
    ("McDonald's", "QSR"), ("Taco Bell", "QSR"), ("Wendy's", "QSR"),
    ("Burger King", "QSR"), ("Domino's", "QSR"), ("Chipotle", "QSR"),
    ("Subway", "QSR"), ("KFC", "QSR"), ("Popeyes", "QSR"),
    # Auto
    ("Toyota", "Auto"), ("Honda", "Auto"), ("Ford", "Auto"), ("Chevrolet", "Auto"),
    ("Hyundai", "Auto"), ("Kia", "Auto"), ("Nissan", "Auto"), ("Volkswagen", "Auto"),
    ("BMW", "Auto"), ("Mercedes-Benz", "Auto"), ("Subaru", "Auto"), ("Jeep", "Auto"),
    # Tech
    ("Apple", "Tech"), ("Samsung", "Tech"), ("Google", "Tech"),
    ("Microsoft", "Tech"), ("Amazon", "Tech"),
    # Telecom
    ("Verizon", "Telecom"), ("T-Mobile", "Telecom"), ("AT&T", "Telecom"),
    ("Xfinity", "Telecom"),
    # Household & personal care CPG
    ("Tide", "CPG"), ("Dove", "CPG"), ("Old Spice", "CPG"), ("Gillette", "CPG"),
    ("Colgate", "CPG"), ("Crest", "CPG"), ("Clorox", "CPG"), ("Lysol", "CPG"),
    # Beverage
    ("Coca-Cola", "Beverage"), ("Pepsi", "Beverage"), ("Dr Pepper", "Beverage"),
    ("Mountain Dew", "Beverage"), ("Gatorade", "Beverage"), ("Red Bull", "Beverage"),
    ("Monster Energy", "Beverage"), ("Michelob Ultra", "Beverage"),
    # Retail
    ("Walmart", "Retail"), ("Target", "Retail"), ("Costco", "Retail"),
    ("Home Depot", "Retail"), ("Lowe's", "Retail"), ("IKEA", "Retail"),
    ("Wayfair", "Retail"), ("Etsy", "Retail"),
    # Finance
    ("Chase", "Finance"), ("Bank of America", "Finance"), ("Capital One", "Finance"),
    ("American Express", "Finance"), ("Discover", "Finance"), ("PayPal", "Finance"),
    ("Rocket Mortgage", "Finance"), ("SoFi", "Finance"), ("Fidelity", "Finance"),
    # Travel
    ("Expedia", "Travel"), ("Booking.com", "Travel"), ("Airbnb", "Travel"),
    ("Delta Air Lines", "Travel"), ("United Airlines", "Travel"),
    ("Southwest Airlines", "Travel"), ("Marriott", "Travel"), ("Hilton", "Travel"),
    ("Royal Caribbean", "Travel"),
    # Health / pharmacy
    ("Advil", "Health"), ("Tylenol", "Health"), ("Claritin", "Health"),
    ("CVS", "Health"), ("Walgreens", "Health"),
    # Entertainment & gaming
    ("PlayStation", "Gaming"), ("Xbox", "Gaming"), ("Nintendo", "Gaming"),
    ("EA Sports", "Gaming"), ("DraftKings", "Gaming"), ("FanDuel", "Gaming"),
    ("Spotify", "Entertainment"), ("Universal Pictures", "Entertainment"),
    ("Warner Bros.", "Entertainment"),
    # Apparel
    ("Nike", "Apparel"), ("Adidas", "Apparel"), ("Under Armour", "Apparel"),
    ("Lululemon", "Apparel"), ("Old Navy", "Apparel"),
    # Snacks & food CPG
    ("Doritos", "Food"), ("Lay's", "Food"), ("Oreo", "Food"), ("M&M's", "Food"),
    ("Cheerios", "Food"), ("Hershey's", "Food"),
    # Marketplace / DTC
    ("Uber", "Marketplace"), ("DoorDash", "Marketplace"), ("Instacart", "Marketplace"),
    ("Peloton", "Marketplace"), ("Squarespace", "Marketplace"), ("Duolingo", "Marketplace"),
][:100]

# Recognizable real campaign concepts, used as flagship creative names.
FAMOUS_CREATIVES = {
    "GEICO": ["Gecko: 15 Minutes Could Save You", "Caveman Comeback"],
    "Progressive": ["Flo: Bundle Bungalow", "Dr. Rick: Un-Become Your Parents"],
    "State Farm": ["Jake from State Farm: Khakis", "Like a Good Neighbor"],
    "Allstate": ["Mayhem: Streaming Edition", "Are You in Good Hands?"],
    "Liberty Mutual": ["LiMu Emu & Doug", "Only Pay for What You Need"],
    "McDonald's": ["I'm Lovin' It: Late Night Menu", "Famous Orders"],
    "Taco Bell": ["Live Más at Midnight", "The Crunchwrap Hour"],
    "Wendy's": ["Where's the Beef (Remix)", "Fresh Never Frozen"],
    "Burger King": ["Whopper Whopper Whopper", "Have It Your Way"],
    "Domino's": ["Emergency Pizza", "The Noid Returns"],
    "Chipotle": ["Cultivate a Better World", "Burrito Season"],
    "Subway": ["Eat Fresh Refresh", "Footlong Season"],
    "KFC": ["Finger Lickin' Binge", "The Colonel's Cut"],
    "Popeyes": ["Love That Chicken", "The Sandwich Wars"],
    "Toyota": ["Let's Go Places", "Tundra Trailhead"],
    "Honda": ["The Power of Dreams", "CR-V Weekend"],
    "Ford": ["Built Ford Tough", "F-150 Lightning Strikes"],
    "Chevrolet": ["Like a Rock", "Silverado Country"],
    "Hyundai": ["Smaht Pahk", "Question Everything"],
    "Kia": ["Movement That Inspires", "Hamster Encore"],
    "Nissan": ["Thrill Driver", "Ariya Awakening"],
    "Volkswagen": ["Drive Bigger", "The Bus Is Back (ID. Buzz)"],
    "BMW": ["The Ultimate Driving Machine", "Electric M Series"],
    "Mercedes-Benz": ["The Best or Nothing", "EQ Silent Luxury"],
    "Subaru": ["Love. It's What Makes a Subaru", "Dog Tested. Dog Approved."],
    "Jeep": ["Groundhog Day", "Earth Odyssey"],
    "Apple": ["Shot on iPhone: Night Mode", "Privacy. That's iPhone."],
    "Samsung": ["Do What You Can't", "Galaxy Unfolds"],
    "Google": ["Loretta: Remembered", "Pixel: Best Take"],
    "Microsoft": ["Copilot for Everyone", "Surface Yourself"],
    "Amazon": ["Alexa Loses Her Voice", "Delivering Smiles"],
    "Verizon": ["Can You Hear Me Now? Good.", "5G Built Right"],
    "T-Mobile": ["The Un-carrier Hour", "Magenta Max Night"],
    "AT&T": ["Lily at the Store", "Connecting Changes Everything"],
    "Xfinity": ["The Slowskys", "Stream All the Things"],
    "Tide": ["It's a Tide Ad", "Cold Callers (Wash Cold)"],
    "Dove": ["Real Beauty", "The Selfie Talk"],
    "Old Spice": ["The Man Your Man Could Smell Like", "Smell Ready"],
    "Gillette": ["The Best a Man Can Get", "Every Beard Counts"],
    "Coca-Cola": ["Share a Coke", "The Polar Bears' Movie Night"],
    "Pepsi": ["Is Pepsi OK?", "Halftime Legacy"],
    "Dr Pepper": ["Fansville: Season 8", "It's Not Cola"],
    "Mountain Dew": ["Puppy Monkey Baby", "Baja Blast Beach"],
    "Gatorade": ["Is It in You?", "Fuel Tomorrow"],
    "Red Bull": ["Gives You Wings", "Cliff Diving Series"],
    "Michelob Ultra": ["Superior Beach", "It's Only Worth It If You Enjoy It"],
    "Walmart": ["Save Money. Live Better.", "Famous Visitors (Cars Cameo)"],
    "Target": ["Tar-zhay All Day", "Run & Done"],
    "Home Depot": ["How Doers Get More Done", "Spring Black Friday"],
    "Capital One": ["What's in Your Wallet?", "The Bank Vault Heist"],
    "American Express": ["Don't Leave Home Without It", "Member Since"],
    "Discover": ["We Treat You Like You'd Treat You", "Cashback Match Twins"],
    "Rocket Mortgage": ["Certain Is Better", "Dream House with Anna"],
    "Expedia": ["Made to Travel", "All By Myself (Upgrade)"],
    "Airbnb": ["Belong Anywhere", "Made Possible by Hosts"],
    "Southwest Airlines": ["Wanna Get Away?", "Bags Fly Free"],
    "Marriott": ["Golden Rule", "Bonvoy Boundless"],
    "Nike": ["Just Do It: Next Chapter", "You Can't Stop Us"],
    "Adidas": ["Impossible Is Nothing", "All In or Nothing"],
    "Doritos": ["Crash the Super Bowl Revival", "Triangle Tracker"],
    "Lay's": ["Betcha Can't Eat Just One", "Golden Grounds"],
    "Oreo": ["Twist, Lick, Dunk", "Stay Playful"],
    "M&M's": ["The Spokescandies Return", "Almost Champions"],
    "Cheerios": ["Good Goes Round", "Heart Healthy Start"],
    "PlayStation": ["Play Has No Limits", "Greatness Awaits"],
    "Xbox": ["Power Your Dreams", "Us Dreamers"],
    "Nintendo": ["Switch and Play Together", "My Way to Play"],
    "EA Sports": ["It's in the Game", "Cover Athlete Reveal"],
    "DraftKings": ["Life's More Fun with Skin in the Game", "The Sweat"],
    "FanDuel": ["Kick of Destiny", "Make Every Moment More"],
    "Spotify": ["Wrapped IRL", "Listening Is Everything"],
    "Uber": ["Anywhere You Go", "One Less Thing to Think About"],
    "DoorDash": ["Your Door to More", "Self-Love Bouquet"],
    "Peloton": ["Motivation That Moves You", "Anyone. Anywhere."],
    "Squarespace": ["A Website Makes It Real", "The Singularity"],
    "Duolingo": ["The Owl Is Watching", "5 Minutes a Day"],
}

CAMPAIGN_NAME_TEMPLATES = [
    "Q3 Binge Boost", "Couch Commerce", "Prestige Pod Takeover", "Midnight Snackable",
    "Autoplay Adventures", "Cliffhanger Countdown", "Season Finale Surge",
    "Weekend Watchlist", "The Big Premiere Push", "Second Season Splash",
    "Pause-Worthy Moments", "Credits Roll Callout", "Golden Hour Streams",
    "Summer Slate Spotlight", "Fall Lineup Frenzy", "Binge Break Bites",
    "Opening Credits Club", "The Recap Rally", "Stream & Redeem",
    "Next Episode Nudge", "Marathon Fuel", "Plot Twist Promo",
]

CREATIVE_TYPES = [
    # (id, name, description, cpm multiplier)
    (1, "awareness", "Brand awareness — 15/30s spots, reach & completion optimized", 1.00),
    (2, "direct_response", "Direct response — conversion optimized, strong CTA", 1.25),
    (3, "click_to_learn_more", "Click-to-learn-more — interactive overlay, engagement optimized", 1.10),
]

# Session cohorts. Supply share sums to 1. attention: 0-1 index.
# demand: advertiser demand pressure index (1.0 = platform average).
# The whole "not all inventory is equal" story is encoded here.
COHORTS = [
    # (id, name, description, supply_share, attention, demand, ad_load_pods_per_hr, cpm_mult)
    (1, "Late-Night Low-Attention Binge", "Post-11pm autoplay chains; high volume, drifting attention", 0.13, 0.42, 0.75, 3.4, 0.82),
    (2, "Prestige Drama Devotee", "Appointment viewing of awards-bait dramas; locked in, ad-recall gold", 0.08, 0.95, 1.60, 2.6, 1.38),
    (3, "Weekend Marathoner", "Saturday 6-episode arcs; long sessions, steady attention", 0.11, 0.72, 1.15, 3.0, 1.05),
    (4, "Family Co-Viewing Couch", "Multi-viewer living-room sessions, early evening; 2.4 pairs of eyes per play", 0.10, 0.78, 1.45, 2.4, 1.30),
    (5, "Comfort-Show Rewatcher", "The Office for the ninth time; predictable, loyal, half-listening", 0.12, 0.55, 0.90, 3.2, 0.92),
    (6, "True-Crime Night Owl", "Docuseries after dark; unusually engaged, skews DR-responsive", 0.07, 0.88, 1.35, 2.8, 1.22),
    (7, "Second-Screen Scroller", "Phone in hand, show in background; impressions land, attention doesn't", 0.11, 0.35, 0.60, 3.5, 0.72),
    (8, "Reality Rubbernecker", "Reality competition devotees; social viewers, strong brand recall", 0.08, 0.68, 1.10, 3.0, 1.02),
    (9, "Global Cinema Explorer", "Subtitled international films; highest attention on the platform", 0.05, 0.97, 1.25, 2.4, 1.28),
    (10, "Anime Superfan", "Simulcast loyalists; young-skewing, gaming-adjacent, completionist", 0.06, 0.85, 1.30, 2.8, 1.18),
    (11, "Sports-Doc Weekend Warrior", "Drive-to-survive types; auto & apparel catnip", 0.05, 0.80, 1.40, 2.9, 1.25),
    (12, "Background Autoplay Ambient", "TV as wallpaper; huge daytime supply nobody bids on", 0.04, 0.22, 0.40, 3.6, 0.58),
]

# (category, cohort_id) -> affinity boost applied to both bidding weight and
# conversion propensity. Default 1.0.
CATEGORY_COHORT_AFFINITY = {
    ("QSR", 1): 1.8, ("QSR", 7): 1.3, ("Food", 1): 1.6, ("Beverage", 1): 1.4,
    ("Insurance", 2): 1.4, ("Finance", 2): 1.5, ("Auto", 2): 1.3, ("Travel", 2): 1.3,
    ("Travel", 3): 1.4, ("Marketplace", 3): 1.2,
    ("CPG", 4): 1.7, ("Food", 4): 1.5, ("Retail", 4): 1.5, ("Auto", 4): 1.2,
    ("Retail", 5): 1.2, ("Food", 5): 1.3,
    ("Finance", 6): 1.3, ("Insurance", 6): 1.4, ("Health", 6): 1.3,
    ("QSR", 10): 1.3, ("Gaming", 10): 2.0, ("Tech", 10): 1.4,
    ("Entertainment", 8): 1.4, ("Beverage", 8): 1.3, ("Apparel", 8): 1.2,
    ("Travel", 9): 1.5, ("Tech", 9): 1.3, ("Entertainment", 9): 1.3,
    ("Auto", 11): 1.8, ("Apparel", 11): 1.7, ("Gaming", 11): 1.5, ("Beverage", 11): 1.4,
    ("CPG", 12): 1.1, ("Health", 12): 1.2,
}

DAYPARTS = ["early_morning", "daytime", "prime", "late_night"]
DAYPART_CPM_MULT = {"early_morning": 0.70, "daytime": 0.90, "prime": 1.25, "late_night": 0.85}
DAYPART_DEMAND = {"early_morning": 0.55, "daytime": 0.80, "prime": 1.35, "late_night": 0.95}

# Cohort daypart mix (rows sum to 1) keyed by cohort_id.
COHORT_DAYPART_MIX = {
    1: [0.02, 0.08, 0.25, 0.65], 2: [0.02, 0.10, 0.70, 0.18], 3: [0.05, 0.40, 0.40, 0.15],
    4: [0.05, 0.20, 0.70, 0.05], 5: [0.08, 0.30, 0.42, 0.20], 6: [0.02, 0.08, 0.35, 0.55],
    7: [0.10, 0.35, 0.35, 0.20], 8: [0.03, 0.17, 0.65, 0.15], 9: [0.05, 0.20, 0.55, 0.20],
    10: [0.03, 0.17, 0.35, 0.45], 11: [0.10, 0.45, 0.35, 0.10], 12: [0.25, 0.55, 0.12, 0.08],
}

CATEGORY_ACTION = {
    "QSR": ("order", 14.0), "Food": ("purchase", 9.0), "Beverage": ("purchase", 7.0),
    "Insurance": ("quote_started", 160.0), "Finance": ("account_signup", 210.0),
    "Auto": ("dealer_visit", 480.0), "Tech": ("purchase", 260.0),
    "Telecom": ("plan_signup", 180.0), "CPG": ("purchase", 11.0),
    "Retail": ("purchase", 64.0), "Travel": ("booking", 420.0),
    "Health": ("purchase", 22.0), "Gaming": ("install_or_deposit", 55.0),
    "Entertainment": ("subscription", 30.0), "Apparel": ("purchase", 85.0),
    "Marketplace": ("first_order", 48.0),
}

# Baseline (unexposed) conversion propensity per category over the 90-day
# window, before cohort affinity. DR-heavy categories convert more measurably.
CATEGORY_BASE_CONV = {
    "QSR": 0.030, "Food": 0.022, "Beverage": 0.018, "Insurance": 0.010,
    "Finance": 0.009, "Auto": 0.004, "Tech": 0.012, "Telecom": 0.008,
    "CPG": 0.025, "Retail": 0.028, "Travel": 0.011, "Health": 0.016,
    "Gaming": 0.020, "Entertainment": 0.024, "Apparel": 0.015, "Marketplace": 0.026,
}

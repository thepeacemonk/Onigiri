/**
 * ONIGIRI GOOGLE APPS SCRIPT - SETUP
 *
 * Existing reward-code sheets are unchanged:
 *
 * Taiyaki Coins
 * - Header row: Code | Amount | Status
 *
 * Onigimon Coins
 * - Header row: Code | Amount | Status | Currency
 *
 * Onigimon Items
 * - Header row: Code | Item Key | Amount | Status
 *
 * Hex Coins
 * - Header row: Code | Amount | Status
 *
 * Ingredient Rush adds three managed sheets:
 *
 * Recipe Rush Restaurants
 * - Header row: Restaurant ID | Restaurant Name | Type | Price | Status | Last Synced
 *   Registry/log of every restaurant, evolution and shop the add-on has ever
 *   reported. Not read by the recipe-selection logic.
 *
 * Rush Groups
 * - Header row: Rush Group | Rush Name | Restaurant IDs Using This Rush
 *   Read-only reference so you know which "Rush Group" key to use below.
 *   Auto-filled once from SHOP_RUSH_GROUPS / RUSH_TITLES (see below);
 *   editing this sheet has no effect - to change which buildings share a
 *   Rush, edit SHOP_RUSH_GROUPS in the code.
 *
 * Recipe Rush Recipes  <- ADD YOUR OWN RECIPES HERE
 * - Header row: Rush Group | Recipe Name | Description | Difficulty |
 *   Ingredients (comma-separated) | Preparation | Deliver To | Status
 *   This is the LIVE source of recipes. Auto-seeded once with 30 starter
 *   recipes per Rush Group (from RUSH_RECIPES below) the first time the
 *   script runs. From then on, every recipeRushToday call reads straight
 *   from this sheet: add a new row with an existing "Rush Group" value
 *   (see the Rush Groups sheet) and Status "Active" to make it show up for
 *   players immediately - no redeploy needed. Set Status to "Inactive" to
 *   retire a recipe without deleting it.
 *
 * Every restaurant, Sushi Evolution stage and shop has its own "Rush" (Sushi
 * Rush, Coffee Rush, Poké Rush, Wizard Rush, ...). SHOP_RUSH_GROUPS / RUSH_TITLES
 * / RUSH_RECIPES below are the seed/fallback data - once the Recipe Rush
 * Recipes sheet has rows for a group, those sheet rows are what gets served.
 */

const REWARD_DATABASES = [
  {
    sheetNames: ['Taiyaki Coins', 'Taiyaki Coin', 'Taiyaki'],
    rewardType: 'taiyaki_coins',
    codeColumn: 1,
    amountColumn: 2,
    statusColumn: 3
  },
  {
    sheetNames: ['Onigimon Coins', 'Onigimon Coin', 'Onigimon Comet Shards', 'Comet Shards'],
    rewardType: 'onigimon_coins',
    codeColumn: 1,
    amountColumn: 2,
    statusColumn: 3,
    currencyColumn: 4,
    defaultCurrency: 'comet_shards'
  },
  {
    sheetNames: ['Onigimon Items', 'Onigimon Itens', 'Onigimon Ítens', 'Items', 'Itens'],
    rewardType: 'onigimon_item',
    codeColumn: 1,
    itemColumn: 2,
    amountColumn: 3,
    statusColumn: 4
  },
  {
    sheetNames: ['Hex Coins', 'Hex Coin', 'Hexagon Land', 'Hexagon Land Coins'],
    rewardType: 'hex_coins',
    codeColumn: 1,
    amountColumn: 2,
    statusColumn: 3
  }
];

const RECIPE_RUSH_RESTAURANTS_SHEET = 'Recipe Rush Restaurants';
const RECIPE_RUSH_RECIPES_SHEET = 'Recipe Rush Recipes';
const RUSH_GROUPS_SHEET = 'Rush Groups';

// Maps every restaurant / Sushi Evolution stage / shop id (as sent by the
// add-on) to the "Rush" content pool it should use. Buildings that are just
// upgrade stages of the same place (all Sushi Evolutions, including the base
// Onigiri Stand) share one pool; every other restaurant or shop gets its own.
const SHOP_RUSH_GROUPS = {
  'default': 'sushi',
  'restaurant_evo_i': 'sushi',
  'restaurant_evo_ii': 'sushi',
  'restaurant_evo_iii': 'sushi',
  'restaurant_evo_iv': 'sushi',
  'restaurant_evo_legendary': 'sushi',
  'restaurant_evo_garden': 'sushi',
  'restaurant_evo_heaven': 'sushi',
  'restaurant_evo_paradise': 'sushi',

  'focus_dango': 'dango',
  'motivated_mochi': 'mochi',
  'macha_delights': 'matcha',
  'macaron_maison': 'macaron',
  'coffee_co': 'coffee',
  'bakery_heaven': 'bakery',
  'awesome_boba': 'boba',
  'awesome_shiny_boba': 'shiny_boba',
  'santas_coffee': 'holiday_coffee',

  'grocery_store': 'grocery',
  'lunar_new_year': 'lunar',
  'astronigiri': 'astro',
  'pokestore': 'poke',
  'wizard_shop': 'wizard',
  'onigilab': 'lab',
  'paws_whiskers': 'paws',
  'dino_shop': 'dino'
};

const RUSH_TITLES = {
  "sushi": "Sushi Rush",
  "dango": "Dango Rush",
  "mochi": "Mochi Rush",
  "matcha": "Matcha Rush",
  "macaron": "Macaron Rush",
  "coffee": "Coffee Rush",
  "bakery": "Bakery Rush",
  "boba": "Boba Rush",
  "shiny_boba": "Shiny Boba Rush",
  "holiday_coffee": "Holiday Coffee Rush",
  "grocery": "Grocery Rush",
  "lunar": "Lunar Rush",
  "astro": "Astro Rush",
  "poke": "Poké Rush",
  "wizard": "Wizard Rush",
  "lab": "Lab Rush",
  "paws": "Paws Rush",
  "dino": "Dino Rush",
};

// Each recipe tuple: [name, description, difficulty, ingredientNames[], preparation, deliverTo]
const RUSH_RECIPES = {
  "sushi": [
    ["Ocean Uramaki", "Ocean Uramaki, an ocean favorite built around Rice and Tuna.", "common", ["Rice", "Tuna", "Avocado"], "Roll it tightly at the sushi counter.", "Onigiri Stand counter"],
    ["Golden Dragon Roll", "A golden twist on the classic, blending Nori, Wasabi, and Eel.", "common", ["Nori", "Wasabi", "Eel"], "Slice with a steady hand and plate with care.", "Sushi counter window"],
    ["Festival Dragon Roll", "Rich with Salmon and finished with Cucumber for a festival touch.", "uncommon", ["Salmon", "Roe", "Cucumber"], "Press the rice gently before adding the topping.", "Evening dinner table"],
    ["Ocean Temaki", "This ocean creation layers Tuna over Avocado for a memorable bite.", "common", ["Tuna", "Avocado", "Sesame"], "Arrange the pieces in a neat line on the tray.", "Garden seating area"],
    ["Ocean Spider Roll", "An ocean specialty starring Wasabi, paired with Eel and a hint of Ginger.", "uncommon", ["Wasabi", "Eel", "Ginger"], "Layer the ingredients and finish with a light glaze.", "Takeout tray for a hungry customer"],
    ["Ocean Chirashi", "Ocean Chirashi, an ocean favorite built around Roe and Cucumber.", "rare", ["Roe", "Cucumber", "Soy Glaze"], "Roll it tightly at the sushi counter.", "Onigiri Stand counter"],
    ["Sunrise Spider Roll", "A sunrise twist on the classic, blending Avocado, Sesame, and Crab.", "uncommon", ["Avocado", "Sesame", "Crab"], "Slice with a steady hand and plate with care.", "Sushi counter window"],
    ["Velvet Bento Tray", "Rich with Eel and finished with Shiso Leaf for a velvet touch.", "rare", ["Eel", "Ginger", "Shiso Leaf"], "Press the rice gently before adding the topping.", "Evening dinner table"],
    ["Midnight Inari", "This midnight creation layers Cucumber over Soy Glaze for a memorable bite.", "epic", ["Cucumber", "Soy Glaze", "Rice"], "Arrange the pieces in a neat line on the tray.", "Garden seating area"],
    ["Midnight Volcano Roll", "A midnight specialty starring Sesame, paired with Crab and a hint of Nori.", "legendary", ["Sesame", "Crab", "Nori"], "Layer the ingredients and finish with a light glaze.", "Takeout tray for a hungry customer"],
    ["Garden Tempura Roll", "Garden Tempura Roll, a garden favorite built around Ginger and Shiso Leaf.", "common", ["Ginger", "Shiso Leaf", "Salmon"], "Roll it tightly at the sushi counter.", "Onigiri Stand counter"],
    ["Midnight Spider Roll", "A midnight twist on the classic, blending Soy Glaze, Rice, and Tuna.", "common", ["Soy Glaze", "Rice", "Tuna"], "Slice with a steady hand and plate with care.", "Sushi counter window"],
    ["Sunrise Nigiri Maguro", "Rich with Crab and finished with Wasabi for a sunrise touch.", "uncommon", ["Crab", "Nori", "Wasabi"], "Press the rice gently before adding the topping.", "Evening dinner table"],
    ["Velvet Dragon Roll", "This velvet creation layers Shiso Leaf over Salmon for a memorable bite.", "common", ["Shiso Leaf", "Salmon", "Roe"], "Arrange the pieces in a neat line on the tray.", "Garden seating area"],
    ["Golden Chirashi", "A golden specialty starring Rice, paired with Tuna and a hint of Avocado.", "uncommon", ["Rice", "Tuna", "Avocado"], "Layer the ingredients and finish with a light glaze.", "Takeout tray for a hungry customer"],
    ["Midnight Nigiri Sake", "Midnight Nigiri Sake, a midnight favorite built around Nori and Wasabi.", "rare", ["Nori", "Wasabi", "Eel"], "Roll it tightly at the sushi counter.", "Onigiri Stand counter"],
    ["Midnight Chirashi", "A midnight twist on the classic, blending Salmon, Roe, and Cucumber.", "uncommon", ["Salmon", "Roe", "Cucumber"], "Slice with a steady hand and plate with care.", "Sushi counter window"],
    ["Golden Tempura Roll", "Rich with Tuna and finished with Sesame for a golden touch.", "rare", ["Tuna", "Avocado", "Sesame"], "Press the rice gently before adding the topping.", "Evening dinner table"],
    ["Garden Rainbow Roll", "This garden creation layers Wasabi over Eel for a memorable bite.", "epic", ["Wasabi", "Eel", "Ginger"], "Arrange the pieces in a neat line on the tray.", "Garden seating area"],
    ["Festival Rainbow Roll", "A festival specialty starring Roe, paired with Cucumber and a hint of Soy Glaze.", "legendary", ["Roe", "Cucumber", "Soy Glaze"], "Layer the ingredients and finish with a light glaze.", "Takeout tray for a hungry customer"],
    ["Ocean Volcano Roll", "Ocean Volcano Roll, an ocean favorite built around Avocado and Sesame.", "common", ["Avocado", "Sesame", "Crab"], "Roll it tightly at the sushi counter.", "Onigiri Stand counter"],
    ["Sunrise Temaki", "A sunrise twist on the classic, blending Eel, Ginger, and Shiso Leaf.", "common", ["Eel", "Ginger", "Shiso Leaf"], "Slice with a steady hand and plate with care.", "Sushi counter window"],
    ["Golden Nigiri Maguro", "Rich with Cucumber and finished with Rice for a golden touch.", "uncommon", ["Cucumber", "Soy Glaze", "Rice"], "Press the rice gently before adding the topping.", "Evening dinner table"],
    ["Garden Volcano Roll", "This garden creation layers Sesame over Crab for a memorable bite.", "common", ["Sesame", "Crab", "Nori"], "Arrange the pieces in a neat line on the tray.", "Garden seating area"],
    ["Velvet Rainbow Roll", "A velvet specialty starring Ginger, paired with Shiso Leaf and a hint of Salmon.", "uncommon", ["Ginger", "Shiso Leaf", "Salmon"], "Layer the ingredients and finish with a light glaze.", "Takeout tray for a hungry customer"],
    ["Imperial Nigiri Sake", "Imperial Nigiri Sake, an imperial favorite built around Soy Glaze and Rice.", "rare", ["Soy Glaze", "Rice", "Tuna"], "Roll it tightly at the sushi counter.", "Onigiri Stand counter"],
    ["Midnight Bento Tray", "A midnight twist on the classic, blending Crab, Nori, and Wasabi.", "uncommon", ["Crab", "Nori", "Wasabi"], "Slice with a steady hand and plate with care.", "Sushi counter window"],
    ["Velvet Volcano Roll", "Rich with Shiso Leaf and finished with Roe for a velvet touch.", "rare", ["Shiso Leaf", "Salmon", "Roe"], "Press the rice gently before adding the topping.", "Evening dinner table"],
    ["Festival Nigiri Maguro", "This festival creation layers Rice over Tuna for a memorable bite.", "epic", ["Rice", "Tuna", "Avocado"], "Arrange the pieces in a neat line on the tray.", "Garden seating area"],
    ["Ocean Tempura Roll", "An ocean specialty starring Nori, paired with Wasabi and a hint of Eel.", "legendary", ["Nori", "Wasabi", "Eel"], "Layer the ingredients and finish with a light glaze.", "Takeout tray for a hungry customer"],
  ],
  "dango": [
    ["Mindful Anko Dango", "Mindful Anko Dango, a mindful favorite built around Rice Flour and Roasted Soybean Powder.", "common", ["Rice Flour", "Roasted Soybean Powder", "Sesame Seeds"], "Skewer the dango evenly and grill until lightly toasted.", "Focus Dango counter"],
    ["Focused Festival Dango", "A focused twist on the classic, blending Sweet Soy Glaze, Matcha Powder, and Sakura Petal.", "common", ["Sweet Soy Glaze", "Matcha Powder", "Sakura Petal"], "Brush on the glaze while it's still warm.", "Study nook tray"],
    ["Tranquil Anko Dango", "Rich with Red Bean Paste and finished with Brown Sugar Syrup for a tranquil touch.", "uncommon", ["Red Bean Paste", "Skewer Stick", "Brown Sugar Syrup"], "Steam gently, then dust with the finishing powder.", "Quiet reading corner"],
    ["Mindful Roasted Dango", "This mindful creation layers Roasted Soybean Powder over Sesame Seeds for a memorable bite.", "common", ["Roasted Soybean Powder", "Sesame Seeds", "Chestnut Bits"], "Shape each ball with calm, steady hands.", "Garden bench"],
    ["Calm Bamboo Skewer Dango", "A calm specialty starring Matcha Powder, paired with Sakura Petal and a hint of Rice Flour.", "uncommon", ["Matcha Powder", "Sakura Petal", "Rice Flour"], "Toast over low heat for a smoky finish.", "Afternoon snack stand"],
    ["Quiet Chestnut Dango", "Quiet Chestnut Dango, a quiet favorite built around Skewer Stick and Brown Sugar Syrup.", "rare", ["Skewer Stick", "Brown Sugar Syrup", "Sweet Soy Glaze"], "Skewer the dango evenly and grill until lightly toasted.", "Focus Dango counter"],
    ["Focused Sakura Dango", "A focused twist on the classic, blending Sesame Seeds, Chestnut Bits, and Red Bean Paste.", "uncommon", ["Sesame Seeds", "Chestnut Bits", "Red Bean Paste"], "Brush on the glaze while it's still warm.", "Study nook tray"],
    ["Mindful Plum Dango", "Rich with Sakura Petal and finished with Roasted Soybean Powder for a mindful touch.", "rare", ["Sakura Petal", "Rice Flour", "Roasted Soybean Powder"], "Steam gently, then dust with the finishing powder.", "Quiet reading corner"],
    ["Quiet Matcha Dango", "This quiet creation layers Brown Sugar Syrup over Sweet Soy Glaze for a memorable bite.", "epic", ["Brown Sugar Syrup", "Sweet Soy Glaze", "Matcha Powder"], "Shape each ball with calm, steady hands.", "Garden bench"],
    ["Steady Three-Color Dango", "A steady specialty starring Chestnut Bits, paired with Red Bean Paste and a hint of Skewer Stick.", "legendary", ["Chestnut Bits", "Red Bean Paste", "Skewer Stick"], "Toast over low heat for a smoky finish.", "Afternoon snack stand"],
    ["Steady Plum Dango", "Steady Plum Dango, a steady favorite built around Rice Flour and Roasted Soybean Powder.", "common", ["Rice Flour", "Roasted Soybean Powder", "Sesame Seeds"], "Skewer the dango evenly and grill until lightly toasted.", "Focus Dango counter"],
    ["Quiet Roasted Dango", "A quiet twist on the classic, blending Sweet Soy Glaze, Matcha Powder, and Sakura Petal.", "common", ["Sweet Soy Glaze", "Matcha Powder", "Sakura Petal"], "Brush on the glaze while it's still warm.", "Study nook tray"],
    ["Steady Sakura Dango", "Rich with Red Bean Paste and finished with Brown Sugar Syrup for a steady touch.", "uncommon", ["Red Bean Paste", "Skewer Stick", "Brown Sugar Syrup"], "Steam gently, then dust with the finishing powder.", "Quiet reading corner"],
    ["Zen Mitarashi Dango", "This zen creation layers Roasted Soybean Powder over Sesame Seeds for a memorable bite.", "common", ["Roasted Soybean Powder", "Sesame Seeds", "Chestnut Bits"], "Shape each ball with calm, steady hands.", "Garden bench"],
    ["Calm Sakura Dango", "A calm specialty starring Matcha Powder, paired with Sakura Petal and a hint of Rice Flour.", "uncommon", ["Matcha Powder", "Sakura Petal", "Rice Flour"], "Toast over low heat for a smoky finish.", "Afternoon snack stand"],
    ["Tranquil Kinako Dango", "Tranquil Kinako Dango, a tranquil favorite built around Skewer Stick and Brown Sugar Syrup.", "rare", ["Skewer Stick", "Brown Sugar Syrup", "Sweet Soy Glaze"], "Skewer the dango evenly and grill until lightly toasted.", "Focus Dango counter"],
    ["Focused Chestnut Dango", "A focused twist on the classic, blending Sesame Seeds, Chestnut Bits, and Red Bean Paste.", "uncommon", ["Sesame Seeds", "Chestnut Bits", "Red Bean Paste"], "Brush on the glaze while it's still warm.", "Study nook tray"],
    ["Calm Festival Dango", "Rich with Sakura Petal and finished with Roasted Soybean Powder for a calm touch.", "rare", ["Sakura Petal", "Rice Flour", "Roasted Soybean Powder"], "Steam gently, then dust with the finishing powder.", "Quiet reading corner"],
    ["Mindful Festival Dango", "This mindful creation layers Brown Sugar Syrup over Sweet Soy Glaze for a memorable bite.", "epic", ["Brown Sugar Syrup", "Sweet Soy Glaze", "Matcha Powder"], "Shape each ball with calm, steady hands.", "Garden bench"],
    ["Zen Sakura Dango", "A zen specialty starring Chestnut Bits, paired with Red Bean Paste and a hint of Skewer Stick.", "legendary", ["Chestnut Bits", "Red Bean Paste", "Skewer Stick"], "Toast over low heat for a smoky finish.", "Afternoon snack stand"],
    ["Zen Festival Dango", "Zen Festival Dango, a zen favorite built around Rice Flour and Roasted Soybean Powder.", "common", ["Rice Flour", "Roasted Soybean Powder", "Sesame Seeds"], "Skewer the dango evenly and grill until lightly toasted.", "Focus Dango counter"],
    ["Mindful Matcha Dango", "A mindful twist on the classic, blending Sweet Soy Glaze, Matcha Powder, and Sakura Petal.", "common", ["Sweet Soy Glaze", "Matcha Powder", "Sakura Petal"], "Brush on the glaze while it's still warm.", "Study nook tray"],
    ["Mindful Mitarashi Dango", "Rich with Red Bean Paste and finished with Brown Sugar Syrup for a mindful touch.", "uncommon", ["Red Bean Paste", "Skewer Stick", "Brown Sugar Syrup"], "Steam gently, then dust with the finishing powder.", "Quiet reading corner"],
    ["Morning Matcha Dango", "This morning creation layers Roasted Soybean Powder over Sesame Seeds for a memorable bite.", "common", ["Roasted Soybean Powder", "Sesame Seeds", "Chestnut Bits"], "Shape each ball with calm, steady hands.", "Garden bench"],
    ["Quiet Festival Dango", "A quiet specialty starring Matcha Powder, paired with Sakura Petal and a hint of Rice Flour.", "uncommon", ["Matcha Powder", "Sakura Petal", "Rice Flour"], "Toast over low heat for a smoky finish.", "Afternoon snack stand"],
    ["Morning Anko Dango", "Morning Anko Dango, a morning favorite built around Skewer Stick and Brown Sugar Syrup.", "rare", ["Skewer Stick", "Brown Sugar Syrup", "Sweet Soy Glaze"], "Skewer the dango evenly and grill until lightly toasted.", "Focus Dango counter"],
    ["Mindful Kinako Dango", "A mindful twist on the classic, blending Sesame Seeds, Chestnut Bits, and Red Bean Paste.", "uncommon", ["Sesame Seeds", "Chestnut Bits", "Red Bean Paste"], "Brush on the glaze while it's still warm.", "Study nook tray"],
    ["Focused Mitarashi Dango", "Rich with Sakura Petal and finished with Roasted Soybean Powder for a focused touch.", "rare", ["Sakura Petal", "Rice Flour", "Roasted Soybean Powder"], "Steam gently, then dust with the finishing powder.", "Quiet reading corner"],
    ["Steady Bamboo Skewer Dango", "This steady creation layers Brown Sugar Syrup over Sweet Soy Glaze for a memorable bite.", "epic", ["Brown Sugar Syrup", "Sweet Soy Glaze", "Matcha Powder"], "Shape each ball with calm, steady hands.", "Garden bench"],
    ["Steady Moonlit Dango", "A steady specialty starring Chestnut Bits, paired with Red Bean Paste and a hint of Skewer Stick.", "legendary", ["Chestnut Bits", "Red Bean Paste", "Skewer Stick"], "Toast over low heat for a smoky finish.", "Afternoon snack stand"],
  ],
  "mochi": [
    ["Bouncy Red Bean Mochi", "Bouncy Red Bean Mochi, a bouncy favorite built around Glutinous Rice Flour and Soybean Powder.", "common", ["Glutinous Rice Flour", "Soybean Powder", "Matcha Filling"], "Knead the dough until soft and stretchy.", "Motivated Mochi stand"],
    ["Lively Red Bean Mochi", "A lively twist on the classic, blending Sweet Red Bean, Coconut Flakes, and Sugar Dust.", "common", ["Sweet Red Bean", "Coconut Flakes", "Sugar Dust"], "Wrap the filling carefully without tearing the mochi skin.", "Study group table"],
    ["Spirited Coconut Mochi", "Rich with Strawberry and finished with Ice Cream Core for a spirited touch.", "uncommon", ["Strawberry", "Peanut Crumble", "Ice Cream Core"], "Dust generously with powder before serving.", "Morning pep-talk corner"],
    ["Energized Kinako Mochi", "This energized creation layers Soybean Powder over Matcha Filling for a memorable bite.", "common", ["Soybean Powder", "Matcha Filling", "Sesame Coating"], "Pound and fold the rice until perfectly chewy.", "Energy break stand"],
    ["Lively Daifuku Mochi", "A lively specialty starring Coconut Flakes, paired with Sugar Dust and a hint of Glutinous Rice Flour.", "uncommon", ["Coconut Flakes", "Sugar Dust", "Glutinous Rice Flour"], "Chill briefly to set the filling.", "Cheer squad table"],
    ["Lively Matcha Mochi", "Lively Matcha Mochi, a lively favorite built around Peanut Crumble and Ice Cream Core.", "rare", ["Peanut Crumble", "Ice Cream Core", "Sweet Red Bean"], "Knead the dough until soft and stretchy.", "Motivated Mochi stand"],
    ["Lively Coconut Mochi", "A lively twist on the classic, blending Matcha Filling, Sesame Coating, and Strawberry.", "uncommon", ["Matcha Filling", "Sesame Coating", "Strawberry"], "Wrap the filling carefully without tearing the mochi skin.", "Study group table"],
    ["Energized Red Bean Mochi", "Rich with Sugar Dust and finished with Soybean Powder for an energized touch.", "rare", ["Sugar Dust", "Glutinous Rice Flour", "Soybean Powder"], "Dust generously with powder before serving.", "Morning pep-talk corner"],
    ["Energized Rainbow Mochi", "This energized creation layers Ice Cream Core over Sweet Red Bean for a memorable bite.", "epic", ["Ice Cream Core", "Sweet Red Bean", "Coconut Flakes"], "Pound and fold the rice until perfectly chewy.", "Energy break stand"],
    ["Spirited Peanut Mochi", "A spirited specialty starring Sesame Coating, paired with Strawberry and a hint of Peanut Crumble.", "legendary", ["Sesame Coating", "Strawberry", "Peanut Crumble"], "Chill briefly to set the filling.", "Cheer squad table"],
    ["Pep Ichigo Mochi", "Pep Ichigo Mochi, a pep favorite built around Glutinous Rice Flour and Soybean Powder.", "common", ["Glutinous Rice Flour", "Soybean Powder", "Matcha Filling"], "Knead the dough until soft and stretchy.", "Motivated Mochi stand"],
    ["Bright Warabi Mochi", "A bright twist on the classic, blending Sweet Red Bean, Coconut Flakes, and Sugar Dust.", "common", ["Sweet Red Bean", "Coconut Flakes", "Sugar Dust"], "Wrap the filling carefully without tearing the mochi skin.", "Study group table"],
    ["Cheerful Peanut Mochi", "Rich with Strawberry and finished with Ice Cream Core for a cheerful touch.", "uncommon", ["Strawberry", "Peanut Crumble", "Ice Cream Core"], "Dust generously with powder before serving.", "Morning pep-talk corner"],
    ["Cheerful Sesame Mochi", "This cheerful creation layers Soybean Powder over Matcha Filling for a memorable bite.", "common", ["Soybean Powder", "Matcha Filling", "Sesame Coating"], "Pound and fold the rice until perfectly chewy.", "Energy break stand"],
    ["Bright Peanut Mochi", "A bright specialty starring Coconut Flakes, paired with Sugar Dust and a hint of Glutinous Rice Flour.", "uncommon", ["Coconut Flakes", "Sugar Dust", "Glutinous Rice Flour"], "Chill briefly to set the filling.", "Cheer squad table"],
    ["Cheerful Matcha Mochi", "Cheerful Matcha Mochi, a cheerful favorite built around Peanut Crumble and Ice Cream Core.", "rare", ["Peanut Crumble", "Ice Cream Core", "Sweet Red Bean"], "Knead the dough until soft and stretchy.", "Motivated Mochi stand"],
    ["Cheerful Red Bean Mochi", "A cheerful twist on the classic, blending Matcha Filling, Sesame Coating, and Strawberry.", "uncommon", ["Matcha Filling", "Sesame Coating", "Strawberry"], "Wrap the filling carefully without tearing the mochi skin.", "Study group table"],
    ["Bouncy Mochi Ice Cream", "Rich with Sugar Dust and finished with Soybean Powder for a bouncy touch.", "rare", ["Sugar Dust", "Glutinous Rice Flour", "Soybean Powder"], "Dust generously with powder before serving.", "Morning pep-talk corner"],
    ["Bouncy Kinako Mochi", "This bouncy creation layers Ice Cream Core over Sweet Red Bean for a memorable bite.", "epic", ["Ice Cream Core", "Sweet Red Bean", "Coconut Flakes"], "Pound and fold the rice until perfectly chewy.", "Energy break stand"],
    ["Cheerful Coconut Mochi", "A cheerful specialty starring Sesame Coating, paired with Strawberry and a hint of Peanut Crumble.", "legendary", ["Sesame Coating", "Strawberry", "Peanut Crumble"], "Chill briefly to set the filling.", "Cheer squad table"],
    ["Bouncy Warabi Mochi", "Bouncy Warabi Mochi, a bouncy favorite built around Glutinous Rice Flour and Soybean Powder.", "common", ["Glutinous Rice Flour", "Soybean Powder", "Matcha Filling"], "Knead the dough until soft and stretchy.", "Motivated Mochi stand"],
    ["Pep Red Bean Mochi", "A pep twist on the classic, blending Sweet Red Bean, Coconut Flakes, and Sugar Dust.", "common", ["Sweet Red Bean", "Coconut Flakes", "Sugar Dust"], "Wrap the filling carefully without tearing the mochi skin.", "Study group table"],
    ["Pep Rainbow Mochi", "Rich with Strawberry and finished with Ice Cream Core for a pep touch.", "uncommon", ["Strawberry", "Peanut Crumble", "Ice Cream Core"], "Dust generously with powder before serving.", "Morning pep-talk corner"],
    ["Cheerful Kinako Mochi", "This cheerful creation layers Soybean Powder over Matcha Filling for a memorable bite.", "common", ["Soybean Powder", "Matcha Filling", "Sesame Coating"], "Pound and fold the rice until perfectly chewy.", "Energy break stand"],
    ["Energized Ichigo Mochi", "An energized specialty starring Coconut Flakes, paired with Sugar Dust and a hint of Glutinous Rice Flour.", "uncommon", ["Coconut Flakes", "Sugar Dust", "Glutinous Rice Flour"], "Chill briefly to set the filling.", "Cheer squad table"],
    ["Energized Sesame Mochi", "Energized Sesame Mochi, an energized favorite built around Peanut Crumble and Ice Cream Core.", "rare", ["Peanut Crumble", "Ice Cream Core", "Sweet Red Bean"], "Knead the dough until soft and stretchy.", "Motivated Mochi stand"],
    ["Bright Mochi Skewers", "A bright twist on the classic, blending Matcha Filling, Sesame Coating, and Strawberry.", "uncommon", ["Matcha Filling", "Sesame Coating", "Strawberry"], "Wrap the filling carefully without tearing the mochi skin.", "Study group table"],
    ["Energized Coconut Mochi", "Rich with Sugar Dust and finished with Soybean Powder for an energized touch.", "rare", ["Sugar Dust", "Glutinous Rice Flour", "Soybean Powder"], "Dust generously with powder before serving.", "Morning pep-talk corner"],
    ["Spirited Red Bean Mochi", "This spirited creation layers Ice Cream Core over Sweet Red Bean for a memorable bite.", "epic", ["Ice Cream Core", "Sweet Red Bean", "Coconut Flakes"], "Pound and fold the rice until perfectly chewy.", "Energy break stand"],
    ["Bright Mochi Ice Cream", "A bright specialty starring Sesame Coating, paired with Strawberry and a hint of Peanut Crumble.", "legendary", ["Sesame Coating", "Strawberry", "Peanut Crumble"], "Chill briefly to set the filling.", "Cheer squad table"],
  ],
  "matcha": [
    ["Roasted Matcha Mousse", "Roasted Matcha Mousse, a roasted favorite built around Ceremonial Matcha and Condensed Milk.", "common", ["Ceremonial Matcha", "Condensed Milk", "Red Bean Swirl"], "Whisk the matcha until smooth and frothy.", "Matcha Delights counter"],
    ["Roasted Matcha Roll Cake", "A roasted twist on the classic, blending Whipped Cream, White Chocolate, and Milk Foam.", "common", ["Whipped Cream", "White Chocolate", "Milk Foam"], "Layer the cake gently to keep the matcha cream intact.", "Tea ceremony table"],
    ["Premium Matcha Mousse", "Rich with Sponge Cake and finished with Honey Drizzle for a premium touch.", "uncommon", ["Sponge Cake", "Mascarpone", "Honey Drizzle"], "Fold the cream slowly to avoid deflating it.", "Afternoon tea tray"],
    ["Ceremonial Matcha Mousse", "This ceremonial creation layers Condensed Milk over Red Bean Swirl for a memorable bite.", "common", ["Condensed Milk", "Red Bean Swirl", "Crushed Pistachio"], "Pipe the filling in a careful spiral.", "Garden patio seat"],
    ["Velvety Matcha Pudding", "A velvety specialty starring White Chocolate, paired with Milk Foam and a hint of Ceremonial Matcha.", "uncommon", ["White Chocolate", "Milk Foam", "Ceremonial Matcha"], "Dust the top with fine matcha powder.", "Window display case"],
    ["Velvety Matcha Tart", "Velvety Matcha Tart, a velvety favorite built around Mascarpone and Honey Drizzle.", "rare", ["Mascarpone", "Honey Drizzle", "Whipped Cream"], "Whisk the matcha until smooth and frothy.", "Matcha Delights counter"],
    ["Premium Matcha Macaron", "A premium twist on the classic, blending Red Bean Swirl, Crushed Pistachio, and Sponge Cake.", "uncommon", ["Red Bean Swirl", "Crushed Pistachio", "Sponge Cake"], "Layer the cake gently to keep the matcha cream intact.", "Tea ceremony table"],
    ["Imperial Matcha Tiramisu", "Rich with Milk Foam and finished with Condensed Milk for an imperial touch.", "rare", ["Milk Foam", "Ceremonial Matcha", "Condensed Milk"], "Fold the cream slowly to avoid deflating it.", "Afternoon tea tray"],
    ["Imperial Matcha Cookie", "This imperial creation layers Honey Drizzle over Whipped Cream for a memorable bite.", "epic", ["Honey Drizzle", "Whipped Cream", "White Chocolate"], "Pipe the filling in a careful spiral.", "Garden patio seat"],
    ["Imperial Matcha Roll Cake", "An imperial specialty starring Crushed Pistachio, paired with Sponge Cake and a hint of Mascarpone.", "legendary", ["Crushed Pistachio", "Sponge Cake", "Mascarpone"], "Dust the top with fine matcha powder.", "Window display case"],
    ["Velvety Matcha Mousse", "Velvety Matcha Mousse, a velvety favorite built around Ceremonial Matcha and Condensed Milk.", "common", ["Ceremonial Matcha", "Condensed Milk", "Red Bean Swirl"], "Whisk the matcha until smooth and frothy.", "Matcha Delights counter"],
    ["Imperial Matcha Soft Serve", "An imperial twist on the classic, blending Whipped Cream, White Chocolate, and Milk Foam.", "common", ["Whipped Cream", "White Chocolate", "Milk Foam"], "Layer the cake gently to keep the matcha cream intact.", "Tea ceremony table"],
    ["Premium Matcha Roll Cake", "Rich with Sponge Cake and finished with Honey Drizzle for a premium touch.", "uncommon", ["Sponge Cake", "Mascarpone", "Honey Drizzle"], "Fold the cream slowly to avoid deflating it.", "Afternoon tea tray"],
    ["Garden Matcha Parfait", "This garden creation layers Condensed Milk over Red Bean Swirl for a memorable bite.", "common", ["Condensed Milk", "Red Bean Swirl", "Crushed Pistachio"], "Pipe the filling in a careful spiral.", "Garden patio seat"],
    ["Roasted Matcha Cheesecake", "A roasted specialty starring White Chocolate, paired with Milk Foam and a hint of Ceremonial Matcha.", "uncommon", ["White Chocolate", "Milk Foam", "Ceremonial Matcha"], "Dust the top with fine matcha powder.", "Window display case"],
    ["Premium Matcha Soft Serve", "Premium Matcha Soft Serve, a premium favorite built around Mascarpone and Honey Drizzle.", "rare", ["Mascarpone", "Honey Drizzle", "Whipped Cream"], "Whisk the matcha until smooth and frothy.", "Matcha Delights counter"],
    ["Ceremonial Matcha Cookie", "A ceremonial twist on the classic, blending Red Bean Swirl, Crushed Pistachio, and Sponge Cake.", "uncommon", ["Red Bean Swirl", "Crushed Pistachio", "Sponge Cake"], "Layer the cake gently to keep the matcha cream intact.", "Tea ceremony table"],
    ["Roasted Matcha Crepe", "Rich with Milk Foam and finished with Condensed Milk for a roasted touch.", "rare", ["Milk Foam", "Ceremonial Matcha", "Condensed Milk"], "Fold the cream slowly to avoid deflating it.", "Afternoon tea tray"],
    ["Silky Matcha Soft Serve", "This silky creation layers Honey Drizzle over Whipped Cream for a memorable bite.", "epic", ["Honey Drizzle", "Whipped Cream", "White Chocolate"], "Pipe the filling in a careful spiral.", "Garden patio seat"],
    ["Premium Matcha Latte", "A premium specialty starring Crushed Pistachio, paired with Sponge Cake and a hint of Mascarpone.", "legendary", ["Crushed Pistachio", "Sponge Cake", "Mascarpone"], "Dust the top with fine matcha powder.", "Window display case"],
    ["Roasted Matcha Cookie", "Roasted Matcha Cookie, a roasted favorite built around Ceremonial Matcha and Condensed Milk.", "common", ["Ceremonial Matcha", "Condensed Milk", "Red Bean Swirl"], "Whisk the matcha until smooth and frothy.", "Matcha Delights counter"],
    ["Roasted Matcha Latte", "A roasted twist on the classic, blending Whipped Cream, White Chocolate, and Milk Foam.", "common", ["Whipped Cream", "White Chocolate", "Milk Foam"], "Layer the cake gently to keep the matcha cream intact.", "Tea ceremony table"],
    ["Velvety Matcha Latte", "Rich with Sponge Cake and finished with Honey Drizzle for a velvety touch.", "uncommon", ["Sponge Cake", "Mascarpone", "Honey Drizzle"], "Fold the cream slowly to avoid deflating it.", "Afternoon tea tray"],
    ["Roasted Matcha Pudding", "This roasted creation layers Condensed Milk over Red Bean Swirl for a memorable bite.", "common", ["Condensed Milk", "Red Bean Swirl", "Crushed Pistachio"], "Pipe the filling in a careful spiral.", "Garden patio seat"],
    ["Garden Matcha Latte", "A garden specialty starring White Chocolate, paired with Milk Foam and a hint of Ceremonial Matcha.", "uncommon", ["White Chocolate", "Milk Foam", "Ceremonial Matcha"], "Dust the top with fine matcha powder.", "Window display case"],
    ["Silky Matcha Crepe", "Silky Matcha Crepe, a silky favorite built around Mascarpone and Honey Drizzle.", "rare", ["Mascarpone", "Honey Drizzle", "Whipped Cream"], "Whisk the matcha until smooth and frothy.", "Matcha Delights counter"],
    ["Garden Matcha Pudding", "A garden twist on the classic, blending Red Bean Swirl, Crushed Pistachio, and Sponge Cake.", "uncommon", ["Red Bean Swirl", "Crushed Pistachio", "Sponge Cake"], "Layer the cake gently to keep the matcha cream intact.", "Tea ceremony table"],
    ["Premium Matcha Cookie", "Rich with Milk Foam and finished with Condensed Milk for a premium touch.", "rare", ["Milk Foam", "Ceremonial Matcha", "Condensed Milk"], "Fold the cream slowly to avoid deflating it.", "Afternoon tea tray"],
    ["Frosted Matcha Latte", "This frosted creation layers Honey Drizzle over Whipped Cream for a memorable bite.", "epic", ["Honey Drizzle", "Whipped Cream", "White Chocolate"], "Pipe the filling in a careful spiral.", "Garden patio seat"],
    ["Frosted Matcha Cheesecake", "A frosted specialty starring Crushed Pistachio, paired with Sponge Cake and a hint of Mascarpone.", "legendary", ["Crushed Pistachio", "Sponge Cake", "Mascarpone"], "Dust the top with fine matcha powder.", "Window display case"],
  ],
  "macaron": [
    ["Boutique Earl Grey Macaron", "Boutique Earl Grey Macaron, a boutique favorite built around Almond Flour and Fruit Jam.", "common", ["Almond Flour", "Fruit Jam", "Powdered Sugar"], "Pipe the shells in neat, even circles.", "Macaron Maison counter"],
    ["Delicate Vanilla Macaron", "A delicate twist on the classic, blending Egg White Meringue, Food Coloring, and Vanilla Bean.", "common", ["Egg White Meringue", "Food Coloring", "Vanilla Bean"], "Rest the shells until a skin forms before baking.", "Gift box pickup window"],
    ["Elegant Raspberry Macaron", "Rich with Buttercream and finished with Caramel Drizzle for an elegant touch.", "uncommon", ["Buttercream", "Ganache", "Caramel Drizzle"], "Sandwich the filling gently between two shells.", "Boutique display shelf"],
    ["Pastel Vanilla Macaron", "This pastel creation layers Fruit Jam over Powdered Sugar for a memorable bite.", "common", ["Fruit Jam", "Powdered Sugar", "Crushed Nuts"], "Whisk the meringue to stiff, glossy peaks.", "Afternoon tea cart"],
    ["Glossy Hazelnut Macaron", "A glossy specialty starring Food Coloring, paired with Vanilla Bean and a hint of Almond Flour.", "uncommon", ["Food Coloring", "Vanilla Bean", "Almond Flour"], "Macaronage the batter until it flows like lava.", "Window display case"],
    ["Dainty Chocolate Macaron", "Dainty Chocolate Macaron, a dainty favorite built around Ganache and Caramel Drizzle.", "rare", ["Ganache", "Caramel Drizzle", "Egg White Meringue"], "Pipe the shells in neat, even circles.", "Macaron Maison counter"],
    ["Dainty Raspberry Macaron", "A dainty twist on the classic, blending Powdered Sugar, Crushed Nuts, and Buttercream.", "uncommon", ["Powdered Sugar", "Crushed Nuts", "Buttercream"], "Rest the shells until a skin forms before baking.", "Gift box pickup window"],
    ["Elegant Rose Macaron", "Rich with Vanilla Bean and finished with Fruit Jam for an elegant touch.", "rare", ["Vanilla Bean", "Almond Flour", "Fruit Jam"], "Sandwich the filling gently between two shells.", "Boutique display shelf"],
    ["Elegant Strawberry Macaron", "This elegant creation layers Caramel Drizzle over Egg White Meringue for a memorable bite.", "epic", ["Caramel Drizzle", "Egg White Meringue", "Food Coloring"], "Whisk the meringue to stiff, glossy peaks.", "Afternoon tea cart"],
    ["Dainty Lavender Macaron", "A dainty specialty starring Crushed Nuts, paired with Buttercream and a hint of Ganache.", "legendary", ["Crushed Nuts", "Buttercream", "Ganache"], "Macaronage the batter until it flows like lava.", "Window display case"],
    ["Glossy Lemon Macaron", "Glossy Lemon Macaron, a glossy favorite built around Almond Flour and Fruit Jam.", "common", ["Almond Flour", "Fruit Jam", "Powdered Sugar"], "Pipe the shells in neat, even circles.", "Macaron Maison counter"],
    ["Petite Coconut Macaron", "A petite twist on the classic, blending Egg White Meringue, Food Coloring, and Vanilla Bean.", "common", ["Egg White Meringue", "Food Coloring", "Vanilla Bean"], "Rest the shells until a skin forms before baking.", "Gift box pickup window"],
    ["Parisian Caramel Macaron", "Rich with Buttercream and finished with Caramel Drizzle for a parisian touch.", "uncommon", ["Buttercream", "Ganache", "Caramel Drizzle"], "Sandwich the filling gently between two shells.", "Boutique display shelf"],
    ["Elegant Earl Grey Macaron", "This elegant creation layers Fruit Jam over Powdered Sugar for a memorable bite.", "common", ["Fruit Jam", "Powdered Sugar", "Crushed Nuts"], "Whisk the meringue to stiff, glossy peaks.", "Afternoon tea cart"],
    ["Delicate Strawberry Macaron", "A delicate specialty starring Food Coloring, paired with Vanilla Bean and a hint of Almond Flour.", "uncommon", ["Food Coloring", "Vanilla Bean", "Almond Flour"], "Macaronage the batter until it flows like lava.", "Window display case"],
    ["Delicate Lemon Macaron", "Delicate Lemon Macaron, a delicate favorite built around Ganache and Caramel Drizzle.", "rare", ["Ganache", "Caramel Drizzle", "Egg White Meringue"], "Pipe the shells in neat, even circles.", "Macaron Maison counter"],
    ["Glossy Earl Grey Macaron", "A glossy twist on the classic, blending Powdered Sugar, Crushed Nuts, and Buttercream.", "uncommon", ["Powdered Sugar", "Crushed Nuts", "Buttercream"], "Rest the shells until a skin forms before baking.", "Gift box pickup window"],
    ["Parisian Earl Grey Macaron", "Rich with Vanilla Bean and finished with Fruit Jam for a parisian touch.", "rare", ["Vanilla Bean", "Almond Flour", "Fruit Jam"], "Sandwich the filling gently between two shells.", "Boutique display shelf"],
    ["Elegant Hazelnut Macaron", "This elegant creation layers Caramel Drizzle over Egg White Meringue for a memorable bite.", "epic", ["Caramel Drizzle", "Egg White Meringue", "Food Coloring"], "Whisk the meringue to stiff, glossy peaks.", "Afternoon tea cart"],
    ["Glossy Rose Macaron", "A glossy specialty starring Crushed Nuts, paired with Buttercream and a hint of Ganache.", "legendary", ["Crushed Nuts", "Buttercream", "Ganache"], "Macaronage the batter until it flows like lava.", "Window display case"],
    ["Delicate Lavender Macaron", "Delicate Lavender Macaron, a delicate favorite built around Almond Flour and Fruit Jam.", "common", ["Almond Flour", "Fruit Jam", "Powdered Sugar"], "Pipe the shells in neat, even circles.", "Macaron Maison counter"],
    ["Glossy Strawberry Macaron", "A glossy twist on the classic, blending Egg White Meringue, Food Coloring, and Vanilla Bean.", "common", ["Egg White Meringue", "Food Coloring", "Vanilla Bean"], "Rest the shells until a skin forms before baking.", "Gift box pickup window"],
    ["Parisian Coconut Macaron", "Rich with Buttercream and finished with Caramel Drizzle for a parisian touch.", "uncommon", ["Buttercream", "Ganache", "Caramel Drizzle"], "Sandwich the filling gently between two shells.", "Boutique display shelf"],
    ["Dainty Vanilla Macaron", "This dainty creation layers Fruit Jam over Powdered Sugar for a memorable bite.", "common", ["Fruit Jam", "Powdered Sugar", "Crushed Nuts"], "Whisk the meringue to stiff, glossy peaks.", "Afternoon tea cart"],
    ["Pastel Chocolate Macaron", "A pastel specialty starring Food Coloring, paired with Vanilla Bean and a hint of Almond Flour.", "uncommon", ["Food Coloring", "Vanilla Bean", "Almond Flour"], "Macaronage the batter until it flows like lava.", "Window display case"],
    ["Pastel Hazelnut Macaron", "Pastel Hazelnut Macaron, a pastel favorite built around Ganache and Caramel Drizzle.", "rare", ["Ganache", "Caramel Drizzle", "Egg White Meringue"], "Pipe the shells in neat, even circles.", "Macaron Maison counter"],
    ["Pastel Coconut Macaron", "A pastel twist on the classic, blending Powdered Sugar, Crushed Nuts, and Buttercream.", "uncommon", ["Powdered Sugar", "Crushed Nuts", "Buttercream"], "Rest the shells until a skin forms before baking.", "Gift box pickup window"],
    ["Elegant Lavender Macaron", "Rich with Vanilla Bean and finished with Fruit Jam for an elegant touch.", "rare", ["Vanilla Bean", "Almond Flour", "Fruit Jam"], "Sandwich the filling gently between two shells.", "Boutique display shelf"],
    ["Delicate Raspberry Macaron", "This delicate creation layers Caramel Drizzle over Egg White Meringue for a memorable bite.", "epic", ["Caramel Drizzle", "Egg White Meringue", "Food Coloring"], "Whisk the meringue to stiff, glossy peaks.", "Afternoon tea cart"],
    ["Petite Chocolate Macaron", "A petite specialty starring Crushed Nuts, paired with Buttercream and a hint of Ganache.", "legendary", ["Crushed Nuts", "Buttercream", "Ganache"], "Macaronage the batter until it flows like lava.", "Window display case"],
  ],
  "coffee": [
    ["Velvet Flat White", "Velvet Flat White, a velvet favorite built around Espresso Beans and Vanilla Syrup.", "common", ["Espresso Beans", "Vanilla Syrup", "Cinnamon Dust"], "Pull a fresh shot and steam the milk to a silky foam.", "Coffee & Co. counter"],
    ["Velvet Mocha", "A velvet twist on the classic, blending Steamed Milk, Whipped Cream, and Oat Milk.", "common", ["Steamed Milk", "Whipped Cream", "Oat Milk"], "Pour slowly to layer the latte art.", "Morning commuter window"],
    ["Artisan Vanilla Cortado", "Rich with Caramel Syrup and finished with Ice Cubes for an artisan touch.", "uncommon", ["Caramel Syrup", "Cocoa Powder", "Ice Cubes"], "Stir gently so the syrup blends evenly.", "Study corner table"],
    ["Roasted Hazelnut Latte", "This roasted creation layers Vanilla Syrup over Cinnamon Dust for a memorable bite.", "common", ["Vanilla Syrup", "Cinnamon Dust", "Chocolate Drizzle"], "Brew low and slow for a smooth finish.", "Takeout window"],
    ["Double Caramel Macchiato", "A double specialty starring Whipped Cream, paired with Oat Milk and a hint of Espresso Beans.", "uncommon", ["Whipped Cream", "Oat Milk", "Espresso Beans"], "Top with foam and a light dusting of cocoa.", "Espresso bar"],
    ["Morning Vanilla Cortado", "Morning Vanilla Cortado, a morning favorite built around Cocoa Powder and Ice Cubes.", "rare", ["Cocoa Powder", "Ice Cubes", "Steamed Milk"], "Pull a fresh shot and steam the milk to a silky foam.", "Coffee & Co. counter"],
    ["Bold Mocha", "A bold twist on the classic, blending Cinnamon Dust, Chocolate Drizzle, and Caramel Syrup.", "uncommon", ["Cinnamon Dust", "Chocolate Drizzle", "Caramel Syrup"], "Pour slowly to layer the latte art.", "Morning commuter window"],
    ["Roasted Caramel Macchiato", "Rich with Oat Milk and finished with Vanilla Syrup for a roasted touch.", "rare", ["Oat Milk", "Espresso Beans", "Vanilla Syrup"], "Stir gently so the syrup blends evenly.", "Study corner table"],
    ["Signature Affogato", "This signature creation layers Ice Cubes over Steamed Milk for a memorable bite.", "epic", ["Ice Cubes", "Steamed Milk", "Whipped Cream"], "Brew low and slow for a smooth finish.", "Takeout window"],
    ["Bold Iced Americano", "A bold specialty starring Chocolate Drizzle, paired with Caramel Syrup and a hint of Cocoa Powder.", "legendary", ["Chocolate Drizzle", "Caramel Syrup", "Cocoa Powder"], "Top with foam and a light dusting of cocoa.", "Espresso bar"],
    ["Velvet Caramel Macchiato", "Velvet Caramel Macchiato, a velvet favorite built around Espresso Beans and Vanilla Syrup.", "common", ["Espresso Beans", "Vanilla Syrup", "Cinnamon Dust"], "Pull a fresh shot and steam the milk to a silky foam.", "Coffee & Co. counter"],
    ["Smooth Cappuccino", "A smooth twist on the classic, blending Steamed Milk, Whipped Cream, and Oat Milk.", "common", ["Steamed Milk", "Whipped Cream", "Oat Milk"], "Pour slowly to layer the latte art.", "Morning commuter window"],
    ["Smooth Flat White", "Rich with Caramel Syrup and finished with Ice Cubes for a smooth touch.", "uncommon", ["Caramel Syrup", "Cocoa Powder", "Ice Cubes"], "Stir gently so the syrup blends evenly.", "Study corner table"],
    ["Morning Latte Art Special", "This morning creation layers Vanilla Syrup over Cinnamon Dust for a memorable bite.", "common", ["Vanilla Syrup", "Cinnamon Dust", "Chocolate Drizzle"], "Brew low and slow for a smooth finish.", "Takeout window"],
    ["Double Hazelnut Latte", "A double specialty starring Whipped Cream, paired with Oat Milk and a hint of Espresso Beans.", "uncommon", ["Whipped Cream", "Oat Milk", "Espresso Beans"], "Top with foam and a light dusting of cocoa.", "Espresso bar"],
    ["Artisan Hazelnut Latte", "Artisan Hazelnut Latte, an artisan favorite built around Cocoa Powder and Ice Cubes.", "rare", ["Cocoa Powder", "Ice Cubes", "Steamed Milk"], "Pull a fresh shot and steam the milk to a silky foam.", "Coffee & Co. counter"],
    ["Double Flat White", "A double twist on the classic, blending Cinnamon Dust, Chocolate Drizzle, and Caramel Syrup.", "uncommon", ["Cinnamon Dust", "Chocolate Drizzle", "Caramel Syrup"], "Pour slowly to layer the latte art.", "Morning commuter window"],
    ["Bold Latte Art Special", "Rich with Oat Milk and finished with Vanilla Syrup for a bold touch.", "rare", ["Oat Milk", "Espresso Beans", "Vanilla Syrup"], "Stir gently so the syrup blends evenly.", "Study corner table"],
    ["Double Cold Brew", "This double creation layers Ice Cubes over Steamed Milk for a memorable bite.", "epic", ["Ice Cubes", "Steamed Milk", "Whipped Cream"], "Brew low and slow for a smooth finish.", "Takeout window"],
    ["Signature Pour-Over", "A signature specialty starring Chocolate Drizzle, paired with Caramel Syrup and a hint of Cocoa Powder.", "legendary", ["Chocolate Drizzle", "Caramel Syrup", "Cocoa Powder"], "Top with foam and a light dusting of cocoa.", "Espresso bar"],
    ["Artisan Pour-Over", "Artisan Pour-Over, an artisan favorite built around Espresso Beans and Vanilla Syrup.", "common", ["Espresso Beans", "Vanilla Syrup", "Cinnamon Dust"], "Pull a fresh shot and steam the milk to a silky foam.", "Coffee & Co. counter"],
    ["Double Latte Art Special", "A double twist on the classic, blending Steamed Milk, Whipped Cream, and Oat Milk.", "common", ["Steamed Milk", "Whipped Cream", "Oat Milk"], "Pour slowly to layer the latte art.", "Morning commuter window"],
    ["Roasted Cold Brew", "Rich with Caramel Syrup and finished with Ice Cubes for a roasted touch.", "uncommon", ["Caramel Syrup", "Cocoa Powder", "Ice Cubes"], "Stir gently so the syrup blends evenly.", "Study corner table"],
    ["Double Mocha", "This double creation layers Vanilla Syrup over Cinnamon Dust for a memorable bite.", "common", ["Vanilla Syrup", "Cinnamon Dust", "Chocolate Drizzle"], "Brew low and slow for a smooth finish.", "Takeout window"],
    ["Roasted Iced Americano", "A roasted specialty starring Whipped Cream, paired with Oat Milk and a hint of Espresso Beans.", "uncommon", ["Whipped Cream", "Oat Milk", "Espresso Beans"], "Top with foam and a light dusting of cocoa.", "Espresso bar"],
    ["Roasted Vanilla Cortado", "Roasted Vanilla Cortado, a roasted favorite built around Cocoa Powder and Ice Cubes.", "rare", ["Cocoa Powder", "Ice Cubes", "Steamed Milk"], "Pull a fresh shot and steam the milk to a silky foam.", "Coffee & Co. counter"],
    ["Double Vanilla Cortado", "A double twist on the classic, blending Cinnamon Dust, Chocolate Drizzle, and Caramel Syrup.", "uncommon", ["Cinnamon Dust", "Chocolate Drizzle", "Caramel Syrup"], "Pour slowly to layer the latte art.", "Morning commuter window"],
    ["Bold Affogato", "Rich with Oat Milk and finished with Vanilla Syrup for a bold touch.", "rare", ["Oat Milk", "Espresso Beans", "Vanilla Syrup"], "Stir gently so the syrup blends evenly.", "Study corner table"],
    ["Smooth Pour-Over", "This smooth creation layers Ice Cubes over Steamed Milk for a memorable bite.", "epic", ["Ice Cubes", "Steamed Milk", "Whipped Cream"], "Brew low and slow for a smooth finish.", "Takeout window"],
    ["Artisan Latte Art Special", "An artisan specialty starring Chocolate Drizzle, paired with Caramel Syrup and a hint of Cocoa Powder.", "legendary", ["Chocolate Drizzle", "Caramel Syrup", "Cocoa Powder"], "Top with foam and a light dusting of cocoa.", "Espresso bar"],
  ],
  "bakery": [
    ["Golden Berry Muffin", "Golden Berry Muffin, a golden favorite built around Butter and Cinnamon Sugar.", "common", ["Butter", "Cinnamon Sugar", "Cream Filling"], "Proof the dough until it doubles in size.", "Bakery Heaven counter"],
    ["Rustic Pretzel Roll", "A rustic twist on the classic, blending Flour, Honey Glaze, and Egg Wash.", "common", ["Flour", "Honey Glaze", "Egg Wash"], "Fold the layers carefully to keep them flaky.", "Morning pickup shelf"],
    ["Golden Baguette", "Rich with Yeast and finished with Sea Salt for a golden touch.", "uncommon", ["Yeast", "Fresh Berries", "Sea Salt"], "Brush with egg wash before baking golden brown.", "Fresh-out-of-the-oven tray"],
    ["Rustic Baguette", "This rustic creation layers Cinnamon Sugar over Cream Filling for a memorable bite.", "common", ["Cinnamon Sugar", "Cream Filling", "Vanilla Custard"], "Pipe in the filling once cooled slightly.", "Window display case"],
    ["Warm Cream Puff", "A warm specialty starring Honey Glaze, paired with Egg Wash and a hint of Butter.", "uncommon", ["Honey Glaze", "Egg Wash", "Butter"], "Bake until the crust turns a deep golden color.", "Pastry basket"],
    ["Warm Cinnamon Roll", "Warm Cinnamon Roll, a warm favorite built around Fresh Berries and Sea Salt.", "rare", ["Fresh Berries", "Sea Salt", "Flour"], "Proof the dough until it doubles in size.", "Bakery Heaven counter"],
    ["Buttery Berry Muffin", "A buttery twist on the classic, blending Cream Filling, Vanilla Custard, and Yeast.", "uncommon", ["Cream Filling", "Vanilla Custard", "Yeast"], "Fold the layers carefully to keep them flaky.", "Morning pickup shelf"],
    ["Rustic Cream Puff", "Rich with Egg Wash and finished with Cinnamon Sugar for a rustic touch.", "rare", ["Egg Wash", "Butter", "Cinnamon Sugar"], "Brush with egg wash before baking golden brown.", "Fresh-out-of-the-oven tray"],
    ["Fresh-Baked Danish Pastry", "This fresh-baked creation layers Sea Salt over Flour for a memorable bite.", "epic", ["Sea Salt", "Flour", "Honey Glaze"], "Pipe in the filling once cooled slightly.", "Window display case"],
    ["Glazed Cinnamon Roll", "A glazed specialty starring Vanilla Custard, paired with Yeast and a hint of Fresh Berries.", "legendary", ["Vanilla Custard", "Yeast", "Fresh Berries"], "Bake until the crust turns a deep golden color.", "Pastry basket"],
    ["Glazed Fruit Tart", "Glazed Fruit Tart, a glazed favorite built around Butter and Cinnamon Sugar.", "common", ["Butter", "Cinnamon Sugar", "Cream Filling"], "Proof the dough until it doubles in size.", "Bakery Heaven counter"],
    ["Golden Honey Bun", "A golden twist on the classic, blending Flour, Honey Glaze, and Egg Wash.", "common", ["Flour", "Honey Glaze", "Egg Wash"], "Fold the layers carefully to keep them flaky.", "Morning pickup shelf"],
    ["Buttery Croissant", "Rich with Yeast and finished with Sea Salt for a buttery touch.", "uncommon", ["Yeast", "Fresh Berries", "Sea Salt"], "Brush with egg wash before baking golden brown.", "Fresh-out-of-the-oven tray"],
    ["Flaky Croissant", "This flaky creation layers Cinnamon Sugar over Cream Filling for a memorable bite.", "common", ["Cinnamon Sugar", "Cream Filling", "Vanilla Custard"], "Pipe in the filling once cooled slightly.", "Window display case"],
    ["Warm Pretzel Roll", "A warm specialty starring Honey Glaze, paired with Egg Wash and a hint of Butter.", "uncommon", ["Honey Glaze", "Egg Wash", "Butter"], "Bake until the crust turns a deep golden color.", "Pastry basket"],
    ["Flaky Honey Bun", "Flaky Honey Bun, a flaky favorite built around Fresh Berries and Sea Salt.", "rare", ["Fresh Berries", "Sea Salt", "Flour"], "Proof the dough until it doubles in size.", "Bakery Heaven counter"],
    ["Warm Baguette", "A warm twist on the classic, blending Cream Filling, Vanilla Custard, and Yeast.", "uncommon", ["Cream Filling", "Vanilla Custard", "Yeast"], "Fold the layers carefully to keep them flaky.", "Morning pickup shelf"],
    ["Flaky Danish Pastry", "Rich with Egg Wash and finished with Cinnamon Sugar for a flaky touch.", "rare", ["Egg Wash", "Butter", "Cinnamon Sugar"], "Brush with egg wash before baking golden brown.", "Fresh-out-of-the-oven tray"],
    ["Warm Sourdough Loaf", "This warm creation layers Sea Salt over Flour for a memorable bite.", "epic", ["Sea Salt", "Flour", "Honey Glaze"], "Pipe in the filling once cooled slightly.", "Window display case"],
    ["Golden Brioche Bun", "A golden specialty starring Vanilla Custard, paired with Yeast and a hint of Fresh Berries.", "legendary", ["Vanilla Custard", "Yeast", "Fresh Berries"], "Bake until the crust turns a deep golden color.", "Pastry basket"],
    ["Flaky Pretzel Roll", "Flaky Pretzel Roll, a flaky favorite built around Butter and Cinnamon Sugar.", "common", ["Butter", "Cinnamon Sugar", "Cream Filling"], "Proof the dough until it doubles in size.", "Bakery Heaven counter"],
    ["Buttery Fruit Tart", "A buttery twist on the classic, blending Flour, Honey Glaze, and Egg Wash.", "common", ["Flour", "Honey Glaze", "Egg Wash"], "Fold the layers carefully to keep them flaky.", "Morning pickup shelf"],
    ["Flaky Cinnamon Roll", "Rich with Yeast and finished with Sea Salt for a flaky touch.", "uncommon", ["Yeast", "Fresh Berries", "Sea Salt"], "Brush with egg wash before baking golden brown.", "Fresh-out-of-the-oven tray"],
    ["Golden Cinnamon Roll", "This golden creation layers Cinnamon Sugar over Cream Filling for a memorable bite.", "common", ["Cinnamon Sugar", "Cream Filling", "Vanilla Custard"], "Pipe in the filling once cooled slightly.", "Window display case"],
    ["Glazed Apple Pie Slice", "A glazed specialty starring Honey Glaze, paired with Egg Wash and a hint of Butter.", "uncommon", ["Honey Glaze", "Egg Wash", "Butter"], "Bake until the crust turns a deep golden color.", "Pastry basket"],
    ["Fresh-Baked Brioche Bun", "Fresh-Baked Brioche Bun, a fresh-baked favorite built around Fresh Berries and Sea Salt.", "rare", ["Fresh Berries", "Sea Salt", "Flour"], "Proof the dough until it doubles in size.", "Bakery Heaven counter"],
    ["Glazed Brioche Bun", "A glazed twist on the classic, blending Cream Filling, Vanilla Custard, and Yeast.", "uncommon", ["Cream Filling", "Vanilla Custard", "Yeast"], "Fold the layers carefully to keep them flaky.", "Morning pickup shelf"],
    ["Rustic Apple Pie Slice", "Rich with Egg Wash and finished with Cinnamon Sugar for a rustic touch.", "rare", ["Egg Wash", "Butter", "Cinnamon Sugar"], "Brush with egg wash before baking golden brown.", "Fresh-out-of-the-oven tray"],
    ["Flaky Brioche Bun", "This flaky creation layers Sea Salt over Flour for a memorable bite.", "epic", ["Sea Salt", "Flour", "Honey Glaze"], "Pipe in the filling once cooled slightly.", "Window display case"],
    ["Glazed Honey Bun", "A glazed specialty starring Vanilla Custard, paired with Yeast and a hint of Fresh Berries.", "legendary", ["Vanilla Custard", "Yeast", "Fresh Berries"], "Bake until the crust turns a deep golden color.", "Pastry basket"],
  ],
  "boba": [
    ["Signature Classic Milk Tea", "Signature Classic Milk Tea, a signature favorite built around Tapioca Pearls and Black Tea.", "common", ["Tapioca Pearls", "Black Tea", "Honey"], "Shake the tea and milk together until frothy.", "Awesome Boba counter"],
    ["Sweet Lychee Tea", "A sweet twist on the classic, blending Brown Sugar Syrup, Taro Powder, and Ice.", "common", ["Brown Sugar Syrup", "Taro Powder", "Ice"], "Cook the pearls until soft and chewy.", "Takeout window"],
    ["Bubbly Classic Milk Tea", "Rich with Milk and finished with Coconut Jelly for a bubbly touch.", "uncommon", ["Milk", "Fruit Puree", "Coconut Jelly"], "Layer the syrup down the glass for a marbled look.", "After-school hangout table"],
    ["Frosty Coconut Boba", "This frosty creation layers Black Tea over Honey for a memorable bite.", "common", ["Black Tea", "Honey", "Cream Foam"], "Blend with ice until perfectly slushy.", "Park bench"],
    ["Frosty Brown Sugar Boba", "A frosty specialty starring Taro Powder, paired with Ice and a hint of Tapioca Pearls.", "uncommon", ["Taro Powder", "Ice", "Tapioca Pearls"], "Top with a thick layer of cream foam.", "Study break stand"],
    ["Chill Classic Milk Tea", "Chill Classic Milk Tea, a chill favorite built around Fruit Puree and Coconut Jelly.", "rare", ["Fruit Puree", "Coconut Jelly", "Brown Sugar Syrup"], "Shake the tea and milk together until frothy.", "Awesome Boba counter"],
    ["Sweet Wintermelon Tea", "A sweet twist on the classic, blending Honey, Cream Foam, and Milk.", "uncommon", ["Honey", "Cream Foam", "Milk"], "Cook the pearls until soft and chewy.", "Takeout window"],
    ["Awesome Honeydew Milk Tea", "Rich with Ice and finished with Black Tea for an awesome touch.", "rare", ["Ice", "Tapioca Pearls", "Black Tea"], "Layer the syrup down the glass for a marbled look.", "After-school hangout table"],
    ["Bubbly Thai Milk Tea", "This bubbly creation layers Coconut Jelly over Brown Sugar Syrup for a memorable bite.", "epic", ["Coconut Jelly", "Brown Sugar Syrup", "Taro Powder"], "Blend with ice until perfectly slushy.", "Park bench"],
    ["Bubbly Wintermelon Tea", "A bubbly specialty starring Cream Foam, paired with Milk and a hint of Fruit Puree.", "legendary", ["Cream Foam", "Milk", "Fruit Puree"], "Top with a thick layer of cream foam.", "Study break stand"],
    ["Signature Brown Sugar Boba", "Signature Brown Sugar Boba, a signature favorite built around Tapioca Pearls and Black Tea.", "common", ["Tapioca Pearls", "Black Tea", "Honey"], "Shake the tea and milk together until frothy.", "Awesome Boba counter"],
    ["Awesome Classic Milk Tea", "An awesome twist on the classic, blending Brown Sugar Syrup, Taro Powder, and Ice.", "common", ["Brown Sugar Syrup", "Taro Powder", "Ice"], "Cook the pearls until soft and chewy.", "Takeout window"],
    ["Classic Matcha Boba", "Rich with Milk and finished with Coconut Jelly for a classic touch.", "uncommon", ["Milk", "Fruit Puree", "Coconut Jelly"], "Layer the syrup down the glass for a marbled look.", "After-school hangout table"],
    ["Awesome Matcha Boba", "This awesome creation layers Black Tea over Honey for a memorable bite.", "common", ["Black Tea", "Honey", "Cream Foam"], "Blend with ice until perfectly slushy.", "Park bench"],
    ["Awesome Taro Milk Tea", "An awesome specialty starring Taro Powder, paired with Ice and a hint of Tapioca Pearls.", "uncommon", ["Taro Powder", "Ice", "Tapioca Pearls"], "Top with a thick layer of cream foam.", "Study break stand"],
    ["Classic Coconut Boba", "Classic Coconut Boba, a classic favorite built around Fruit Puree and Coconut Jelly.", "rare", ["Fruit Puree", "Coconut Jelly", "Brown Sugar Syrup"], "Shake the tea and milk together until frothy.", "Awesome Boba counter"],
    ["Awesome Mango Slush", "An awesome twist on the classic, blending Honey, Cream Foam, and Milk.", "uncommon", ["Honey", "Cream Foam", "Milk"], "Cook the pearls until soft and chewy.", "Takeout window"],
    ["Extra Coconut Boba", "Rich with Ice and finished with Black Tea for an extra touch.", "rare", ["Ice", "Tapioca Pearls", "Black Tea"], "Layer the syrup down the glass for a marbled look.", "After-school hangout table"],
    ["Sweet Classic Milk Tea", "This sweet creation layers Coconut Jelly over Brown Sugar Syrup for a memorable bite.", "epic", ["Coconut Jelly", "Brown Sugar Syrup", "Taro Powder"], "Blend with ice until perfectly slushy.", "Park bench"],
    ["Chill Matcha Boba", "A chill specialty starring Cream Foam, paired with Milk and a hint of Fruit Puree.", "legendary", ["Cream Foam", "Milk", "Fruit Puree"], "Top with a thick layer of cream foam.", "Study break stand"],
    ["Frosty Grape Slush", "Frosty Grape Slush, a frosty favorite built around Tapioca Pearls and Black Tea.", "common", ["Tapioca Pearls", "Black Tea", "Honey"], "Shake the tea and milk together until frothy.", "Awesome Boba counter"],
    ["Chill Wintermelon Tea", "A chill twist on the classic, blending Brown Sugar Syrup, Taro Powder, and Ice.", "common", ["Brown Sugar Syrup", "Taro Powder", "Ice"], "Cook the pearls until soft and chewy.", "Takeout window"],
    ["Sweet Coconut Boba", "Rich with Milk and finished with Coconut Jelly for a sweet touch.", "uncommon", ["Milk", "Fruit Puree", "Coconut Jelly"], "Layer the syrup down the glass for a marbled look.", "After-school hangout table"],
    ["Sweet Grape Slush", "This sweet creation layers Black Tea over Honey for a memorable bite.", "common", ["Black Tea", "Honey", "Cream Foam"], "Blend with ice until perfectly slushy.", "Park bench"],
    ["Signature Mango Slush", "A signature specialty starring Taro Powder, paired with Ice and a hint of Tapioca Pearls.", "uncommon", ["Taro Powder", "Ice", "Tapioca Pearls"], "Top with a thick layer of cream foam.", "Study break stand"],
    ["Bubbly Honeydew Milk Tea", "Bubbly Honeydew Milk Tea, a bubbly favorite built around Fruit Puree and Coconut Jelly.", "rare", ["Fruit Puree", "Coconut Jelly", "Brown Sugar Syrup"], "Shake the tea and milk together until frothy.", "Awesome Boba counter"],
    ["Classic Mango Slush", "A classic twist on the classic, blending Honey, Cream Foam, and Milk.", "uncommon", ["Honey", "Cream Foam", "Milk"], "Cook the pearls until soft and chewy.", "Takeout window"],
    ["Frosty Lychee Tea", "Rich with Ice and finished with Black Tea for a frosty touch.", "rare", ["Ice", "Tapioca Pearls", "Black Tea"], "Layer the syrup down the glass for a marbled look.", "After-school hangout table"],
    ["Classic Honeydew Milk Tea", "This classic creation layers Coconut Jelly over Brown Sugar Syrup for a memorable bite.", "epic", ["Coconut Jelly", "Brown Sugar Syrup", "Taro Powder"], "Blend with ice until perfectly slushy.", "Park bench"],
    ["Chill Lychee Tea", "A chill specialty starring Cream Foam, paired with Milk and a hint of Fruit Puree.", "legendary", ["Cream Foam", "Milk", "Fruit Puree"], "Top with a thick layer of cream foam.", "Study break stand"],
  ],
  "shiny_boba": [
    ["Glimmering Diamond Pearl Tea", "Glimmering Diamond Pearl Tea, a glimmering favorite built around Edible Glitter and Milk.", "common", ["Edible Glitter", "Milk", "Honey"], "Swirl in the edible glitter just before sealing the cup.", "Shiny Awesome Boba counter"],
    ["Luminous Glittering Milk Tea", "A luminous twist on the classic, blending Tapioca Pearls, Fruit Puree, and Ice.", "common", ["Tapioca Pearls", "Fruit Puree", "Ice"], "Layer the colors carefully for a shimmering effect.", "VIP takeout window"],
    ["Shiny Starlight Mango Tea", "Rich with Color-Changing Syrup and finished with Shimmer Powder for a shiny touch.", "uncommon", ["Color-Changing Syrup", "Crystal Boba", "Shimmer Powder"], "Cook the crystal boba until clear and glossy.", "Sparkling display stand"],
    ["Glimmering Shimmer Taro Boba", "This glimmering creation layers Milk over Honey for a memorable bite.", "common", ["Milk", "Honey", "Cream Foam"], "Shake until the drink sparkles under the light.", "Limited-edition pickup tray"],
    ["Radiant Galaxy Slush", "A radiant specialty starring Fruit Puree, paired with Ice and a hint of Edible Glitter.", "uncommon", ["Fruit Puree", "Ice", "Edible Glitter"], "Top with shimmer powder for the finishing touch.", "Collector's corner"],
    ["Prismatic Starlight Mango Tea", "Prismatic Starlight Mango Tea, a prismatic favorite built around Crystal Boba and Shimmer Powder.", "rare", ["Crystal Boba", "Shimmer Powder", "Tapioca Pearls"], "Swirl in the edible glitter just before sealing the cup.", "Shiny Awesome Boba counter"],
    ["Rare Crystal Fruit Tea", "A rare twist on the classic, blending Honey, Cream Foam, and Color-Changing Syrup.", "uncommon", ["Honey", "Cream Foam", "Color-Changing Syrup"], "Layer the colors carefully for a shimmering effect.", "VIP takeout window"],
    ["Luminous Rainbow Jelly Tea", "Rich with Ice and finished with Milk for a luminous touch.", "rare", ["Ice", "Edible Glitter", "Milk"], "Cook the crystal boba until clear and glossy.", "Sparkling display stand"],
    ["Iridescent Sparkling Lychee Tea", "This iridescent creation layers Shimmer Powder over Tapioca Pearls for a memorable bite.", "epic", ["Shimmer Powder", "Tapioca Pearls", "Fruit Puree"], "Shake until the drink sparkles under the light.", "Limited-edition pickup tray"],
    ["Iridescent Shiny Brown Sugar Boba", "An iridescent specialty starring Cream Foam, paired with Color-Changing Syrup and a hint of Crystal Boba.", "legendary", ["Cream Foam", "Color-Changing Syrup", "Crystal Boba"], "Top with shimmer powder for the finishing touch.", "Collector's corner"],
    ["Radiant Starlight Mango Tea", "Radiant Starlight Mango Tea, a radiant favorite built around Edible Glitter and Milk.", "common", ["Edible Glitter", "Milk", "Honey"], "Swirl in the edible glitter just before sealing the cup.", "Shiny Awesome Boba counter"],
    ["Radiant Shiny Brown Sugar Boba", "A radiant twist on the classic, blending Tapioca Pearls, Fruit Puree, and Ice.", "common", ["Tapioca Pearls", "Fruit Puree", "Ice"], "Layer the colors carefully for a shimmering effect.", "VIP takeout window"],
    ["Shiny Diamond Pearl Tea", "Rich with Color-Changing Syrup and finished with Shimmer Powder for a shiny touch.", "uncommon", ["Color-Changing Syrup", "Crystal Boba", "Shimmer Powder"], "Cook the crystal boba until clear and glossy.", "Sparkling display stand"],
    ["Dazzling Starlight Mango Tea", "This dazzling creation layers Milk over Honey for a memorable bite.", "common", ["Milk", "Honey", "Cream Foam"], "Shake until the drink sparkles under the light.", "Limited-edition pickup tray"],
    ["Radiant Sparkling Lychee Tea", "A radiant specialty starring Fruit Puree, paired with Ice and a hint of Edible Glitter.", "uncommon", ["Fruit Puree", "Ice", "Edible Glitter"], "Top with shimmer powder for the finishing touch.", "Collector's corner"],
    ["Iridescent Glow Berry Slush", "Iridescent Glow Berry Slush, an iridescent favorite built around Crystal Boba and Shimmer Powder.", "rare", ["Crystal Boba", "Shimmer Powder", "Tapioca Pearls"], "Swirl in the edible glitter just before sealing the cup.", "Shiny Awesome Boba counter"],
    ["Shiny Glittering Milk Tea", "A shiny twist on the classic, blending Honey, Cream Foam, and Color-Changing Syrup.", "uncommon", ["Honey", "Cream Foam", "Color-Changing Syrup"], "Layer the colors carefully for a shimmering effect.", "VIP takeout window"],
    ["Dazzling Glittering Milk Tea", "Rich with Ice and finished with Milk for a dazzling touch.", "rare", ["Ice", "Edible Glitter", "Milk"], "Cook the crystal boba until clear and glossy.", "Sparkling display stand"],
    ["Iridescent Aurora Milk Tea", "This iridescent creation layers Shimmer Powder over Tapioca Pearls for a memorable bite.", "epic", ["Shimmer Powder", "Tapioca Pearls", "Fruit Puree"], "Shake until the drink sparkles under the light.", "Limited-edition pickup tray"],
    ["Prismatic Crystal Fruit Tea", "A prismatic specialty starring Cream Foam, paired with Color-Changing Syrup and a hint of Crystal Boba.", "legendary", ["Cream Foam", "Color-Changing Syrup", "Crystal Boba"], "Top with shimmer powder for the finishing touch.", "Collector's corner"],
    ["Luminous Shimmer Taro Boba", "Luminous Shimmer Taro Boba, a luminous favorite built around Edible Glitter and Milk.", "common", ["Edible Glitter", "Milk", "Honey"], "Swirl in the edible glitter just before sealing the cup.", "Shiny Awesome Boba counter"],
    ["Rare Comet Honeydew Tea", "A rare twist on the classic, blending Tapioca Pearls, Fruit Puree, and Ice.", "common", ["Tapioca Pearls", "Fruit Puree", "Ice"], "Layer the colors carefully for a shimmering effect.", "VIP takeout window"],
    ["Dazzling Galaxy Slush", "Rich with Color-Changing Syrup and finished with Shimmer Powder for a dazzling touch.", "uncommon", ["Color-Changing Syrup", "Crystal Boba", "Shimmer Powder"], "Cook the crystal boba until clear and glossy.", "Sparkling display stand"],
    ["Glimmering Shiny Brown Sugar Boba", "This glimmering creation layers Milk over Honey for a memorable bite.", "common", ["Milk", "Honey", "Cream Foam"], "Shake until the drink sparkles under the light.", "Limited-edition pickup tray"],
    ["Shiny Galaxy Slush", "A shiny specialty starring Fruit Puree, paired with Ice and a hint of Edible Glitter.", "uncommon", ["Fruit Puree", "Ice", "Edible Glitter"], "Top with shimmer powder for the finishing touch.", "Collector's corner"],
    ["Prismatic Rainbow Jelly Tea", "Prismatic Rainbow Jelly Tea, a prismatic favorite built around Crystal Boba and Shimmer Powder.", "rare", ["Crystal Boba", "Shimmer Powder", "Tapioca Pearls"], "Swirl in the edible glitter just before sealing the cup.", "Shiny Awesome Boba counter"],
    ["Iridescent Starlight Mango Tea", "An iridescent twist on the classic, blending Honey, Cream Foam, and Color-Changing Syrup.", "uncommon", ["Honey", "Cream Foam", "Color-Changing Syrup"], "Layer the colors carefully for a shimmering effect.", "VIP takeout window"],
    ["Shiny Rainbow Jelly Tea", "Rich with Ice and finished with Milk for a shiny touch.", "rare", ["Ice", "Edible Glitter", "Milk"], "Cook the crystal boba until clear and glossy.", "Sparkling display stand"],
    ["Radiant Glittering Milk Tea", "This radiant creation layers Shimmer Powder over Tapioca Pearls for a memorable bite.", "epic", ["Shimmer Powder", "Tapioca Pearls", "Fruit Puree"], "Shake until the drink sparkles under the light.", "Limited-edition pickup tray"],
    ["Rare Sparkling Lychee Tea", "A rare specialty starring Cream Foam, paired with Color-Changing Syrup and a hint of Crystal Boba.", "legendary", ["Cream Foam", "Color-Changing Syrup", "Crystal Boba"], "Top with shimmer powder for the finishing touch.", "Collector's corner"],
  ],
  "holiday_coffee": [
    ["Snowy Hot Chocolate Supreme", "Snowy Hot Chocolate Supreme, a snowy favorite built around Peppermint Syrup and Whipped Cream.", "common", ["Peppermint Syrup", "Whipped Cream", "Cocoa Powder"], "Steam the milk with festive spices mixed in.", "Santa's Coffee counter"],
    ["Snowy Santa's Cocoa Float", "A snowy twist on the classic, blending Gingerbread Spice, Cinnamon Stick, and Maple Syrup.", "common", ["Gingerbread Spice", "Cinnamon Stick", "Maple Syrup"], "Stir in the syrup until it swirls through the cup.", "Snowy window seat"],
    ["Spiced Cinnamon Spice Coffee", "Rich with Eggnog and finished with Marshmallows for a spiced touch.", "uncommon", ["Eggnog", "Candy Cane Bits", "Marshmallows"], "Top with whipped cream and a sprinkle of spice.", "Holiday market stall"],
    ["Winter Santa's Cocoa Float", "This winter creation layers Whipped Cream over Cocoa Powder for a memorable bite.", "common", ["Whipped Cream", "Cocoa Powder", "Nutmeg"], "Warm gently so the cocoa stays silky smooth.", "Fireplace corner table"],
    ["Cozy Santa's Cocoa Float", "A cozy specialty starring Cinnamon Stick, paired with Maple Syrup and a hint of Peppermint Syrup.", "uncommon", ["Cinnamon Stick", "Maple Syrup", "Peppermint Syrup"], "Garnish with a candy cane stirrer.", "Gift-wrapped takeout tray"],
    ["Spiced Eggnog Cappuccino", "Spiced Eggnog Cappuccino, a spiced favorite built around Candy Cane Bits and Marshmallows.", "rare", ["Candy Cane Bits", "Marshmallows", "Gingerbread Spice"], "Steam the milk with festive spices mixed in.", "Santa's Coffee counter"],
    ["Merry Gingerbread Latte", "A merry twist on the classic, blending Cocoa Powder, Nutmeg, and Eggnog.", "uncommon", ["Cocoa Powder", "Nutmeg", "Eggnog"], "Stir in the syrup until it swirls through the cup.", "Snowy window seat"],
    ["Twinkling Santa's Cocoa Float", "Rich with Maple Syrup and finished with Whipped Cream for a twinkling touch.", "rare", ["Maple Syrup", "Peppermint Syrup", "Whipped Cream"], "Top with whipped cream and a sprinkle of spice.", "Holiday market stall"],
    ["Snowy Eggnog Cappuccino", "This snowy creation layers Marshmallows over Gingerbread Spice for a memorable bite.", "epic", ["Marshmallows", "Gingerbread Spice", "Cinnamon Stick"], "Warm gently so the cocoa stays silky smooth.", "Fireplace corner table"],
    ["Winter Holly Jolly Espresso", "A winter specialty starring Nutmeg, paired with Eggnog and a hint of Candy Cane Bits.", "legendary", ["Nutmeg", "Eggnog", "Candy Cane Bits"], "Garnish with a candy cane stirrer.", "Gift-wrapped takeout tray"],
    ["Merry Hot Chocolate Supreme", "Merry Hot Chocolate Supreme, a merry favorite built around Peppermint Syrup and Whipped Cream.", "common", ["Peppermint Syrup", "Whipped Cream", "Cocoa Powder"], "Steam the milk with festive spices mixed in.", "Santa's Coffee counter"],
    ["Merry Peppermint Mocha", "A merry twist on the classic, blending Gingerbread Spice, Cinnamon Stick, and Maple Syrup.", "common", ["Gingerbread Spice", "Cinnamon Stick", "Maple Syrup"], "Stir in the syrup until it swirls through the cup.", "Snowy window seat"],
    ["Merry Frosted Sugar Cookie Latte", "Rich with Eggnog and finished with Marshmallows for a merry touch.", "uncommon", ["Eggnog", "Candy Cane Bits", "Marshmallows"], "Top with whipped cream and a sprinkle of spice.", "Holiday market stall"],
    ["Festive Cinnamon Spice Coffee", "This festive creation layers Whipped Cream over Cocoa Powder for a memorable bite.", "common", ["Whipped Cream", "Cocoa Powder", "Nutmeg"], "Warm gently so the cocoa stays silky smooth.", "Fireplace corner table"],
    ["Jolly Peppermint Mocha", "A jolly specialty starring Cinnamon Stick, paired with Maple Syrup and a hint of Peppermint Syrup.", "uncommon", ["Cinnamon Stick", "Maple Syrup", "Peppermint Syrup"], "Garnish with a candy cane stirrer.", "Gift-wrapped takeout tray"],
    ["Twinkling Eggnog Cappuccino", "Twinkling Eggnog Cappuccino, a twinkling favorite built around Candy Cane Bits and Marshmallows.", "rare", ["Candy Cane Bits", "Marshmallows", "Gingerbread Spice"], "Steam the milk with festive spices mixed in.", "Santa's Coffee counter"],
    ["Twinkling Frosted Sugar Cookie Latte", "A twinkling twist on the classic, blending Cocoa Powder, Nutmeg, and Eggnog.", "uncommon", ["Cocoa Powder", "Nutmeg", "Eggnog"], "Stir in the syrup until it swirls through the cup.", "Snowy window seat"],
    ["Jolly Cinnamon Spice Coffee", "Rich with Maple Syrup and finished with Whipped Cream for a jolly touch.", "rare", ["Maple Syrup", "Peppermint Syrup", "Whipped Cream"], "Top with whipped cream and a sprinkle of spice.", "Holiday market stall"],
    ["Cozy Frosted Sugar Cookie Latte", "This cozy creation layers Marshmallows over Gingerbread Spice for a memorable bite.", "epic", ["Marshmallows", "Gingerbread Spice", "Cinnamon Stick"], "Warm gently so the cocoa stays silky smooth.", "Fireplace corner table"],
    ["Spiced Holly Jolly Espresso", "A spiced specialty starring Nutmeg, paired with Eggnog and a hint of Candy Cane Bits.", "legendary", ["Nutmeg", "Eggnog", "Candy Cane Bits"], "Garnish with a candy cane stirrer.", "Gift-wrapped takeout tray"],
    ["Snowy Maple Pecan Latte", "Snowy Maple Pecan Latte, a snowy favorite built around Peppermint Syrup and Whipped Cream.", "common", ["Peppermint Syrup", "Whipped Cream", "Cocoa Powder"], "Steam the milk with festive spices mixed in.", "Santa's Coffee counter"],
    ["Twinkling Gingerbread Latte", "A twinkling twist on the classic, blending Gingerbread Spice, Cinnamon Stick, and Maple Syrup.", "common", ["Gingerbread Spice", "Cinnamon Stick", "Maple Syrup"], "Stir in the syrup until it swirls through the cup.", "Snowy window seat"],
    ["Spiced Maple Pecan Latte", "Rich with Eggnog and finished with Marshmallows for a spiced touch.", "uncommon", ["Eggnog", "Candy Cane Bits", "Marshmallows"], "Top with whipped cream and a sprinkle of spice.", "Holiday market stall"],
    ["Merry Eggnog Cappuccino", "This merry creation layers Whipped Cream over Cocoa Powder for a memorable bite.", "common", ["Whipped Cream", "Cocoa Powder", "Nutmeg"], "Warm gently so the cocoa stays silky smooth.", "Fireplace corner table"],
    ["Jolly Maple Pecan Latte", "A jolly specialty starring Cinnamon Stick, paired with Maple Syrup and a hint of Peppermint Syrup.", "uncommon", ["Cinnamon Stick", "Maple Syrup", "Peppermint Syrup"], "Garnish with a candy cane stirrer.", "Gift-wrapped takeout tray"],
    ["Jolly Winter Spice Cocoa", "Jolly Winter Spice Cocoa, a jolly favorite built around Candy Cane Bits and Marshmallows.", "rare", ["Candy Cane Bits", "Marshmallows", "Gingerbread Spice"], "Steam the milk with festive spices mixed in.", "Santa's Coffee counter"],
    ["Twinkling Candy Cane Cold Brew", "A twinkling twist on the classic, blending Cocoa Powder, Nutmeg, and Eggnog.", "uncommon", ["Cocoa Powder", "Nutmeg", "Eggnog"], "Stir in the syrup until it swirls through the cup.", "Snowy window seat"],
    ["Snowy Winter Spice Cocoa", "Rich with Maple Syrup and finished with Whipped Cream for a snowy touch.", "rare", ["Maple Syrup", "Peppermint Syrup", "Whipped Cream"], "Top with whipped cream and a sprinkle of spice.", "Holiday market stall"],
    ["Twinkling Peppermint Mocha", "This twinkling creation layers Marshmallows over Gingerbread Spice for a memorable bite.", "epic", ["Marshmallows", "Gingerbread Spice", "Cinnamon Stick"], "Warm gently so the cocoa stays silky smooth.", "Fireplace corner table"],
    ["Twinkling Cinnamon Spice Coffee", "A twinkling specialty starring Nutmeg, paired with Eggnog and a hint of Candy Cane Bits.", "legendary", ["Nutmeg", "Eggnog", "Candy Cane Bits"], "Garnish with a candy cane stirrer.", "Gift-wrapped takeout tray"],
  ],
  "grocery": [
    ["Everyday Bento Lunch Set", "Everyday Bento Lunch Set, an everyday favorite built around Rice Crackers and Deli Meat.", "common", ["Rice Crackers", "Deli Meat", "Bread"], "Pack everything neatly into a tidy box.", "Grocery Store checkout"],
    ["Stocked Deli Wrap", "A stocked twist on the classic, blending Fresh Fruit, Granola, and Pickles.", "common", ["Fresh Fruit", "Granola", "Pickles"], "Slice the ingredients fresh from the shelf.", "Picnic basket pickup"],
    ["Fresh Bento Lunch Set", "Rich with Sliced Cheese and finished with Trail Mix for a fresh touch.", "uncommon", ["Sliced Cheese", "Juice Box", "Trail Mix"], "Stack the items so nothing gets crushed in the bag.", "Park bench lunch spot"],
    ["Budget Granola Bar Pack", "This budget creation layers Deli Meat over Bread for a memorable bite.", "common", ["Deli Meat", "Bread", "Bottled Tea"], "Wrap it snugly for an easy grab-and-go.", "Quick grab-and-go shelf"],
    ["Handy Bento Lunch Set", "A handy specialty starring Granola, paired with Pickles and a hint of Rice Crackers.", "uncommon", ["Granola", "Pickles", "Rice Crackers"], "Arrange the tray so each snack has its place.", "Community potluck table"],
    ["Wholesome Instant Noodle Cup", "Wholesome Instant Noodle Cup, a wholesome favorite built around Juice Box and Trail Mix.", "rare", ["Juice Box", "Trail Mix", "Fresh Fruit"], "Pack everything neatly into a tidy box.", "Grocery Store checkout"],
    ["Stocked Bento Lunch Set", "A stocked twist on the classic, blending Bread, Bottled Tea, and Sliced Cheese.", "uncommon", ["Bread", "Bottled Tea", "Sliced Cheese"], "Slice the ingredients fresh from the shelf.", "Picnic basket pickup"],
    ["Stocked Juice & Snack Combo", "Rich with Pickles and finished with Deli Meat for a stocked touch.", "rare", ["Pickles", "Rice Crackers", "Deli Meat"], "Stack the items so nothing gets crushed in the bag.", "Park bench lunch spot"],
    ["Handy Granola Bar Pack", "This handy creation layers Trail Mix over Fresh Fruit for a memorable bite.", "epic", ["Trail Mix", "Fresh Fruit", "Granola"], "Wrap it snugly for an easy grab-and-go.", "Quick grab-and-go shelf"],
    ["Budget Picnic Box", "A budget specialty starring Bottled Tea, paired with Sliced Cheese and a hint of Juice Box.", "legendary", ["Bottled Tea", "Sliced Cheese", "Juice Box"], "Arrange the tray so each snack has its place.", "Community potluck table"],
    ["Everyday Trail Mix Bag", "Everyday Trail Mix Bag, an everyday favorite built around Rice Crackers and Deli Meat.", "common", ["Rice Crackers", "Deli Meat", "Bread"], "Pack everything neatly into a tidy box.", "Grocery Store checkout"],
    ["Budget Instant Noodle Cup", "A budget twist on the classic, blending Fresh Fruit, Granola, and Pickles.", "common", ["Fresh Fruit", "Granola", "Pickles"], "Slice the ingredients fresh from the shelf.", "Picnic basket pickup"],
    ["Wholesome Snack Pack", "Rich with Sliced Cheese and finished with Trail Mix for a wholesome touch.", "uncommon", ["Sliced Cheese", "Juice Box", "Trail Mix"], "Stack the items so nothing gets crushed in the bag.", "Park bench lunch spot"],
    ["Everyday Sandwich Platter", "This everyday creation layers Deli Meat over Bread for a memorable bite.", "common", ["Deli Meat", "Bread", "Bottled Tea"], "Wrap it snugly for an easy grab-and-go.", "Quick grab-and-go shelf"],
    ["Wholesome Deli Wrap", "A wholesome specialty starring Granola, paired with Pickles and a hint of Rice Crackers.", "uncommon", ["Granola", "Pickles", "Rice Crackers"], "Arrange the tray so each snack has its place.", "Community potluck table"],
    ["Wholesome Sandwich Platter", "Wholesome Sandwich Platter, a wholesome favorite built around Juice Box and Trail Mix.", "rare", ["Juice Box", "Trail Mix", "Fresh Fruit"], "Pack everything neatly into a tidy box.", "Grocery Store checkout"],
    ["Budget Sandwich Platter", "A budget twist on the classic, blending Bread, Bottled Tea, and Sliced Cheese.", "uncommon", ["Bread", "Bottled Tea", "Sliced Cheese"], "Slice the ingredients fresh from the shelf.", "Picnic basket pickup"],
    ["Handy Instant Noodle Cup", "Rich with Pickles and finished with Deli Meat for a handy touch.", "rare", ["Pickles", "Rice Crackers", "Deli Meat"], "Stack the items so nothing gets crushed in the bag.", "Park bench lunch spot"],
    ["Everyday Deli Wrap", "This everyday creation layers Trail Mix over Fresh Fruit for a memorable bite.", "epic", ["Trail Mix", "Fresh Fruit", "Granola"], "Wrap it snugly for an easy grab-and-go.", "Quick grab-and-go shelf"],
    ["Quick Granola Bar Pack", "A quick specialty starring Bottled Tea, paired with Sliced Cheese and a hint of Juice Box.", "legendary", ["Bottled Tea", "Sliced Cheese", "Juice Box"], "Arrange the tray so each snack has its place.", "Community potluck table"],
    ["Wholesome Fruit Basket", "Wholesome Fruit Basket, a wholesome favorite built around Rice Crackers and Deli Meat.", "common", ["Rice Crackers", "Deli Meat", "Bread"], "Pack everything neatly into a tidy box.", "Grocery Store checkout"],
    ["Quick Fruit Basket", "A quick twist on the classic, blending Fresh Fruit, Granola, and Pickles.", "common", ["Fresh Fruit", "Granola", "Pickles"], "Slice the ingredients fresh from the shelf.", "Picnic basket pickup"],
    ["Everyday Fruit Basket", "Rich with Sliced Cheese and finished with Trail Mix for an everyday touch.", "uncommon", ["Sliced Cheese", "Juice Box", "Trail Mix"], "Stack the items so nothing gets crushed in the bag.", "Park bench lunch spot"],
    ["Stocked Sandwich Platter", "This stocked creation layers Deli Meat over Bread for a memorable bite.", "common", ["Deli Meat", "Bread", "Bottled Tea"], "Wrap it snugly for an easy grab-and-go.", "Quick grab-and-go shelf"],
    ["Everyday Rice Cracker Mix", "An everyday specialty starring Granola, paired with Pickles and a hint of Rice Crackers.", "uncommon", ["Granola", "Pickles", "Rice Crackers"], "Arrange the tray so each snack has its place.", "Community potluck table"],
    ["Tidy Picnic Box", "Tidy Picnic Box, a tidy favorite built around Juice Box and Trail Mix.", "rare", ["Juice Box", "Trail Mix", "Fresh Fruit"], "Pack everything neatly into a tidy box.", "Grocery Store checkout"],
    ["Fresh Instant Noodle Cup", "A fresh twist on the classic, blending Bread, Bottled Tea, and Sliced Cheese.", "uncommon", ["Bread", "Bottled Tea", "Sliced Cheese"], "Slice the ingredients fresh from the shelf.", "Picnic basket pickup"],
    ["Stocked Fruit Basket", "Rich with Pickles and finished with Deli Meat for a stocked touch.", "rare", ["Pickles", "Rice Crackers", "Deli Meat"], "Stack the items so nothing gets crushed in the bag.", "Park bench lunch spot"],
    ["Everyday Snack Pack", "This everyday creation layers Trail Mix over Fresh Fruit for a memorable bite.", "epic", ["Trail Mix", "Fresh Fruit", "Granola"], "Wrap it snugly for an easy grab-and-go.", "Quick grab-and-go shelf"],
    ["Budget Snack Pack", "A budget specialty starring Bottled Tea, paired with Sliced Cheese and a hint of Juice Box.", "legendary", ["Bottled Tea", "Sliced Cheese", "Juice Box"], "Arrange the tray so each snack has its place.", "Community potluck table"],
  ],
  "lunar": [
    ["Lucky Eight Treasure Rice", "Lucky Eight Treasure Rice, a lucky favorite built around Sticky Rice and Soy Sauce.", "common", ["Sticky Rice", "Soy Sauce", "Lotus Leaf"], "Steam until the rice cake turns glossy and firm.", "Lunar New Year Feast hall"],
    ["Prosperous Lantern Cookie", "A prosperous twist on the classic, blending Red Bean Paste, Scallion, and Sesame Oil.", "common", ["Red Bean Paste", "Scallion", "Sesame Oil"], "Fold each dumpling carefully to seal in the luck.", "Family reunion table"],
    ["Festive Sticky Rice Cake", "Rich with Five-Spice and finished with Dried Mushroom for a festive touch.", "uncommon", ["Five-Spice", "Lucky Coin Charm", "Dried Mushroom"], "Arrange the tray in a circle for good fortune.", "Lantern-lit courtyard"],
    ["Golden Red Bean Bun", "This golden creation layers Soy Sauce over Lotus Leaf for a memorable bite.", "common", ["Soy Sauce", "Lotus Leaf", "Lantern Candle Wax Wrap"], "Simmer slowly to deepen the festive aroma.", "Festival market stall"],
    ["Auspicious Dumpling Platter", "An auspicious specialty starring Scallion, paired with Sesame Oil and a hint of Sticky Rice.", "uncommon", ["Scallion", "Sesame Oil", "Sticky Rice"], "Wrap and steam inside the lotus leaf.", "Red-and-gold banquet table"],
    ["Lantern-Lit Whole Steamed Fish", "Lantern-Lit Whole Steamed Fish, a lantern-lit favorite built around Lucky Coin Charm and Dried Mushroom.", "rare", ["Lucky Coin Charm", "Dried Mushroom", "Red Bean Paste"], "Steam until the rice cake turns glossy and firm.", "Lunar New Year Feast hall"],
    ["Radiant Whole Steamed Fish", "A radiant twist on the classic, blending Lotus Leaf, Lantern Candle Wax Wrap, and Five-Spice.", "uncommon", ["Lotus Leaf", "Lantern Candle Wax Wrap", "Five-Spice"], "Fold each dumpling carefully to seal in the luck.", "Family reunion table"],
    ["Grand Red Bean Bun", "Rich with Sesame Oil and finished with Soy Sauce for a grand touch.", "rare", ["Sesame Oil", "Sticky Rice", "Soy Sauce"], "Arrange the tray in a circle for good fortune.", "Lantern-lit courtyard"],
    ["Lucky Nian Gao", "This lucky creation layers Dried Mushroom over Red Bean Paste for a memorable bite.", "epic", ["Dried Mushroom", "Red Bean Paste", "Scallion"], "Simmer slowly to deepen the festive aroma.", "Festival market stall"],
    ["Lantern-Lit Golden Coin Pastry", "A lantern-lit specialty starring Lantern Candle Wax Wrap, paired with Five-Spice and a hint of Lucky Coin Charm.", "legendary", ["Lantern Candle Wax Wrap", "Five-Spice", "Lucky Coin Charm"], "Wrap and steam inside the lotus leaf.", "Red-and-gold banquet table"],
    ["Festive Spring Rolls", "Festive Spring Rolls, a festive favorite built around Sticky Rice and Soy Sauce.", "common", ["Sticky Rice", "Soy Sauce", "Lotus Leaf"], "Steam until the rice cake turns glossy and firm.", "Lunar New Year Feast hall"],
    ["Golden Festival Hot Pot", "A golden twist on the classic, blending Red Bean Paste, Scallion, and Sesame Oil.", "common", ["Red Bean Paste", "Scallion", "Sesame Oil"], "Fold each dumpling carefully to seal in the luck.", "Family reunion table"],
    ["Prosperous Longevity Noodles", "Rich with Five-Spice and finished with Dried Mushroom for a prosperous touch.", "uncommon", ["Five-Spice", "Lucky Coin Charm", "Dried Mushroom"], "Arrange the tray in a circle for good fortune.", "Lantern-lit courtyard"],
    ["Radiant Longevity Noodles", "This radiant creation layers Soy Sauce over Lotus Leaf for a memorable bite.", "common", ["Soy Sauce", "Lotus Leaf", "Lantern Candle Wax Wrap"], "Simmer slowly to deepen the festive aroma.", "Festival market stall"],
    ["Festive Longevity Noodles", "A festive specialty starring Scallion, paired with Sesame Oil and a hint of Sticky Rice.", "uncommon", ["Scallion", "Sesame Oil", "Sticky Rice"], "Wrap and steam inside the lotus leaf.", "Red-and-gold banquet table"],
    ["Radiant Dumpling Platter", "Radiant Dumpling Platter, a radiant favorite built around Lucky Coin Charm and Dried Mushroom.", "rare", ["Lucky Coin Charm", "Dried Mushroom", "Red Bean Paste"], "Steam until the rice cake turns glossy and firm.", "Lunar New Year Feast hall"],
    ["Lantern-Lit Nian Gao", "A lantern-lit twist on the classic, blending Lotus Leaf, Lantern Candle Wax Wrap, and Five-Spice.", "uncommon", ["Lotus Leaf", "Lantern Candle Wax Wrap", "Five-Spice"], "Fold each dumpling carefully to seal in the luck.", "Family reunion table"],
    ["Auspicious Sticky Rice Cake", "Rich with Sesame Oil and finished with Soy Sauce for an auspicious touch.", "rare", ["Sesame Oil", "Sticky Rice", "Soy Sauce"], "Arrange the tray in a circle for good fortune.", "Lantern-lit courtyard"],
    ["Radiant Lantern Cookie", "This radiant creation layers Dried Mushroom over Red Bean Paste for a memorable bite.", "epic", ["Dried Mushroom", "Red Bean Paste", "Scallion"], "Simmer slowly to deepen the festive aroma.", "Festival market stall"],
    ["Grand Whole Steamed Fish", "A grand specialty starring Lantern Candle Wax Wrap, paired with Five-Spice and a hint of Lucky Coin Charm.", "legendary", ["Lantern Candle Wax Wrap", "Five-Spice", "Lucky Coin Charm"], "Wrap and steam inside the lotus leaf.", "Red-and-gold banquet table"],
    ["Auspicious Spring Rolls", "Auspicious Spring Rolls, an auspicious favorite built around Sticky Rice and Soy Sauce.", "common", ["Sticky Rice", "Soy Sauce", "Lotus Leaf"], "Steam until the rice cake turns glossy and firm.", "Lunar New Year Feast hall"],
    ["Prosperous Sticky Rice Cake", "A prosperous twist on the classic, blending Red Bean Paste, Scallion, and Sesame Oil.", "common", ["Red Bean Paste", "Scallion", "Sesame Oil"], "Fold each dumpling carefully to seal in the luck.", "Family reunion table"],
    ["Grand Spring Rolls", "Rich with Five-Spice and finished with Dried Mushroom for a grand touch.", "uncommon", ["Five-Spice", "Lucky Coin Charm", "Dried Mushroom"], "Arrange the tray in a circle for good fortune.", "Lantern-lit courtyard"],
    ["Prosperous Lucky Orange Tray", "This prosperous creation layers Soy Sauce over Lotus Leaf for a memorable bite.", "common", ["Soy Sauce", "Lotus Leaf", "Lantern Candle Wax Wrap"], "Simmer slowly to deepen the festive aroma.", "Festival market stall"],
    ["Lucky Golden Coin Pastry", "A lucky specialty starring Scallion, paired with Sesame Oil and a hint of Sticky Rice.", "uncommon", ["Scallion", "Sesame Oil", "Sticky Rice"], "Wrap and steam inside the lotus leaf.", "Red-and-gold banquet table"],
    ["Prosperous Whole Steamed Fish", "Prosperous Whole Steamed Fish, a prosperous favorite built around Lucky Coin Charm and Dried Mushroom.", "rare", ["Lucky Coin Charm", "Dried Mushroom", "Red Bean Paste"], "Steam until the rice cake turns glossy and firm.", "Lunar New Year Feast hall"],
    ["Radiant Sticky Rice Cake", "A radiant twist on the classic, blending Lotus Leaf, Lantern Candle Wax Wrap, and Five-Spice.", "uncommon", ["Lotus Leaf", "Lantern Candle Wax Wrap", "Five-Spice"], "Fold each dumpling carefully to seal in the luck.", "Family reunion table"],
    ["Festive Eight Treasure Rice", "Rich with Sesame Oil and finished with Soy Sauce for a festive touch.", "rare", ["Sesame Oil", "Sticky Rice", "Soy Sauce"], "Arrange the tray in a circle for good fortune.", "Lantern-lit courtyard"],
    ["Prosperous Nian Gao", "This prosperous creation layers Dried Mushroom over Red Bean Paste for a memorable bite.", "epic", ["Dried Mushroom", "Red Bean Paste", "Scallion"], "Simmer slowly to deepen the festive aroma.", "Festival market stall"],
    ["Lantern-Lit Spring Rolls", "A lantern-lit specialty starring Lantern Candle Wax Wrap, paired with Five-Spice and a hint of Lucky Coin Charm.", "legendary", ["Lantern Candle Wax Wrap", "Five-Spice", "Lucky Coin Charm"], "Wrap and steam inside the lotus leaf.", "Red-and-gold banquet table"],
  ],
  "astro": [
    ["Celestial Cosmic Dumpling", "Celestial Cosmic Dumpling, a celestial favorite built around Star Rice and Comet Shard.", "common", ["Star Rice", "Comet Shard", "Nebula Jelly"], "Swirl the toppings into a bright nebula pattern.", "Astronigiri observation deck"],
    ["Galactic Lunar Crater Cookie", "A galactic twist on the classic, blending Seaweed Dust, Star Piece, and Solar Citrus Zest.", "common", ["Seaweed Dust", "Star Piece", "Solar Citrus Zest"], "Plate it under the observation deck lights for full effect.", "Orbital snack bar"],
    ["Stellar Asteroid Popcorn", "Rich with Crystal Sauce and finished with Meteor Pepper Flake for a stellar touch.", "uncommon", ["Crystal Sauce", "Moon Cheese Curd", "Meteor Pepper Flake"], "Layer the ingredients to mimic a starfield.", "Space station galley"],
    ["Nebular Cosmic Dumpling", "This nebular creation layers Comet Shard over Nebula Jelly for a memorable bite.", "common", ["Comet Shard", "Nebula Jelly", "Zero-Gravity Foam"], "Chill until it sparkles like distant stars.", "Stargazing lounge"],
    ["Orbital Stardust Parfait", "An orbital specialty starring Star Piece, paired with Solar Citrus Zest and a hint of Star Rice.", "uncommon", ["Star Piece", "Solar Citrus Zest", "Star Rice"], "Assemble carefully so nothing floats away in zero gravity.", "Docking bay canteen"],
    ["Celestial Solar Flare Skewer", "Celestial Solar Flare Skewer, a celestial favorite built around Moon Cheese Curd and Meteor Pepper Flake.", "rare", ["Moon Cheese Curd", "Meteor Pepper Flake", "Seaweed Dust"], "Swirl the toppings into a bright nebula pattern.", "Astronigiri observation deck"],
    ["Astral Cosmic Dumpling", "An astral twist on the classic, blending Nebula Jelly, Zero-Gravity Foam, and Crystal Sauce.", "uncommon", ["Nebula Jelly", "Zero-Gravity Foam", "Crystal Sauce"], "Plate it under the observation deck lights for full effect.", "Orbital snack bar"],
    ["Orbital Black Hole Brownie", "Rich with Solar Citrus Zest and finished with Comet Shard for an orbital touch.", "rare", ["Solar Citrus Zest", "Star Rice", "Comet Shard"], "Layer the ingredients to mimic a starfield.", "Space station galley"],
    ["Orbital Galaxy Ramen", "This orbital creation layers Meteor Pepper Flake over Seaweed Dust for a memorable bite.", "epic", ["Meteor Pepper Flake", "Seaweed Dust", "Star Piece"], "Chill until it sparkles like distant stars.", "Stargazing lounge"],
    ["Stellar Orbit Onigiri", "A stellar specialty starring Zero-Gravity Foam, paired with Crystal Sauce and a hint of Moon Cheese Curd.", "legendary", ["Zero-Gravity Foam", "Crystal Sauce", "Moon Cheese Curd"], "Assemble carefully so nothing floats away in zero gravity.", "Docking bay canteen"],
    ["Interstellar Solar Flare Skewer", "Interstellar Solar Flare Skewer, an interstellar favorite built around Star Rice and Comet Shard.", "common", ["Star Rice", "Comet Shard", "Nebula Jelly"], "Swirl the toppings into a bright nebula pattern.", "Astronigiri observation deck"],
    ["Stellar Meteor Mochi", "A stellar twist on the classic, blending Seaweed Dust, Star Piece, and Solar Citrus Zest.", "common", ["Seaweed Dust", "Star Piece", "Solar Citrus Zest"], "Plate it under the observation deck lights for full effect.", "Orbital snack bar"],
    ["Interstellar Asteroid Popcorn", "Rich with Crystal Sauce and finished with Meteor Pepper Flake for an interstellar touch.", "uncommon", ["Crystal Sauce", "Moon Cheese Curd", "Meteor Pepper Flake"], "Layer the ingredients to mimic a starfield.", "Space station galley"],
    ["Cosmic Meteor Mochi", "This cosmic creation layers Comet Shard over Nebula Jelly for a memorable bite.", "common", ["Comet Shard", "Nebula Jelly", "Zero-Gravity Foam"], "Chill until it sparkles like distant stars.", "Stargazing lounge"],
    ["Nebular Galaxy Ramen", "A nebular specialty starring Star Piece, paired with Solar Citrus Zest and a hint of Star Rice.", "uncommon", ["Star Piece", "Solar Citrus Zest", "Star Rice"], "Assemble carefully so nothing floats away in zero gravity.", "Docking bay canteen"],
    ["Galactic Nova Noodle Bowl", "Galactic Nova Noodle Bowl, a galactic favorite built around Moon Cheese Curd and Meteor Pepper Flake.", "rare", ["Moon Cheese Curd", "Meteor Pepper Flake", "Seaweed Dust"], "Swirl the toppings into a bright nebula pattern.", "Astronigiri observation deck"],
    ["Galactic Stardust Parfait", "A galactic twist on the classic, blending Nebula Jelly, Zero-Gravity Foam, and Crystal Sauce.", "uncommon", ["Nebula Jelly", "Zero-Gravity Foam", "Crystal Sauce"], "Plate it under the observation deck lights for full effect.", "Orbital snack bar"],
    ["Galactic Star Rice Nebula", "Rich with Solar Citrus Zest and finished with Comet Shard for a galactic touch.", "rare", ["Solar Citrus Zest", "Star Rice", "Comet Shard"], "Layer the ingredients to mimic a starfield.", "Space station galley"],
    ["Interstellar Stardust Parfait", "This interstellar creation layers Meteor Pepper Flake over Seaweed Dust for a memorable bite.", "epic", ["Meteor Pepper Flake", "Seaweed Dust", "Star Piece"], "Chill until it sparkles like distant stars.", "Stargazing lounge"],
    ["Nebular Solar Flare Skewer", "A nebular specialty starring Zero-Gravity Foam, paired with Crystal Sauce and a hint of Moon Cheese Curd.", "legendary", ["Zero-Gravity Foam", "Crystal Sauce", "Moon Cheese Curd"], "Assemble carefully so nothing floats away in zero gravity.", "Docking bay canteen"],
    ["Galactic Orbit Onigiri", "Galactic Orbit Onigiri, a galactic favorite built around Star Rice and Comet Shard.", "common", ["Star Rice", "Comet Shard", "Nebula Jelly"], "Swirl the toppings into a bright nebula pattern.", "Astronigiri observation deck"],
    ["Astral Asteroid Popcorn", "An astral twist on the classic, blending Seaweed Dust, Star Piece, and Solar Citrus Zest.", "common", ["Seaweed Dust", "Star Piece", "Solar Citrus Zest"], "Plate it under the observation deck lights for full effect.", "Orbital snack bar"],
    ["Orbital Orbit Onigiri", "Rich with Crystal Sauce and finished with Meteor Pepper Flake for an orbital touch.", "uncommon", ["Crystal Sauce", "Moon Cheese Curd", "Meteor Pepper Flake"], "Layer the ingredients to mimic a starfield.", "Space station galley"],
    ["Celestial Stardust Parfait", "This celestial creation layers Comet Shard over Nebula Jelly for a memorable bite.", "common", ["Comet Shard", "Nebula Jelly", "Zero-Gravity Foam"], "Chill until it sparkles like distant stars.", "Stargazing lounge"],
    ["Cosmic Nova Noodle Bowl", "A cosmic specialty starring Star Piece, paired with Solar Citrus Zest and a hint of Star Rice.", "uncommon", ["Star Piece", "Solar Citrus Zest", "Star Rice"], "Assemble carefully so nothing floats away in zero gravity.", "Docking bay canteen"],
    ["Celestial Nova Noodle Bowl", "Celestial Nova Noodle Bowl, a celestial favorite built around Moon Cheese Curd and Meteor Pepper Flake.", "rare", ["Moon Cheese Curd", "Meteor Pepper Flake", "Seaweed Dust"], "Swirl the toppings into a bright nebula pattern.", "Astronigiri observation deck"],
    ["Astral Nova Noodle Bowl", "An astral twist on the classic, blending Nebula Jelly, Zero-Gravity Foam, and Crystal Sauce.", "uncommon", ["Nebula Jelly", "Zero-Gravity Foam", "Crystal Sauce"], "Plate it under the observation deck lights for full effect.", "Orbital snack bar"],
    ["Nebular Comet Sushi Roll", "Rich with Solar Citrus Zest and finished with Comet Shard for a nebular touch.", "rare", ["Solar Citrus Zest", "Star Rice", "Comet Shard"], "Layer the ingredients to mimic a starfield.", "Space station galley"],
    ["Orbital Cosmic Dumpling", "This orbital creation layers Meteor Pepper Flake over Seaweed Dust for a memorable bite.", "epic", ["Meteor Pepper Flake", "Seaweed Dust", "Star Piece"], "Chill until it sparkles like distant stars.", "Stargazing lounge"],
    ["Nebular Stardust Parfait", "A nebular specialty starring Zero-Gravity Foam, paired with Crystal Sauce and a hint of Moon Cheese Curd.", "legendary", ["Zero-Gravity Foam", "Crystal Sauce", "Moon Cheese Curd"], "Assemble carefully so nothing floats away in zero gravity.", "Docking bay canteen"],
  ],
  "poke": [
    ["Legendary Friendship Berry Tart", "Legendary Friendship Berry Tart, a legendary favorite built around Comet Shard and Egg.", "common", ["Comet Shard", "Egg", "Battle Snack Bar"], "Plate it the way a trainer would prep for a big battle.", "Onigimon Mart counter"],
    ["Trainer's Evolution Stone Soup", "A trainer's twist on the classic, blending Star Piece, Rice, and Evolution Crystal Dust.", "common", ["Star Piece", "Rice", "Evolution Crystal Dust"], "Mix carefully so the berries don't lose their shine.", "Trainer's rest stop"],
    ["Legendary Trainer's Bento", "Rich with Onigimon Berry and finished with Capture Net Fiber for a legendary touch.", "uncommon", ["Onigimon Berry", "Friendship Treat", "Capture Net Fiber"], "Simmer until the broth glows faintly like a Comet Shard.", "Gym battle lobby"],
    ["Wild Legendary Den Hot Pot", "This wild creation layers Egg over Battle Snack Bar for a memorable bite.", "common", ["Egg", "Battle Snack Bar", "Gym Badge Garnish"], "Skewer and grill until perfectly evolved in flavor.", "Friendship festival booth"],
    ["Evolved Evolution Stone Soup", "An evolved specialty starring Rice, paired with Evolution Crystal Dust and a hint of Comet Shard.", "uncommon", ["Rice", "Evolution Crystal Dust", "Comet Shard"], "Arrange in a circle like a Gym battle formation.", "Evolution lab snack bar"],
    ["Wild Star Piece Salad", "Wild Star Piece Salad, a wild favorite built around Friendship Treat and Capture Net Fiber.", "rare", ["Friendship Treat", "Capture Net Fiber", "Star Piece"], "Plate it the way a trainer would prep for a big battle.", "Onigimon Mart counter"],
    ["Evolved Badge Cookie Set", "An evolved twist on the classic, blending Battle Snack Bar, Gym Badge Garnish, and Onigimon Berry.", "uncommon", ["Battle Snack Bar", "Gym Badge Garnish", "Onigimon Berry"], "Mix carefully so the berries don't lose their shine.", "Trainer's rest stop"],
    ["Wild Friendship Berry Tart", "Rich with Evolution Crystal Dust and finished with Egg for a wild touch.", "rare", ["Evolution Crystal Dust", "Comet Shard", "Egg"], "Simmer until the broth glows faintly like a Comet Shard.", "Gym battle lobby"],
    ["Legendary Badge Cookie Set", "This legendary creation layers Capture Net Fiber over Star Piece for a memorable bite.", "epic", ["Capture Net Fiber", "Star Piece", "Rice"], "Skewer and grill until perfectly evolved in flavor.", "Friendship festival booth"],
    ["Evolved Comet Shard Stew", "An evolved specialty starring Gym Badge Garnish, paired with Onigimon Berry and a hint of Friendship Treat.", "legendary", ["Gym Badge Garnish", "Onigimon Berry", "Friendship Treat"], "Arrange in a circle like a Gym battle formation.", "Evolution lab snack bar"],
    ["Rare Onigimon Treat Skewer", "Rare Onigimon Treat Skewer, a rare favorite built around Comet Shard and Egg.", "common", ["Comet Shard", "Egg", "Battle Snack Bar"], "Plate it the way a trainer would prep for a big battle.", "Onigimon Mart counter"],
    ["Evolved Friendship Berry Tart", "An evolved twist on the classic, blending Star Piece, Rice, and Evolution Crystal Dust.", "common", ["Star Piece", "Rice", "Evolution Crystal Dust"], "Mix carefully so the berries don't lose their shine.", "Trainer's rest stop"],
    ["Champion Badge Cookie Set", "Rich with Onigimon Berry and finished with Capture Net Fiber for a champion touch.", "uncommon", ["Onigimon Berry", "Friendship Treat", "Capture Net Fiber"], "Simmer until the broth glows faintly like a Comet Shard.", "Gym battle lobby"],
    ["Wild Onigimon Treat Skewer", "This wild creation layers Egg over Battle Snack Bar for a memorable bite.", "common", ["Egg", "Battle Snack Bar", "Gym Badge Garnish"], "Skewer and grill until perfectly evolved in flavor.", "Friendship festival booth"],
    ["Wild Capture Net Noodles", "A wild specialty starring Rice, paired with Evolution Crystal Dust and a hint of Comet Shard.", "uncommon", ["Rice", "Evolution Crystal Dust", "Comet Shard"], "Arrange in a circle like a Gym battle formation.", "Evolution lab snack bar"],
    ["Trainer's Star Piece Salad", "Trainer's Star Piece Salad, a trainer's favorite built around Friendship Treat and Capture Net Fiber.", "rare", ["Friendship Treat", "Capture Net Fiber", "Star Piece"], "Plate it the way a trainer would prep for a big battle.", "Onigimon Mart counter"],
    ["Rare Capture Net Noodles", "A rare twist on the classic, blending Battle Snack Bar, Gym Badge Garnish, and Onigimon Berry.", "uncommon", ["Battle Snack Bar", "Gym Badge Garnish", "Onigimon Berry"], "Mix carefully so the berries don't lose their shine.", "Trainer's rest stop"],
    ["Rare Trainer's Bento", "Rich with Evolution Crystal Dust and finished with Egg for a rare touch.", "rare", ["Evolution Crystal Dust", "Comet Shard", "Egg"], "Simmer until the broth glows faintly like a Comet Shard.", "Gym battle lobby"],
    ["Trainer's Comet Shard Stew", "This trainer's creation layers Capture Net Fiber over Star Piece for a memorable bite.", "epic", ["Capture Net Fiber", "Star Piece", "Rice"], "Skewer and grill until perfectly evolved in flavor.", "Friendship festival booth"],
    ["Friendly Trainer's Bento", "A friendly specialty starring Gym Badge Garnish, paired with Onigimon Berry and a hint of Friendship Treat.", "legendary", ["Gym Badge Garnish", "Onigimon Berry", "Friendship Treat"], "Arrange in a circle like a Gym battle formation.", "Evolution lab snack bar"],
    ["Rare Comet Shard Stew", "Rare Comet Shard Stew, a rare favorite built around Comet Shard and Egg.", "common", ["Comet Shard", "Egg", "Battle Snack Bar"], "Plate it the way a trainer would prep for a big battle.", "Onigimon Mart counter"],
    ["Champion Evolution Stone Soup", "A champion twist on the classic, blending Star Piece, Rice, and Evolution Crystal Dust.", "common", ["Star Piece", "Rice", "Evolution Crystal Dust"], "Mix carefully so the berries don't lose their shine.", "Trainer's rest stop"],
    ["Friendly Legendary Den Hot Pot", "Rich with Onigimon Berry and finished with Capture Net Fiber for a friendly touch.", "uncommon", ["Onigimon Berry", "Friendship Treat", "Capture Net Fiber"], "Simmer until the broth glows faintly like a Comet Shard.", "Gym battle lobby"],
    ["Shiny Star Piece Salad", "This shiny creation layers Egg over Battle Snack Bar for a memorable bite.", "common", ["Egg", "Battle Snack Bar", "Gym Badge Garnish"], "Skewer and grill until perfectly evolved in flavor.", "Friendship festival booth"],
    ["Trainer's Gym Battle Bento", "A trainer's specialty starring Rice, paired with Evolution Crystal Dust and a hint of Comet Shard.", "uncommon", ["Rice", "Evolution Crystal Dust", "Comet Shard"], "Arrange in a circle like a Gym battle formation.", "Evolution lab snack bar"],
    ["Trainer's Friendship Berry Tart", "Trainer's Friendship Berry Tart, a trainer's favorite built around Friendship Treat and Capture Net Fiber.", "rare", ["Friendship Treat", "Capture Net Fiber", "Star Piece"], "Plate it the way a trainer would prep for a big battle.", "Onigimon Mart counter"],
    ["Evolved Onigimon Treat Skewer", "An evolved twist on the classic, blending Battle Snack Bar, Gym Badge Garnish, and Onigimon Berry.", "uncommon", ["Battle Snack Bar", "Gym Badge Garnish", "Onigimon Berry"], "Mix carefully so the berries don't lose their shine.", "Trainer's rest stop"],
    ["Rare Badge Cookie Set", "Rich with Evolution Crystal Dust and finished with Egg for a rare touch.", "rare", ["Evolution Crystal Dust", "Comet Shard", "Egg"], "Simmer until the broth glows faintly like a Comet Shard.", "Gym battle lobby"],
    ["Wild Badge Cookie Set", "This wild creation layers Capture Net Fiber over Star Piece for a memorable bite.", "epic", ["Capture Net Fiber", "Star Piece", "Rice"], "Skewer and grill until perfectly evolved in flavor.", "Friendship festival booth"],
    ["Champion Star Piece Salad", "A champion specialty starring Gym Badge Garnish, paired with Onigimon Berry and a hint of Friendship Treat.", "legendary", ["Gym Badge Garnish", "Onigimon Berry", "Friendship Treat"], "Arrange in a circle like a Gym battle formation.", "Evolution lab snack bar"],
  ],
  "wizard": [
    ["Enchanted Star Dust Pastry", "Enchanted Star Dust Pastry, an enchanted favorite built around Potion Ink and Enchanted Herb.", "common", ["Potion Ink", "Enchanted Herb", "Star Dust"], "Stir the cauldron three times clockwise before serving.", "Wizard Shop counter"],
    ["Ancient Spellbound Tart", "An ancient twist on the classic, blending Phoenix Feather, Dragon Scale, and Cauldron Brew.", "common", ["Phoenix Feather", "Dragon Scale", "Cauldron Brew"], "Let the brew bubble until it glows faintly.", "Enchanted back room"],
    ["Magical Dragon Scale Crisp", "Rich with Moonstone Dust and finished with Spell Scroll Paper for a magical touch.", "uncommon", ["Moonstone Dust", "Crystal Shard", "Spell Scroll Paper"], "Fold the spell scroll gently around the filling.", "Spellcaster's table"],
    ["Ancient Bubbling Potion Brew", "This ancient creation layers Enchanted Herb over Star Dust for a memorable bite.", "common", ["Enchanted Herb", "Star Dust", "Wand Wood Shaving"], "Sprinkle star dust right before it's served.", "Mystic market stall"],
    ["Arcane Phoenix Feather Tonic", "An arcane specialty starring Dragon Scale, paired with Cauldron Brew and a hint of Potion Ink.", "uncommon", ["Dragon Scale", "Cauldron Brew", "Potion Ink"], "Simmer slowly under candlelight for the full effect.", "Candlelit study nook"],
    ["Arcane Cauldron Stew", "Arcane Cauldron Stew, an arcane favorite built around Crystal Shard and Spell Scroll Paper.", "rare", ["Crystal Shard", "Spell Scroll Paper", "Phoenix Feather"], "Stir the cauldron three times clockwise before serving.", "Wizard Shop counter"],
    ["Glowing Witch's Brew Float", "A glowing twist on the classic, blending Star Dust, Wand Wood Shaving, and Moonstone Dust.", "uncommon", ["Star Dust", "Wand Wood Shaving", "Moonstone Dust"], "Let the brew bubble until it glows faintly.", "Enchanted back room"],
    ["Magical Mystic Scroll Wrap", "Rich with Cauldron Brew and finished with Enchanted Herb for a magical touch.", "rare", ["Cauldron Brew", "Potion Ink", "Enchanted Herb"], "Fold the spell scroll gently around the filling.", "Spellcaster's table"],
    ["Magical Witch's Brew Float", "This magical creation layers Spell Scroll Paper over Phoenix Feather for a memorable bite.", "epic", ["Spell Scroll Paper", "Phoenix Feather", "Dragon Scale"], "Sprinkle star dust right before it's served.", "Mystic market stall"],
    ["Mystic Cauldron Stew", "A mystic specialty starring Wand Wood Shaving, paired with Moonstone Dust and a hint of Crystal Shard.", "legendary", ["Wand Wood Shaving", "Moonstone Dust", "Crystal Shard"], "Simmer slowly under candlelight for the full effect.", "Candlelit study nook"],
    ["Spellbound Witch's Brew Float", "Spellbound Witch's Brew Float, a spellbound favorite built around Potion Ink and Enchanted Herb.", "common", ["Potion Ink", "Enchanted Herb", "Star Dust"], "Stir the cauldron three times clockwise before serving.", "Wizard Shop counter"],
    ["Bewitched Enchanted Herb Soup", "A bewitched twist on the classic, blending Phoenix Feather, Dragon Scale, and Cauldron Brew.", "common", ["Phoenix Feather", "Dragon Scale", "Cauldron Brew"], "Let the brew bubble until it glows faintly.", "Enchanted back room"],
    ["Spellbound Star Dust Pastry", "Rich with Moonstone Dust and finished with Spell Scroll Paper for a spellbound touch.", "uncommon", ["Moonstone Dust", "Crystal Shard", "Spell Scroll Paper"], "Fold the spell scroll gently around the filling.", "Spellcaster's table"],
    ["Bewitched Cauldron Stew", "This bewitched creation layers Enchanted Herb over Star Dust for a memorable bite.", "common", ["Enchanted Herb", "Star Dust", "Wand Wood Shaving"], "Sprinkle star dust right before it's served.", "Mystic market stall"],
    ["Ancient Phoenix Feather Tonic", "An ancient specialty starring Dragon Scale, paired with Cauldron Brew and a hint of Potion Ink.", "uncommon", ["Dragon Scale", "Cauldron Brew", "Potion Ink"], "Simmer slowly under candlelight for the full effect.", "Candlelit study nook"],
    ["Ancient Witch's Brew Float", "Ancient Witch's Brew Float, an ancient favorite built around Crystal Shard and Spell Scroll Paper.", "rare", ["Crystal Shard", "Spell Scroll Paper", "Phoenix Feather"], "Stir the cauldron three times clockwise before serving.", "Wizard Shop counter"],
    ["Magical Crystal Shard Candy", "A magical twist on the classic, blending Star Dust, Wand Wood Shaving, and Moonstone Dust.", "uncommon", ["Star Dust", "Wand Wood Shaving", "Moonstone Dust"], "Let the brew bubble until it glows faintly.", "Enchanted back room"],
    ["Bewitched Spellbound Tart", "Rich with Cauldron Brew and finished with Enchanted Herb for a bewitched touch.", "rare", ["Cauldron Brew", "Potion Ink", "Enchanted Herb"], "Fold the spell scroll gently around the filling.", "Spellcaster's table"],
    ["Mystic Phoenix Feather Tonic", "This mystic creation layers Spell Scroll Paper over Phoenix Feather for a memorable bite.", "epic", ["Spell Scroll Paper", "Phoenix Feather", "Dragon Scale"], "Sprinkle star dust right before it's served.", "Mystic market stall"],
    ["Mystic Enchanted Herb Soup", "A mystic specialty starring Wand Wood Shaving, paired with Moonstone Dust and a hint of Crystal Shard.", "legendary", ["Wand Wood Shaving", "Moonstone Dust", "Crystal Shard"], "Simmer slowly under candlelight for the full effect.", "Candlelit study nook"],
    ["Spellbound Dragon Scale Crisp", "Spellbound Dragon Scale Crisp, a spellbound favorite built around Potion Ink and Enchanted Herb.", "common", ["Potion Ink", "Enchanted Herb", "Star Dust"], "Stir the cauldron three times clockwise before serving.", "Wizard Shop counter"],
    ["Enchanted Moonlit Spell Cookie", "An enchanted twist on the classic, blending Phoenix Feather, Dragon Scale, and Cauldron Brew.", "common", ["Phoenix Feather", "Dragon Scale", "Cauldron Brew"], "Let the brew bubble until it glows faintly.", "Enchanted back room"],
    ["Glowing Star Dust Pastry", "Rich with Moonstone Dust and finished with Spell Scroll Paper for a glowing touch.", "uncommon", ["Moonstone Dust", "Crystal Shard", "Spell Scroll Paper"], "Fold the spell scroll gently around the filling.", "Spellcaster's table"],
    ["Enchanted Crystal Shard Candy", "This enchanted creation layers Enchanted Herb over Star Dust for a memorable bite.", "common", ["Enchanted Herb", "Star Dust", "Wand Wood Shaving"], "Sprinkle star dust right before it's served.", "Mystic market stall"],
    ["Spellbound Moonlit Spell Cookie", "A spellbound specialty starring Dragon Scale, paired with Cauldron Brew and a hint of Potion Ink.", "uncommon", ["Dragon Scale", "Cauldron Brew", "Potion Ink"], "Simmer slowly under candlelight for the full effect.", "Candlelit study nook"],
    ["Spellbound Bubbling Potion Brew", "Spellbound Bubbling Potion Brew, a spellbound favorite built around Crystal Shard and Spell Scroll Paper.", "rare", ["Crystal Shard", "Spell Scroll Paper", "Phoenix Feather"], "Stir the cauldron three times clockwise before serving.", "Wizard Shop counter"],
    ["Mystic Dragon Scale Crisp", "A mystic twist on the classic, blending Star Dust, Wand Wood Shaving, and Moonstone Dust.", "uncommon", ["Star Dust", "Wand Wood Shaving", "Moonstone Dust"], "Let the brew bubble until it glows faintly.", "Enchanted back room"],
    ["Arcane Star Dust Pastry", "Rich with Cauldron Brew and finished with Enchanted Herb for an arcane touch.", "rare", ["Cauldron Brew", "Potion Ink", "Enchanted Herb"], "Fold the spell scroll gently around the filling.", "Spellcaster's table"],
    ["Arcane Spellbound Tart", "This arcane creation layers Spell Scroll Paper over Phoenix Feather for a memorable bite.", "epic", ["Spell Scroll Paper", "Phoenix Feather", "Dragon Scale"], "Sprinkle star dust right before it's served.", "Mystic market stall"],
    ["Arcane Crystal Shard Candy", "An arcane specialty starring Wand Wood Shaving, paired with Moonstone Dust and a hint of Crystal Shard.", "legendary", ["Wand Wood Shaving", "Moonstone Dust", "Crystal Shard"], "Simmer slowly under candlelight for the full effect.", "Candlelit study nook"],
  ],
  "lab": [
    ["Calibrated Beaker Berry Fizz", "Calibrated Beaker Berry Fizz, a calibrated favorite built around Test Tube Broth and Chemical Compound Drizzle.", "common", ["Test Tube Broth", "Chemical Compound Drizzle", "DNA Strand Noodle"], "Measure each ingredient precisely before mixing.", "OnigiLab counter"],
    ["Analytical Bubbling Test-Tube Tea", "An analytical twist on the classic, blending Beaker Berry, Petri Dish Jelly, and Microscope Slide Cracker.", "common", ["Beaker Berry", "Petri Dish Jelly", "Microscope Slide Cracker"], "Heat gently over a low Bunsen flame.", "Research bench"],
    ["Calibrated Reaction Flask Smoothie", "Rich with Lab Goggle Garnish and finished with Formula Fizz Powder for a calibrated touch.", "uncommon", ["Lab Goggle Garnish", "Bunsen Flame Char", "Formula Fizz Powder"], "Stir until the reaction turns a satisfying color.", "Sample collection tray"],
    ["Lab-Grade Genome Noodle Bowl", "This lab-grade creation layers Chemical Compound Drizzle over DNA Strand Noodle for a memorable bite.", "common", ["Chemical Compound Drizzle", "DNA Strand Noodle", "Specimen Jar Cream"], "Let it culture briefly before plating.", "Observation window"],
    ["Analytical Chemical Compound Cake", "An analytical specialty starring Petri Dish Jelly, paired with Microscope Slide Cracker and a hint of Test Tube Broth.", "uncommon", ["Petri Dish Jelly", "Microscope Slide Cracker", "Test Tube Broth"], "Pour through a fine filter for a clear finish.", "Specimen pickup station"],
    ["Reactive Petri Dish Snack Tray", "Reactive Petri Dish Snack Tray, a reactive favorite built around Bunsen Flame Char and Formula Fizz Powder.", "rare", ["Bunsen Flame Char", "Formula Fizz Powder", "Beaker Berry"], "Measure each ingredient precisely before mixing.", "OnigiLab counter"],
    ["Catalyzed Genome Noodle Bowl", "A catalyzed twist on the classic, blending DNA Strand Noodle, Specimen Jar Cream, and Lab Goggle Garnish.", "uncommon", ["DNA Strand Noodle", "Specimen Jar Cream", "Lab Goggle Garnish"], "Heat gently over a low Bunsen flame.", "Research bench"],
    ["Synthesized Specimen Jar Pudding", "Rich with Microscope Slide Cracker and finished with Chemical Compound Drizzle for a synthesized touch.", "rare", ["Microscope Slide Cracker", "Test Tube Broth", "Chemical Compound Drizzle"], "Stir until the reaction turns a satisfying color.", "Sample collection tray"],
    ["Precision Reaction Flask Smoothie", "This precision creation layers Formula Fizz Powder over Beaker Berry for a memorable bite.", "epic", ["Formula Fizz Powder", "Beaker Berry", "Petri Dish Jelly"], "Let it culture briefly before plating.", "Observation window"],
    ["Analytical Beaker Berry Fizz", "An analytical specialty starring Specimen Jar Cream, paired with Lab Goggle Garnish and a hint of Bunsen Flame Char.", "legendary", ["Specimen Jar Cream", "Lab Goggle Garnish", "Bunsen Flame Char"], "Pour through a fine filter for a clear finish.", "Specimen pickup station"],
    ["Reactive DNA Strand Noodles", "Reactive DNA Strand Noodles, a reactive favorite built around Test Tube Broth and Chemical Compound Drizzle.", "common", ["Test Tube Broth", "Chemical Compound Drizzle", "DNA Strand Noodle"], "Measure each ingredient precisely before mixing.", "OnigiLab counter"],
    ["Lab-Grade Microscope Slide Crackers", "A lab-grade twist on the classic, blending Beaker Berry, Petri Dish Jelly, and Microscope Slide Cracker.", "common", ["Beaker Berry", "Petri Dish Jelly", "Microscope Slide Cracker"], "Heat gently over a low Bunsen flame.", "Research bench"],
    ["Lab-Grade Bunsen Burner Toast", "Rich with Lab Goggle Garnish and finished with Formula Fizz Powder for a lab-grade touch.", "uncommon", ["Lab Goggle Garnish", "Bunsen Flame Char", "Formula Fizz Powder"], "Stir until the reaction turns a satisfying color.", "Sample collection tray"],
    ["Experimental Petri Dish Snack Tray", "This experimental creation layers Chemical Compound Drizzle over DNA Strand Noodle for a memorable bite.", "common", ["Chemical Compound Drizzle", "DNA Strand Noodle", "Specimen Jar Cream"], "Let it culture briefly before plating.", "Observation window"],
    ["Calibrated Bunsen Burner Toast", "A calibrated specialty starring Petri Dish Jelly, paired with Microscope Slide Cracker and a hint of Test Tube Broth.", "uncommon", ["Petri Dish Jelly", "Microscope Slide Cracker", "Test Tube Broth"], "Pour through a fine filter for a clear finish.", "Specimen pickup station"],
    ["Synthesized Lab Coat Lunch Wrap", "Synthesized Lab Coat Lunch Wrap, a synthesized favorite built around Bunsen Flame Char and Formula Fizz Powder.", "rare", ["Bunsen Flame Char", "Formula Fizz Powder", "Beaker Berry"], "Measure each ingredient precisely before mixing.", "OnigiLab counter"],
    ["Experimental Genome Noodle Bowl", "An experimental twist on the classic, blending DNA Strand Noodle, Specimen Jar Cream, and Lab Goggle Garnish.", "uncommon", ["DNA Strand Noodle", "Specimen Jar Cream", "Lab Goggle Garnish"], "Heat gently over a low Bunsen flame.", "Research bench"],
    ["Synthesized Beaker Berry Fizz", "Rich with Microscope Slide Cracker and finished with Chemical Compound Drizzle for a synthesized touch.", "rare", ["Microscope Slide Cracker", "Test Tube Broth", "Chemical Compound Drizzle"], "Stir until the reaction turns a satisfying color.", "Sample collection tray"],
    ["Precision Genome Noodle Bowl", "This precision creation layers Formula Fizz Powder over Beaker Berry for a memorable bite.", "epic", ["Formula Fizz Powder", "Beaker Berry", "Petri Dish Jelly"], "Let it culture briefly before plating.", "Observation window"],
    ["Precision Bubbling Test-Tube Tea", "A precision specialty starring Specimen Jar Cream, paired with Lab Goggle Garnish and a hint of Bunsen Flame Char.", "legendary", ["Specimen Jar Cream", "Lab Goggle Garnish", "Bunsen Flame Char"], "Pour through a fine filter for a clear finish.", "Specimen pickup station"],
    ["Catalyzed Specimen Jar Pudding", "Catalyzed Specimen Jar Pudding, a catalyzed favorite built around Test Tube Broth and Chemical Compound Drizzle.", "common", ["Test Tube Broth", "Chemical Compound Drizzle", "DNA Strand Noodle"], "Measure each ingredient precisely before mixing.", "OnigiLab counter"],
    ["Catalyzed Lab Coat Lunch Wrap", "A catalyzed twist on the classic, blending Beaker Berry, Petri Dish Jelly, and Microscope Slide Cracker.", "common", ["Beaker Berry", "Petri Dish Jelly", "Microscope Slide Cracker"], "Heat gently over a low Bunsen flame.", "Research bench"],
    ["Synthesized Bunsen Burner Toast", "Rich with Lab Goggle Garnish and finished with Formula Fizz Powder for a synthesized touch.", "uncommon", ["Lab Goggle Garnish", "Bunsen Flame Char", "Formula Fizz Powder"], "Stir until the reaction turns a satisfying color.", "Sample collection tray"],
    ["Reactive Bubbling Test-Tube Tea", "This reactive creation layers Chemical Compound Drizzle over DNA Strand Noodle for a memorable bite.", "common", ["Chemical Compound Drizzle", "DNA Strand Noodle", "Specimen Jar Cream"], "Let it culture briefly before plating.", "Observation window"],
    ["Lab-Grade Formula Fizz Float", "A lab-grade specialty starring Petri Dish Jelly, paired with Microscope Slide Cracker and a hint of Test Tube Broth.", "uncommon", ["Petri Dish Jelly", "Microscope Slide Cracker", "Test Tube Broth"], "Pour through a fine filter for a clear finish.", "Specimen pickup station"],
    ["Lab-Grade Petri Dish Snack Tray", "Lab-Grade Petri Dish Snack Tray, a lab-grade favorite built around Bunsen Flame Char and Formula Fizz Powder.", "rare", ["Bunsen Flame Char", "Formula Fizz Powder", "Beaker Berry"], "Measure each ingredient precisely before mixing.", "OnigiLab counter"],
    ["Experimental Microscope Slide Crackers", "An experimental twist on the classic, blending DNA Strand Noodle, Specimen Jar Cream, and Lab Goggle Garnish.", "uncommon", ["DNA Strand Noodle", "Specimen Jar Cream", "Lab Goggle Garnish"], "Heat gently over a low Bunsen flame.", "Research bench"],
    ["Catalyzed Bubbling Test-Tube Tea", "Rich with Microscope Slide Cracker and finished with Chemical Compound Drizzle for a catalyzed touch.", "rare", ["Microscope Slide Cracker", "Test Tube Broth", "Chemical Compound Drizzle"], "Stir until the reaction turns a satisfying color.", "Sample collection tray"],
    ["Precision Bunsen Burner Toast", "This precision creation layers Formula Fizz Powder over Beaker Berry for a memorable bite.", "epic", ["Formula Fizz Powder", "Beaker Berry", "Petri Dish Jelly"], "Let it culture briefly before plating.", "Observation window"],
    ["Reactive Genome Noodle Bowl", "A reactive specialty starring Specimen Jar Cream, paired with Lab Goggle Garnish and a hint of Bunsen Flame Char.", "legendary", ["Specimen Jar Cream", "Lab Goggle Garnish", "Bunsen Flame Char"], "Pour through a fine filter for a clear finish.", "Specimen pickup station"],
  ],
  "paws": [
    ["Furry Fish Treat Skewer", "Furry Fish Treat Skewer, a furry favorite built around Catnip and Fish Treat Flake.", "common", ["Catnip", "Fish Treat Flake", "Bird Seed Topping"], "Shape the dough into little paw prints before baking.", "Paws & Whiskers counter"],
    ["Fluffy Paw Print Pancakes", "A fluffy twist on the classic, blending Kibble Crunch, Yarn Ball Spun Sugar, and Whisker-Shaped Pretzel.", "common", ["Kibble Crunch", "Yarn Ball Spun Sugar", "Whisker-Shaped Pretzel"], "Mix gently so the kibble crunch stays crisp.", "Pet café corner booth"],
    ["Pampered Yarn Ball Candy", "Rich with Milk Bottle Cream and finished with Paw Print Stamp Icing for a pampered touch.", "uncommon", ["Milk Bottle Cream", "Dog Biscuit Crumble", "Paw Print Stamp Icing"], "Stack the layers like a cozy cat nap.", "Sunny window perch"],
    ["Gentle Yarn Ball Candy", "This gentle creation layers Fish Treat Flake over Bird Seed Topping for a memorable bite.", "common", ["Fish Treat Flake", "Bird Seed Topping", "Tail Wag Sprinkle"], "Drizzle the cream in playful swirls.", "Adoption day table"],
    ["Pampered Bird Seed Muffin", "A pampered specialty starring Yarn Ball Spun Sugar, paired with Whisker-Shaped Pretzel and a hint of Catnip.", "uncommon", ["Yarn Ball Spun Sugar", "Whisker-Shaped Pretzel", "Catnip"], "Top with a sprinkle shaped like a wagging tail.", "Grooming lounge snack bar"],
    ["Playful Purrfect Pie Slice", "Playful Purrfect Pie Slice, a playful favorite built around Dog Biscuit Crumble and Paw Print Stamp Icing.", "rare", ["Dog Biscuit Crumble", "Paw Print Stamp Icing", "Kibble Crunch"], "Shape the dough into little paw prints before baking.", "Paws & Whiskers counter"],
    ["Cuddly Paw Print Pancakes", "A cuddly twist on the classic, blending Bird Seed Topping, Tail Wag Sprinkle, and Milk Bottle Cream.", "uncommon", ["Bird Seed Topping", "Tail Wag Sprinkle", "Milk Bottle Cream"], "Mix gently so the kibble crunch stays crisp.", "Pet café corner booth"],
    ["Cuddly Dog Biscuit Parfait", "Rich with Whisker-Shaped Pretzel and finished with Fish Treat Flake for a cuddly touch.", "rare", ["Whisker-Shaped Pretzel", "Catnip", "Fish Treat Flake"], "Stack the layers like a cozy cat nap.", "Sunny window perch"],
    ["Cozy Dog Biscuit Parfait", "This cozy creation layers Paw Print Stamp Icing over Kibble Crunch for a memorable bite.", "epic", ["Paw Print Stamp Icing", "Kibble Crunch", "Yarn Ball Spun Sugar"], "Drizzle the cream in playful swirls.", "Adoption day table"],
    ["Playful Fish Treat Skewer", "A playful specialty starring Tail Wag Sprinkle, paired with Milk Bottle Cream and a hint of Dog Biscuit Crumble.", "legendary", ["Tail Wag Sprinkle", "Milk Bottle Cream", "Dog Biscuit Crumble"], "Top with a sprinkle shaped like a wagging tail.", "Grooming lounge snack bar"],
    ["Gentle Dog Biscuit Parfait", "Gentle Dog Biscuit Parfait, a gentle favorite built around Catnip and Fish Treat Flake.", "common", ["Catnip", "Fish Treat Flake", "Bird Seed Topping"], "Shape the dough into little paw prints before baking.", "Paws & Whiskers counter"],
    ["Fluffy Tail Wag Tart", "A fluffy twist on the classic, blending Kibble Crunch, Yarn Ball Spun Sugar, and Whisker-Shaped Pretzel.", "common", ["Kibble Crunch", "Yarn Ball Spun Sugar", "Whisker-Shaped Pretzel"], "Mix gently so the kibble crunch stays crisp.", "Pet café corner booth"],
    ["Adorable Yarn Ball Candy", "Rich with Milk Bottle Cream and finished with Paw Print Stamp Icing for an adorable touch.", "uncommon", ["Milk Bottle Cream", "Dog Biscuit Crumble", "Paw Print Stamp Icing"], "Stack the layers like a cozy cat nap.", "Sunny window perch"],
    ["Adorable Fish Treat Skewer", "This adorable creation layers Fish Treat Flake over Bird Seed Topping for a memorable bite.", "common", ["Fish Treat Flake", "Bird Seed Topping", "Tail Wag Sprinkle"], "Drizzle the cream in playful swirls.", "Adoption day table"],
    ["Adorable Bone-Shaped Cookie Tray", "An adorable specialty starring Yarn Ball Spun Sugar, paired with Whisker-Shaped Pretzel and a hint of Catnip.", "uncommon", ["Yarn Ball Spun Sugar", "Whisker-Shaped Pretzel", "Catnip"], "Top with a sprinkle shaped like a wagging tail.", "Grooming lounge snack bar"],
    ["Fluffy Fish Treat Skewer", "Fluffy Fish Treat Skewer, a fluffy favorite built around Dog Biscuit Crumble and Paw Print Stamp Icing.", "rare", ["Dog Biscuit Crumble", "Paw Print Stamp Icing", "Kibble Crunch"], "Shape the dough into little paw prints before baking.", "Paws & Whiskers counter"],
    ["Playful Bone-Shaped Cookie Tray", "A playful twist on the classic, blending Bird Seed Topping, Tail Wag Sprinkle, and Milk Bottle Cream.", "uncommon", ["Bird Seed Topping", "Tail Wag Sprinkle", "Milk Bottle Cream"], "Mix gently so the kibble crunch stays crisp.", "Pet café corner booth"],
    ["Gentle Paw Print Pancakes", "Rich with Whisker-Shaped Pretzel and finished with Fish Treat Flake for a gentle touch.", "rare", ["Whisker-Shaped Pretzel", "Catnip", "Fish Treat Flake"], "Stack the layers like a cozy cat nap.", "Sunny window perch"],
    ["Adorable Paw Print Pancakes", "This adorable creation layers Paw Print Stamp Icing over Kibble Crunch for a memorable bite.", "epic", ["Paw Print Stamp Icing", "Kibble Crunch", "Yarn Ball Spun Sugar"], "Drizzle the cream in playful swirls.", "Adoption day table"],
    ["Playful Dog Biscuit Parfait", "A playful specialty starring Tail Wag Sprinkle, paired with Milk Bottle Cream and a hint of Dog Biscuit Crumble.", "legendary", ["Tail Wag Sprinkle", "Milk Bottle Cream", "Dog Biscuit Crumble"], "Top with a sprinkle shaped like a wagging tail.", "Grooming lounge snack bar"],
    ["Pampered Paw Print Pancakes", "Pampered Paw Print Pancakes, a pampered favorite built around Catnip and Fish Treat Flake.", "common", ["Catnip", "Fish Treat Flake", "Bird Seed Topping"], "Shape the dough into little paw prints before baking.", "Paws & Whiskers counter"],
    ["Cuddly Milk Bottle Pudding", "A cuddly twist on the classic, blending Kibble Crunch, Yarn Ball Spun Sugar, and Whisker-Shaped Pretzel.", "common", ["Kibble Crunch", "Yarn Ball Spun Sugar", "Whisker-Shaped Pretzel"], "Mix gently so the kibble crunch stays crisp.", "Pet café corner booth"],
    ["Cuddly Bird Seed Muffin", "Rich with Milk Bottle Cream and finished with Paw Print Stamp Icing for a cuddly touch.", "uncommon", ["Milk Bottle Cream", "Dog Biscuit Crumble", "Paw Print Stamp Icing"], "Stack the layers like a cozy cat nap.", "Sunny window perch"],
    ["Cozy Whisker Waffle", "This cozy creation layers Fish Treat Flake over Bird Seed Topping for a memorable bite.", "common", ["Fish Treat Flake", "Bird Seed Topping", "Tail Wag Sprinkle"], "Drizzle the cream in playful swirls.", "Adoption day table"],
    ["Furry Bird Seed Muffin", "A furry specialty starring Yarn Ball Spun Sugar, paired with Whisker-Shaped Pretzel and a hint of Catnip.", "uncommon", ["Yarn Ball Spun Sugar", "Whisker-Shaped Pretzel", "Catnip"], "Top with a sprinkle shaped like a wagging tail.", "Grooming lounge snack bar"],
    ["Adorable Catnip Cream Puff", "Adorable Catnip Cream Puff, an adorable favorite built around Dog Biscuit Crumble and Paw Print Stamp Icing.", "rare", ["Dog Biscuit Crumble", "Paw Print Stamp Icing", "Kibble Crunch"], "Shape the dough into little paw prints before baking.", "Paws & Whiskers counter"],
    ["Cozy Paw Print Pancakes", "A cozy twist on the classic, blending Bird Seed Topping, Tail Wag Sprinkle, and Milk Bottle Cream.", "uncommon", ["Bird Seed Topping", "Tail Wag Sprinkle", "Milk Bottle Cream"], "Mix gently so the kibble crunch stays crisp.", "Pet café corner booth"],
    ["Cuddly Catnip Cream Puff", "Rich with Whisker-Shaped Pretzel and finished with Fish Treat Flake for a cuddly touch.", "rare", ["Whisker-Shaped Pretzel", "Catnip", "Fish Treat Flake"], "Stack the layers like a cozy cat nap.", "Sunny window perch"],
    ["Gentle Fish Treat Skewer", "This gentle creation layers Paw Print Stamp Icing over Kibble Crunch for a memorable bite.", "epic", ["Paw Print Stamp Icing", "Kibble Crunch", "Yarn Ball Spun Sugar"], "Drizzle the cream in playful swirls.", "Adoption day table"],
    ["Playful Paw Print Pancakes", "A playful specialty starring Tail Wag Sprinkle, paired with Milk Bottle Cream and a hint of Dog Biscuit Crumble.", "legendary", ["Tail Wag Sprinkle", "Milk Bottle Cream", "Dog Biscuit Crumble"], "Top with a sprinkle shaped like a wagging tail.", "Grooming lounge snack bar"],
  ],
  "dino": [
    ["Prehistoric Pterodactyl Wing Skewer", "Prehistoric Pterodactyl Wing Skewer, a prehistoric favorite built around Fossil Fern and Dino Egg.", "common", ["Fossil Fern", "Dino Egg", "Meteor Dust"], "Excavate the layers carefully before plating.", "Dino Shop counter"],
    ["Prehistoric Amber Resin Candy", "A prehistoric twist on the classic, blending Amber Resin, Prehistoric Fruit, and Swamp Greens.", "common", ["Amber Resin", "Prehistoric Fruit", "Swamp Greens"], "Simmer slowly like a dish trapped in amber.", "Excavation site tent"],
    ["Volcanic Excavation Site Stew", "Rich with Volcanic Berry and finished with Raptor Claw Chip Shell for a volcanic touch.", "uncommon", ["Volcanic Berry", "Jurassic Leaf", "Raptor Claw Chip Shell"], "Crack the egg gently to reveal the surprise inside.", "Roaring canyon overlook"],
    ["Fossilized Pterodactyl Wing Skewer", "This fossilized creation layers Dino Egg over Meteor Dust for a memorable bite.", "common", ["Dino Egg", "Meteor Dust", "Excavation Root Vegetable"], "Roast over volcanic heat until perfectly charred.", "Fossil display hall"],
    ["Ancient Pterodactyl Wing Skewer", "An ancient specialty starring Prehistoric Fruit, paired with Swamp Greens and a hint of Fossil Fern.", "uncommon", ["Prehistoric Fruit", "Swamp Greens", "Fossil Fern"], "Arrange the skewers in a fearsome row.", "Prehistoric playground table"],
    ["Ancient Jurassic Leaf Wrap", "Ancient Jurassic Leaf Wrap, an ancient favorite built around Jurassic Leaf and Raptor Claw Chip Shell.", "rare", ["Jurassic Leaf", "Raptor Claw Chip Shell", "Amber Resin"], "Excavate the layers carefully before plating.", "Dino Shop counter"],
    ["Ancient Excavation Site Stew", "An ancient twist on the classic, blending Meteor Dust, Excavation Root Vegetable, and Volcanic Berry.", "uncommon", ["Meteor Dust", "Excavation Root Vegetable", "Volcanic Berry"], "Simmer slowly like a dish trapped in amber.", "Excavation site tent"],
    ["Volcanic Dino Egg Omelet", "Rich with Swamp Greens and finished with Dino Egg for a volcanic touch.", "rare", ["Swamp Greens", "Fossil Fern", "Dino Egg"], "Crack the egg gently to reveal the surprise inside.", "Roaring canyon overlook"],
    ["Primal Amber Resin Candy", "This primal creation layers Raptor Claw Chip Shell over Amber Resin for a memorable bite.", "epic", ["Raptor Claw Chip Shell", "Amber Resin", "Prehistoric Fruit"], "Roast over volcanic heat until perfectly charred.", "Fossil display hall"],
    ["Prehistoric Swamp Green Smoothie", "A prehistoric specialty starring Excavation Root Vegetable, paired with Volcanic Berry and a hint of Jurassic Leaf.", "legendary", ["Excavation Root Vegetable", "Volcanic Berry", "Jurassic Leaf"], "Arrange the skewers in a fearsome row.", "Prehistoric playground table"],
    ["Roaring Prehistoric Fruit Bowl", "Roaring Prehistoric Fruit Bowl, a roaring favorite built around Fossil Fern and Dino Egg.", "common", ["Fossil Fern", "Dino Egg", "Meteor Dust"], "Excavate the layers carefully before plating.", "Dino Shop counter"],
    ["Extinct-Era Raptor Claw Chips", "An extinct-era twist on the classic, blending Amber Resin, Prehistoric Fruit, and Swamp Greens.", "common", ["Amber Resin", "Prehistoric Fruit", "Swamp Greens"], "Simmer slowly like a dish trapped in amber.", "Excavation site tent"],
    ["Roaring Excavation Site Stew", "Rich with Volcanic Berry and finished with Raptor Claw Chip Shell for a roaring touch.", "uncommon", ["Volcanic Berry", "Jurassic Leaf", "Raptor Claw Chip Shell"], "Crack the egg gently to reveal the surprise inside.", "Roaring canyon overlook"],
    ["Jurassic Swamp Green Smoothie", "This jurassic creation layers Dino Egg over Meteor Dust for a memorable bite.", "common", ["Dino Egg", "Meteor Dust", "Excavation Root Vegetable"], "Roast over volcanic heat until perfectly charred.", "Fossil display hall"],
    ["Ancient Raptor Claw Chips", "An ancient specialty starring Prehistoric Fruit, paired with Swamp Greens and a hint of Fossil Fern.", "uncommon", ["Prehistoric Fruit", "Swamp Greens", "Fossil Fern"], "Arrange the skewers in a fearsome row.", "Prehistoric playground table"],
    ["Extinct-Era Swamp Green Smoothie", "Extinct-Era Swamp Green Smoothie, an extinct-era favorite built around Jurassic Leaf and Raptor Claw Chip Shell.", "rare", ["Jurassic Leaf", "Raptor Claw Chip Shell", "Amber Resin"], "Excavate the layers carefully before plating.", "Dino Shop counter"],
    ["Roaring Dino Egg Omelet", "A roaring twist on the classic, blending Meteor Dust, Excavation Root Vegetable, and Volcanic Berry.", "uncommon", ["Meteor Dust", "Excavation Root Vegetable", "Volcanic Berry"], "Simmer slowly like a dish trapped in amber.", "Excavation site tent"],
    ["Fossilized Amber Resin Candy", "Rich with Swamp Greens and finished with Dino Egg for a fossilized touch.", "rare", ["Swamp Greens", "Fossil Fern", "Dino Egg"], "Crack the egg gently to reveal the surprise inside.", "Roaring canyon overlook"],
    ["Volcanic Raptor Claw Chips", "This volcanic creation layers Raptor Claw Chip Shell over Amber Resin for a memorable bite.", "epic", ["Raptor Claw Chip Shell", "Amber Resin", "Prehistoric Fruit"], "Roast over volcanic heat until perfectly charred.", "Fossil display hall"],
    ["Ancient Triceratops Trail Mix", "An ancient specialty starring Excavation Root Vegetable, paired with Volcanic Berry and a hint of Jurassic Leaf.", "legendary", ["Excavation Root Vegetable", "Volcanic Berry", "Jurassic Leaf"], "Arrange the skewers in a fearsome row.", "Prehistoric playground table"],
    ["Fossilized Swamp Green Smoothie", "Fossilized Swamp Green Smoothie, a fossilized favorite built around Fossil Fern and Dino Egg.", "common", ["Fossil Fern", "Dino Egg", "Meteor Dust"], "Excavate the layers carefully before plating.", "Dino Shop counter"],
    ["Fossilized Raptor Claw Chips", "A fossilized twist on the classic, blending Amber Resin, Prehistoric Fruit, and Swamp Greens.", "common", ["Amber Resin", "Prehistoric Fruit", "Swamp Greens"], "Simmer slowly like a dish trapped in amber.", "Excavation site tent"],
    ["Prehistoric Raptor Claw Chips", "Rich with Volcanic Berry and finished with Raptor Claw Chip Shell for a prehistoric touch.", "uncommon", ["Volcanic Berry", "Jurassic Leaf", "Raptor Claw Chip Shell"], "Crack the egg gently to reveal the surprise inside.", "Roaring canyon overlook"],
    ["Fossilized Jurassic Leaf Wrap", "This fossilized creation layers Dino Egg over Meteor Dust for a memorable bite.", "common", ["Dino Egg", "Meteor Dust", "Excavation Root Vegetable"], "Roast over volcanic heat until perfectly charred.", "Fossil display hall"],
    ["Jurassic Excavation Site Stew", "A jurassic specialty starring Prehistoric Fruit, paired with Swamp Greens and a hint of Fossil Fern.", "uncommon", ["Prehistoric Fruit", "Swamp Greens", "Fossil Fern"], "Arrange the skewers in a fearsome row.", "Prehistoric playground table"],
    ["Volcanic Prehistoric Fruit Bowl", "Volcanic Prehistoric Fruit Bowl, a volcanic favorite built around Jurassic Leaf and Raptor Claw Chip Shell.", "rare", ["Jurassic Leaf", "Raptor Claw Chip Shell", "Amber Resin"], "Excavate the layers carefully before plating.", "Dino Shop counter"],
    ["Jurassic Fossil Fern Salad", "A jurassic twist on the classic, blending Meteor Dust, Excavation Root Vegetable, and Volcanic Berry.", "uncommon", ["Meteor Dust", "Excavation Root Vegetable", "Volcanic Berry"], "Simmer slowly like a dish trapped in amber.", "Excavation site tent"],
    ["Prehistoric Excavation Site Stew", "Rich with Swamp Greens and finished with Dino Egg for a prehistoric touch.", "rare", ["Swamp Greens", "Fossil Fern", "Dino Egg"], "Crack the egg gently to reveal the surprise inside.", "Roaring canyon overlook"],
    ["Extinct-Era Volcanic Berry Tart", "This extinct-era creation layers Raptor Claw Chip Shell over Amber Resin for a memorable bite.", "epic", ["Raptor Claw Chip Shell", "Amber Resin", "Prehistoric Fruit"], "Roast over volcanic heat until perfectly charred.", "Fossil display hall"],
    ["Primal Swamp Green Smoothie", "A primal specialty starring Excavation Root Vegetable, paired with Volcanic Berry and a hint of Jurassic Leaf.", "legendary", ["Excavation Root Vegetable", "Volcanic Berry", "Jurassic Leaf"], "Arrange the skewers in a fearsome row.", "Prehistoric playground table"],
  ],
};

function doGet(e) {
  return routeOnigiriDatabase_(e && e.parameter ? e.parameter : {});
}

function doPost(e) {
  const body = e && e.postData && e.postData.contents
    ? JSON.parse(e.postData.contents)
    : {};
  return routeOnigiriDatabase_(body);
}

function routeOnigiriDatabase_(body) {
  const payload = body || {};
  const action = String(payload.action || '').trim();

  if (action === 'recipeRushToday') {
    return getRecipeRushToday_(payload);
  }

  if (action === 'recipeRushSyncRestaurants') {
    return syncRecipeRushRestaurants_(payload);
  }

  if (payload.code) {
    return redeemRewardCode_(payload);
  }

  return json_({
    result: 'error',
    message: 'Missing code or action'
  });
}

function getRecipeRushToday_(requestData) {
  const lock = LockService.getScriptLock();

  try {
    lock.waitLock(10000);
  } catch (error) {
    return json_({ result: 'error', message: 'Server busy' });
  }

  try {
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    seedRushGroupsReferenceIfEmpty_(spreadsheet);
    const restaurants = normalizeRecipeRushRestaurants_(requestData.restaurants || []);
    syncRecipeRushRestaurantsIntoSheets_(spreadsheet, restaurants);

    const restaurantId = String(requestData.restaurant_id || 'default').trim() || 'default';
    const ankiDay = String(requestData.anki_day || Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd')).trim();
    const difficulty = String(requestData.difficulty || 'Apprendice').trim();
    const restaurantInfo = restaurants.filter(function (r) { return r.id === restaurantId; })[0]
      || { id: restaurantId, name: '', type: 'restaurant', price: 0 };

    const recipe = chooseRecipeRushRecipe_(spreadsheet, restaurantId, ankiDay);

    if (!recipe) {
      return json_({
        result: 'error',
        message: 'No Ingredient Rush recipes found'
      });
    }

    return json_({
      result: 'success',
      ticket: buildRecipeRushTicket_(recipe, restaurantInfo, ankiDay, difficulty)
    });
  } catch (error) {
    return json_({
      result: 'error',
      message: String(error && error.message ? error.message : error)
    });
  } finally {
    lock.releaseLock();
  }
}

function syncRecipeRushRestaurants_(requestData) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const restaurants = normalizeRecipeRushRestaurants_(requestData.restaurants || []);
  const result = syncRecipeRushRestaurantsIntoSheets_(spreadsheet, restaurants);
  return json_({
    result: 'success',
    restaurants_synced: result.restaurantsSynced
  });
}

function syncRecipeRushRestaurantsIntoSheets_(spreadsheet, restaurants) {
  const restaurantSheet = getOrCreateSheet_(spreadsheet, RECIPE_RUSH_RESTAURANTS_SHEET, [
    'Restaurant ID', 'Restaurant Name', 'Type', 'Price', 'Status', 'Last Synced'
  ]);

  if (!restaurants.some(function (restaurant) { return restaurant.id === 'default'; })) {
    restaurants.unshift({ id: 'default', name: 'Onigiri Stand', type: 'restaurant', price: 0 });
  }

  const restaurantIds = existingKeys_(restaurantSheet, 1);
  const now = new Date().toISOString();
  let restaurantsSynced = 0;

  restaurants.forEach(function (restaurant) {
    if (!restaurant.id) {
      return;
    }

    if (!restaurantIds[restaurant.id]) {
      restaurantSheet.appendRow([
        restaurant.id,
        restaurant.name || restaurant.id,
        restaurant.type || 'restaurant',
        Number(restaurant.price || 0),
        'Active',
        now
      ]);
      restaurantIds[restaurant.id] = true;
    }

    restaurantsSynced += 1;
  });

  return { restaurantsSynced: restaurantsSynced };
}

function resolveRushGroup_(restaurantId) {
  if (SHOP_RUSH_GROUPS[restaurantId]) {
    return SHOP_RUSH_GROUPS[restaurantId];
  }

  // Unknown id (e.g. a future building not mapped yet) - fall back to the
  // base Onigiri Stand / Sushi Evolutions line instead of failing the ticket.
  return 'sushi';
}

function chooseRecipeRushRecipe_(spreadsheet, restaurantId, ankiDay) {
  const group = resolveRushGroup_(restaurantId);
  const pool = loadRushRecipePool_(spreadsheet, group);

  if (!pool || !pool.length) {
    return null;
  }

  const index = deterministicIndex_(ankiDay + ':' + restaurantId, pool.length);
  const tuple = pool[index];

  return {
    group: group,
    poolIndex: index,
    rushName: RUSH_TITLES[group] || 'Ingredient Rush',
    recipeId: group + '_' + restaurantId + '_' + (index + 1),
    name: tuple[0],
    description: tuple[1],
    difficulty: tuple[2],
    ingredientNames: tuple[3],
    preparation: tuple[4],
    deliverTo: tuple[5]
  };
}

// Reads active recipes for a Rush Group from the Recipe Rush Recipes sheet
// (auto-seeding it with the starter catalog on first run). Falls back to the
// in-script RUSH_RECIPES pool if the sheet has no active rows for the group
// (e.g. everything for that group got set to Inactive by mistake).
function loadRushRecipePool_(spreadsheet, group) {
  const sheet = seedRecipeRushRecipesIfEmpty_(spreadsheet);
  const values = sheet.getDataRange().getValues();
  const pool = [];

  for (let i = 1; i < values.length; i += 1) {
    const row = values[i];
    const rowGroup = String(row[0] || '').trim().toLowerCase();
    const status = String(row[7] || '').trim().toLowerCase();

    if (rowGroup !== group || status !== 'active') {
      continue;
    }

    const name = String(row[1] || '').trim();
    if (!name) {
      continue;
    }

    const ingredients = String(row[4] || '')
      .split(',')
      .map(function (part) { return part.trim(); })
      .filter(function (part) { return part; });

    pool.push([
      name,
      String(row[2] || '').trim(),
      String(row[3] || 'common').trim().toLowerCase(),
      ingredients.length ? ingredients : ['Rice', 'Filling'],
      String(row[5] || '').trim(),
      String(row[6] || '').trim()
    ]);
  }

  return pool.length ? pool : (RUSH_RECIPES[group] || []);
}

// One-time setup: creates the Rush Groups reference sheet and fills it from
// SHOP_RUSH_GROUPS / RUSH_TITLES. Purely informational - editing it does
// nothing; it exists so you know which "Rush Group" value to type into the
// Recipe Rush Recipes sheet.
function seedRushGroupsReferenceIfEmpty_(spreadsheet) {
  const sheet = getOrCreateSheet_(spreadsheet, RUSH_GROUPS_SHEET, [
    'Rush Group', 'Rush Name', 'Restaurant IDs Using This Rush'
  ]);

  if (sheet.getLastRow() > 1) {
    return sheet;
  }

  const idsByGroup = {};
  Object.keys(SHOP_RUSH_GROUPS).forEach(function (restaurantId) {
    const group = SHOP_RUSH_GROUPS[restaurantId];
    if (!idsByGroup[group]) {
      idsByGroup[group] = [];
    }
    idsByGroup[group].push(restaurantId);
  });

  const rows = Object.keys(RUSH_TITLES).map(function (group) {
    return [group, RUSH_TITLES[group], (idsByGroup[group] || []).join(', ')];
  });

  if (rows.length) {
    sheet.getRange(2, 1, rows.length, 3).setValues(rows);
  }

  return sheet;
}

// One-time setup: creates the Recipe Rush Recipes sheet and seeds it with the
// 30-recipe starter pool per Rush Group from RUSH_RECIPES. Does nothing if
// the sheet already has data rows in the current format (so manual
// additions/edits are preserved). If the sheet predates this format (the old
// per-restaurant layout with an "Recipe ID" column) it is cleared and
// reseeded automatically, since that old data isn't readable by this layout.
function seedRecipeRushRecipesIfEmpty_(spreadsheet) {
  const expectedHeader = [
    'Rush Group', 'Recipe Name', 'Description', 'Difficulty',
    'Ingredients (comma-separated)', 'Preparation', 'Deliver To', 'Status'
  ];
  const sheet = getOrCreateSheet_(spreadsheet, RECIPE_RUSH_RECIPES_SHEET, expectedHeader);

  const currentHeader = sheet.getRange(1, 1, 1, expectedHeader.length).getValues()[0]
    .map(function (v) { return String(v || '').trim(); });
  const headerMatches = expectedHeader.every(function (col, i) { return currentHeader[i] === col; });

  if (!headerMatches) {
    sheet.clear();
    sheet.appendRow(expectedHeader);
  } else if (sheet.getLastRow() > 1) {
    return sheet;
  }

  const rows = [];
  Object.keys(RUSH_RECIPES).forEach(function (group) {
    RUSH_RECIPES[group].forEach(function (tuple) {
      rows.push([group, tuple[0], tuple[1], tuple[2], tuple[3].join(', '), tuple[4], tuple[5], 'Active']);
    });
  });

  if (rows.length) {
    sheet.getRange(2, 1, rows.length, 8).setValues(rows);
  }

  applyRecipeSheetValidation_(spreadsheet, sheet);
  return sheet;
}

// Adds dropdown-style data validation to the Recipe Rush Recipes sheet so
// future manually-added rows get the same Rush Group / Difficulty / Status
// choices instead of free-typed text that might not match anything.
function applyRecipeSheetValidation_(spreadsheet, sheet) {
  const maxRows = 2000;
  const groupsSheet = spreadsheet.getSheetByName(RUSH_GROUPS_SHEET);

  if (groupsSheet && groupsSheet.getLastRow() > 1) {
    const groupRange = groupsSheet.getRange(2, 1, groupsSheet.getLastRow() - 1, 1);
    const groupValidation = SpreadsheetApp.newDataValidation()
      .requireValueInRange(groupRange, true)
      .setAllowInvalid(true)
      .build();
    sheet.getRange(2, 1, maxRows - 1, 1).setDataValidation(groupValidation);
  }

  const difficultyValidation = SpreadsheetApp.newDataValidation()
    .requireValueInList(['common', 'uncommon', 'rare', 'epic', 'legendary'], true)
    .setAllowInvalid(true)
    .build();
  sheet.getRange(2, 4, maxRows - 1, 1).setDataValidation(difficultyValidation);

  const statusValidation = SpreadsheetApp.newDataValidation()
    .requireValueInList(['Active', 'Inactive'], true)
    .setAllowInvalid(true)
    .build();
  sheet.getRange(2, 8, maxRows - 1, 1).setDataValidation(statusValidation);
}

function buildRecipeRushTicket_(recipe, restaurantInfo, ankiDay, restaurantDifficulty) {
  const price = Number((restaurantInfo && restaurantInfo.price) || 0);
  const minCards = price >= 1500 ? 28 : price >= 800 ? 18 : price >= 400 ? 12 : 8;
  const jitter = recipe.poolIndex % 3;

  const ingredients = recipe.ingredientNames.map(function (name, ingredientIndex) {
    return { name: name, cards: minCards + ingredientIndex * 2 + jitter };
  });
  const ingredientCards = ingredients.reduce(function (total, item) {
    return total + item.cards;
  }, 0);

  const prepCardsBase = Math.max(3, Math.floor(minCards * 0.45));
  const deliveryCardsBase = Math.max(2, Math.floor(minCards * 0.25));

  const difficultyMultiplier = restaurantDifficulty === 'Chef' ? 4 : restaurantDifficulty === 'Cook' ? 2 : 1;
  const prepCards = Math.max(1, prepCardsBase * difficultyMultiplier);
  const deliveryCards = Math.max(1, deliveryCardsBase * difficultyMultiplier);
  const scaledIngredients = ingredients.map(function (item) {
    return { name: item.name, cards: Math.max(1, item.cards * difficultyMultiplier) };
  });
  const scaledIngredientCards = ingredientCards * difficultyMultiplier;
  const targetCards = scaledIngredientCards + prepCards + deliveryCards;

  const difficulty = String(recipe.difficulty || 'common').toLowerCase();
  const xpMultiplier = difficulty === 'legendary' ? 2.5 : difficulty === 'epic' ? 2 : difficulty === 'rare' ? 1.5 : difficulty === 'uncommon' ? 1.2 : 1;

  return {
    recipe_id: recipe.recipeId,
    restaurant_id: (restaurantInfo && restaurantInfo.id) || 'default',
    restaurant_name: (restaurantInfo && restaurantInfo.name) || '',
    rush_name: recipe.rushName,
    anki_day: ankiDay,
    name: recipe.name,
    description: recipe.description,
    difficulty: difficulty,
    ingredients: scaledIngredients,
    prep_cards: prepCards,
    delivery_cards: deliveryCards,
    preparation: recipe.preparation,
    delivery: recipe.deliverTo,
    target_cards: targetCards,
    xp_reward: Math.max(50, Math.floor(targetCards * 5 * xpMultiplier)),
    source: 'apps_script'
  };
}

function normalizeRecipeRushRestaurants_(restaurants) {
  if (!Array.isArray(restaurants)) {
    return [];
  }

  return restaurants.map(function (restaurant) {
    return {
      id: String(restaurant.id || restaurant.restaurant_id || '').trim(),
      name: String(restaurant.name || restaurant.restaurant_name || '').trim(),
      type: String(restaurant.type || 'restaurant').trim(),
      price: Number(restaurant.price || 0)
    };
  }).filter(function (restaurant) {
    return restaurant.id;
  });
}

function existingKeys_(sheet, column) {
  const values = sheet.getDataRange().getValues();
  const keys = {};
  for (let i = 1; i < values.length; i += 1) {
    const key = String(values[i][column - 1] || '').trim();
    if (key) {
      keys[key] = true;
    }
  }
  return keys;
}

function getOrCreateSheet_(spreadsheet, name, headers) {
  let sheet = spreadsheet.getSheetByName(name);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(name);
  }

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
  }

  return sheet;
}

function deterministicIndex_(seedText, length) {
  let hash = 0;
  for (let i = 0; i < seedText.length; i += 1) {
    hash = ((hash << 5) - hash) + seedText.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) % Math.max(1, length);
}

function redeemRewardCode_(requestData) {
  const lock = LockService.getScriptLock();

  try {
    lock.waitLock(10000);
  } catch (error) {
    return json_({
      result: 'error',
      message: 'Server busy'
    });
  }

  try {
    const sentCode = normalizeRewardCode_(requestData.code);

    if (!sentCode) {
      return json_({
        result: 'error',
        message: 'Missing code'
      });
    }

    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    const checkedSheets = [];

    for (let d = 0; d < REWARD_DATABASES.length; d += 1) {
      const db = REWARD_DATABASES[d];
      const sheet = findRewardSheet_(spreadsheet, db.sheetNames || [db.sheetName]);

      if (!sheet) {
        checkedSheets.push('missing: ' + (db.sheetNames || [db.sheetName]).join(' / '));
        continue;
      }

      checkedSheets.push(sheet.getName());

      const data = sheet.getDataRange().getValues();

      for (let i = 1; i < data.length; i += 1) {
        const row = data[i];
        const rowCode = normalizeRewardCode_(row[db.codeColumn - 1]);
        const rowStatus = String(row[db.statusColumn - 1] || '').trim().toLowerCase();

        if (rowCode !== sentCode) {
          continue;
        }

        if (rowStatus !== 'active') {
          return json_({
            result: 'error',
            message: 'Code already used'
          });
        }

        const reward = buildReward_(db, row);

        if (reward.result !== 'success') {
          return json_(reward);
        }

        sheet.getRange(i + 1, db.statusColumn).setValue('Used');

        reward.sheet = sheet.getName();
        reward.redeemed_at = new Date().toISOString();

        return json_(reward);
      }
    }

    return json_({
      result: 'error',
      message: 'Invalid Code. Checked sheets: ' + checkedSheets.join(', ')
    });
  } catch (error) {
    return json_({
      result: 'error',
      message: String(error && error.message ? error.message : error)
    });
  } finally {
    lock.releaseLock();
  }
}

function buildReward_(db, row) {
  let amount = Number(row[db.amountColumn - 1] || 0);

  if (!Number.isFinite(amount) || amount <= 0) {
    return {
      result: 'error',
      message: 'Invalid reward amount'
    };
  }

  amount = Math.floor(amount);

  const reward = {
    result: 'success',
    reward_type: db.rewardType,
    amount: amount
  };

  if (db.rewardType === 'taiyaki_coins') {
    reward.coins = amount;
    return reward;
  }

  if (db.rewardType === 'onigimon_coins') {
    let currency = db.defaultCurrency || 'comet_shards';

    if (db.currencyColumn) {
      currency = String(row[db.currencyColumn - 1] || currency).trim().toLowerCase();
    }

    if (currency === 'star_piece' || currency === 'star pieces' || currency === 'star-pieces') {
      currency = 'star_pieces';
    }

    if (currency === 'comet shard' || currency === 'comet shards' || currency === 'comet-shards') {
      currency = 'comet_shards';
    }

    if (currency !== 'comet_shards' && currency !== 'star_pieces') {
      return {
        result: 'error',
        message: 'Invalid Onigimon currency'
      };
    }

    reward.currency = currency;
    return reward;
  }

  if (db.rewardType === 'onigimon_item') {
    const itemKey = String(row[db.itemColumn - 1] || '').trim();

    if (!itemKey) {
      return {
        result: 'error',
        message: 'Missing Onigimon item key'
      };
    }

    reward.item_key = itemKey;
    return reward;
  }

  return reward;
}

function normalizeRewardCode_(value) {
  return String(value || '')
    .trim()
    .replace(/[\s-]+/g, '')
    .toUpperCase();
}

function findRewardSheet_(spreadsheet, names) {
  for (let i = 0; i < names.length; i += 1) {
    const sheet = spreadsheet.getSheetByName(names[i]);

    if (sheet) {
      return sheet;
    }
  }

  return null;
}

function json_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

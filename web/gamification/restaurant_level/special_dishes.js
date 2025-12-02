// List of 400+ sushi dishes with descriptions
const restaurantSpecials = {
    "default": [
        {
            name: "Uramaki",
            description: "A delicious roll with seaweed (nori) on the inside, surrounding the fillings.",
            minCards: 10,
            maxCards: 150
        },
        {
            name: "Nigiri Sake",
            description: "Fresh salmon slices over pressed rice, a classic favorite.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Temaki",
            description: "Hand-rolled cone of nori filled with rice and fresh ingredients.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Chirashi",
            description: "A colorful bowl of sushi rice topped with assorted sashimi.",
            minCards: 25,
            maxCards: 150
        },
        {
            name: "Inari",
            description: "Sweet tofu pouches filled with sushi rice.",
            minCards: 10,
            maxCards: 50
        },
        {
            name: "Dragon Roll",
            description: "An inside-out roll with eel and avocado, resembling a dragon.",
            minCards: 30,
            maxCards: 150,
            difficulty: "epic"
        },
        {
            name: "Rainbow Roll",
            description: "Colorful assortment of fish on a California roll.",
            minCards: 25,
            maxCards: 120,
            difficulty: "rare"
        },
        {
            name: "Spider Roll",
            description: "Soft-shell crab tempura with spicy mayo and cucumber.",
            minCards: 20,
            maxCards: 100,
            difficulty: "uncommon"
        },
        {
            name: "Caterpillar Roll",
            description: "Eel and cucumber topped with thin avocado slices.",
            minCards: 15,
            maxCards: 80,
            difficulty: "common"
        },
        {
            name: "Volcano Roll",
            description: "Baked seafood and spicy mayo on a California roll.",
            minCards: 35,
            maxCards: 150,
            difficulty: "legendary"
        },
        {
            name: "Nigiri Maguro",
            description: "Classic tuna slice over pressed sushi rice.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Nigiri Hamachi",
            description: "Yellowtail slice over pressed sushi rice.",
            minCards: 15,
            maxCards: 110
        },
        {
            name: "Nigiri Ebi",
            description: "Cooked shrimp over pressed sushi rice.",
            minCards: 10,
            maxCards: 90
        },
        {
            name: "Nigiri Unagi",
            description: "Grilled freshwater eel with sauce over rice.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Nigiri Tamago",
            description: "Sweet egg omelet over pressed sushi rice.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Nigiri Ika",
            description: "Squid slice over pressed sushi rice.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Nigiri Tako",
            description: "Octopus slice over pressed sushi rice.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Nigiri Saba",
            description: "Cured mackerel slice over pressed sushi rice.",
            minCards: 10,
            maxCards: 90
        },
        {
            name: "Nigiri Hotate",
            description: "Raw scallop over pressed sushi rice.",
            minCards: 20,
            maxCards: 130,
            difficulty: "uncommon"
        },
        {
            name: "Nigiri Amaebi",
            description: "Sweet raw shrimp over pressed sushi rice.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Nigiri Kani",
            description: "Crab stick (kanikama) over pressed sushi rice.",
            minCards: 10,
            maxCards: 70
        },
        {
            name: "Nigiri Shime Saba",
            description: "Vinegar-cured mackerel on rice.",
            minCards: 15,
            maxCards: 90
        },
        {
            name: "Nigiri Aji",
            description: "Japanese horse mackerel on rice.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Nigiri Suzuki",
            description: "Japanese sea bass slice on rice.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Nigiri Tai",
            description: "Red snapper slice on pressed rice.",
            minCards: 15,
            maxCards: 110
        },
        {
            name: "Nigiri Engawa",
            description: "Fluke fin, often lightly seared, on rice.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Nigiri Hirame",
            description: "Halibut slice over pressed sushi rice.",
            minCards: 15,
            maxCards: 110
        },
        {
            name: "Nigiri Kanpachi",
            description: "Amberjack slice over pressed sushi rice.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Nigiri Buri",
            description: "Adult yellowtail (winter) on rice.",
            minCards: 20,
            maxCards: 130,
            difficulty: "rare"
        },
        {
            name: "Nigiri Toro",
            description: "Fatty tuna belly slice on rice.",
            minCards: 30,
            maxCards: 150,
            difficulty: "epic"
        },
        {
            name: "Nigiri Otoro",
            description: "Premium fatty tuna belly on rice.",
            minCards: 40,
            maxCards: 160,
            difficulty: "legendary"
        },
        {
            name: "Nigiri Chutoro",
            description: "Medium-fatty tuna belly on rice.",
            minCards: 35,
            maxCards: 150,
            difficulty: "epic"
        },
        {
            name: "Nigiri Aburi Sake",
            description: "Seared salmon slice on rice, often with mayo.",
            minCards: 20,
            maxCards: 110
        },
        {
            name: "Nigiri Aburi Toro",
            description: "Seared fatty tuna belly on rice.",
            minCards: 35,
            maxCards: 150,
            difficulty: "epic"
        },
        {
            name: "Nigiri Aburi Hamachi",
            description: "Seared yellowtail slice on rice.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Nigiri Aburi Ebi",
            description: "Seared shrimp with sauce on rice.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Nigiri Aburi Hotate",
            description: "Seared scallop with sauce on rice.",
            minCards: 25,
            maxCards: 130
        },
        {
            name: "Nigiri Wagyu",
            description: "Seared Wagyu beef slice on rice.",
            minCards: 30,
            maxCards: 150,
            difficulty: "epic"
        },
        {
            name: "Nigiri Foie Gras",
            description: "Seared foie gras on rice with unagi sauce.",
            minCards: 35,
            maxCards: 150,
            difficulty: "legendary"
        },
        {
            name: "Nigiri Avocado",
            description: "Avocado slice on pressed sushi rice.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Nigiri Shiitake",
            description: "Simmered shiitake mushroom on rice.",
            minCards: 10,
            maxCards: 50
        },
        {
            name: "Nigiri Nasu",
            description: "Grilled or pickled eggplant on rice.",
            minCards: 10,
            maxCards: 50
        },
        {
            name: "Nigiri Asparagus",
            description: "Blanched asparagus spear on rice.",
            minCards: 10,
            maxCards: 50
        },
        {
            name: "Nigiri Zucchini",
            description: "Grilled zucchini slice on rice.",
            minCards: 10,
            maxCards: 50
        },
        {
            name: "Nigiri Red Pepper",
            description: "Roasted red pepper slice on rice.",
            minCards: 10,
            maxCards: 50
        },
        {
            name: "Nigiri Inari",
            description: "Simple Inari tofu pouch (variation of Inari).",
            minCards: 10,
            maxCards: 40
        },
        {
            name: "Gunkan Ikura",
            description: "Salmon roe 'battleship' maki.",
            minCards: 25,
            maxCards: 130,
            difficulty: "rare"
        },
        {
            name: "Gunkan Tobiko",
            description: "Flying fish roe 'battleship' maki.",
            minCards: 20,
            maxCards: 110
        },
        {
            name: "Gunkan Masago",
            description: "Capelin roe 'battleship' maki.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Gunkan Uni",
            description: "Sea urchin 'battleship' maki.",
            minCards: 30,
            maxCards: 150,
            difficulty: "epic"
        },
        {
            name: "Gunkan Negitoro",
            description: "Minced fatty tuna and scallion 'battleship' maki.",
            minCards: 25,
            maxCards: 140
        },
        {
            name: "Gunkan Kani Miso",
            description: "Crab brain/miso 'battleship' maki.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Gunkan Ankimo",
            description: "Monkfish liver 'battleship' maki.",
            minCards: 25,
            maxCards: 130
        },
        {
            name: "Gunkan Spicy Scallop",
            description: "Chopped scallop with spicy mayo gunkan.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Gunkan Spicy Tuna",
            description: "Spicy tuna mix 'battleship' maki.",
            minCards: 15,
            maxCards: 110
        },
        {
            name: "Gunkan Corn Mayo",
            description: "Sweet corn with Japanese mayo gunkan.",
            minCards: 10,
            maxCards: 50
        },
        {
            name: "Gunkan Wakame",
            description: "Seasoned seaweed salad 'battleship' maki.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Gunkan Natto",
            description: "Fermented soybean 'battleship' maki.",
            minCards: 10,
            maxCards: 70
        },
        {
            name: "Gunkan Uzura",
            description: "Quail egg, often on tobiko or uni, 'battleship' maki.",
            minCards: 20,
            maxCards: 100
        },
        {
            name: "Gunkan Shirako",
            description: "Cod milt 'battleship' maki.",
            minCards: 30,
            maxCards: 150,
            difficulty: "legendary"
        },
        {
            name: "Gunkan Tarako",
            description: "Salted pollock roe 'battleship' maki.",
            minCards: 15,
            maxCards: 90
        },
        {
            name: "Maki Tekkamaki",
            description: "Simple tuna roll with nori on the outside.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Maki Kappamaki",
            description: "Simple cucumber roll with nori on the outside.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Maki Sakemaki",
            description: "Simple salmon roll with nori on the outside.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Maki Oshinko",
            description: "Pickled daikon radish roll.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Maki Kanpyo",
            description: "Dried gourd strips roll.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Maki Avocado",
            description: "Simple avocado roll with nori on the outside.",
            minCards: 10,
            maxCards: 70
        },
        {
            name: "Maki Negihama",
            description: "Yellowtail and scallion roll.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Maki Negitoro",
            description: "Fatty tuna and scallion roll.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Maki Ume Shiso",
            description: "Pickled plum paste and shiso leaf roll.",
            minCards: 10,
            maxCards: 70
        },
        {
            name: "Maki Yamagobo",
            description: "Pickled burdock root roll.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Maki Futomaki",
            description: "Thick 'fat' roll with multiple ingredients (egg, veg).",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Maki Ebi",
            description: "Cooked shrimp roll.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Maki Unagi",
            description: "Grilled eel and cucumber roll.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Maki Tamago",
            description: "Sweet egg omelet roll.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Maki Shiitake",
            description: "Simmered shiitake mushroom roll.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Maki Natto",
            description: "Fermented soybean roll.",
            minCards: 10,
            maxCards: 70
        },
        {
            name: "Maki Asparagus",
            description: "Blanched asparagus roll.",
            minCards: 10,
            maxCards: 60
        },
        {
            name: "Maki Sweet Potato",
            description: "Tempura sweet potato roll.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Maki Kani",
            description: "Crab stick (kanikama) roll.",
            minCards: 10,
            maxCards: 70
        },
        {
            name: "Maki Spicy Tuna",
            description: "Spicy tuna mix roll (nori outside).",
            minCards: 15,
            maxCards: 90
        },
        {
            name: "Maki Spicy Salmon",
            description: "Spicy salmon mix roll (nori outside).",
            minCards: 15,
            maxCards: 90
        },
        {
            name: "Maki Spicy Yellowtail",
            description: "Spicy yellowtail mix roll (nori outside).",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Uramaki California",
            description: "Krab, avocado, cucumber, rice on outside.",
            minCards: 10,
            maxCards: 90
        },
        {
            name: "Uramaki Spicy Tuna",
            description: "Spicy tuna mix, cucumber, rice on outside.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Uramaki Spicy Salmon",
            description: "Spicy salmon mix, cucumber/avocado, rice outside.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Uramaki Philadelphia",
            description: "Smoked salmon, cream cheese, avocado.",
            minCards: 15,
            maxCards: 110
        },
        {
            name: "Uramaki Eel Avocado",
            description: "Grilled eel and avocado, rice on outside.",
            minCards: 15,
            maxCards: 110
        },
        {
            name: "Uramaki Eel Cucumber",
            description: "Grilled eel and cucumber, rice on outside.",
            minCards: 15,
            maxCards: 110
        },
        {
            name: "Uramaki Shrimp Tempura",
            description: "Shrimp tempura, avocado, cucumber, spicy mayo.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Uramaki Boston Roll",
            description: "Cooked shrimp, avocado, cucumber, lettuce.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Uramaki Alaskan Roll",
            description: "Smoked salmon, avocado, crab stick.",
            minCards: 15,
            maxCards: 110
        },
        {
            name: "Uramaki Salmon Skin",
            description: "Crispy grilled salmon skin, cucumber, scallion.",
            minCards: 10,
            maxCards: 90
        },
        {
            name: "Uramaki Avocado Cucumber",
            description: "Avocado and cucumber roll.",
            minCards: 10,
            maxCards: 70
        },
        {
            name: "Uramaki Sweet Potato Tempura",
            description: "Tempura sweet potato roll with rice outside.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Uramaki Vegetable",
            description: "Assorted vegetables (avocado, cucumber, carrot).",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Uramaki Spicy Scallop",
            description: "Chopped scallop, spicy mayo, masago.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Uramaki Jalapeno Popper Roll",
            description: "Jalapeno, cream cheese, crab, tempura fried.",
            minCards: 20,
            maxCards: 130
        },
        {
            name: "Uramaki Green Machine Roll",
            description: "Asparagus, avocado, cucumber, wrapped in soy paper.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Uramaki Red Phoenix Roll",
            description: "Shrimp tempura, cucumber, topped with spicy tuna.",
            minCards: 25,
            maxCards: 140
        },
    ],
    "macha_delights": [
        {
            name: "Matcha Latte",
            description: "A smooth and creamy green tea latte.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Matcha Mochi",
            description: "Soft and chewy rice cake with matcha filling.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Matcha Cake",
            description: "Fluffy sponge cake infused with premium matcha.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Matcha Ice Cream",
            description: "Rich and creamy matcha flavored ice cream.",
            minCards: 25,
            maxCards: 140,
            difficulty: "uncommon"
        },
        {
            name: "Matcha Tiramisu",
            description: "A Japanese twist on the classic Italian dessert.",
            minCards: 30,
            maxCards: 150,
            difficulty: "rare"
        },
        {
            name: "Matcha Parfait",
            description: "Layers of matcha jelly, cream, and sponge cake.",
            minCards: 35,
            maxCards: 160,
            difficulty: "epic"
        },
        {
            name: "Ceremonial Matcha",
            description: "The highest grade matcha, whisked to perfection.",
            minCards: 40,
            maxCards: 180,
            difficulty: "legendary"
        }
    ],
    "macaroon_maison": [
        {
            name: "Vanilla Macaron",
            description: "Classic vanilla bean macaron with white chocolate ganache.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Chocolate Macaron",
            description: "Rich dark chocolate ganache in a cocoa shell.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Raspberry Macaron",
            description: "Tangy raspberry jam filling in a pink shell.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Pistachio Macaron",
            description: "Nutty pistachio cream filling.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Salted Caramel Macaron",
            description: "Sweet and salty caramel filling.",
            minCards: 20,
            maxCards: 120,
            difficulty: "uncommon"
        },
        {
            name: "Rose Macaron",
            description: "Delicate rose water buttercream.",
            minCards: 25,
            maxCards: 130,
            difficulty: "rare"
        },
        {
            name: "Gold Leaf Macaron",
            description: "Premium macaron topped with edible gold leaf.",
            minCards: 40,
            maxCards: 180,
            difficulty: "legendary"
        }
    ],
    "coffee_co": [
        {
            name: "Espresso",
            description: "A strong and concentrated shot of coffee.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Cappuccino",
            description: "Espresso with steamed milk and foam.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Latte Art",
            description: "A beautiful design poured into your latte.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Cold Brew",
            description: "Smooth coffee steeped for 12 hours.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Caramel Macchiato",
            description: "Espresso with vanilla syrup and caramel drizzle.",
            minCards: 20,
            maxCards: 120,
            difficulty: "uncommon"
        },
        {
            name: "Affogato",
            description: "Espresso poured over vanilla ice cream.",
            minCards: 25,
            maxCards: 140,
            difficulty: "rare"
        },
        {
            name: "Blue Mountain Coffee",
            description: "Rare and exclusive coffee beans from Jamaica.",
            minCards: 40,
            maxCards: 180,
            difficulty: "legendary"
        }
    ],
    "grocery_store": [
        {
            name: "Fresh Apple",
            description: "Crisp and juicy red apple.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Banana Bunch",
            description: "Perfectly ripe bananas.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Carrot Bundle",
            description: "Fresh and crunchy organic carrots.",
            minCards: 15,
            maxCards: 90
        },
        {
            name: "Milk Carton",
            description: "Fresh dairy milk.",
            minCards: 15,
            maxCards: 90
        },
        {
            name: "Artisan Bread",
            description: "Freshly baked sourdough loaf.",
            minCards: 20,
            maxCards: 110,
            difficulty: "uncommon"
        },
        {
            name: "Imported Cheese",
            description: "Fine aged cheese from Europe.",
            minCards: 25,
            maxCards: 130,
            difficulty: "rare"
        },
        {
            name: "Truffle Oil",
            description: "Premium oil infused with black truffles.",
            minCards: 35,
            maxCards: 160,
            difficulty: "legendary"
        }
    ],
    "bakery_heaven": [
        {
            name: "Croissant",
            description: "Buttery and flaky French pastry.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Baguette",
            description: "Classic French bread with a crispy crust.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Pain au Chocolat",
            description: "Croissant dough filled with chocolate.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Danish Pastry",
            description: "Sweet pastry with fruit filling.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Sourdough Loaf",
            description: "Tangy and chewy sourdough bread.",
            minCards: 25,
            maxCards: 130,
            difficulty: "uncommon"
        },
        {
            name: "Opera Cake",
            description: "Layers of almond sponge, coffee syrup, and ganache.",
            minCards: 30,
            maxCards: 150,
            difficulty: "rare"
        },
        {
            name: "Wedding Cake",
            description: "A magnificent multi-tiered cake for special occasions.",
            minCards: 40,
            maxCards: 180,
            difficulty: "legendary"
        }
    ],
    "awesome_boba": [
        {
            name: "Classic Milk Tea",
            description: "Black tea with milk and tapioca pearls.",
            minCards: 10,
            maxCards: 90
        },
        {
            name: "Taro Milk Tea",
            description: "Sweet and creamy purple taro tea.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Thai Tea",
            description: "Spiced orange tea with condensed milk.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Brown Sugar Boba",
            description: "Milk with rich brown sugar syrup stripes.",
            minCards: 20,
            maxCards: 120,
            difficulty: "uncommon"
        },
        {
            name: "Fruit Tea",
            description: "Refreshing tea with fresh fruit slices.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Cheese Foam Tea",
            description: "Tea topped with savory cream cheese foam.",
            minCards: 25,
            maxCards: 130,
            difficulty: "rare"
        },
        {
            name: "Golden Boba",
            description: "Premium tea with golden tapioca pearls.",
            minCards: 35,
            maxCards: 160,
            difficulty: "legendary"
        }
    ],
    "santas_coffee": [
        {
            name: "Hot Cocoa",
            description: "Rich hot chocolate with marshmallows.",
            minCards: 10,
            maxCards: 80
        },
        {
            name: "Peppermint Mocha",
            description: "Coffee with chocolate and peppermint syrup.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Gingerbread Latte",
            description: "Spiced latte with gingerbread flavor.",
            minCards: 15,
            maxCards: 100
        },
        {
            name: "Eggnog Latte",
            description: "Rich and creamy eggnog with espresso.",
            minCards: 20,
            maxCards: 120
        },
        {
            name: "Candy Cane Frappe",
            description: "Blended ice drink with candy cane pieces.",
            minCards: 20,
            maxCards: 120,
            difficulty: "uncommon"
        },
        {
            name: "Christmas Cookie",
            description: "Festive sugar cookie with icing.",
            minCards: 25,
            maxCards: 130,
            difficulty: "rare"
        },
        {
            name: "North Pole Special",
            description: "Santa's secret recipe for holiday cheer.",
            minCards: 40,
            maxCards: 180,
            difficulty: "legendary"
        }
    ]
};

// Map shiny boba to same list as regular boba
restaurantSpecials["awesome_shiny_boba"] = restaurantSpecials["awesome_boba"];

// XP rewards based on difficulty
const xpRewards = {
    common: {
        baseXP: 10,
        multiplier: 1.0,
        color: "#4CAF50"
    },
    uncommon: {
        baseXP: 20,
        multiplier: 1.2,
        color: "#2196F3"
    },
    rare: {
        baseXP: 35,
        multiplier: 1.5,
        color: "#9C27B0"
    },
    epic: {
        baseXP: 50,
        multiplier: 2.0,
        color: "#FF9800"
    },
    legendary: {
        baseXP: 75,
        multiplier: 2.5,
        color: "#F44336"
    }
};

// Function to get today's special based on the date and restaurant ID
window.getTodaysSpecial = function (restaurantId) {
    // Use the current date to get a consistent daily special
    const today = new Date();
    const dayOfYear = Math.floor((today - new Date(today.getFullYear(), 0, 0)) / (1000 * 60 * 60 * 24));

    // Get the list of specials for the current restaurant
    // If the restaurant ID is not found (or is an evolution), fallback to default
    let specialsList = restaurantSpecials[restaurantId];

    // If not found, check if it's an evolution (starts with restaurant_evo_)
    if (!specialsList) {
        if (restaurantId && restaurantId.startsWith('restaurant_evo_')) {
            specialsList = restaurantSpecials['default'];
        } else {
            // Fallback to default for any unknown restaurant
            specialsList = restaurantSpecials['default'];
        }
    }

    // Use modulo to cycle through the array based on the day of the year
    const index = dayOfYear % specialsList.length;
    const special = { ...specialsList[index] };

    // Generate a consistent target cards value based on the date and dish index
    // This ensures the same dish on the same day always has the same target
    const seed = dayOfYear * 31 + index;  // Simple hash combining day and dish index
    const random = ((seed * 9301 + 49297) % 233280) / 233280;  // Simple PRNG with seed
    special.targetCards = Math.floor(random * (special.maxCards - special.minCards + 1)) + special.minCards;

    // Set default difficulty if not specified
    special.difficulty = special.difficulty || 'common';

    // Calculate XP reward based on target cards
    // Base: 5 XP per card
    let xp = special.targetCards * 5;

    // Apply difficulty multiplier
    const difficulty = xpRewards[special.difficulty] || xpRewards.common;
    xp = Math.floor(xp * difficulty.multiplier);

    // Ensure minimum 50 XP
    special.xpReward = Math.max(50, xp);

    // Add difficulty color
    special.difficultyColor = difficulty.color;

    return special;
}

// Backward compatibility for existing calls
window.getTodaysSushiSpecial = function () {
    return window.getTodaysSpecial('default');
}
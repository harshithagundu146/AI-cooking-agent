from flask import Blueprint, request, jsonify
from db import get_db, get_memory_store
import math, json, os, hashlib

recipes_bp = Blueprint('recipes', __name__)

SUBSTITUTIONS = {
    "milk": ["almond milk", "soy milk", "oat milk", "coconut milk"],
    "egg": ["banana (mashed)", "yogurt", "flaxseed + water", "applesauce"],
    "butter": ["olive oil", "coconut oil", "avocado", "ghee"],
    "cream": ["coconut cream", "cashew cream", "silken tofu blend"],
    "cheese": ["nutritional yeast", "tofu ricotta", "cashew cheese"],
    "wheat flour": ["almond flour", "oat flour", "rice flour", "coconut flour"],
    "sugar": ["honey", "maple syrup", "stevia", "jaggery"],
    "soy sauce": ["coconut aminos", "tamari", "worcestershire sauce"],
    "heavy cream": ["coconut cream", "cashew cream", "evaporated milk"],
    "yogurt": ["coconut yogurt", "sour cream", "buttermilk"],
    "chicken": ["tofu", "paneer", "jackfruit", "mushrooms"],
    "beef": ["portobello mushrooms", "lentils", "tempeh"],
    "fish": ["tofu", "banana blossom", "hearts of palm"],
    "shrimp": ["king oyster mushrooms", "hearts of palm", "konjac"],
    "onion": ["shallots", "leeks", "scallions"],
    "garlic": ["garlic powder", "shallots", "asafoetida"],
    "tomato": ["red bell pepper", "canned tomatoes", "sun-dried tomatoes"],
    "lemon juice": ["lime juice", "vinegar", "citric acid"],
    "rice": ["quinoa", "cauliflower rice", "couscous", "bulgur wheat"],
    "pasta": ["zucchini noodles", "rice noodles", "spaghetti squash"],
    "bread": ["lettuce wraps", "rice cakes", "tortillas"],
    "cornstarch": ["arrowroot powder", "potato starch", "tapioca starch"],
    "baking powder": ["baking soda + cream of tartar", "self-rising flour"],
    "vanilla extract": ["almond extract", "maple syrup", "vanilla bean"],
    "vegetable oil": ["canola oil", "sunflower oil", "melted butter"],
    "paneer": ["tofu", "halloumi", "cottage cheese"],
    "ghee": ["butter", "coconut oil", "vegetable oil"],
    "garam masala": ["cumin + coriander + cardamom", "curry powder", "allspice"],
    "coconut milk": ["almond milk", "cashew milk", "regular milk + coconut extract"]
}

def _load_seed_recipes():
    seed_file = os.path.join(os.path.dirname(__file__), 'seed_recipes.json')
    if os.path.exists(seed_file):
        with open(seed_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# ===== SAVED RECIPES FILE HELPERS =====
_SAVED_RECIPES_FILE = os.path.join(os.path.dirname(__file__), 'saved_recipes.json')

def _load_saved_recipes():
    """Load all saved recipes from saved_recipes.json."""
    if os.path.exists(_SAVED_RECIPES_FILE):
        try:
            with open(_SAVED_RECIPES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def _save_recipe_to_file(recipe):
    """Append or update a recipe in saved_recipes.json."""
    recipes = _load_saved_recipes()
    # Update if already exists, otherwise append
    existing_idx = next((i for i, r in enumerate(recipes) if r.get('id') == recipe.get('id')), None)
    if existing_idx is not None:
        recipes[existing_idx] = recipe
    else:
        recipes.append(recipe)
    with open(_SAVED_RECIPES_FILE, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)

def get_all_recipes_internal(category=None):
    db = get_db()
    if db is not None:
        query = {}
        if category:
            query["category"] = category
        recipes = list(db.recipes.find(query, {"_id": 0}))
    else:
        store = get_memory_store()
        if not store["recipes"]:
            store["recipes"] = _load_seed_recipes()
        recipes = list(store["recipes"]) # copy
        if category:
            recipes = [r for r in recipes if r.get("category") == category]
    return recipes

def _cosine_similarity(vec_a, vec_b):
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0
    return dot / (mag_a * mag_b)

def _build_preference_vector(prefs):
    vec = []
    vec.append(1 if prefs.get("spice_preference") == "spicy" else 0)
    vec.append(1 if prefs.get("taste_preference") == "sweet" else 0)
    vec.append(1 if prefs.get("health_preference") == "healthy" else 0)
    vec.append(1 if prefs.get("health_preference") == "fast_food" else 0)
    return vec

def _build_recipe_vector(recipe):
    tags = recipe.get("tags", [])
    vec = []
    vec.append(1 if "spicy" in tags else 0)
    vec.append(1 if "sweet" in tags else 0)
    vec.append(1 if "healthy" in tags else 0)
    vec.append(1 if "fast_food" in tags else 0)
    return vec

@recipes_bp.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    category = data.get("category")
    user_id = data.get("user_id")
    user_prefs = data.get("preferences", {})
    cuisine = data.get("cuisine")
    recipes = get_all_recipes_internal(category)
    
    # Get user favorites to mark them
    favorites = []
    if user_id:
        db = get_db()
        if db is not None:
            user_favs = db.favorites.find_one({"user_id": user_id})
            if user_favs:
                favorites = user_favs.get("recipe_ids", [])
        else:
            store = get_memory_store()
            favorites = store["favorites"].get(user_id, [])

    for r in recipes:
        r["is_favorite"] = r["id"] in favorites

    if user_prefs:
        pref_vec = _build_preference_vector(user_prefs)
        scored = []
        for r in recipes:
            r_vec = _build_recipe_vector(r)
            score = _cosine_similarity(pref_vec, r_vec)
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        recipes = [r for _, r in scored]
    return jsonify(recipes), 200

@recipes_bp.route('/all', methods=['GET'])
def all_recipes():
    category = request.args.get('category')
    cuisine = request.args.get('cuisine')
    recipes = get_all_recipes_internal(category)
    if cuisine and cuisine != "All":
        recipes = [r for r in recipes if r.get("cuisine", "").lower() == cuisine.lower()]
    return jsonify(recipes), 200

@recipes_bp.route('/<recipe_id>', methods=['GET'])
def get_recipe(recipe_id):
    db = get_db()
    if db is not None:
        recipe = db.recipes.find_one({"id": recipe_id}, {"_id": 0})
    else:
        store = get_memory_store()
        if not store["recipes"]:
            store["recipes"] = _load_seed_recipes()
        recipe = next((r for r in store["recipes"] if r["id"] == recipe_id), None)
    # Fallback: check saved_recipes.json for AI-generated recipes
    if not recipe:
        saved = _load_saved_recipes()
        recipe = next((r for r in saved if r.get('id') == recipe_id), None)
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404
    return jsonify(recipe), 200

@recipes_bp.route('/check-ingredients', methods=['POST'])
def check_ingredients():
    data = request.get_json()
    required = [i.lower().strip() for i in data.get("required", [])]
    available = [i.lower().strip() for i in data.get("available", [])]
    missing = [i for i in required if i not in available and not any(a in i or i in a for a in available)]
    suggestions = {}
    for item in missing:
        for key, subs in SUBSTITUTIONS.items():
            if key in item or item in key:
                suggestions[item] = subs
                break
        if item not in suggestions:
            suggestions[item] = ["No common substitute available - please purchase"]
    return jsonify({"missing": missing, "substitutions": suggestions}), 200

@recipes_bp.route('/update-nutrition', methods=['POST'])
def update_nutrition():
    data = request.get_json()
    original_nutrition = data.get("nutrition", {})
    substitutions_used = data.get("substitutions_used", {})
    updated = dict(original_nutrition)
    for original, substitute in substitutions_used.items():
        sub_lower = substitute.lower()
        if "almond" in sub_lower or "oat" in sub_lower:
            updated["calories"] = max(0, updated.get("calories", 0) - 20)
            updated["fats"] = max(0, updated.get("fats", 0) - 2)
        if "coconut" in sub_lower:
            updated["fats"] = updated.get("fats", 0) + 3
        if "banana" in sub_lower or "applesauce" in sub_lower:
            updated["carbohydrates"] = updated.get("carbohydrates", 0) + 5
            updated["fiber"] = updated.get("fiber", 0) + 1
        if "tofu" in sub_lower or "lentil" in sub_lower:
            updated["protein"] = updated.get("protein", 0) + 3
            updated["fats"] = max(0, updated.get("fats", 0) - 5)
        if "honey" in sub_lower or "maple" in sub_lower or "jaggery" in sub_lower:
            updated["carbohydrates"] = updated.get("carbohydrates", 0) + 2
        if "olive oil" in sub_lower:
            updated["fats"] = updated.get("fats", 0) + 2
    return jsonify(updated), 200

@recipes_bp.route('/search', methods=['GET'])
def search():
    q = request.args.get('q', '').lower().strip()
    category = request.args.get('category')
    user_id = request.args.get('user_id')
    if not q:
        return jsonify([]), 200
    recipes = get_all_recipes_internal(category)
    
    # Favorites mark
    favorites = []
    if user_id:
        db = get_db()
        if db is not None:
            user_favs = db.favorites.find_one({"user_id": user_id})
            if user_favs: favorites = user_favs.get("recipe_ids", [])
        else:
            store = get_memory_store()
            favorites = store["favorites"].get(user_id, [])

    # AI-like NLP search scoring
    # Extract potential cuisines, tags, and ingredients from query
    query_words = set(q.replace(',', '').replace('.', '').split())
    
    scored_results = []
    for r in recipes:
        score = 0
        r_name = r.get("name", "").lower()
        r_cuisine = r.get("cuisine", "").lower()
        r_tags = [t.lower() for t in r.get("tags", [])]
        r_ingredients = [i.lower() for i in r.get("ingredients", [])]
        
        # Exact match boost
        if q in r_name:
            score += 10
        if q in r_cuisine:
            score += 8
            
        # Semantic word match
        for word in query_words:
            # Skip common stop words
            if word in ['i', 'want', 'to', 'eat', 'some', 'food', 'with', 'a', 'an', 'the', 'recipe', 'recipes', 'for']:
                continue
                
            if word in r_name:
                score += 3
            if word == r_cuisine:
                score += 4
            if word in r_tags:
                score += 3
            if any(word in ing for ing in r_ingredients):
                score += 2
                
            # Cross-cuisine / multi-cuisine matching (e.g., "asian", "european" generalizations could be added)
            if word == "asian" and r_cuisine in ["indian", "thai"]:
                score += 2
            if word == "european" and r_cuisine in ["italian", "french", "mediterranean"]:
                score += 2

        if score > 0:
            r_copy = dict(r)
            r_copy["is_favorite"] = r_copy["id"] in favorites
            scored_results.append((score, r_copy))

    # Sort by highest score first
    scored_results.sort(key=lambda x: x[0], reverse=True)
    
    # Optional: threshold to only show relevant ones, or just return all scored
    results = [r for score, r in scored_results if score >= 2]
    
    # Adaptable AI Feature: Fetch real recipe from TheMealDB or fallback to dynamic exact recipe
    if not results and q:
        import uuid, urllib.request, urllib.parse, json
        words = [w for w in q.split() if w not in ['i', 'want', 'to', 'eat', 'some', 'food', 'with', 'a', 'an', 'the', 'recipe', 'recipes', 'for']]
        main_theme = " ".join(words).title() if words else "Surprise"
        
        dynamic_recipe = None
        try:
            # Try to fetch exactly from TheMealDB
            url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(main_theme)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            res = urllib.request.urlopen(req, timeout=3)
            data = json.loads(res.read())
            if data and data.get('meals'):
                meal = data['meals'][0]
                
                # Extract ingredients
                ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f'strIngredient{i}')
                    measure = meal.get(f'strMeasure{i}')
                    if ing and ing.strip():
                        ingredients.append(f"{measure.strip()} {ing.strip()}" if measure else ing.strip())
                
                # Extract instructions
                instructions = meal.get('strInstructions', '').replace('\r\n', '\n').split('\n')
                steps = []
                step_idx = 1
                for inst in instructions:
                    if inst.strip():
                        steps.append({
                            "step": step_idx,
                            "title": f"Step {step_idx}",
                            "instruction": inst.strip(),
                            "why": "Follow the authentic recipe.",
                            "tip": "Keep an eye on the cooking time."
                        })
                        step_idx += 1

                dynamic_recipe = {
                    "id": "dyn_" + meal['idMeal'],
                    "name": meal['strMeal'],
                    "category": meal.get('strCategory', 'non-vegetarian'),
                    "cuisine": meal.get('strArea', 'Fusion'),
                    "image": meal.get('strMealThumb', '✨'),
                    "duration": "45 mins",
                    "difficulty": "Medium",
                    "tags": ["AI-fetched", meal.get('strArea', 'Fusion').lower()],
                    "ingredients": ingredients,
                    "nutrition": {"calories": 400, "protein": 20, "carbohydrates": 45, "fats": 15, "fiber": 5, "vitamins": "A, B, C", "minerals": "Iron, Calcium"},
                    "steps": steps,
                    "is_favorite": False
                }
        except Exception as e:
            pass
            
        if not dynamic_recipe:
            detected_cuisine = "Fusion"
            for c in ["indian", "italian", "mexican", "french", "thai", "american", "mediterranean"]:
                if c in q:
                    detected_cuisine = c.title()
                    break
            is_veg = "veg" in q or "vegan" in q
            
            dynamic_recipe = {
                "id": "dyn_" + str(uuid.uuid4())[:8],
                "name": main_theme,
                "category": "vegetarian" if is_veg else "non-vegetarian",
                "cuisine": detected_cuisine,
                "image": "✨",
                "duration": "30 mins",
                "difficulty": "Medium",
                "tags": ["AI-generated", "dynamic", detected_cuisine.lower()],
                "ingredients": [words[-1] if words else "mystery ingredient", "olive oil", "garlic", "onions", "chef's special spices", "salt", "pepper"],
                "nutrition": {"calories": 350, "protein": 15, "carbohydrates": 25, "fats": 12, "fiber": 4, "vitamins": "A, C", "minerals": "Iron"},
                "steps": [
                    {"step": 1, "title": "Prepare Base", "instruction": f"Prepare the ingredients for {main_theme}. Heat olive oil in a pan.", "why": "Builds the flavor foundation.", "tip": "Don't burn the garlic!"},
                    {"step": 2, "title": "Main Cooking", "instruction": f"Add the main ingredients for {main_theme} and the chef's special spices. Cook for 15 minutes.", "why": "Allows flavors to meld.", "tip": "Stir occasionally."},
                    {"step": 3, "title": "Simmer & Serve", "instruction": f"Simmer on low heat for 5 minutes. Serve your delicious {main_theme} hot!", "why": "Finishes the dish perfectly.", "tip": "Garnish with fresh herbs."}
                ],
                "is_favorite": False
            }
        results.append(dynamic_recipe)
    
    # If we have some low score results but we still want to limit to top 3
    if len(results) > 3 and not any(r.get("id", "").startswith("dyn_") for r in results):
        results = results[:3]
        
    return jsonify(results), 200

@recipes_bp.route('/favorite/toggle', methods=['POST'])
def toggle_favorite():
    data = request.get_json()
    user_id = data.get('user_id')
    recipe_id = data.get('recipe_id')
    if not user_id or not recipe_id:
        return jsonify({"error": "Missing data"}), 400
    
    db = get_db()
    is_fav = False
    if db is not None:
        user_favs = db.favorites.find_one({"user_id": user_id})
        if not user_favs:
            db.favorites.insert_one({"user_id": user_id, "recipe_ids": [recipe_id]})
            is_fav = True
        else:
            ids = user_favs.get("recipe_ids", [])
            if recipe_id in ids:
                ids.remove(recipe_id)
                is_fav = False
            else:
                ids.append(recipe_id)
                is_fav = True
            db.favorites.update_one({"user_id": user_id}, {"$set": {"recipe_ids": ids}})
    else:
        store = get_memory_store()
        if user_id not in store["favorites"]:
            store["favorites"][user_id] = [recipe_id]
            is_fav = True
        else:
            ids = store["favorites"][user_id]
            if recipe_id in ids:
                ids.remove(recipe_id)
                is_fav = False
            else:
                ids.append(recipe_id)
                is_fav = True
    
    return jsonify({"is_favorite": is_fav}), 200

@recipes_bp.route('/favorites/<user_id>', methods=['GET'])
def get_favorites(user_id):
    db = get_db()
    fav_ids = []
    if db is not None:
        user_favs = db.favorites.find_one({"user_id": user_id})
        if user_favs:
            fav_ids = user_favs.get("recipe_ids", [])
    else:
        store = get_memory_store()
        fav_ids = store["favorites"].get(user_id, [])
    
    all_recipes = get_all_recipes_internal()
    favorites = [r for r in all_recipes if r["id"] in fav_ids]
    for r in favorites: r["is_favorite"] = True
    return jsonify(favorites), 200


# ===== AI RECIPE GENERATION =====
_CUISINE_DATA = {
    "Indian":      {"veg": ["Aloo Gobi","Dal Tadka","Chana Masala","Malai Kofta","Dum Aloo"],       "nonveg": ["Chicken Tikka Masala","Lamb Rogan Josh","Fish Amritsari","Egg Curry"],     "base": ["onion","tomato","garlic","ginger","cumin","turmeric","garam masala","salt"], "vp": ["paneer","chickpeas","lentils"],          "np": ["chicken","lamb","fish"],          "img": "🍛"},
    "Chinese":     {"veg": ["Kung Pao Tofu","Mapo Tofu","Buddha's Delight","Braised Eggplant"],  "nonveg": ["Kung Pao Chicken","Sweet & Sour Pork","Beef & Broccoli","Shrimp Stir-Fry"], "base": ["soy sauce","garlic","ginger","sesame oil","cornstarch","scallions"],          "vp": ["tofu","tempeh","edamame"],         "np": ["chicken","pork","beef","shrimp"],  "img": "🥢"},
    "Italian":     {"veg": ["Pasta Pomodoro","Margherita Pizza","Cacio e Pepe","Pesto Gnocchi"],   "nonveg": ["Chicken Piccata","Spaghetti Bolognese","Chicken Cacciatore"],              "base": ["olive oil","garlic","tomato","basil","parmesan","salt"],                     "vp": ["mozzarella","ricotta","eggs"],     "np": ["chicken","beef","pancetta"],       "img": "🍝"},
    "Mexican":     {"veg": ["Bean Burrito Bowl","Veggie Enchiladas","Black Bean Tacos"],           "nonveg": ["Chicken Tacos","Carnitas Bowl","Shrimp Fajitas"],                          "base": ["tortillas","lime juice","cilantro","cumin","chili powder","garlic"],          "vp": ["black beans","pinto beans","tofu"],"np": ["chicken","beef","pork","shrimp"],  "img": "🌮"},
    "Korean":      {"veg": ["Bibimbap","Japchae","Doenjang Jjigae","Sundubu Jjigae"],             "nonveg": ["Bulgogi","Dakgalbi","Samgyeopsal","Galbi"],                               "base": ["soy sauce","sesame oil","garlic","gochujang","sesame seeds","scallions"],    "vp": ["tofu","eggs","mushrooms"],         "np": ["beef","chicken","pork"],           "img": "🍲"},
    "Japanese":    {"veg": ["Vegetable Ramen","Tofu Teriyaki","Miso Soup Bowl","Veggie Sushi Roll"],"nonveg": ["Teriyaki Chicken","Salmon Bowl","Chicken Katsu","Tuna Sashimi Bowl"],   "base": ["soy sauce","mirin","sake","dashi","sesame oil","ginger"],                   "vp": ["tofu","edamame","eggs"],           "np": ["chicken","salmon","tuna","pork"],  "img": "🍱"},
    "American":    {"veg": ["Mac & Cheese","Veggie Burger","Loaded Nachos","Grilled Cheese"],      "nonveg": ["BBQ Chicken","Beef Burger","Buffalo Wings","Club Sandwich"],               "base": ["butter","onion","garlic","salt","black pepper","olive oil"],                 "vp": ["cheddar cheese","beans","eggs"],   "np": ["chicken","beef","turkey"],         "img": "🍔"},
    "Continental": {"veg": ["Pasta Primavera","Ratatouille","Mushroom Quiche","Caprese Salad"],   "nonveg": ["Chicken Marsala","Beef Stroganoff","Coq au Vin","Lamb Chops"],           "base": ["butter","olive oil","onion","garlic","cream","white wine","fresh herbs"],   "vp": ["mushrooms","cheese","eggs"],       "np": ["chicken","beef","lamb"],           "img": "🍽️"},
}

def _ai_generate(cuisine, category, spice_pref, health_pref):
    import uuid, random
    data = _CUISINE_DATA.get(cuisine, _CUISINE_DATA["Indian"])
    is_veg = category == "vegetarian"
    dish_name = random.choice(data["veg"] if is_veg else data["nonveg"])
    protein = random.choice(data["vp"] if is_veg else data["np"])
    ingredients = data["base"] + [protein, "fresh herbs", "salt", "black pepper"]
    calories = 290 if health_pref == "healthy" else 480 if health_pref == "fast_food" else 370
    spicy_tag = "spicy" if spice_pref == "spicy" else "mild"
    steps = [
        {"step": 1, "title": "Mise en Place",        "instruction": f"Gather and prep all ingredients: mince garlic, dice onion, and prepare {protein} as needed.",                                      "why": "Having everything ready before cooking prevents mistakes and keeps the process smooth.",             "tip": "Read all steps through once before starting."},
        {"step": 2, "title": "Build Aromatic Base",  "instruction": f"Heat oil in a pan. Add base aromatics ({', '.join(data['base'][:3])}) and cook 2-3 minutes until fragrant.",               "why": f"A well-developed aromatic base is the foundation of {cuisine} cooking.",                         "tip": "Medium heat here — aromatics should sizzle gently, not burn."},
        {"step": 3, "title": f"Cook the {protein.title()}", "instruction": f"Add {protein} and cook appropriately, seasoning with {cuisine}-inspired spices throughout.",                         "why": f"Proper cooking of {protein} ensures ideal texture, flavor, and food safety.",                    "tip": "Season in layers — add a pinch of salt each stage rather than all at the end."},
        {"step": 4, "title": "Combine & Simmer",     "instruction": "Bring all components together and simmer 5-8 minutes, allowing flavors to meld harmoniously.",                               "why": "Simmering integrates individual flavors into a cohesive, balanced dish.",                          "tip": "Taste frequently — adjust salt, acid (lemon/vinegar), and heat before serving."},
        {"step": 5, "title": "Plate & Serve",        "instruction": f"Plate elegantly with fresh herbs. Pair with a classic {cuisine} side dish and serve immediately.",                          "why": "Thoughtful presentation enhances the overall dining experience.",                                 "tip": "A finishing drizzle of quality oil or fresh citrus elevates any dish instantly."}
    ]
    return {
        "id": "ai_" + str(uuid.uuid4())[:8],
        "name": dish_name,
        "category": category,
        "cuisine": cuisine,
        "image": data["img"],
        "duration": "35 mins",
        "difficulty": "Medium",
        "tags": ["AI-generated", cuisine.lower(), spicy_tag, "healthy" if health_pref == "healthy" else "comfort"],
        "ingredients": ingredients,
        "nutrition": {
            "calories": calories,
            "protein": 22 if is_veg else 30,
            "carbohydrates": 35,
            "fats": 10 if health_pref == "healthy" else 20,
            "fiber": 6 if is_veg else 3,
            "vitamins": "A, B, C, D",
            "minerals": "Iron, Potassium, Calcium"
        },
        "steps": steps,
        "is_favorite": False,
        "ai_generated": True
    }

@recipes_bp.route('/generate', methods=['POST'])
def generate_recipe():
    data = request.get_json()
    cuisine  = data.get('cuisine', 'Indian').strip()
    category = data.get('category', 'vegetarian').strip()
    prefs    = data.get('preferences', {})
    recipe   = _ai_generate(cuisine, category,
                            prefs.get('spice_preference', 'medium'),
                            prefs.get('health_preference', 'balanced'))
    # Persist in memory store so /recipes/<id> can return it
    store = get_memory_store()
    if not any(r.get('id') == recipe['id'] for r in store['recipes']):
        store['recipes'].append(recipe)
    return jsonify(recipe), 200

@recipes_bp.route('/meal-plan', methods=['POST'])
def generate_meal_plan():
    data = request.get_json()
    category = data.get("category", "vegetarian")
    prefs = data.get("preferences", {})
    recipes = get_all_recipes_internal(category)
    import random
    
    # Filter by user preferences if possible
    if prefs.get("cuisine_preference") and prefs["cuisine_preference"] != "all":
        filtered = [r for r in recipes if r.get("cuisine", "").lower() == prefs["cuisine_preference"].lower()]
        if len(filtered) >= 9:
            recipes = filtered
            
    if len(recipes) < 9:
        # Pad with AI generated recipes to ensure we have 9 meals
        needed = 9 - len(recipes)
        for _ in range(needed):
            recipes.append(_ai_generate(random.choice(list(_CUISINE_DATA.keys())), category, "medium", "balanced"))
            
    random.shuffle(recipes)
    meal_plan = {
        "Day 1": {"Breakfast": recipes[0], "Lunch": recipes[1], "Dinner": recipes[2]},
        "Day 2": {"Breakfast": recipes[3], "Lunch": recipes[4], "Dinner": recipes[5]},
        "Day 3": {"Breakfast": recipes[6], "Lunch": recipes[7], "Dinner": recipes[8]}
    }
    
    return jsonify(meal_plan), 200


# ===== AI RECIPE GENERATION ENDPOINT (TheMealDB + Smart Template) =====

_ENHANCED_INGREDIENTS = {
    "Indian":      {"base": ["2 tbsp vegetable oil", "1 large onion, diced", "3 cloves garlic, minced", "1 inch ginger, grated", "1 tsp cumin seeds", "1 tsp turmeric powder", "1 tsp garam masala", "1 tsp salt"],
                    "vp": ["200g paneer, cubed", "1 cup chickpeas, drained", "1 cup red lentils"],
                    "np": ["500g chicken thigh, cubed", "400g lamb, cubed", "300g fish fillet, cubed"],
                    "extras": ["1 cup tomato puree", "1/2 cup yogurt", "Fresh cilantro for garnish"]},
    "Chinese":     {"base": ["2 tbsp soy sauce", "3 cloves garlic, minced", "1 inch ginger, sliced", "1 tbsp sesame oil", "1 tbsp cornstarch", "2 scallions, chopped"],
                    "vp": ["300g firm tofu, cubed", "1 cup tempeh, sliced", "1 cup edamame"],
                    "np": ["500g chicken breast, sliced", "400g pork loin, sliced", "400g beef sirloin, sliced", "300g shrimp, peeled"],
                    "extras": ["1 tbsp rice vinegar", "1 tsp sugar", "1 cup mixed bell peppers, sliced"]},
    "Italian":     {"base": ["3 tbsp olive oil", "4 cloves garlic, minced", "400g canned tomatoes", "1/4 cup fresh basil", "1/2 cup parmesan, grated", "1 tsp salt"],
                    "vp": ["250g mozzarella, sliced", "1 cup ricotta cheese", "2 large eggs"],
                    "np": ["400g chicken breast, pounded", "500g ground beef", "150g pancetta, diced"],
                    "extras": ["400g pasta of choice", "1 tsp dried oregano", "Black pepper to taste"]},
    "Mexican":     {"base": ["8 small tortillas", "2 tbsp lime juice", "1/4 cup fresh cilantro", "1 tsp cumin", "1 tsp chili powder", "3 cloves garlic, minced"],
                    "vp": ["1 can black beans, drained", "1 can pinto beans", "200g firm tofu, crumbled"],
                    "np": ["500g chicken thigh, sliced", "400g ground beef", "400g pork shoulder, shredded", "300g shrimp, peeled"],
                    "extras": ["1 avocado, sliced", "1/2 cup sour cream", "1 cup shredded cheese"]},
    "Korean":      {"base": ["2 tbsp soy sauce", "1 tbsp sesame oil", "4 cloves garlic, minced", "2 tbsp gochujang", "1 tbsp sesame seeds", "3 scallions, sliced"],
                    "vp": ["300g firm tofu, sliced", "2 large eggs", "200g mixed mushrooms"],
                    "np": ["500g beef ribeye, sliced thin", "400g chicken thigh, cubed", "400g pork belly, sliced"],
                    "extras": ["2 cups cooked rice", "1 tbsp rice vinegar", "1 cup kimchi"]},
    "Japanese":    {"base": ["3 tbsp soy sauce", "2 tbsp mirin", "1 tbsp sake", "1 tsp dashi powder", "1 tbsp sesame oil", "1 inch ginger, grated"],
                    "vp": ["300g silken tofu", "1 cup edamame, shelled", "2 large eggs"],
                    "np": ["400g chicken thigh, sliced", "300g salmon fillet", "300g tuna, sashimi-grade", "400g pork cutlet"],
                    "extras": ["2 cups sushi rice, cooked", "1 sheet nori, shredded", "Pickled ginger for serving"]},
    "American":    {"base": ["2 tbsp butter", "1 medium onion, diced", "2 cloves garlic, minced", "1 tsp salt", "1/2 tsp black pepper", "1 tbsp olive oil"],
                    "vp": ["2 cups cheddar cheese, shredded", "1 can beans, drained", "3 large eggs"],
                    "np": ["500g chicken breast", "500g ground beef", "400g turkey breast"],
                    "extras": ["4 burger buns", "Lettuce and tomato slices", "Ketchup and mustard"]},
    "Continental": {"base": ["3 tbsp butter", "2 tbsp olive oil", "1 medium onion, finely diced", "3 cloves garlic, minced", "1/2 cup heavy cream", "1/4 cup white wine", "2 tbsp fresh herbs (thyme, rosemary)"],
                    "vp": ["250g mixed mushrooms, sliced", "200g gruyere cheese, grated", "3 large eggs"],
                    "np": ["500g chicken breast, butterflied", "400g beef tenderloin", "400g lamb rack"],
                    "extras": ["2 cups baby potatoes, halved", "1 cup green beans, trimmed", "Fresh parsley for garnish"]},
}

_CUISINE_EMOJIS = {
    "indian": "🍛", "chinese": "🥢", "italian": "🍝", "mexican": "🌮",
    "korean": "🍲", "japanese": "🍱", "american": "🍔", "continental": "🍽️",
    "thai": "🍜", "french": "🥐", "mediterranean": "🥗", "fusion": "✨",
}

def _detect_cuisine(query):
    """Detect cuisine from query string."""
    q = query.lower()
    cuisine_keywords = {
        "Indian": ["indian", "curry", "masala", "tikka", "biryani", "dal", "paneer", "naan", "samosa", "tandoori"],
        "Chinese": ["chinese", "kung pao", "mapo", "stir fry", "wonton", "dim sum", "fried rice", "chow mein"],
        "Italian": ["italian", "pasta", "pizza", "risotto", "lasagna", "pesto", "carbonara", "bolognese"],
        "Mexican": ["mexican", "taco", "burrito", "enchilada", "fajita", "quesadilla", "guacamole", "salsa"],
        "Korean": ["korean", "bibimbap", "bulgogi", "kimchi", "japchae", "tteokbokki", "gochujang"],
        "Japanese": ["japanese", "sushi", "ramen", "teriyaki", "miso", "katsu", "tempura", "udon"],
        "American": ["american", "burger", "bbq", "mac and cheese", "buffalo wings", "hotdog", "pancakes"],
        "Continental": ["continental", "stroganoff", "quiche", "ratatouille", "coq au vin", "gratin"],
        "Thai": ["thai", "pad thai", "green curry", "tom yum", "tom kha", "satay", "basil chicken"],
        "French": ["french", "croissant", "souffle", "bouillabaisse", "crepe", "baguette"],
        "Mediterranean": ["mediterranean", "hummus", "falafel", "tzatziki", "shawarma", "pita"],
    }
    for cuisine, keywords in cuisine_keywords.items():
        for kw in keywords:
            if kw in q:
                return cuisine
    return "Fusion"

def _build_template_recipe(query, servings):
    """Generate a detailed template-based recipe using _CUISINE_DATA + enhanced ingredients."""
    import random as _rand

    q = query.lower().strip()
    cuisine = _detect_cuisine(q)
    is_veg = any(w in q for w in ["veg", "vegan", "vegetarian", "tofu", "paneer"])
    category = "vegetarian" if is_veg else "non-vegetarian"

    # Determine dish name
    dish_name = query.strip().title()

    # Extract specific protein from query if possible
    main_protein = None
    for p_kw, p_val in [
        ("chicken", "500g chicken breast, cubed"),
        ("beef", "400g beef sirloin, sliced"),
        ("pork", "400g pork tenderloin, sliced"),
        ("lamb", "400g lamb, cubed"),
        ("fish", "300g white fish fillet, cubed"),
        ("shrimp", "300g shrimp, peeled"),
        ("prawn", "300g prawns, peeled"),
        ("paneer", "200g paneer, cubed"),
        ("tofu", "300g firm tofu, cubed"),
        ("egg", "4 large eggs")
    ]:
        if p_kw in q:
            main_protein = p_val
            break
            
    if not main_protein:
        words = q.split()
        if len(words) > 1 and not is_veg:
            main_protein = f"500g {words[-1]}"
        elif is_veg:
            main_protein = "200g mixed vegetables or tofu"
        else:
            main_protein = f"500g {q} (main ingredient)"

    # Build ingredients with quantities
    enh = _ENHANCED_INGREDIENTS.get(cuisine)
    if enh:
        base_ings = list(enh["base"])
        protein_ing = main_protein if main_protein else _rand.choice(enh["vp"] if is_veg else enh["np"])
        extras = list(enh.get("extras", []))
        ingredients = base_ings + [protein_ing] + extras
    else:
        # Fallback for cuisines not in enhanced data
        ingredients = [
            "2 tbsp vegetable oil", "1 medium onion, diced", "3 cloves garlic, minced",
            "1 tsp salt", "1/2 tsp black pepper", "1 tsp paprika",
            main_protein, "2 cups mixed vegetables",
            "1 cup broth or water", "Fresh herbs for garnish"
        ]

    emoji = _CUISINE_EMOJIS.get(cuisine.lower(), "🍽️")
    recipe_id = "ai_" + hashlib.md5(query.lower().strip().encode()).hexdigest()[:10]

    steps = [
        {"step": 1, "title": "Prep Ingredients",
         "instruction": f"Gather all ingredients for {dish_name}. Wash, peel, and chop vegetables. Measure out spices and sauces. Pat protein dry if using meat or press tofu if using tofu.",
         "why": "Proper mise en place ensures smooth cooking without scrambling for ingredients mid-recipe.",
         "tip": "Read through all the steps once before starting to cook."},
        {"step": 2, "title": "Build the Flavor Base",
         "instruction": f"Heat oil in a large pan or wok over medium heat. Add aromatics (onion, garlic, ginger if using) and sauté for 2-3 minutes until fragrant and translucent.",
         "why": f"Aromatics form the backbone of {cuisine} cuisine — they release essential oils when gently heated.",
         "tip": "Keep the heat at medium. Burnt garlic turns bitter and ruins the dish."},
        {"step": 3, "title": "Add Spices & Seasonings",
         "instruction": f"Add the dry spices and seasonings. Stir constantly for 30-60 seconds to bloom the spices and release their full aroma.",
         "why": "Blooming spices in oil activates fat-soluble flavor compounds that water alone cannot extract.",
         "tip": "If spices start to smoke, reduce heat immediately and add a splash of water."},
        {"step": 4, "title": "Cook the Main Protein",
         "instruction": f"Add your protein to the pan. Cook for 5-7 minutes, turning occasionally, until golden on the outside. Season lightly as you go.",
         "why": "Browning creates a Maillard reaction — complex flavors that elevate the entire dish.",
         "tip": "Don't move the protein too much — let it develop a golden crust before flipping."},
        {"step": 5, "title": "Combine & Simmer",
         "instruction": f"Add remaining ingredients (sauces, liquids, vegetables). Stir to combine, bring to a gentle simmer, and cook for 10-15 minutes with the lid partially on.",
         "why": "Simmering allows all the flavors to meld together into a harmonious, well-rounded dish.",
         "tip": "Taste and adjust seasoning — a squeeze of lemon or pinch of sugar can balance flavors."},
        {"step": 6, "title": "Plate & Serve",
         "instruction": f"Remove from heat. Plate your {dish_name} beautifully and garnish with fresh herbs. Serve immediately while hot.",
         "why": "Presentation matters — we eat with our eyes first, and fresh garnishes add brightness.",
         "tip": "A final drizzle of quality oil or a squeeze of citrus can elevate the dish dramatically."}
    ]

    return {
        "id": recipe_id,
        "name": dish_name,
        "category": category,
        "cuisine": cuisine,
        "image": emoji,
        "duration": "40 mins",
        "difficulty": "Medium",
        "servings": servings,
        "tags": ["AI-generated", cuisine.lower()],
        "ingredients": ingredients,
        "nutrition": {
            "calories": 380,
            "protein": 18 if is_veg else 28,
            "carbohydrates": 40,
            "fats": 14,
            "fiber": 6 if is_veg else 3,
            "vitamins": "A, B, C",
            "minerals": "Iron, Calcium, Potassium"
        },
        "steps": steps,
        "is_favorite": False,
        "ai_generated": True
    }


@recipes_bp.route('/ai-generate', methods=['POST'])
def ai_generate_recipe():
    """Generate a recipe by querying TheMealDB first, falling back to smart template."""
    import urllib.request, urllib.parse

    data = request.get_json() or {}
    query = data.get('query', '').strip()
    servings = data.get('servings', 4)

    if not query:
        return jsonify({"error": "Query is required"}), 400

    recipe_id = "ai_" + hashlib.md5(query.lower().strip().encode()).hexdigest()[:10]

    # Check if we already generated this exact recipe
    saved = _load_saved_recipes()
    existing = next((r for r in saved if r.get('id') == recipe_id), None)
    if existing:
        existing['servings'] = servings
        return jsonify(existing), 200

    generated_recipe = None

    # --- Attempt 1: Fetch from TheMealDB ---
    try:
        url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=5)
        api_data = json.loads(res.read())

        if api_data and api_data.get('meals'):
            meal = api_data['meals'][0]

            # Extract ingredients with quantities
            ingredients = []
            for i in range(1, 21):
                ing = meal.get(f'strIngredient{i}')
                measure = meal.get(f'strMeasure{i}')
                if ing and ing.strip():
                    part = f"{measure.strip()} {ing.strip()}" if measure and measure.strip() else ing.strip()
                    ingredients.append(part)

            # Parse instructions into steps
            raw_instructions = meal.get('strInstructions', '').replace('\r\n', '\n').split('\n')
            steps = []
            step_idx = 1
            for inst in raw_instructions:
                line = inst.strip()
                if line:
                    steps.append({
                        "step": step_idx,
                        "title": f"Step {step_idx}",
                        "instruction": line,
                        "why": "Follow the authentic recipe for best results.",
                        "tip": "Adjust seasoning to your taste as you cook."
                    })
                    step_idx += 1

            meal_category = meal.get('strCategory', '').lower()
            is_veg = meal_category in ['vegetarian', 'vegan', 'dessert', 'side']
            cuisine_area = meal.get('strArea', 'Fusion')
            emoji = _CUISINE_EMOJIS.get(cuisine_area.lower(), "🍽️")

            generated_recipe = {
                "id": recipe_id,
                "name": meal['strMeal'],
                "category": "vegetarian" if is_veg else "non-vegetarian",
                "cuisine": cuisine_area,
                "image": emoji,
                "duration": "45 mins",
                "difficulty": "Medium",
                "servings": servings,
                "tags": ["AI-generated", cuisine_area.lower()],
                "ingredients": ingredients,
                "nutrition": {
                    "calories": 400, "protein": 20, "carbohydrates": 45,
                    "fats": 15, "fiber": 5, "vitamins": "A, B, C",
                    "minerals": "Iron, Calcium"
                },
                "steps": steps,
                "is_favorite": False,
                "ai_generated": True
            }
    except Exception:
        pass

    # --- Attempt 2: Smart template fallback ---
    if not generated_recipe:
        generated_recipe = _build_template_recipe(query, servings)

    # Persist to saved_recipes.json
    _save_recipe_to_file(generated_recipe)

    # Also add to memory store for current session
    store = get_memory_store()
    if not any(r.get('id') == generated_recipe['id'] for r in store['recipes']):
        store['recipes'].append(generated_recipe)

    return jsonify(generated_recipe), 200

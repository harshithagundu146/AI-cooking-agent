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


# ===== DISH-SPECIFIC RECIPE KNOWLEDGE BASE =====
_DISH_RECIPES = {
    "butter chicken": {
        "name": "Butter Chicken (Murgh Makhani)", "cuisine": "Indian", "category": "non-vegetarian",
        "duration": "50 mins", "difficulty": "Medium",
        "ingredients": [
            "800g boneless chicken thighs, cut into chunks",
            "2 tbsp plain yogurt", "1 tbsp lemon juice", "2 tsp kashmiri red chili powder",
            "1 tsp garam masala", "1 tsp cumin powder", "1 tsp coriander powder",
            "1 tsp turmeric powder", "3 tbsp butter", "2 tbsp vegetable oil",
            "1 large onion, finely chopped", "4 cloves garlic, minced",
            "1 inch ginger, grated", "400g crushed tomatoes",
            "1 cup heavy cream", "1 tbsp sugar", "1 tsp fenugreek leaves (kasuri methi)",
            "Salt to taste", "Fresh coriander for garnish"
        ],
        "steps": [
            {"step":1,"title":"Marinate the Chicken","instruction":"Mix yogurt, lemon juice, 1 tsp red chili powder, garam masala, and salt in a bowl. Add chicken pieces and coat well. Cover and refrigerate for at least 30 minutes (or overnight).","why":"Yogurt tenderizes the meat and the spices penetrate deep for maximum flavor.","tip":"The longer you marinate, the more flavorful and tender the chicken will be."},
            {"step":2,"title":"Cook the Chicken","instruction":"Heat 1 tbsp oil in a pan over high heat. Add marinated chicken and cook for 8-10 minutes, turning until nicely charred on the outside. Remove and set aside.","why":"High heat creates a charred exterior similar to a tandoor, adding smoky flavor.","tip":"Don't overcrowd the pan — cook in batches if needed for better browning."},
            {"step":3,"title":"Build the Makhani Sauce","instruction":"In the same pan, melt butter with remaining oil over medium heat. Add onions and cook for 8 minutes until golden. Add garlic and ginger, cook 2 minutes until fragrant.","why":"Slowly caramelizing onions builds a sweet, deep flavor base for the sauce.","tip":"Don't rush this step — properly cooked onions make all the difference."},
            {"step":4,"title":"Add Tomatoes and Spices","instruction":"Add remaining red chili powder, cumin, coriander, turmeric and stir for 1 minute. Pour in crushed tomatoes and cook on medium heat for 15 minutes until oil separates.","why":"Cooking the tomato paste until oil separates removes raw tomato taste and concentrates flavor.","tip":"You can blend the sauce at this point for a smoother restaurant-style gravy."},
            {"step":5,"title":"Add Cream and Chicken","instruction":"Stir in heavy cream and sugar. Add the cooked chicken and simmer on low heat for 10 minutes. Crush kasuri methi between your palms and stir in.","why":"Cream adds richness while kasuri methi gives the authentic Makhani aroma.","tip":"Add cream off the heat to prevent curdling if using full-fat cream."},
            {"step":6,"title":"Finish and Serve","instruction":"Adjust salt and seasoning. Garnish with fresh coriander and a drizzle of cream. Serve hot with naan, roti, or steamed basmati rice.","why":"Fresh garnish adds color and aroma, making the dish visually and aromatically inviting.","tip":"A small knob of butter swirled in at the end gives an ultra-glossy, restaurant finish."}
        ],
        "nutrition": {"calories": 520, "protein": 38, "carbohydrates": 18, "fats": 32, "fiber": 3, "vitamins": "A, B12, C, D", "minerals": "Iron, Calcium, Potassium"}
    },
    "chicken biryani": {
        "name": "Chicken Biryani", "cuisine": "Indian", "category": "non-vegetarian",
        "duration": "75 mins", "difficulty": "Hard",
        "ingredients": [
            "1kg bone-in chicken pieces", "3 cups basmati rice, soaked 30 mins",
            "1 cup plain yogurt", "2 large onions, thinly sliced",
            "4 tbsp ghee or oil", "4 cloves garlic, minced", "2 inch ginger, grated",
            "2 tsp biryani masala", "1 tsp red chili powder", "1 tsp turmeric",
            "1 tsp garam masala", "4 green cardamoms", "4 cloves", "2 bay leaves",
            "1 cinnamon stick", "Saffron strands soaked in 4 tbsp warm milk",
            "Fresh mint leaves", "Fresh coriander", "2 tbsp fried onions", "Salt to taste"
        ],
        "steps": [
            {"step":1,"title":"Marinate Chicken","instruction":"Mix chicken with yogurt, garlic, ginger, biryani masala, red chili powder, turmeric, and salt. Marinate for 1 hour minimum or overnight in the fridge.","why":"Long marination ensures the chicken is deeply flavored and tender throughout.","tip":"Yogurt acts as a tenderizer — don't skip it!"},
            {"step":2,"title":"Fry the Onions","instruction":"Heat 3 tbsp ghee in a heavy pan. Fry sliced onions on medium-high heat for 20-25 minutes, stirring frequently, until deep golden brown and crispy.","why":"Crispy fried onions (birista) are the heart of biryani flavor — they add sweetness and crunch.","tip":"Spread on paper towels immediately after frying to keep them crispy."},
            {"step":3,"title":"Cook the Chicken","instruction":"In the same ghee, add whole spices (cardamom, cloves, bay leaves, cinnamon). Add marinated chicken and cook for 15-20 minutes, stirring, until chicken is 80% cooked and gravy thickens.","why":"Partially cooking the chicken here ensures it finishes perfectly during the dum process.","tip":"The gravy should be thick enough to coat the rice but not watery."},
            {"step":4,"title":"Par-Cook the Rice","instruction":"Boil a large pot of water with whole spices and salt. Add soaked rice and cook for exactly 7 minutes until 70% done. Drain immediately.","why":"Par-cooking the rice precisely ensures it finishes perfectly in the dum without becoming mushy.","tip":"The rice should still have a tiny hard center when you drain it."},
            {"step":5,"title":"Layer the Biryani","instruction":"In a heavy-bottomed pot, layer half the chicken, then half the rice, then mint leaves and fried onions. Repeat layers. Drizzle saffron milk and 1 tbsp ghee over the top.","why":"Layering creates pockets of flavor so every spoonful has rice, chicken, and spices.","tip":"Seal the pot with foil before the lid for a better dum (steam cooking)."},
            {"step":6,"title":"Dum Cook and Serve","instruction":"Place the pot on a tawa (griddle) over the lowest heat possible. Cook for 25-30 minutes on dum. Let rest 10 minutes before gently mixing and serving.","why":"Slow steam cooking (dum) allows all flavors to meld together beautifully.","tip":"Use the tawa/griddle to prevent the bottom from burning during dum cooking."}
        ],
        "nutrition": {"calories": 680, "protein": 42, "carbohydrates": 72, "fats": 22, "fiber": 4, "vitamins": "A, B6, B12, C", "minerals": "Iron, Calcium, Zinc"}
    },
    "pad thai": {
        "name": "Pad Thai", "cuisine": "Thai", "category": "non-vegetarian",
        "duration": "30 mins", "difficulty": "Medium",
        "ingredients": [
            "200g flat rice noodles", "200g medium shrimp or chicken strips",
            "3 tbsp vegetable oil", "2 eggs", "3 cloves garlic, minced",
            "2 shallots, thinly sliced", "3 tbsp tamarind paste",
            "2 tbsp fish sauce", "1 tbsp oyster sauce", "1 tbsp sugar",
            "100g bean sprouts", "3 spring onions, cut into 2-inch pieces",
            "4 tbsp roasted peanuts, crushed", "1 lime, cut into wedges",
            "Fresh coriander", "Dried chili flakes to taste"
        ],
        "steps": [
            {"step":1,"title":"Prepare Noodles and Sauce","instruction":"Soak rice noodles in warm water for 20-30 minutes until flexible but still firm. Mix tamarind paste, fish sauce, oyster sauce, and sugar in a bowl to make the Pad Thai sauce.","why":"Pre-soaked noodles stir-fry evenly without breaking or sticking together.","tip":"Never use boiling water to soak — it makes noodles too soft before they hit the wok."},
            {"step":2,"title":"High Heat Wok Cooking","instruction":"Heat wok or large pan over the highest heat until smoking. Add oil, then garlic and shallots. Stir fry for 30 seconds until fragrant.","why":"Very high heat (wok hei) gives Pad Thai its characteristic smoky, slightly charred flavor.","tip":"If your wok isn't smoking hot, your Pad Thai will steam instead of stir-fry."},
            {"step":3,"title":"Cook the Protein","instruction":"Add shrimp or chicken to the wok. Cook for 2-3 minutes, tossing constantly, until cooked through. Push to the side of the wok.","why":"Cooking protein separately first ensures it's properly cooked and not steamed by other ingredients.","tip":"Shrimp is ready when it turns pink and curls into a C-shape."},
            {"step":4,"title":"Scramble Eggs and Add Noodles","instruction":"Crack eggs into the empty side of the wok, scramble quickly for 30 seconds. Add drained noodles and pour Pad Thai sauce over everything. Toss vigorously for 2-3 minutes.","why":"The sauce caramelizes slightly on the hot noodles, creating the signature sticky-glossy coating.","tip":"Keep tossing constantly — noodles stick together if left still."},
            {"step":5,"title":"Add Vegetables and Finish","instruction":"Add bean sprouts and spring onions. Toss for 1 minute until slightly wilted but still crunchy. Remove from heat.","why":"Bean sprouts should retain some crunch for textural contrast.","tip":"Add sprouts last so they don't become completely limp."},
            {"step":6,"title":"Plate and Garnish","instruction":"Serve immediately garnished with crushed peanuts, fresh coriander, lime wedges, and chili flakes. Squeeze lime over the dish just before eating.","why":"Fresh lime juice brightens all the flavors and cuts through the richness.","tip":"The lime squeeze at the table is essential — don't serve without it!"}
        ],
        "nutrition": {"calories": 480, "protein": 28, "carbohydrates": 58, "fats": 16, "fiber": 3, "vitamins": "A, B6, C, E", "minerals": "Iron, Calcium, Phosphorus"}
    },
    "pasta carbonara": {
        "name": "Spaghetti Carbonara", "cuisine": "Italian", "category": "non-vegetarian",
        "duration": "25 mins", "difficulty": "Medium",
        "ingredients": [
            "400g spaghetti", "200g pancetta or guanciale, diced",
            "4 large egg yolks", "2 whole eggs", "100g Pecorino Romano, finely grated",
            "50g Parmesan, finely grated", "2 cloves garlic (optional)",
            "Freshly cracked black pepper (generous amount)", "Salt for pasta water"
        ],
        "steps": [
            {"step":1,"title":"Cook Pasta in Salty Water","instruction":"Bring a large pot of heavily salted water to a boil. Cook spaghetti until 1 minute less than al dente. Reserve 2 cups of pasta cooking water before draining.","why":"Pasta water is starchy gold — it's the secret to creamy carbonara without cream.","tip":"The water should taste like the sea — this is your only chance to season the pasta itself."},
            {"step":2,"title":"Render the Pancetta","instruction":"Cook pancetta or guanciale in a large pan over medium heat for 8-10 minutes until crispy and golden. Remove from heat and let the pan cool slightly.","why":"Crispy pancetta adds texture and its rendered fat becomes part of the sauce.","tip":"No oil needed — the pork fat renders out naturally."},
            {"step":3,"title":"Make the Egg Sauce","instruction":"Whisk egg yolks, whole eggs, grated Pecorino, and Parmesan in a bowl. Add generous black pepper. This is your carbonara sauce.","why":"The eggs form a custard-like sauce when gently heated by the pasta — no cooking needed.","tip":"Room temperature eggs work better — they integrate more smoothly."},
            {"step":4,"title":"Combine with Perfect Timing","instruction":"Add hot drained pasta directly to the pan with pancetta (off heat). Toss vigorously. Pour egg mixture over, tossing constantly and adding pasta water splash by splash to reach creamy consistency.","why":"The residual heat cooks the eggs gently without scrambling them — timing is everything.","tip":"Work fast and keep tossing — if it looks too thick, add more pasta water immediately."},
            {"step":5,"title":"Serve Immediately","instruction":"Divide into warm bowls. Top with extra Pecorino, cracked black pepper, and any crispy pancetta bits left in the pan. Serve instantly.","why":"Carbonara waits for no one — it thickens as it cools and must be eaten fresh.","tip":"Warm your serving bowls with hot water first so the pasta stays hot longer."}
        ],
        "nutrition": {"calories": 620, "protein": 32, "carbohydrates": 65, "fats": 25, "fiber": 3, "vitamins": "B6, B12, D", "minerals": "Calcium, Iron, Phosphorus"}
    },
    "tiramisu": {
        "name": "Tiramisu", "cuisine": "Italian", "category": "vegetarian",
        "duration": "30 mins + 4 hours chilling", "difficulty": "Medium",
        "ingredients": [
            "300g ladyfinger biscuits (savoiardi)", "500g mascarpone cheese",
            "4 large eggs, separated", "100g caster sugar",
            "300ml strong espresso, cooled", "3 tbsp Marsala wine or rum (optional)",
            "4 tbsp cocoa powder, for dusting", "Dark chocolate shavings for garnish"
        ],
        "steps": [
            {"step":1,"title":"Make the Espresso Mixture","instruction":"Brew strong espresso and let it cool to room temperature. Mix in Marsala wine or rum if using. Pour into a shallow bowl for dipping.","why":"Cool coffee prevents the ladyfingers from becoming too soggy when dipped.","tip":"Use proper espresso — instant coffee won't give the same intense flavor."},
            {"step":2,"title":"Beat Egg Yolks and Sugar","instruction":"Whisk egg yolks and sugar in a bowl for 5-6 minutes until pale, thick, and doubled in volume. Fold in mascarpone gently until smooth.","why":"Whisking yolks with sugar creates a sabayon-like base that gives tiramisu its creamy richness.","tip":"The mixture should fall in thick ribbons from the whisk when done."},
            {"step":3,"title":"Whip Egg Whites","instruction":"In a clean dry bowl, whisk egg whites until stiff peaks form. Gently fold into the mascarpone mixture in three additions using a large metal spoon.","why":"Folded egg whites make the cream light and airy rather than heavy and dense.","tip":"Any fat in the bowl will prevent whites from whipping — ensure bowl is perfectly clean."},
            {"step":4,"title":"Layer the Tiramisu","instruction":"Quickly dip each ladyfinger in espresso (1 second per side) and arrange in a single layer in your dish. Spread half the mascarpone cream on top. Repeat with another layer of dipped ladyfingers and remaining cream.","why":"Quick dipping (not soaking) keeps ladyfingers moist but not mushy.","tip":"Work quickly — over-soaked ladyfingers fall apart and make a soggy mess."},
            {"step":5,"title":"Chill and Serve","instruction":"Cover with cling film and refrigerate for at least 4 hours (overnight is best). Just before serving, dust generously with cocoa powder through a fine sieve.","why":"Chilling allows all the layers to set and flavors to meld beautifully.","tip":"Dust the cocoa right before serving — it can turn damp if applied too early."}
        ],
        "nutrition": {"calories": 420, "protein": 10, "carbohydrates": 45, "fats": 22, "fiber": 1, "vitamins": "A, B12, D", "minerals": "Calcium, Phosphorus"}
    },
    "sushi roll": {
        "name": "Sushi Roll (Maki)", "cuisine": "Japanese", "category": "non-vegetarian",
        "duration": "45 mins", "difficulty": "Hard",
        "ingredients": [
            "2 cups sushi rice", "2.5 cups water",
            "3 tbsp rice vinegar", "1 tbsp sugar", "1 tsp salt",
            "4 sheets nori (seaweed)", "200g fresh sushi-grade salmon or tuna",
            "1 avocado, sliced", "1 cucumber, julienned",
            "Soy sauce for serving", "Pickled ginger (gari) for serving",
            "Wasabi for serving", "Sesame seeds for garnish"
        ],
        "steps": [
            {"step":1,"title":"Cook Perfect Sushi Rice","instruction":"Wash rice until water runs clear. Cook in rice cooker or pot with 2.5 cups water. Mix vinegar, sugar, and salt until dissolved. Fold gently into hot cooked rice with a wooden spoon. Fan while mixing to cool.","why":"Properly seasoned, shiny sushi rice is the foundation of great sushi.","tip":"Use a wooden spoon and fan simultaneously — the fanning creates the characteristic glossy finish."},
            {"step":2,"title":"Prepare the Fillings","instruction":"Slice fish into long strips about 1cm thick. Cut avocado and cucumber into similar-sized strips. Lay out all ingredients before rolling.","why":"Having everything ready before assembly ensures smooth rolling without the rice drying out.","tip":"Dip your knife in water between cuts for clean, precise slices of fish."},
            {"step":3,"title":"Set Up Rolling Station","instruction":"Place a bamboo mat on a flat surface and cover with cling film. Place a nori sheet shiny-side down on the mat. Wet your hands to prevent sticking.","why":"Damp hands prevent rice from sticking to you instead of the nori.","tip":"Keep a bowl of water handy to constantly re-wet your hands during rolling."},
            {"step":4,"title":"Spread Rice and Add Filling","instruction":"Spread a thin, even layer of rice over the nori, leaving a 2cm border at the far edge. Arrange fish, avocado, and cucumber in a line across the center.","why":"Even rice layer prevents thick spots that cause uneven rolling.","tip":"Don't overfill — less is more for clean, tight rolls."},
            {"step":5,"title":"Roll Tightly","instruction":"Use the mat to lift the nearest edge of nori over the filling. Tuck firmly and roll away from you, squeezing gently but firmly as you go. Seal the edge with a little water.","why":"Firm, even pressure creates a compact roll that holds together when cut.","tip":"The first roll is the hardest — it gets easier with practice."},
            {"step":6,"title":"Cut and Serve","instruction":"Slice the roll into 8 pieces with a very sharp, wet knife using a single clean motion each time. Arrange on a plate with soy sauce, wasabi, and pickled ginger.","why":"A clean, sharp knife prevents squashing the roll during cutting.","tip":"Wipe and wet the knife between every cut for clean presentation."}
        ],
        "nutrition": {"calories": 320, "protein": 18, "carbohydrates": 45, "fats": 8, "fiber": 3, "vitamins": "A, B12, D, E", "minerals": "Iodine, Omega-3, Iron"}
    },
    "fried rice": {
        "name": "Egg Fried Rice", "cuisine": "Chinese", "category": "vegetarian",
        "duration": "20 mins", "difficulty": "Easy",
        "ingredients": [
            "3 cups cooked jasmine rice (day-old is best)", "3 large eggs",
            "3 tbsp vegetable oil", "4 cloves garlic, minced",
            "1 cup frozen peas and carrots", "3 spring onions, sliced",
            "3 tbsp soy sauce", "1 tbsp oyster sauce",
            "1 tsp sesame oil", "1/2 tsp white pepper",
            "Salt to taste"
        ],
        "steps": [
            {"step":1,"title":"Prep Rice and Ingredients","instruction":"Use day-old refrigerated rice — break up any clumps with your hands. Have all ingredients chopped and sauces measured before you start, as this dish cooks very fast.","why":"Cold, dry rice fries instead of steaming, giving the essential separate grains texture.","tip":"If using fresh rice, spread it on a tray and refrigerate for 1 hour to dry it out."},
            {"step":2,"title":"High Heat Scrambled Eggs","instruction":"Heat wok or large pan over highest heat until smoking. Add 1 tbsp oil, crack in eggs, and scramble quickly for 30 seconds until just set but still soft. Remove and set aside.","why":"Pre-scrambling eggs separately means they stay fluffy and distinct in the final dish.","tip":"Don't fully cook the eggs here — they'll finish cooking when added back to the rice."},
            {"step":3,"title":"Fry Garlic and Vegetables","instruction":"Add remaining oil to the hot wok. Add garlic and fry for 30 seconds. Add frozen peas and carrots, stir fry for 2 minutes until heated through.","why":"Aromatics and vegetables need a head start before the rice goes in.","tip":"Keep everything moving constantly on high heat."},
            {"step":4,"title":"Fry the Rice","instruction":"Add the cold rice all at once. Press and toss against the hot wok surface for 3-4 minutes, breaking up any remaining clumps, until every grain is separate and slightly crispy.","why":"Direct contact with the screaming hot wok creates the coveted smoky wok hei flavor.","tip":"Spread rice in a thin layer and let it sit for 30 seconds before tossing — this creates crispy edges."},
            {"step":5,"title":"Season and Serve","instruction":"Add scrambled eggs and spring onions back to the wok. Pour in soy sauce, oyster sauce, and white pepper. Toss everything vigorously for 1 minute. Drizzle sesame oil off the heat and serve.","why":"Adding sesame oil off the heat preserves its delicate nutty aroma.","tip":"Taste and adjust soy sauce — different brands vary in saltiness."}
        ],
        "nutrition": {"calories": 380, "protein": 12, "carbohydrates": 58, "fats": 12, "fiber": 3, "vitamins": "A, B6, B12", "minerals": "Iron, Zinc, Phosphorus"}
    },
    "tacos": {
        "name": "Tacos Al Pastor", "cuisine": "Mexican", "category": "non-vegetarian",
        "duration": "45 mins", "difficulty": "Medium",
        "ingredients": [
            "600g pork shoulder, thinly sliced", "3 dried guajillo chilies, soaked",
            "2 chipotle peppers in adobo", "4 cloves garlic",
            "1/2 cup pineapple juice", "2 tbsp apple cider vinegar",
            "1 tsp cumin", "1 tsp oregano", "1/2 tsp cinnamon",
            "Salt and pepper", "12 small corn tortillas",
            "1/2 pineapple, diced", "1 white onion, finely diced",
            "Fresh coriander", "Lime wedges", "Salsa verde to serve"
        ],
        "steps": [
            {"step":1,"title":"Make the Al Pastor Marinade","instruction":"Blend soaked guajillo chilies, chipotle peppers, garlic, pineapple juice, vinegar, cumin, oregano, and cinnamon into a smooth sauce. Season with salt.","why":"The combination of dried chilies and pineapple is the defining flavor of Al Pastor.","tip":"Toast the dried chilies in a dry pan for 30 seconds before soaking to intensify their flavor."},
            {"step":2,"title":"Marinate the Pork","instruction":"Pour marinade over pork slices, mix well to coat evenly. Marinate for at least 2 hours in the fridge, or overnight for deeper flavor.","why":"The pineapple juice tenderizes the pork while the chilies penetrate every fiber.","tip":"Overnight marination transforms the flavor — plan ahead if you can."},
            {"step":3,"title":"Cook the Meat","instruction":"Cook pork in a hot skillet or grill pan over high heat for 3-4 minutes per side until caramelized and slightly charred. Cook in batches to avoid steaming.","why":"High heat caramelization of the marinade creates the signature Al Pastor char.","tip":"The marinade burns easily — watch carefully and flip when edges char."},
            {"step":4,"title":"Rest and Slice","instruction":"Let cooked pork rest for 5 minutes, then chop into small pieces. Toss pineapple cubes in the hot pan for 1-2 minutes until lightly caramelized.","why":"Resting lets juices redistribute so every bite is moist and flavorful.","tip":"Charred pineapple is non-negotiable in authentic Al Pastor."},
            {"step":5,"title":"Warm Tortillas and Assemble","instruction":"Warm corn tortillas directly over a gas flame or in a dry pan for 30 seconds each side. Fill with pork, pineapple, diced onion, and coriander. Serve with lime and salsa verde.","why":"Charred tortillas add smokiness and flexibility to hold the fillings.","tip":"Double up the tortillas for authentic taco truck style — prevents tearing."}
        ],
        "nutrition": {"calories": 420, "protein": 30, "carbohydrates": 38, "fats": 16, "fiber": 5, "vitamins": "A, B6, C", "minerals": "Iron, Zinc, Potassium"}
    },
    "pizza": {
        "name": "Margherita Pizza", "cuisine": "Italian", "category": "vegetarian",
        "duration": "30 mins + 1hr rise", "difficulty": "Medium",
        "ingredients": [
            "2 cups 00 flour or all-purpose flour", "7g instant yeast",
            "1 tsp sugar", "3/4 cup warm water", "1 tbsp olive oil", "1 tsp salt",
            "200ml tomato passata", "2 cloves garlic, minced",
            "Fresh basil leaves", "200g fresh mozzarella, torn",
            "2 tbsp extra virgin olive oil", "Salt and pepper"
        ],
        "steps": [
            {"step":1,"title":"Make the Pizza Dough","instruction":"Mix yeast, sugar, and warm water, let sit 5 minutes until foamy. Combine with flour, salt, and olive oil. Knead for 8-10 minutes until smooth and elastic. Cover and rise for 1 hour until doubled.","why":"Proper gluten development through kneading gives the crust its chewy, airy texture.","tip":"The dough is ready when it springs back slowly when poked."},
            {"step":2,"title":"Prepare the Tomato Sauce","instruction":"Mix tomato passata with minced garlic, salt, pepper, and 1 tbsp olive oil. No cooking needed — the oven does the work.","why":"Raw, uncooked tomato sauce stays bright and fresh-tasting compared to cooked sauce.","tip":"Keep the sauce simple — great pizza needs fewer, better ingredients."},
            {"step":3,"title":"Shape and Top the Pizza","instruction":"Preheat oven to its highest setting (250°C+) with a baking stone or sheet inside for 30 minutes. Stretch dough by hand into a thin round. Spoon on tomato sauce, add torn mozzarella pieces.","why":"A screaming hot oven and surface are essential for a crispy base and blistered crust.","tip":"Stretch by hand, not rolling pin — rolling degasses the dough and makes it flat."},
            {"step":4,"title":"Bake at Maximum Heat","instruction":"Carefully slide pizza onto the hot stone/sheet. Bake for 8-12 minutes until crust is golden with dark blistered spots and cheese is bubbling.","why":"Extreme heat cooks the pizza quickly, keeping the base crispy and toppings fresh.","tip":"Rotate the pizza halfway through if your oven has hot spots."},
            {"step":5,"title":"Finish and Serve","instruction":"Remove from oven, immediately scatter fresh basil leaves and drizzle with extra virgin olive oil. Slice and serve at once.","why":"Fresh basil wilts perfectly from the residual heat without losing its bright green color.","tip":"Never put fresh basil in the oven — it turns black. Always add after baking."}
        ],
        "nutrition": {"calories": 380, "protein": 16, "carbohydrates": 48, "fats": 14, "fiber": 3, "vitamins": "A, B12, C, D", "minerals": "Calcium, Iron, Potassium"}
    },
    "burger": {
        "name": "Classic Smash Burger", "cuisine": "American", "category": "non-vegetarian",
        "duration": "25 mins", "difficulty": "Easy",
        "ingredients": [
            "600g 80/20 ground beef (divided into 6 balls of 100g each)",
            "6 slices American cheese", "6 potato buns",
            "1 white onion, very finely diced",
            "Burger sauce: 4 tbsp mayo, 2 tbsp ketchup, 1 tbsp mustard, 1 tsp pickle juice",
            "Shredded iceberg lettuce", "Dill pickle slices",
            "Salt and black pepper"
        ],
        "steps": [
            {"step":1,"title":"Make Burger Sauce and Prep","instruction":"Mix mayo, ketchup, mustard, and pickle juice to make the burger sauce. Set aside. Toast buns cut-side down in a dry pan until golden. Set aside.","why":"Toasted buns stay crispy and don't get soggy from the sauce and juices.","tip":"Make extra sauce — it's addictive and works as a dipping sauce too."},
            {"step":2,"title":"Heat Pan to Smoking Hot","instruction":"Heat a cast iron skillet or griddle over the highest heat possible for 5 minutes. You want it absolutely screaming hot — a drop of water should evaporate instantly.","why":"Extreme heat is the secret to the crispy, lacy edges that define a smash burger.","tip":"No oil needed — the beef's own fat renders immediately on contact."},
            {"step":3,"title":"Smash and Season","instruction":"Place a beef ball in the hot pan. Immediately press down hard with a heavy spatula or burger press until it's very thin (about 1cm). Season generously with salt and pepper. Add diced onion on top.","why":"Smashing maximizes contact with the hot surface, creating maximum Maillard browning.","tip":"Smash immediately after placing — once it starts cooking you can't flatten it further."},
            {"step":4,"title":"Flip and Add Cheese","instruction":"Cook for 90 seconds until edges are brown and crispy. Flip and immediately add cheese slice. Cook 60 more seconds until cheese melts. For a double, smash a second patty and stack on top while cheese melts.","why":"The cheese melts best on the freshly flipped hot side.","tip":"Cover with a metal bowl or lid for 20 seconds to steam the cheese and melt it perfectly."},
            {"step":5,"title":"Assemble and Serve","instruction":"Spread burger sauce on both bun halves. Add lettuce on bottom bun, then the cheesy smash patty, then pickles. Close and serve immediately.","why":"Immediate serving ensures the crispy edges haven't softened.","tip":"Serve within 2 minutes of cooking — smash burgers are best fresh off the griddle."}
        ],
        "nutrition": {"calories": 650, "protein": 38, "carbohydrates": 38, "fats": 36, "fiber": 2, "vitamins": "B12, D", "minerals": "Iron, Zinc, Calcium"}
    },
    "dosa": {
        "name": "Masala Dosa", "cuisine": "Indian", "category": "vegetarian",
        "duration": "40 mins + overnight fermentation", "difficulty": "Hard",
        "ingredients": [
            "For batter: 2 cups parboiled rice, 1/2 cup urad dal (black gram), 1/4 tsp fenugreek seeds, Salt",
            "For masala filling: 500g potatoes, boiled and mashed",
            "2 medium onions, thinly sliced", "2 green chilies, chopped",
            "1 tsp mustard seeds", "1 tsp cumin seeds", "10 curry leaves",
            "1/2 tsp turmeric", "2 tbsp oil", "Salt to taste",
            "2 tbsp ghee or oil for cooking dosa",
            "Coconut chutney and sambar for serving"
        ],
        "steps": [
            {"step":1,"title":"Soak and Grind Batter","instruction":"Soak rice and urad dal separately for 6 hours. Grind urad dal with fenugreek to a smooth, fluffy batter. Grind rice to a slightly coarser texture. Mix together with salt and ferment overnight at room temperature.","why":"Fermentation creates the characteristic sour flavor and makes the batter light and airy.","tip":"Fermentation works better in warm climates — in cold weather, place batter in an oven with just the light on."},
            {"step":2,"title":"Make the Potato Masala","instruction":"Heat oil in a pan. Add mustard and cumin seeds and let them splutter. Add curry leaves, green chilies, and onions. Cook until onions are translucent. Add turmeric and mashed potatoes, mix well and cook for 5 minutes.","why":"The tempering of mustard and curry leaves releases essential aromatic oils.","tip":"The masala should be dry enough to hold its shape when placed on the dosa."},
            {"step":3,"title":"Heat the Tawa","instruction":"Heat a flat iron tawa or non-stick pan until hot. Sprinkle a few drops of water — they should evaporate immediately. Rub with a cut onion half dipped in oil.","why":"The onion prevents sticking and adds subtle flavor to each dosa.","tip":"The temperature is perfect when water drops dance and evaporate in 2 seconds."},
            {"step":4,"title":"Pour and Spread the Dosa","instruction":"Pour a ladleful of batter in the center of the tawa. Using the back of the ladle, spread in circular motions from center outward to make a thin, large circle. Drizzle ghee around the edges.","why":"The circular spreading motion thins the batter evenly for a crispy dosa.","tip":"Work quickly — the batter sets fast on a hot surface."},
            {"step":5,"title":"Fill and Fold","instruction":"When the dosa turns golden and the edges lift from the pan, place 2-3 tbsp potato masala on one side. Fold the dosa over the filling. Serve immediately with coconut chutney and hot sambar.","why":"Masala dosa is served the moment it's made for maximum crispiness.","tip":"Don't flip the dosa — it's cooked on only one side for the best texture."}
        ],
        "nutrition": {"calories": 380, "protein": 10, "carbohydrates": 58, "fats": 12, "fiber": 5, "vitamins": "B6, C", "minerals": "Iron, Calcium, Potassium"}
    },
    "paneer tikka": {
        "name": "Paneer Tikka", "cuisine": "Indian", "category": "vegetarian",
        "duration": "35 mins + 30 min marination", "difficulty": "Easy",
        "ingredients": [
            "400g paneer, cut into 2-inch cubes", "1 cup thick yogurt",
            "2 tbsp lemon juice", "2 tsp kashmiri red chili powder",
            "1 tsp garam masala", "1 tsp cumin powder", "1 tsp coriander powder",
            "1/2 tsp turmeric", "1 tbsp ginger-garlic paste",
            "2 tbsp mustard oil or vegetable oil",
            "1 green bell pepper, cubed", "1 red bell pepper, cubed",
            "1 large onion, petals separated", "Salt to taste",
            "Chaat masala for serving", "Mint chutney for serving", "Lemon wedges"
        ],
        "steps": [
            {"step":1,"title":"Prepare Marinade","instruction":"Whisk together yogurt, lemon juice, ginger-garlic paste, all spices, oil, and salt until smooth. The marinade should be thick and vibrant red-orange.","why":"Thick yogurt marinade clings to paneer and creates a flavorful crust when grilled.","tip":"Hung curd (strained yogurt) works even better — it creates a thicker, creamier coating."},
            {"step":2,"title":"Marinate Paneer and Vegetables","instruction":"Gently coat paneer cubes, bell peppers, and onion petals in the marinade. Ensure everything is well coated. Marinate for at least 30 minutes (or 2 hours for best results).","why":"Marination allows the spices to penetrate and flavors to develop fully.","tip":"Handle paneer gently — it's fragile and can break if mixed too vigorously."},
            {"step":3,"title":"Thread on Skewers","instruction":"Thread marinated paneer alternating with bell pepper and onion pieces onto skewers. Leave a little space between pieces for even cooking.","why":"Skewering ensures even exposure to heat and easy turning during cooking.","tip":"Soak wooden skewers in water for 30 minutes to prevent burning."},
            {"step":4,"title":"Grill or Broil","instruction":"Grill on a hot griddle/barbecue or broil in oven at maximum heat (220°C) for 12-15 minutes, turning halfway, until nicely charred and blistered on the outside.","why":"High heat creates the characteristic charred spots that give tikka its distinctive flavor.","tip":"Brush with butter or oil halfway through cooking to keep moist and add richness."},
            {"step":5,"title":"Serve with Accompaniments","instruction":"Sprinkle with chaat masala immediately after grilling. Serve on a sizzling plate with mint chutney, sliced onions, and lemon wedges on the side.","why":"Chaat masala adds a tangy, zingy finish that balances the smoky richness.","tip":"Serve straight off the grill — paneer tikka is best piping hot and just charred."}
        ],
        "nutrition": {"calories": 320, "protein": 22, "carbohydrates": 12, "fats": 20, "fiber": 3, "vitamins": "A, B12, C, D", "minerals": "Calcium, Iron, Phosphorus"}
    },
    "noodles": {
        "name": "Garlic Noodles with Vegetables", "cuisine": "Chinese", "category": "vegetarian",
        "duration": "20 mins", "difficulty": "Easy",
        "ingredients": [
            "300g egg noodles or hakka noodles", "4 tbsp sesame oil",
            "6 cloves garlic, minced", "2 tsp ginger, minced",
            "2 tbsp soy sauce", "1 tbsp oyster sauce (or hoisin for veg)",
            "1 tsp chili sauce or sriracha", "1 cup mixed vegetables (bell peppers, carrots, spring onions)",
            "2 eggs (optional)", "2 tsp rice vinegar",
            "White sesame seeds for garnish", "Spring onions for garnish"
        ],
        "steps": [
            {"step":1,"title":"Cook the Noodles","instruction":"Cook noodles in boiling salted water until just al dente (1 minute less than package instructions). Drain and toss immediately with 1 tbsp sesame oil to prevent sticking.","why":"Al dente noodles have better texture and won't turn mushy when stir-fried.","tip":"Run cold water over drained noodles briefly to stop cooking if not using immediately."},
            {"step":2,"title":"Make the Sauce","instruction":"Mix soy sauce, oyster sauce, chili sauce, rice vinegar, and 1 tsp sesame oil in a bowl. Taste and adjust balance of salty, spicy, and tangy.","why":"Mixing the sauce separately ensures even, instant coating when added to the noodles.","tip":"The sauce is the soul of this dish — taste it and adjust before adding to the noodles."},
            {"step":3,"title":"Stir Fry Aromatics and Veg","instruction":"Heat remaining sesame oil in a wok over high heat. Add garlic and ginger, fry for 30 seconds until golden and fragrant. Add vegetables and stir fry for 2-3 minutes until tender-crisp.","why":"Browning garlic in oil creates a rich, nutty base that coats every strand of noodle.","tip":"High heat is essential — you want a sizzle, not a steam."},
            {"step":4,"title":"Toss Noodles and Season","instruction":"Add noodles to the wok and pour sauce over everything. Toss vigorously over high heat for 2 minutes until every strand is coated and slightly sticky.","why":"High heat slightly reduces the sauce, making it cling to every noodle.","tip":"Use tongs for easiest tossing and even sauce distribution."},
            {"step":5,"title":"Finish and Serve","instruction":"Top with sesame seeds and sliced spring onions. Serve immediately while hot and glossy.","why":"The dish is best eaten fresh — noodles absorb sauce as they sit.","tip":"A drizzle of chili oil at the table adds extra heat for those who want it."}
        ],
        "nutrition": {"calories": 420, "protein": 14, "carbohydrates": 62, "fats": 14, "fiber": 4, "vitamins": "A, B6, C", "minerals": "Iron, Calcium, Potassium"}
    },
    "ramen": {
        "name": "Tonkotsu Ramen", "cuisine": "Japanese", "category": "non-vegetarian",
        "duration": "45 mins (with store broth)", "difficulty": "Medium",
        "ingredients": [
            "2 portions ramen noodles", "1 litre pork or chicken broth",
            "2 tbsp white miso paste", "2 tbsp soy sauce",
            "1 tbsp sesame oil", "1 tbsp ginger, grated",
            "3 cloves garlic, minced", "200g chashu pork belly (or sliced chicken)",
            "2 soft-boiled marinated eggs (ramen eggs)",
            "2 sheets nori", "4 tbsp corn kernels",
            "4 tbsp bamboo shoots (menma)", "2 spring onions, sliced",
            "Black sesame seeds", "Chili oil to taste"
        ],
        "steps": [
            {"step":1,"title":"Prepare Ramen Eggs","instruction":"Soft boil eggs for exactly 6.5 minutes in boiling water. Transfer to ice water. Peel and marinate in 2 tbsp soy sauce + 1 tbsp mirin + water for at least 1 hour.","why":"Marinated eggs (ajitsuke tamago) add a savory, umami richness that's essential to ramen.","tip":"Make these a day ahead — overnight marination creates the best flavor and color."},
            {"step":2,"title":"Build the Broth Base","instruction":"Sauté garlic and ginger in sesame oil for 1 minute. Add broth and bring to a simmer. Whisk in miso paste and soy sauce. Taste and adjust seasoning.","why":"Miso adds complex umami depth and body to the broth.","tip":"Never boil miso — it destroys the delicate enzymes. Add at a low simmer."},
            {"step":3,"title":"Cook Ramen Noodles","instruction":"Cook noodles in a separate pot of boiling water according to package instructions (usually 2-3 minutes). Drain well.","why":"Cooking noodles separately prevents starch from clouding your beautifully clear broth.","tip":"Cook noodles to just al dente — they continue cooking in the hot broth when served."},
            {"step":4,"title":"Warm Toppings","instruction":"Slice chashu pork and lightly sear in a hot pan until caramelized. Slice marinated egg in half lengthwise.","why":"A quick sear on the pork caramelizes the surface, adding texture and flavor.","tip":"Warm all toppings separately so they don't cool down the hot broth."},
            {"step":5,"title":"Assemble the Bowl","instruction":"Place hot noodles in a deep bowl. Ladle hot broth over them. Arrange pork, egg halves, nori, corn, bamboo shoots artfully on top. Garnish with spring onions and sesame seeds.","why":"Proper assembly of ramen is an art — presentation is part of the experience.","tip":"Serve in pre-warmed bowls to keep the ramen hot for longer."}
        ],
        "nutrition": {"calories": 580, "protein": 32, "carbohydrates": 62, "fats": 22, "fiber": 4, "vitamins": "B12, D, K", "minerals": "Iron, Zinc, Sodium"}
    },
}

def _build_template_recipe(query, servings):
    """Generate dish-specific or smart template-based recipe."""
    import random as _rand

    q = query.lower().strip()

    # === Check dish-specific knowledge base first ===
    # Try exact match, then partial match
    specific = None
    for key, recipe in _DISH_RECIPES.items():
        if key == q or key in q or q in key:
            specific = recipe
            break

    if specific:
        recipe_id = "ai_" + hashlib.md5(query.lower().strip().encode()).hexdigest()[:10]
        cuisine = specific["cuisine"]
        emoji = _CUISINE_EMOJIS.get(cuisine.lower(), "🍽️")
        
        # Scale servings ratio
        base_servings = 4
        steps = specific["steps"]

        main_image = _fetch_pexels_image(specific["name"])
        if main_image == "✨":
            main_image = emoji
            
        formatted_ingredients = []
        for ing in specific["ingredients"]:
            # generic template ingredients are simple strings
            img_kw = ing.split()[-1].lower() # extremely naive for templates
            formatted_ingredients.append({
                "item": ing,
                "image": f"https://spoonacular.com/cdn/ingredients_100x100/{img_kw}.jpg"
            })

        return {
            "id": recipe_id,
            "name": specific["name"],
            "category": specific["category"],
            "cuisine": cuisine,
            "image": main_image,
            "duration": specific["duration"],
            "difficulty": specific["difficulty"],
            "servings": servings,
            "tags": ["AI-generated", cuisine.lower()],
            "ingredients": formatted_ingredients,
            "nutrition": specific["nutrition"],
            "steps": steps,
            "is_favorite": False,
            "ai_generated": True
        }

    # === Smart fallback for unknown dishes ===
    cuisine = _detect_cuisine(q)
    is_veg = any(w in q for w in ["veg", "vegan", "vegetarian", "tofu", "paneer", "dal", "chana"])
    category = "vegetarian" if is_veg else "non-vegetarian"
    dish_name = query.strip().title()

    main_protein = None
    for p_kw, p_val in [
        ("chicken", "500g boneless chicken, cut into pieces"),
        ("beef", "400g beef sirloin, sliced thin"),
        ("pork", "400g pork tenderloin, sliced"),
        ("lamb", "400g lamb, cubed"),
        ("fish", "300g white fish fillet"),
        ("shrimp", "300g shrimp, peeled and deveined"),
        ("prawn", "300g large prawns, peeled"),
        ("paneer", "250g fresh paneer, cubed"),
        ("tofu", "300g firm tofu, pressed and cubed"),
        ("egg", "4 large eggs"),
    ]:
        if p_kw in q:
            main_protein = p_val
            break

    if not main_protein:
        main_protein = "200g mixed vegetables" if is_veg else f"500g {dish_name.split()[0].lower()}"

    enh = _ENHANCED_INGREDIENTS.get(cuisine)
    if enh:
        base_ings = list(enh["base"])
        extras = list(enh.get("extras", []))
        ingredients = base_ings + [main_protein] + extras
    else:
        ingredients = [
            "3 tbsp cooking oil", "1 large onion, diced",
            "4 cloves garlic, minced", "1 inch ginger, grated",
            "1 tsp cumin", "1 tsp coriander powder",
            "1/2 tsp turmeric", "1 tsp garam masala",
            main_protein, "2 medium tomatoes, chopped",
            "1 cup water or stock", "Salt to taste",
            "Fresh coriander and lemon for garnish"
        ]

    emoji = _CUISINE_EMOJIS.get(cuisine.lower(), "🍽️")
    recipe_id = "ai_" + hashlib.md5(query.lower().strip().encode()).hexdigest()[:10]

    steps = [
        {"step": 1, "title": "Prepare All Ingredients",
         "instruction": f"Wash, peel, and chop all vegetables. Measure and organize all spices. If using meat, pat dry and season lightly with salt and pepper.",
         "why": "Having everything ready (mise en place) before you start cooking reduces stress and improves results.",
         "tip": "Read the full recipe once before starting to cook."},
        {"step": 2, "title": "Build Aromatic Base",
         "instruction": f"Heat oil in a heavy pan over medium heat. Add onions and cook for 7-8 minutes until golden and soft. Add garlic and ginger, cook for 2 more minutes.",
         "why": f"A well-cooked aromatic base is the foundation of great {cuisine} cooking.",
         "tip": "Don't rush the onions — properly caramelized onions add sweetness and depth."},
        {"step": 3, "title": "Toast the Spices",
         "instruction": "Add all dry spices and cook for 60 seconds, stirring constantly. Add a splash of water if spices start to stick.",
         "why": "Blooming spices in oil releases fat-soluble compounds that dramatically increase their flavor.",
         "tip": "Spices burn quickly — have water ready and keep stirring."},
        {"step": 4, "title": "Cook the Main Ingredient",
         "instruction": f"Add {main_protein} and cook on medium-high heat for 6-8 minutes, stirring until cooked through and starting to brown.",
         "why": "Browning the main ingredient through the Maillard reaction creates complex, deep flavors.",
         "tip": "Don't crowd the pan — cook in batches if needed for better browning."},
        {"step": 5, "title": "Add Liquid and Simmer",
         "instruction": "Add tomatoes and stock/water. Bring to a boil, then reduce heat and simmer covered for 12-15 minutes until sauce thickens.",
         "why": "Simmering allows all ingredients to meld together and the sauce to concentrate.",
         "tip": "Stir occasionally to prevent sticking. Adjust consistency with more water if needed."},
        {"step": 6, "title": "Finish and Serve",
         "instruction": f"Taste and adjust seasoning with salt and lemon. Garnish with fresh herbs. Serve your {dish_name} hot with rice, bread, or your preferred side.",
         "why": "A squeeze of acid (lemon/lime) brightens all the flavors right before serving.",
         "tip": "Always taste before serving and adjust salt and spice to your preference."}
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
            "calories": 380, "protein": 18 if is_veg else 28,
            "carbohydrates": 40, "fats": 14,
            "fiber": 6 if is_veg else 3,
            "vitamins": "A, B, C", "minerals": "Iron, Calcium, Potassium"
        },
        "steps": steps,
        "is_favorite": False,
        "ai_generated": True
    }



# ===== REAL AI RECIPE GENERATION WITH GROQ =====
from groq import Groq
import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

def _fetch_pexels_image(query):
    """Fetch a high quality image for the recipe from Pexels API."""
    if not PEXELS_API_KEY:
        return "✨"
    try:
        import requests
        import urllib.parse
        url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query + ' food')}&per_page=1"
        headers = {"Authorization": PEXELS_API_KEY}
        res = requests.get(url, headers=headers, timeout=5)
        if res.ok:
            data = res.json()
            if data.get("photos"):
                return data["photos"][0]["src"]["large"]
    except Exception as e:
        print(f"Pexels error: {e}")
    return "✨"

def _generate_with_ai(query, servings):
    """Use Groq AI to generate a complete, unique recipe."""
    prompt = f"""You are a professional chef AI. Generate a complete, authentic recipe for: "{query}"
Servings: {servings}

Respond with ONLY a valid JSON object, no markdown, no code fences. Use this exact structure:
{{
  "name": "Exact dish name",
  "category": "vegetarian or non-vegetarian",
  "cuisine": "Indian/Italian/Chinese/Thai/Mexican/Japanese/Korean/American/French/Continental/Fusion",
  "duration": "e.g. 45 mins",
  "difficulty": "Easy/Medium/Hard",
  "ingredients": [
    {{
      "item": "500g boneless chicken thighs, cubed",
      "image_keyword": "chicken-thighs"
    }},
    {{
      "item": "2 tbsp butter",
      "image_keyword": "butter"
    }}
  ],
  "nutrition": {{
    "calories": 450,
    "protein": 35,
    "carbohydrates": 20,
    "fats": 25,
    "fiber": 3,
    "vitamins": "A, B6, C",
    "minerals": "Iron, Calcium, Potassium"
  }},
  "steps": [
    {{
      "step": 1,
      "title": "Step title",
      "instruction": "Detailed 2-3 sentence instruction.",
      "why": "Why this step matters.",
      "tip": "Pro chef tip."
    }}
  ]
}}

CRITICAL RULES:
- For "{query}" use ONLY the correct, authentic ingredients for THAT specific dish
- 'image_keyword' must be a simple, singular noun phrase with dashes instead of spaces (e.g. 'heavy-cream', 'olive-oil', 'red-onion').
- Include ALL ingredients with precise measurements
- Provide 5-8 detailed steps
- Nutrition must be realistic per serving
- Return ONLY the JSON object, nothing else"""

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        text = response.choices[0].message.content.strip()
        # Clean markdown fences if any
        if text.startswith('```'):
            text = '\n'.join(text.split('\n')[1:])
        if text.endswith('```'):
            text = text.rsplit('```', 1)[0]
        text = text.strip()
        recipe_data = json.loads(text)
        print(f"Groq AI generated recipe for: {query}")
        return recipe_data
    except Exception as e:
        print(f"Groq AI generation failed: {e}")
        return None



@recipes_bp.route('/ai-generate', methods=['POST'])
def ai_generate_recipe():
    """Generate a recipe using REAL Google Gemini AI, with TheMealDB and template fallbacks."""
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

    # --- Attempt 1: REAL AI with Groq ---
    ai_data = _generate_with_ai(query, servings)
    if ai_data:
        cuisine = ai_data.get('cuisine', 'Fusion')
        emoji = _CUISINE_EMOJIS.get(cuisine.lower(), "🍽️")
        
        # Ensure steps have correct format
        steps = ai_data.get('steps', [])
        for i, s in enumerate(steps):
            s['step'] = i + 1
            if 'title' not in s:
                s['title'] = f"Step {i+1}"
            if 'why' not in s:
                s['why'] = ''
            if 'tip' not in s:
                s['tip'] = ''

        recipe_name = ai_data.get('name', query.title())
        main_image = _fetch_pexels_image(recipe_name)
        if main_image == "✨":
            main_image = emoji
            
        raw_ingredients = ai_data.get('ingredients', [])
        formatted_ingredients = []
        for ing in raw_ingredients:
            if isinstance(ing, dict):
                img_kw = ing.get('image_keyword', 'ingredient')
                formatted_ingredients.append({
                    "item": ing.get('item', ''),
                    "image": f"https://spoonacular.com/cdn/ingredients_100x100/{img_kw}.jpg"
                })
            else:
                formatted_ingredients.append({
                    "item": str(ing),
                    "image": "https://spoonacular.com/cdn/ingredients_100x100/ingredient.jpg"
                })

        generated_recipe = {
            "id": recipe_id,
            "name": recipe_name,
            "category": ai_data.get('category', 'non-vegetarian'),
            "cuisine": cuisine,
            "image": main_image,
            "duration": ai_data.get('duration', '40 mins'),
            "difficulty": ai_data.get('difficulty', 'Medium'),
            "servings": servings,
            "tags": ["AI-generated", cuisine.lower()],
            "ingredients": formatted_ingredients,
            "nutrition": ai_data.get('nutrition', {
                "calories": 400, "protein": 20, "carbohydrates": 45,
                "fats": 15, "fiber": 5, "vitamins": "A, B, C",
                "minerals": "Iron, Calcium"
            }),
            "steps": steps,
            "is_favorite": False,
            "ai_generated": True
        }

    # --- Attempt 2: Fetch from TheMealDB ---
    if not generated_recipe:
        try:
            url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            res = urllib.request.urlopen(req, timeout=5)
            api_data = json.loads(res.read())

            if api_data and api_data.get('meals'):
                meal = api_data['meals'][0]
                ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f'strIngredient{i}')
                    measure = meal.get(f'strMeasure{i}')
                    if ing and ing.strip():
                        part = f"{measure.strip()} {ing.strip()}" if measure and measure.strip() else ing.strip()
                        img_kw = ing.strip().lower().replace(" ", "-")
                        ingredients.append({
                            "item": part,
                            "image": f"https://spoonacular.com/cdn/ingredients_100x100/{img_kw}.jpg"
                        })

                raw_instructions = meal.get('strInstructions', '').replace('\r\n', '\n').split('\n')
                steps = []
                step_idx = 1
                for inst in raw_instructions:
                    line = inst.strip()
                    if line:
                        steps.append({
                            "step": step_idx, "title": f"Step {step_idx}",
                            "instruction": line,
                            "why": "Follow the authentic recipe for best results.",
                            "tip": "Adjust seasoning to your taste as you cook."
                        })
                        step_idx += 1

                meal_category = meal.get('strCategory', '').lower()
                is_veg = meal_category in ['vegetarian', 'vegan', 'dessert', 'side']
                cuisine_area = meal.get('strArea', 'Fusion')
                emoji = _CUISINE_EMOJIS.get(cuisine_area.lower(), "🍽️")
                main_image = meal.get('strMealThumb', emoji)

                generated_recipe = {
                    "id": recipe_id,
                    "name": meal['strMeal'],
                    "category": "vegetarian" if is_veg else "non-vegetarian",
                    "cuisine": cuisine_area,
                    "image": main_image,
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

    # --- Attempt 3: Smart template fallback ---
    if not generated_recipe:
        generated_recipe = _build_template_recipe(query, servings)

    # Persist to saved_recipes.json
    _save_recipe_to_file(generated_recipe)

    # Also add to memory store for current session
    store = get_memory_store()
    if not any(r.get('id') == generated_recipe['id'] for r in store['recipes']):
        store['recipes'].append(generated_recipe)

    return jsonify(generated_recipe), 200


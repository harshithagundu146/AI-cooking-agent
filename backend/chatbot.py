import random, re
from flask import Blueprint, request, jsonify
from recipes import get_all_recipes_internal

chatbot_bp = Blueprint('chatbot', __name__)

RESPONSES = {
    "greeting": [
        "Hello! I'm your AI Cooking Assistant 🍳 How can I help you today?",
        "Hi there, Chef! Ready to cook something amazing? 👨‍🍳",
        "Welcome! Ask me anything about cooking, recipes, or nutrition!"
    ],
    "recipe_suggestion": [
        "Based on your preferences, I'd recommend trying a {cuisine} dish! Would you like to see some options?",
        "How about trying something new? I have great {cuisine} recipes for you!",
        "Let me find the perfect recipe for you. What ingredients do you have?"
    ],
    "substitution": [
        "Great question! {original} can be replaced with {substitute}. The taste will be slightly different but still delicious!",
        "No {original}? No problem! Try using {substitute} instead. It works wonderfully!"
    ],
    "nutrition": [
        "Nutrition is key to a healthy lifestyle! Would you like me to analyze a specific recipe's nutritional content?",
        "I can help you track calories, proteins, carbs, and more. Which recipe are you interested in?",
        "Eating healthy doesn't mean boring food! Let me suggest some nutritious and delicious recipes."
    ],
    "cooking_tip": [
        "Pro tip: Always let your pan heat up before adding oil. This prevents food from sticking! 🔥",
        "Did you know? Adding a pinch of salt to boiling water raises the boiling point and cooks pasta faster! 🧂",
        "Chef's secret: Rest your meat for 5-10 minutes after cooking. It redistributes the juices! 🥩",
        "Tip: Fresh herbs should be added at the end of cooking to preserve their flavor and color! 🌿",
        "Always taste your food as you cook! Seasoning adjustments are easier during cooking than after. 👅",
        "When sautéing, don't overcrowd the pan. It lowers the temperature and steams food instead of browning it.",
        "Use room temperature eggs for baking — they incorporate better into batters for fluffier results! 🥚"
    ],
    "healthy": [
        "For a healthy meal, try grilled vegetables with quinoa and a lemon-herb dressing!",
        "Swap white rice for brown rice or cauliflower rice to reduce calories while keeping you full!",
        "Steaming vegetables preserves more nutrients than boiling. Give it a try! 🥦"
    ],
    "farewell": [
        "Happy cooking! Don't hesitate to ask if you need more help! 🍽️",
        "Enjoy your meal! Come back anytime for more cooking inspiration! 😊",
        "Bon appétit! Remember, cooking is an art — have fun with it! 🎨🍳"
    ],
    "default": [
        "That's an interesting question! While I focus on cooking, I'd suggest checking out some recipes related to your query.",
        "I'm here to help with all things cooking! Could you rephrase that or ask me about recipes, ingredients, or nutrition?",
        "Hmm, let me think about that... In the meantime, would you like a cooking tip or recipe suggestion?"
    ]
}

SUBSTITUTION_MAP = {
    "milk": "almond milk, soy milk, or oat milk",
    "egg": "mashed banana, yogurt, or flaxseed mixed with water",
    "butter": "olive oil, coconut oil, or avocado",
    "sugar": "honey, maple syrup, or stevia",
    "cream": "coconut cream or cashew cream",
    "cheese": "nutritional yeast or cashew cheese",
    "flour": "almond flour, oat flour, or rice flour",
    "chicken": "tofu, paneer, or mushrooms",
    "beef": "lentils, portobello mushrooms, or tempeh",
    "rice": "quinoa, cauliflower rice, or couscous",
    "pasta": "zucchini noodles or rice noodles",
    "soy sauce": "coconut aminos or tamari",
    "paneer": "tofu or cottage cheese",
    "ghee": "butter or coconut oil"
}

def _classify_intent(message):
    msg = message.lower()
    
    def matches(keywords):
        return any(re.search(r'\b' + re.escape(kw) + r'\b', msg) for kw in keywords)

    greetings = ["hello", "hi", "hey", "good morning", "good evening", "howdy"]
    farewells = ["bye", "goodbye", "see you", "thanks", "thank you", "that's all"]
    
    if matches(greetings): return "greeting"
    if matches(farewells): return "farewell"
    if matches(["replace", "substitute", "instead of", "alternative", "swap"]): return "substitution"
    if matches(["recipe", "suggest", "recommend", "cook", "make", "prepare", "dish"]): return "recipe_suggestion"
    if matches(["nutrition", "calorie", "protein", "healthy", "diet", "fat", "carb", "vitamin"]): return "nutrition"
    if matches(["tip", "trick", "advice", "how to", "technique", "secret"]): return "cooking_tip"
    if matches(["healthy", "health", "fit", "wellness", "clean eating"]): return "healthy"
    
    return "default"

def _find_substitution(msg):
    msg_lower = msg.lower()
    for ingredient, subs in SUBSTITUTION_MAP.items():
        if ingredient in msg_lower:
            return ingredient, subs
    return None, None

@chatbot_bp.route('/message', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    intent = _classify_intent(message)
    
    if intent == "substitution":
        ingredient, substitute = _find_substitution(message)
        if ingredient and substitute:
            template = random.choice(RESPONSES["substitution"])
            response = template.format(original=ingredient, substitute=substitute)
        else:
            response = "I can help with ingredient substitutions! Tell me which ingredient you'd like to replace, and I'll suggest alternatives. Common ones include milk, eggs, butter, sugar, and flour."
    elif intent == "recipe_suggestion":
        recipes = get_all_recipes_internal()
        # Filter by mention if any
        msg_lower = message.lower()
        suggestions = []
        if any(w in msg_lower for w in ["spicy", "hot", "chili"]):
            suggestions = [r for r in recipes if "spicy" in r.get("tags", [])]
        elif any(w in msg_lower for w in ["dessert", "sweet", "cake", "sugar"]):
            suggestions = [r for r in recipes if "sweet" in r.get("tags", [])]
        elif any(w in msg_lower for w in ["healthy", "clean", "light"]):
            suggestions = [r for r in recipes if "healthy" in r.get("tags", [])]
        elif any(w in msg_lower for w in ["indian", "desi", "curry"]):
            suggestions = [r for r in recipes if r.get("cuisine") == "Indian"]
        elif any(w in msg_lower for w in ["italian", "pasta", "pizza"]):
            suggestions = [r for r in recipes if r.get("cuisine") == "Italian"]

        if suggestions:
            selected = random.choice(suggestions)
            template = random.choice(RESPONSES["recipe_suggestion"])
            response = f"{template.format(cuisine=selected.get('cuisine', 'World'))} I'd specifically recommend **{selected.get('name')}**. It's a {selected.get('difficulty', 'moderate')} difficulty dish that takes about {selected.get('duration', 'some time')}."
        else:
            # Adaptable AI: Generate a response for a custom requested recipe
            words = [w for w in msg_lower.split() if w not in ['i', 'want', 'to', 'eat', 'some', 'food', 'with', 'a', 'an', 'the', 'recipe', 'recipes', 'for', 'can', 'you', 'make', 'suggest', 'recommend', 'cook']]
            main_theme = " ".join(words).title() if words else "Surprise"
            # Escape single quotes to avoid breaking the JS onclick
            safe_theme = main_theme.replace("'", "\\'")
            gen_link = f"<a href=\"#\" onclick=\"generateFromChatbot('{safe_theme}'); return false;\" style=\"color: var(--pink-600); font-weight: bold; text-decoration: underline;\">✨ Click here to generate the full '{main_theme}' recipe</a>"
            response = f"I don't have that exact recipe in my collection, but I can create one for you right now! 🧑‍🍳<br><br>{gen_link} — I'll build the complete ingredients list and step-by-step instructions instantly!"
    else:
        response = random.choice(RESPONSES.get(intent, RESPONSES["default"]))

    return jsonify({"response": response, "intent": intent}), 200

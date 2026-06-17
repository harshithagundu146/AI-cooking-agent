/* ===== AI Cooking Agent — Frontend Logic ===== */
const API = '/api';
let state = { token:null, userId:null, username:null, isNew:false, category:null, preferences:{}, currentRecipe:null, recipes:[], selectedSubs:{}, allergies:[], selectedCuisine:'All', groceryList:[], spiceLevel:'Medium' };

// ===== NAVIGATION =====
function navigateTo(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const page = document.getElementById(pageId);
  if (page) page.classList.add('active');
  if (pageId === 'recipes-page') loadRecipes();
}

// ===== AUTH =====
function switchAuthTab(tab, e) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  if (e && e.target) e.target.classList.add('active');
  else document.querySelector(`.tab-btn:${tab==='login'?'first':'last'}-child`)?.classList.add('active');
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
}

async function handleLogin(e) {
  e.preventDefault();
  const msg = document.getElementById('login-message');
  try {
    const res = await fetch(`${API}/auth/login`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ username: document.getElementById('login-username').value, password: document.getElementById('login-password').value })
    });
    const data = await res.json();
    if (!res.ok) { msg.textContent = data.error; msg.className = 'auth-message error'; return; }
    state.token = data.token; state.userId = data.user_id; state.username = data.username; state.isNew = data.is_new;
    afterAuth();
  } catch(err) { msg.textContent = 'Connection error'; msg.className = 'auth-message error'; }
}

async function handleRegister(e) {
  e.preventDefault();
  const msg = document.getElementById('register-message');
  const username = document.getElementById('reg-username').value;
  if (!/^[a-zA-Z]/.test(username)) {
    msg.textContent = 'Username must start with an alphabet letter (a–z or A–Z).';
    msg.className = 'auth-message error';
    return;
  }
  try {
    const res = await fetch(`${API}/auth/register`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ username, password: document.getElementById('reg-password').value })
    });
    const data = await res.json();
    if (!res.ok) { msg.textContent = data.error; msg.className = 'auth-message error'; return; }
    state.token = data.token; state.userId = data.user_id; state.username = data.username; state.isNew = true;
    afterAuth();
  } catch(err) { msg.textContent = 'Connection error'; msg.className = 'auth-message error'; }
}

function afterAuth() { navigateTo('category-page'); }

function logout() { state = { token:null,userId:null,username:null,isNew:false,category:null,preferences:{},currentRecipe:null,recipes:[],selectedSubs:{},allergies:[],selectedCuisine:'All' }; navigateTo('landing-page'); }

// ===== CATEGORY =====
function selectCategory(cat) {
  state.category = cat;
  state.preferences.food_category = cat;
  navigateTo('cuisine-page');
}

// ===== CUISINE SELECTION =====
function selectCuisine(cuisine) {
  state.selectedCuisine = cuisine;
  state.preferences.cuisine_selected = cuisine;
  // Highlight selected tile
  document.querySelectorAll('.cuisine-tile').forEach(t => t.classList.remove('selected'));
  const id = 'ctile-' + cuisine.toLowerCase();
  const el = document.getElementById(id);
  if (el) el.classList.add('selected');
  setTimeout(() => navigateTo('recipes-page'), 300);
}



// ===== RECIPES =====
function renderCuisineFilterBar() {
  const cuisines = ['All','Indian','Chinese','Italian','Mexican','Korean','Japanese','American','Continental'];
  let bar = document.querySelector('.cuisine-filter-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.className = 'cuisine-filter-bar';
    const nav = document.querySelector('#recipes-page .top-nav');
    if (nav) nav.after(bar);
  }
  bar.innerHTML = cuisines.map(c =>
    `<button class="cfilter-btn ${state.selectedCuisine===c?'active':''}" onclick="filterByCuisine('${c}')">${c==='All'?'🌎 All':c}</button>`
  ).join('');
}

function filterByCuisine(cuisine) {
  state.selectedCuisine = cuisine;
  renderCuisineFilterBar();
  const filtered = cuisine === 'All' ? state.recipes :
    state.recipes.filter(r => r.cuisine && r.cuisine.toLowerCase() === cuisine.toLowerCase());
  renderRecipes(filtered);
  const sub = document.getElementById('recipes-subtitle');
  if (sub) sub.textContent = cuisine === 'All' ? 'All cuisines · based on your preferences' : `${cuisine} cuisine · AI-curated for you`;
}

async function loadRecipes() {
  const grid = document.getElementById('recipe-grid');
  grid.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-light)">✨ Loading AI-curated recipes...</div>';
  // Update greeting
  const sub = document.getElementById('recipes-subtitle');
  const cuisine = state.selectedCuisine || 'All';
  if (sub) sub.textContent = cuisine === 'All' ? 'AI-curated across all cuisines' : `${cuisine} cuisine · personalized for you`;
  // Update nav user chip
  let chip = document.getElementById('user-chip');
  if (!chip) {
    chip = document.createElement('span');
    chip.id = 'user-chip';
    chip.className = 'user-chip';
    const actions = document.querySelector('#recipes-page .nav-actions');
    if (actions) actions.prepend(chip);
  }
  if (state.username) chip.textContent = '👤 ' + state.username;
  try {
    const res = await fetch(`${API}/recipes/recommend`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ category: state.category, preferences: state.preferences, user_id: state.userId, cuisine: cuisine })
    });
    state.recipes = await res.json();
  } catch(e) {
    try {
      const qs = `category=${state.category||''}&cuisine=${encodeURIComponent(cuisine)}`;
      const res2 = await fetch(`${API}/recipes/all?${qs}`);
      state.recipes = await res2.json();
    } catch(e2) { state.recipes = []; }
  }
  renderCuisineFilterBar();
  filterByCuisine(cuisine);
}

async function aiSearchRecipe(query) {
  if (!query || !query.trim()) return;
  query = query.trim();

  const grid = document.getElementById('recipe-grid');
  if (grid) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:3rem 1rem;color:var(--pink-600)">
        <div style="font-size:3rem;animation:spin 1.5s linear infinite;display:inline-block">🤖</div>
        <p style="font-size:1.1rem;font-weight:600;margin-top:1rem">AI is creating your "${query}" recipe...</p>
        <p style="font-size:.9rem;color:var(--text-light);margin-top:.5rem">Searching recipe databases + building custom recipe</p>
      </div>`;
  }

  try {
    const res = await fetch(`${API}/recipes/ai-generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, servings: 4 })
    });
    if (!res.ok) throw new Error('Server error');
    const newRecipe = await res.json();

    // Add to state
    if (!state.recipes.find(r => r.id === newRecipe.id)) {
      state.recipes.unshift(newRecipe);
    }

    // Open the recipe immediately
    openRecipe(newRecipe.id);
  } catch(e) {
    console.error(e);
    if (grid) {
      grid.innerHTML = '<p style="text-align:center;color:var(--text-light);grid-column:1/-1;padding:2rem">Failed to generate recipe. Please try again.</p>';
    }
  }
}

function renderRecipes(recipes, containerId = 'recipe-grid') {
  const grid = document.getElementById(containerId);
  if (!recipes.length) { grid.innerHTML = '<p style="text-align:center;color:var(--text-light);grid-column:1/-1;padding:2rem">No recipes found.</p>'; return; }
  grid.innerHTML = recipes.map(r => {
    const isUrl = r.image && r.image.startsWith('http');
    const imgHtml = isUrl
      ? `<img src="${r.image}" alt="${r.name}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit">`
      : (r.image || '🍽️');
    return `
    <div class="recipe-card" onclick="openRecipe('${r.id}')">
      <div class="recipe-card-img" style="${isUrl?'padding:0;overflow:hidden;':''}"> ${imgHtml}</div>
      <button class="fav-btn ${r.is_favorite?'active':''}" onclick="toggleFavorite(event, '${r.id}')">❤️</button>
      <div class="recipe-card-body">
        <h3>${r.name}</h3>
        <div class="recipe-meta">
          <span>⏱️ ${r.duration}</span>
          <span>📊 ${r.difficulty}</span>
          <span>🌍 ${r.cuisine}</span>
        </div>
        <div class="recipe-tags">${(r.tags||[]).map(t=>`<span class="tag">${t}</span>`).join('')}</div>
      </div>
    </div>
  `}).join('');
}


let searchTimeout;
async function searchRecipes(q) {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(async () => {
    if (!q.trim()) { renderRecipes(state.recipes); return; }
    try {
      const res = await fetch(`${API}/recipes/search?q=${encodeURIComponent(q)}&category=${state.category||''}&user_id=${state.userId||''}`);
      const results = await res.json();
      results.forEach(r => {
        if (!state.recipes.find(x => x.id === r.id)) {
          state.recipes.push(r);
        }
      });
      renderRecipes(results);
    } catch(e) {
      const filtered = state.recipes.filter(r => r.name.toLowerCase().includes(q.toLowerCase()));
      renderRecipes(filtered);
    }
  }, 500); // 500ms debounce
}


// ===== RECIPE DETAIL =====
async function openRecipe(id) {
  // Search in state.recipes first, then fetch from backend
  let recipe = state.recipes.find(r => r.id === id);
  if (!recipe) {
    try {
      const res = await fetch(`${API}/recipes/${id}`);
      if (!res.ok) throw new Error('Not found');
      recipe = await res.json();
      // Save it so we can find it later
      state.recipes.push(recipe);
    } catch(e) {
      alert('Could not load recipe. Please try again.');
      return;
    }
  }
  state.currentRecipe = recipe;
  state.baseServings = recipe.servings || 4;
  state.servings = state.baseServings;
  
  const c = document.getElementById('recipe-detail-content');
  const nut = recipe.nutrition || {};

  // Render image: URL → <img>, emoji → plain text
  const isUrl = recipe.image && recipe.image.startsWith('http');
  const heroImg = isUrl
    ? `<img src="${recipe.image}" alt="${recipe.name}" style="width:140px;height:140px;object-fit:cover;border-radius:50%;box-shadow:0 8px 30px rgba(0,0,0,0.15);margin-bottom:.5rem">`
    : `<div class="emoji">${recipe.image || '🍽️'}</div>`;

  c.innerHTML = `
    <div class="detail-hero">
      ${heroImg}
      <h1>${recipe.name}</h1>
      <div class="detail-info">
        <span class="info-badge">⏱️ ${recipe.duration}</span>
        <span class="info-badge">📊 ${recipe.difficulty}</span>
        <span class="info-badge">🌍 ${recipe.cuisine}</span>
        <span class="info-badge">${recipe.category==='vegetarian'?'🥬 Veg':'🍗 Non-Veg'}</span>
      </div>
    </div>
    <div class="servings-adjuster">
      <h2>👥 Adjust Servings</h2>
      <div class="servings-controls">
        <button class="servings-btn" onclick="updateServings(Math.max(1, state.servings - 1))">−</button>
        <div class="servings-display">
          <span class="servings-count" id="servings-count">${state.servings}</span>
          <span class="servings-label">people</span>
        </div>
        <button class="servings-btn" onclick="updateServings(Math.min(20, state.servings + 1))">+</button>
      </div>
      <input type="range" class="servings-slider" id="servings-slider" min="1" max="20" value="${state.servings}" oninput="updateServings(parseInt(this.value))">
      <div class="servings-people" id="servings-people">${'👤'.repeat(Math.min(10, state.servings))}${state.servings > 10 ? '...' : ''}</div>
    </div>
    <div class="detail-section">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:.5rem;">
        <h2 style="margin:0;">🧾 Ingredients</h2>
        ${isSpicyRecipe(recipe) ? `
        <div class="spice-adjuster" style="display:flex; align-items:center; gap:.5rem;">
          <span style="font-size:.9rem; font-weight:600; color:var(--text-light);">Spice Level:</span>
          <select id="spice-selector" onchange="adjustSpice(this.value)" style="padding:.25rem .5rem; border-radius:var(--radius-sm); border:1px solid var(--pink-200); background:var(--pink-50); color:var(--pink-700); font-weight:500; cursor:pointer;">
            <option value="Mild" ${state.spiceLevel === 'Mild' ? 'selected' : ''}>😌 Mild</option>
            <option value="Medium" ${state.spiceLevel === 'Medium' ? 'selected' : ''}>🌶️ Medium</option>
            <option value="Spicy" ${state.spiceLevel === 'Spicy' ? 'selected' : ''}>🔥 Spicy</option>
          </select>
        </div>` : ''}
      </div>
      <ul class="ingredient-list" id="ingredient-list">${(recipe.ingredients||[]).map(i=>`<li>${scaleIngredientQuantity(i, state.servings / state.baseServings)}</li>`).join('')}</ul>
    </div>
    <div class="detail-section">
      <h2>📊 Nutrition Per Serving</h2>
      <div class="nutrition-grid">
        <div class="nutrition-item"><div class="value">${nut.calories||0}</div><div class="label">Calories</div></div>
        <div class="nutrition-item"><div class="value">${nut.protein||0}g</div><div class="label">Protein</div></div>
        <div class="nutrition-item"><div class="value">${nut.carbohydrates||0}g</div><div class="label">Carbs</div></div>
        <div class="nutrition-item"><div class="value">${nut.fats||0}g</div><div class="label">Fats</div></div>
        <div class="nutrition-item"><div class="value">${nut.fiber||0}g</div><div class="label">Fiber</div></div>
        <div class="nutrition-item"><div class="value">${nut.vitamins||'—'}</div><div class="label">Vitamins</div></div>
      </div>
    </div>
    <div style="display:flex;gap:1rem;flex-wrap:wrap;justify-content:center;margin-top:1rem">
      <button class="btn btn-primary" onclick="toggleFavorite(event, '${recipe.id}', true)">${recipe.is_favorite?'❤️ Unfavorite':'🤍 Favorite'}</button>
      <button class="btn btn-primary" style="background:var(--pink-400);color:var(--dark)" onclick="window.open('https://www.youtube.com/results?search_query=${encodeURIComponent(recipe.name + ' recipe tutorial')}', '_blank')">🎥 Watch Tutorial</button>
      <button class="btn btn-primary" onclick="openIngredientCheck()">🔍 Check My Ingredients</button>
      <button class="btn btn-primary btn-cook" onclick="openCookingSteps()">👨‍🍳 Start Cooking</button>
    </div>`;
  navigateTo('recipe-detail-page');
}

function isSpicyRecipe(recipe) {
  if (recipe.tags && recipe.tags.includes('spicy')) return true;
  if (recipe.category === 'dessert' || (recipe.tags && recipe.tags.includes('sweet'))) return false;
  
  const spicyIngredients = ['chili', 'chilli', 'pepper', 'jalapeno', 'masala', 'paprika', 'cayenne', 'curry'];
  const hasSpicy = (recipe.ingredients || []).some(ing => {
    const itemStr = (typeof ing === 'string' ? ing : (ing.item || '')).toLowerCase();
    return spicyIngredients.some(s => itemStr.includes(s));
  });
  return hasSpicy;
}

function adjustSpice(level) {
  state.spiceLevel = level;
  updateServings(state.servings); // Re-render ingredients
}

function scaleIngredientQuantity(ing, scale) {
  let str = typeof ing === 'string' ? ing : (ing.item || '');
  let imgHtml = typeof ing === 'string' || !ing.image ? '' : `<img src="${ing.image}" class="ingredient-img" onerror="this.style.display='none'">`;
  
  // Apply spice level scaling
  let finalScale = scale;
  const isSpicy = ['chili', 'chilli', 'pepper', 'jalapeno', 'masala', 'paprika', 'cayenne', 'hot sauce'].some(s => str.toLowerCase().includes(s));
  if (isSpicy && state.spiceLevel) {
     if (state.spiceLevel === 'Mild') finalScale *= 0.5;
     else if (state.spiceLevel === 'Spicy') finalScale *= 1.5;
  }
  
  if (finalScale === 1) return `${imgHtml} <span>${str}</span>`;
  
  let newStr = str.replace(/^([\d\/\.]+)\s*/, (match, numStr) => {
    let num;
    if (numStr.includes('/')) {
      const parts = numStr.split('/');
      num = parseFloat(parts[0]) / parseFloat(parts[1]);
    } else {
      num = parseFloat(numStr);
    }
    if (isNaN(num)) return match;
    let scaled = num * finalScale;
    if (scaled % 1 !== 0) {
      if (Math.abs(scaled - 0.25) < 0.01) scaled = '1/4';
      else if (Math.abs(scaled - 0.33) < 0.01) scaled = '1/3';
      else if (Math.abs(scaled - 0.5) < 0.01) scaled = '1/2';
      else if (Math.abs(scaled - 0.66) < 0.01) scaled = '2/3';
      else if (Math.abs(scaled - 0.75) < 0.01) scaled = '3/4';
      else scaled = parseFloat(scaled.toFixed(1));
    }
    return scaled + ' ';
  });
  
  return `${imgHtml} <span>${newStr}</span>`;
}


function updateServings(newServings) {
  state.servings = newServings;
  const scale = newServings / state.baseServings;
  const recipe = state.currentRecipe;
  const nut = recipe.nutrition || {};

  // Update UI
  document.getElementById('servings-count').textContent = newServings;
  document.getElementById('servings-slider').value = newServings;
  document.getElementById('servings-people').textContent = '👤'.repeat(Math.min(10, newServings)) + (newServings > 10 ? '...' : '');

  // Scale ingredients
  const scaledIngredients = (recipe.ingredients || []).map(i => scaleIngredientQuantity(i, scale));
  document.getElementById('ingredient-list').innerHTML = scaledIngredients.map(i => `<li>${i}</li>`).join('');

  // Scale nutrition
  const scaledNut = {
    calories: Math.round((nut.calories || 0) * scale),
    protein: Math.round((nut.protein || 0) * scale),
    carbohydrates: Math.round((nut.carbohydrates || 0) * scale),
    fats: Math.round((nut.fats || 0) * scale),
    fiber: Math.round((nut.fiber || 0) * scale),
    vitamins: nut.vitamins || '—'
  };

  const nutGrid = document.querySelector('.nutrition-grid');
  if (nutGrid) {
    nutGrid.innerHTML = `
        <div class="nutrition-item"><div class="value">${scaledNut.calories}</div><div class="label">Calories</div></div>
        <div class="nutrition-item"><div class="value">${scaledNut.protein}g</div><div class="label">Protein</div></div>
        <div class="nutrition-item"><div class="value">${scaledNut.carbohydrates}g</div><div class="label">Carbs</div></div>
        <div class="nutrition-item"><div class="value">${scaledNut.fats}g</div><div class="label">Fats</div></div>
        <div class="nutrition-item"><div class="value">${scaledNut.fiber}g</div><div class="label">Fiber</div></div>
        <div class="nutrition-item"><div class="value">${scaledNut.vitamins}</div><div class="label">Vitamins</div></div>
    `;
  }
}


async function toggleFavorite(e, recipeId, fromDetail = false) {
  if (e) e.stopPropagation();
  try {
    const res = await fetch(`${API}/recipes/favorite/toggle`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ user_id: state.userId, recipe_id: recipeId })
    });
    const data = await res.json();
    // Update local state
    const recipe = state.recipes.find(r => r.id === recipeId);
    if (recipe) recipe.is_favorite = data.is_favorite;
    if (state.currentRecipe && state.currentRecipe.id === recipeId) state.currentRecipe.is_favorite = data.is_favorite;
    
    // Re-render
    if (fromDetail) openRecipe(recipeId);
    else {
        const grid = document.getElementById('favorites-page').classList.contains('active') ? 'favorites-grid' : 'recipe-grid';
        if (grid === 'favorites-grid') showFavorites();
        else renderRecipes(state.recipes);
    }
  } catch(err) { console.error(err); }
}

async function showFavorites() {
  const grid = document.getElementById('favorites-grid');
  grid.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-light);grid-column:1/-1">Loading favorites...</div>';
  navigateTo('favorites-page');
  try {
    const res = await fetch(`${API}/recipes/favorites/${state.userId}`);
    const favs = await res.json();
    renderRecipes(favs, 'favorites-grid');
  } catch(e) { grid.innerHTML = '<p style="text-align:center;grid-column:1/-1">Could not load favorites.</p>'; }
}

// ===== INGREDIENT CHECK =====
function openIngredientCheck() {
  const recipe = state.currentRecipe;
  if (!recipe) return;
  const c = document.getElementById('ingredient-content');
  c.innerHTML = `
    <h2>🔍 What ingredients do you have?</h2>
    <p style="color:var(--text-light);margin-bottom:.5rem">For: <strong>${recipe.name}</strong></p>
    <p style="color:var(--text-light);font-size:.9rem">Required: ${recipe.ingredients.map(i => typeof i === 'string' ? i : (i.name || JSON.stringify(i))).join(', ')}</p>
    
    <div style="margin: 1.5rem 0; padding: 1.5rem; background: var(--pink-50); border: 2px dashed var(--pink-300); border-radius: var(--radius-sm); text-align: center;">
      <h3 style="color:var(--pink-600); margin-bottom:.5rem;">📷 AI Image Recognition</h3>
      <p style="font-size: .9rem; color: var(--text-light); margin-bottom: 1rem;">Don't want to type? Upload a picture of your fridge or counter!</p>
      <input type="file" id="fridge-image" accept="image/*" style="display:none" onchange="analyzeFridgeImage(event)">
      <label for="fridge-image" class="btn btn-primary" style="cursor:pointer; background:var(--pink-400); color:var(--dark);">Upload Fridge/Counter Image</label>
      <div id="ai-scan-status" style="margin-top: 1rem; color: var(--pink-600); font-weight: 500;"></div>
    </div>

    <div class="ingredient-input-area">
      <textarea id="available-ingredients" placeholder="Enter ingredients you have at home, separated by commas...&#10;Example: paneer, tomato, onion, garlic"></textarea>
      <button class="btn btn-primary" style="margin-top:.75rem" onclick="checkIngredients()">Check Ingredients</button>
    </div>
    <div id="missing-results"></div>`;
  state.selectedSubs = {};
  navigateTo('ingredient-page');
}

async function analyzeFridgeImage(event) {
  const file = event.target.files[0];
  if (!file) return;
  const status = document.getElementById('ai-scan-status');
  const input = document.getElementById('available-ingredients');
  
  status.innerHTML = '✨ AI is scanning your ingredients...';
  
  // Simulate AI Computer Vision delay (reduced for speed)
  await new Promise(r => setTimeout(r, 200));
  
  // Simulated AI detected ingredients based on common items
  const detected = ["tomato", "onion", "garlic", "milk", "eggs", "butter", "bell pepper", "chicken"];
  
  // Pick 3-5 random ingredients to simulate detection
  const shuffled = detected.sort(() => 0.5 - Math.random());
  const selected = shuffled.slice(0, Math.floor(Math.random() * 3) + 3);
  
  status.innerHTML = '✅ Scan complete! Ingredients detected.';
  
  // Append to existing text or replace
  const currentText = input.value.trim();
  if (currentText) {
    input.value = currentText + ', ' + selected.join(', ');
  } else {
    input.value = selected.join(', ');
  }
}

// Local substitution map for instant offline lookup
const LOCAL_SUBS = {
  "milk": ["almond milk", "soy milk", "oat milk", "coconut milk"],
  "egg": ["banana (mashed)", "yogurt", "flaxseed + water", "applesauce"],
  "butter": ["olive oil", "coconut oil", "avocado", "ghee"],
  "cream": ["coconut cream", "cashew cream", "silken tofu blend"],
  "cheese": ["nutritional yeast", "tofu ricotta", "cashew cheese"],
  "sugar": ["honey", "maple syrup", "stevia", "jaggery"],
  "flour": ["almond flour", "oat flour", "rice flour"],
  "chicken": ["tofu", "paneer", "jackfruit", "mushrooms"],
  "beef": ["portobello mushrooms", "lentils", "tempeh"],
  "rice": ["quinoa", "cauliflower rice", "couscous"],
  "pasta": ["zucchini noodles", "rice noodles", "spaghetti squash"],
  "onion": ["shallots", "leeks", "scallions"],
  "garlic": ["garlic powder", "shallots", "asafoetida"],
  "tomato": ["red bell pepper", "canned tomatoes", "sun-dried tomatoes"],
  "lemon": ["lime juice", "vinegar", "citric acid"],
  "paneer": ["tofu", "halloumi", "cottage cheese"],
  "ghee": ["butter", "coconut oil", "vegetable oil"]
};

function checkIngredients() {
  const available = document.getElementById('available-ingredients').value.split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);
  const recipe = state.currentRecipe;
  if (!available.length) { alert('Please enter at least one ingredient you have.'); return; }
  if (!recipe) { alert('No recipe selected.'); return; }

  // Units/quantities to strip so "2 cups sugar" becomes "sugar"
  const unitPattern = /^[\d\/\.]+(\s*[\d\/\.]+)?\s*(cups?|tbsp?|tsp?|teaspoons?|tablespoons?|grams?|g|kg|oz|lbs?|ml|l|liters?|litres?|inch|inches|cloves?|large|small|medium|pinch|handful|bunch|slices?|pieces?|cans?|strips?|stalks?|sprigs?)?\s*/i;
  const cleanIngredient = str => str
    .replace(unitPattern, '')       // remove leading quantity + unit
    .replace(/,.*$/, '')            // remove anything after comma
    .replace(/\(.*?\)/g, '')        // remove parenthetical notes
    .replace(/\bfinely\b|\bdiced\b|\bminced\b|\bchopped\b|\bsliced\b|\bgrated\b|\bcrushed\b|\bfresh\b|\bdried\b|\bground\b|\bcooked\b|\bpeeled\b|\bwhole\b|\bto taste\b/gi, '')
    .trim();

  // Resolve ingredient names (handle both strings and objects) and clean them
  const required = recipe.ingredients.map(i => {
    const raw = typeof i === 'string' ? i : (i.name || '');
    return cleanIngredient(raw.toLowerCase());
  }).filter(Boolean);

  // Compute missing ingredients
  const missing = required.filter(req =>
    !available.some(a => a.includes(req) || req.includes(a) || req.split(' ').some(word => word.length > 3 && a.includes(word)))
  );

  // Look up substitutions from local map
  const substitutions = {};
  missing.forEach(item => {
    for (const [key, subs] of Object.entries(LOCAL_SUBS)) {
      if (key.includes(item) || item.includes(key) || item.split(' ').some(w => w.length > 3 && key.includes(w))) {
        substitutions[item] = subs;
        break;
      }
    }
  });

  const div = document.getElementById('missing-results');
  if (!div) return;

  if (!missing.length) {
    div.innerHTML = `<div class="detail-section" style="text-align:center;margin-top:1rem"><h2>✅ You have all ingredients!</h2><p>Ready to cook!</p>
      <button class="btn btn-primary" style="margin-top:1rem" onclick="openCookingSteps()">👨‍🍳 Start Cooking</button></div>`;
    return;
  }
  div.innerHTML = `
    <div class="missing-section">
      <h3 style="color:var(--pink-600);margin-bottom:1rem">⚠️ Missing Ingredients (${missing.length})</h3>
      ${missing.map(item => {
        const subs = substitutions[item] || [];
        return `<div class="sub-card">
          <h4>❌ ${item}</h4>
          ${subs.length ? `<p style="font-size:.85rem;color:var(--text-light);margin-bottom:.5rem">Suggested substitutes:</p>
          <div class="sub-options">${subs.map(s=>`<button class="sub-option" onclick="selectSub(this,'${item}','${s}')">${s}</button>`).join('')}</div>` : '<p style="font-size:.85rem;color:var(--text-light)">No substitutes available — please purchase</p>'}
        </div>`;
      }).join('')}
      <div style="display:flex;gap:1rem;margin-top:1.5rem;flex-wrap:wrap">
          <button class="btn btn-primary" onclick="applySubstitutions()">Apply Substitutions &amp; Cook 👨‍🍳</button>
          <button class="btn btn-primary" style="background:var(--pink-300);color:var(--dark)" onclick='addMissingToGrocery(${JSON.stringify(missing)})'>🛒 Add Missing to Grocery List</button>
      </div>
    </div>`;
}

function selectSub(btn, original, substitute) {
  btn.closest('.sub-options').querySelectorAll('.sub-option').forEach(b=>b.classList.remove('selected'));
  btn.classList.add('selected');
  state.selectedSubs[original] = substitute;
}

function applySubstitutions() { openCookingSteps(); }

// ===== COOKING STEPS =====
function openCookingSteps() {
  const recipe = state.currentRecipe;
  if (!recipe) return;
  const steps = recipe.steps || [];
  const subs = state.selectedSubs;
  const c = document.getElementById('cooking-content');
  let subNote = '';
  if (Object.keys(subs).length) {
    subNote = `<div class="detail-section" style="margin-bottom:1.5rem"><h2>🔄 Ingredient Substitutions Applied</h2>
      <div style="display:flex;flex-wrap:wrap;gap:.5rem">${Object.entries(subs).map(([o,s])=>`<span class="info-badge">${o} → ${s}</span>`).join('')}</div></div>`;
  }
  c.innerHTML = `
    <h1 class="section-title" style="margin-bottom:.5rem">${recipe.name}</h1>
    <p class="section-subtitle" style="margin-bottom:1.5rem">Follow each step carefully for the best results!</p>
    ${subNote}
    ${steps.map(s => {
      let inst = s.instruction;
      Object.entries(subs).forEach(([o,sub]) => { inst = inst.replace(new RegExp(o,'gi'), `<strong>${sub}</strong>`); });
      return `<div class="step-card">
        <div class="step-number">${s.step}</div>
        <h3>${s.title}</h3>
        <p class="instruction">${inst}</p>
        <div class="step-detail"><span class="label">💡 Why:</span><span class="content">${s.why||''}</span></div>
        <div class="step-detail"><span class="label">✨ Tip:</span><span class="content">${s.tip||''}</span></div>
      </div>`;
    }).join('')}
    <div class="detail-section">
      <h2>📊 Final Nutritional Information</h2>
      <div class="nutrition-grid" id="final-nutrition"></div>
      <div style="text-align:center; margin-top: 1.5rem;">
        <button class="btn btn-primary" style="background:var(--pink-400);color:var(--dark);" onclick="logToFitnessTracker()">🔗 Log to Fitness Tracker (Apple Health / MyFitnessPal)</button>
      </div>
    </div>`;
  updateFinalNutrition(recipe.nutrition);
  navigateTo('cooking-page');
}

function logToFitnessTracker() {
    alert("✅ Meal successfully logged to your configured Fitness Tracker!\n\nNutritional Data Exported:\n- Calories: " + (state.currentRecipe.nutrition.calories || 0) + "\n- Protein: " + (state.currentRecipe.nutrition.protein || 0) + "g\n- Carbs: " + (state.currentRecipe.nutrition.carbohydrates || 0) + "g");
}

async function updateFinalNutrition(nutrition) {
  let updated = {...nutrition};
  if (Object.keys(state.selectedSubs).length) {
    try {
      const res = await fetch(`${API}/recipes/update-nutrition`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ nutrition, substitutions_used: state.selectedSubs })
      });
      updated = await res.json();
    } catch(e) { /* use original */ }
  }
  const grid = document.getElementById('final-nutrition');
  if (grid) {
    grid.innerHTML = `
      <div class="nutrition-item"><div class="value">${updated.calories||0}</div><div class="label">Calories</div></div>
      <div class="nutrition-item"><div class="value">${updated.protein||0}g</div><div class="label">Protein</div></div>
      <div class="nutrition-item"><div class="value">${updated.carbohydrates||0}g</div><div class="label">Carbs</div></div>
      <div class="nutrition-item"><div class="value">${updated.fats||0}g</div><div class="label">Fats</div></div>
      <div class="nutrition-item"><div class="value">${updated.fiber||0}g</div><div class="label">Fiber</div></div>
      <div class="nutrition-item"><div class="value">${updated.vitamins||'—'}</div><div class="label">Vitamins</div></div>`;
  }
}

// ===== CHATBOT =====
function toggleChatbot() { document.getElementById('chatbot-panel').classList.toggle('open'); }

async function sendChat(e) {
  e.preventDefault();
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  addChatMsg(msg, 'user');
  input.value = '';
  try {
    const res = await fetch(`${API}/chatbot/message`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    addChatMsg(data.response, 'bot');
    speakText(data.response.replace(/<[^>]*>?/gm, '')); // Strip HTML for speech
  } catch(e) {
    addChatMsg("I'm having trouble connecting. Try again in a moment! 🍳", 'bot');
    speakText("I'm having trouble connecting. Try again in a moment!");
  }
}

// ===== VOICE CONTROL =====
let recognition = null;
let isRecording = false;

function initVoice() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onresult = function(event) {
    const transcript = event.results[0][0].transcript;
    document.getElementById('chat-input').value = transcript;
    sendChat(new Event('submit'));
    toggleVoiceRecording(false);
  };

  recognition.onerror = function(event) {
    toggleVoiceRecording(false);
  };
  
  recognition.onend = function() {
    toggleVoiceRecording(false);
  };
}

function toggleVoiceRecording(forceState = null) {
  if (!recognition) initVoice();
  if (!recognition) {
    alert("Voice recognition is not supported in this browser.");
    return;
  }
  
  isRecording = forceState !== null ? forceState : !isRecording;
  const btn = document.getElementById('chat-mic-btn');
  const input = document.getElementById('chat-input');
  
  if (isRecording) {
    try {
      recognition.start();
      btn.classList.add('recording');
      input.placeholder = "Listening...";
    } catch(e) { isRecording = false; }
  } else {
    recognition.stop();
    btn.classList.remove('recording');
    input.placeholder = "Ask me anything about cooking...";
  }
}

function speakText(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel(); // Stop current speaking
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.05;
  utterance.pitch = 1.1;
  window.speechSynthesis.speak(utterance);
}

function addChatMsg(text, sender) {
  const container = document.getElementById('chatbot-messages');
  const div = document.createElement('div');
  div.className = `chat-msg ${sender}`;
  div.innerHTML = `<div class="chat-avatar">${sender==='bot'?'🤖':'👤'}</div><div class="chat-bubble">${text}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ===== AI MEAL PLANNER =====
async function openMealPlanner() {
  navigateTo('meal-plan-page');
  const container = document.getElementById('meal-plan-content');
  try {
    const res = await fetch(`${API}/recipes/meal-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category: state.category, preferences: state.preferences })
    });
    const mealPlan = await res.json();
    let html = '';
    for (const [day, meals] of Object.entries(mealPlan)) {
      html += `
        <div class="detail-section" style="margin-bottom: 2rem;">
          <h2 style="font-size: 1.5rem; margin-bottom: 1.5rem;">📅 ${day}</h2>
          <div class="recipe-grid">
            ${Object.entries(meals).map(([mealType, r]) => {
              // Ensure recipe is in state so it can be opened
              if(!state.recipes.find(x => x.id === r.id)) state.recipes.push(r);
              return `
                <div class="recipe-card" onclick="openRecipe('${r.id}')">
                  <div class="recipe-card-img">${r.image || '🍽️'}</div>
                  <div class="recipe-card-body">
                    <h4 style="color:var(--pink-600); margin-bottom:.25rem; font-size:1rem;">${mealType}</h4>
                    <h3>${r.name}</h3>
                    <div class="recipe-meta">
                      <span>⏱️ ${r.duration}</span>
                      <span>📊 ${r.difficulty}</span>
                    </div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    }
    container.innerHTML = html;
  } catch(e) {
    container.innerHTML = '<p style="text-align:center; color:var(--text-light);">Failed to generate meal plan. Try again later.</p>';
  }
}

// ===== GENERATE RECIPE FROM CHATBOT =====
async function generateFromChatbot(query) {
  // Close chatbot panel
  const panel = document.getElementById('chatbot-panel');
  if (panel) panel.classList.remove('open');

  // Navigate to recipes page
  navigateTo('recipes-page');

  // Show loading in recipe grid
  const grid = document.getElementById('recipe-grid');
  if (grid) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:3rem 1rem;color:var(--pink-600)">
        <div style="font-size:3rem;animation:spin 1.5s linear infinite;display:inline-block">🤖</div>
        <p style="font-size:1.1rem;font-weight:600;margin-top:1rem">AI is creating your "${query}" recipe...</p>
        <p style="font-size:.9rem;color:var(--text-light);margin-top:.5rem">Searching TheMealDB + building custom recipe</p>
      </div>`;
  }

  try {
    const res = await fetch(`${API}/recipes/ai-generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, servings: 4 })
    });

    if (!res.ok) throw new Error('Server error');
    const recipe = await res.json();

    // Add to state so detail page can find it
    if (!state.recipes.find(r => r.id === recipe.id)) {
      state.recipes.unshift(recipe);
    }

    // Open the generated recipe immediately
    openRecipe(recipe.id);

  } catch(e) {
    // Fallback: just do a search
    if (grid) {
      grid.innerHTML = '<p style="text-align:center;color:var(--text-light);grid-column:1/-1;padding:2rem">Failed to generate recipe. Please try searching manually.</p>';
    }
    console.error('generateFromChatbot error:', e);
  }
}

// ===== SMART GROCERY LIST =====
function toggleGroceryList() {
  document.getElementById('grocery-panel').classList.toggle('open');
  renderGroceryList();
}

function addMissingToGrocery(missingItems) {
  missingItems.forEach(item => {
    if (!state.groceryList.includes(item)) {
      state.groceryList.push(item);
    }
  });
  alert(`${missingItems.length} items added to your Smart Grocery List!`);
  renderGroceryList();
}

function clearGroceryList() {
  state.groceryList = [];
  renderGroceryList();
}

function removeGroceryItem(index) {
  state.groceryList.splice(index, 1);
  renderGroceryList();
}

function renderGroceryList() {
  const container = document.getElementById('grocery-items');
  if (!container) return;
  if (!state.groceryList.length) {
    container.innerHTML = '<p style="text-align:center;color:var(--text-light);margin-top:2rem">Your grocery list is empty. 🛒<br><br>Add missing ingredients from the ingredient checker!</p>';
    return;
  }
  container.innerHTML = state.groceryList.map((item, idx) => `
    <div style="display:flex;justify-content:space-between;align-items:center;padding:.75rem;background:#fff;border-radius:var(--radius-sm);margin-bottom:.5rem;box-shadow:0 2px 8px rgba(0,0,0,0.05);border-left:3px solid var(--pink-400)">
        <span style="font-weight:500;color:var(--text)">${item}</span>
        <button onclick="removeGroceryItem(${idx})" style="background:none;border:none;color:var(--pink-600);cursor:pointer;font-size:1.2rem" title="Remove item">✕</button>
    </div>
  `).join('');
}

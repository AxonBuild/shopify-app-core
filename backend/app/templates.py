DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shopify Data Dashboard</title>
    <!-- Tailwind CSS for instant clean styling -->
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
        body {{ font-family: 'Inter', sans-serif; background-color: #f7fafc; }}
        .card {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 20px; }}
    </style>
</head>
<body class="bg-gray-50 min-h-screen p-8">
    <div class="max-w-6xl mx-auto">
        <!-- Header -->
        <header class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-2xl font-bold text-gray-800">Shopify Data Dashboard</h1>
                <p class="text-gray-500 text-sm mt-1">Status: <span class="text-green-600 font-semibold">● Connected</span></p>
                <div class="text-xs text-gray-400 mt-1">Shop: {shop_domain} | Token: ••••••{masked_token}</div>
            </div>
            <a href="/" class="px-4 py-2 bg-white border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50">Back Home</a>
        </header>

        <!-- Stats Grid -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="card border-l-4 border-blue-500">
                <div class="text-gray-500 text-sm font-medium uppercase">Total Products</div>
                <div class="text-3xl font-bold text-gray-800 mt-2">{product_count}</div>
            </div>
            <div class="card border-l-4 border-green-500">
                <div class="text-gray-500 text-sm font-medium uppercase">Total Customers</div>
                <div class="text-3xl font-bold text-gray-800 mt-2">{customer_count}</div>
            </div>
            <div class="card border-l-4 border-purple-500">
                <div class="text-gray-500 text-sm font-medium uppercase">Recent Orders</div>
                <div class="text-3xl font-bold text-gray-800 mt-2">{order_count}</div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <!-- Products Section -->
            <div class="card">
                <h2 class="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b">Recent Products</h2>
                <div class="space-y-3">
                    {products_html}
                </div>
            </div>

            <!-- Customers Section -->
            <div class="card">
                <h2 class="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b">Recent Customers</h2>
                <div class="space-y-3">
                    {customers_html}
                </div>
            </div>
        </div>

        <!-- Orders Section -->
        <div class="card mt-8">
            <h2 class="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b">Latest Orders</h2>
            <div class="overflow-x-auto">
                <table class="min-w-full text-left text-sm">
                    <thead class="bg-gray-50 text-gray-500 font-medium">
                        <tr>
                            <th class="px-4 py-2">Order #</th>
                            <th class="px-4 py-2">Date</th>
                            <th class="px-4 py-2">Customer</th>
                            <th class="px-4 py-2">Total</th>
                            <th class="px-4 py-2">Status</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">
                        {orders_html}
                    </tbody>
                </table>
            </div>
        </div>
        
    </div>
</body>
</html>
"""

def generate_product_row(p):
    img = p.get('image', {}).get('src') if p.get('image') else 'https://via.placeholder.com/40'
    return f"""
    <div class="flex items-center space-x-3 p-2 hover:bg-gray-50 rounded transition">
        <img src="{img}" class="w-10 h-10 rounded object-cover border" alt="">
        <div>
            <div class="font-medium text-gray-800">{p.get('title')}</div>
            <div class="text-xs text-gray-500">{p.get('product_type', 'Unknown Type')} | {len(p.get('variants', []))} Variants</div>
        </div>
    </div>
    """

def generate_customer_row(c):
    return f"""
    <div class="flex items-center space-x-3 p-2 hover:bg-gray-50 rounded transition">
        <div class="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center font-bold text-xs">
            {c.get('first_name', '?')[0]}{c.get('last_name', '?')[0]}
        </div>
        <div>
            <div class="font-medium text-gray-800">{c.get('first_name')} {c.get('last_name')}</div>
            <div class="text-xs text-gray-500">{c.get('email')} | {c.get('orders_count', 0)} orders</div>
        </div>
    </div>
    """

def generate_order_row(o):
    return f"""
    <tr class="hover:bg-gray-50">
        <td class="px-4 py-3 font-medium text-gray-800">{o.get('name')}</td>
        <td class="px-4 py-3 text-gray-500">{o.get('created_at', '')[:10]}</td>
        <td class="px-4 py-3 text-gray-600">{o.get('customer', {}).get('first_name', 'Guest')} {o.get('customer', {}).get('last_name', '')}</td>
        <td class="px-4 py-3 font-medium text-gray-800">{o.get('total_price')} {o.get('currency')}</td>
        <td class="px-4 py-3"><span class="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">{o.get('financial_status')}</span></td>
    </tr>
    """

SEARCH_VISUALIZER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Isla Search Visualizer</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --bg:        #0d1117;
            --surface:   #161b22;
            --surface2:  #1c2430;
            --border:    #30363d;
            --text:      #e6edf3;
            --muted:     #8b949e;
            --accent:    #58a6ff;
            --green:     #3fb950;
            --yellow:    #d29922;
            --orange:    #f0883e;
            --purple:    #bc8cff;
            --red:       #f85149;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        /* ── Layout ─────────────────────────────────────────────── */
        .container { max-width: 1300px; margin: 0 auto; padding: 40px 24px; }

        header { text-align: center; margin-bottom: 40px; }
        header h1 { font-size: 2rem; font-weight: 800; background: linear-gradient(135deg, var(--accent), var(--purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        header p  { color: var(--muted); margin-top: 8px; font-size: 0.95rem; }

        /* ── Mode tabs ──────────────────────────────────────────── */
        .tabs { display: flex; gap: 8px; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 0; }
        .tab  { padding: 10px 20px; font-size: 0.9rem; font-weight: 600; border: none; border-radius: 8px 8px 0 0; cursor: pointer; background: transparent; color: var(--muted); transition: all .2s; border-bottom: 2px solid transparent; }
        .tab.active { color: var(--accent); border-bottom-color: var(--accent); background: rgba(88,166,255,.07); }

        /* ── Search panel ───────────────────────────────────────── */
        .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 28px; margin-bottom: 28px; }
        label  { display: block; font-size: 0.8rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }

        input[type="text"], select {
            width: 100%; padding: 12px 16px; background: var(--bg);
            border: 1px solid var(--border); border-radius: 10px;
            color: var(--text); font-family: inherit; font-size: .95rem;
            outline: none; transition: border-color .2s;
        }
        input[type="text"]:focus, select:focus { border-color: var(--accent); }
        input[type="file"] { color: var(--muted); font-size: .85rem; }

        .row { display: flex; gap: 16px; align-items: flex-end; }
        .row .grow { flex: 1; }
        .row .w32 { width: 120px; }

        .btn {
            width: 100%; padding: 14px; margin-top: 20px;
            background: var(--accent); color: #000; border: none;
            border-radius: 12px; font-size: .95rem; font-weight: 700;
            cursor: pointer; transition: opacity .2s;
        }
        .btn:hover { opacity: .85; }
        .btn.secondary { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }

        /* ── AI Extraction Panel ────────────────────────────────── */
        .ai-panel {
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 16px; padding: 24px; margin-bottom: 28px;
            display: none;
        }
        .ai-panel.visible { display: block; }
        .ai-panel-title { font-size: .75rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--purple); margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
        .ai-panel-title::before { content: ''; width: 8px; height: 8px; background: var(--purple); border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .4; } }

        .ai-msg { font-size: .9rem; color: var(--text); margin-bottom: 16px; font-style: italic; }

        .tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
        .tag  { padding: 5px 12px; border-radius: 20px; font-size: .78rem; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
        .tag.query  { background: rgba(88,166,255,.12); color: var(--accent); border: 1px solid rgba(88,166,255,.3); }
        .tag.color  { background: rgba(63,185,80,.12);  color: var(--green);  border: 1px solid rgba(63,185,80,.3); }
        .tag.price  { background: rgba(240,136,62,.12); color: var(--orange); border: 1px solid rgba(240,136,62,.3); }
        .tag.filter { background: rgba(210,153,34,.12); color: var(--yellow); border: 1px solid rgba(210,153,34,.3); }
        .tag.none   { background: rgba(139,148,158,.1); color: var(--muted);  border: 1px solid var(--border); }
        .tag.model  { background: rgba(188,140,255,.1); color: var(--purple); border: 1px solid rgba(188,140,255,.3); }

        .ai-meta { display: flex; gap: 16px; font-size: .75rem; color: var(--muted); border-top: 1px solid var(--border); padding-top: 12px; margin-top: 4px; }
        .ai-meta span b { color: var(--text); }

        /* ── Results ─────────────────────────────────────────────── */
        .results-header { font-size: .75rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 16px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }

        .card {
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 14px; overflow: hidden; transition: transform .2s, border-color .2s;
        }
        .card:hover { transform: translateY(-4px); border-color: var(--accent); }
        .card img { width: 100%; aspect-ratio: 1; object-fit: cover; background: var(--surface2); }
        .card-body { padding: 12px 14px; }
        .card-title { font-size: .85rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; }
        .card-type  { font-size: .72rem; color: var(--muted); margin-bottom: 8px; }
        .card-price { font-size: .85rem; font-weight: 700; color: var(--green); }
        .card-meta  { font-size: .7rem; color: var(--muted); margin-top: 3px; }
        .card-score { font-size: .7rem; font-family: 'JetBrains Mono', monospace; color: var(--muted); margin-top: 6px; }
        .card-badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: .65rem; font-weight: 700; text-transform: uppercase; }
        .badge-both  { background: rgba(210,153,34,.2); color: var(--yellow); }
        .badge-text  { background: rgba(63,185,80,.2);  color: var(--green); }
        .badge-image { background: rgba(88,166,255,.2); color: var(--accent); }
        .card-actions { margin-top: 10px; }
        .card-actions a { display: block; text-align: center; font-size: .75rem; font-weight: 600; padding: 7px; background: var(--surface2); border-radius: 8px; color: var(--text); text-decoration: none; transition: background .2s; }
        .card-actions a:hover { background: var(--border); }

        /* ── Loading spinner ───────────────────────────────────── */
        .loading { display: none; text-align: center; padding: 40px; }
        .spinner { width: 40px; height: 40px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto 12px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading p { color: var(--muted); font-size: .9rem; }

        .empty { text-align: center; padding: 60px 20px; color: var(--muted); }
        .empty div { font-size: 2.5rem; margin-bottom: 12px; }

        /* ── Score slider ──────────────────────────────────────── */
        .slider-row { margin-top: 16px; }
        .slider-row label { display: flex; justify-content: space-between; align-items: center; }
        .slider-label-val { font-family: 'JetBrains Mono', monospace; font-size: .8rem;
                            color: var(--accent); font-weight: 700; }
        .slider-hint { font-size: .7rem; color: var(--muted); margin-top: 4px; }
        input[type=range] {
            -webkit-appearance: none; appearance: none;
            width: 100%; height: 4px; border-radius: 4px;
            background: var(--border); outline: none; cursor: pointer;
        }
        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none; appearance: none;
            width: 16px; height: 16px; border-radius: 50%;
            background: var(--accent); cursor: pointer;
            box-shadow: 0 0 6px rgba(88,166,255,.5);
        }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>Isla Search Visualizer</h1>
        <p>Debug the hybrid search pipeline — with or without the AI extraction layer</p>
    </header>

    <!-- Mode Tabs -->
    <div class="tabs">
        <button class="tab active" id="tabAI"     onclick="switchTab('ai')">🤖 AI Search (with tool call)</button>
        <button class="tab"        id="tabDirect" onclick="switchTab('direct')">⚡ Direct Search (no AI)</button>
    </div>

    <!-- ── AI Search Panel ─────────────────────────────────────── -->
    <div id="panelAI">
        <div class="panel">
            <div style="margin-bottom:16px">
                <label>Natural Language Query</label>
                <input type="text" id="aiQuery" placeholder="e.g. Mujhe navy wali jeans chahiye 1200 se kam mein" />
            </div>
            <div class="row">
                <div class="grow">
                    <label>Results to Fetch</label>
                    <select id="aiLimit">
                        <option value="4">4</option>
                        <option value="6" selected>6</option>
                        <option value="9">9</option>
                        <option value="12">12</option>
                    </select>
                </div>
            </div>
            <div class="slider-row">
                <label>
                    Min Score Threshold
                    <span class="slider-label-val" id="aiScoreVal">0.00 (off)</span>
                </label>
                <input type="range" id="aiScore" min="0" max="1" step="0.05" value="0"
                       oninput="updateSlider('aiScore','aiScoreVal')">
                <div class="slider-hint">Drag right to filter out low-relevance results &nbsp;·&nbsp; production default: <b>0.70</b> (Stage 4 only)</div>
            </div>
            <button class="btn" onclick="runAISearch()">🤖 Run AI Search (forced tool call)</button>
        </div>

        <!-- AI Extraction Badge Panel -->
        <div class="ai-panel" id="aiPanel">
            <div class="ai-panel-title">🧠 AI Tool Call Extraction</div>
            <div class="ai-msg" id="aiMessage"></div>
            <div class="tags" id="aiTags"></div>
            <div class="ai-meta" id="aiMeta"></div>
        </div>

        <div class="loading" id="aiLoading">
            <div class="spinner"></div>
            <p id="aiLoadingMsg">Calling AI... extracting search parameters...</p>
        </div>
        <div class="results-header" id="aiResultsHeader" style="display:none"></div>
        <div class="grid" id="aiGrid"></div>
    </div>

    <!-- ── Direct Search Panel ─────────────────────────────────── -->
    <div id="panelDirect" style="display:none">
        <div class="panel">
            <div style="margin-bottom:16px">
                <label>Text Query</label>
                <input type="text" id="directQuery" placeholder="e.g. black cargo pants" />
            </div>
            <div class="row">
                <div class="grow">
                    <label>Color Filter</label>
                    <select id="directColor">
                        <option value="">— Any color —</option>
                        <option>BLACK</option><option>NAVY</option><option>WHITE</option>
                        <option>GREY</option><option>RED</option><option>BLUE</option>
                        <option>YELLOW</option><option>LIGHT BLUE</option><option>DARK BLUE</option>
                        <option>ORANGE</option><option>GREEN</option><option>CHARCOAL</option>
                        <option>AQUA</option><option>BROWN</option><option>SKIN</option>
                        <option>KHAKI</option><option>OLIVE</option><option>BEIGE</option>
                        <option>MUSTARD</option><option>ROYAL BLUE</option>
                    </select>
                </div>
                <div class="grow">
                    <label>Max Price (PKR)</label>
                    <input type="text" id="directPrice" placeholder="e.g. 1200" />
                </div>
                <div class="w32">
                    <label>Limit</label>
                    <select id="directLimit">
                        <option value="4">4</option>
                        <option value="8" selected>8</option>
                        <option value="12">12</option>
                        <option value="20">20</option>
                    </select>
                </div>
            </div>
            <div style="margin-top:16px">
                <label>Image Search (Visual Intent)</label>
                <input type="file" id="directImage" accept="image/*" />
            </div>
            <div class="slider-row">
                <label>
                    Min Score Threshold
                    <span class="slider-label-val" id="directScoreVal">0.00 (off)</span>
                </label>
                <input type="range" id="directScore" min="0" max="1" step="0.05" value="0"
                       oninput="updateSlider('directScore','directScoreVal')">
                <div class="slider-hint">Drag right to filter out low-relevance results &nbsp;·&nbsp; production default: <b>0.70</b> (Stage 4 only)</div>
            </div>
            <button class="btn secondary" onclick="runDirectSearch()">⚡ Execute Hybrid Search</button>
        </div>

        <div class="loading" id="directLoading">
            <div class="spinner"></div>
            <p>Embedding and searching...</p>
        </div>
        <div class="results-header" id="directResultsHeader" style="display:none"></div>
        <div class="grid" id="directGrid"></div>
    </div>
</div>

<script>
    // ── Slider helper ─────────────────────────────────────────────
    function updateSlider(sliderId, valId) {
        const v = parseFloat(document.getElementById(sliderId).value);
        document.getElementById(valId).textContent = v === 0 ? '0.00 (off)' : v.toFixed(2);
    }

    // ── Tab switching ─────────────────────────────────────────────
    function switchTab(mode) {
        document.getElementById('panelAI').style.display     = mode === 'ai'     ? '' : 'none';
        document.getElementById('panelDirect').style.display = mode === 'direct' ? '' : 'none';
        document.getElementById('tabAI').classList.toggle('active',     mode === 'ai');
        document.getElementById('tabDirect').classList.toggle('active', mode === 'direct');
    }

    // ── Card builder ──────────────────────────────────────────────
    function buildCard(item) {
        const badgeClass = item._score === 2 ? 'badge-both' : (item._sources?.includes('text') ? 'badge-text' : 'badge-image');
        const badgeText  = item._score === 2 ? 'Text+Image' : (item._sources?.includes('text') ? 'Text' : 'Image');
        const score      = item._rankingScore ? item._rankingScore.toFixed(3) : '—';
        return `
            <div class="card">
                <img src="${item.image_url || 'https://placehold.co/300x300/1c2430/8b949e?text=?'}" alt="${item.title}" loading="lazy">
                <div class="card-body">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
                        <span class="card-badge ${badgeClass}">${badgeText}</span>
                        <span style="font-size:.7rem;font-family:'JetBrains Mono',monospace;color:var(--muted)">⭐${score}</span>
                    </div>
                    <div class="card-title">${item.title}</div>
                    <div class="card-type">${item.type || ''}</div>
                    <div class="card-price">PKR ${item.price ? item.price.toLocaleString() : 'N/A'}</div>
                    <div class="card-meta">${item.color || '—'} · ${item.handle}</div>
                    <div class="card-actions">
                        <a href="https://ismailsclothing.com/products/${item.handle}" target="_blank">View Product ↗</a>
                    </div>
                </div>
            </div>`;
    }

    function showEmpty(gridId) {
        document.getElementById(gridId).innerHTML =
            '<div class="empty" style="grid-column:1/-1"><div>🔍</div>No products found for this query.</div>';
    }

    // ── AI Search ─────────────────────────────────────────────────
    async function runAISearch() {
        const query = document.getElementById('aiQuery').value.trim();
        if (!query) { alert('Please enter a query.'); return; }

        const limit    = document.getElementById('aiLimit').value;
        const minScore = parseFloat(document.getElementById('aiScore').value);
        const grid     = document.getElementById('aiGrid');
        const loading  = document.getElementById('aiLoading');
        const aiPanel  = document.getElementById('aiPanel');
        const aiHeader = document.getElementById('aiResultsHeader');
        const loadMsg  = document.getElementById('aiLoadingMsg');

        grid.innerHTML = '';
        aiPanel.classList.remove('visible');
        aiHeader.style.display = 'none';
        loading.style.display  = 'block';
        loadMsg.textContent    = 'Step 1/2 — Calling AI (forced tool call)...';

        try {
            const res  = await fetch('/api/search/ai-visualize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, limit: parseInt(limit), min_score: minScore > 0 ? minScore : null })
            });
            const data = await res.json();

            if (data.error) { alert('Error: ' + data.error); loading.style.display = 'none'; return; }

            loading.style.display = 'none';

            // ── Render AI extraction panel ──────────────────────
            const ex = data.ai_extraction;
            document.getElementById('aiMessage').textContent = '"' + ex.searching_message + '"';

            const tagsEl = document.getElementById('aiTags');
            tagsEl.innerHTML = '';
            const addTag = (label, val, cls) => {
                tagsEl.insertAdjacentHTML('beforeend',
                    `<span class="tag ${cls}"><b>${label}:</b> ${val}</span>`);
            };
            addTag('search_query',  ex.search_query,               'query');
            addTag('color_filter',  ex.color_filter  || 'none',    ex.color_filter  ? 'color'  : 'none');
            addTag('max_price',     ex.max_price != null ? 'PKR ' + ex.max_price : 'none', ex.max_price != null ? 'price' : 'none');
            addTag('filter_str',    ex.filter_str    || 'none',    ex.filter_str    ? 'filter' : 'none');
            if (minScore > 0) addTag('min_score', minScore.toFixed(2), 'filter');

            document.getElementById('aiMeta').innerHTML =
                `<span>Model: <b>${ex.model}</b></span>
                 <span>Prompt tokens: <b>${ex.prompt_tokens ?? '—'}</b></span>
                 <span>Completion tokens: <b>${ex.completion_tokens ?? '—'}</b></span>`;

            aiPanel.classList.add('visible');

            // ── Render results ──────────────────────────────────
            const count = data.results.length;
            aiHeader.style.display = '';
            aiHeader.textContent   = `${count} product${count !== 1 ? 's' : ''} returned`;

            if (count === 0) { showEmpty('aiGrid'); return; }
            data.results.forEach(item => grid.insertAdjacentHTML('beforeend', buildCard(item)));

        } catch (err) {
            loading.style.display = 'none';
            alert('Request failed: ' + err.message);
        }
    }

    // ── Direct Search ─────────────────────────────────────────────
    async function runDirectSearch() {
        const query      = document.getElementById('directQuery').value;
        const imageFile  = document.getElementById('directImage').files[0];
        const limit      = document.getElementById('directLimit').value;
        const color      = document.getElementById('directColor').value;
        const maxPrice   = document.getElementById('directPrice').value;
        const minScore   = parseFloat(document.getElementById('directScore').value);
        const grid       = document.getElementById('directGrid');
        const loading    = document.getElementById('directLoading');
        const header     = document.getElementById('directResultsHeader');

        grid.innerHTML = '';
        header.style.display  = 'none';
        loading.style.display = 'block';

        try {
            const formData = new FormData();
            formData.append('query', query);
            formData.append('limit', limit);
            if (color)         formData.append('color_filter', color);
            if (maxPrice)      formData.append('max_price', maxPrice);
            if (minScore > 0)  formData.append('min_score', minScore);
            if (imageFile) formData.append('image', imageFile);

            const res  = await fetch('/api/search/visualize', { method: 'POST', body: formData });
            const data = await res.json();
            loading.style.display = 'none';

            // Show active filters
            const parts = [];
            if (color)        parts.push(`color=${color}`);
            if (maxPrice)     parts.push(`max_price≤${maxPrice}`);
            if (minScore > 0) parts.push(`min_score≥${minScore.toFixed(2)}`);
            const filterNote = parts.length ? ` · filters: ${parts.join(', ')}` : '';

            const count = data.results.length;
            header.style.display = '';
            header.textContent   = `${count} product${count !== 1 ? 's' : ''} returned${filterNote}`;

            if (count === 0) { showEmpty('directGrid'); return; }
            data.results.forEach(item => grid.insertAdjacentHTML('beforeend', buildCard(item)));

        } catch (err) {
            loading.style.display = 'none';
            alert('Search failed: ' + err.message);
        }
    }

    // Enter key support
    document.addEventListener('keydown', e => {
        if (e.key !== 'Enter') return;
        if (document.getElementById('panelAI').style.display !== 'none') runAISearch();
        else runDirectSearch();
    });
</script>
</body>
</html>
"""


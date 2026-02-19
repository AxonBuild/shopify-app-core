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

import requests
import json
import os

# مفاتيح API
SHOPIFY_API_KEY = os.getenv('SHOPIFY_API_KEY')
SHOPIFY_STORE_URL = "https://www.glowaistore.com/admin/api/2025-01"
CJ_API_KEY = os.getenv('CJ_API_KEY')

# هامش الربح (35%)
PROFIT_MARGIN = 1.35  

# جلب المنتجات من CJ Dropshipping
def get_cj_products():
    url = "https://developers.cjdropshipping.com/api/product/list"
    headers = {
        "CJ-Access-Token": CJ_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "pageSize": 10,  # يمكنك زيادة العدد حسب الحاجة
        "pageNum": 1,
        "categoryName": "Beauty & Health"  
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json().get('data', {}).get('list', [])
    else:
        print("❌ خطأ في جلب المنتجات:", response.text)
        return []

# جلب قائمة المنتجات الحالية من Shopify
def get_shopify_products():
    url = f"{SHOPIFY_STORE_URL}/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_KEY
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('products', [])
    else:
        print("❌ فشل في جلب منتجات Shopify:", response.text)
        return []

# حذف المنتجات المنتهية من Shopify
def delete_old_products(existing_products, new_products):
    existing_skus = {product['variants'][0]['sku']: product['id'] for product in existing_products}
    new_skus = {product.get("sku", "") for product in new_products}

    for sku, product_id in existing_skus.items():
        if sku not in new_skus:
            url = f"{SHOPIFY_STORE_URL}/products/{product_id}.json"
            headers = {"X-Shopify-Access-Token": SHOPIFY_API_KEY}
            response = requests.delete(url, headers=headers)
            if response.status_code == 200:
                print(f"🗑️ تم حذف المنتج المنتهي: {sku}")
            else:
                print(f"❌ فشل في حذف المنتج {sku}: {response.text}")

# إضافة المنتجات إلى Shopify
def add_product_to_shopify(product):
    url = f"{SHOPIFY_STORE_URL}/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_KEY,
        "Content-Type": "application/json"
    }

    # حساب السعر بعد إضافة هامش الربح
    original_price = float(product.get("sellPrice", 0))
    final_price = round(original_price * PROFIT_MARGIN, 2)

    product_data = {
        "product": {
            "title": product.get("name", "منتج غير معروف"),
            "body_html": product.get("description", ""),
            "vendor": "CJ Dropshipping",
            "product_type": "Beauty & Health",
            "tags": ["Beauty", "Skincare", "Health"],
            "variants": [
                {
                    "price": str(final_price),
                    "sku": product.get("sku", ""),
                    "inventory_management": "shopify",
                    "inventory_quantity": 10,
                }
            ],
            "images": [{"src": img} for img in product.get("imageUrls", [])]
        }
    }

    response = requests.post(url, headers=headers, json=product_data)
    if response.status_code == 201:
        print(f"✅ تمت إضافة المنتج: {product['name']} بسعر {final_price} دولار")
    else:
        print(f"❌ فشل في إضافة المنتج {product['name']}: {response.text}")

# تنفيذ الاستيراد التلقائي
def import_products():
    print("🔄 جلب المنتجات من CJ Dropshipping...")
    new_products = get_cj_products()
    existing_products = get_shopify_products()

    print("🔄 حذف المنتجات المنتهية من Shopify...")
    delete_old_products(existing_products, new_products)

    print("🔄 إضافة المنتجات الجديدة...")
    for product in new_products:
        add_product_to_shopify(product)

# تشغيل الوظيفة
if __name__ == "__main__":
    import_products()

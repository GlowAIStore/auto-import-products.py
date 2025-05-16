// autoSync.js
import 'dotenv/config';
import axios from 'axios';
import { getTagFromTitle, getCollectionId } from './lib/classify.js';

const SHOPIFY_STORE_DOMAIN = process.env.SHOPIFY_STORE_DOMAIN;
const SHOPIFY_ACCESS_TOKEN = process.env.SHOPIFY_ACCESS_TOKEN;
const AUTODS_API_TOKEN = process.env.AUTODS_API_TOKEN;
const SHOPIFY_API_VERSION = process.env.SHOPIFY_API_VERSION || '2025-04';

const shopify = axios.create({
  baseURL: `https://${SHOPIFY_STORE_DOMAIN}/admin/api/${SHOPIFY_API_VERSION}`,
  headers: {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json',
  },
});

function shortenTitle(title) {
  const maxLength = 60;
  const clean = title.replace(/\s+/g, ' ').trim();
  return clean.length > maxLength ? `${clean.slice(0, maxLength)}...` : clean;
}

function isSuspiciousVendor(vendor) {
  return /temu|shein|wish|alibaba/i.test(vendor);
}

function isBadProduct(product) {
  return !product.title || !product.price || !product.images || product.images.length === 0;
}

const seenSKUs = new Set();

async function fetchAutoDSProducts() {
  try {
    const res = await axios.get('https://api.autods.com/v1/products', {
      headers: { Authorization: `Bearer ${AUTODS_API_TOKEN}` },
    });
    return res.data.products || [];
  } catch (err) {
    console.error('[AutoSync] ❌ Failed to fetch AutoDS products:', err.message);
    return [];
  }
}

async function findProductBySKU(sku) {
  try {
    let page = 1;
    while (true) {
      const res = await shopify.get(`/products.json?limit=250&page=${page}`);
      const products = res.data.products;
      if (!products.length) break;
      const found = products.find(p => p.variants.some(v => v.sku && v.sku.toLowerCase() === sku.toLowerCase()));
      if (found) return found;
      page++;
    }
    return null;
  } catch (err) {
    console.error('[AutoSync] ❌ Failed to check product SKU:', err.message);
    return null;
  }
}

async function syncProduct(product) {
  if (isBadProduct(product)) return;
  if (seenSKUs.has(product.sku)) return;
  if (isSuspiciousVendor(product.supplier_name)) return;

  const tag = getTagFromTitle(product.title);
  if (!tag) return;

  const existing = await findProductBySKU(product.sku);
  if (existing) return;

  const title = shortenTitle(product.title);
  const body = product.body_html || `<p>${product.title}</p>`; // retain AutoDS description
  const price = product.price.toFixed(2);
  const collectionId = getCollectionId(tag);

  try {
    const created = await shopify.post('/products.json', {
      product: {
        title,
        body_html: body,
        vendor: product.supplier_name || 'AutoDS Supplier',
        status: product.stock === 0 ? 'draft' : 'active',
        tags: [tag],
        variants: [
          {
            price,
            sku: product.sku,
            inventory_quantity: product.stock,
            inventory_management: 'shopify',
          },
        ],
        images: product.images.map(src => ({ src })),
      },
    });

    if (collectionId) {
      await shopify.post('/collects.json', {
        collect: {
          product_id: created.data.product.id,
          collection_id: collectionId,
        },
      });
    }

    seenSKUs.add(product.sku);
    console.log(`[AutoSync] ✅ Created: ${title} → ${tag}`);
  } catch (err) {
    console.error(`[AutoSync] ❌ Failed to create product ${title}:`, err.response?.data || err.message);
  }
}

async function runAutoSync() {
  console.log('[AutoSync] 🚀 Starting sync...');
  const products = await fetchAutoDSProducts();
  console.log(`[AutoSync] 🔍 Fetched ${products.length} products.`);
  for (const p of products) {
    await syncProduct(p);
  }
  console.log('[AutoSync] ✅ Sync completed.');
}

runAutoSync();

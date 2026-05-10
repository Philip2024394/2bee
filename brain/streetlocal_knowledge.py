"""
StreetLocal Knowledge Base — feeds all app data into 2bee's memory.
Run once: python -m brain.streetlocal_knowledge
"""

from brain.memory import init, add_fact

def load_all():
    init()

    # Company
    add_fact("streetlocal", "StreetLocal is a software company that builds branded mobile apps for local businesses like food vendors, restaurants, and product sellers. Website: streetlocal.live", source="user_taught")
    add_fact("streetlocal", "StreetLocal charges 0% commission — vendors keep 100% of revenue. Only a monthly subscription fee.", source="user_taught")
    add_fact("streetlocal", "StreetLocal apps are mobile-first PWAs that work on any phone via a link — no app store needed.", source="user_taught")
    add_fact("streetlocal", "StreetLocal is a software-only company, NOT a food business, delivery service, or employer.", source="user_taught")
    add_fact("streetlocal", "StreetLocal supports 16 countries and 11 languages including English, Indonesian, Malay, Vietnamese, Thai, Filipino, French, German, Spanish, Chinese, and Arabic.", source="user_taught")

    # FoodLocal
    add_fact("foodlocal", "FoodLocal is StreetLocal's food ordering app. Price: Rp 35,000/month or Rp 456,000/year. URL: streetlocal.live/food/basic/", source="user_taught")
    add_fact("foodlocal", "FoodLocal features: WhatsApp ordering (zero commission), digital menu with photos, promo pricing, halal badges, spice indicators, customer order notes, prep time per item.", source="user_taught")
    add_fact("foodlocal", "FoodLocal design features: 20+ theme backgrounds, custom logo & branding, custom accent colors, landing page with city/country display, hero text effects, button customization, splash screen.", source="user_taught")
    add_fact("foodlocal", "FoodLocal delivery features: GPS delivery estimates with local rates, city-based GoJek/Grab rate defaults, multi-currency support (16 countries), configurable delivery radius, free delivery threshold, pickup-only mode.", source="user_taught")
    add_fact("foodlocal", "FoodLocal business features: shop open/close toggle, per-day opening hours, visit us page with map, shop bio & social links, QR code generator, QRIS payment, customer directory, daily deals.", source="user_taught")
    add_fact("foodlocal", "FoodLocal marketing features: WhatsApp share templates, auto-reply text for WhatsApp Business, Instagram & TikTok bio link, shareable URL, promo banner with scrolling text, search listing on StreetLocal.live.", source="user_taught")
    add_fact("foodlocal", "FoodLocal food categories: Nasi, Mie, Sop/Soto, Sate/Bakar, Gorengan, Jajanan, Ayam, Seafood, Roti, Minuman, Dessert, Bubur.", source="user_taught")

    # Food Pro
    add_fact("foodpro", "Food Pro (Restaurant) is StreetLocal's premium restaurant app. Price: Rp 100,000/month or Rp 1,200,000/year. URL: streetlocal.live/food/pro/", source="user_taught")
    add_fact("foodpro", "Food Pro features: branded restaurant app, full menu with delivery estimates, daily deals & promo offers, customer discount campaigns, seating & venue showcase, live music & entertainment listings, outside catering, weekly events, opening hours management.", source="user_taught")

    # ProductsLocal
    add_fact("productslocal", "ProductsLocal is StreetLocal's product store app. Price: Rp 35,000/month or Rp 456,000/year. URL: streetlocal.live/products/local/", source="user_taught")
    add_fact("productslocal", "ProductsLocal features: product catalog with photos, category management, promo pricing, stock availability toggle, product variants & options, customer order notes, WhatsApp ordering (zero commission).", source="user_taught")
    add_fact("productslocal", "ProductsLocal product categories: Fashion, Electronics, Beauty, Home & Living, Handmade, Sports, Automotive, Books & School, Grocery, Digital, General, Baby & Kids, Pet Supplies.", source="user_taught")
    add_fact("productslocal", "ProductsLocal has 31 theme backgrounds: Clothing, Shoes, Handbags, Hijab, Batik, Electronics, Computer Repair, Phone Cases, Beauty Products, Cosmetics, Perfume, Home Decor, Furniture, Kitchenware, Packaging, Handicrafts, Jewelry, Candles, Sports, Baby Clothes, School Accessories, Books, Motorbike Tyres, Seat Covers, Automotive, Pet Supplies, Grocery, Tobacco, Herbal, Digital, General Store.", source="user_taught")

    # Pricing
    add_fact("pricing", "StreetLocal pricing: FoodLocal Rp 35,000/month, Food Pro Rp 100,000/month, ProductsLocal Rp 35,000/month. All plans include hosting, updates, security, and support.", source="user_taught")
    add_fact("pricing", "StreetLocal yearly pricing: FoodLocal Rp 456,000/year, Food Pro Rp 1,200,000/year, ProductsLocal Rp 456,000/year.", source="user_taught")
    add_fact("pricing", "StreetLocal has no setup fees, no contracts, no lock-in. Cancel anytime.", source="user_taught")

    # Domain services
    add_fact("domains", "StreetLocal domain Tier 1 (Branded Subdomain): shopname.streetlocal.live — Rp 25,000/month, Rp 50,000 setup. Instant deployment, managed SSL.", source="user_taught")
    add_fact("domains", "StreetLocal domain Tier 2 (Custom Domain, most popular): menu.yourbrand.com — Rp 75,000/month, Rp 150,000 onboarding. Full DNS config, branded experience.", source="user_taught")
    add_fact("domains", "StreetLocal domain Tier 3 (Fully Managed): yourbrand.com — Rp 150,000/month, Rp 300,000 setup. Domain acquisition, SSL automation, ownership transfer after 12 months.", source="user_taught")
    add_fact("domains", "All domain plans require 3-month minimum. Setup fees are non-refundable. Domain services are optional — apps work perfectly without them.", source="user_taught")

    # Delivery pricing
    add_fact("delivery", "Indonesia delivery rates: Jakarta Rp 10,000 base (4km) + Rp 2,500/km. Yogyakarta/Semarang Rp 7,000 base (3km) + Rp 2,000/km. Bali Rp 10,000 base (4km) + Rp 2,500/km.", source="user_taught")
    add_fact("delivery", "International delivery rates: Malaysia RM 5 base, Singapore S$3 base, Thailand ฿25 base, Vietnam ₫15,000 base, Philippines ₱49 base, Australia A$6 base, UK £3 base, US $4 base.", source="user_taught")

    # Key benefits
    add_fact("benefits", "StreetLocal key benefit: Keep More Money — zero commission, get paid directly, no platform fees.", source="user_taught")
    add_fact("benefits", "StreetLocal key benefit: Grow Your Brand — your brand identity not a marketplace, share on social media, built-in SEO.", source="user_taught")
    add_fact("benefits", "StreetLocal key benefit: Own Your Business — full analytics, customer reviews on YOUR app, instant updates without platform approval.", source="user_taught")
    add_fact("benefits", "StreetLocal key benefit: Better Customer Experience — one-tap ordering, WhatsApp checkout, works offline, build real customer loyalty.", source="user_taught")

    # FAQ
    add_fact("faq", "StreetLocal FAQ: How does it work? Choose your plan, subscribe, and we set up your branded app within 24 hours. You get a link to share with customers.", source="user_taught")
    add_fact("faq", "StreetLocal FAQ: Do I need technical skills? No! Everything is managed through a simple dashboard. If you can use WhatsApp, you can manage your app.", source="user_taught")
    add_fact("faq", "StreetLocal FAQ: Can I cancel anytime? Yes. No contracts, no lock-in. Cancel anytime from your dashboard.", source="user_taught")
    add_fact("faq", "StreetLocal FAQ: Do you take commission? Never. You keep 100% of your revenue. We only charge the monthly subscription.", source="user_taught")
    add_fact("faq", "StreetLocal FAQ: Can I buy the app? No — StreetLocal is a service, not a product. Building this from scratch would cost Rp 15-30 million plus hosting and maintenance.", source="user_taught")
    add_fact("faq", "StreetLocal FAQ: Can I have my own domain? Yes! Three domain plans available: subdomain, custom domain, or fully managed domain. All optional.", source="user_taught")

    # Technical
    add_fact("technical", "StreetLocal tech stack: React 19, Vite, Supabase (database + storage + auth), PWA (Progressive Web App), mobile-first 480px max-width design.", source="user_taught")
    add_fact("technical", "StreetLocal hosting: All images stored on Supabase Storage. Apps deployed as static PWAs. Service worker for offline support.", source="user_taught")
    add_fact("technical", "StreetLocal uses inline CSS-in-JS styling (no CSS files), dark theme with glass morphism, 24+ theme backgrounds per app.", source="user_taught")

    # Marketing knowledge for 2bee
    add_fact("marketing", "StreetLocal target market: street food vendors, small restaurants, cafes, product sellers, and local businesses in Indonesia and Southeast Asia.", source="user_taught")
    add_fact("marketing", "StreetLocal competitive advantage: 0% commission vs GoFood (20-25%), GrabFood (20-30%), ShopeeFood (15-20%). Vendors save Rp 200,000-500,000/month in commission fees.", source="user_taught")
    add_fact("marketing", "StreetLocal sales pitch: 'Stop paying 25% commission to GoFood. Get your own branded food app for just Rp 35,000/month — that is less than one order's commission fee.'", source="user_taught")
    add_fact("marketing", "StreetLocal upsell path: FoodLocal (Rp 35k) → Food Pro (Rp 100k) → Custom Domain (Rp 75k/month). Each tier adds more features and brand control.", source="user_taught")
    add_fact("marketing", "StreetLocal distribution: shareable link (streetlocal.live/vendor-name), QR codes for stalls, WhatsApp sharing, Instagram/TikTok bio links, Google search listing.", source="user_taught")

    # Free tools 2bee knows about
    add_fact("tools", "Pollinations.ai — free AI image generation via URL. No API key needed. Usage: https://image.pollinations.ai/prompt/YOUR+PROMPT?width=768&height=512", source="user_taught")
    add_fact("tools", "DuckDuckGo Instant Answer API — free factual search. No API key. URL: https://api.duckduckgo.com/?q=QUERY&format=json", source="user_taught")
    add_fact("tools", "Wikipedia API — free encyclopedia. URL: https://en.wikipedia.org/api/rest_v1/page/summary/TOPIC", source="user_taught")
    add_fact("tools", "Wikidata API — free structured facts. URL: https://www.wikidata.org/w/api.php?action=wbsearchentities&search=QUERY&language=en&format=json", source="user_taught")
    add_fact("tools", "Unsplash API — free stock photos. 50 requests/hour free tier. Good for real product photos.", source="user_taught")
    add_fact("tools", "QR Server API — free QR code generation. URL: https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=URL", source="user_taught")
    add_fact("tools", "FFmpeg — free video creation from images and audio. Can create slideshows, add text overlays, transitions. Installed via command line.", source="user_taught")
    add_fact("tools", "Canvas API (HTML5) — free browser-based image/video rendering. Can create animations, text effects, image compositing.", source="user_taught")
    add_fact("tools", "Supabase Storage — free 1GB storage for images and files. Used by StreetLocal for all app images.", source="user_taught")

    print("[OK] Loaded StreetLocal knowledge base into 2bee memory")


if __name__ == "__main__":
    load_all()

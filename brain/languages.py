"""
2B Language & Marketing Words Database
Knows what to say and what NOT to say on product images in each language.
"""

from brain.memory import add_fact

# Marketing words approved for theme images — per language
MARKETING_WORDS = {
    "id": {  # Indonesian (Bahasa Indonesia)
        "name": "Indonesian",
        "good": [
            "Koleksi Terbaru", "Gaya Hidup Modern", "Kualitas Terbaik",
            "Produk Unggulan", "Terlaris", "Baru", "Pilihan Terbaik",
            "Belanja Sekarang", "Lihat Semua", "Pesan Sekarang",
            "Gratis Ongkir", "Promo Spesial", "Diskon Besar",
            "Tersedia Sekarang", "Stok Terbatas", "Edisi Terbatas",
            "Kenyamanan Maksimal", "Desain Eksklusif", "Premium",
            "Tren Terkini", "Pilihan Cerdas", "Gaya Anda",
            "Untuk Anda", "Favorit Pelanggan", "Paling Diminati",
            "Bahan Berkualitas", "Harga Terjangkau", "Nyaman Dipakai",
            "Tampil Percaya Diri", "Elegan", "Stylish",
        ],
        "bad": [
            "Murah", "Murahan", "Obral", "Cuci Gudang",  # sounds cheap
            "Tiruan", "KW", "Replika", "Palsu",  # fake/counterfeit
            "Bekas", "Second",  # used goods (unless selling used items)
        ],
        "cta": ["Belanja Sekarang", "Pesan Sekarang", "Lihat Koleksi", "Dapatkan Sekarang"],
        "hero": ["Koleksi Terbaru", "Gaya Hidup Modern", "Kualitas Premium", "Desain Eksklusif"],
    },
    "ms": {  # Malay
        "name": "Malay",
        "good": [
            "Koleksi Terbaru", "Gaya Hidup Moden", "Kualiti Terbaik",
            "Produk Pilihan", "Terlaris", "Baharu", "Pilihan Terbaik",
            "Beli Sekarang", "Lihat Semua", "Tempah Sekarang",
            "Penghantaran Percuma", "Promosi Istimewa", "Diskaun Besar",
            "Kini Tersedia", "Stok Terhad", "Edisi Terhad",
        ],
        "bad": ["Murah", "Tiruan", "Palsu", "Terpakai"],
        "cta": ["Beli Sekarang", "Tempah Sekarang", "Lihat Koleksi"],
        "hero": ["Koleksi Terbaru", "Gaya Hidup Moden", "Kualiti Premium"],
    },
    "th": {  # Thai
        "name": "Thai",
        "good": [
            "คอลเลกชันใหม่", "ไลฟ์สไตล์ทันสมัย", "คุณภาพดีที่สุด",
            "สินค้าแนะนำ", "ขายดี", "ใหม่", "ตัวเลือกที่ดีที่สุด",
            "ช้อปเลย", "ดูทั้งหมด", "สั่งเลย",
            "ส่งฟรี", "โปรโมชั่นพิเศษ", "ลดราคา",
            "มีสินค้าแล้ว", "สินค้ามีจำนวนจำกัด",
        ],
        "bad": ["ถูก", "เลียนแบบ", "ปลอม", "มือสอง"],
        "cta": ["ช้อปเลย", "สั่งเลย", "ดูคอลเลกชัน"],
        "hero": ["คอลเลกชันใหม่", "ไลฟ์สไตล์ทันสมัย", "คุณภาพพรีเมียม"],
    },
    "vi": {  # Vietnamese
        "name": "Vietnamese",
        "good": [
            "Bộ Sưu Tập Mới", "Phong Cách Hiện Đại", "Chất Lượng Tốt Nhất",
            "Sản Phẩm Nổi Bật", "Bán Chạy", "Mới", "Lựa Chọn Tốt Nhất",
            "Mua Ngay", "Xem Tất Cả", "Đặt Hàng Ngay",
            "Miễn Phí Vận Chuyển", "Khuyến Mãi Đặc Biệt", "Giảm Giá Lớn",
            "Có Sẵn Ngay", "Số Lượng Có Hạn",
        ],
        "bad": ["Rẻ", "Hàng nhái", "Hàng giả", "Đã qua sử dụng"],
        "cta": ["Mua Ngay", "Đặt Hàng Ngay", "Xem Bộ Sưu Tập"],
        "hero": ["Bộ Sưu Tập Mới", "Phong Cách Hiện Đại", "Chất Lượng Cao Cấp"],
    },
    "en": {  # English
        "name": "English",
        "good": [
            "New Collection", "Modern Lifestyle", "Best Quality",
            "Featured Products", "Best Seller", "New Arrival", "Top Pick",
            "Shop Now", "View All", "Order Now",
            "Free Shipping", "Special Offer", "Big Sale",
            "Available Now", "Limited Stock", "Limited Edition",
            "Maximum Comfort", "Exclusive Design", "Premium",
            "Trending Now", "Smart Choice", "Your Style",
        ],
        "bad": [
            "Cheap", "Knockoff", "Fake", "Counterfeit", "Used",
            "Clearance", "Going Out of Business",  # sounds desperate
        ],
        "cta": ["Shop Now", "Order Now", "View Collection", "Get Yours"],
        "hero": ["New Collection", "Modern Lifestyle", "Premium Quality", "Exclusive Design"],
    },
    "ar": {  # Arabic
        "name": "Arabic",
        "good": [
            "مجموعة جديدة", "أسلوب حياة عصري", "أفضل جودة",
            "منتجات مميزة", "الأكثر مبيعاً", "جديد", "أفضل اختيار",
            "تسوق الآن", "عرض الكل", "اطلب الآن",
            "شحن مجاني", "عرض خاص", "خصم كبير",
        ],
        "bad": ["رخيص", "تقليد", "مزيف", "مستعمل"],
        "cta": ["تسوق الآن", "اطلب الآن", "شاهد المجموعة"],
        "hero": ["مجموعة جديدة", "أسلوب حياة عصري", "جودة ممتازة"],
    },
    "zh": {  # Chinese
        "name": "Chinese",
        "good": [
            "新品上市", "现代生活", "最佳品质",
            "精选产品", "热卖", "新款", "首选",
            "立即购买", "查看全部", "立即下单",
            "免费配送", "特别优惠", "大促销",
        ],
        "bad": ["便宜", "仿制", "假货", "二手"],
        "cta": ["立即购买", "立即下单", "查看系列"],
        "hero": ["新品上市", "现代生活", "高端品质"],
    },
}

# Words that should NEVER appear on any theme image in any language
UNIVERSAL_BANNED = [
    "free", "gratis", "0%", "100%", "$", "Rp", "USD", "€",  # pricing
    "discount", "diskon", "sale", "clearance",  # unless specifically asked
    "click here", "klik di sini", "buy now button",  # UI elements
    "lorem ipsum",  # placeholder text
    "whatsapp", "instagram", "facebook", "tiktok",  # social media logos
    "©", "trademark", "™", "®",  # legal symbols
]


def load_languages():
    """Load all language knowledge into 2B memory."""
    for code, lang in MARKETING_WORDS.items():
        # Good words
        good_list = ", ".join(lang["good"][:15])
        add_fact("language_marketing",
                 f'{lang["name"]} ({code}) approved marketing words for themes: {good_list}',
                 source="user_taught")

        # Bad words
        bad_list = ", ".join(lang["bad"])
        add_fact("language_marketing",
                 f'{lang["name"]} ({code}) BANNED words on themes (never use): {bad_list}',
                 source="user_taught")

        # CTAs
        cta_list = ", ".join(lang["cta"])
        add_fact("language_marketing",
                 f'{lang["name"]} ({code}) call-to-action phrases: {cta_list}',
                 source="user_taught")

    # Universal banned
    add_fact("language_marketing",
             f'NEVER put these on any theme image: {", ".join(UNIVERSAL_BANNED[:20])}',
             source="user_taught")

    print(f"[OK] Loaded {len(MARKETING_WORDS)} languages into 2B memory")


def get_marketing_words(language_code, word_type="good"):
    """Get marketing words for a specific language."""
    lang = MARKETING_WORDS.get(language_code, MARKETING_WORDS.get("en"))
    return lang.get(word_type, [])


def get_theme_text(language_code, layout_type="hero"):
    """Get appropriate text for a theme image."""
    lang = MARKETING_WORDS.get(language_code, MARKETING_WORDS.get("en"))
    import random
    if layout_type == "hero":
        return random.choice(lang.get("hero", ["New Collection"]))
    elif layout_type == "cta":
        return random.choice(lang.get("cta", ["Shop Now"]))
    else:
        return random.choice(lang.get("good", ["Featured"]))


if __name__ == "__main__":
    from brain.memory import init
    init()
    load_languages()

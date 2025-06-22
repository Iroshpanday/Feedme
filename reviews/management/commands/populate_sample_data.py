from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from reviews.models import Category, Brand, Product, Review
import random

class Command(BaseCommand):
    help = 'Populate database with sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')

        # Create categories
        categories_data = [
            {'name': 'Smartphones', 'icon': 'fas fa-mobile-alt'},
            {'name': 'Laptops', 'icon': 'fas fa-laptop'},
            {'name': 'Tablets', 'icon': 'fas fa-tablet-alt'},
            {'name': 'Headphones', 'icon': 'fas fa-headphones'},
            {'name': 'Cameras', 'icon': 'fas fa-camera'},
            {'name': 'Gaming', 'icon': 'fas fa-gamepad'},
            {'name': 'Smart Home', 'icon': 'fas fa-home'},
            {'name': 'Wearables', 'icon': 'fas fa-clock'},
            {'name': 'Audio', 'icon': 'fas fa-volume-up'},
            {'name': 'Accessories', 'icon': 'fas fa-plug'},
            {'name': 'TV & Video', 'icon': 'fas fa-tv'},
            {'name': 'Computing', 'icon': 'fas fa-desktop'},
        ]

        categories = {}
        for cat in categories_data:
            obj, _ = Category.objects.get_or_create(name=cat["name"], defaults={"icon": cat["icon"]})
            categories[cat["name"]] = obj

        # Create brands
        brand_names = [
            'Apple', 'Samsung', 'Google', 'OnePlus', 'Xiaomi', 'Huawei',
            'Sony', 'LG', 'Dell', 'HP', 'Lenovo', 'Asus', 'MSI',
            'Bose', 'JBL', 'Sennheiser', 'Audio-Technica', 'Beats',
            'Canon', 'Nikon', 'Fujifilm', 'Panasonic', 'GoPro'
        ]

        brands = {}
        for name in brand_names:
            obj, _ = Brand.objects.get_or_create(name=name)
            brands[name] = obj

        # Product data
        products_data = [
            {'name': 'iPhone 15 Pro', 'brand': 'Apple', 'category': 'Smartphones', 'price': 999.00},
            {'name': 'Galaxy S24 Ultra', 'brand': 'Samsung', 'category': 'Smartphones', 'price': 1199.00},
            {'name': 'Pixel 8 Pro', 'brand': 'Google', 'category': 'Smartphones', 'price': 899.00},
            {'name': 'OnePlus 12', 'brand': 'OnePlus', 'category': 'Smartphones', 'price': 799.00},
            {'name': 'MacBook Pro 16"', 'brand': 'Apple', 'category': 'Laptops', 'price': 2499.00},
            {'name': 'Dell XPS 13', 'brand': 'Dell', 'category': 'Laptops', 'price': 1299.00},
            {'name': 'ThinkPad X1 Carbon', 'brand': 'Lenovo', 'category': 'Laptops', 'price': 1599.00},
            {'name': 'ZenBook Pro', 'brand': 'Asus', 'category': 'Laptops', 'price': 1399.00},
            {'name': 'AirPods Pro', 'brand': 'Apple', 'category': 'Headphones', 'price': 249.00},
            {'name': 'WH-1000XM5', 'brand': 'Sony', 'category': 'Headphones', 'price': 399.00},
            {'name': 'QuietComfort 45', 'brand': 'Bose', 'category': 'Headphones', 'price': 329.00},
            {'name': 'HD 660S', 'brand': 'Sennheiser', 'category': 'Headphones', 'price': 499.00},
        ]

        products = []
        for p in products_data:
            product, created = Product.objects.get_or_create(
                name=p["name"],
                brand=brands[p["brand"]],
                category=categories[p["category"]],
                defaults={
                    "price": p["price"],
                    "description": f"Sample description for {p['name']}."
                }
            )
            products.append(product)
            if created:
                self.stdout.write(f"Created product: {product}")

        # Create users if none exist
        if not User.objects.exists():
            for i in range(1, 6):
                User.objects.create_user(username=f"user{i}", password="password123")
            self.stdout.write("Created sample users.")

        users = list(User.objects.all())

        # Create reviews
        for product in products:
            for _ in range(random.randint(2, 5)):
                user = random.choice(users)
                rating = random.randint(1, 5)
                title = f"{rating} Star Review"
                content = f"This is a sample review with rating {rating}."
                is_verified = random.choice([True, False])
                try:
                    Review.objects.create(
                        product=product,
                        user=user,
                        title=title,
                        content=content,
                        rating=rating,
                        is_verified_purchase=is_verified,
                        is_approved=True
                    )
                    self.stdout.write(f"Review added for {product.name} by {user.username}")
                except:
                    continue  # Skip duplicate reviews for same user-product

        self.stdout.write(self.style.SUCCESS("Sample data created successfully."))

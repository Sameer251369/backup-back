from rest_framework import serializers
from .models import Brand, Vehicle, VehicleVariant, VehicleImage

class BrandSerializer(serializers.ModelSerializer):
    vehicle_count = serializers.IntegerField(source='vehicles.count', read_only=True)

    class Meta:
        model = Brand
        fields = ['id', 'name', 'slug', 'logo_url', 'description', 'vehicle_count', 'created_at']


class VehicleVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleVariant
        fields = ['id', 'variant_name', 'ex_showroom_price', 'fuel_type', 'transmission']


class VehicleImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = VehicleImage
        fields = ['id', 'image_type', 'image_url', 'alt_text', 'is_primary', 'display_order']

    def get_image_url(self, obj):
        if not obj.image_url:
            return None
        image_url = obj.image_url.url if hasattr(obj.image_url, 'url') else obj.image_url
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(image_url)
        return image_url


class VehicleListSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    brand_slug = serializers.CharField(source='brand.slug', read_only=True)
    brand_logo = serializers.CharField(source='brand.logo_url', read_only=True)
    primary_image = serializers.SerializerMethodField()
    variants = VehicleVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'name', 'slug', 'brand', 'brand_name', 'brand_slug', 'brand_logo',
            'body_type', 'fuel_type', 'ev_hybrid_cng_flag', 'starting_price',
            'top_variant_price', 'ex_showroom_price', 'seats', 'transmission',
            'key_specs', 'description', 'is_featured', 'is_tba', 'is_active', 'primary_image',
            'variants',
        ]

    def get_primary_image(self, obj):
        first_img = (
            obj.images.filter(image_type='front').first()
            or obj.images.filter(is_primary=True).first()
            or obj.images.first()
        )
        if not first_img or not first_img.image_url:
            return None
        image_url = first_img.image_url.url if hasattr(first_img.image_url, 'url') else first_img.image_url
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(image_url)
        return image_url


class VehicleDetailSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    variants = VehicleVariantSerializer(many=True, read_only=True)
    images = VehicleImageSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'name', 'slug', 'brand', 'body_type', 'fuel_type',
            'ev_hybrid_cng_flag', 'starting_price', 'top_variant_price',
            'ex_showroom_price', 'seats', 'transmission', 'key_specs',
            'description', 'is_featured', 'is_tba', 'is_active', 'meta_title', 'meta_description',
            'variants', 'images', 'created_at',
        ]


class VehicleAdminWorklistSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    images = VehicleImageSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'name', 'slug', 'brand', 'brand_name', 'body_type', 'fuel_type',
            'ev_hybrid_cng_flag', 'starting_price', 'top_variant_price', 'ex_showroom_price',
            'seats', 'transmission', 'key_specs', 'description', 'needs_review', 'is_active',
            'is_featured', 'is_tba', 'data_source', 'created_at', 'primary_image', 'images',
            'meta_title', 'meta_description',
        ]

    def get_primary_image(self, obj):
        first_img = (
            obj.images.filter(image_type='front').first()
            or obj.images.filter(is_primary=True).first()
            or obj.images.first()
        )
        if not first_img or not first_img.image_url:
            return None
        image_url = first_img.image_url.url if hasattr(first_img.image_url, 'url') else first_img.image_url
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(image_url)
        return image_url


class VehicleAdminCreateSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(max_length=100, write_only=True)
    primary_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    front_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    exterior_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    interior_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    rear_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    published_vehicle = VehicleListSerializer(source='*', read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'brand_name', 'name', 'body_type', 'fuel_type',
            'ev_hybrid_cng_flag', 'starting_price', 'top_variant_price',
            'ex_showroom_price', 'seats', 'transmission', 'key_specs',
            'description', 'is_featured', 'is_tba', 'is_active', 'meta_title',
            'meta_description', 'primary_image', 'front_image', 'exterior_image',
            'interior_image', 'rear_image', 'published_vehicle',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        is_tba = attrs.get('is_tba', False)
        starting_price = attrs.get('starting_price')
        ex_showroom_price = attrs.get('ex_showroom_price')

        if not is_tba and not starting_price and not ex_showroom_price:
            raise serializers.ValidationError({
                'starting_price': 'Enter a starting or ex-showroom price, or mark the car as TBA.'
            })
        return attrs

    def create(self, validated_data):
        brand_name = validated_data.pop('brand_name').strip()
        primary_image = validated_data.pop('primary_image', None)
        uploaded_images = {
            'front': validated_data.pop('front_image', None),
            'exterior': validated_data.pop('exterior_image', None),
            'interior': validated_data.pop('interior_image', None),
            'rear': validated_data.pop('rear_image', None),
        }
        brand, _ = Brand.objects.get_or_create(name=brand_name)

        vehicle = Vehicle.objects.create(
            brand=brand,
            data_source='manual',
            needs_review=False,
            is_active=validated_data.pop('is_active', True),
            **validated_data,
        )

        if primary_image:
            VehicleImage.objects.create(
                vehicle=vehicle,
                image_url=primary_image,
                alt_text=f"{brand.name} {vehicle.name}",
                image_type='front',
                is_primary=True,
            )

        for image_type, image in uploaded_images.items():
            if image and not (image_type == 'front' and primary_image):
                VehicleImage.objects.create(
                    vehicle=vehicle,
                    image_url=image,
                    image_type=image_type,
                    alt_text=f"{brand.name} {vehicle.name} {image_type} view",
                    is_primary=not primary_image and image_type == 'front',
                )

        return vehicle


class VehicleAdminUpdateSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(max_length=100, write_only=True, required=False)
    primary_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    front_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    exterior_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    interior_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    rear_image = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'brand_name', 'name', 'body_type', 'fuel_type',
            'ev_hybrid_cng_flag', 'starting_price', 'top_variant_price',
            'ex_showroom_price', 'seats', 'transmission', 'key_specs',
            'description', 'is_featured', 'is_tba', 'is_active', 'meta_title',
            'meta_description', 'primary_image', 'front_image', 'exterior_image',
            'interior_image', 'rear_image',
        ]

    def update(self, instance, validated_data):
        brand_name = validated_data.pop('brand_name', None)
        if brand_name:
            brand, _ = Brand.objects.get_or_create(name=brand_name.strip())
            instance.brand = brand

        primary_image = validated_data.pop('primary_image', None)
        uploaded_images = {
            'front': validated_data.pop('front_image', None),
            'exterior': validated_data.pop('exterior_image', None),
            'interior': validated_data.pop('interior_image', None),
            'rear': validated_data.pop('rear_image', None),
        }

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Update or create images
        if primary_image:
            img_obj = instance.images.filter(image_type='front').first() or instance.images.filter(is_primary=True).first()
            if img_obj:
                img_obj.image_url = primary_image
                img_obj.is_primary = True
                img_obj.save()
            else:
                VehicleImage.objects.create(
                    vehicle=instance,
                    image_url=primary_image,
                    alt_text=f"{instance.brand.name} {instance.name}",
                    image_type='front',
                    is_primary=True,
                )

        for image_type, image in uploaded_images.items():
            if image:
                img_obj = instance.images.filter(image_type=image_type).first()
                if img_obj:
                    img_obj.image_url = image
                    img_obj.save()
                else:
                    VehicleImage.objects.create(
                        vehicle=instance,
                        image_url=image,
                        image_type=image_type,
                        alt_text=f"{instance.brand.name} {instance.name} {image_type} view",
                        is_primary=(image_type == 'front'),
                    )

        return instance


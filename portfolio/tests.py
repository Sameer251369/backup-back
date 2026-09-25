import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Brand, Vehicle, VehicleVariant


class AdminVehicleVariantUpdateTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='test-password',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=admin)
        brand = Brand.objects.create(name='Hyundai', slug='hyundai')
        self.vehicle = Vehicle.objects.create(
            brand=brand,
            name='Creta Electric',
            slug='hyundai-creta-electric',
            fuel_type='Electric',
            starting_price=Decimal('1800000'),
            ex_showroom_price=Decimal('1800000'),
        )
        self.variant = VehicleVariant.objects.create(
            vehicle=self.vehicle,
            variant_name='Standard',
            ex_showroom_price=Decimal('1800000'),
            fuel_type='Electric',
            transmission='Automatic',
        )

    def test_multipart_update_persists_variant_changes(self):
        variants = [
            {
                'id': self.variant.id,
                'variant_name': 'Executive',
                'ex_showroom_price': '1900000',
                'fuel_type': 'Electric',
                'transmission': 'Automatic',
            },
            {
                'variant_name': 'Premium',
                'ex_showroom_price': '2200000',
                'fuel_type': 'Electric',
                'transmission': 'Automatic',
            },
        ]

        response = self.client.patch(
            f'/api/v1/admin/vehicles/{self.vehicle.id}/',
            {'name': 'Creta Electric Updated', 'variants_json': json.dumps(variants)},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.name, 'Creta Electric Updated')
        self.assertEqual(self.vehicle.variants.count(), 2)
        self.assertEqual(
            self.vehicle.variants.get(id=self.variant.id).ex_showroom_price,
            Decimal('1900000'),
        )
        self.assertTrue(self.vehicle.variants.filter(variant_name='Premium').exists())

    def test_invalid_variant_does_not_partially_update_vehicle(self):
        response = self.client.patch(
            f'/api/v1/admin/vehicles/{self.vehicle.id}/',
            {
                'name': 'Should Not Persist',
                'variants_json': json.dumps([{
                    'id': self.variant.id,
                    'variant_name': 'Invalid',
                    'ex_showroom_price': 'not-a-price',
                }]),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.vehicle.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.vehicle.name, 'Creta Electric')
        self.assertEqual(self.variant.variant_name, 'Standard')

    def test_catalog_petrol_filter_includes_combined_fuel_labels(self):
        petrol_diesel = Vehicle.objects.create(
            brand=self.vehicle.brand,
            name='Creta Petrol Diesel',
            slug='hyundai-creta-petrol-diesel',
            fuel_type='Petrol/Diesel',
            starting_price=Decimal('1100000'),
        )

        response = self.client.get('/api/v1/vehicles/?fuel_type=Petrol')

        self.assertEqual(response.status_code, 200)
        self.assertIn(petrol_diesel.id, [item['id'] for item in response.data['results']])
        self.assertNotIn(self.vehicle.id, [item['id'] for item in response.data['results']])

    def test_admin_starting_price_updates_ex_showroom_alias(self):
        response = self.client.patch(
            f'/api/v1/admin/vehicles/{self.vehicle.id}/',
            {'starting_price': '1950000'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.starting_price, Decimal('1950000'))
        self.assertEqual(self.vehicle.ex_showroom_price, Decimal('1950000'))
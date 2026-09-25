from decimal import Decimal
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from portfolio.models import Brand, Vehicle, VehicleVariant
from calculator.models import State, RoadTaxSlab, InsuranceEstimate, DealerCharge, VehicleStateEstimate, StateOnRoadPrice
from calculator.services import calculate_on_road_price
from leads.models import Lead

class RuleEnginePricingServiceTestCase(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Tata Motors", slug="tata-motors")
        
        # Vehicle <= 10L (e.g. ₹8,00,000)
        self.nexon = Vehicle.objects.create(
            brand=self.brand,
            name="Nexon",
            slug="tata-nexon",
            body_type="suv",
            fuel_type="petrol",
            ex_showroom_price=Decimal("800000.00")
        )
        
        # Vehicle > 10L (e.g. ₹15,00,000)
        self.harrier = Vehicle.objects.create(
            brand=self.brand,
            name="Harrier",
            slug="tata-harrier",
            body_type="suv",
            fuel_type="diesel",
            ex_showroom_price=Decimal("1500000.00")
        )

        # EV Vehicle
        self.nexon_ev = Vehicle.objects.create(
            brand=self.brand,
            name="Nexon EV",
            slug="tata-nexon-ev",
            body_type="ev",
            fuel_type="electric",
            ex_showroom_price=Decimal("1400000.00")
        )

        # Union Territory State (Delhi)
        self.delhi = State.objects.create(
            name="Delhi",
            code="DL",
            price_basis="ex_showroom",
            registration_fee=Decimal("600.00"),
            smart_card_fee=Decimal("200.00"),
            hsrp_fee=Decimal("400.00"),
            hypothecation_fee=Decimal("1500.00"),
            fastag_fee=Decimal("500.00")
        )
        # Delhi Petrol Individual Slab (10%)
        RoadTaxSlab.objects.create(
            state=self.delhi, fuel_type="petrol", ownership_type="individual",
            min_price=Decimal("0"), max_price=None, rate=Decimal("0.10"), cess_rate=Decimal("0.01"),
            notification_number="DL-RTO-2026/01", source_url="https://transport.delhi.gov.in"
        )
        # Delhi Petrol Company Slab (12.5%)
        RoadTaxSlab.objects.create(
            state=self.delhi, fuel_type="petrol", ownership_type="company",
            min_price=Decimal("0"), max_price=None, rate=Decimal("0.10"), company_surcharge_rate=Decimal("0.0250"),
            notification_number="DL-RTO-2026/CORP-01", source_url="https://transport.delhi.gov.in"
        )

        DealerCharge.objects.create(name="Handling Fee", amount=Decimal("1500.00"), is_default_included=True)

    def test_company_ownership_surcharge(self):
        indiv = calculate_on_road_price(self.nexon, self.delhi, fuel_type="petrol", ownership_type="individual")
        corp = calculate_on_road_price(self.nexon, self.delhi, fuel_type="petrol", ownership_type="company")

        self.assertEqual(indiv['road_tax_rate_percent'], 10.0)
        self.assertEqual(corp['road_tax_rate_percent'], 12.5)
        self.assertGreater(corp['road_tax'], indiv['road_tax'])

    def test_13_modular_charge_categories_and_subtotals(self):
        result = calculate_on_road_price(self.harrier, self.delhi, fuel_type="petrol", ownership_type="individual", is_financed=True)
        
        self.assertIn('ex_showroom_price', result)
        self.assertIn('road_tax', result)
        self.assertIn('registration_fee', result)
        self.assertIn('smart_card_fee', result)
        self.assertIn('hsrp_fee', result)
        self.assertIn('hypothecation_fee', result)
        self.assertIn('temp_registration_fee', result)
        self.assertIn('road_safety_cess', result)
        self.assertIn('green_tax', result)
        self.assertIn('municipal_cess', result)
        self.assertIn('insurance_estimate', result)
        self.assertIn('fastag_fee', result)
        self.assertIn('tcs_amount', result)

        self.assertIn('total_government_charges', result)
        self.assertIn('total_insurance', result)
        self.assertIn('optional_charges', result)
        self.assertIn('final_on_road_price', result)

    def test_rule_verification_metadata(self):
        result = calculate_on_road_price(self.nexon, self.delhi, fuel_type="petrol", ownership_type="individual")
        meta = result['rule_metadata']
        self.assertEqual(meta['notificationNumber'], 'DL-RTO-2026/01')
        self.assertEqual(meta['sourceURL'], 'https://transport.delhi.gov.in')


class CalculatorAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.brand = Brand.objects.create(name="Hyundai", slug="hyundai")
        self.vehicle = Vehicle.objects.create(
            brand=self.brand, name="Creta", slug="hyundai-creta",
            body_type="suv", fuel_type="petrol", ex_showroom_price=Decimal("1100000.00")
        )
        self.state = State.objects.create(
            name="Maharashtra", code="MH", price_basis="ex_showroom", is_active=True
        )
        RoadTaxSlab.objects.create(state=self.state, fuel_type="petrol", min_price=Decimal("0"), max_price=None, rate=Decimal("0.11"))

    def test_estimate_endpoint_with_ownership_type(self):
        payload = {
            "vehicle_id": self.vehicle.id,
            "state_id": self.state.id,
            "fuel_type": "petrol",
            "ownership_type": "company",
            "is_financed": False
        }
        response = self.client.post(reverse('calculator-estimate'), data=payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('breakdown', response.data)
        self.assertEqual(response.data['breakdown']['ownership_type'], 'company')

    def test_selected_variant_price_is_not_overridden_by_state_summary(self):
        variant = VehicleVariant.objects.create(
            vehicle=self.vehicle,
            variant_name='SX',
            ex_showroom_price=Decimal('1500000.00'),
            fuel_type='petrol',
        )
        StateOnRoadPrice.objects.create(
            car=self.vehicle,
            state=self.state,
            start_ex_showroom=1100000,
            top_ex_showroom=1600000,
            start_on_road=1300000,
            top_on_road=1900000,
        )

        result = calculate_on_road_price(
            self.vehicle,
            self.state,
            fuel_type='petrol',
            variant=variant,
        )

        self.assertEqual(result['ex_showroom_price'], 1500000.0)

    def test_calculator_seed_restores_nonzero_ev_tax_rate(self):
        call_command('seed_tax_slabs_36', verbosity=0)

        ev_slab = RoadTaxSlab.objects.get(
            state=self.state,
            fuel_type='electric',
            ownership_type='all',
        )

        self.assertEqual(ev_slab.rate, Decimal('0.0600'))

    def test_bihar_on_road_price_all_fuels(self):
        bihar = State.objects.create(name="Bihar", code="BR", price_basis="ex_showroom", is_active=True)
        # Seed Bihar slabs
        RoadTaxSlab.objects.create(state=bihar, fuel_type="petrol", min_price=Decimal("0"), max_price=Decimal("800000"), rate=Decimal("0.08"))
        RoadTaxSlab.objects.create(state=bihar, fuel_type="petrol", min_price=Decimal("800000"), max_price=Decimal("1500000"), rate=Decimal("0.09"))
        RoadTaxSlab.objects.create(state=bihar, fuel_type="petrol", min_price=Decimal("1500000"), max_price=None, rate=Decimal("0.10"))
        RoadTaxSlab.objects.create(state=bihar, fuel_type="diesel", min_price=Decimal("0"), max_price=Decimal("800000"), rate=Decimal("0.10"))
        RoadTaxSlab.objects.create(state=bihar, fuel_type="diesel", min_price=Decimal("800000"), max_price=None, rate=Decimal("0.11"))
        RoadTaxSlab.objects.create(state=bihar, fuel_type="electric", min_price=Decimal("0"), max_price=None, rate=Decimal("0.00"))

        # Test Petrol, Hybrid, CNG, Diesel, EV in Bihar
        for fuel in ["Petrol", "Petrol Hybrid", "Petrol/CNG", "Diesel", "Electric"]:
            result = calculate_on_road_price(self.vehicle, bihar, fuel_type=fuel, ownership_type="individual")
            self.assertTrue(result['data_available'], f"Failed for {fuel} in Bihar")
            self.assertIsNotNone(result['total_on_road_price'], f"Null on-road price for {fuel} in Bihar")
            self.assertGreater(result['total_on_road_price'], float(self.vehicle.ex_showroom_price))

    def test_candidate_fuel_fallbacks_and_clamping(self):
        # State with only bounded petrol slabs up to 10L
        test_state = State.objects.create(name="Test State", code="TS", price_basis="ex_showroom", is_active=True)
        RoadTaxSlab.objects.create(state=test_state, fuel_type="petrol", min_price=Decimal("0"), max_price=Decimal("1000000"), rate=Decimal("0.08"))

        # Luxury car priced at 50L (exceeds all slabs) with Hybrid fuel
        luxury_car = Vehicle.objects.create(
            brand=self.brand, name="Luxury Hybrid", slug="luxury-hybrid",
            body_type="sedan", fuel_type="Petrol Hybrid", ex_showroom_price=Decimal("5000000.00")
        )

        result = calculate_on_road_price(luxury_car, test_state, fuel_type="Petrol Hybrid")
        self.assertTrue(result['data_available'])
        self.assertIsNotNone(result['total_on_road_price'])
        self.assertGreater(result['total_on_road_price'], 5000000)

    def test_calculator_data_command_repairs_state_dependencies(self):
        andaman = State.objects.create(
            name="Andaman and Nicobar Islands", code="AN", is_active=True
        )
        InsuranceEstimate.objects.all().delete()
        DealerCharge.objects.all().delete()

        call_command('seed_calculator_data', verbosity=0)

        self.assertTrue(RoadTaxSlab.objects.filter(state=andaman).exists())
        self.assertTrue(InsuranceEstimate.objects.filter(state__isnull=True).exists())
        self.assertTrue(DealerCharge.objects.filter(is_default_included=True).exists())
        result = calculate_on_road_price(self.vehicle, andaman, fuel_type='petrol')
        self.assertTrue(result['data_available'])
        self.assertIsNotNone(result['final_on_road_price'])

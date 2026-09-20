import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from portfolio.models import Vehicle, VehicleVariant

TRIM_TEMPLATES = {
    'maruti suzuki': [
        ('LXi 1.2 MT', 0.0, 'Manual'),
        ('VXi 1.2 MT', 0.25, 'Manual'),
        ('VXi 1.2 AMT', 0.45, 'Automatic'),
        ('ZXi 1.2 MT', 0.70, 'Manual'),
        ('ZXi+ 1.2 AMT', 1.0, 'Automatic')
    ],
    'hyundai': [
        ('E 1.5 MT', 0.0, 'Manual'),
        ('EX 1.5 MT', 0.20, 'Manual'),
        ('S 1.5 MT', 0.40, 'Manual'),
        ('SX Tech IVT', 0.75, 'Automatic'),
        ('SX (O) ADAS DCT', 1.0, 'Automatic')
    ],
    'tata motors': [
        ('Smart MT', 0.0, 'Manual'),
        ('Pure MT', 0.25, 'Manual'),
        ('Creative DCA', 0.55, 'Automatic'),
        ('Fearless+ MT', 0.80, 'Manual'),
        ('Empowered+ Dark AT', 1.0, 'Automatic')
    ],
    'tata': [
        ('Smart MT', 0.0, 'Manual'),
        ('Pure MT', 0.25, 'Manual'),
        ('Creative DCA', 0.55, 'Automatic'),
        ('Fearless+ MT', 0.80, 'Manual'),
        ('Empowered+ Dark AT', 1.0, 'Automatic')
    ],
    'mahindra': [
        ('MX1 MT', 0.0, 'Manual'),
        ('MX3 MT', 0.25, 'Manual'),
        ('AX5 AT', 0.55, 'Automatic'),
        ('AX7 MT', 0.80, 'Manual'),
        ('AX7L 4x4 AT', 1.0, 'Automatic')
    ],
    'kia': [
        ('HTE MT', 0.0, 'Manual'),
        ('HTK+ MT', 0.30, 'Manual'),
        ('HTX AT', 0.60, 'Automatic'),
        ('GTX+ Turbo DCT', 0.85, 'Automatic'),
        ('X-Line AT', 1.0, 'Automatic')
    ],
    'toyota': [
        ('GX MT', 0.0, 'Manual'),
        ('VX MT', 0.45, 'Manual'),
        ('ZX Hybrid e-CVT', 0.80, 'Automatic'),
        ('GR-Sport AT', 1.0, 'Automatic')
    ],
    'honda': [
        ('SV MT', 0.0, 'Manual'),
        ('V CVT', 0.35, 'Automatic'),
        ('VX CVT', 0.70, 'Automatic'),
        ('ZX e:HEV Hybrid', 1.0, 'Automatic')
    ],
    'volkswagen': [
        ('Comfortline MT', 0.0, 'Manual'),
        ('Highline MT', 0.40, 'Manual'),
        ('Topline AT', 0.75, 'Automatic'),
        ('GT Plus DSG', 1.0, 'Automatic')
    ],
    'skoda': [
        ('Active MT', 0.0, 'Manual'),
        ('Ambition MT', 0.40, 'Manual'),
        ('Style AT', 0.75, 'Automatic'),
        ('Monte Carlo DSG', 1.0, 'Automatic')
    ],
}

DEFAULT_TRIMS = [
    ('Base Edition MT', 0.0, 'Manual'),
    ('Plus Executive MT', 0.35, 'Manual'),
    ('Highline Tech AT', 0.70, 'Automatic'),
    ('Top Luxury AT', 1.0, 'Automatic')
]

LUXURY_TRIMS = [
    ('Standard Edition AT', 0.0, 'Automatic'),
    ('Dynamic Sport AT', 0.50, 'Automatic'),
    ('First Edition Performance AT', 1.0, 'Automatic')
]


class Command(BaseCommand):
    help = 'Seed realistic vehicle variants (trim levels, fuel types, transmission, and ex-showroom price) for all active vehicles.'

    def handle(self, *args, **options):
        self.stdout.write("Starting Vehicle Variant Seeding...")
        
        vehicles = Vehicle.objects.filter(is_active=True)
        created_count = 0
        updated_count = 0

        for v in vehicles:
            brand_name_lower = v.brand.name.strip().lower()
            start_price = float(v.starting_price or v.ex_showroom_price or 0)
            top_price = float(v.top_variant_price or v.starting_price or v.ex_showroom_price or 0)

            # If prices are 0, estimate from body type / segment
            if start_price == 0:
                start_price = 800000.0
                top_price = 1400000.0

            # Determine trims template
            trims = TRIM_TEMPLATES.get(brand_name_lower)
            if not trims:
                for b_key, b_trims in TRIM_TEMPLATES.items():
                    if b_key in brand_name_lower:
                        trims = b_trims
                        break

            if not trims:
                if start_price >= 3000000:
                    trims = LUXURY_TRIMS
                else:
                    trims = DEFAULT_TRIMS

            # Primary fuel type and optional secondary fuel type
            fuel_primary = (v.fuel_type or 'Petrol').strip()
            ev_flag = (v.ev_hybrid_cng_flag or 'No').strip()

            available_fuels = [fuel_primary]
            if 'cng' in ev_flag.lower() and 'CNG' not in available_fuels:
                available_fuels.append('CNG')
            if 'hybrid' in ev_flag.lower() and 'Hybrid' not in available_fuels:
                available_fuels.append('Hybrid')
            if 'ev' in ev_flag.lower() or 'electric' in ev_flag.lower() or 'ev' in v.name.lower() or 'electric' in v.name.lower():
                if 'Electric' not in available_fuels:
                    available_fuels.append('Electric')

            # Create variants
            price_span = top_price - start_price

            for trim_idx, (trim_name, ratio, trans_def) in enumerate(trims):
                if price_span > 0:
                    var_price = start_price + (price_span * ratio)
                else:
                    var_price = start_price if trim_idx == 0 else start_price * (1 + (0.05 * trim_idx))

                var_price = round(var_price / 10000) * 10000
                if var_price <= 0:
                    var_price = start_price

                if len(available_fuels) > 1 and trim_idx % 2 == 1:
                    var_fuel = available_fuels[1]
                else:
                    var_fuel = available_fuels[0]

                transmission = trans_def
                if any(x in trim_name for x in ['AMT', 'Automatic', 'AT', 'CVT', 'DSG', 'IVT', 'DCT', 'DCA']):
                    transmission = 'Automatic'
                elif any(x in trim_name for x in ['Manual', 'MT']):
                    transmission = 'Manual'
                else:
                    transmission = v.transmission or 'Manual'

                variant_obj, created = VehicleVariant.objects.get_or_create(
                    vehicle=v,
                    variant_name=trim_name,
                    defaults={
                        'ex_showroom_price': Decimal(str(int(var_price))),
                        'fuel_type': var_fuel,
                        'transmission': transmission
                    }
                )

                if created:
                    created_count += 1
                else:
                    variant_obj.ex_showroom_price = Decimal(str(int(var_price)))
                    variant_obj.fuel_type = var_fuel
                    variant_obj.transmission = transmission
                    variant_obj.save()
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully completed variant seeding! Created: {created_count}, Updated: {updated_count}. Total Variants: {VehicleVariant.objects.count()}"
        ))

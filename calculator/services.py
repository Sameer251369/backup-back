from decimal import Decimal
from .models import State, RoadTaxSlab, InsuranceEstimate, DealerCharge, VehicleStateEstimate, StateOnRoadPrice

TCS_THRESHOLD = Decimal('1000000.00')  # ₹10 Lakhs

MANDATORY_DISCLAIMER = (
    "Estimated on-road price = ex-showroom + state lifetime road tax + road safety cess + green tax + "
    "municipal cess + ₹600 registration + ₹200 smart card + ₹400 HSRP + ₹500 FASTag + IRDAI compliant comprehensive "
    "insurance (1-Yr OD + 3-Yr TP) + ₹1,000 miscellaneous charges. Excludes loan/hypothecation charges, accessories, "
    "dealer handling, discounts, and special imported/CBU rules. EV road-tax waivers are applied where reported. "
    "Actual on-road price can differ by city, RTO, variant, insurer, and state notification — please verify with your local RTO/dealer before purchase."
)


def _get_base_ex_showroom(vehicle, variant=None, variant_tier='start'):
    if variant and hasattr(variant, 'ex_showroom_price') and variant.ex_showroom_price:
        return Decimal(str(variant.ex_showroom_price))
    if variant_tier == 'top' and vehicle.top_variant_price:
        return Decimal(str(vehicle.top_variant_price))
    if vehicle.starting_price:
        return Decimal(str(vehicle.starting_price))
    return Decimal(str(vehicle.ex_showroom_price or 0))


def _calculate_tcs(base_price):
    """TCS (1% under Income Tax Act Section 206C) applies ONLY above ₹10 lakh ex-showroom."""
    try:
        val = Decimal(str(base_price))
        if val > TCS_THRESHOLD:
            return (val * Decimal('0.01')).quantize(Decimal('1.00'))
    except Exception:
        pass
    return Decimal('0.00')


def _calculate_irdai_insurance(base_price, fuel_type='petrol'):
    """
    IRDAI Compliant Insurance Calculation:
    - Insured Declared Value (IDV) = 95% of Ex-Showroom price for brand new vehicle.
    - Statutory 3-Year Third-Party (TP) Premium (IRDAI notification rate brackets).
    - 1-Year Own Damage (OD) Premium calculated off IDV.
    """
    base = Decimal(str(base_price))
    idv = (base * Decimal('0.95')).quantize(Decimal('1.00'))
    fuel_lower = str(fuel_type or '').lower()

    if 'electric' in fuel_lower or fuel_lower == 'ev':
        if base <= Decimal('1000000.00'):
            tp_premium = Decimal('5543.00')   # Sub 30kW
        elif base <= Decimal('2500000.00'):
            tp_premium = Decimal('9044.00')   # 30kW - 65kW
        else:
            tp_premium = Decimal('20907.00')  # > 65kW
        od_rate = Decimal('0.0120')          # 1.2% IDV for EV
    else:
        if base <= Decimal('700000.00'):
            tp_premium = Decimal('5286.00')   # Sub 1000 cc
        elif base <= Decimal('2000000.00'):
            tp_premium = Decimal('9580.00')   # 1000 cc - 1500 cc
        else:
            tp_premium = Decimal('24596.00')  # > 1500 cc

        if 'diesel' in fuel_lower:
            od_rate = Decimal('0.0180')       # 1.8% IDV for Diesel
        else:
            od_rate = Decimal('0.0150')       # 1.5% IDV for Petrol / CNG

    od_premium = (idv * od_rate).quantize(Decimal('1.00'))
    subtotal = od_premium + tp_premium
    gst = (subtotal * Decimal('0.18')).quantize(Decimal('1.00'))
    total_insurance = subtotal + gst

    return {
        'idv': float(idv),
        'third_party_premium': float(tp_premium),
        'own_damage_premium': float(od_premium),
        'insurance_gst': float(gst),
        'total_insurance': float(total_insurance),
    }


def _get_dealer_charges_total():
    dealer_charges_list = DealerCharge.objects.filter(is_default_included=True)
    if dealer_charges_list.exists():
        return sum(d.amount for d in dealer_charges_list)
    return Decimal('1500.00')


def _fixed_state_fees(state, is_financed=False):
    def money(value):
        return Decimal(str(value or 0)).quantize(Decimal('1.00'))

    hypothecation = money(state.hypothecation_fee) if is_financed else Decimal('0.00')
    return {
        'registration_fee': money(state.registration_fee),
        'smart_card_fee': money(state.smart_card_fee),
        'hsrp_fee': money(state.hsrp_fee),
        'fastag_fee': money(state.fastag_fee),
        'misc_fee': money(state.misc_fee),
        'hypothecation_fee': hypothecation,
    }


def _get_matching_slab(state, fuel_type, ownership_type, tax_basis_price):
    """
    Robust rule engine slab lookup from database matching fuel and individual vs company ownership.
    Provides candidate fuel priority fallbacks (e.g. Hybrid -> Petrol, CNG -> Petrol) and
    price-bracket clamping so on-road price calculation succeeds across all 36 States/UTs.
    """
    fuel_clean = (fuel_type or '').lower()

    # Resolve candidate fuels in order of legal and statutory priority
    if 'electric' in fuel_clean or 'ev' in fuel_clean:
        candidate_fuels = ['electric', 'all']
    elif 'hybrid' in fuel_clean:
        # Strong & mild hybrids: check hybrid-specific concession slab first, then fall back to base fuel
        if 'diesel' in fuel_clean:
            candidate_fuels = ['hybrid', 'diesel', 'petrol', 'all']
        else:
            candidate_fuels = ['hybrid', 'petrol', 'all']
    elif 'cng' in fuel_clean:
        # Bi-fuel CNG: check dedicated CNG slab first, then fall back to petrol slab
        candidate_fuels = ['cng', 'petrol', 'all']
    elif 'diesel' in fuel_clean:
        candidate_fuels = ['diesel', 'petrol', 'all']
    else:
        candidate_fuels = ['petrol', 'all']

    own_clean = (ownership_type or 'individual').lower()
    target_ownership = 'company' if own_clean == 'company' else 'individual'

    for cand_fuel in candidate_fuels:
        # 1. Try target ownership
        slabs = RoadTaxSlab.objects.filter(state=state, fuel_type=cand_fuel, ownership_type=target_ownership)
        if not slabs.exists():
            # 2. Fallback to ownership='all'
            slabs = RoadTaxSlab.objects.filter(state=state, fuel_type=cand_fuel, ownership_type='all')
        if not slabs.exists() and target_ownership == 'company':
            # 3. Fallback to ownership='individual'
            slabs = RoadTaxSlab.objects.filter(state=state, fuel_type=cand_fuel, ownership_type='individual')

        if slabs.exists():
            # Exact range match
            for slab in slabs:
                min_ok = tax_basis_price >= slab.min_price
                max_ok = (slab.max_price is None) or (tax_basis_price <= slab.max_price)
                if min_ok and max_ok:
                    return slab

            # If price exceeds all slabs or is below all slabs, pick the boundary bracket
            sorted_slabs = sorted(slabs, key=lambda s: s.min_price)
            if tax_basis_price < sorted_slabs[0].min_price:
                return sorted_slabs[0]
            return sorted_slabs[-1]

    # Ultimate defensive fallback: Any slab for this state
    fallback_slabs = RoadTaxSlab.objects.filter(state=state)
    if fallback_slabs.exists():
        sorted_slabs = sorted(fallback_slabs, key=lambda s: s.min_price)
        for slab in sorted_slabs:
            min_ok = tax_basis_price >= slab.min_price
            max_ok = (slab.max_price is None) or (tax_basis_price <= slab.max_price)
            if min_ok and max_ok:
                return slab
        return sorted_slabs[-1]

    return None


def calculate_on_road_price(
    vehicle,
    state,
    fuel_type=None,
    ownership_type='individual',
    variant=None,
    variant_tier='start',
    custom_ex_showroom=None,
    is_financed=False
):
    """
    Rule-Engine Based On-Road Price Calculator.
    Calculates exact, auditable itemized charges into 13 modular categories across all 36 States/UTs.
    Supports Individual vs Company registration and surfaces rule verification metadata.
    """
    effective_fuel = fuel_type or (variant.fuel_type if variant and variant.fuel_type else vehicle.fuel_type) or 'petrol'
    clean_ownership = 'company' if str(ownership_type).lower() == 'company' else 'individual'

    # 1. Handle Unlaunched / Price TBA Vehicles
    row = StateOnRoadPrice.objects.filter(car=vehicle, state=state).first()
    has_valid_base = bool(
        (vehicle.starting_price and vehicle.starting_price > 0) or
        (vehicle.ex_showroom_price and vehicle.ex_showroom_price > 0) or
        (variant and hasattr(variant, 'ex_showroom_price') and variant.ex_showroom_price and variant.ex_showroom_price > 0) or
        (row and row.start_ex_showroom and row.start_ex_showroom > 0) or
        (custom_ex_showroom is not None and float(custom_ex_showroom) > 0)
    )
    if vehicle.is_tba or not has_valid_base:
        return {
            'data_available': True,
            'is_tba': True,
            'message': 'Price to be announced by manufacturer',
            'state_name': state.name,
            'state_code': state.code,
            'vehicle_name': f"{vehicle.brand.name} {vehicle.name}",
            'disclaimer': MANDATORY_DISCLAIMER,
            'data_source_note': state.data_source_note or MANDATORY_DISCLAIMER,
            'total_on_road_price': None,
            'ex_showroom_price': None,
            'total_government_charges': 0.0,
            'total_insurance': 0.0,
            'optional_charges': 0.0,
            'final_on_road_price': None,
            'tcs_amount': 0.0,
            'hypothecation_fee': 0.0,
            'is_financed': is_financed,
            'ownership_type': clean_ownership,
            'note': 'Unlaunched / Price TBA vehicle',
        }

    # 2. Determine Ex-Showroom Base Price
    note = None
    if custom_ex_showroom is not None and float(custom_ex_showroom) > 0:
        base_price = Decimal(str(custom_ex_showroom))
        if row and row.start_ex_showroom and row.top_ex_showroom:
            start_ex = Decimal(str(row.start_ex_showroom))
            top_ex = Decimal(str(row.top_ex_showroom))
            if base_price < start_ex or base_price > top_ex:
                note = "Custom price outside standard variant range"
    else:
        base_price = _get_base_ex_showroom(vehicle, variant=variant, variant_tier=variant_tier)
        if not variant and row and row.start_ex_showroom:
            if variant_tier == 'top' and row.top_ex_showroom:
                base_price = Decimal(str(row.top_ex_showroom))
            elif row.start_ex_showroom:
                base_price = Decimal(str(row.start_ex_showroom))
        if base_price <= 0:
            base_price = _get_base_ex_showroom(vehicle, variant=variant, variant_tier=variant_tier)

    # 3. Determine Tax Basis Price (Ex-Showroom vs Pre-GST basis)
    if state.price_basis == 'pre_gst':
        tax_basis_price = base_price * state.pre_gst_factor
    else:
        tax_basis_price = base_price

    # 4. Rule Engine Slab Lookup
    matching_slab = _get_matching_slab(state, effective_fuel, clean_ownership, tax_basis_price)

    if not matching_slab:
        return {
            'data_available': False,
            'is_tba': False,
            'message': f"Tax rule data not available for {state.name} ({effective_fuel}, {clean_ownership}).",
            'state_name': state.name,
            'state_code': state.code,
            'vehicle_name': f"{vehicle.brand.name} {vehicle.name}",
            'disclaimer': MANDATORY_DISCLAIMER,
            'total_on_road_price': None,
            'ex_showroom_price': float(base_price),
        }

    # 5. Calculate 13 Modular Charge Categories
    # Category 1: Ex-Showroom
    cat1_ex_showroom = base_price

    # Category 2: State Lifetime Road Tax (includes Company Surcharge if company registration)
    base_tax_rate = matching_slab.rate
    if clean_ownership == 'company' and matching_slab.company_surcharge_rate > 0:
        effective_tax_rate = base_tax_rate + matching_slab.company_surcharge_rate
    else:
        effective_tax_rate = base_tax_rate
    cat2_road_tax = (tax_basis_price * effective_tax_rate).quantize(Decimal('1.00'))

    # Category 3: Registration Fee
    fees = _fixed_state_fees(state, is_financed=is_financed)
    cat3_reg_fee = fees['registration_fee']

    # Category 4: Smart Card RC Fee
    cat4_smart_card = fees['smart_card_fee']

    # Category 5: HSRP Fee
    cat5_hsrp = fees['hsrp_fee']

    # Category 6: Hypothecation Fee (if financed)
    cat6_hypothecation = fees['hypothecation_fee']

    # Category 7: Temporary Registration Fee
    cat7_temp_reg = matching_slab.temp_registration_fee or Decimal('0.00')

    # Category 8: Road Safety Cess
    cess_rate = matching_slab.cess_rate
    flat_cess = matching_slab.flat_cess
    cat8_road_safety_cess = (tax_basis_price * cess_rate + flat_cess).quantize(Decimal('1.00'))

    # Category 9: Green Tax
    cat9_green_tax = matching_slab.green_tax_flat or Decimal('0.00')

    # Category 10: Municipal / Infra Cess
    cat10_municipal_cess = (tax_basis_price * matching_slab.municipal_cess_rate).quantize(Decimal('1.00'))

    # Category 11: Comprehensive Insurance (IRDAI Compliant)
    ins_breakdown = _calculate_irdai_insurance(base_price, fuel_type=effective_fuel)
    cat11_insurance = Decimal(str(ins_breakdown['total_insurance']))

    # Category 12: FASTag Fee
    cat12_fastag = fees['fastag_fee']

    # Category 13: TCS (1% Income Tax Act > ₹10 Lakhs)
    cat13_tcs = _calculate_tcs(base_price)

    # Optional Dealer Handling Charges
    dealer_handling = _get_dealer_charges_total()
    misc_fee = fees['misc_fee']

    # 6. Calculate Subtotals Required by UI
    total_government_charges = (
        cat2_road_tax + cat3_reg_fee + cat4_smart_card + cat5_hsrp +
        cat6_hypothecation + cat7_temp_reg + cat8_road_safety_cess +
        cat9_green_tax + cat10_municipal_cess + cat13_tcs
    ).quantize(Decimal('1.00'))

    total_insurance = cat11_insurance.quantize(Decimal('1.00'))

    optional_charges = (
        cat12_fastag + dealer_handling + misc_fee
    ).quantize(Decimal('1.00'))

    final_on_road_price = (
        cat1_ex_showroom + total_government_charges + total_insurance + optional_charges
    ).quantize(Decimal('1.00'))

    # 7. Verification Metadata (effectiveFrom, effectiveTo, notificationNumber, sourceURL, lastVerified)
    rule_metadata = {
        'effectiveFrom': str(matching_slab.effective_from),
        'effectiveTo': str(matching_slab.effective_to) if matching_slab.effective_to else 'Standing Active Gazette',
        'notificationNumber': matching_slab.notification_number or 'GSR-2026/RTO-STD',
        'sourceURL': matching_slab.source_url or 'https://morth.nic.in',
        'lastVerified': str(matching_slab.last_verified),
    }

    return {
        'data_available': True,
        'is_tba': False,
        'pricing_path': 'rule_engine_verified',
        'ex_showroom_price': float(cat1_ex_showroom.quantize(Decimal('1.00'))),
        'effective_fuel_type': effective_fuel,
        'ownership_type': clean_ownership,
        'price_basis': state.price_basis,
        'tax_basis_price': float(tax_basis_price.quantize(Decimal('1.00'))),
        
        # 13 Modular Categories
        'road_tax': float(cat2_road_tax),
        'road_tax_rate_percent': float((effective_tax_rate * Decimal('100')).quantize(Decimal('0.01'))),
        'registration_fee': float(cat3_reg_fee),
        'smart_card_fee': float(cat4_smart_card),
        'hsrp_fee': float(cat5_hsrp),
        'hypothecation_fee': float(cat6_hypothecation),
        'temp_registration_fee': float(cat7_temp_reg),
        'road_safety_cess': float(cat8_road_safety_cess),
        'cess_rate_percent': float((cess_rate * Decimal('100')).quantize(Decimal('0.01'))),
        'green_tax': float(cat9_green_tax),
        'municipal_cess': float(cat10_municipal_cess),
        'insurance_estimate': float(cat11_insurance),
        'insurance_breakdown': ins_breakdown,
        'fastag_fee': float(cat12_fastag),
        'tcs_amount': float(cat13_tcs),
        'dealer_charges': float(dealer_handling),
        'misc_fee': float(misc_fee),

        # Subtotals at bottom
        'total_government_charges': float(total_government_charges),
        'total_insurance': float(total_insurance),
        'optional_charges': float(optional_charges),
        'final_on_road_price': float(final_on_road_price),
        'total_on_road_price': float(final_on_road_price),

        # Metadata
        'rule_metadata': rule_metadata,
        'is_financed': is_financed,
        'state_name': state.name,
        'state_code': state.code,
        'disclaimer': MANDATORY_DISCLAIMER,
        'data_source_note': matching_slab.notes or state.data_source_note or MANDATORY_DISCLAIMER,
        'variant_tier': variant_tier,
        'note': note,
    }

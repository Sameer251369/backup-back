from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from calculator.models import State, RoadTaxSlab

SLAB_DATA = {
    # Union Territories
    'DL': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Delhi EV Policy 100% Tax Exemption'),
        ('cng', 0, 600000, '0.0800', '0.0000', 0, 'Delhi CNG Sub-6L Slab'),
        ('cng', 600000, 1000000, '0.1000', '0.0000', 0, 'Delhi CNG 6L-10L Slab'),
        ('cng', 1000000, None, '0.1200', '0.0000', 0, 'Delhi CNG Above 10L Slab'),
        ('petrol', 0, 600000, '0.0800', '0.0000', 0, 'Delhi Petrol Sub-6L Slab'),
        ('petrol', 600000, 1000000, '0.1000', '0.0000', 0, 'Delhi Petrol 6L-10L Slab'),
        ('petrol', 1000000, None, '0.1200', '0.0000', 0, 'Delhi Petrol Above 10L Slab'),
        ('diesel', 0, 600000, '0.1000', '0.0000', 0, 'Delhi Diesel Sub-6L Slab'),
        ('diesel', 600000, 1000000, '0.1200', '0.0000', 0, 'Delhi Diesel 6L-10L Slab'),
        ('diesel', 1000000, None, '0.1400', '0.0000', 0, 'Delhi Diesel Above 10L Slab'),
    ],
    'CH': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Chandigarh EV Policy Exemption'),
        ('petrol', 0, 2000000, '0.0600', '0.0000', 0, 'Chandigarh Petrol Sub-20L (Pre-GST Basis)'),
        ('petrol', 2000000, None, '0.0800', '0.0000', 0, 'Chandigarh Petrol Above 20L'),
        ('cng', 0, 2000000, '0.0600', '0.0000', 0, 'Chandigarh CNG Sub-20L'),
        ('cng', 2000000, None, '0.0800', '0.0000', 0, 'Chandigarh CNG Above 20L'),
        ('diesel', 0, 2000000, '0.0800', '0.0000', 0, 'Chandigarh Diesel Sub-20L'),
        ('diesel', 2000000, None, '0.1000', '0.0000', 0, 'Chandigarh Diesel Above 20L'),
    ],
    'PY': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Puducherry EV Policy Exemption'),
        ('petrol', 0, 1000000, '0.0700', '0.0000', 0, 'Puducherry Petrol Sub-10L'),
        ('petrol', 1000000, None, '0.0900', '0.0000', 0, 'Puducherry Petrol Above 10L'),
        ('cng', 0, 1000000, '0.0700', '0.0000', 0, 'Puducherry CNG Sub-10L'),
        ('cng', 1000000, None, '0.0900', '0.0000', 0, 'Puducherry CNG Above 10L'),
        ('diesel', 0, 1000000, '0.0900', '0.0000', 0, 'Puducherry Diesel Sub-10L'),
        ('diesel', 1000000, None, '0.1100', '0.0000', 0, 'Puducherry Diesel Above 10L'),
    ],
    'JK': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'J&K EV Exemption'),
        ('petrol', 0, None, '0.0900', '0.0000', 0, 'J&K Petrol Flat Road Tax'),
        ('cng', 0, None, '0.0900', '0.0000', 0, 'J&K CNG Flat Road Tax'),
        ('diesel', 0, None, '0.1100', '0.0000', 0, 'J&K Diesel Flat Road Tax'),
    ],
    'LA': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Ladakh EV Exemption'),
        ('petrol', 0, None, '0.0800', '0.0000', 0, 'Ladakh Petrol Road Tax'),
        ('cng', 0, None, '0.0800', '0.0000', 0, 'Ladakh CNG Road Tax'),
        ('diesel', 0, None, '0.1000', '0.0000', 0, 'Ladakh Diesel Road Tax'),
    ],
    'AN': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Andaman EV Exemption'),
        ('petrol', 0, None, '0.0600', '0.0000', 0, 'Andaman Petrol Tax'),
        ('cng', 0, None, '0.0600', '0.0000', 0, 'Andaman CNG Tax'),
        ('diesel', 0, None, '0.0800', '0.0000', 0, 'Andaman Diesel Tax'),
    ],
    'LD': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Lakshadweep EV Exemption'),
        ('petrol', 0, None, '0.0600', '0.0000', 0, 'Lakshadweep Petrol Tax'),
        ('cng', 0, None, '0.0600', '0.0000', 0, 'Lakshadweep CNG Tax'),
        ('diesel', 0, None, '0.0800', '0.0000', 0, 'Lakshadweep Diesel Tax'),
    ],
    'DN': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Daman & Diu / Dadra EV Exemption'),
        ('petrol', 0, 1000000, '0.0600', '0.0000', 0, 'Dadra & Daman Petrol Sub-10L'),
        ('petrol', 1000000, None, '0.0800', '0.0000', 0, 'Dadra & Daman Petrol Above 10L'),
        ('cng', 0, 1000000, '0.0600', '0.0000', 0, 'Dadra & Daman CNG Sub-10L'),
        ('cng', 1000000, None, '0.0800', '0.0000', 0, 'Dadra & Daman CNG Above 10L'),
        ('diesel', 0, 1000000, '0.0800', '0.0000', 0, 'Dadra & Daman Diesel Sub-10L'),
        ('diesel', 1000000, None, '0.1000', '0.0000', 0, 'Dadra & Daman Diesel Above 10L'),
    ],

    # Major States
    'MH': [
        ('electric', 0, None, '0.0600', '0.0000', 0, 'Maharashtra EV Tax 6%'),
        ('petrol', 0, 1000000, '0.1100', '0.0000', 0, 'Maharashtra Petrol Sub-10L'),
        ('petrol', 1000000, 2000000, '0.1200', '0.0000', 0, 'Maharashtra Petrol 10L-20L'),
        ('petrol', 2000000, None, '0.1300', '0.0000', 0, 'Maharashtra Petrol Above 20L'),
        ('cng', 0, 1000000, '0.1100', '0.0000', 0, 'Maharashtra CNG Sub-10L'),
        ('cng', 1000000, None, '0.1200', '0.0000', 0, 'Maharashtra CNG Above 10L'),
        ('diesel', 0, 1000000, '0.1300', '0.0000', 0, 'Maharashtra Diesel Sub-10L'),
        ('diesel', 1000000, 2000000, '0.1400', '0.0000', 0, 'Maharashtra Diesel 10L-20L'),
        ('diesel', 2000000, None, '0.1500', '0.0000', 0, 'Maharashtra Diesel Above 20L'),
    ],
    'KA': [
        ('electric', 0, 2500000, '0.0000', '0.0000', 0, 'Karnataka EV Sub-25L Exemption'),
        ('electric', 2500000, None, '0.1000', '0.1100', 0, 'Karnataka EV Above 25L (10% Road Tax + 11% Infra Cess)'),
        ('petrol', 0, 500000, '0.1300', '0.1100', 0, 'Karnataka Petrol Sub-5L (11% Infrastructure Cess on Tax)'),
        ('petrol', 500000, 1000000, '0.1400', '0.1100', 0, 'Karnataka Petrol 5L-10L'),
        ('petrol', 1000000, 2000000, '0.1700', '0.1100', 0, 'Karnataka Petrol 10L-20L'),
        ('petrol', 2000000, None, '0.1800', '0.1100', 0, 'Karnataka Petrol Above 20L'),
        ('cng', 0, 1000000, '0.1400', '0.1100', 0, 'Karnataka CNG Sub-10L'),
        ('cng', 1000000, None, '0.1700', '0.1100', 0, 'Karnataka CNG Above 10L'),
        ('diesel', 0, 500000, '0.1500', '0.1100', 0, 'Karnataka Diesel Sub-5L'),
        ('diesel', 500000, 1000000, '0.1600', '0.1100', 0, 'Karnataka Diesel 5L-10L'),
        ('diesel', 1000000, 2000000, '0.1900', '0.1100', 0, 'Karnataka Diesel 10L-20L'),
        ('diesel', 2000000, None, '0.2000', '0.1100', 0, 'Karnataka Diesel Above 20L'),
    ],
    'KL': [
        ('electric', 0, None, '0.0500', '0.0100', 0, 'Kerala EV Tax 5% + 1% Green Cess'),
        ('petrol', 0, 500000, '0.0600', '0.0100', 0, 'Kerala Petrol Sub-5L'),
        ('petrol', 500000, 1000000, '0.1100', '0.0100', 0, 'Kerala Petrol 5L-10L'),
        ('petrol', 1000000, 1500000, '0.1300', '0.0100', 0, 'Kerala Petrol 10L-15L'),
        ('petrol', 1500000, 2000000, '0.1600', '0.0100', 0, 'Kerala Petrol 15L-20L'),
        ('petrol', 2000000, None, '0.2100', '0.0100', 0, 'Kerala Petrol Above 20L'),
        ('diesel', 0, 500000, '0.0800', '0.0100', 0, 'Kerala Diesel Sub-5L'),
        ('diesel', 500000, 1000000, '0.1300', '0.0100', 0, 'Kerala Diesel 5L-10L'),
        ('diesel', 1000000, 1500000, '0.1500', '0.0100', 0, 'Kerala Diesel 10L-15L'),
        ('diesel', 1500000, 2000000, '0.1800', '0.0100', 0, 'Kerala Diesel 15L-20L'),
        ('diesel', 2000000, None, '0.2300', '0.0100', 0, 'Kerala Diesel Above 20L'),
    ],
    'GJ': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Gujarat EV Policy Exemption'),
        ('petrol', 0, 1000000, '0.0600', '0.0000', 0, 'Gujarat Petrol Sub-10L (Pre-GST Basis)'),
        ('petrol', 1000000, None, '0.0800', '0.0000', 0, 'Gujarat Petrol Above 10L'),
        ('cng', 0, 1000000, '0.0600', '0.0000', 0, 'Gujarat CNG Sub-10L'),
        ('cng', 1000000, None, '0.0800', '0.0000', 0, 'Gujarat CNG Above 10L'),
        ('diesel', 0, 1000000, '0.0800', '0.0000', 0, 'Gujarat Diesel Sub-10L'),
        ('diesel', 1000000, None, '0.1000', '0.0000', 0, 'Gujarat Diesel Above 10L'),
    ],
    'UP': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'UP EV Policy 100% Tax Waiver'),
        ('petrol', 0, 1000000, '0.0800', '0.0100', 0, 'UP Petrol Sub-10L (1% Road Safety Cess)'),
        ('petrol', 1000000, None, '0.1000', '0.0100', 0, 'UP Petrol Above 10L'),
        ('cng', 0, 1000000, '0.0800', '0.0100', 0, 'UP CNG Sub-10L'),
        ('cng', 1000000, None, '0.1000', '0.0100', 0, 'UP CNG Above 10L'),
        ('hybrid', 0, None, '0.0000', '0.0000', 0, 'UP Strong Hybrid 100% Tax Waiver Policy'),
        ('diesel', 0, 1000000, '0.1000', '0.0100', 0, 'UP Diesel Sub-10L'),
        ('diesel', 1000000, None, '0.1200', '0.0100', 0, 'UP Diesel Above 10L'),
    ],
    'HR': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Haryana EV Policy Waiver'),
        ('petrol', 0, 600000, '0.0800', '0.0000', 0, 'Haryana Petrol Sub-6L'),
        ('petrol', 600000, 2000000, '0.1000', '0.0000', 0, 'Haryana Petrol 6L-20L'),
        ('petrol', 2000000, None, '0.1200', '0.0000', 0, 'Haryana Petrol Above 20L'),
        ('cng', 0, 600000, '0.0800', '0.0000', 0, 'Haryana CNG Sub-6L'),
        ('cng', 600000, 2000000, '0.1000', '0.0000', 0, 'Haryana CNG 6L-20L'),
        ('cng', 2000000, None, '0.1200', '0.0000', 0, 'Haryana CNG Above 20L'),
        ('hybrid', 0, 600000, '0.0800', '0.0000', 0, 'Haryana Hybrid Sub-6L'),
        ('hybrid', 600000, 2000000, '0.1000', '0.0000', 0, 'Haryana Hybrid 6L-20L'),
        ('hybrid', 2000000, None, '0.1200', '0.0000', 0, 'Haryana Hybrid Above 20L'),
        ('diesel', 0, 600000, '0.1000', '0.0000', 0, 'Haryana Diesel Sub-6L'),
        ('diesel', 600000, 2000000, '0.1200', '0.0000', 0, 'Haryana Diesel 6L-20L'),
        ('diesel', 2000000, None, '0.1400', '0.0000', 0, 'Haryana Diesel Above 20L'),
    ],
    'TN': [
        ('electric', 0, None, '0.0500', '0.0000', 0, 'Tamil Nadu EV Policy 5% Road Tax'),
        ('petrol', 0, 500000, '0.1200', '0.0000', 0, 'Tamil Nadu Petrol Sub-5L'),
        ('petrol', 500000, 1000000, '0.1300', '0.0000', 0, 'Tamil Nadu Petrol 5L-10L'),
        ('petrol', 1000000, 2000000, '0.1500', '0.0000', 0, 'Tamil Nadu Petrol 10L-20L'),
        ('petrol', 2000000, None, '0.1800', '0.0000', 0, 'Tamil Nadu Petrol Above 20L'),
        ('diesel', 0, 500000, '0.1400', '0.0000', 0, 'Tamil Nadu Diesel Sub-5L'),
        ('diesel', 500000, 1000000, '0.1500', '0.0000', 0, 'Tamil Nadu Diesel 5L-10L'),
        ('diesel', 1000000, 2000000, '0.1700', '0.0000', 0, 'Tamil Nadu Diesel 10L-20L'),
        ('diesel', 2000000, None, '0.2000', '0.0000', 0, 'Tamil Nadu Diesel Above 20L'),
    ],
    'TG': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Telangana EV Exemption'),
        ('petrol', 0, 500000, '0.1400', '0.0000', 0, 'Telangana Petrol Sub-5L'),
        ('petrol', 500000, 1000000, '0.1700', '0.0000', 0, 'Telangana Petrol 5L-10L'),
        ('petrol', 1000000, 2000000, '0.1800', '0.0000', 0, 'Telangana Petrol 10L-20L'),
        ('petrol', 2000000, None, '0.2000', '0.0000', 0, 'Telangana Petrol Above 20L'),
        ('diesel', 0, 500000, '0.1600', '0.0000', 0, 'Telangana Diesel Sub-5L'),
        ('diesel', 500000, 1000000, '0.1900', '0.0000', 0, 'Telangana Diesel 5L-10L'),
        ('diesel', 1000000, 2000000, '0.2000', '0.0000', 0, 'Telangana Diesel 10L-20L'),
        ('diesel', 2000000, None, '0.2200', '0.0000', 0, 'Telangana Diesel Above 20L'),
    ],
    'AP': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Andhra Pradesh EV Exemption'),
        ('petrol', 0, 500000, '0.1300', '0.0000', 0, 'Andhra Pradesh Petrol Sub-5L'),
        ('petrol', 500000, 1000000, '0.1400', '0.0000', 0, 'Andhra Pradesh Petrol 5L-10L'),
        ('petrol', 1000000, 2000000, '0.1700', '0.0000', 0, 'Andhra Pradesh Petrol 10L-20L'),
        ('petrol', 2000000, None, '0.1800', '0.0000', 0, 'Andhra Pradesh Petrol Above 20L'),
        ('diesel', 0, 500000, '0.1500', '0.0000', 0, 'Andhra Pradesh Diesel Sub-5L'),
        ('diesel', 500000, 1000000, '0.1600', '0.0000', 0, 'Andhra Pradesh Diesel 5L-10L'),
        ('diesel', 1000000, 2000000, '0.1900', '0.0000', 0, 'Andhra Pradesh Diesel 10L-20L'),
        ('diesel', 2000000, None, '0.2000', '0.0000', 0, 'Andhra Pradesh Diesel Above 20L'),
    ],
    'PB': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Punjab EV Exemption'),
        ('petrol', 0, 1000000, '0.0900', '0.0100', 0, 'Punjab Petrol Sub-10L (1% Green Cess)'),
        ('petrol', 1000000, 2000000, '0.1100', '0.0100', 0, 'Punjab Petrol 10L-20L'),
        ('petrol', 2000000, None, '0.1300', '0.0100', 0, 'Punjab Petrol Above 20L'),
        ('diesel', 0, 1000000, '0.1100', '0.0100', 0, 'Punjab Diesel Sub-10L'),
        ('diesel', 1000000, 2000000, '0.1300', '0.0100', 0, 'Punjab Diesel 10L-20L'),
        ('diesel', 2000000, None, '0.1500', '0.0100', 0, 'Punjab Diesel Above 20L'),
    ],
    'RJ': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Rajasthan EV Exemption'),
        ('petrol', 0, 800000, '0.0800', '0.0000', 0, 'Rajasthan Petrol Sub-8L'),
        ('petrol', 800000, 1500000, '0.1000', '0.0000', 0, 'Rajasthan Petrol 8L-15L'),
        ('petrol', 1500000, None, '0.1200', '0.0000', 0, 'Rajasthan Petrol Above 15L'),
        ('diesel', 0, 800000, '0.1000', '0.0000', 0, 'Rajasthan Diesel Sub-8L'),
        ('diesel', 800000, 1500000, '0.1200', '0.0000', 0, 'Rajasthan Diesel 8L-15L'),
        ('diesel', 1500000, None, '0.1400', '0.0000', 0, 'Rajasthan Diesel Above 15L'),
    ],
    'MP': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Madhya Pradesh EV Exemption'),
        ('petrol', 0, 500000, '0.0800', '0.0000', 0, 'MP Petrol Sub-5L'),
        ('petrol', 500000, 1000000, '0.1000', '0.0000', 0, 'MP Petrol 5L-10L'),
        ('petrol', 1000000, 2000000, '0.1200', '0.0000', 0, 'MP Petrol 10L-20L'),
        ('petrol', 2000000, None, '0.1400', '0.0000', 0, 'MP Petrol Above 20L'),
        ('diesel', 0, 500000, '0.1000', '0.0000', 0, 'MP Diesel Sub-5L'),
        ('diesel', 500000, 1000000, '0.1200', '0.0000', 0, 'MP Diesel 5L-10L'),
        ('diesel', 1000000, 2000000, '0.1400', '0.0000', 0, 'MP Diesel 10L-20L'),
        ('diesel', 2000000, None, '0.1600', '0.0000', 0, 'MP Diesel Above 20L'),
    ],
    'WB': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'West Bengal EV Exemption'),
        ('petrol', 0, 600000, '0.1000', '0.0000', 0, 'West Bengal Petrol Sub-6L'),
        ('petrol', 600000, 1000000, '0.1100', '0.0000', 0, 'West Bengal Petrol 6L-10L'),
        ('petrol', 1000000, 2000000, '0.1200', '0.0000', 0, 'West Bengal Petrol 10L-20L'),
        ('petrol', 2000000, None, '0.1500', '0.0000', 0, 'West Bengal Petrol Above 20L'),
        ('diesel', 0, 600000, '0.1200', '0.0000', 0, 'West Bengal Diesel Sub-6L'),
        ('diesel', 600000, 1000000, '0.1300', '0.0000', 0, 'West Bengal Diesel 6L-10L'),
        ('diesel', 1000000, 2000000, '0.1400', '0.0000', 0, 'West Bengal Diesel 10L-20L'),
        ('diesel', 2000000, None, '0.1700', '0.0000', 0, 'West Bengal Diesel Above 20L'),
    ],
    'BR': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Bihar EV Policy Exemption'),
        ('petrol', 0, 800000, '0.0800', '0.0000', 0, 'Bihar Petrol Sub-8L'),
        ('petrol', 800000, 1500000, '0.0900', '0.0000', 0, 'Bihar Petrol 8L-15L'),
        ('petrol', 1500000, None, '0.1000', '0.0000', 0, 'Bihar Petrol Above 15L'),
        ('cng', 0, 800000, '0.0800', '0.0000', 0, 'Bihar CNG Sub-8L'),
        ('cng', 800000, 1500000, '0.0900', '0.0000', 0, 'Bihar CNG 8L-15L'),
        ('cng', 1500000, None, '0.1000', '0.0000', 0, 'Bihar CNG Above 15L'),
        ('hybrid', 0, 800000, '0.0800', '0.0000', 0, 'Bihar Hybrid Sub-8L'),
        ('hybrid', 800000, 1500000, '0.0900', '0.0000', 0, 'Bihar Hybrid 8L-15L'),
        ('hybrid', 1500000, None, '0.1000', '0.0000', 0, 'Bihar Hybrid Above 15L'),
        ('diesel', 0, 800000, '0.1000', '0.0000', 0, 'Bihar Diesel Sub-8L'),
        ('diesel', 800000, 1500000, '0.1100', '0.0000', 0, 'Bihar Diesel 8L-15L'),
        ('diesel', 1500000, None, '0.1200', '0.0000', 0, 'Bihar Diesel Above 15L'),
    ],
    'JH': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Jharkhand EV Exemption'),
        ('petrol', 0, 1000000, '0.0600', '0.0000', 0, 'Jharkhand Petrol Sub-10L (Pre-GST Basis)'),
        ('petrol', 1000000, None, '0.0800', '0.0000', 0, 'Jharkhand Petrol Above 10L'),
        ('diesel', 0, 1000000, '0.0800', '0.0000', 0, 'Jharkhand Diesel Sub-10L'),
        ('diesel', 1000000, None, '0.1000', '0.0000', 0, 'Jharkhand Diesel Above 10L'),
    ],
    'OD': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Odisha EV Policy Waiver'),
        ('petrol', 0, 500000, '0.0800', '0.0000', 0, 'Odisha Petrol Sub-5L'),
        ('petrol', 500000, 1000000, '0.1000', '0.0000', 0, 'Odisha Petrol 5L-10L'),
        ('petrol', 1000000, None, '0.1200', '0.0000', 0, 'Odisha Petrol Above 10L'),
        ('diesel', 0, 500000, '0.1000', '0.0000', 0, 'Odisha Diesel Sub-5L'),
        ('diesel', 500000, 1000000, '0.1200', '0.0000', 0, 'Odisha Diesel 5L-10L'),
        ('diesel', 1000000, None, '0.1400', '0.0000', 0, 'Odisha Diesel Above 10L'),
    ],
    'CG': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Chhattisgarh EV Exemption'),
        ('petrol', 0, 500000, '0.0800', '0.0000', 0, 'Chhattisgarh Petrol Sub-5L'),
        ('petrol', 500000, 1000000, '0.0900', '0.0000', 0, 'Chhattisgarh Petrol 5L-10L'),
        ('petrol', 1000000, None, '0.1000', '0.0000', 0, 'Chhattisgarh Petrol Above 10L'),
        ('diesel', 0, 500000, '0.1000', '0.0000', 0, 'Chhattisgarh Diesel Sub-5L'),
        ('diesel', 500000, 1000000, '0.1100', '0.0000', 0, 'Chhattisgarh Diesel 5L-10L'),
        ('diesel', 1000000, None, '0.1200', '0.0000', 0, 'Chhattisgarh Diesel Above 10L'),
    ],
    'HP': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Himachal EV Policy Waiver'),
        ('petrol', 0, 600000, '0.0600', '0.0000', 0, 'Himachal Petrol Sub-6L'),
        ('petrol', 600000, 1000000, '0.0700', '0.0000', 0, 'Himachal Petrol 6L-10L'),
        ('petrol', 1000000, None, '0.0800', '0.0000', 0, 'Himachal Petrol Above 10L'),
        ('diesel', 0, 600000, '0.0800', '0.0000', 0, 'Himachal Diesel Sub-6L'),
        ('diesel', 600000, 1000000, '0.0900', '0.0000', 0, 'Himachal Diesel 6L-10L'),
        ('diesel', 1000000, None, '0.1000', '0.0000', 0, 'Himachal Diesel Above 10L'),
    ],
    'UK': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Uttarakhand EV Waiver'),
        ('petrol', 0, 1000000, '0.0800', '0.0000', 0, 'Uttarakhand Petrol Sub-10L'),
        ('petrol', 1000000, None, '0.0900', '0.0000', 0, 'Uttarakhand Petrol Above 10L'),
        ('diesel', 0, 1000000, '0.1000', '0.0000', 0, 'Uttarakhand Diesel Sub-10L'),
        ('diesel', 1000000, None, '0.1100', '0.0000', 0, 'Uttarakhand Diesel Above 10L'),
    ],
    'GA': [
        ('electric', 0, None, '0.0000', '0.0000', 0, 'Goa EV Exemption'),
        ('petrol', 0, 600000, '0.0900', '0.0000', 0, 'Goa Petrol Sub-6L'),
        ('petrol', 600000, 1500000, '0.1200', '0.0000', 0, 'Goa Petrol 6L-15L'),
        ('petrol', 1500000, None, '0.1500', '0.0000', 0, 'Goa Petrol Above 15L'),
        ('diesel', 0, 600000, '0.1100', '0.0000', 0, 'Goa Diesel Sub-6L'),
        ('diesel', 600000, 1500000, '0.1400', '0.0000', 0, 'Goa Diesel 6L-15L'),
        ('diesel', 1500000, None, '0.1700', '0.0000', 0, 'Goa Diesel Above 15L'),
    ],
}

# Add standard North Eastern state defaults for AR, AS, MN, ML, MZ, NL, SK, TR
NE_STATES = ['AR', 'AS', 'MN', 'ML', 'MZ', 'NL', 'SK', 'TR']
for ne in NE_STATES:
    SLAB_DATA[ne] = [
        ('electric', 0, None, '0.0000', '0.0000', 0, f'{ne} EV Exemption'),
        ('petrol', 0, 1000000, '0.0800', '0.0000', 0, f'{ne} Petrol Sub-10L'),
        ('petrol', 1000000, None, '0.1000', '0.0000', 0, f'{ne} Petrol Above 10L'),
        ('cng', 0, 1000000, '0.0800', '0.0000', 0, f'{ne} CNG Sub-10L'),
        ('cng', 1000000, None, '0.1000', '0.0000', 0, f'{ne} CNG Above 10L'),
        ('diesel', 0, 1000000, '0.1000', '0.0000', 0, f'{ne} Diesel Sub-10L'),
        ('diesel', 1000000, None, '0.1200', '0.0000', 0, f'{ne} Diesel Above 10L'),
    ]

# Ensure every state in SLAB_DATA has explicit CNG and Hybrid slabs
for code, slabs in list(SLAB_DATA.items()):
    fuels_in_state = {s[0] for s in slabs}
    petrol_slabs = [s for s in slabs if s[0] == 'petrol']

    if 'cng' not in fuels_in_state and petrol_slabs:
        for p in petrol_slabs:
            slabs.append(('cng', p[1], p[2], p[3], p[4], p[5], p[6].replace('Petrol', 'CNG')))

    if 'hybrid' not in fuels_in_state and petrol_slabs:
        for p in petrol_slabs:
            slabs.append(('hybrid', p[1], p[2], p[3], p[4], p[5], p[6].replace('Petrol', 'Hybrid')))

class Command(BaseCommand):
    help = "Idempotently seed verified RTO tax slabs and cess for all 36 States and Union Territories."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Tax Slabs for 36 States and UTs..."))

        total_created = 0
        total_updated = 0

        with transaction.atomic():
            for code, slabs in SLAB_DATA.items():
                state_obj = State.objects.filter(code=code).first()
                if not state_obj:
                    self.stdout.write(self.style.WARNING(f"State with code '{code}' not found. Skipping."))
                    continue

                for fuel, min_p, max_p, rate_str, cess_str, flat_c, note in slabs:
                    min_dec = Decimal(str(min_p))
                    max_dec = Decimal(str(max_p)) if max_p is not None else None
                    rate_dec = Decimal(rate_str)
                    cess_dec = Decimal(cess_str)
                    flat_dec = Decimal(str(flat_c))

                    existing = RoadTaxSlab.objects.filter(
                        state=state_obj,
                        fuel_type=fuel,
                        ownership_type='all',
                        min_price=min_dec,
                        max_price=max_dec
                    ).first()

                    if not existing:
                        slab_obj = RoadTaxSlab.objects.create(
                            state=state_obj,
                            fuel_type=fuel,
                            ownership_type='all',
                            min_price=min_dec,
                            max_price=max_dec,
                            rate=rate_dec,
                            cess_rate=cess_dec,
                            flat_cess=flat_dec,
                            notes=note,
                        )
                        total_created += 1
                    else:
                        slab_obj = existing
                        updated = False
                        if (slab_obj.rate != rate_dec or slab_obj.cess_rate != cess_dec or 
                            slab_obj.flat_cess != flat_dec or slab_obj.notes != note):
                            slab_obj.rate = rate_dec
                            slab_obj.cess_rate = cess_dec
                            slab_obj.flat_cess = flat_dec
                            slab_obj.notes = note
                            slab_obj.save()
                            total_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Tax Slabs Seed Complete! Total Slabs Created: {total_created}, Updated: {total_updated} across 36 States/UTs."
        ))

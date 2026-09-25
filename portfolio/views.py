from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from .models import Brand, Vehicle
from .serializers import (
    BrandSerializer,
    VehicleListSerializer,
    VehicleDetailSerializer,
    VehicleAdminWorklistSerializer,
    VehicleAdminCreateSerializer,
    VehicleAdminUpdateSerializer,
)


class VehiclePagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 1000

    def get_page_size(self, request):
        page_size = request.query_params.get(self.page_size_query_param)
        if page_size == 'all':
            return self.max_page_size
        return super().get_page_size(request)


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.filter(
        vehicles__is_active=True,
        vehicles__needs_review=False,
    ).distinct()
    serializer_class = BrandSerializer
    lookup_field = 'slug'
    pagination_class = None


class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vehicle.objects.filter(
        is_active=True
    ).select_related('brand').prefetch_related('images', 'variants')
    lookup_field = 'slug'
    pagination_class = VehiclePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['brand', 'brand__id', 'brand__slug', 'body_type', 'ev_hybrid_cng_flag', 'is_featured', 'is_tba']
    search_fields = ['name', 'brand__name', 'key_specs', 'transmission']
    ordering_fields = ['ex_showroom_price', 'starting_price', 'created_at', 'name']
    ordering = ['-is_featured', 'brand__name', 'name']

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        fuel_param = self.request.query_params.get('fuel_type')
        if fuel_param:
            fuel = fuel_param.strip().lower()
            if fuel in ('electric', 'ev'):
                queryset = queryset.filter(
                    Q(fuel_type__icontains='electric')
                    | Q(fuel_type__icontains='ev')
                    | Q(ev_hybrid_cng_flag__iexact='EV')
                )
            elif fuel in ('petrol', 'diesel', 'cng', 'hybrid'):
                queryset = queryset.filter(fuel_type__icontains=fuel)
            else:
                queryset = queryset.none()
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return VehicleDetailSerializer
        return VehicleListSerializer

    @action(detail=False, methods=['get'])
    def facets(self, request):
        """Return distinct filter values from active, reviewed vehicles."""
        base_qs = Vehicle.objects.filter(is_active=True, needs_review=False)
        raw_fuels = base_qs.values_list('fuel_type', flat=True).distinct()
        clean_fuels = set()
        for f in raw_fuels:
            if not f:
                continue
            s = str(f).lower()
            if 'petrol' in s:
                clean_fuels.add('Petrol')
            if 'diesel' in s:
                clean_fuels.add('Diesel')
            if 'cng' in s:
                clean_fuels.add('CNG')
            if 'electric' in s or 'ev' in s:
                clean_fuels.add('Electric')
            if 'hybrid' in s:
                clean_fuels.add('Hybrid')

        # Distinct active brands
        brand_qs = (
            Brand.objects.filter(vehicles__is_active=True, vehicles__needs_review=False)
            .annotate(vehicle_count=Count('vehicles', distinct=True))
            .values('id', 'name', 'slug', 'vehicle_count')
            .order_by('name')
        )
        unique_brands = list({b['id']: b for b in brand_qs}.values())

        return Response({
            'brands': unique_brands,
            'body_types': sorted(
                list(set(filter(None, base_qs.values_list('body_type', flat=True).distinct())))
            ),
            'fuel_types': sorted(list(clean_fuels)),
            'ev_hybrid_cng_flags': sorted(
                list(set(filter(None, base_qs.values_list('ev_hybrid_cng_flag', flat=True).distinct())))
            ),
        })


class AdminVehicleWorklistViewSet(viewsets.ModelViewSet):
    """Admin endpoint for listing, reviewing, creating, and updating vehicles."""
    queryset = Vehicle.objects.all().select_related('brand').prefetch_related('images', 'variants').order_by('-created_at', 'brand__name', 'name')
    serializer_class = VehicleAdminWorklistSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['brand__slug', 'is_active', 'body_type', 'fuel_type', 'data_source', 'needs_review']
    search_fields = ['name', 'brand__name', 'transmission']
    ordering_fields = ['created_at', 'name', 'starting_price']
    ordering = ['-created_at']
    pagination_class = None

    def get_queryset(self):
        if self.action == 'create':
            return Vehicle.objects.none()
        qs = Vehicle.objects.all().select_related('brand').prefetch_related('images', 'variants').order_by('-created_at')
        params = self.request.query_params
        if 'data_source' in params and params['data_source'] != 'all':
            qs = qs.filter(data_source=params['data_source'])
        if 'needs_review' in params:
            val = params['needs_review'].lower() in ('true', '1', 'yes')
            qs = qs.filter(needs_review=val)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return VehicleAdminCreateSerializer
        if self.action in ('update', 'partial_update'):
            return VehicleAdminUpdateSerializer
        if self.action == 'retrieve':
            return VehicleDetailSerializer
        return VehicleAdminWorklistSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        vehicle = serializer.save()
        output = VehicleListSerializer(vehicle, context={'request': request})
        return Response({
            'message': 'Vehicle published successfully.',
            'vehicle': output.data,
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={'request': request})
        serializer.is_valid(raise_exception=True)
        vehicle = serializer.save()
        output = VehicleAdminWorklistSerializer(vehicle, context={'request': request})
        return Response({
            'message': 'Vehicle updated successfully.',
            'vehicle': output.data,
        })

    @action(detail=False, methods=['get'], url_path='needs-review')
    def needs_review(self, request):
        queryset = self.get_queryset().filter(needs_review=True)
        serializer = VehicleAdminWorklistSerializer(queryset, many=True, context={'request': request})
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
        })


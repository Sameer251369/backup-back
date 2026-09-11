from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from .models import Brand, Vehicle
from .serializers import (
    BrandSerializer,
    VehicleListSerializer,
    VehicleDetailSerializer,
    VehicleAdminWorklistSerializer,
    VehicleAdminCreateSerializer,
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
    queryset = Brand.objects.all()
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
    filterset_fields = ['brand__slug', 'body_type', 'fuel_type', 'ev_hybrid_cng_flag', 'is_featured', 'is_tba']
    search_fields = ['name', 'brand__name', 'key_specs', 'transmission']
    ordering_fields = ['ex_showroom_price', 'starting_price', 'created_at', 'name']
    ordering = ['-is_featured', 'brand__name', 'name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return VehicleDetailSerializer
        return VehicleListSerializer

    @action(detail=False, methods=['get'])
    def facets(self, request):
        """Return distinct filter values from active, reviewed vehicles."""
        base_qs = Vehicle.objects.filter(is_active=True, needs_review=False)
        return Response({
            'brands': list(
                Brand.objects.filter(vehicles__is_active=True, vehicles__needs_review=False)
                .annotate(vehicle_count=Count('vehicles'))
                .values('id', 'name', 'slug', 'vehicle_count')
                .order_by('name')
            ),
            'body_types': sorted(
                base_qs.values_list('body_type', flat=True).distinct()
            ),
            'fuel_types': sorted(
                base_qs.values_list('fuel_type', flat=True).distinct()
            ),
            'ev_hybrid_cng_flags': sorted(
                base_qs.values_list('ev_hybrid_cng_flag', flat=True).distinct()
            ),
        })


class AdminVehicleWorklistViewSet(viewsets.ModelViewSet):
    """Admin endpoint for reviewing and publishing vehicles."""
    queryset = Vehicle.objects.filter(needs_review=True).select_related('brand').order_by('brand__name', 'name')
    serializer_class = VehicleAdminWorklistSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['brand__slug', 'is_active', 'body_type', 'fuel_type']
    search_fields = ['name', 'brand__name', 'transmission']
    ordering_fields = ['created_at', 'name', 'starting_price']
    ordering = ['-created_at']
    pagination_class = None

    def get_queryset(self):
        if self.action == 'create':
            return Vehicle.objects.none()
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == 'create':
            return VehicleAdminCreateSerializer
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

    @action(detail=False, methods=['get'], url_path='needs-review')
    def needs_review(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
        })

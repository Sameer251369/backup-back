import csv
import datetime
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q
from .models import Lead
from .serializers import LeadAdminSerializer

class AdminLeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.all()
    serializer_class = LeadAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_exported', 'brand_snapshot', 'state']
    search_fields = ['name', 'phone_number', 'city', 'brand_snapshot', 'vehicle_name_snapshot']
    ordering_fields = ['created_at', 'on_road_price_calculated']
    ordering = ['-created_at']
    pagination_class = PageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset().select_related('state', 'vehicle')
        params = self.request.query_params

        # Filter by Date range or preset
        date_preset = params.get('date_preset')
        now = timezone.now()

        if date_preset == 'today':
            qs = qs.filter(created_at__date=now.date())
        elif date_preset == 'yesterday':
            yesterday = (now - datetime.timedelta(days=1)).date()
            qs = qs.filter(created_at__date=yesterday)
        elif date_preset == 'this_week' or date_preset == '7days':
            qs = qs.filter(created_at__gte=now - datetime.timedelta(days=7))
        elif date_preset == 'this_month' or date_preset == '30days':
            qs = qs.filter(created_at__gte=now - datetime.timedelta(days=30))

        date_from = params.get('date_from')
        if date_from:
            try:
                qs = qs.filter(created_at__date__gte=date_from)
            except Exception:
                pass

        date_to = params.get('date_to')
        if date_to:
            try:
                qs = qs.filter(created_at__date__lte=date_to)
            except Exception:
                pass

        # Filter by State (ID or Name)
        state_param = params.get('state_id') or params.get('state_name') or params.get('state')
        if state_param and state_param.lower() != 'all':
            if state_param.isdigit():
                qs = qs.filter(state_id=int(state_param))
            else:
                qs = qs.filter(state__name__icontains=state_param)

        # Filter by Car / Vehicle
        car_param = params.get('car') or params.get('vehicle') or params.get('vehicle_name')
        if car_param and car_param.lower() != 'all':
            if car_param.isdigit():
                qs = qs.filter(vehicle_id=int(car_param))
            else:
                qs = qs.filter(
                    Q(vehicle_name_snapshot__icontains=car_param) |
                    Q(brand_snapshot__icontains=car_param)
                )

        brand_param = params.get('brand')
        if brand_param and brand_param.lower() != 'all':
            qs = qs.filter(brand_snapshot__icontains=brand_param)

        return qs

    @action(detail=False, methods=['post'])
    def mark_exported(self, request):
        lead_ids = request.data.get('lead_ids', [])
        if not lead_ids:
            return Response({'error': 'lead_ids array is required'}, status=status.HTTP_400_BAD_REQUEST)

        updated_count = Lead.objects.filter(id__in=lead_ids).update(
            is_exported=True,
            exported_at=timezone.now(),
        )
        return Response({'message': f'Successfully marked {updated_count} leads as exported'})

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export leads as CSV respecting all current filters."""
        queryset = self.filter_queryset(self.get_queryset())

        is_exported = request.query_params.get('is_exported')
        if is_exported is not None and is_exported.lower() != 'all':
            queryset = queryset.filter(is_exported=is_exported.lower() in ('true', '1', 'yes'))

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="car_guide_leads.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Name', 'Phone', 'City', 'State', 'Brand', 'Vehicle',
            'Ex-Showroom Price', 'On-Road Price', 'Source Page',
            'Created At', 'Is Exported', 'Exported At',
        ])

        for lead in queryset:
            writer.writerow([
                lead.id,
                lead.name,
                lead.phone_number,
                lead.city,
                lead.state.name if lead.state else '',
                lead.brand_snapshot,
                lead.vehicle_name_snapshot,
                lead.ex_showroom_price_at_query,
                lead.on_road_price_calculated,
                lead.source_page,
                lead.created_at.isoformat() if lead.created_at else '',
                lead.is_exported,
                lead.exported_at.isoformat() if lead.exported_at else '',
            ])

        return response


# Save as: tender/management/commands/export_plots_with_location.py

import os
from django.core.management.base import BaseCommand
from openpyxl import Workbook
from tender.models import Plot


class Command(BaseCommand):
    help = 'Export plots with lat/lng to Excel'

    def handle(self, *args, **options):
        plots = (
            Plot.objects
            .filter(latitude__isnull=False, longitude__isnull=False)
            .select_related('farmer')
            .prefetch_related('clusters')
        )

        wb = Workbook()
        ws = wb.active
        ws.title = 'Plots with Location'

        # Header
        ws.append([
            'Plot ID',
            'Plot Name',
            'Plot Code',
            'Area (Acres)',
            'Crop',
            'Variety',
            'Pruning Date',
            'Latitude',
            'Longitude',
            'Farmer ID',
            'Farmer Name',
            'Farmer Phone',
            'Farmer Location',
            'Farmer Latitude',
            'Farmer Longitude',
            'Clusters',
        ])

        count = 0
        for p in plots:
            clusters = ', '.join(c.name for c in p.clusters.all())
            ws.append([
                p.id,
                p.name,
                p.plot_code or '',
                float(p.area_acres),
                p.crop_name,
                p.variety,
                str(p.pruning_date) if p.pruning_date else '',
                float(p.latitude),
                float(p.longitude),
                p.farmer_id,
                p.farmer.farmer_name,
                p.farmer.phone_number,
                p.farmer.location,
                float(p.farmer.latitude) if p.farmer.latitude else '',
                float(p.farmer.longitude) if p.farmer.longitude else '',
                clusters,
            ])
            count += 1

        path = 'plots_with_location.xlsx'
        wb.save(path)
        self.stdout.write(self.style.SUCCESS(
            f'Exported {count} plots with location to {os.path.abspath(path)}'
        ))
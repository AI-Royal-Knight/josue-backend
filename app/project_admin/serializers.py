from rest_framework import serializers
from .models import Project
from app.account.models import RoleAssignment, UserAccount
from django.db.models import Q, Sum


class ProjectListSerializer(serializers.ModelSerializer):
    estimate_profit = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    is_overdue = serializers.BooleanField(read_only=True)
    total_po_raised = serializers.SerializerMethodField()
    proforma_nr = serializers.SerializerMethodField()
    total_unclaimed = serializers.SerializerMethodField()
    total_overspend = serializers.SerializerMethodField()
    is_user_clock_in_enabled = serializers.SerializerMethodField()

    def get_is_user_clock_in_enabled(self, obj):
        from app.project_admin.models import ApprovalConfiguration
        config = ApprovalConfiguration.objects.filter(
            project=obj,
            action_type=ApprovalConfiguration.ActionType.USER_CLOCK_IN
        ).first()
        if config:
            return config.is_active
        return True

    def _calculate_subfolder_totals(self, obj):
        from app.project_admin.models import UserInvoice, FolderAssignment, ProjectSubfolder

        subfolders = ProjectSubfolder.objects.filter(
            folder__project=obj
        ).select_related('folder')

        if not subfolders.exists():
            return 0.0, 0.0

        all_invoices = list(UserInvoice.objects.filter(
            project=obj,
            source_type=UserInvoice.SourceType.LABOUR_TARGET,
            status=UserInvoice.Status.SUBMITTED,
        ))

        subfolder_assignments = {}
        for sub in subfolders:
            assignments = FolderAssignment.objects.filter(subfolder=sub)
            subfolder_assignments[sub.id] = {
                'subfolder': sub,
                'assignment_ids': [str(a.id) for a in assignments],
                'user_ids': [a.user_id for a in assignments],
                'invoices_sum': 0.0
            }

        processed_invoice_ids = set()

        for inv in all_invoices:
            matched_sub_id = None
            sid = inv.source_id or ""

            # 1. Try to match by assignment_id in source_id
            for sub_id, data in subfolder_assignments.items():
                for aid in data['assignment_ids']:
                    if sid == aid or sid.startswith(f"{aid}:"):
                        matched_sub_id = sub_id
                        break
                if matched_sub_id:
                    break

            # 2. Try to match by work_area / subfolder name
            if not matched_sub_id and inv.work_area:
                for sub_id, data in subfolder_assignments.items():
                    if inv.work_area.strip().lower() == data['subfolder'].name.strip().lower():
                        matched_sub_id = sub_id
                        break

            # 3. Try to match by user_id
            if not matched_sub_id and inv.created_by_id:
                for sub_id, data in subfolder_assignments.items():
                    if inv.created_by_id in data['user_ids']:
                        matched_sub_id = sub_id
                        break

            # 4. Fallback: attribute to the first subfolder of the project
            if not matched_sub_id and subfolders.exists():
                matched_sub_id = subfolders.first().id

            if matched_sub_id and inv.id not in processed_invoice_ids:
                subfolder_assignments[matched_sub_id]['invoices_sum'] += float(inv.total or 0)
                processed_invoice_ids.add(inv.id)

        # Calculate per-row: each row's invoice is compared against that row's labour target
        total_unclaimed = 0.0
        total_overspend = 0.0

        from app.project_admin.models import FolderAssignment
        for data in subfolder_assignments.values():
            sub = data['subfolder']
            assignment_ids = data['assignment_ids']
            rows = sub.rows or []

            for row_index, row in enumerate(rows):
                row_lt = float(row.get('labourTarget', 0) or 0)
                if row_lt == 0:
                    continue

                # Match invoices for this exact row (source_id = "aid:row_index")
                q_row = Q()
                for aid in assignment_ids:
                    q_row |= Q(source_id=f"{aid}:{row_index}")

                row_invoiced = UserInvoice.objects.filter(
                    q_row,
                    project=obj,
                    source_type=UserInvoice.SourceType.LABOUR_TARGET,
                ).aggregate(t=Sum('total'))['t'] or 0
                row_invoiced = float(row_invoiced)

                total_unclaimed += max(row_lt - row_invoiced, 0.0)
                total_overspend += max(row_invoiced - row_lt, 0.0)

            # Handle subfolders with no rows but a top-level labour_target
            if not rows and sub.labour_target:
                sub_lt = float(sub.labour_target)
                q_sub = Q()
                for aid in assignment_ids:
                    q_sub |= Q(source_id=aid) | Q(source_id__startswith=f"{aid}:")
                sub_invoiced = float(UserInvoice.objects.filter(
                    q_sub,
                    project=obj,
                    source_type=UserInvoice.SourceType.LABOUR_TARGET,
                ).aggregate(t=Sum('total'))['t'] or 0)
                total_unclaimed += max(sub_lt - sub_invoiced, 0.0)
                total_overspend += max(sub_invoiced - sub_lt, 0.0)

        return total_unclaimed, total_overspend

    def get_total_unclaimed(self, obj):
        unclaimed, _ = self._calculate_subfolder_totals(obj)
        return unclaimed

    def get_total_overspend(self, obj):
        _, overspend = self._calculate_subfolder_totals(obj)
        return overspend

    def get_proforma_nr(self, obj):
        from app.project_admin.models import UserInvoice
        from django.db.models import Sum
        proformas = UserInvoice.objects.filter(
            project=obj, 
            source_type=UserInvoice.SourceType.PROFORMA,
            status=UserInvoice.Status.SUBMITTED
        )
        return proformas.aggregate(amt=Sum('total'))['amt'] or 0

    def get_total_po_raised(self, obj):
        from app.procurement_department.models import Quotation
        from django.db.models import Sum, Q
        approved_pos = Quotation.objects.filter(
            project=obj,
            status=Quotation.Status.APPROVED,
        ).filter(
            Q(variation_ref__isnull=True) | 
            Q(variation_ref__exact="") | 
            Q(variation_ref__iexact="none") | 
            Q(variation_ref__exact="-")
        )
        return approved_pos.aggregate(total=Sum('quote_total'))['total'] or 0

    class Meta:
        model = Project
        fields = [
            "id",
            "project_name",
            "job_code",
            "vat_rate",
            "address",
            "created_at",
            "project_value",
            "material_estimate",
            "labour_estimate",
            "prelims_estimate",
            "estimate_profit",
            "start_date",
            "completion_date",
            "is_overdue",
            "is_completed",
            "total_po_raised",
            "proforma_nr",
            "total_unclaimed",
            "total_overspend",
            "is_user_clock_in_enabled",
        ]


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "project_name",
            "job_code",
            "vat_rate",
            "address",
            "project_value",
            "material_estimate",
            "labour_estimate",
            "prelims_estimate",
            "start_date",
            "completion_date",
            "is_completed",
        ]


class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "project_name",
            "job_code",
            "vat_rate",
            "address",
            "project_value",
            "material_estimate",
            "labour_estimate",
            "prelims_estimate",
            "start_date",
            "completion_date",
            "is_completed",
        ]


class UserAccountMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['id', 'first_name', 'last_name', 'email']

class RoleAssignmentSerializer(serializers.ModelSerializer):
    user = UserAccountMinimalSerializer(read_only=True)
    
    class Meta:
        model = RoleAssignment
        fields = ['id', 'user', 'role', 'project']


from .models import ProjectFolder, ProjectSubfolder, FolderAssignment

class FolderAssignmentSerializer(serializers.ModelSerializer):
    user = UserAccountMinimalSerializer(read_only=True)
    class Meta:
        model = FolderAssignment
        fields = ['id', 'user', 'hide_labour_target', 'is_management_assignment']

class ProjectSubfolderSerializer(serializers.ModelSerializer):
    assignments = FolderAssignmentSerializer(many=True, read_only=True)
    class Meta:
        model = ProjectSubfolder
        fields = ['id', 'name', 'project_value', 'labour_target', 'rows', 'assignments']

class ProjectFolderSerializer(serializers.ModelSerializer):
    subfolders = ProjectSubfolderSerializer(many=True, read_only=True)
    class Meta:
        model = ProjectFolder
        fields = ['id', 'name', 'is_management', 'subfolders']


from .models import ApprovalConfiguration

class ApprovalConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalConfiguration
        fields = ['id', 'action_type', 'condition_value', 'required_roles', 'role_thresholds', 'toggle_states', 'is_active']


from .models import ProformaAccess

class ProformaAccessSerializer(serializers.ModelSerializer):
    user = UserAccountMinimalSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = ProformaAccess
        fields = ['id', 'project', 'user', 'user_id', 'is_active', 'created_at']
        read_only_fields = ['project', 'created_at']

from .models import LoadingClearingAccess

class LoadingClearingAccessSerializer(serializers.ModelSerializer):
    user = UserAccountMinimalSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = LoadingClearingAccess
        fields = ['id', 'project', 'user', 'user_id', 'is_active', 'created_at']
        read_only_fields = ['project', 'created_at']

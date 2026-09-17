from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('supplier', '0001_initial'),
        ('procurement_department', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplierinvoice',
            name='po_reference',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=100,
                help_text='The PO (Quotation) reference this invoice is against, e.g. QR-2026-ABC123',
            ),
        ),
        migrations.AddField(
            model_name='supplierinvoice',
            name='call_off',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='supplier_invoices',
                to='procurement_department.orderlinecalloff',
                help_text='FK to the specific call-off this invoice covers',
            ),
        ),
        migrations.AddField(
            model_name='supplierinvoice',
            name='call_off_reference',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=100,
                help_text='Call-off reference string, e.g. CO-XXXXXX (mirrors call_off.call_off_ref)',
            ),
        ),
    ]

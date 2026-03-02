from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule


class Command(BaseCommand):
    help = 'Set up Celery Beat periodic tasks for price checking and predictions'

    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.HOURS,
        )

        task, created = PeriodicTask.objects.get_or_create(
            name='Schedule Product Checks',
            task='trackers.tasks.schedule_product_checks',
            defaults={'interval': schedule},
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created periodic task: Schedule Product Checks'))
        else:
            self.stdout.write('Periodic task already exists: Schedule Product Checks')

        pred_schedule, _ = IntervalSchedule.objects.get_or_create(
            every=6,
            period=IntervalSchedule.HOURS,
        )

        pred_task, created = PeriodicTask.objects.get_or_create(
            name='Update Predictions',
            task='trackers.tasks.update_predictions',
            defaults={'interval': pred_schedule},
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created periodic task: Update Predictions'))
        else:
            self.stdout.write('Periodic task already exists: Update Predictions')

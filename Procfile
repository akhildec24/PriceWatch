web: gunicorn pricewatch.wsgi --log-file -
worker: celery -A pricewatch worker -l info
beat: celery -A pricewatch beat -l info

.PHONY: help setup dev test clean deploy

help:
	@echo "Available commands:"
	@echo "  setup     - Initial project setup"
	@echo "  dev       - Start development server"
	@echo "  test      - Run tests"
	@echo "  clean     - Clean cache and logs"
	@echo "  deploy    - Deploy to production"

setup:
	pip install -r requirements/development.txt
	python manage.py migrate
	python manage.py collectstatic --noinput

dev:
	python manage.py runserver

test:
	pytest

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf logs/*.log

deploy:
	docker-compose -f docker-compose.prod.yml up -d --build

.PHONY: dev build migrate worker shell logs test

## Start the full dev environment (web + worker + db + redis)
dev:
	docker compose up

## Rebuild all images
build:
	docker compose build

## Run database migrations
migrate:
	docker compose run --rm web python manage.py migrate

## Open a Django shell
shell:
	docker compose run --rm web python manage.py shell

## Tail logs for all services
logs:
	docker compose logs -f

## Run the test suite
test:
	docker compose run --rm web python manage.py test

## Create a Django superuser
superuser:
	docker compose run --rm web python manage.py createsuperuser

## Stop all services and remove containers
down:
	docker compose down

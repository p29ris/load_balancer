.PHONY: all build up down clean test

all: build up

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

clean:
	docker-compose down -v
	docker system prune -f

test:
	python tests/test_load_balancer.py
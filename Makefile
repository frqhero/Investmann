update: ## Обновляет local-окружение: скачивает и пересобирает докер-образы, применяет миграции и создаёт суперпользователя
	docker compose pull --ignore-buildable
	docker compose build
	make migrate
	docker compose run --rm django ./manage.py createsuperuser --no-input; true  # ignore error if user exist
	@echo "Update done successfully."

lint: ## Проверяет линтером код в репозитории
	docker compose run -T --rm linters flake8 /src/  # flake8 src

lint_file: ## Проверяет линтером открытых в редакторе файл
	cat $1 | docker compose run -T --rm linters flake8 -

test: ## Запускает автотесты
	docker compose run --rm django pytest ./ .contrib-candidates/

makemigrations: ## Создаёт новые файлы миграций Django ORM
	docker compose run --rm django ./manage.py makemigrations

migrate: ## Применяет новые миграции Django ORM
	docker compose run --rm django ./manage.py migrate

help: ## Отображает список доступных команд и их описания
	@echo "Cписок доступных команд:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

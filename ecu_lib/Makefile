.PHONY: help install dev-install test lint format clean run demo simulate docker-build docker-run

help: ## 显示帮助信息
	@echo "ECU库管理命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装ECU库
	pip install -e .

dev-install: ## 安装开发依赖
	pip install -e ".[dev]"

test: ## 运行测试
	pytest ecu_lib/tests/ -v --cov=ecu_lib --cov-report=html --cov-report=term

test-unit: ## 运行单元测试
	pytest ecu_lib/tests/test_ecu_core.py -v

test-db: ## 运行数据库测试
	pytest ecu_lib/tests/test_database.py -v

lint: ## 代码检查
	flake8 ecu_lib/
	black --check ecu_lib/
	isort --check-only ecu_lib/

format: ## 代码格式化
	black ecu_lib/
	isort ecu_lib/

clean: ## 清理构建文件
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf data/*.db
	rm -rf logs/*.log

run: ## 运行ECU库（交互模式）
	python -m ecu_lib.main --interactive

demo: ## 运行演示
	python -m ecu_lib.main --demo

simulate: ## 运行模拟
	python -m ecu_lib.main --simulate basic_test

simulate-stress: ## 运行压力测试模拟
	python -m ecu_lib.main --simulate stress_test

docker-build: ## 构建Docker镜像
	docker build -t ecu-library:latest .

docker-run: ## 运行Docker容器
	docker run -it --rm \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/logs:/app/logs \
		ecu-library:latest

docker-compose-up: ## 启动Docker Compose
	docker-compose up -d

docker-compose-down: ## 停止Docker Compose
	docker-compose down

docker-compose-logs: ## 查看Docker Compose日志
	docker-compose logs -f

create-docs: ## 创建文档
	pdoc --html ecu_lib --output-dir docs

package: ## 创建发布包
	python setup.py sdist bdist_wheel

publish-test: ## 发布到测试PyPI
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*

publish: ## 发布到PyPI
	twine upload dist/*

requirements: ## 生成requirements.txt
	pip freeze > requirements.txt
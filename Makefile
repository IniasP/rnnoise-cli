PYTHON = python3

.PHONY: help init clean build

help:
	@echo "*-----------------------*"
	@echo "| rnnoise-cli make help |"
	@echo "*-----------------------*"
	@echo
	@echo "init:      install requirements"
	@echo "build:     build the package"
	@echo "clean:     clean previously built package files"

init:
	pip install -r requirements.txt

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf src/rnnoise_cli.egg-info/

build: clean
	${PYTHON} -m build

PYTHON = python3

.PHONY: help init clean build test intall

help:
	@echo "*-----------------------*"
	@echo "| rnnoise-cli make help |"
	@echo "*-----------------------*"
	@echo
	@echo "init:      install requirements"
	@echo "test:      runs unit tests, will run 'install' first"
	@echo "install:   install the package (installs locally without building)"
	@echo "build:     build the package (builds distribution archives)"
	@echo "clean:     clean previously built package files"

init:
	${PYTHON} -m pip install -r requirements.txt

install:
	${PYTHON} -m pip install .

test: install
	${PYTHON} -m unittest -v

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf src/rnnoise_cli.egg-info/

build: clean
	${PYTHON} -m build

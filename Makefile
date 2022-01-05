PYTHON = python3

.PHONY: help init clean build test intall completion bash_completion zsh_completion fish_completion

help:
	@echo "*-----------------------*"
	@echo "| rnnoise-cli make help |"
	@echo "*-----------------------*"
	@echo
	@echo "init:             install requirements"
	@echo "test:             runs unit tests, will run 'install' first"
	@echo "install:          install the package (installs locally without building distribution archives)"
	@echo "build:            build the package (builds distribution archives)"
	@echo "clean:            clean previously built package files"
	@echo "completion:       generate all tab-completion files"
	@echo "bash_completion:  generate tab-completion file to be sourced by bash"
	@echo "zsh_completion:   generate tab-completion file to be sourced by zsh"
	@echo "fish_completion:  generate tab-completion file to be sourced by fish"

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

bash_completion:
	_RNNOISE_COMPLETE=bash_source rnnoise > ./completion.sh

zsh_completion:
	_RNNOISE_COMPLETE=zsh_source rnnoise > ./completion.zsh

fish_completion:
	_RNNOISE_COMPLETE=fish_source rnnoise > ./completion.fish

completion: bash_completion zsh_completion fish_completion

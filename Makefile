.PHONY: test test-unit test-browser

test: test-unit test-browser

test-unit:
	python3 -m unittest discover -s tests -t .

test-browser: tests/browser/node_modules
	tests/browser/node_modules/.bin/playwright test -c tests/browser

tests/browser/node_modules: tests/browser/package.json
	npm install --prefix tests/browser --no-audit --no-fund --silent

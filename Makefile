.PHONY: test test-unit test-browser

test: test-unit test-browser

test-unit:
	python3 -m unittest discover -s tests -t .

test-browser:
	npx --no-install playwright test -c tests/browser

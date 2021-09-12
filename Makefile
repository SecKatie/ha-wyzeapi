

.PHONY: create-test-env
create-test-env:
	scripts/test-setup.sh

.PHONY: test
test:
	scripts/test.sh

.PHONY: clean
clean:
	rm -rf .test
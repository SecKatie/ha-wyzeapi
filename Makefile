# SPDX-FileCopyrightText: 2021 Joshua Mulliken <joshua@mulliken.net>
#
# SPDX-License-Identifier: Apache-2.0

.PHONY: create-test-env
create-test-env:
	scripts/test-setup.sh

.PHONY: test
test:
	scripts/test.sh

.PHONY: clean
clean:
	rm -rf .test
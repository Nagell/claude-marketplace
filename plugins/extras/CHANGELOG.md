# Changelog

## [3.2.0](https://github.com/Nagell/claude-marketplace/compare/extras-v3.1.0...extras-v3.2.0) (2026-11-23)


### Features

* **extras:** add PR_AUTHOR_NOTE switch for the author's note ([1d11b57](https://github.com/Nagell/claude-marketplace/commit/1d11b575ead445d6cdecbbd2f06fc93695d84d83))
* **extras:** add PR_AUTHOR_NOTE switch for the author's note question ([c203f79](https://github.com/Nagell/claude-marketplace/commit/c203f796f6a629d84e6eff99827606b4d6e92b2e))

## [3.1.0](https://github.com/Nagell/claude-marketplace/compare/extras-v3.0.1...extras-v3.1.0) (2026-11-21)


### Features

* **extras:** add BROWSER_SCALE for HiDPI screens under WSLg ([22812ff](https://github.com/Nagell/claude-marketplace/commit/22812fff55f208b0b1e31ad517fab4672213ced7))


### Bug Fixes

* **extras:** sandbox browser sessions and quote stored logins ([e1e50be](https://github.com/Nagell/claude-marketplace/commit/e1e50be77b53a3163654b7935d587e13d2714ae2))
* **extras:** sandbox browser sessions and quote stored logins ([992289b](https://github.com/Nagell/claude-marketplace/commit/992289b81eae20a369f17c924c17efb264a9c9b8))

## [3.0.1](https://github.com/Nagell/claude-marketplace/compare/extras-v3.0.0...extras-v3.0.1) (2026-11-21)


### Documentation

* format plugin READMEs like the root README ([5d71ac1](https://github.com/Nagell/claude-marketplace/commit/5d71ac19160424d80be2977e5a8ccb76c516800f))
* format plugin READMEs like the root README ([733529e](https://github.com/Nagell/claude-marketplace/commit/733529e6b6d7c38abaf3b3fbac4aaf67eef0ca6f))

## [3.0.0](https://github.com/Nagell/claude-marketplace/compare/extras-v2.0.0...extras-v3.0.0) (2026-11-21)


### ⚠ BREAKING CHANGES

* /base:setup-token-savings is now /extras:setup-token-savings.
* the plugins install as base@dawidnitka and extras@dawidnitka; slash commands change from /base-setup: to /base:. Uninstall base-setup and dev-extras, then install the new names.

### Features

* move setup-token-savings into the extras plugin ([1930e69](https://github.com/Nagell/claude-marketplace/commit/1930e697644eeb5f68bc8b18408c20316bdc8862))
* move the browser skill into the extras plugin ([aaa5b2c](https://github.com/Nagell/claude-marketplace/commit/aaa5b2c244badd4daf63ac55cf9bbbd1b5acef24))
* rename base-setup to base and dev-extras to extras ([8ac9b24](https://github.com/Nagell/claude-marketplace/commit/8ac9b24ef7fe40b9d3265ac4a1d26c7c6b4c84c8))

## [2.0.0](https://github.com/Nagell/claude-marketplace/compare/dev-extras-v1.1.0...dev-extras-v2.0.0) (2026-11-21)


### ⚠ BREAKING CHANGES

* **dev-extras:** start-chrome-debug and the bundled chrome-devtools MCP server are gone; the browser plugin replaces them.

### Features

* add browser and review plugins, retire start-chrome-debug ([95f197d](https://github.com/Nagell/claude-marketplace/commit/95f197dd0869fabb24046090f5940dfbd722d0d1))
* **dev-extras:** remove start-chrome-debug and its chrome-devtools MCP ([21cf875](https://github.com/Nagell/claude-marketplace/commit/21cf87561f968c96157f643239e4d7b718231f7b))

## [1.1.0](https://github.com/Nagell/claude-marketplace/compare/dev-extras-v1.0.0...dev-extras-v1.1.0) (2026-09-30)


### Features

* **dev-extras:** describe the branch end state in PR/MR refreshes ([082e325](https://github.com/Nagell/claude-marketplace/commit/082e325569ef412f47db69947044582743171761))
* **dev-extras:** describe the branch end state in PR/MR refreshes ([75dcb5e](https://github.com/Nagell/claude-marketplace/commit/75dcb5ef2dfea3572e73af3ebdf95fb5ca116da8))

## [1.0.0](https://github.com/Nagell/claude-marketplace/compare/dev-extras-v0.2.0...dev-extras-v1.0.0) (2026-09-25)


### ⚠ BREAKING CHANGES

* pr-descriptions is no longer shipped with base-setup; install dev-extras to keep it.

### Features

* **dev-extras:** add open-pr skill and PR/MR description refresh hook ([d715a39](https://github.com/Nagell/claude-marketplace/commit/d715a39f27a0d24c892b2e539f49c142790dd629))
* move pr-descriptions skill from base-setup to dev-extras ([9852558](https://github.com/Nagell/claude-marketplace/commit/9852558ba17438e53d01f0f0d77c6f54817a8ee1))

## [0.2.0](https://github.com/Nagell/claude-marketplace/compare/dev-extras-v0.1.0...dev-extras-v0.2.0) (2026-09-23)


### Features

* split skill-creator and chrome debugging into dev-extras ([416c75c](https://github.com/Nagell/claude-marketplace/commit/416c75c69ac544cb4f1b6cf94e784a59eaad3231))
* split skill-creator and chrome debugging into dev-extras ([d2f71d9](https://github.com/Nagell/claude-marketplace/commit/d2f71d9234e55bfe9186e53603b091f6a26790ff))


### Bug Fixes

* **dev-extras:** ship chrome-devtools MCP config ([e14fc6c](https://github.com/Nagell/claude-marketplace/commit/e14fc6c456275174ae7242ec25bce2259047e9c4))

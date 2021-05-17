---
name: Bug report
about: Create a report to help us improve
title: "[Bug] <short description of issue>"
labels: bug
assignees: JoshuaMulliken

---

**Describe the bug**
<!-- A clear and concise description of what the bug is. -->

**To Reproduce**
Steps to reproduce the behavior:

1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
<!-- A clear and concise description of what you expected to happen. -->

**System configuration**
System: <!-- Docker, HASS.IO, Bare Metal -->
HA Version: <!-- v0.103.0 -->
WyzeApi Version: <!-- v0.4.0 -->

**configuration.yaml**
<!-- The config you are using to enable wyzeapi -->

```yaml
<YOUR CONFIG HERE>
```

**home-assistant.log**
<!--
Ensure that your logger is set up by adding this to your configuration.yaml
logger:
  default: warning
  logs:
    custom_components.wyzeapi: debug

For additional information see the readme: https://github.com/JoshuaMulliken/ha-wyzeapi#reporting-an-issue
-->

```
<PUT YOUR LOG HERE>
```

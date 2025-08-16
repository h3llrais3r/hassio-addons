# AdGuardHome Sync

Synchronize your main AdGuard Home configuration to one or more replica instances.

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg

This add-on uses [bakito/adguardhome-sync](https://github.com/bakito/adguardhome-sync).

## Features

- Run once or on a cron schedule
- Configure one or more replicate instances
- Embedded web/API UI

## Installation

1. Add this repository to Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Install **AdGuardHome Sync**
3. Configure origin/replica instances in add-on options
4. Start the add-on

## Configuration Example

```yaml
cron: "*/5 * * * *"
run_on_start: true
continue_on_error: false
origin_url: http://192.168.0.2:3000
origin_username: username
origin_password: password
replicas:
  - url: http://192.168.0.3:3000
    username: username
    password: password
api:
  port: 8080
```

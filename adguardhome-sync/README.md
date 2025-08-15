# AdGuardHome Sync

This add-on packages [bakito/adguardhome-sync](https://github.com/bakito/adguardhome-sync) to replicate AdGuard Home configuration from an origin instance to one or more replica instances.

## Features

- Run once or on a cron schedule
- Configure one or more replicate instances
- Optional embedded web/API UI

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

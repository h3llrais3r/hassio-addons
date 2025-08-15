# Home Assistant Add-on: AdGuardHome Sync

## Installation

- Navigate in your Home Assistant frontend to **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add the following repository:
  ```
  https://github.com/h3llrais3r/hassio-addons
  ```
- Find the "AdGuardHome Sync" add-on and click it.
- Click on the "INSTALL" button.

## Configuration

Example Add-on configuration:

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

| Option              | Description                                                 |
| ------------------- | ----------------------------------------------------------- |
| `cron`              | CRON expression for periodic sync. Leave empty to run once. |
| `run_on_start`      | Run synchronization immediately when add-on starts.         |
| `continue_on_error` | Continue synchronization on single errors, but log it.      |
| `origin_url`        | URL of the origin AdGuard Home instance.                    |
| `origin_username`   | (Optional) Login username for origin.                       |
| `origin_password`   | (Optional) Login password for origin.                       |
| `replicas`          | List of replicas with `url`, `username`, and `password`.    |

## API/UI

Accessible on port `8080` by default (no built-in auth).

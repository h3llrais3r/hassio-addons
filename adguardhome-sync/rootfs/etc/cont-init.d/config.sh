#!/usr/bin/with-contenv bashio
# Generate or update the adguardhome_sync.yaml config file from HA add-on settings

CONFIG_FILE="${CONFIG_FILE:-/etc/adguardhome_sync/adguardhome_sync.yaml}"

# Ensure the folder exists
mkdir -p "$(dirname "$CONFIG_FILE")"

# Create default config if missing
if [ ! -f "$CONFIG_FILE" ]; then
    bashio::log.info "Creating default configuration file..."
    cat > "$CONFIG_FILE" <<EOF
cron: "*/5 * * * *"
runOnStart: true
continueOnError: false
origin:
  url: ""
  username: ""
  password: ""
replicas: []
api:
  port: 8080
features:
  generalSettings: true
  queryLogConfig: true
  statsConfig: true
  clientSettings: true
  services: true
  filters: true
  dhcp:
    serverConfig: true
    staticLeases: true
  dns:
    serverConfig: true
    accessLists: true
    rewrites: true
EOF
fi

bashio::log.info "Updating configuration file from addon config..."

# Update cron
yq -i ".cron = \"$(bashio::config 'cron')\"" "$CONFIG_FILE"

# Update runOnStart
yq -i ".runOnStart = $(bashio::config 'run_on_start')" "$CONFIG_FILE"

# Update continueOnError
yq -i ".continueOnError = $(bashio::config 'continue_on_error')" "$CONFIG_FILE"

# Update origin
yq -i ".origin.url = \"$(bashio::config 'origin_url')\"" "$CONFIG_FILE"
yq -i ".origin.username = \"$(bashio::config 'origin_username')\"" "$CONFIG_FILE"
yq -i ".origin.password = \"$(bashio::config 'origin_password')\"" "$CONFIG_FILE"

# Update replicas
yq -i ".replicas = []" "$CONFIG_FILE"
replicas_count=$(bashio::config 'replicas | length')
for i in $(seq 0 $((replicas_count - 1))); do
  url=$(bashio::config "replicas[$i].url")
  username=$(bashio::config "replicas[$i].username")
  password=$(bashio::config "replicas[$i].password")

  # Append replica entry
  yq -i ".replicas += [{\"url\": \"$url\"}]" "$CONFIG_FILE"
  [ -n "$username" ] && yq -i ".replicas[$i].username = \"$username\"" "$CONFIG_FILE"
  [ -n "$password" ] && yq -i ".replicas[$i].password = \"$password\"" "$CONFIG_FILE"
done

# Update API port
API_PORT=$(bashio::addon.port 8080)
yq -i ".api.port = $API_PORT" "$CONFIG_FILE"

bashio::log.info "Configuration file generated at $CONFIG_FILE"

# Debug configuration file content (set to true to log the generated configuration file)
DEBUG=false
if [ "$DEBUG" = true ]; then
    bashio::log.info ">>>"
    while IFS= read -r line; do
        bashio::log.info "$line"
    done < "$CONFIG_FILE"
    bashio::log.info "<<<"
fi
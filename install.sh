#!/bin/bash

# отсюда берем значения
if [ -f ./config/default.env ]; then
    source ./config/default.env
fi

echo " "
echo "╔═══════════════════════════════════════════════════════════════════════════╗"
echo "║                                  WELCOME                                  ║"
echo "║                      PT Sandbox Telegram Checking Bot                     ║"
echo "║                          by @github.com/kaifuss/                          ║"
echo "╚═══════════════════════════════════════════════════════════════════════════╝"

echo " "
echo "Before running an application you must set up it."
echo "Here is the description of its parameters:"
echo " "
echo "═════════════════════════════════════════════════════════════════════════════"
echo "TG_BOT_TOKEN: Access token to your Telegram-bot, that you got from BotFather."
echo "FIRST_BOT_ADMIN_ID: TG ID of main administrator of the bot, mostly - your ID."
echo "PTSB_ROOT_ADDR: Web address of PT Sandbox (without https://), (FQDN or IP)."
echo "PTSB_TOKEN: Access token to PT Sandbox for sending objects to check via API."
echo "VERIFY_SSL_CONNECTIONS: Check SSL connections while sending api requests to PT Sandbox (0 - no / 1 - yes)."
echo "═════════════════════════════════════════════════════════════════════════════"
echo " "

input_with_default() {
  local var_name=$1
  local default_value=$2
  local input
  local escaped_default_value

  escaped_default_value=$(printf '%q' "$default_value")

  read -p "Input value for parameter ${var_name} (current: ${escaped_default_value}): " input
  if [[ $input =~ [^a-zA-Z0-9_] ]]; then
    export $var_name="'${input:-$default_value}'"
  else
    export $var_name=${input:-$default_value}
  fi
}

input_with_default "TG_BOT_TOKEN" "$TG_BOT_TOKEN"
input_with_default "FIRST_BOT_ADMIN_ID" "$FIRST_BOT_ADMIN_ID"
input_with_default "PTSB_ROOT_ADDR" "$PTSB_ROOT_ADDR"
input_with_default "PTSB_TOKEN" "$PTSB_TOKEN"
input_with_default "VERIFY_SSL_CONNECTIONS" "$VERIFY_SSL_CONNECTIONS"

cat << EOF > ./config/default.env
TG_BOT_TOKEN=${TG_BOT_TOKEN}
FIRST_BOT_ADMIN_ID=${FIRST_BOT_ADMIN_ID}
PTSB_ROOT_ADDR=${PTSB_ROOT_ADDR}
PTSB_TOKEN=${PTSB_TOKEN}
VERIFY_SSL_CONNECTIONS=${VERIFY_SSL_CONNECTIONS}
EOF

echo " "
echo "═════════════════════════════════════════════════════════════════════════════"
echo " "

if command -v docker-compose &> /dev/null && docker-compose --version &> /dev/null; then
    compose_cmd="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    compose_cmd="docker compose"
else
    echo "Error: commands 'docker-compose' either 'docker compose' were not found. Please, install 'docker' & 'docker-compose' first."
    exit 1
fi

builder_dir="./builder"

if docker images | grep -q "ptsb-checkbot"; then
    read -p "Image of 'ptsb-checkbot' already exists. Do you want to update parameters of application or fully rebuild? (update/rebuild): " choice
    case $choice in
        update)
            $compose_cmd -f "$builder_dir/docker-compose.yaml" down
            $compose_cmd -f "$builder_dir/docker-compose.yaml" up -d
            ;;
        rebuild)
            # replacing db file with a shapshot
            if [ "$1" == "--backup_db=true" ]; then
                if [ ! -f ./ptsb-checkbot/database/kernel_base.db ]; then
                    echo "Backup file was not found! Container will run with the old db parameters."
                    $compose_cmd -f "$builder_dir/docker-compose.yaml" down
                else
                    $compose_cmd -f "$builder_dir/docker-compose.yaml" down -v
                fi
            else
                $compose_cmd -f "$builder_dir/docker-compose.yaml" down
            fi
            $compose_cmd -f "$builder_dir/docker-compose.yaml" up --build -d
            ;;
        *)
            echo "Incorrect input. Please, input 'update' or 'rebuild'."
            ;;
    esac
else
    $compose_cmd -f "$builder_dir/docker-compose.yaml" up -d
fi
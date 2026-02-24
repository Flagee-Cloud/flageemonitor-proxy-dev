#!/bin/bash

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

json_escape() {
  printf "%s" "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g; s/\n/\\n/g'
}

timezone=""
timezone_file=""
localtime_target=""
timedatectl_timezone=""
network_time_on=""
ntp_synchronized=""
rtc_local_tz=""
timesyncd_active=""
timesyncd_status=""
timesyncd_server=""
timesyncd_ntp_config=""
ntpdate_path=""
adjtime_mode=""

if command -v timedatectl >/dev/null 2>&1; then
  td_out="$(timedatectl 2>/dev/null)"
  timedatectl_timezone="$(printf "%s\n" "$td_out" | awk -F': *' '/Time zone:/{print $2}' | awk '{print $1}')"
  network_time_on="$(printf "%s\n" "$td_out" | awk -F': *' '/Network time on:/{print $2}' | head -n1)"
  if [ -z "$network_time_on" ]; then
    network_time_on="$(printf "%s\n" "$td_out" | awk -F': *' '/NTP service:/{print $2}' | head -n1)"
  fi
  ntp_synchronized="$(printf "%s\n" "$td_out" | awk -F': *' '/NTP synchronized:/{print $2}' | head -n1)"
  if [ -z "$ntp_synchronized" ]; then
    ntp_synchronized="$(printf "%s\n" "$td_out" | awk -F': *' '/System clock synchronized:/{print $2}' | head -n1)"
  fi
  rtc_local_tz="$(printf "%s\n" "$td_out" | awk -F': *' '/RTC in local TZ:/{print $2}' | head -n1)"
fi

if [ -n "$network_time_on" ]; then
  case "$(printf "%s" "$network_time_on" | tr '[:upper:]' '[:lower:]')" in
    yes|active)
      network_time_on="yes"
      ;;
    no|inactive|disabled)
      network_time_on="no"
      ;;
  esac
fi

if [ -f /etc/adjtime ]; then
  adjtime_mode="$(tail -n1 /etc/adjtime 2>/dev/null | tr -d '[:space:]')"
  if [ "$adjtime_mode" = "UTC" ]; then
    rtc_local_tz="no"
  elif [ "$adjtime_mode" = "LOCAL" ]; then
    rtc_local_tz="yes"
  fi
fi

if [ -f /etc/timezone ]; then
  timezone_file="$(head -n1 /etc/timezone 2>/dev/null)"
fi

localtime_target="$(readlink -f /etc/localtime 2>/dev/null)"

if command -v systemctl >/dev/null 2>&1; then
  timesyncd_active="$(systemctl is-active systemd-timesyncd 2>/dev/null)"
  status_out="$(systemctl status systemd-timesyncd 2>/dev/null)"
  timesyncd_status="$(printf "%s\n" "$status_out" | awk -F': *' '/Status:/{print $2}' | head -n1 | sed 's/^"//; s/"$//')"
  timesyncd_server="$(printf "%s\n" "$status_out" | awk -F'time server ' '/time server/{print $2}' | head -n1 | sed 's/[\".]$//')"
fi

if [ -f /etc/systemd/timesyncd.conf ]; then
  timesyncd_ntp_config="$(grep -E '^NTP=' /etc/systemd/timesyncd.conf 2>/dev/null | head -n1 | cut -d= -f2)"
fi

if command -v ntpdate >/dev/null 2>&1; then
  ntpdate_path="$(command -v ntpdate 2>/dev/null)"
elif [ -x /usr/sbin/ntpdate ]; then
  ntpdate_path="/usr/sbin/ntpdate"
fi

timezone="${timedatectl_timezone:-$timezone_file}"
if [ -n "$timesyncd_status" ] && printf "%s" "$timesyncd_status" | grep -qi "Synchronized to time server"; then
  ntp_synchronized="yes"
elif [ -n "$timesyncd_status" ] && printf "%s" "$timesyncd_status" | grep -qi "Initial synchronization to time server"; then
  ntp_synchronized="yes"
fi

if [ -n "$ntp_synchronized" ]; then
  case "$(printf "%s" "$ntp_synchronized" | tr '[:upper:]' '[:lower:]')" in
    yes|active|synchronized)
      ntp_synchronized="yes"
      ;;
    no|inactive|unsynchronized)
      ntp_synchronized="no"
      ;;
  esac
fi

if [ -n "$timesyncd_active" ]; then
  case "$(printf "%s" "$timesyncd_active" | tr '[:upper:]' '[:lower:]')" in
    active)
      timesyncd_active="yes"
      ;;
    inactive|failed|deactivating)
      timesyncd_active="no"
      ;;
  esac
fi

printf "{"
printf "\"timezone\":\"%s\"," "$(json_escape "$timezone")"
printf "\"timezone_file\":\"%s\"," "$(json_escape "$timezone_file")"
printf "\"localtime_target\":\"%s\"," "$(json_escape "$localtime_target")"
printf "\"timedatectl_timezone\":\"%s\"," "$(json_escape "$timedatectl_timezone")"
printf "\"network_time_on\":\"%s\"," "$(json_escape "$network_time_on")"
printf "\"ntp_synchronized\":\"%s\"," "$(json_escape "$ntp_synchronized")"
printf "\"rtc_in_local_tz\":\"%s\"," "$(json_escape "$rtc_local_tz")"
printf "\"timesyncd_active\":\"%s\"," "$(json_escape "$timesyncd_active")"
printf "\"timesyncd_status\":\"%s\"," "$(json_escape "$timesyncd_status")"
printf "\"timesyncd_server\":\"%s\"," "$(json_escape "$timesyncd_server")"
printf "\"timesyncd_ntp_config\":\"%s\"," "$(json_escape "$timesyncd_ntp_config")"
printf "\"ntpdate_path\":\"%s\"" "$(json_escape "$ntpdate_path")"
printf "}\n"

"""Constants for the Brightwheel integration."""

DOMAIN = "brightwheel"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_AUTH_COOKIE = "auth_cookie"
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes
ACTIVITY_TYPES = {
    "ac_nap": "Nap",
    "ac_potty": "Diaper",
    "ac_food": "Food",
    "ac_checkin": "Check-in",
    "ac_photo": "Photo",
    "ac_video": "Video",
    "ac_kudo": "Kudos",
}

"""Config flow for the Reolink camera component."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientResponseError, InvalidURL
from aiohttp.web import Request
import async_timeout
from reolink_aio.exceptions import ApiError, CredentialsInvalidError, ReolinkError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp, webhook
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

<<<<<<< HEAD
from .const import CONF_PROTOCOL, CONF_USE_HTTPS, DOMAIN
from .exceptions import ReolinkException, ReolinkWebhookException, UserNotAdmin
=======
from .const import (
    CONF_ONVIF_EVENTS_REVERSE_PROXY,
    CONF_PROTOCOL,
    CONF_USE_HTTPS,
    DOMAIN,
)
from .exceptions import ReolinkException, ReolinkWebhookException, UserNotAdmin
>>>>>>> 94dcb8f408 (support onvif events reverse proxy)
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)

DEFAULT_PROTOCOL = "rtsp"
DEFAULT_ONVIF_EVENTS_REVERSE_PROXY = ""
DEFAULT_OPTIONS = {
    CONF_PROTOCOL: DEFAULT_PROTOCOL,
    CONF_ONVIF_EVENTS_REVERSE_PROXY: DEFAULT_ONVIF_EVENTS_REVERSE_PROXY,
}

WEBHOOK_REACHABILITY_TEST_TIMEOUT = 10


class ReolinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Reolink options."""

    def __init__(self, config_entry) -> None:
        """Initialize ReolinkOptionsFlowHandler."""
        self.config_options = config_entry.options
        self.protocol = self.config_options[CONF_PROTOCOL]
        self.webhook_reverse_proxy = self.config_options.get(
            CONF_ONVIF_EVENTS_REVERSE_PROXY
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Reolink options."""
        errors = {}
        placeholders = {}
        if user_input is not None:
            reverse_proxy = user_input.get(CONF_ONVIF_EVENTS_REVERSE_PROXY)
            # Only perform the webhook test if a new reverse proxy is configured
            if reverse_proxy and reverse_proxy != self.config_options.get(
                CONF_ONVIF_EVENTS_REVERSE_PROXY
            ):
                try:
                    webhook_reachable = await self.check_webhook_reachability(
                        reverse_proxy
                    )
                    if not webhook_reachable:
                        errors[
                            CONF_ONVIF_EVENTS_REVERSE_PROXY
                        ] = "webhook_test_unreachable"
                except asyncio.TimeoutError:
                    errors[CONF_ONVIF_EVENTS_REVERSE_PROXY] = "webhook_test_timeout"
                except InvalidURL:
                    errors[CONF_ONVIF_EVENTS_REVERSE_PROXY] = "webhook_test_invalid_url"
                except ClientResponseError as err:
                    errors[
                        CONF_ONVIF_EVENTS_REVERSE_PROXY
                    ] = "webhook_test_error_response"
                    placeholders["response_code"] = str(err.status)

            if not errors:
                return self.async_create_entry(data=user_input)

            self.protocol = user_input[CONF_PROTOCOL]
            self.webhook_reverse_proxy = reverse_proxy

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROTOCOL, default=self.protocol): vol.In(
                        ["rtsp", "rtmp", "flv"]
                    ),
                    vol.Optional(
                        CONF_ONVIF_EVENTS_REVERSE_PROXY,
                        description={"suggested_value": self.webhook_reverse_proxy},
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def check_webhook_reachability(self, proxy_addr: str) -> bool:
        """Test whether the webhook is reachable via the reverse proxy."""
        webhook_id = webhook.async_generate_id()
        webhook_reachable = False

        async def handle_webhook(
            hass: HomeAssistant, webhook_id: str, request: Request
        ) -> None:
            data = await request.text()
            if webhook_id == data:
                nonlocal webhook_reachable
                webhook_reachable = True

        webhook.async_register(
            self.hass, DOMAIN, "Reolink Webhook Test", webhook_id, handle_webhook
        )

        path = webhook.async_generate_path(webhook_id)
        url = f"{proxy_addr}{path}"
        try:
            async with async_timeout.timeout(WEBHOOK_REACHABILITY_TEST_TIMEOUT):
                await async_get_clientsession(self.hass).post(
                    url, data=webhook_id, raise_for_status=True
                )
                return webhook_reachable
        finally:
            webhook.async_unregister(self.hass, webhook_id)


class ReolinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reolink device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host: str | None = None
        self._username: str = "admin"
        self._password: str | None = None
        self._reauth: bool = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ReolinkOptionsFlowHandler:
        """Options callback for Reolink."""
        return ReolinkOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an authentication error or no admin privileges."""
        self._host = entry_data[CONF_HOST]
        self._username = entry_data[CONF_USERNAME]
        self._password = entry_data[CONF_PASSWORD]
        self._reauth = True
        self.context["title_placeholders"]["ip_address"] = entry_data[CONF_HOST]
        self.context["title_placeholders"]["hostname"] = self.context[
            "title_placeholders"
        ]["name"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        mac_address = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        self.context["title_placeholders"] = {
            "ip_address": discovery_info.ip,
            "hostname": discovery_info.hostname,
        }

        self._host = discovery_info.ip
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        placeholders = {
            "error": "",
            "troubleshooting_link": "https://www.home-assistant.io/integrations/reolink/#troubleshooting",
        }

        if user_input is not None:
            if CONF_HOST not in user_input:
                user_input[CONF_HOST] = self._host

            host = ReolinkHost(self.hass, user_input, DEFAULT_OPTIONS)
            try:
                await host.async_init()
            except UserNotAdmin:
                errors[CONF_USERNAME] = "not_admin"
                placeholders["username"] = host.api.username
                placeholders["userlevel"] = host.api.user_level
            except CredentialsInvalidError:
                errors[CONF_HOST] = "invalid_auth"
            except ApiError as err:
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "api_error"
            except ReolinkWebhookException as err:
                placeholders["error"] = str(err)
                placeholders[
                    "more_info"
                ] = "https://www.home-assistant.io/more-info/no-url-available/#configuring-the-instance-url"
                errors["base"] = "webhook_exception"
            except (ReolinkError, ReolinkException) as err:
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "unknown"
            finally:
                await host.stop()

            if not errors:
                user_input[CONF_PORT] = host.api.port
                user_input[CONF_USE_HTTPS] = host.api.use_https

                existing_entry = await self.async_set_unique_id(
                    host.unique_id, raise_on_progress=False
                )
                if existing_entry and self._reauth:
                    if self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    ):
                        await self.hass.config_entries.async_reload(
                            existing_entry.entry_id
                        )
                    return self.async_abort(reason="reauth_successful")
                self._abort_if_unique_id_configured(updates=user_input)

                return self.async_create_entry(
                    title=str(host.api.nvr_name),
                    data=user_input,
                    options=DEFAULT_OPTIONS,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=self._username): str,
                vol.Required(CONF_PASSWORD, default=self._password): str,
            }
        )
        if self._host is None or errors:
            data_schema = data_schema.extend(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                }
            )
        if errors:
            data_schema = data_schema.extend(
                {
                    vol.Optional(CONF_PORT): cv.positive_int,
                    vol.Required(CONF_USE_HTTPS, default=False): bool,
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=placeholders,
        )

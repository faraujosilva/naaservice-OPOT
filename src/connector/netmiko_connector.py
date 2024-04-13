import logging
from netmiko import ConnectHandler
from netmiko.snmp_autodetect import SNMPDetect
from netmiko.ssh_autodetect import SSHDetect
from netmiko.exceptions import (
    NetMikoTimeoutException,
    NetMikoAuthenticationException,
    NetMikoTimeoutException,
)
from src.device.interface import IDevice
from src.connector.interface import IConnector
from src.models.models import Command, ConnectorOutput
from src.utils.utils import netmiko_commandError

# Set up logging to only display critical errors for Paramiko and Netmiko
logging.getLogger("paramiko").setLevel(logging.CRITICAL)  # No tracebacks for Paramiko
logging.getLogger("netmiko").setLevel(logging.CRITICAL)  # No tracebacks for Netmiko

GLOBAL_DRIVER_CACHING = {}


class NetmikoConnector(IConnector):
    """Implementation of IConnector using Netmiko as the underlying library"""
    def __try_ssh_autodetect(self, ssh_detect: SSHDetect):
        best_match = 'cisco_ios'
        try:
            best_match = ssh_detect.autodetect()
        except NetMikoTimeoutException:
            return ConnectorOutput(error="Timeout in autodetecting device type")
        except NetMikoAuthenticationException:
            return ConnectorOutput(
                error="Authentication error in autodetecting device type"
            )
        except Exception:
            return ConnectorOutput(
                error="General error in autodetecting device type"
            )
        return best_match
            
    def run(
        self, device: IDevice, command_detail: Command, credentials: dict
    ) -> ConnectorOutput:
        """ Implementation metdod for IConnector interface"""
        if not credentials.get("username") or not credentials.get("password"):
            return ConnectorOutput(error="Username and password are required")
        net_device = {
            "device_type": "autodetect",  # or 'cisco_ios
            "host": device.get_ip(),
            "username": credentials.get("username"),
            "password": credentials.get("password"),
        }

        if GLOBAL_DRIVER_CACHING.get(device.get_ip()):
            ##print('Using cache')
            net_device["device_type"] = GLOBAL_DRIVER_CACHING[device.get_ip()]
        else:
            if credentials.get("community"):
                ##print('Discovering using SNMP')
                try:
                    snmp_detect = SNMPDetect(
                        hostname=device.get_ip(),
                        snmp_version="v2c",
                        community=credentials.get("community"),
                    )
                    best_match = snmp_detect.autodetect()
                    if best_match:
                        net_device["device_type"] = best_match
                        GLOBAL_DRIVER_CACHING[device.get_ip()] = best_match
                except Exception:
                    try:
                        detect_ssh = SSHDetect(**net_device)
                        best_match = self.__try_ssh_autodetect(detect_ssh(**net_device))
                        if best_match:
                            net_device["device_type"] = best_match
                            GLOBAL_DRIVER_CACHING[device.get_ip()] = best_match
                    except Exception:
                        return ConnectorOutput(error="Could not detect device type neither by SNMP nor SSH")
            else:
                try:
                    detect_ssh = SSHDetect(**net_device)
                    best_match = self.__try_ssh_autodetect(detect_ssh(**net_device))
                    if best_match:
                        net_device["device_type"] = best_match
                        GLOBAL_DRIVER_CACHING[device.get_ip()] = best_match
                except Exception:
                    return ConnectorOutput(error="Could not detect device type by SSH")
        try:
            with ConnectHandler(**net_device) as net_connect:
                # test if have exception connecthandler
                output = net_connect.send_command(command_detail.command).strip()
                if netmiko_commandError(output):
                    return ConnectorOutput(
                        error=f"Command: {command_detail.command} ran with error: {output}"
                    )
        except NetMikoTimeoutException:  # This is instance for paramiko errors
            return ConnectorOutput(error="Timeout in connecting to device")
        
        except NetMikoAuthenticationException: 
            return ConnectorOutput(error="Authentication error in connecting to device")

        except Exception:
            return ConnectorOutput(error="General error in connecting to device")

        return ConnectorOutput(output=output)

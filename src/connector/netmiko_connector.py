from netmiko import ConnectHandler
from netmiko.snmp_autodetect import SNMPDetect
from netmiko.ssh_autodetect import SSHDetect
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException, NetMikoTimeoutException
from src.engine.parser import Parser
from src.device.device import Device
from src.connector.interface import IConnector
from src.models.models import Command

GLOBAL_DRIVER_CACHING = {}

class NetmikoConnector(IConnector):
    def run(self, device: Device, command_detail: Command, parser: Parser, credentials: dict) -> dict:
        print(f"Running Netmiko driver for {device.ip} with command {command_detail.command}")
        net_device = {
            "device_type": 'autodetect', # or 'cisco_ios
            "host": device.ip,
            "username": credentials.get('username'),
            "password": credentials.get('password'),
        }
        
        if GLOBAL_DRIVER_CACHING.get(device.ip):
            print('Using cache')
            net_device['device_type'] = GLOBAL_DRIVER_CACHING[device.ip]
        else:
            if credentials.get('community'):
                print('Discovering using SNMP')
                try:
                    snmp_detect = SNMPDetect(hostname=device.ip, snmp_version='v2c', community=credentials.get('community'))
                    best_match = snmp_detect.autodetect()
                    if best_match:
                        net_device["device_type"] = best_match
                        GLOBAL_DRIVER_CACHING[device.ip] = best_match
                except Exception:
                    pass
            else:
                print('Discovering using SSH')
                try:
                    ssh_Detect = SSHDetect(**net_device)
                    best_match = ssh_Detect.autodetect()
                    
                    if best_match:
                        net_device["device_type"] = best_match
                        GLOBAL_DRIVER_CACHING[device.ip] = best_match
                except NetMikoTimeoutException:
                    return {
                        "error": "Timeout in autodetecting device type"
                    }
                except NetMikoAuthenticationException:
                    return {
                        "error": "Authentication error in autodetecting device type"
                    }
                except Exception:
                    return {
                        "error": "General error in autodetecting device type"
                    }
        try:
            with ConnectHandler(**net_device) as net_connect:
                output = net_connect.send_command(command_detail.command)
        except NetMikoTimeoutException:
            return {
                "error": "Timeout in connecting to device"
            }
        except NetMikoAuthenticationException:
            return {
                "error": "Authentication error in connecting to device"
            }
        except Exception:
            return {
                "error": "General error in connecting to device"
            }
                
        return {
            "output": parser.parse(output, command_detail.parse, command_detail.group)
        }
    
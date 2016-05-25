#!/usr/bin/env python

# standard library
import argparse
import sys
import time

# pip
# [sudo] pip install boto
import boto
import boto.ec2
# [sudo] pip install requests
import requests


# aws instance states
RUNNING = 16
STOPPED = 80

# HOST = 'demondice.quasisemi.com'
# if HOST[-1] != '.':
#     HOST += '.'
# INSTANCE = 'web'
# REGION = 'us-east-1'

def getZone(r53Conn, host):
    """
    return zone which might contain the specified host.
    @param host: str -- fqdn for host including terminal '.'
    @returns: boto route53 zone object.
    """
    candidates = []
    match = None
    for zone in  r53Conn.get_zones():
        if host.endswith(zone.name):
            match = zone.get_a(host)
            if match:
                # print(match.__dict__)
                print('Found record:  A {} {}'.format(host, match.resource_records))
                return zone
            candidates.append(zone)
    if not candidates:
        return None
    elif len(candidates) == 1:
        return candidates[0]
    else:
        # TODO: something more clever
        return candidates[0]

def getInstance(ec2Conn, instance):
    for instanceObj in ec2Conn.get_only_instances():
        if instanceObj.tags['Name'] == instance or instanceObj.id == instance:
            return instanceObj

def getInstanceIPAddress(ec2Conn, instance):
    instanceObj = getInstance(ec2Conn, instance)
    if instanceObj:
        return instanceObj.ip_address
    else:
        print('No instance \'{}\' could be found.'.format(instance))
        sys.exit(2)

def startInstance(ec2Conn, instance):
    instanceObj = getInstance(ec2Conn, instance)
    print('Starting {}({}).'.format(instance, instanceObj.id))
    if instanceObj.state_code == STOPPED:
        instanceObj.start()
    waitForState(instanceObj, RUNNING)

def killInstance(ec2Conn, instance):
    instanceObj = getInstance(ec2Conn, instance)
    print('Stopping {}({}).'.format(instance, instanceObj.id))
    if instanceObj.state_code == RUNNING:
        instanceObj.stop()
    waitForState(instanceObj, STOPPED)

def waitForState(instanceObj, state):
    cnt = 0
    while instanceObj.state_code != state:
        time.sleep(1)
        instanceObj.update()
        cnt +=1
        if cnt % 10 == 0:
            print('still waiting for operation on "{}" to complete'.format(instanceObj.id))

def getMyIPAddress():
    return requests.get('https://api.ipify.org').text

def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument('host', metavar='Hostname',
                help='The fully qualified domain name to be modified.')
    parser.add_argument('instance', nargs='?', default=None, metavar='Instance',
                help='Instance name or ID to act as the destination for host.  '\
                    'If instance isn\'t supplied the name is associated with  '\
                    'the machine running this script.')
    parser.add_argument('--region', '-r', default='us-east-1', metavar='region',
                help='region where the instance is running.  (us-east-1)')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--start', '-s', default=False, action='store_true',
                help='If the instance isn\'t running, start it.')
    action.add_argument('--kill', '-k', default=False, action='store_true',
                help='Don\'t do anything with route53.  Simply stop the instance.')
    return parser.parse_args()


def main():
    args = parseArgs()
    if args.host[-1] != '.':
        args.host += '.'
    if args.instance is None and (args.start or args.kill):
        print('--start or --kill require an instance.  Exiting.')
        sys.exit(3)
    match = True

    # print('({}, {})'.format(args.host, args.instance))
    r53Conn = boto.connect_route53()

    if args.instance:
        ec2Conn = boto.ec2.connect_to_region(args.region)
        if args.kill:
            killInstance(ec2Conn, args.instance)
            sys.exit(0)
        if args.start:
            startInstance(ec2Conn, args.instance)
        newIP = getInstanceIPAddress(ec2Conn, args.instance)
    else:
        print('No instance provided, looking up public IP.')
        newIP = getMyIPAddress()
    print('IP Address found: {}'.format(newIP))

    zone = getZone(r53Conn, args.host)
    if zone is None:
        print('No appropriate route53 zone could be found for {}'.format(args.host))
        sys.exit(1)
    # should have a zone and IP at this point
    if match:
        print('Updating to record:  A {} {}'.format(args.host, newIP))
        zone.update_a(args.host, newIP)
    else:
        print('Adding record:  A {} {}'.format(args.host, newIP))
        zone.add_a(args.host, newIP)

if __name__ == '__main__':
    main()

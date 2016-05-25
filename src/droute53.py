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

def getZone(r53Conn, host):
    """
    Return route53 zone which might contain the specified host.

    @param host: str -- fqdn for host including terminal '.'

    @returns: tuple of boto route53 zone object (or None) and
            resouceRecord (or None ``(zone, resource)`` or
            ``(zone, None)`` or ``(None, None)``.  If an existing
            record could be found it will be returned as the
            second element.
    """
    candidates = []
    match = None
    for zone in  r53Conn.get_zones():
        if host.endswith(zone.name):
            match = zone.get_a(host)
            if match:
                # print(match.__dict__)
                print('Found record:  A {} {}'.format(host, match.resource_records))
                return (zone, match)
            candidates.append(zone)
    if not candidates:
        return (None, None)
    elif len(candidates) == 1:
        return (candidates[0], None)
    else:
        # TODO: something more clever
        return (candidates[0], None)

def getInstance(ec2Conn, instance):
    """
    Return the boto instance object with a name or id matching instance.

    @param ec2Conn: ec2 connection object to appropriate region
    @param insance: str -- name or id of desired instance.

    @return: boto ec2.Instance object.
    """
    for instanceObj in ec2Conn.get_only_instances():
        if instanceObj.tags['Name'] == instance or instanceObj.id == instance:
            return instanceObj
    print('No instance \'{}\' could be found.'.format(instance))
    sys.exit(2)


def getInstanceIPAddress(ec2Conn, instance):
    """
    Return the public IP associated with the instance.

    @param ec2Conn: ec2 connection object to appropriate region
    @param insance: str -- name or id of desired instance.

    @return: str -- public IP address.
    """
    return  getInstance(ec2Conn, instance).ip_address

def changeState(instanceObj, fx, desiredState, opStr):
    """
    Change the state of the instance.

    @param insanceObj: ec2.Instance -- Instance to be manipulated.
    @param fx: function -- function to execute to change state.  Takes
                no argument (e.g instanceObj.stop or instanceObj.start)
    @param desiredState: int -- The state to be achieved.
    @param opStr: str -- A string to reprsnting the operation to the,
                user (e.g. 'Starting' or 'Stopping')

    @return: None
    """
    # If it is changing state wait until the operation is complete.
    waitForState(instanceObj, [RUNNING, STOPPED])
    if instanceObj.state_code != desiredState:
        try:
            ident = instanceObj.tags['Name']
        except KeyError:
            ident = 'unknown'
        print('{} {}({}).'.format(opStr, ident, instanceObj.id))
        fx()
        waitForState(instanceObj, [desiredState])

def startInstance(ec2Conn, instance):
    """
    Start the instance if stopped.  Will exit if the instance can't
    be found.

    @param ec2Conn: ec2 connection object to appropriate region
    @param insance: str -- name or id of the instance to manipulate.

    @return: None
    """
    instanceObj = getInstance(ec2Conn, instance)
    changeState(instanceObj, instanceObj.start, RUNNING, 'Starting')

def killInstance(ec2Conn, instance):
    """
    Stop the instance if running.  Will exit if the instance can't
    be found.

    @param ec2Conn: ec2 connection object to appropriate region
    @param insance: str -- name or id of instance to manipulate.

    @return: None
    """
    instanceObj = getInstance(ec2Conn, instance)
    changeState(instanceObj, instanceObj.stop, STOPPED, 'Stopping')

def waitForState(instanceObj, state):
    """
    Wait until the instance is in a desired state.  This function
    doesn't initiate any change, so if not used carefully it may wait
    forever.

    @param insanceObj: ec2.Instance -- Instance to be manipulated.
    @param state: list of int -- List of acceptable states.

    @returns: None

    """
    cnt = 0
    while instanceObj.state_code not in state:
        time.sleep(1)
        instanceObj.update()
        cnt +=1
        if cnt % 10 == 0:
            print('still waiting for operation on "{}" to complete'.format(instanceObj.id))

def getMyIPAddress():
    """
    Returns the public facing IP address of localhost.  Depending on
    network engineering there may be no way to reach localhost by
    using this address, but it will certainly be where traffic from
    localhost will appear to originate.

    @returns: str -- external ip address of localhost
    """
    return requests.get('https://api.ipify.org').text

def parseArgs():
    """
    Define and parse command line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.description = 'A small script to dynamically update route53 '\
                'with the public IP address of an EC2 instance.  It can '\
                'also be run from a host with a dynamic public IP address '\
                'to update from localhost\'s public IP address.  To run in '\
                'this mode do not include an instance name/id.'
    parser.add_argument('host', metavar='Hostname',
                help='The fully qualified domain name to be modified.')
    parser.add_argument('instance', nargs='?', default=None, metavar='Instance',
                help='Instance name or ID to act as the destination for host.  '\
                    'If instance isn\'t supplied the name is associated with  '\
                    'the public IP address of localhost.')
    parser.add_argument('--region', '-r', default='us-east-1', metavar='region',
                help='region where the instance is running.  (us-east-1)')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--start', '-s', default=False, action='store_true',
                help='If the instance isn\'t running, start it.')
    action.add_argument('--kill', '-k', default=False, action='store_true',
                help='Don\'t do anything with route53.  Simply stop the instance.')

    args =  parser.parse_args()

    # route53 requires proper fqdn with '.' termination
    if args.host[-1] != '.':
        args.host += '.'

    # trying to start or stop will no instance is probably an error
    if args.instance is None and (args.start or args.kill):
        print('--start or --kill require an instance.  Exiting.')
        sys.exit(3)
    return args


def procInstance(args):
    """
    Process instance and return the public facing IP address.
    If the --kill command line option is present this function
    will exit.  It will also exit if no matching Instance could
    be found.

    @param args: ArgParser args

    @return: str -- IP Address.
    """
    ec2Conn = boto.ec2.connect_to_region(args.region)
    if args.kill:
        killInstance(ec2Conn, args.instance)
        sys.exit(0)
    if args.start:
        startInstance(ec2Conn, args.instance)
    return getInstanceIPAddress(ec2Conn, args.instance)

def procHost(args, newIP):
    """
    Process host and update route53 records.  Will exit if no
    appropriate route53 zone could be found.

    @param args: ArgParser args

    @return: None
    """
    match = None
    r53Conn = boto.connect_route53()
    (zone, match) = getZone(r53Conn, args.host)
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

def main():
    """
    Main part of the script.
    """
    args = parseArgs()

    if args.instance:
        newIP = procInstance(args)
    else:
        print('No instance provided, looking up public IP.')
        newIP = getMyIPAddress()
    print('IP Address found: {}'.format(newIP))

    procHost(args, newIP)


if __name__ == '__main__':
    main()

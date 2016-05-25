# droute53

Dynamic DNS using route53.

Elastic IP addresses can be associated with EC2 instances and that
in combination with route53 can be used to effectively solve the
problem of attaching a name to an ephemeral resource.

However AWS charges for Elastic IP addresses associated with stopped
instances, rendering this inappropriate low budget operations or if
you have many resourced kept primarily in a stopped state.

This command line python script which should be appropriate for
use by shell scripts automates looking up an instance and updating
route53 with it's public facing IP address.

It can also be run on any node with a public facing IP address and
it can update route53 with that public facing IP address.

And just for fun it also has options to start or stop EC2 instances
by name (or id).

The script is based on boto2 so keys should be stored in a
~/.boto configuration file.
See http://boto.cloudhackers.com/en/latest/boto_config_tut.html
for all the details.

Basic usage for updating a host ``foo.example.com`` to point to
public IP address of the EC2 instance with a name of ``web``.

    $ ./droute53.py foo.example.com web
    IP Address found: 54.210.124.178
    Found record:  A foo.example.com. ['71.163.166.62']
    Updating to record:  A foo.example.com. 54.210.124.178

If there is no record for foo.example.com but there is a route53
HostedZone for ``example.com`` it will create a recored for
``foo.example.com`` in the hosted zone.  (This has not been well
tested.)

The optional parameter ``--start`` will start a stopped instance and
wait until the instance comes up before updating route53.  If the
node is already running, this option is ignored.

The optional parameter ``--kill`` will stop a running instance and
wait until the instance goes down.  With ``--kill`` the script does
no updating of route53. If the node is already stopped, this option
causes the script to silently exit.

The optional parameter ``--region`` allows the specification of the
AWS region (``us-west-1``, etc.)  route53 doesn't use it, but it is
required to find the EC2 instance.  By default the script checks
``us-east-1`` (N. Virginia).

If instead you want to update route 53 with the public IP address of
localhost, simple leave off the instance name.

    $ ./droute53.py foo.example.com
    No instance provided, looking up public IP.
    IP Address found: 72.163.166.62
    Found record:  A foo.example.com. ['54.210.124.178']
    Updating to record:  A foo.example.com. 72.163.166.62

Uses the ipify.org service (https://www.ipify.org/) to look up the
public facing IP address.  This is the IP that your traffic orginates
from when going to the Internet.  There's no guarantee the traffic
originating from the Internet when directed to that IP address
will reach localhost.  That is a question of your local network
engineering.

If you include ``--start`` or ``--kill`` the script will exit with
an error message, since those require that the script do something it
can't do since no instance has been specified. ``--region`` is silently
ignored since it doesn't change behavior.

The script has only really been tested on my rather simple route53
zone.  While I think it will work under more complicated situations,
without testing I can't be sure.

At present the script only manipulates ``A`` records though it
shouldn't be too tough to expand that to do other sorts of
DNS records.

An example using the instance id and ``--start`` option.

    $ ./droute53.py foo.example.com i-326c87a2 --start
    Starting web(i-326c87a2).
    still waiting for operation on "i-326c87a2" to complete
    still waiting for operation on "i-326c87a2" to complete
    IP Address found: 54.174.46.34
    Found record:  A foo.example.com. ['54.210.124.178']
    Updating to record:  A foo.example.com. 54.174.46.34

That's probably enough for a help file that probably nobody
else in the whole world will read.

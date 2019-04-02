# Copyright 2011-2012 James McCauley
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An L2 learning switch.

It is derived from one written live for an SDN crash course.
It is somwhat similar to NOX's pyswitch in that it installs
exact-match rules for each flow.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.util import str_to_bool
import time

log = core.getLogger()

# We don't want to flood immediately when a switch connects.
# Can be overriden on commandline.
_flood_delay = 0

class LearningSwitch (object):
  """
  The learning switch "brain" associated with a single OpenFlow switch.

  When we see a packet, we'd like to output it on a port which will
  eventually lead to the destination.  To accomplish this, we build a
  table that maps addresses to ports.

  We populate the table by observing traffic.  When we see a packet
  from some source coming from some port, we know that source is out
  that port.

  When we want to forward traffic, we look up the desintation in our
  table.  If we don't know the port, we simply send the message out
  all ports except the one it came in on.  (In the presence of loops,
  this is bad!).

  In short, our algorithm looks like this:

  For each packet from the switch:
  1) Use source address and switch port to update address/port table
  2) Is transparent = False and either Ethertype is LLDP or the packet's
     destination address is a Bridge Filtered address?
     Yes:
        2a) Drop packet -- don't forward link-local traffic (LLDP, 802.1x)
            DONE
  3) Is destination multicast?
     Yes:
        3a) Flood the packet
            DONE
  4) Port for destination address in our address/port table?
     No:
        4a) Flood the packet
            DONE
  5) Is output port the same as input port?
     Yes:
        5a) Drop packet and similar ones for a while
  6) Install flow table entry in the switch so that this
     flow goes out the appopriate port
     6a) Send the packet out appropriate port
  """
  def __init__ (self, connection, transparent):
    # Switch we'll be adding L2 learning switch capabilities to
    self.connection = connection
    self.transparent = transparent

    # Our table
    self.macToPort = {}

    # We want to hear PacketIn messages, so we listen
    # to the connection
    connection.addListeners(self)

    # We just use this to know when to log a helpful message
    self.hold_down_expired = _flood_delay == 0

    #log.debug("Initializing LearningSwitch, transparent=%s",
    #          str(self.transparent))

  def _handle_PacketIn (self, event):
    """
    Handle packet in messages from the switch to implement above algorithm.
    """

    packet = event.parsed
    if packet.type == packet.IP_TYPE:
	ip_packet = packet.payload
	ip_origen = ip_packet.scrip
	print "La IP de origen es: ", ip_origen
	print "La MAC de origen es: ", packet.arc

    def flood (message = None):
      """ Floods the packet """
      msg = of.ofp_packet_out()
      if time.time() - self.connection.connect_time >= _flood_delay:
        # Only flood if we've been connected for a little while...

        if self.hold_down_expired is False:
          # Oh yes it is!
          self.hold_down_expired = True
          log.info("%s: Flood hold-down expired -- flooding",
              dpid_to_str(event.dpid))

        if message is not None: log.debug(message)
        #log.debug("%i: flood %s -> %s", event.dpid,packet.src,packet.dst)
        # OFPP_FLOOD is optional; on some switches you may need to change
        # this to OFPP_ALL.
        msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
      else:
        pass
        #log.info("Holding down flood for %s", dpid_to_str(event.dpid))
      msg.data = event.ofp
      msg.in_port = event.port
      self.connection.send(msg)

    def drop (duration = None):
      """
      Drops this packet and optionally installs a flow to continue
      dropping similar ones for a while
      """
      if duration is not None:
        if not isinstance(duration, tuple):
          duration = (duration,duration)
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.idle_timeout = duration[0]
        msg.hard_timeout = duration[1]
        msg.buffer_id = event.ofp.buffer_id
        self.connection.send(msg)
      elif event.ofp.buffer_id is not None:
        msg = of.ofp_packet_out()
        msg.buffer_id = event.ofp.buffer_id
        msg.in_port = event.port
        self.connection.send(msg)

    self.macToPort[packet.src] = event.port # 1

    if not self.transparent: # 2
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        drop() # 2a
        return

    if packet.dst.is_multicast:
      flood() # 3a
    else:
      if packet.dst not in self.macToPort: # 4
        flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
      else:
        port = self.macToPort[packet.dst]
        if port == event.port: # 5
          # 5a
          log.warning("Same port for packet from %s -> %s on %s.%s.  Drop."
              % (packet.src, packet.dst, dpid_to_str(event.dpid), port))
          drop(10)
          return
        # 6
        log.debug("installing flow for %s.%i -> %s.%i" %
                  (packet.src, event.port, packet.dst, port))
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.idle_timeout = 10
        msg.hard_timeout = 30
        msg.actions.append(of.ofp_action_output(port = port))
        msg.data = event.ofp # 6a
        self.connection.send(msg)

mininet@192.168.56.100's password:
Welcome to Ubuntu 14.04.4 LTS (GNU/Linux 4.2.0-27-generic x86_64)

 * Documentation:  https://help.ubuntu.com/
Last login: Mon Apr  1 18:51:32 2019 from 192.168.56.1
mininet@mininet-vm:~$ cd pox
mininet@mininet-vm:~/pox$ ls
debug-pox.py  LICENSE  pox     README     tests
ext           NOTICE   pox.py  setup.cfg  tools
mininet@mininet-vm:~/pox$ cd pox
mininet@mininet-vm:~/pox/pox$ cd pox/
-bash: cd: pox/: No such file or directory
mininet@mininet-vm:~/pox/pox$ clear
mininet@mininet-vm:~/pox/pox$ ls
boot.py   datapaths     info          log        proto    tk.py
boot.pyc  forwarding    __init__.py   messenger  py.py    topology
core.py   help.py       __init__.pyc  misc       py.pyc   web
core.pyc  host_tracker  lib           openflow   samples
mininet@mininet-vm:~/pox/pox$ ./pox.py forwarding.l2_learning
-bash: ./pox.py: No such file or directory
mininet@mininet-vm:~/pox/pox$ ls
boot.py   datapaths     info          log        proto    tk.py
boot.pyc  forwarding    __init__.py   messenger  py.py    topology
core.py   help.py       __init__.pyc  misc       py.pyc   web
core.pyc  host_tracker  lib           openflow   samples
mininet@mininet-vm:~/pox/pox$ cd forwarding
mininet@mininet-vm:~/pox/pox/forwarding$ ls
hub.py        l2_flowvisor.py  l2_multi.py             l2_pairs.py
__init__.py   l2_learning.py   l2_nx.py                l3_learning.py
__init__.pyc  l2_learning.pyc  l2_nx_self_learning.py  topo_proactive.py
mininet@mininet-vm:~/pox/pox/forwarding$ cd l2_learning.py
-bash: cd: l2_learning.py: Not a directory
mininet@mininet-vm:~/pox/pox/forwarding$ ls
hub.py        l2_flowvisor.py  l2_multi.py             l2_pairs.py
__init__.py   l2_learning.py   l2_nx.py                l3_learning.py
__init__.pyc  l2_learning.pyc  l2_nx_self_learning.py  topo_proactive.py
mininet@mininet-vm:~/pox/pox/forwarding$ cd l2_learning.py
-bash: cd: l2_learning.py: Not a directory
mininet@mininet-vm:~/pox/pox/forwarding$ cd
mininet@mininet-vm:~$ cd pox
mininet@mininet-vm:~/pox$ ./pox.py forwarding.l2_learning
POX 0.2.0 (carp) / Copyright 2011-2013 James McCauley, et al.
INFO:core:POX 0.2.0 (carp) is up.
^CINFO:core:Going down...
INFO:core:Down.
mininet@mininet-vm:~/pox$ ls
debug-pox.py  LICENSE  pox     README     tests
ext           NOTICE   pox.py  setup.cfg  tools
mininet@mininet-vm:~/pox$ cd pox
mininet@mininet-vm:~/pox/pox$ cd forwarding
mininet@mininet-vm:~/pox/pox/forwarding$ nano l2_learning.py
login as: mininet
mininet@192.168.56.100's password:
Welcome to Ubuntu 14.04.4 LTS (GNU/Linux 4.2.0-27-generic x86_64)

 * Documentation:  https://help.ubuntu.com/
Last login: Mon Apr  1 18:54:07 2019 from 192.168.56.1
mininet@mininet-vm:~$ sudo mn --controller=remote,ip=127.0.0.1,port=6633
*** Creating network
*** Adding controller
Unable to contact the remote controller at 127.0.0.1:6633
*** Adding hosts:
h1 h2
*** Adding switches:
s1
*** Adding links:
(h1, s1) (h2, s1)
*** Configuring hosts
h1 h2
*** Starting controller
c0
*** Starting 1 switches
s1 ...
*** Starting CLI:
mininet> ls
*** Unknown command: ls
mininet>



class l2_learning (object):
  """
  Waits for OpenFlow switches to connect and makes them learning switches.
  """
  def __init__ (self, transparent):
    core.openflow.addListeners(self)
    self.transparent = transparent

  def _handle_ConnectionUp (self, event):
    log.debug("Connection %s" % (event.connection,))
    LearningSwitch(event.connection, self.transparent)


def launch (transparent=False, hold_down=_flood_delay):
  """
  Starts an L2 learning switch.
  """
  try:
    global _flood_delay
    _flood_delay = int(str(hold_down), 10)
    assert _flood_delay >= 0
  except:
    raise RuntimeError("Expected hold-down to be a number")

  core.registerNew(l2_learning, str_to_bool(transparent))

Synchronize clients in multi machine (server) tests
===================================================

Synchronization is useful when is started server part test which starts client 
part test on multiple hosts, then is sometimes needed to synchronize state or
data between client part tests. By this reason was created class **Barrier** and
class **Syncdata**. Both classes are placed in **autotest/client/shared**.

class Barrier
-------------

Barrier allows only state synchronization. Both clients start::

    job.barrier(host_name, tag, timeout)

Where:

:host_name: Host identifier (host_ip | host_name[#optional_tag]).
:tag: Identifier of barrier.
:timeout: Timeout for barrier.

Usage::

    b = job.barrier(ME, 'server-up', 120) # Create barrier object
    b.rendezvous(CLIENT, SERVER)          # Block test(thread) until barrier is reached
                                          # by all sides or barrier timeouted.

Where **ME** depends where is this code started. It could be CLIENT or SERVER.
The same code is started all hosts which waits for barrier.

Communication::

    MASTER                        CLIENT1         CLIENT2
    <-------------TAG C1-------------
    --------------wait-------------->
                  [...]
    <-------------TAG C2-----------------------------
    --------------wait------------------------------>
                  [...]
    --------------ping-------------->
    <-------------pong---------------
    --------------ping------------------------------>
    <-------------pong-------------------------------
            ----- BARRIER conditions MET -----
    --------------rlse-------------->
    --------------rlse------------------------------>

Master side creates socket server. Client side connects to this server and
communicate through them. During waiting, the barrier checks if all sides
which wait for barrier are alive. For the checking barrier uses ping-pong messages.

class SyncData
--------------

SyncData class allows synchronization of state and data but it not check liveness of synchronized nodes.
When one node dies after sending his data, others nodes know nothing about death of node. Information about
death is logged to log. SyncData class could be use instead class Barrier.

::
     
    SyncData(master_id, hostid, hosts, session_id, sync_server)

Where:

:master_id: master host identifier. This host has or create sync_server and others connect to them.
:hostid: host identifier.
:hosts: list of all host which should exchange data.
:session_id: session_id identifies data synchronization. Session_id must be unique.
:sync_server: If sync_server is None then master create new sync_server for synchronization.

Usage::

    from autotest.client.shared.syncdata import SyncData

    master_id = MASTER
    sync = SyncData(master_id, hostid, hosts,
                    session_id), tag))

    data = sync.sync(data, timeout, session_id) # sync could be run in different threads 
                                                # with different session_id simultaneously. 
                                                # session_id there override session_id defined in 
                                                # class definition. session_id could be None.

    data_hostid2 = data[hostid2]                # data = {hostid1: data1, hostid2: data2} 

sync return dictionary with data from all clients.

Communication::

    MASTER                                    CLIENT1         CLIENT2
    if not listen_server -> create
    
    <-------session_id/hosts/timeout-------------
    <-----------------data1----------------------
                     [...]
    <-----------------session_id/hosts/timeout----------------------
    <----------------------------data2------------------------------
    -------{hostid1: data1, hostid2: data2}------>
    <---------------------BYE---------------------
    -----------------{hostid1: data1, hostid2: data2}-------------->
    <-------------------------------BYE-----------------------------

Server waits for data from all clients and then sends data to all clients.

# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

###############################################################################
# Name         test_ft_lag_dynamic_tagged_vlan.py
#
# Objective:   Verify if a dynamic LAG with tagged vlan can be created.
#
# Description: This test verifies that a dynamic LAG can be configure with
#              tagged vlan
#
# Topology:   |Host| ----- |Switch| ------------------ |Switch| ----- |2 -Host|
#                                   (Dynamic LAG - 2 links)
#
# Success Criteria:  PASS -> This test is effective if pinging between
#                            the workstations(step 6 and 9) is successful.
#                            This test is effective if connectivity in the
#                            single workstation is not successful.
#
#                    FAILED -> This test fails if the ping(step 6 and 9)
#                              does not reach the other side.
#                              This test fails if connectivity in the single
#                              workstation is successful
###############################################################################

import pytest
from lacp_lib import (
    associate_interface_to_lag,
    associate_vlan_to_l2_interface,
    check_connectivity_between_hosts,
    create_lag,
    create_vlan,
    LOCAL_STATE,
    REMOTE_STATE,
    tagged_vlan_to_lag,
    turn_on_interface,
    verify_lag_config,
    verify_state_sync_lag,
    verify_turn_on_interfaces
)

TOPOLOGY = """

# +-------+                  +-------+         +-------+
# |       |                  |       |         |       |
# |  hs1  |                  |  hs2  |         |  hs3  |
# |       |                  |       |         |       |
# +---1---+                  +---1---+         +---1---+
#     |                          |                 |
#     |                          |                 |
#     |                          --------    -------
#     |                                  |   |
# +---1---+                            +-1---4-+
# |       |                            |       |
# |       2----------------------------2       |
# |  sw1  3----------------------------3  sw2  |
# |       |                            |       |
# +-------+                            +-------+



# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=host name="Host 1"] hs1
[type=host name="Host 2"] hs2
[type=host name="Host 3"] hs3

# Links
sw1:1 -- hs1:1
sw1:2 -- sw2:2
sw1:3 -- sw2:3
sw2:1 -- hs2:1
sw2:4 -- hs3:1
"""


@pytest.mark.skipif(True, reason="Skipping due to instability")
def test_dynamic_tagged_vlan(topology, step):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')
    hs3 = topology.get('hs3')

    assert sw1 is not None
    assert sw2 is not None
    assert hs1 is not None
    assert hs2 is not None
    assert hs3 is not None

    ports_sw1 = list()
    ports_sw2 = list()
    port_labels = ['1', '2', '3', '4']

    lag_id = '1'
    vlans_id = ['800', '900']
    mode_active = 'active'
    mode_passive = 'passive'

    step("### Mapping interfaces from Docker ###")
    for port in port_labels[:3]:
        ports_sw1.append(sw1.ports[port])

    for port in port_labels:
        ports_sw2.append(sw2.ports[port])

    step("#### Turning on interfaces in sw1 ###")
    for port in ports_sw1:
        turn_on_interface(sw1, port)

    step("#### Turning on interfaces in sw2 ###")
    for port in ports_sw2:
        turn_on_interface(sw2, port)

    step("#### Validate interfaces are turn on ####")
    verify_turn_on_interfaces(sw1, ports_sw1)
    verify_turn_on_interfaces(sw2, ports_sw2)

    step("##### Create LAGs ####")
    create_lag(sw1, lag_id, mode_active)
    create_lag(sw2, lag_id, mode_passive)

    step("#### Associate Interfaces to LAG ####")
    for intf in ports_sw1[1:3]:
        associate_interface_to_lag(sw1, intf, lag_id)

    for intf in ports_sw2[1:3]:
        associate_interface_to_lag(sw2, intf, lag_id)

    step("#### Verify LAG configuration ####")
    verify_lag_config(sw1, lag_id, ports_sw1[1:3], mode=mode_active)
    verify_lag_config(sw2, lag_id, ports_sw2[1:3], mode=mode_passive)

    step("#### Configure VLANs on switches ####")
    for vlan in vlans_id:
        create_vlan(sw1, vlan)
        create_vlan(sw2, vlan)

    step("### Tagged VLANs on LAG interfaces")
    tagged_vlan_to_lag(sw1, vlans_id, lag_id)
    tagged_vlan_to_lag(sw2, vlans_id, lag_id)

    associate_vlan_to_l2_interface(sw1, vlans_id[0], ports_sw1[0])
    associate_vlan_to_l2_interface(sw2, vlans_id[0], ports_sw2[0])
    associate_vlan_to_l2_interface(sw2, vlans_id[1], ports_sw2[3])

    step("#### Configure workstations ####")
    hs1.libs.ip.interface('1', addr='140.1.1.10/24', up=True)
    hs2.libs.ip.interface('1', addr='140.1.1.11/24', up=True)
    hs3.libs.ip.interface('1', addr='140.1.1.12/24', up=True)

    step("### Verify if LAG is synchronized")
    verify_state_sync_lag(sw1, ports_sw1[1:3], LOCAL_STATE, mode_active)
    verify_state_sync_lag(sw1, ports_sw1[1:3], REMOTE_STATE, mode_passive)

    step("#### Test ping between clients in the same vlan ####")
    check_connectivity_between_hosts(hs1, '140.1.1.10', hs2, '140.1.1.11',
                                     5, True)

    step("#### Test ping between clients in the different vlan ####")
    check_connectivity_between_hosts(hs1, '140.1.1.10', hs3, '140.1.1.12',
                                     5, False)

    step("### Move one WS to the VLAN with the single workstation ###")
    associate_vlan_to_l2_interface(sw1, vlans_id[1], ports_sw1[0])

    step("#### Test ping between clients in the same vlan ####")
    check_connectivity_between_hosts(hs1, '140.1.1.10', hs3, '140.1.1.12',
                                     5, True)

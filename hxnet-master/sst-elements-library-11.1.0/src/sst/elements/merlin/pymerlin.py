#!/usr/bin/env python
#
# Copyright 2009-2021 NTESS. Under the terms
# of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.
#
# Copyright (c) 2009-2021, NTESS
# All rights reserved.
#
# Portions are copyright of other developers:
# See the file CONTRIBUTORS.TXT in the top level directory
# the distribution for more information.
#
# This file is part of the SST software package. For license
# information, see the LICENSE file in the top level directory of the
# distribution.

import math
import sys

import sst

# This just suppresses the warning when using emberload.py
if "USING_EMBER_LOAD" in globals():
    print(
        "#WARNING: sst.merlin python module is deprecated and will be removed in SST 12.  Please use the new merlin python modules."
    )

try:
    input = raw_input
except NameError:
    pass


class Params(dict):
    def __missing__(self, key):
        print("Please enter %s: " % key)
        val = input()
        self[key] = val
        return val

    def subset(self, keys, optKeys=[]):
        ret = dict((k, self[k]) for k in keys)
        # ret.update(dict((k, self[k]) for k in (optKeys and self)))
        for k in optKeys:
            if k in self:
                ret[k] = self[k]
        return ret

    def subsetWithRename(self, keys):
        ret = dict()
        for k, nk in keys:
            if k in self:
                ret[nk] = self[k]
        return ret

    # Needed to avoid asking for input when a key isn't present


#    def optional_subset(self, keys):
#        return

_params = Params()
debug = 0


class Topo(object):
    def __init__(self):
        self.topoKeys = []
        self.topoOptKeys = []
        self.bundleEndpoints = True

        def epFunc(epID):
            return None

        self._getEndPoint = epFunc

    def keepEndPointsWithRouter(self):
        self.bundleEndpoints = False

    def getName(self):
        return "NoName"

    def prepParams(self):
        pass

    def setEndPoint(self, endPoint):
        def epFunc(epID):
            return endPoint

        self._getEndPoint = epFunc

    def setEndPointFunc(self, epFunc):
        self._getEndPoint = epFunc

    def build(self):
        pass

    def getRouterNameForId(self, rtr_id):
        return "rtr.%d" % rtr_id

    def findRouterById(self, rtr_id):
        return sst.findComponentByName(self.getRouterNameForId(rtr_id))

    def _instanceRouter(self, rtr_id, rtr_type):
        return sst.Component(self.getRouterNameForId(rtr_id), rtr_type)


class topoSimple(Topo):
    def __init__(self):
        Topo.__init__(self)
        self.topoKeys.extend(
            [
                "topology",
                "debug",
                "num_ports",
                "flit_size",
                "link_bw",
                "xbar_bw",
                "input_latency",
                "output_latency",
                "input_buf_size",
                "output_buf_size",
            ]
        )
        self.topoOptKeys.extend(
            [
                "xbar_arb",
                "num_vns",
                "vn_remap",
                "vn_remap_shm",
                "portcontrol:output_arb",
                "portcontrol:arbitration:qos_settings",
                "portcontrol:arbitration:arb_vns",
                "portcontrol:arbitration:arb_vcs",
            ]
        )

    def getName(self):
        return "Simple"

    def prepParams(self):
        #        if "xbar_arb" not in _params:
        #            _params["xbar_arb"] = "merlin.xbar_arb_lru"
        _params["topology"] = "merlin.singlerouter"
        _params["debug"] = debug
        _params["num_ports"] = int(_params["router_radix"])
        _params["num_peers"] = int(_params["router_radix"])

    def build(self):
        rtr = self._instanceRouter(0, "merlin.hr)_router")
        rtr.setSubComponent("topology", "merlin.singlerouter", 0)
        _params["topology"] = "merlin.singlerouter"
        _params["debug"] = debug
        #        rtr.addParams(_params.subset(self.rtrKeys))
        rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
        rtr.addParam("id", 0)

        for l in range(_params["num_ports"]):
            ep = self._getEndPoint(l).build(l, {})
            if ep:
                link = sst.Link("link:%d" % l)
                if self.bundleEndpoints:
                    link.setNoCut()
                link.connect(ep, (rtr, "port%d" % l, _params["link_lat"]))

    def getRouterNameForId(self, rtr_id):
        return "router"


class topoTorus(Topo):
    def __init__(self):
        Topo.__init__(self)
        self.topoKeys.extend(
            [
                "topology",
                "debug",
                "num_ports",
                "flit_size",
                "link_bw",
                "nic_link_bw",
                "xbar_bw",
                "torus:shape",
                "torus:width",
                "torus:local_ports",
                "input_latency",
                "output_latency",
                "input_buf_size",
                "output_buf_size",
            ]
        )
        self.topoOptKeys.extend(
            [
                "xbar_arb",
                "num_vns",
                "vn_remap",
                "vn_remap_shm",
                "portcontrol:output_arb",
                "portcontrol:arbitration:qos_settings",
                "portcontrol:arbitration:arb_vns",
                "portcontrol:arbitration:arb_vcs",
            ]
        )

    def getName(self):
        return "Torus"

    def prepParams(self):
        #        if "xbar_arb" not in _params:
        #            _params["xbar_arb"] = "merlin.xbar_arb_lru"
        peers = 1
        radix = 0
        self.dims = []
        self.dimwidths = []
        if not "torus:shape" in _params:
            self.nd = int(_params["num_dims"])
            for x in range(self.nd):
                print("Dim %d size:" % x)
                ds = int(input())
                self.dims.append(ds)
            _params["torus:shape"] = self._formatShape(self.dims)
        else:
            self.dims = [int(x) for x in _params["torus:shape"].split("x")]
            self.nd = len(self.dims)
        if not "torus:width" in _params:
            for x in range(self.nd):
                print("Dim %d width (# of links in this dimension):" % x)
                dw = int(input())
                self.dimwidths.append(dw)
            _params["torus:width"] = self._formatShape(self.dimwidths)
        else:
            self.dimwidths = [int(x) for x in _params["torus:width"].split("x")]

        local_ports = int(_params["torus:local_ports"])
        radix = local_ports + 2 * sum(self.dimwidths)

        # print("Radix Torus is " + str(radix))

        for x in self.dims:
            peers = peers * x
        peers = peers * local_ports

        # print("Peer is " + str(peers))

        _params["num_peers"] = peers
        _params["num_dims"] = self.nd
        _params["topology"] = _params["topology"] = "merlin.torus"
        _params["debug"] = debug
        _params["num_ports"] = _params["router_radix"] = radix
        _params["torus:local_ports"] = local_ports

    def _formatShape(self, arr):
        return "x".join([str(x) for x in arr])

    def _idToLoc(self, rtr_id):
        foo = list()
        for i in range(self.nd - 1, 0, -1):
            div = 1
            for j in range(0, i):
                div = div * self.dims[j]
            value = rtr_id // div
            foo.append(value)
            rtr_id = rtr_id - (value * div)
        foo.append(rtr_id)
        foo.reverse()
        return foo

    def getRouterNameForId(self, rtr_id):
        return self.getRouterNameForLocation(self._idToLoc(rtr_id))

    def getRouterNameForLocation(self, location):
        return "rtr.%s" % (self._formatShape(location))

    def findRouterByLocation(self, location):
        return sst.findComponentByName(self.getRouterNameForLocation(location))

    def build(self):
        num_routers = _params["num_peers"] // _params["torus:local_ports"]
        links = dict()

        def getLink(leftName, rightName, num):
            name = "link.%s:%s:%d" % (leftName, rightName, num)
            if name not in links:
                links[name] = sst.Link(name)
            return links[name]

        swap_keys = [
            ("torus:shape", "shape"),
            ("torus:width", "width"),
            ("torus:local_ports", "local_ports"),
        ]

        _topo_params = _params.subsetWithRename(swap_keys)
        for i in range(num_routers):
            # set up 'mydims'
            mydims = self._idToLoc(i)
            mylocstr = self._formatShape(mydims)
            rtr = self._instanceRouter(i, "merlin.hr_router")
            # rtr = sst.Component("rtr.%s"%mylocstr, "merlin.hr_router")
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", i)
            topology = rtr.setSubComponent("topology", "merlin.torus")
            topology.addParams(_topo_params)

            port = 0
            for dim in range(self.nd):
                theirdims = mydims[:]

                # Positive direction
                theirdims[dim] = (mydims[dim] + 1) % self.dims[dim]
                theirlocstr = self._formatShape(theirdims)
                for num in range(self.dimwidths[dim]):
                    rtr.addLink(
                        getLink(mylocstr, theirlocstr, num),
                        "port%d" % port,
                        _params["link_lat"],
                    )
                    port = port + 1

                # Negative direction
                theirdims[dim] = ((mydims[dim] - 1) + self.dims[dim]) % self.dims[dim]
                theirlocstr = self._formatShape(theirdims)
                for num in range(self.dimwidths[dim]):
                    rtr.addLink(
                        getLink(theirlocstr, mylocstr, num),
                        "port%d" % port,
                        _params["link_lat"],
                    )
                    port = port + 1

            for n in range(_params["torus:local_ports"]):
                nodeID = int(_params["torus:local_ports"]) * i + n
                ep = self._getEndPoint(nodeID).build(nodeID, {})
                if ep:
                    nicLink = sst.Link("nic.%d:%d" % (i, n))
                    if self.bundleEndpoints:
                        nicLink.setNoCut()
                    nicLink.connect(ep, (rtr, "port%d" % port, _params["link_lat"]))
                port = port + 1


class topoMesh(Topo):
    def __init__(self):
        Topo.__init__(self)
        self.topoKeys = [
            "topology",
            "debug",
            "num_ports",
            "flit_size",
            "link_bw",
            "nic_link_bw",
            "xbar_bw",
            "mesh:shape",
            "mesh:width",
            "mesh:local_ports",
            "input_latency",
            "output_latency",
            "input_buf_size",
            "output_buf_size",
        ]
        self.topoOptKeys = [
            "xbar_arb",
            "num_vns",
            "vn_remap",
            "vn_remap_shm",
            "portcontrol:output_arb",
            "portcontrol:arbitration:qos_settings",
            "portcontrol:arbitration:arb_vns",
            "portcontrol:arbitration:arb_vcs",
        ]

    def getName(self):
        return "Mesh"

    def prepParams(self):
        #        if "xbar_arb" not in _params:
        #            _params["xbar_arb"] = "merlin.xbar_arb_lru"
        peers = 1
        radix = 0
        self.dims = []
        self.dimwidths = []
        if not "mesh:shape" in _params:
            self.nd = int(_params["num_dims"])
            for x in range(self.nd):
                print("Dim %d size:" % x)
                ds = int(input())
                self.dims.append(ds)
            _params["mesh:shape"] = self._formatShape(self.dims)
        else:
            self.dims = [int(x) for x in _params["mesh:shape"].split("x")]
            self.nd = len(self.dims)
        if not "mesh:width" in _params:
            for x in range(self.nd):
                print("Dim %d width (# of links in this dimension):" % x)
                dw = int(input())
                self.dimwidths.append(dw)
            _params["mesh:width"] = self._formatShape(self.dimwidths)
        else:
            self.dimwidths = [int(x) for x in _params["mesh:width"].split("x")]

        local_ports = int(_params["mesh:local_ports"])
        radix = local_ports + 2 * sum(self.dimwidths)

        for x in self.dims:
            peers = peers * x
        peers = peers * local_ports

        _params["num_peers"] = peers
        _params["num_dims"] = self.nd
        _params["topology"] = _params["topology"] = "merlin.mesh"
        _params["debug"] = debug
        _params["num_ports"] = _params["router_radix"] = radix
        _params["mesh:local_ports"] = local_ports

    def _formatShape(self, arr):
        return "x".join([str(x) for x in arr])

    def _idToLoc(self, rtr_id):
        foo = list()
        for i in range(self.nd - 1, 0, -1):
            div = 1
            for j in range(0, i):
                div = div * self.dims[j]
            value = rtr_id // div
            foo.append(value)
            rtr_id = rtr_id - (value * div)
        foo.append(rtr_id)
        foo.reverse()
        return foo

    def getRouterNameForId(self, rtr_id):
        return self.getRouterNameForLocation(self._idToLoc(rtr_id))

    def getRouterNameForLocation(self, location):
        return "rtr.%s" % (self._formatShape(location))

    def findRouterByLocation(self, location):
        return sst.findComponentByName(self.getRouterNameForLocation(location))

    def build(self):

        num_routers = _params["num_peers"] // _params["mesh:local_ports"]
        links = dict()

        def getLink(leftName, rightName, num):
            name = "link.%s:%s:%d" % (leftName, rightName, num)
            if name not in links:
                links[name] = sst.Link(name)
            return links[name]

        swap_keys = [
            ("mesh:shape", "shape"),
            ("mesh:width", "width"),
            ("mesh:local_ports", "local_ports"),
        ]

        _topo_params = _params.subsetWithRename(swap_keys)
        for i in range(num_routers):
            # set up 'mydims'
            mydims = self._idToLoc(i)
            mylocstr = self._formatShape(mydims)

            rtr = self._instanceRouter(i, "merlin.hr_router")
            # rtr = sst.Component("rtr.%s"%mylocstr, "merlin.hr_router")
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", i)
            topology = rtr.setSubComponent("topology", "merlin.mesh")
            topology.addParams(_topo_params)

            port = 0
            for dim in range(self.nd):
                theirdims = mydims[:]

                # Positive direction
                if mydims[dim] + 1 < self.dims[dim]:
                    theirdims[dim] = (mydims[dim] + 1) % self.dims[dim]
                    theirlocstr = self._formatShape(theirdims)
                    for num in range(self.dimwidths[dim]):
                        rtr.addLink(
                            getLink(mylocstr, theirlocstr, num),
                            "port%d" % port,
                            _params["link_lat"],
                        )
                        port = port + 1
                else:
                    port += self.dimwidths[dim]

                # Negative direction
                if mydims[dim] > 0:
                    theirdims[dim] = ((mydims[dim] - 1) + self.dims[dim]) % self.dims[
                        dim
                    ]
                    theirlocstr = self._formatShape(theirdims)
                    for num in range(self.dimwidths[dim]):
                        rtr.addLink(
                            getLink(theirlocstr, mylocstr, num),
                            "port%d" % port,
                            _params["link_lat"],
                        )
                        port = port + 1
                else:
                    port += self.dimwidths[dim]

            for n in range(_params["mesh:local_ports"]):
                nodeID = int(_params["mesh:local_ports"]) * i + n
                ep = self._getEndPoint(nodeID).build(nodeID, {})
                if ep:
                    nicLink = sst.Link("nic.%d:%d" % (i, n))
                    if self.bundleEndpoints:
                        nicLink.setNoCut()
                    nicLink.connect(ep, (rtr, "port%d" % port, _params["link_lat"]))
                port = port + 1


class topoHamming(Topo):
    def __init__(self):
        Topo.__init__(self)
        self.topoKeys = [
            "topology",
            "debug",
            "num_ports",
            "flit_size",
            "link_bw",
            "nic_link_bw",
            "xbar_bw",
            "hamming:fat_tree_shape",
            "hamming:shape",
            "hamming:single_switch_fat_tree",
            "hamming:link_width",
            "hamming:switches_first_level",
            "hamming:board_shape",
            "hamming:global_shape",
            "hamming:is_board_switch",
            "hamming:algorithm",
            "hamming:global_switch_id",
            "hamming:local_switch_id",
            "hamming:global_pos",
            "hamming:local_pos",
            "hamming:unique_pos",
            "hamming:fat_tree_id",
            "hamming:fat_tree_pos",
            "hamming:width",
            "hamming:local_ports",
            "hamming:is_jellyfish",
            "hamming:routing_table",
            "hamming:row_ft_port",
            "hamming:col_ft_port",
            "hamming:nearest_row_edge",
            "hamming:nearest_col_edge",
            "input_latency",
            "output_latency",
            "input_buf_size",
            "output_buf_size",
        ]
        self.topoOptKeys = [
            "xbar_arb",
            "num_vns",
            "vn_remap",
            "vn_remap_shm",
            "portcontrol:output_arb",
            "portcontrol:arbitration:qos_settings",
            "portcontrol:arbitration:arb_vns",
            "portcontrol:arbitration:arb_vcs",
        ]

    def getName(self):
        return "Hamming"

    def prepParams(self):
        #        if "xbar_arb" not in _params:
        #            _params["xbar_arb"] = "merlin.xbar_arb_lru"
        peers = 1
        radix = 0
        self.num_boards = 1
        self.switch_per_board = 1
        self.dims = []
        self.global_shape = []
        self.dimwidths = []
        self.list_routers = {}
        self.global_to_local = {}
        self.global_router_id = 0
        if not "hamming:shape" in _params:
            self.nd = int(_params["num_dims"])
            for x in range(self.nd):
                # print("Dim %d size:"%x)
                ds = int(input())
                self.dims.append(ds)
            _params["hamming:shape"] = self._formatShape(self.dims)
        else:  # If we define shape when running SST
            self.dims = [int(x) for x in _params["hamming:shape"].split("x")]
            self.nd = len(self.dims)
            self.global_shape = [
                int(x) for x in _params["hamming:global_shape"].split("x")
            ]
            self.fat_tree_shape = _params["hamming:fat_tree_shape"].split(",")
            self.radix_fat_tree_switches = int(self.fat_tree_shape[1])
            self.fat_tree_shape = [int(x) for x in self.fat_tree_shape[0].split(":")]
        if not "hamming:width" in _params:
            for x in range(self.nd):
                # print("Dim %d width (# of links in this dimension):" % x)
                dw = int(input())
                self.dimwidths.append(dw)
            _params["hamming:width"] = self._formatShape(self.dimwidths)
            # print("default width is " + str(_params["hamming:width"]))
        else:
            self.dimwidths = [int(x) for x in _params["hamming:width"].split("x")]
            # print("set width is " + str(_params["hamming:width"]))

        local_ports = int(_params["hamming:local_ports"])
        # We should only need 1x1 width, but let's keep it open
        radix = local_ports + 2 * sum(self.dimwidths)

        """print("self.dimwidths" + str(self.dimwidths))
        print("self.dims" + str(self.dims))
        print("self.global" + str(self.global_shape))
        print("self.fat_tree_shape" + str(self.fat_tree_shape))
        print("radix is " + str(radix))"""
        # Board shape
        for x in self.dims:
            peers = peers * x
            self.switch_per_board = self.switch_per_board * x
        # Global Shape
        for x in self.global_shape:
            peers = peers * x
        peers = peers * local_ports
        self.num_boards = int(peers / self.switch_per_board)
        self.switches_first_level = -1
        self.link_width = -1

        # print("Peers is " + str(peers))
        # print("num_boards is " + str(self.num_boards))
        # print("switch_per_board is " + str(self.switch_per_board))

        _params["num_peers"] = peers
        _params["num_dims"] = self.nd
        _params["topology"] = _params["topology"] = "merlin.hamming"
        _params["debug"] = debug
        _params["num_ports"] = _params["router_radix"] = radix
        _params["hamming:local_ports"] = local_ports

        # Jellyfish local topology: check if user requested it
        self.use_jellyfish = _params.get("hamming:use_jellyfish", False)
        if isinstance(self.use_jellyfish, str):
            self.use_jellyfish = self.use_jellyfish.lower() in ("true", "1", "yes")

        # Jellyfish-as-fat-tree-leaf mode. jf_ft_nodes > 0 simply enables it; its
        # magnitude is ignored (see _compute_jf_gateways) because the gateway set
        # is sized to match the 2D mesh exactly, giving identical global bandwidth.
        self.jf_ft_nodes = int(_params.get("hamming:jellyfish_ft_nodes", 0))
        self._jf_gateway_map = {}  # board_id -> {'row_ft': set, 'col_ft': set}
        self._current_board_id = 0  # set before _get_reserved_ports() is called

    def _formatShape(self, arr):
        return "x".join([str(x) for x in arr])

    def _idToLoc(self, rtr_id):
        foo = list()
        for i in range(self.nd - 1, 0, -1):
            div = 1
            for j in range(0, i):
                div = div * self.dims[j]
            value = rtr_id // div
            foo.append(value)
            rtr_id = rtr_id - (value * div)
        foo.append(rtr_id)
        foo.reverse()
        return foo

    def getRouterNameForId(self, rtr_id):
        return self.getRouterNameForLocation(self._idToLoc(rtr_id))

    def getRouterNameForLocation(self, location):
        return "rtr.%d" % (self.global_router_id)

    def findRouterByLocation(self, location):
        return sst.findComponentByName(self.getRouterNameForLocation(location))

    def getGlobalDims(self, location):
        maxRowLength = self.dims[0] * self.global_shape[0]

        myRow = location // (maxRowLength - 1)
        myCol = location % (maxRowLength - 1)

        myId = [myRow, myCol]
        return myId

    def getLocalDims(self, location):
        myRow = location // (self.dims[1])
        myCol = location % (self.dims[1])
        myId = [myRow, myCol]
        return myId

    def getUniquePos(self, local_pos, board_id):
        myRow = board_id // (self.global_shape[1])
        myCol = board_id % (self.global_shape[1])
        myId = [myRow, myCol]
        unique_pos = [local_pos, myId]
        return unique_pos

    def getRouterNameString(self, pos):
        return "{}x{}x{}x{}".format(pos[0][0], pos[0][1], pos[1][0], pos[1][1])

    def getTotRoutersMeshes(self):
        tot_routers = 1
        for d in self.global_shape:
            tot_routers = tot_routers * d
        for d in self.dims:
            tot_routers = tot_routers * d
        # print("Tot Routers -> {}".format(tot_routers))
        return tot_routers

    def getUniquePosFromGlobal(self, global_pos):
        total_rows = self.global_shape[0] * self.dims[0]
        total_cols = self.global_shape[1] * self.dims[1]
        unique_id = (global_pos[0] * total_cols) + global_pos[1]
        # print("Unique ID is {}".format(unique_id))

    def GlobalToString(self, glob):
        return "{}x{}".format(glob[0], glob[1])

    def getOffsetPerDirection(self, direction):
        if direction == 0:
            return [-1, 0]
        elif direction == 1:
            return [0, 1]
        elif direction == 2:
            return [1, 0]
        elif direction == 3:
            return [0, -1]

    def isInsideBoard(self, pos):
        return (pos[0] >= 0 and pos[0] < self.dims[0]) and (
            pos[1] >= 0 and pos[1] < self.dims[1]
        )

    def isFirstOrLast(self, pos, limit_direction):
        my_pos = pos % limit_direction
        return my_pos == 0 or my_pos == limit_direction - 1

    def isFirst(self, pos, limit_direction):
        my_pos = pos % limit_direction
        return my_pos == 0

    def setParameters(
        self,
        _params,
        is_bd_sw,
        global_router_id,
        local_router_id,
        my_glob_id,
        my_loc_id,
        unique_pos,
        fat_tree_id,
        fat_tree_pos,
    ):
        _params["hamming:is_board_switch"] = is_bd_sw
        _params["hamming:global_switch_id"] = global_router_id
        _params["hamming:local_switch_id"] = local_router_id
        _params["hamming:global_pos"] = my_glob_id
        _params["hamming:local_pos"] = my_loc_id
        _params["hamming:unique_pos"] = [
            unique_pos[0][0],
            unique_pos[0][1],
            unique_pos[1][0],
            unique_pos[1][1],
        ]
        _params["hamming:fat_tree_id"] = fat_tree_id
        _params["hamming:fat_tree_pos"] = fat_tree_pos
        _params["hamming:link_width"] = self.link_width
        _params["hamming:switches_first_level"] = self.switches_first_level
        _params["hamming:single_switch_fat_tree"] = False
        # Jellyfish defaults
        _params["hamming:is_jellyfish"] = False
        _params["hamming:routing_table"] = ""
        _params["hamming:row_ft_port"] = -1
        _params["hamming:col_ft_port"] = -1
        _params["hamming:nearest_row_edge"] = -1
        _params["hamming:nearest_col_edge"] = -1

    def createRowFatTree(self, nodes, total, row, col):
        """Create a 2-level fat tree (edge + core) for a row.

        Level 1 (edge/aggregation): radix/2 down-ports to gateways, radix/2 up-ports to core.
        Level 2 (core): all ports connect down to edge switches.
        Each core switch connects to every edge switch with links_num links.
        """

        # Helper function
        links = dict()

        def getLink(leftName, rightName, num):
            name = "link.%s:%s:%d" % (leftName, rightName, num)
            if name not in links:
                links[name] = sst.Link(name)
            return links[name]

        # Initialize overall values
        num_ports_per_switch = self.radix_fat_tree_switches
        num_switches_first_level = int(math.ceil(nodes / (num_ports_per_switch / 2)))
        tot_ports_up = num_switches_first_level * (num_ports_per_switch / 2)
        num_swithes_second_level = int(math.ceil(tot_ports_up / num_ports_per_switch))
        down_ports = num_ports_per_switch / 2
        list_routers_first_level = {}
        list_routers_second_level = {}

        # Iterate routers first level and link them to board switches
        col_idx = 0
        for router_level_1 in range(int(num_switches_first_level)):
            # Create router
            current_down_port = down_ports
            port = 0
            rtr = self._instanceRouter(self.global_router_id, "merlin.hr_router")
            _params["num_ports"] = _params["router_radix"] = (
                self.radix_fat_tree_switches
            )
            _params["hamming:local_ports"] = 0
            self.setParameters(
                _params,
                False,
                self.global_router_id,
                -1,
                [-1, -1],
                [-1, -1],
                [[-1, -1], [-1, -1]],
                [0, row],
                [0, router_level_1],
            )
            _params["hamming:link_width"] = int(down_ports / num_swithes_second_level)
            _params["hamming:switches_first_level"] = num_switches_first_level
            _params["hamming:jf_ft_nodes"] = (
                self.jf_ft_nodes if self.use_jellyfish else 0
            )
            swap_keys = [
                ("hamming:algorithm", "algorithm"),
                ("hamming:jf_ft_nodes", "jf_ft_nodes"),
                ("hamming:shape", "shape"),
                ("hamming:fat_tree_shape", "fat_tree_shape"),
                ("hamming:width", "width"),
                ("hamming:board_shape", "board_shape"),
                ("hamming:local_ports", "local_ports"),
                ("hamming:global_shape", "global_shape"),
                ("hamming:is_board_switch", "is_board_switch"),
                ("hamming:global_switch_id", "global_switch_id"),
                ("hamming:local_switch_id", "local_switch_id"),
                ("hamming:global_pos", "global_pos"),
                ("hamming:local_pos", "local_pos"),
                ("hamming:unique_pos", "unique_pos"),
                ("hamming:fat_tree_id", "fat_tree_id"),
                ("hamming:fat_tree_pos", "fat_tree_pos"),
                ("hamming:link_width", "link_width"),
                ("hamming:switches_first_level", "switches_first_level"),
            ]
            _topo_params = _params.subsetWithRename(swap_keys)
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", self.global_router_id)
            topology = rtr.setSubComponent("topology", "merlin.hamming")
            topology.addParams(_topo_params)
            self.global_router_id = self.global_router_id + 1
            name_rtr = "rowx{}:{}x{}".format(row, 0, router_level_1)
            list_routers_first_level[name_rtr] = rtr

            while (
                col_idx != self.global_shape[1] * self.dims[1]
            ) and current_down_port != 0:
                if self.use_jellyfish and self.jf_ft_nodes > 0:
                    board_id_ft = (row // self.dims[0]) * self.global_shape[1] + (
                        col_idx // self.dims[1]
                    )
                    local_id_ft = (row % self.dims[0]) * self.dims[1] + (
                        col_idx % self.dims[1]
                    )
                    should_connect = local_id_ft in self._jf_gateway_map.get(
                        board_id_ft, {}
                    ).get("row_ft", set())
                    my_port = 3
                else:
                    should_connect = self.isFirstOrLast(col_idx, self.dims[1])
                    isFirst = self.isFirst(col_idx, self.dims[1])
                    my_port = 3 if isFirst else 1
                if should_connect:
                    # Connect from Fat Tree router to board router
                    unique_pos = self.global_to_local[
                        self.GlobalToString([row, col_idx])
                    ]
                    partner_str = self.getRouterNameString((unique_pos))
                    rtr.addLink(
                        getLink(name_rtr, partner_str, 0),
                        "port%d" % port,
                        _params["link_lat"],
                    )
                    # Connect from board router to fat tree router
                    other_rtr = self.list_routers[partner_str]
                    other_rtr.addLink(
                        getLink(name_rtr, partner_str, 0),
                        "port%d" % my_port,
                        _params["link_lat"],
                    )
                    port = port + 1
                    current_down_port = current_down_port - 1

                col_idx = col_idx + 1

        # Iterate routers second level and link them to first level switches
        for router_level_2 in range(int(num_swithes_second_level)):
            # Create router
            rtr = self._instanceRouter(self.global_router_id, "merlin.hr_router")
            _params["num_ports"] = _params["router_radix"] = num_ports_per_switch
            _params["hamming:local_ports"] = 0
            self.setParameters(
                _params,
                False,
                self.global_router_id,
                -1,
                [-1, -1],
                [-1, -1],
                [[-1, -1], [-1, -1]],
                [0, row],
                [1, router_level_2],
            )
            _params["hamming:link_width"] = int(down_ports / num_swithes_second_level)
            _params["hamming:switches_first_level"] = num_switches_first_level
            _params["hamming:jf_ft_nodes"] = (
                self.jf_ft_nodes if self.use_jellyfish else 0
            )
            swap_keys = [
                ("hamming:algorithm", "algorithm"),
                ("hamming:jf_ft_nodes", "jf_ft_nodes"),
                ("hamming:shape", "shape"),
                ("hamming:fat_tree_shape", "fat_tree_shape"),
                ("hamming:width", "width"),
                ("hamming:board_shape", "board_shape"),
                ("hamming:local_ports", "local_ports"),
                ("hamming:global_shape", "global_shape"),
                ("hamming:is_board_switch", "is_board_switch"),
                ("hamming:global_switch_id", "global_switch_id"),
                ("hamming:local_switch_id", "local_switch_id"),
                ("hamming:global_pos", "global_pos"),
                ("hamming:local_pos", "local_pos"),
                ("hamming:unique_pos", "unique_pos"),
                ("hamming:fat_tree_id", "fat_tree_id"),
                ("hamming:fat_tree_pos", "fat_tree_pos"),
                ("hamming:link_width", "link_width"),
                ("hamming:switches_first_level", "switches_first_level"),
            ]
            _topo_params = _params.subsetWithRename(swap_keys)
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", self.global_router_id)
            topology = rtr.setSubComponent("topology", "merlin.hamming")
            topology.addParams(_topo_params)
            self.global_router_id = self.global_router_id + 1
            name_rtr = "rowx{}:{}x{}".format(row, 1, router_level_2)
            list_routers_second_level[name_rtr] = rtr

        # Wire edge-to-core inter-level links
        starting_port_2_down = 0

        starting_port_down = [None] * num_swithes_second_level
        links_num = int(down_ports / num_swithes_second_level)

        for idx_2 in range(0, num_swithes_second_level):
            starting_port_down[idx_2] = list()
            for idx in range(0, num_switches_first_level):
                starting_port_down[idx_2].append(idx * links_num)

        starting_port_1_up = int(down_ports)

        for link_num in range(links_num):
            for router_level_2 in range(num_swithes_second_level):
                for router_level_1 in range(num_switches_first_level):
                    name_rtr_1 = "rowx{}:{}x{}".format(row, 0, router_level_1)
                    rtr_1 = list_routers_first_level[name_rtr_1]

                    name_rtr_2 = "rowx{}:{}x{}".format(row, 1, router_level_2)
                    rtr_2 = list_routers_second_level[name_rtr_2]

                    rtr_1.addLink(
                        getLink(name_rtr_1, name_rtr_2, link_num),
                        "port%d" % starting_port_1_up,
                        _params["link_lat"],
                    )
                    rtr_2.addLink(
                        getLink(name_rtr_1, name_rtr_2, link_num),
                        "port%d" % starting_port_down[router_level_2][router_level_1],
                        _params["link_lat"],
                    )

                    starting_port_down[router_level_2][router_level_1] = (
                        starting_port_down[router_level_2][router_level_1] + 1
                    )

                starting_port_1_up = starting_port_1_up + 1

            starting_port_2_down = starting_port_2_down + 1

        return 1

    def createColFatTree(self, nodes, total, row, col):
        """Create a 2-level fat tree (edge + core) for a column.

        Same approach as createRowFatTree but for column-wise fat trees.
        Gateways use port 0 (N) or 2 (S) instead of port 3 (W) or 1 (E).
        """

        # Helper function
        links = dict()

        def getLink(leftName, rightName, num):
            name = "link.%s:%s:%d" % (leftName, rightName, num)
            if name not in links:
                links[name] = sst.Link(name)
            return links[name]

        # Initialize overall values
        num_ports_per_switch = self.radix_fat_tree_switches
        num_switches_first_level = int(math.ceil(nodes / (num_ports_per_switch / 2)))
        tot_ports_up = num_switches_first_level * (num_ports_per_switch / 2)
        num_swithes_second_level = int(math.ceil(tot_ports_up / num_ports_per_switch))
        down_ports = num_ports_per_switch / 2
        list_routers_first_level = {}
        list_routers_second_level = {}

        # Iterate routers first level and link them to board switches
        row_idx = 0
        for router_level_1 in range(int(num_switches_first_level)):
            # Create router
            current_down_port = down_ports
            port = 0
            rtr = self._instanceRouter(self.global_router_id, "merlin.hr_router")
            _params["num_ports"] = _params["router_radix"] = num_ports_per_switch
            _params["hamming:local_ports"] = 0
            self.setParameters(
                _params,
                False,
                self.global_router_id,
                -1,
                [-1, -1],
                [-1, -1],
                [[-1, -1], [-1, -1]],
                [1, col],
                [0, router_level_1],
            )
            _params["hamming:link_width"] = int(down_ports / num_swithes_second_level)
            _params["hamming:switches_first_level"] = num_switches_first_level
            _params["hamming:jf_ft_nodes"] = (
                self.jf_ft_nodes if self.use_jellyfish else 0
            )
            swap_keys = [
                ("hamming:algorithm", "algorithm"),
                ("hamming:jf_ft_nodes", "jf_ft_nodes"),
                ("hamming:shape", "shape"),
                ("hamming:fat_tree_shape", "fat_tree_shape"),
                ("hamming:width", "width"),
                ("hamming:board_shape", "board_shape"),
                ("hamming:local_ports", "local_ports"),
                ("hamming:global_shape", "global_shape"),
                ("hamming:is_board_switch", "is_board_switch"),
                ("hamming:global_switch_id", "global_switch_id"),
                ("hamming:local_switch_id", "local_switch_id"),
                ("hamming:global_pos", "global_pos"),
                ("hamming:local_pos", "local_pos"),
                ("hamming:unique_pos", "unique_pos"),
                ("hamming:fat_tree_id", "fat_tree_id"),
                ("hamming:fat_tree_pos", "fat_tree_pos"),
                ("hamming:link_width", "link_width"),
                ("hamming:switches_first_level", "switches_first_level"),
            ]
            _topo_params = _params.subsetWithRename(swap_keys)
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", self.global_router_id)
            topology = rtr.setSubComponent("topology", "merlin.hamming")
            topology.addParams(_topo_params)
            self.global_router_id = self.global_router_id + 1
            name_rtr = "colx{}:{}x{}".format(col, 0, router_level_1)
            list_routers_first_level[name_rtr] = rtr

            while (
                row_idx != self.global_shape[0] * self.dims[0]
            ) and current_down_port != 0:
                if self.use_jellyfish and self.jf_ft_nodes > 0:
                    board_id_ft = (row_idx // self.dims[0]) * self.global_shape[1] + (
                        col // self.dims[1]
                    )
                    local_id_ft = (row_idx % self.dims[0]) * self.dims[1] + (
                        col % self.dims[1]
                    )
                    should_connect = local_id_ft in self._jf_gateway_map.get(
                        board_id_ft, {}
                    ).get("col_ft", set())
                    my_port = 0
                else:
                    should_connect = self.isFirstOrLast(row_idx, self.dims[0])
                    isFirst = self.isFirst(row_idx, self.dims[0])
                    my_port = 0 if isFirst else 2
                if should_connect:
                    # Connect from Fat Tree router to board router
                    unique_pos = self.global_to_local[
                        self.GlobalToString([row_idx, col])
                    ]
                    partner_str = self.getRouterNameString((unique_pos))
                    rtr.addLink(
                        getLink(name_rtr, partner_str, 0),
                        "port%d" % port,
                        _params["link_lat"],
                    )
                    # Connect from board router to fat tree router
                    other_rtr = self.list_routers[partner_str]
                    other_rtr.addLink(
                        getLink(name_rtr, partner_str, 0),
                        "port%d" % my_port,
                        _params["link_lat"],
                    )
                    port = port + 1
                    current_down_port = current_down_port - 1

                row_idx = row_idx + 1

        # Iterate routers second level and link them to first level switches
        for router_level_2 in range(int(num_swithes_second_level)):
            # Create router
            rtr = self._instanceRouter(self.global_router_id, "merlin.hr_router")
            _params["num_ports"] = _params["router_radix"] = num_ports_per_switch
            _params["hamming:local_ports"] = 0
            self.setParameters(
                _params,
                False,
                self.global_router_id,
                -1,
                [-1, -1],
                [-1, -1],
                [[-1, -1], [-1, -1]],
                [1, col],
                [1, router_level_2],
            )
            _params["hamming:link_width"] = int(down_ports / num_swithes_second_level)
            _params["hamming:switches_first_level"] = num_switches_first_level
            _params["hamming:jf_ft_nodes"] = (
                self.jf_ft_nodes if self.use_jellyfish else 0
            )
            swap_keys = [
                ("hamming:algorithm", "algorithm"),
                ("hamming:jf_ft_nodes", "jf_ft_nodes"),
                ("hamming:shape", "shape"),
                ("hamming:fat_tree_shape", "fat_tree_shape"),
                ("hamming:width", "width"),
                ("hamming:board_shape", "board_shape"),
                ("hamming:local_ports", "local_ports"),
                ("hamming:global_shape", "global_shape"),
                ("hamming:is_board_switch", "is_board_switch"),
                ("hamming:global_switch_id", "global_switch_id"),
                ("hamming:local_switch_id", "local_switch_id"),
                ("hamming:global_pos", "global_pos"),
                ("hamming:local_pos", "local_pos"),
                ("hamming:unique_pos", "unique_pos"),
                ("hamming:fat_tree_id", "fat_tree_id"),
                ("hamming:fat_tree_pos", "fat_tree_pos"),
                ("hamming:link_width", "link_width"),
                ("hamming:switches_first_level", "switches_first_level"),
            ]
            _topo_params = _params.subsetWithRename(swap_keys)
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", self.global_router_id)
            topology = rtr.setSubComponent("topology", "merlin.hamming")
            topology.addParams(_topo_params)
            self.global_router_id = self.global_router_id + 1
            name_rtr = "colx{}:{}x{}".format(col, 1, router_level_2)
            list_routers_second_level[name_rtr] = rtr

        # Wire edge-to-core inter-level links
        starting_port_2_down = 0

        starting_port_down = [None] * num_swithes_second_level
        links_num = int(down_ports / num_swithes_second_level)

        for idx_2 in range(0, num_swithes_second_level):
            starting_port_down[idx_2] = list()
            for idx in range(0, num_switches_first_level):
                starting_port_down[idx_2].append(idx * links_num)

        starting_port_1_up = int(down_ports)

        for link_num in range(links_num):
            for router_level_2 in range(num_swithes_second_level):
                for router_level_1 in range(num_switches_first_level):
                    name_rtr_1 = "colx{}:{}x{}".format(col, 0, router_level_1)
                    rtr_1 = list_routers_first_level[name_rtr_1]

                    name_rtr_2 = "colx{}:{}x{}".format(col, 1, router_level_2)
                    rtr_2 = list_routers_second_level[name_rtr_2]

                    rtr_1.addLink(
                        getLink(name_rtr_1, name_rtr_2, link_num),
                        "port%d" % starting_port_1_up,
                        _params["link_lat"],
                    )
                    rtr_2.addLink(
                        getLink(name_rtr_1, name_rtr_2, link_num),
                        "port%d" % starting_port_down[router_level_2][router_level_1],
                        _params["link_lat"],
                    )

                    starting_port_down[router_level_2][router_level_1] = (
                        starting_port_down[router_level_2][router_level_1] + 1
                    )

                starting_port_1_up = starting_port_1_up + 1

            starting_port_2_down = starting_port_2_down + 1

        return 1

    def _get_reserved_ports(self, local_id):
        """For Jellyfish boards: determine which ports are reserved for fat tree connections.
        Returns dict: port_number -> 'row_ft' or 'col_ft'

        When jf_ft_nodes > 0: uses randomly-selected gateway nodes stored in _jf_gateway_map.
          - row FT gateways use port 3 (W)
          - col FT gateways use port 0 (N)
        Otherwise: original border-position logic (mirrors mesh convention)."""
        reserved = {}
        if self.jf_ft_nodes > 0:
            gw = self._jf_gateway_map.get(self._current_board_id, {})
            if local_id in gw.get("row_ft", set()):
                reserved[3] = "row_ft"  # W port -> row fat tree
            if local_id in gw.get("col_ft", set()):
                reserved[0] = "col_ft"  # N port -> col fat tree
        else:
            row = local_id // self.dims[1]
            col = local_id % self.dims[1]
            if row == 0:
                reserved[0] = "col_ft"  # N port -> col fat tree
            if col == self.dims[1] - 1:
                reserved[1] = "row_ft"  # E port -> row fat tree
            if row == self.dims[0] - 1:
                reserved[2] = "col_ft"  # S port -> col fat tree
            if col == 0:
                reserved[3] = "row_ft"  # W port -> row fat tree
        return reserved

    def _compute_jf_gateways(self, board_id):
        """Select fat-tree gateway nodes so that a Jellyfish board has EXACTLY the
        same number of board<->fat-tree uplinks as the 2D-mesh variant.

        The mesh connects every perimeter node to a fat tree (see the
        ``isFirstOrLast`` logic in createRowFatTree/createColFatTree):
          - row fat tree: nodes in the first and last board column -> 2*dims[0] links/board
          - col fat tree: nodes in the first and last board row    -> 2*dims[1] links/board

        We mirror that exact node selection. Because the selected set is
        identical in size and per-global-row/col distribution to the mesh,
        ``_count_jf_ft_connections`` returns the same node counts the mesh uses
        (global_shape*2), so the fat-tree radix/sizing and total global
        bandwidth are identical to the mesh. The ONLY difference from the mesh
        is the local board fabric (a Jellyfish random graph instead of a 2D
        mesh) and that each gateway uses a single fixed port (row -> 3 'W',
        col -> 0 'N'); a corner node is a gateway for both directions and uses
        both ports, exactly like a mesh corner.

        NOTE: with this scheme jf_ft_nodes only acts as an on/off switch for
        "Jellyfish-as-fat-tree-leaf" mode; its magnitude (e.g. 1 vs 2) no longer
        changes the topology, so the ft1 and ft2 variants are now identical."""
        rows, cols = self.dims[0], self.dims[1]
        row_ft = set()
        col_ft = set()
        for local_id in range(rows * cols):
            r = local_id // cols
            c = local_id % cols
            if c == 0 or c == cols - 1:
                row_ft.add(local_id)  # first/last column -> row fat tree (port 3)
            if r == 0 or r == rows - 1:
                col_ft.add(local_id)  # first/last row -> col fat tree (port 0)
        self._jf_gateway_map[board_id] = {
            "row_ft": row_ft,
            "col_ft": col_ft,
        }

    def _count_jf_ft_connections(
        self, ft_type, fixed_axis, fixed_global_idx, total_varying
    ):
        """Count how many gateway connections exist for a given fat tree row or col.
        ft_type:          'row_ft' or 'col_ft'
        fixed_axis:       'row' (row fat tree, fixed global row) or 'col' (col fat tree)
        fixed_global_idx: the global row or col index being built
        total_varying:    total number of positions in the varying axis"""
        count = 0
        for v in range(total_varying):
            if fixed_axis == "row":
                global_row, global_col = fixed_global_idx, v
            else:
                global_row, global_col = v, fixed_global_idx
            board_id = (global_row // self.dims[0]) * self.global_shape[1] + (
                global_col // self.dims[1]
            )
            local_id = (global_row % self.dims[0]) * self.dims[1] + (
                global_col % self.dims[1]
            )
            if local_id in self._jf_gateway_map.get(board_id, {}).get(ft_type, set()):
                count += 1
        return count

    def _generate_jellyfish_graph(self, num_nodes, reserved_ports_per_node):
        """Generate a random graph for a board. Each node has 4 inter-router ports (0-3).
        Some ports are reserved for fat trees. Remaining ports are used for random intra-board links.
        Returns: adjacency dict {node_id: [(neighbor_id, my_port, their_port), ...]}, port_map dict {node_id: {port: neighbor_id}}"""
        import random

        # Determine available (non-reserved) ports per node
        available = {}  # node -> list of free port numbers
        for n in range(num_nodes):
            reserved = reserved_ports_per_node.get(n, {})
            available[n] = [p for p in range(4) if p not in reserved]

        # First attempt: greedy without multi-edges (preferred for clean Jellyfish graph)
        max_attempts = 100
        for attempt in range(max_attempts):
            stubs = []
            for n in range(num_nodes):
                for p in available[n]:
                    stubs.append((n, p))
            random.shuffle(stubs)

            adjacency = {n: [] for n in range(num_nodes)}
            port_map = {n: {} for n in range(num_nodes)}
            used_pairs = set()
            paired = [False] * len(stubs)
            for i in range(len(stubs)):
                if paired[i]:
                    continue
                n1, p1 = stubs[i]
                for j in range(i + 1, len(stubs)):
                    if paired[j]:
                        continue
                    n2, p2 = stubs[j]
                    if n1 == n2:
                        continue
                    pair_key = (min(n1, n2), max(n1, n2))
                    if pair_key in used_pairs:
                        continue
                    paired[i] = True
                    paired[j] = True
                    adjacency[n1].append((n2, p1, p2))
                    adjacency[n2].append((n1, p2, p1))
                    port_map[n1][p1] = n2
                    port_map[n2][p2] = n1
                    used_pairs.add(pair_key)
                    break

            if sum(1 for p in paired if not p) == 0:
                return adjacency, port_map

        # Fallback: degree-ordered matching that allows multi-edges and is guaranteed to
        # find a perfect matching whenever one exists (Hall's theorem holds for this topology).
        # This handles small boards (e.g. 2x2 with ft_nodes=1) where the number of free
        # port stubs exceeds the number of distinct node pairs.
        print(
            "WARNING: Jellyfish graph using degree-ordered matching (multi-edges allowed)."
        )
        # Build per-node stub queues, shuffled for randomness
        stubs_per_node = {}
        for n in range(num_nodes):
            ports = list(available[n])
            random.shuffle(ports)
            stubs_per_node[n] = ports

        adjacency = {n: [] for n in range(num_nodes)}
        port_map = {n: {} for n in range(num_nodes)}

        total_stubs = sum(len(s) for s in stubs_per_node.values())
        for _ in range(total_stubs // 2):
            # Pick the node with the most remaining stubs as n1
            remaining = [(len(s), n) for n, s in stubs_per_node.items() if s]
            if not remaining:
                break
            remaining.sort(reverse=True)
            n1 = remaining[0][1]
            p1 = stubs_per_node[n1].pop()

            # Pick the node with the next most remaining stubs (different from n1) as n2
            found = False
            for _, n2 in remaining:
                if n2 == n1 or not stubs_per_node[n2]:
                    continue
                p2 = stubs_per_node[n2].pop()
                adjacency[n1].append((n2, p1, p2))
                adjacency[n2].append((n1, p2, p1))
                port_map[n1][p1] = n2
                port_map[n2][p2] = n1
                found = True
                break

            if not found:
                print(
                    "ERROR: stub (%d, %d) has no eligible partner — port will be unwired!"
                    % (n1, p1)
                )

        # Ensure the graph is connected: perform edge swaps between disconnected components.
        # This is necessary for small boards (e.g. 2x2 with ft_nodes=1) where the
        # degree-ordered matching can produce isolated cliques.
        adjacency, port_map = self._ensure_connected(adjacency, port_map, num_nodes)

        return adjacency, port_map

    def _ensure_connected(self, adjacency, port_map, num_nodes):
        """Post-process a generated graph: perform edge swaps to connect any isolated components.
        Each edge swap removes one intra-component edge from each of two disconnected components
        and replaces them with two cross-component edges, merging the components."""

        def get_component(start):
            comp = set()
            stack = [start]
            while stack:
                n = stack.pop()
                if n in comp:
                    continue
                comp.add(n)
                for neighbor, _, _ in adjacency[n]:
                    if neighbor not in comp:
                        stack.append(neighbor)
            return comp

        for _ in range(num_nodes * num_nodes):
            comp1 = get_component(0)
            if len(comp1) == num_nodes:
                break  # fully connected

            comp2_node = next(n for n in range(num_nodes) if n not in comp1)
            comp2 = get_component(comp2_node)

            # Find an intra-comp1 edge
            edge1 = None
            for a in comp1:
                for b, pa, pb in adjacency[a]:
                    if b in comp1:
                        edge1 = (a, b, pa, pb)
                        break
                if edge1:
                    break

            # Find an intra-comp2 edge
            edge2 = None
            for c in comp2:
                for d, pc, pd in adjacency[c]:
                    if d in comp2:
                        edge2 = (c, d, pc, pd)
                        break
                if edge2:
                    break

            if edge1 is None or edge2 is None:
                print(
                    "WARNING: _ensure_connected could not find intra-component edges to swap"
                )
                break

            a, b, pa, pb = edge1
            c, d, pc, pd = edge2

            # Remove edge (a, b) — use first match with matching port (handles multi-edges)
            for i, (n, mp, tp) in enumerate(adjacency[a]):
                if n == b and mp == pa:
                    adjacency[a].pop(i)
                    break
            for i, (n, mp, tp) in enumerate(adjacency[b]):
                if n == a and mp == pb:
                    adjacency[b].pop(i)
                    break
            port_map[a].pop(pa, None)
            port_map[b].pop(pb, None)

            # Remove edge (c, d)
            for i, (n, mp, tp) in enumerate(adjacency[c]):
                if n == d and mp == pc:
                    adjacency[c].pop(i)
                    break
            for i, (n, mp, tp) in enumerate(adjacency[d]):
                if n == c and mp == pd:
                    adjacency[d].pop(i)
                    break
            port_map[c].pop(pc, None)
            port_map[d].pop(pd, None)

            # Add cross-component edges (a, c) and (b, d)
            adjacency[a].append((c, pa, pc))
            adjacency[c].append((a, pc, pa))
            port_map[a][pa] = c
            port_map[c][pc] = a

            adjacency[b].append((d, pb, pd))
            adjacency[d].append((b, pd, pb))
            port_map[b][pb] = d
            port_map[d][pd] = b

        return adjacency, port_map

    def _compute_routing_tables(self, num_nodes, port_map):
        """Compute shortest-path routing tables using BFS.
        Returns: dict {src: {dst: next_hop_port}} for all src, dst pairs."""
        from collections import deque

        # Build adjacency from port_map: node -> [(neighbor, port_to_neighbor)]
        adj = {n: [] for n in range(num_nodes)}
        for n in range(num_nodes):
            for port, neighbor in port_map[n].items():
                adj[n].append((neighbor, port))

        routing_tables = {}
        for src in range(num_nodes):
            # BFS from src
            visited = {src: None}  # node -> (prev_node, port_from_prev)
            queue = deque([src])
            while queue:
                current = queue.popleft()
                for neighbor, port in adj[current]:
                    if neighbor not in visited:
                        visited[neighbor] = (current, port)
                        queue.append(neighbor)

            # Build routing table: for each dest, trace back to find first hop port from src
            table = {}
            for dst in range(num_nodes):
                if dst == src:
                    table[dst] = -1  # self, will deliver to NIC
                    continue
                if dst not in visited:
                    table[dst] = -1  # unreachable (shouldn't happen in connected graph)
                    continue
                # Trace back from dst to src to find first hop
                node = dst
                while visited[node][0] != src:
                    node = visited[node][0]
                table[dst] = visited[node][1]  # port from src toward dst

            routing_tables[src] = table

        return routing_tables

    def _find_nearest_edges(self, num_nodes, routing_tables, reserved_ports_per_node):
        """For each node, find the nearest row-edge and col-edge node (by hop count).
        Returns: dict {node_id: {'nearest_row_edge': local_id, 'nearest_col_edge': local_id}}"""
        from collections import deque

        # Classify edge nodes
        row_edge_nodes = set()
        col_edge_nodes = set()
        for n in range(num_nodes):
            reserved = reserved_ports_per_node.get(n, {})
            for port, ft_type in reserved.items():
                if ft_type == "row_ft":
                    row_edge_nodes.add(n)
                elif ft_type == "col_ft":
                    col_edge_nodes.add(n)

        result = {}
        for src in range(num_nodes):
            table = routing_tables[src]
            # Find nearest row edge (fewest hops)
            nearest_row = -1
            min_row_hops = 9999
            for edge_node in row_edge_nodes:
                if edge_node == src:
                    nearest_row = src
                    min_row_hops = 0
                    break
                # Count hops by tracing routing table
                hops = 0
                node = src
                visited = set()
                while node != edge_node and hops < num_nodes:
                    next_port = table.get(edge_node, -1)
                    if next_port < 0:
                        break
                    # We don't have easy hop tracing from routing_tables alone,
                    # so just use BFS distance
                    hops = num_nodes  # will be overridden below
                    break
                # Use BFS distance instead
            # Simpler: just BFS from src and record distances
            # (We already have routing tables, but let's compute distances directly)

            nearest_row = -1
            nearest_col = -1
            result[src] = {"nearest_row_edge": -1, "nearest_col_edge": -1}

            if src in row_edge_nodes:
                result[src]["nearest_row_edge"] = src
            else:
                # Find closest row edge by hop count (trace routing table)
                best_dist = 9999
                for edge_n in row_edge_nodes:
                    dist = self._hop_distance(
                        src, edge_n, routing_tables[src], routing_tables
                    )
                    if dist < best_dist:
                        best_dist = dist
                        result[src]["nearest_row_edge"] = edge_n

            if src in col_edge_nodes:
                result[src]["nearest_col_edge"] = src
            else:
                best_dist = 9999
                for edge_n in col_edge_nodes:
                    dist = self._hop_distance(
                        src, edge_n, routing_tables[src], routing_tables
                    )
                    if dist < best_dist:
                        best_dist = dist
                        result[src]["nearest_col_edge"] = edge_n

        return result

    def _hop_distance(self, src, dst, src_table, all_tables):
        """Count hops from src to dst using routing tables."""
        if src == dst:
            return 0
        hops = 0
        current = src
        visited = set()
        while current != dst and hops < 100:
            if current in visited:
                return 9999  # loop
            visited.add(current)
            next_port = all_tables[current].get(dst, -1)
            if next_port < 0:
                return 9999
            # Find which neighbor is on that port
            # We need port_map for this - store it on self
            neighbor = self._current_port_map.get(current, {}).get(next_port, -1)
            if neighbor < 0:
                return 9999
            current = neighbor
            hops += 1
        return hops

    def _wire_jellyfish_board(self, board_routers_info, board_id, _params, getLink):
        """Wire a board as a Jellyfish random graph instead of a 2D mesh.
        Also creates NIC connections and sets routing table parameters."""
        num_nodes = len(board_routers_info)

        # Determine reserved ports for each node (fat tree connections)
        reserved_ports = {}
        for info in board_routers_info:
            reserved_ports[info["local_id"]] = self._get_reserved_ports(
                info["local_id"]
            )

        # Generate random Jellyfish graph
        adjacency, port_map = self._generate_jellyfish_graph(num_nodes, reserved_ports)
        self._current_port_map = port_map  # Store for hop distance calculation

        # Compute shortest-path routing tables
        routing_tables = self._compute_routing_tables(num_nodes, port_map)

        # Find nearest edge nodes for inter-board routing
        nearest_edges = self._find_nearest_edges(
            num_nodes, routing_tables, reserved_ports
        )

        # Board-wide lists of ALL row-FT / col-FT gateway nodes. These are identical
        # for every switch on the board and let the router spread inter-board traffic
        # across all gateways (deterministically, as a function of the destination)
        row_gateways = sorted(
            n
            for n in range(num_nodes)
            if "row_ft" in reserved_ports.get(n, {}).values()
        )
        col_gateways = sorted(
            n
            for n in range(num_nodes)
            if "col_ft" in reserved_ports.get(n, {}).values()
        )
        row_gw_str = ",".join(str(n) for n in row_gateways)
        col_gw_str = ",".join(str(n) for n in col_gateways)

        # Wire up the Jellyfish links and set parameters
        # Deduplication is per-port (not per-node-pair) to correctly handle multi-edges:
        # multi-edges can arise on small boards where free ports exceed distinct node pairs.
        created_ports = set()  # Track (node_id, port) pairs that already have a link
        for info in board_routers_info:
            local_id = info["local_id"]
            rtr = info["rtr"]
            my_str = info["my_str"]
            topology = info["topology"]
            reserved = reserved_ports.get(local_id, {})

            # Create Jellyfish inter-router links
            for neighbor_id, my_port, their_port in adjacency[local_id]:
                port_key = (local_id, my_port)
                if port_key in created_ports:
                    continue
                created_ports.add(port_key)
                created_ports.add((neighbor_id, their_port))
                partner_info = board_routers_info[neighbor_id]
                partner_str = partner_info["my_str"]
                # Include port numbers in link name so multi-edges get distinct link objects
                link_name = "jflink.%s.p%d:%s.p%d" % (
                    my_str,
                    my_port,
                    partner_str,
                    their_port,
                )
                link = sst.Link(link_name)
                rtr.addLink(link, "port%d" % my_port, _params["link_lat"])
                partner_info["rtr"].addLink(
                    link, "port%d" % their_port, _params["link_lat"]
                )

            # Create NIC connection (port 4 = last port before local ports)
            nic_port = 4  # Same as mesh: ports 0-3 are inter-router, port 4 is NIC
            for n in range(_params["hamming:local_ports"]):
                # global_router_id was already incremented; compute the correct one
                global_id = info["local_id"]  # Need to use the stored global ID
                # Actually, we need the global router ID. Let's compute it from board_id
                switches_per_board = self.switch_per_board
                global_rtr_id = board_id * switches_per_board + local_id
                nodeID = int(_params["hamming:local_ports"]) * global_rtr_id + n
                ep = self._getEndPoint(nodeID).build(nodeID, {})
                if ep:
                    nicLink = sst.Link("nic.%d:%d" % (global_rtr_id, n))
                    if self.bundleEndpoints:
                        nicLink.setNoCut()
                    nicLink.connect(ep, (rtr, "port%d" % nic_port, _params["link_lat"]))
                nic_port += 1

            # Set Jellyfish-specific parameters on the topology subcomponent
            rt_str = ",".join(
                str(routing_tables[local_id].get(d, -1)) for d in range(num_nodes)
            )

            # Determine fat tree port numbers for this node
            row_ft_port = -1
            col_ft_port = -1
            for port, ft_type in reserved.items():
                if ft_type == "row_ft":
                    row_ft_port = port
                elif ft_type == "col_ft":
                    col_ft_port = port

            # Per-switch hop-distance table: dist[d] = hops from this switch to local d.
            # Used for the intra-board fat-tree shortcut cost check.
            dist_str = ",".join(
                str(
                    self._hop_distance(
                        local_id, d, routing_tables[local_id], routing_tables
                    )
                )
                for d in range(num_nodes)
            )

            topology.addParam("is_jellyfish", True)
            topology.addParam("routing_table", rt_str)
            topology.addParam("row_ft_port", row_ft_port)
            topology.addParam("col_ft_port", col_ft_port)
            topology.addParam(
                "nearest_row_edge", nearest_edges[local_id]["nearest_row_edge"]
            )
            topology.addParam(
                "nearest_col_edge", nearest_edges[local_id]["nearest_col_edge"]
            )
            topology.addParam("row_ft_gateways", row_gw_str)
            topology.addParam("col_ft_gateways", col_gw_str)
            topology.addParam("dist_table", dist_str)

    def build(self):
        # Temp
        links = dict()

        def getLink(leftName, rightName):
            name = "link.%s:%s" % (leftName, rightName)
            if name not in links:
                links[name] = sst.Link(name)
            return links[name]

        # Initialize variables
        local_router_id = 0
        glob_col_offest = 0
        glob_row_offest = 0
        tmp_boards_per_row = self.global_shape[1]
        board_routers_info = []  # Collect router info per board for Jellyfish wiring

        # Start building each individual mesh, assign ids and connect links (leaving empty links for fat tree)
        for board_id in range(0, self.num_boards):
            board_routers_info = []  # Reset for each board
            for router_in_board in range(0, self.switch_per_board):
                mydims = self._idToLoc(local_router_id)
                my_loc_id = self.getLocalDims(local_router_id)
                my_glob_id = list(my_loc_id)
                # my_glob_id = my_loc_id.copy()
                my_glob_id[0] = my_loc_id[0] + glob_row_offest
                my_glob_id[1] = my_loc_id[1] + glob_col_offest
                unique_pos = self.getUniquePos(my_loc_id, board_id)
                # print("I am router {} (global) {} (local) - loc_pos {} - glob_pos {} - Unique pos {}".format(self.global_router_id, local_router_id, my_loc_id, my_glob_id, unique_pos))
                self.global_to_local[self.GlobalToString(my_glob_id)] = unique_pos

                # Create Router instance
                rtr = self._instanceRouter(self.global_router_id, "merlin.hr_router")
                my_str = self.getRouterNameString(
                    self.getUniquePos(my_loc_id, board_id)
                )
                self.list_routers[my_str] = rtr

                # Add parameters to topology object
                self.setParameters(
                    _params,
                    True,
                    self.global_router_id,
                    local_router_id,
                    my_glob_id,
                    my_loc_id,
                    unique_pos,
                    -1,
                    [-1, -1],
                )
                swap_keys = [
                    ("hamming:shape", "shape"),
                    ("hamming:fat_tree_shape", "fat_tree_shape"),
                    ("hamming:board_shape", "board_shape"),
                    ("hamming:width", "width"),
                    ("hamming:local_ports", "local_ports"),
                    ("hamming:global_shape", "global_shape"),
                    ("hamming:is_board_switch", "is_board_switch"),
                    ("hamming:global_switch_id", "global_switch_id"),
                    ("hamming:local_switch_id", "local_switch_id"),
                    ("hamming:global_pos", "global_pos"),
                    ("hamming:local_pos", "local_pos"),
                    ("hamming:unique_pos", "unique_pos"),
                    ("hamming:fat_tree_id", "fat_tree_id"),
                    ("hamming:fat_tree_pos", "fat_tree_pos"),
                    ("hamming:algorithm", "algorithm"),
                    ("hamming:is_jellyfish", "is_jellyfish"),
                    ("hamming:routing_table", "routing_table"),
                    ("hamming:row_ft_port", "row_ft_port"),
                    ("hamming:col_ft_port", "col_ft_port"),
                    ("hamming:nearest_row_edge", "nearest_row_edge"),
                    ("hamming:nearest_col_edge", "nearest_col_edge"),
                    ("hamming:row_ft_gateways", "row_ft_gateways"),
                    ("hamming:col_ft_gateways", "col_ft_gateways"),
                    ("hamming:dist_table", "dist_table"),
                ]
                _topo_params = _params.subsetWithRename(swap_keys)
                rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
                rtr.addParam("id", self.global_router_id)
                topology = rtr.setSubComponent("topology", "merlin.hamming")
                topology.addParams(_topo_params)

                # Store router info for Jellyfish wiring (done per-board after all routers created)
                board_routers_info.append(
                    {
                        "rtr": rtr,
                        "local_id": router_in_board,
                        "my_str": my_str,
                        "my_loc_id": list(my_loc_id),
                        "topology": topology,
                    }
                )

                if not self.use_jellyfish:
                    # Original mesh wiring: iterate in each direction and create links
                    port = 0
                    for direction in range(0, 4):
                        # Find Partner
                        offset = self.getOffsetPerDirection(direction)
                        partner_pos = list(my_loc_id)
                        partner_pos[0] = partner_pos[0] + offset[0]
                        partner_pos[1] = partner_pos[1] + offset[1]
                        partner_str = self.getRouterNameString(
                            self.getUniquePos(partner_pos, board_id)
                        )

                        # Create Links
                        if self.isInsideBoard(partner_pos):
                            if direction <= 1:
                                rtr.addLink(
                                    getLink(my_str, partner_str),
                                    "port%d" % port,
                                    _params["link_lat"],
                                )
                            else:
                                rtr.addLink(
                                    getLink(partner_str, my_str),
                                    "port%d" % port,
                                    _params["link_lat"],
                                )
                        port = port + 1

                if not self.use_jellyfish:
                    # Create NIC connection (mesh mode - port is already at 4)
                    for n in range(_params["hamming:local_ports"]):
                        nodeID = (
                            int(_params["hamming:local_ports"]) * self.global_router_id
                            + n
                        )
                        ep = self._getEndPoint(nodeID).build(nodeID, {})
                        if ep:
                            nicLink = sst.Link("nic.%d:%d" % (self.global_router_id, n))
                            if self.bundleEndpoints:
                                nicLink.setNoCut()
                            nicLink.connect(
                                ep, (rtr, "port%d" % port, _params["link_lat"])
                            )
                        port = port + 1

                # Update IDs
                local_router_id = local_router_id + 1
                self.global_router_id = self.global_router_id + 1

            # After all routers in this board are created, do Jellyfish wiring if enabled
            if self.use_jellyfish and board_routers_info:
                self._current_board_id = board_id
                if self.jf_ft_nodes > 0:
                    self._compute_jf_gateways(board_id)
                self._wire_jellyfish_board(
                    board_routers_info, board_id, _params, getLink
                )
                board_routers_info = []

            # Decrease how many boards we have left per this row or start a new row
            tmp_boards_per_row = tmp_boards_per_row - 1
            if tmp_boards_per_row > 0:
                glob_col_offest = glob_col_offest + self.dims[1]
            elif tmp_boards_per_row == 0:
                glob_col_offest = 0
                tmp_boards_per_row = self.global_shape[1]
                glob_row_offest = glob_row_offest + self.dims[0]
            # New Board, reset local router id
            local_router_id = 0

        total_rows = self.global_shape[0] * self.dims[0]
        total_cols = self.global_shape[1] * self.dims[1]
        # Create fat tree,  first row wise
        for row in range(total_rows):
            # Determine node count (may vary per row when using custom Jellyfish gateways)
            if self.use_jellyfish and self.jf_ft_nodes > 0:
                nodes_count = self._count_jf_ft_connections(
                    "row_ft", "row", row, total_cols
                )
                if nodes_count == 0:
                    continue  # no gateways in this global row; skip fat tree
            else:
                nodes_count = self.global_shape[1] * 2

            # Iterate all routers of this row and connect them to the router
            if nodes_count > self.radix_fat_tree_switches:
                self.createRowFatTree(nodes_count, total_cols, row, -1)
            else:
                # Here, for now, we just create a single router to connect everything
                # Create single Router instance
                port = 0
                rtr = self._instanceRouter(self.global_router_id, "merlin.hr_router")
                _params["num_ports"] = _params["router_radix"] = nodes_count
                _params["hamming:local_ports"] = 0
                self.setParameters(
                    _params,
                    False,
                    self.global_router_id,
                    -1,
                    [-1, -1],
                    [-1, -1],
                    [[-1, -1], [-1, -1]],
                    [0, row],
                    [0, 0],
                )
                _params["hamming:single_switch_fat_tree"] = True
                _params["hamming:jf_ft_nodes"] = (
                    self.jf_ft_nodes if self.use_jellyfish else 0
                )
                swap_keys = [
                    ("hamming:algorithm", "algorithm"),
                    ("hamming:single_switch_fat_tree", "single_switch_fat_tree"),
                    ("hamming:jf_ft_nodes", "jf_ft_nodes"),
                    ("hamming:shape", "shape"),
                    ("hamming:width", "width"),
                    ("hamming:board_shape", "board_shape"),
                    ("hamming:local_ports", "local_ports"),
                    ("hamming:global_shape", "global_shape"),
                    ("hamming:is_board_switch", "is_board_switch"),
                    ("hamming:global_switch_id", "global_switch_id"),
                    ("hamming:local_switch_id", "local_switch_id"),
                    ("hamming:global_pos", "global_pos"),
                    ("hamming:local_pos", "local_pos"),
                    ("hamming:unique_pos", "unique_pos"),
                    ("hamming:fat_tree_id", "fat_tree_id"),
                    ("hamming:fat_tree_pos", "fat_tree_pos"),
                ]
                _topo_params = _params.subsetWithRename(swap_keys)
                rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
                rtr.addParam("id", self.global_router_id)
                topology = rtr.setSubComponent("topology", "merlin.hamming")
                topology.addParams(_topo_params)
                self.global_router_id = self.global_router_id + 1
                name_rtr = "rowx{}".format(row)

                # Iterate all routers of this row and connect them to the router
                for col in range(total_cols):
                    if self.use_jellyfish and self.jf_ft_nodes > 0:
                        board_id_ft = (row // self.dims[0]) * self.global_shape[1] + (
                            col // self.dims[1]
                        )
                        local_id_ft = (row % self.dims[0]) * self.dims[1] + (
                            col % self.dims[1]
                        )
                        should_connect = local_id_ft in self._jf_gateway_map.get(
                            board_id_ft, {}
                        ).get("row_ft", set())
                        my_port = 3
                    else:
                        should_connect = self.isFirstOrLast(col, self.dims[1])
                        isFirst = self.isFirst(col, self.dims[1])
                        my_port = 3 if isFirst else 1
                    if should_connect:
                        # Connect from Fat Tree router to board router
                        unique_pos = self.global_to_local[
                            self.GlobalToString([row, col])
                        ]
                        partner_str = self.getRouterNameString((unique_pos))

                        # print("Connecting {} to {} with port {}".format(name_rtr, partner_str, port))
                        rtr.addLink(
                            getLink(name_rtr, partner_str),
                            "port%d" % port,
                            _params["link_lat"],
                        )

                        # Connect from board router to fat tree router
                        # print("Connecting {} to {} with port {}".format(partner_str, name_rtr, my_port))
                        other_rtr = self.list_routers[partner_str]
                        other_rtr.addLink(
                            getLink(name_rtr, partner_str),
                            "port%d" % my_port,
                            _params["link_lat"],
                        )

                        port = port + 1

        # Fat Tree Col wise
        for col in range(total_cols):
            # Determine node count (may vary per col when using custom Jellyfish gateways)
            if self.use_jellyfish and self.jf_ft_nodes > 0:
                nodes_count = self._count_jf_ft_connections(
                    "col_ft", "col", col, total_rows
                )
                if nodes_count == 0:
                    continue  # no gateways in this global col; skip fat tree
            else:
                nodes_count = self.global_shape[0] * 2

            # Here, for now, we just create a single router to connect everything
            # Create single Router instance
            if nodes_count > self.radix_fat_tree_switches:
                self.createColFatTree(nodes_count, total_rows, -1, col)
            else:
                # Here, for now, we just create a single router to connect everything
                # Create single Router instance
                port = 0
                rtr = self._instanceRouter(self.global_router_id, "merlin.hr_router")
                _params["num_ports"] = _params["router_radix"] = nodes_count
                _params["hamming:local_ports"] = 0
                self.setParameters(
                    _params,
                    False,
                    self.global_router_id,
                    -1,
                    [-1, -1],
                    [-1, -1],
                    [[-1, -1], [-1, -1]],
                    [1, col],
                    [0, 0],
                )
                _params["hamming:single_switch_fat_tree"] = True
                _params["hamming:jf_ft_nodes"] = (
                    self.jf_ft_nodes if self.use_jellyfish else 0
                )
                swap_keys = [
                    ("hamming:algorithm", "algorithm"),
                    ("hamming:single_switch_fat_tree", "single_switch_fat_tree"),
                    ("hamming:jf_ft_nodes", "jf_ft_nodes"),
                    ("hamming:shape", "shape"),
                    ("hamming:width", "width"),
                    ("hamming:board_shape", "board_shape"),
                    ("hamming:local_ports", "local_ports"),
                    ("hamming:global_shape", "global_shape"),
                    ("hamming:is_board_switch", "is_board_switch"),
                    ("hamming:global_switch_id", "global_switch_id"),
                    ("hamming:local_switch_id", "local_switch_id"),
                    ("hamming:global_pos", "global_pos"),
                    ("hamming:local_pos", "local_pos"),
                    ("hamming:unique_pos", "unique_pos"),
                    ("hamming:fat_tree_id", "fat_tree_id"),
                    ("hamming:fat_tree_pos", "fat_tree_pos"),
                ]
                _topo_params = _params.subsetWithRename(swap_keys)
                rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
                rtr.addParam("id", self.global_router_id)
                topology = rtr.setSubComponent("topology", "merlin.hamming")
                topology.addParams(_topo_params)
                self.global_router_id = self.global_router_id + 1
                name_rtr = "colx{}".format(col)

                # Iterate all routers of this col and connect them to the router
                for row in range(total_rows):
                    if self.use_jellyfish and self.jf_ft_nodes > 0:
                        board_id_ft = (row // self.dims[0]) * self.global_shape[1] + (
                            col // self.dims[1]
                        )
                        local_id_ft = (row % self.dims[0]) * self.dims[1] + (
                            col % self.dims[1]
                        )
                        should_connect = local_id_ft in self._jf_gateway_map.get(
                            board_id_ft, {}
                        ).get("col_ft", set())
                        my_port = 0
                    else:
                        should_connect = self.isFirstOrLast(row, self.dims[0])
                        isFirst = self.isFirst(row, self.dims[0])
                        my_port = 0 if isFirst else 2
                    if should_connect:
                        # Connect from Fat Tree router to board router
                        unique_pos = self.global_to_local[
                            self.GlobalToString([row, col])
                        ]
                        partner_str = self.getRouterNameString((unique_pos))

                        # print("Connecting {} to {} with port {}".format(name_rtr, partner_str, port))
                        rtr.addLink(
                            getLink(name_rtr, partner_str),
                            "port%d" % port,
                            _params["link_lat"],
                        )

                        # Connect from board router to fat tree router
                        # print("Connecting {} to {} with port {}".format(partner_str, name_rtr, my_port))
                        other_rtr = self.list_routers[partner_str]
                        other_rtr.addLink(
                            getLink(name_rtr, partner_str),
                            "port%d" % my_port,
                            _params["link_lat"],
                        )

                        port = port + 1

        """
        total_rows = self.global_shape[0] * self.dims[0]
        total_cols = self.global_shape[1] * self.dims[1]
        # Create fat tree,  first row wise
        for row in range(total_rows):
            # Here, for now, we just create a single router to connect everything
            # Create single Router instance
            port = 0
            rtr = self._instanceRouter(self.global_router_id,"merlin.hr_router")
            _params["num_ports"] = _params["router_radix"] = self.global_shape[1] * 2
            _params["hamming:local_ports"] = 0
            self.setParameters(_params, False, global_router_id, -1, [-1,-1], [-1,-1],  [[-1, -1], [-1, -1]], -1, [0, row])
            swap_keys = [("hamming:shape","shape"),("hamming:fat_tree_shape","fat_tree_shape"), ("hamming:board_shape","board_shape"),("hamming:width","width"),("hamming:local_ports","local_ports"),("hamming:global_shape","global_shape"),("hamming:is_board_switch","is_board_switch"),("hamming:global_switch_id","global_switch_id"),("hamming:local_switch_id","local_switch_id"),("hamming:global_pos","global_pos"),("hamming:local_pos","local_pos"),("hamming:unique_pos","unique_pos"),("hamming:fat_tree_id","fat_tree_id"),("hamming:fat_tree_pos","fat_tree_pos")]
            _topo_params = _params.subsetWithRename(swap_keys)
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", global_router_id)
            topology = rtr.setSubComponent("topology","merlin.hamming")
            topology.addParams(_topo_params)
            global_router_id = global_router_id + 1
            name_rtr = "rowx{}".format(row)

            # Iterate all routers of this row and connect them to the router
            for col in range(total_cols):
                if (self.isFirstOrLast(col, self.dims[1])):
                    # Get if we are connecting to the first or last router
                    isFirst = self.isFirst(col, self.dims[1])
                    # Connect from Fat Tree router to board router
                    unique_pos = self.global_to_local[self.GlobalToString([row, col])]
                    partner_str = self.getRouterNameString((unique_pos))

                    #print("Connecting {} to {} with port {}".format(name_rtr, partner_str, port))
                    rtr.addLink(getLink(name_rtr, partner_str), "port%d"%port, _params["link_lat"])

                    # Connect from board router to fat tree router
                    if (isFirst):
                        my_port = 3
                    else:
                        my_port = 1

                    print("Connecting {} to {} with port {}".format(partner_str, name_rtr, my_port))
                    other_rtr = self.list_routers[partner_str]
                    other_rtr.addLink(getLink(name_rtr, partner_str), "port%d"%my_port, _params["link_lat"])

                    port = port + 1


        # Fat Tree Col wise
        for col in range(total_cols):
            # Here, for now, we just create a single router to connect everything
            # Create single Router instance
            port = 0
            rtr = self._instanceRouter(global_router_id,"merlin.hr_router")
            _params["num_ports"] = _params["router_radix"] = self.global_shape[0] * 2
            _params["hamming:local_ports"] = 0
            self.setParameters(_params, False, global_router_id, -1, [-1,-1], [-1,-1], [[-1, -1], [-1, -1]], -1, [1, col])
            swap_keys = [("hamming:shape","shape"),("hamming:width","width"), ("hamming:board_shape","board_shape"),("hamming:local_ports","local_ports"),("hamming:global_shape","global_shape"),("hamming:is_board_switch","is_board_switch"),("hamming:global_switch_id","global_switch_id"),("hamming:local_switch_id","local_switch_id"),("hamming:global_pos","global_pos"),("hamming:local_pos","local_pos"),("hamming:unique_pos","unique_pos"),("hamming:fat_tree_id","fat_tree_id"),("hamming:fat_tree_pos","fat_tree_pos")]
            _topo_params = _params.subsetWithRename(swap_keys)
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", global_router_id)
            topology = rtr.setSubComponent("topology","merlin.hamming")
            topology.addParams(_topo_params)
            global_router_id = global_router_id + 1
            name_rtr = "colx{}".format(col)

            # Iterate all routers of this row and connect them to the router
            for row in range(total_rows):
                if (self.isFirstOrLast(row, self.dims[0])):
                    # Get if we are connecting to the first or last router
                    isFirst = self.isFirst(row, self.dims[0])
                    # Connect from Fat Tree router to board router
                    unique_pos = self.global_to_local[self.GlobalToString([row, col])]
                    partner_str = self.getRouterNameString((unique_pos))

                    print("Connecting {} to {} with port {}".format(name_rtr, partner_str, port))
                    rtr.addLink(getLink(name_rtr, partner_str), "port%d"%port, _params["link_lat"])

                    # Connect from board router to fat tree router
                    if (isFirst):
                        my_port = 0
                    else:
                        my_port = 2

                    print("Connecting {} to {} with port {}".format(partner_str, name_rtr, my_port))
                    other_rtr = self.list_routers[partner_str]
                    other_rtr.addLink(getLink(name_rtr, partner_str), "port%d"%my_port, _params["link_lat"])

                    port = port + 1

        num_routers = self.getTotRoutersMeshes()
        for i in range(num_routers):
            # set up 'mydims'
            mydims = self._idToLoc(i)
            mylocstr = self._formatShape(mydims)
            print(mylocstr)

            rtr = self._instanceRouter(i,"merlin.hr_router")
            #rtr = sst.Component("rtr.%s"%mylocstr, "merlin.hr_router")
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", i)
            topology = rtr.setSubComponent("topology","merlin.hamming")
            topology.addParams(_topo_params)

            port = 0
            if (i < self.switch_per_board):
                for dim in range(self.nd):
                    theirdims = mydims[:]

                    # Positive direction
                    theirdims[dim] = (mydims[dim] +1 ) % self.dims[dim]
                    #print("Positive - I {}  Port {} mydims {} dims {} mylocstr {} theirdim {} dimwidths[dim] {}".format(str(i), port,
                    #mydims,self.dims, mylocstr, theirdims, self.dimwidths[dim]))
                    if (mydims[dim] + 1 <= self.dims[dim] - 1):
                        theirlocstr = self._formatShape(theirdims)
                        print("theirlocstr {} - getLink {}".format(theirlocstr, getLink(mylocstr, theirlocstr, 0)))
                        for num in range(self.dimwidths[dim]):
                            print("Yes Linking {} - I am {} - Partner is {} - Port {}".format(i, mylocstr, theirlocstr, port))
                            rtr.addLink(getLink(mylocstr, theirlocstr, num), "port%d"%port, _params["link_lat"])
                            port = port+1
                    else:
                        print("not linking")
                        port = port+1

                    # Negative direction
                    theirdims[dim] = ((mydims[dim] -1) +self.dims[dim]) % self.dims[dim]
                    #print("Negative - Router {} Port {} mydims {} dims {} mylocstr {} theirdim {}".format(str(i), port, mydims,self.dims, mylocstr, theirdims))
                    if ((mydims[dim] - 1) >= 0):
                        theirlocstr = self._formatShape(theirdims)
                        for num in range(self.dimwidths[dim]):
                            print("Yes Linking {} - I am {} - Partner is {} - Port {}".format(i, theirlocstr, mylocstr, port))
                            rtr.addLink(getLink(theirlocstr, mylocstr, num), "port%d"%port, _params["link_lat"])
                            port = port+1
                    else:
                        print("not linking2")
                        port = port+1

            for n in range(_params["hamming:local_ports"]):
                nodeID = int(_params["hamming:local_ports"]) * i + n
                print("Building NIC {} in router {} using port {}".format(nodeID, i, port))

                ep = self._getEndPoint(nodeID).build(nodeID, {})
                if ep:
                    nicLink = sst.Link("nic.%d:%d"%(i, n))
                    if self.bundleEndpoints:
                        nicLink.setNoCut()
                    nicLink.connect(ep, (rtr, "port%d"%port, _params["link_lat"]))
                port = port+1"""


class topoJellyfish(topoHamming):
    """Standalone, single-board Jellyfish topology (no fat tree, no global structure).

    This is its own topology (selected with --topo=jellyfish) used to benchmark the
    Jellyfish LOCAL board fabric in complete isolation. It subclasses topoHamming
    solely to reuse its proven helpers (prepParams, setParameters, getLocalDims,
    getUniquePos, _generate_jellyfish_graph, _ensure_connected,
    _compute_routing_tables, _find_nearest_edges, _wire_jellyfish_board); it does
    NOT inherit topoHamming.build(), so no fat tree or inter-board structure is
    created.

    Two overrides vs. topoHamming:
      * _get_reserved_ports() returns {} -> every node keeps all 4 inter-router
        ports for random links => a canonical 4-regular Jellyfish.
      * build() constructs exactly one board and stops; the compiled merlin.hamming
        router routes all (same-board) destinations via the per-node routing table
        (hamming.cc route_packet_jellyfish, Case 2) and never touches fat-tree
        ports, so single-board operation needs only the routing table.

    Expects hamming params with global_shape="1x1" and use_jellyfish=True (see
    networkConfig.HammingInfo / emberLoad.py jellyfish branch).
    """

    def getName(self):
        return "Jellyfish"

    def _get_reserved_ports(self, local_id):
        # No fat-tree port reservations: all 4 inter-router ports are free for
        # random Jellyfish links (canonical 4-regular random graph).
        return {}

    def build(self):
        if self.num_boards != 1 or self.global_shape != [1, 1]:
            print(
                "topoJellyfish: expected a single board (global_shape=1x1), got "
                "global_shape=%s, num_boards=%d" % (self.global_shape, self.num_boards)
            )
            sys.exit(1)
        if not self.use_jellyfish:
            print("topoJellyfish: requires hamming:use_jellyfish=True")
            sys.exit(1)

        links = dict()

        def getLink(leftName, rightName):
            name = "link.%s:%s" % (leftName, rightName)
            if name not in links:
                links[name] = sst.Link(name)
            return links[name]

        # Build the single board's switches. With one board there is no global
        # offset, so the global position equals the local position.
        board_id = 0
        board_routers_info = []
        for router_in_board in range(0, self.switch_per_board):
            local_router_id = router_in_board
            my_loc_id = self.getLocalDims(local_router_id)
            my_glob_id = list(my_loc_id)
            unique_pos = self.getUniquePos(my_loc_id, board_id)
            self.global_to_local[self.GlobalToString(my_glob_id)] = unique_pos

            # Create Router instance
            rtr = self._instanceRouter(self.global_router_id, "merlin.hr_router")
            my_str = self.getRouterNameString(unique_pos)
            self.list_routers[my_str] = rtr

            # Add parameters to topology object (jellyfish-specific params are set
            # per-router later by _wire_jellyfish_board).
            self.setParameters(
                _params,
                True,
                self.global_router_id,
                local_router_id,
                my_glob_id,
                my_loc_id,
                unique_pos,
                -1,
                [-1, -1],
            )
            swap_keys = [
                ("hamming:shape", "shape"),
                ("hamming:fat_tree_shape", "fat_tree_shape"),
                ("hamming:board_shape", "board_shape"),
                ("hamming:width", "width"),
                ("hamming:local_ports", "local_ports"),
                ("hamming:global_shape", "global_shape"),
                ("hamming:is_board_switch", "is_board_switch"),
                ("hamming:global_switch_id", "global_switch_id"),
                ("hamming:local_switch_id", "local_switch_id"),
                ("hamming:global_pos", "global_pos"),
                ("hamming:local_pos", "local_pos"),
                ("hamming:unique_pos", "unique_pos"),
                ("hamming:fat_tree_id", "fat_tree_id"),
                ("hamming:fat_tree_pos", "fat_tree_pos"),
                ("hamming:algorithm", "algorithm"),
                ("hamming:is_jellyfish", "is_jellyfish"),
                ("hamming:routing_table", "routing_table"),
                ("hamming:row_ft_port", "row_ft_port"),
                ("hamming:col_ft_port", "col_ft_port"),
                ("hamming:nearest_row_edge", "nearest_row_edge"),
                ("hamming:nearest_col_edge", "nearest_col_edge"),
            ]
            _topo_params = _params.subsetWithRename(swap_keys)
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", self.global_router_id)
            topology = rtr.setSubComponent("topology", "merlin.hamming")
            topology.addParams(_topo_params)

            board_routers_info.append(
                {
                    "rtr": rtr,
                    "local_id": router_in_board,
                    "my_str": my_str,
                    "my_loc_id": list(my_loc_id),
                    "topology": topology,
                }
            )
            self.global_router_id = self.global_router_id + 1

        # Wire the board as a pure Jellyfish random graph and attach NICs.
        # No fat tree is created.
        self._current_board_id = board_id
        self._wire_jellyfish_board(board_routers_info, board_id, _params, getLink)


class topoHyperX(Topo):
    def __init__(self):
        Topo.__init__(self)
        self.topoKeys = [
            "topology",
            "debug",
            "num_ports",
            "flit_size",
            "nic_link_bw",
            "link_bw",
            "xbar_bw",
            "hyperx:shape",
            "hyperx:width",
            "hyperx:local_ports",
            "input_latency",
            "output_latency",
            "input_buf_size",
            "output_buf_size",
        ]
        self.topoOptKeys = [
            "xbar_arb",
            "num_vns",
            "vn_remap",
            "vn_remap_shm",
            "portcontrol:output_arb",
            "portcontrol:arbitration:qos_settings",
            "portcontrol:arbitration:arb_vns",
            "portcontrol:arbitration:arb_vcs",
        ]

    def getName(self):
        return "HyperX"

    def prepParams(self):
        #        if "xbar_arb" not in _params:
        #            _params["xbar_arb"] = "merlin.xbar_arb_lru"
        peers = 1
        radix = 0
        self.dims = []
        self.dimwidths = []
        if not "hyperx:shape" in _params:
            self.nd = int(_params["num_dims"])
            for x in range(self.nd):
                print("Dim %d size:" % x)
                ds = int(input())
                self.dims.append(ds)
            _params["hyperx:shape"] = self._formatShape(self.dims)
        else:
            self.dims = [int(x) for x in _params["hyperx:shape"].split("x")]
            self.nd = len(self.dims)
        if not "hyperx:width" in _params:
            for x in range(self.nd):
                print("Dim %d width (# of links in this dimension):" % x)
                dw = int(input())
                self.dimwidths.append(dw)
            _params["hyperx:width"] = self._formatShape(self.dimwidths)
        else:
            self.dimwidths = [int(x) for x in _params["hyperx:width"].split("x")]

        local_ports = int(_params["hyperx:local_ports"])
        radix = local_ports
        for x in range(self.nd):
            radix += self.dimwidths[x] * (self.dims[x] - 1)

        for x in self.dims:
            peers = peers * x
        peers = peers * local_ports

        _params["num_peers"] = peers
        _params["num_dims"] = self.nd
        _params["topology"] = _params["topology"] = "merlin.hyperx"
        _params["debug"] = debug
        _params["num_ports"] = _params["router_radix"] = radix
        _params["hyperx:local_ports"] = local_ports

    def _formatShape(self, arr):
        return "x".join([str(x) for x in arr])

    def _idToLoc(self, rtr_id):
        foo = list()
        for i in range(self.nd - 1, 0, -1):
            div = 1
            for j in range(0, i):
                div = div * self.dims[j]
            value = rtr_id // div
            foo.append(value)
            rtr_id = rtr_id - (value * div)
        foo.append(rtr_id)
        foo.reverse()
        return foo

    def getRouterNameForId(self, rtr_id):
        return self.getRouterNameForLocation(self._idToLoc(rtr_id))

    def getRouterNameForLocation(self, location):
        return "rtr.%s" % (self._formatShape(location))

    def findRouterByLocation(self, location):
        return sst.findComponentByName(self.getRouterNameForLocation(location))

    def build(self):
        num_routers = _params["num_peers"] // _params["hyperx:local_ports"]
        links = dict()

        def getLink(name1, name2, num):
            # Sort name1 and name2 so order doesn't matter
            if str(name1) < str(name2):
                name = "link.%s:%s:%d" % (name1, name2, num)
            else:
                name = "link.%s:%s:%d" % (name2, name1, num)
            if name not in links:
                links[name] = sst.Link(name)
            # print("Getting link with name: %s"%name)
            return links[name]

        swap_keys = [
            ("hyperx:shape", "shape"),
            ("hyperx:width", "width"),
            ("hyperx:local_ports", "local_ports"),
            ("hyperx:algorithm", "algorithm"),
        ]

        _topo_params = _params.subsetWithRename(swap_keys)
        # loop through the routers to hook up links
        for i in range(num_routers):
            # set up 'mydims'
            mydims = self._idToLoc(i)
            mylocstr = self._formatShape(mydims)

            # print("Creating router %s (%d)"%(mylocstr,i))

            rtr = self._instanceRouter(i, "merlin.hr_router")
            # rtr = sst.Component("rtr.%s"%mylocstr, "merlin.hr_router")
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", i)
            topology = rtr.setSubComponent("topology", "merlin.hyperx")
            topology.addParams(_topo_params)

            port = 0
            # Connect to all routers that only differ in one location index
            for dim in range(self.nd):
                theirdims = mydims[:]

                # We have links to every other router in each dimension
                for router in range(self.dims[dim]):
                    if router != mydims[dim]:  # no link to ourselves
                        theirdims[dim] = router
                        theirlocstr = self._formatShape(theirdims)
                        # Hook up "width" number of links for this dimension
                        for num in range(self.dimwidths[dim]):
                            rtr.addLink(
                                getLink(mylocstr, theirlocstr, num),
                                "port%d" % port,
                                _params["link_lat"],
                            )
                            # print("Wired up port %d"%port)
                            port = port + 1

            for n in range(_params["hyperx:local_ports"]):
                nodeID = int(_params["hyperx:local_ports"]) * i + n
                ep = self._getEndPoint(nodeID).build(nodeID, {})
                if ep:
                    nicLink = sst.Link("nic.%d:%d" % (i, n))
                    if self.bundleEndpoints:
                        nicLink.setNoCut()
                    nicLink.connect(ep, (rtr, "port%d" % port, _params["link_lat"]))
                port = port + 1


class topoFatTree(Topo):
    def __init__(self):
        Topo.__init__(self)
        self.topoKeys = [
            "topology",
            "debug",
            "flit_size",
            "link_bw",
            "xbar_bw",
            "nic_link_bw",
            "input_latency",
            "output_latency",
            "input_buf_size",
            "output_buf_size",
            "fattree:shape",
        ]
        self.topoOptKeys = [
            "xbar_arb",
            "fattree:routing_alg",
            "fattree:adaptive_threshold",
            "num_vns",
            "vn_remap",
            "vn_remap_shm",
            "portcontrol:output_arb",
            "portcontrol:arbitration:qos_settings",
            "portcontrol:arbitration:arb_vns",
            "portcontrol:arbitration:arb_vcs",
        ]
        self.nicKeys = ["link_bw"]
        self.ups = []
        self.downs = []
        self.routers_per_level = []
        self.groups_per_level = []
        self.start_ids = []

    def getName(self):
        return "Fat Tree"

    def prepParams(self):
        #        if "xbar_arb" in _params:
        #            self.rtrKeys.append("xbar_arb")
        #            _params["xbar_arb"] = "merlin.xbar_arb_lru"
        #        if "fattree:routing_alg" in _params:
        #            self.rtrKeys.append("fattree:routing_alg")
        #        if "fattree:adaptive_threshold" in _params:
        #            self.rtrKeys.append("fattree:adaptive_threshold")

        self.shape = _params["fattree:shape"]

        levels = self.shape.split(":")

        # print(levels)

        for l in levels:
            links = l.split(",")

            # print(links)

            self.downs.append(int(links[0]))
            if len(links) > 1:
                self.ups.append(int(links[1]))

        # print(self.downs)
        # print(self.ups)

        self.total_hosts = 1
        for i in self.downs:
            self.total_hosts *= i

        # print("Total hosts: " + str(self.total_hosts))

        self.routers_per_level = [0] * len(self.downs)
        self.routers_per_level[0] = self.total_hosts // self.downs[0]
        for i in range(1, len(self.downs)):
            self.routers_per_level[i] = (
                self.routers_per_level[i - 1] * self.ups[i - 1] // self.downs[i]
            )

        self.start_ids = [0] * len(self.downs)
        for i in range(1, len(self.downs)):
            self.start_ids[i] = self.start_ids[i - 1] + self.routers_per_level[i - 1]

        self.groups_per_level = [1] * len(self.downs)
        if self.ups:  # if ups is empty, then this is a single level and the following line will fail
            self.groups_per_level[0] = self.total_hosts // self.downs[0]

        for i in range(1, len(self.downs) - 1):
            self.groups_per_level[i] = self.groups_per_level[i - 1] // self.downs[i]

        # print(self.groups_per_level)
        _params["debug"] = debug
        _params["topology"] = "merlin.fattree"
        _params["num_peers"] = self.total_hosts

    def getRouterNameForId(self, rtr_id):
        num_levels = len(self.start_ids)

        # Check to make sure the index is in range
        level = num_levels - 1
        if (
            rtr_id >= (self.start_ids[level] + self.routers_per_level[level])
            or rtr_id < 0
        ):
            print(
                "ERROR: topoFattree.getRouterNameForId: rtr_id not found: %d" % rtr_id
            )
            sst.exit()

        # Find the level
        for x in range(num_levels - 1, 0, -1):
            if rtr_id >= self.start_ids[x]:
                break
            level = level - 1

        # Find the group
        remainder = rtr_id - self.start_ids[level]
        routers_per_group = (
            self.routers_per_level[level] // self.groups_per_level[level]
        )
        group = remainder // routers_per_group
        router = remainder % routers_per_group
        return self.getRouterNameForLocation((level, group, router))

    def getRouterNameForLocation(self, location):
        return "rtr_l%s_g%d_r%d" % (location[0], location[1], location[2])

    def findRouterByLocation(self, location):
        return sst.findComponentByName(self.getRouterNameForLocation(location))

    def fattree_rb(self, level, group, links):
        #        print("routers_per_level: %d, groups_per_level: %d, start_ids: %d"%(self.routers_per_level[level],self.groups_per_level[level],self.start_ids[level]))
        id = self.start_ids[level] + group * (
            self.routers_per_level[level] // self.groups_per_level[level]
        )
        # print("start id: " + str(id))

        host_links = []
        if level == 0:
            # create all the nodes
            for i in range(self.downs[0]):
                node_id = id * self.downs[0] + i
                # print("group: %d, id: %d, node_id: %d"%(group, id, node_id))
                ep = self._getEndPoint(node_id).build(node_id, {})
                if ep:
                    hlink = sst.Link("hostlink_%d" % node_id)
                    if self.bundleEndpoints:
                        hlink.setNoCut()
                    ep[0].addLink(hlink, ep[1], ep[2])
                    host_links.append(hlink)

            # Create the edge router
            rtr_id = id

            rtr = self._instanceRouter(rtr_id, "merlin.hr_router")
            # rtr = sst.Component("rtr_l0_g%d_r0"%(group), "merlin.hr_router")

            # Add parameters
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", rtr_id)
            rtr.addParam("num_ports", self.ups[0] + self.downs[0])
            topology = rtr.setSubComponent("topology", "merlin.fattree")
            topology.addParams(self._topo_params)
            # Add links
            for l in range(len(host_links)):
                rtr.addLink(host_links[l], "port%d" % l, _params["link_lat"])
            for l in range(len(links)):
                rtr.addLink(
                    links[l], "port%d" % (l + self.downs[0]), _params["link_lat"]
                )
            return

        rtrs_in_group = self.routers_per_level[level] // self.groups_per_level[level]
        # Create the down links for the routers
        rtr_links = [[] for index in range(rtrs_in_group)]
        for i in range(rtrs_in_group):
            for j in range(self.downs[level]):
                #                print("Creating link: link_l%d_g%d_r%d_p%d"%(level,group,i,j);)
                rtr_links[i].append(
                    sst.Link("link_l%d_g%d_r%d_p%d" % (level, group, i, j))
                )

        # Now create group links to pass to lower level groups from router down links
        group_links = [[] for index in range(self.downs[level])]
        for i in range(self.downs[level]):
            for j in range(rtrs_in_group):
                group_links[i].append(rtr_links[j][i])

        for i in range(self.downs[level]):
            self.fattree_rb(level - 1, group * self.downs[level] + i, group_links[i])

        # Create the routers in this level.
        # Start by adding up links to rtr_links
        for i in range(len(links)):
            rtr_links[i % rtrs_in_group].append(links[i])

        for i in range(rtrs_in_group):
            rtr_id = id + i

            rtr = self._instanceRouter(rtr_id, "merlin.hr_router")
            # rtr = sst.Component("rtr_l%d_g%d_r%d"%(level,group,i), "merlin.hr_router")

            # Add parameters
            rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
            rtr.addParam("id", rtr_id)
            rtr.addParam("num_ports", self.ups[level] + self.downs[level])
            topology = rtr.setSubComponent("topology", "merlin.fattree")
            topology.addParams(self._topo_params)
            # Add links
            for l in range(len(rtr_links[i])):
                rtr.addLink(rtr_links[i][l], "port%d" % l, _params["link_lat"])

    def build(self):
        #        print("build()")

        swap_keys = [
            ("fattree:shape", "shape"),
            ("fattree:algorithm", "algorithm"),
            ("fattree:adaptive_threshold", "adaptive_threshold"),
        ]

        self._topo_params = _params.subsetWithRename(swap_keys)
        level = len(self.ups)
        if self.ups:  # True for all cases except for single level
            #  Create the router links
            rtrs_in_group = (
                self.routers_per_level[level] // self.groups_per_level[level]
            )
            # print(rtrs_in_group)
            # Create the down links for the routers
            rtr_links = [[] for index in range(rtrs_in_group)]
            for i in range(rtrs_in_group):
                for j in range(self.downs[level]):
                    #                    print("Creating link: link_l%d_g0_r%d_p%d"%(level,i,j))
                    rtr_links[i].append(sst.Link("link_l%d_g0_r%d_p%d" % (level, i, j)))

            # Now create group links to pass to lower level groups from router down links
            group_links = [[] for index in range(self.downs[level])]
            for i in range(self.downs[level]):
                for j in range(rtrs_in_group):
                    group_links[i].append(rtr_links[j][i])

            for i in range(self.downs[len(self.ups)]):
                self.fattree_rb(level - 1, i, group_links[i])

            # Create the routers in this level
            radix = self.downs[level]
            for i in range(self.routers_per_level[level]):
                rtr_id = self.start_ids[len(self.ups)] + i

                rtr = self._instanceRouter(rtr_id, "merlin.hr_router")
                # rtr = sst.Component("rtr_l%d_g0_r%d"%(len(self.ups),i),"merlin.hr_router")

                rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
                rtr.addParam("id", rtr_id)
                rtr.addParam("num_ports", radix)
                topology = rtr.setSubComponent("topology", "merlin.fattree")
                topology.addParams(self._topo_params)

                for l in range(len(rtr_links[i])):
                    rtr.addLink(rtr_links[i][l], "port%d" % l, _params["link_lat"])

        else:  # Single level case
            # create all the nodes
            for i in range(self.downs[0]):
                node_id = i
        #                print("Instancing node " + str(node_id))
        rtr_id = 0


#        print("Instancing router " + str(rtr_id))


class topoDragonFly(Topo):
    def __init__(self):
        Topo.__init__(self)
        self.topoKeys = [
            "topology",
            "debug",
            "num_ports",
            "flit_size",
            "link_bw",
            "nic_link_bw",
            "xbar_bw",
            "dragonfly:hosts_per_router",
            "dragonfly:routers_per_group",
            "dragonfly:intergroup_per_router",
            "dragonfly:num_groups",
            "dragonfly:intergroup_links",
            "input_latency",
            "output_latency",
            "input_buf_size",
            "output_buf_size",
            "dragonfly:global_route_mode",
        ]
        self.topoOptKeys = [
            "xbar_arb",
            "link_bw:host",
            "link_bw:group",
            "link_bw:global",
            "input_latency:host",
            "input_latency:group",
            "input_latency:global",
            "output_latency:host",
            "output_latency:group",
            "output_latency:global",
            "input_buf_size:host",
            "input_buf_size:group",
            "input_buf_size:global",
            "output_buf_size:host",
            "output_buf_size:group",
            "output_buf_size:global",
            "num_vns",
            "vn_remap",
            "vn_remap_shm",
            "portcontrol:output_arb",
            "portcontrol:arbitration:qos_settings",
            "portcontrol:arbitration:arb_vns",
            "portcontrol:arbitration:arb_vcs",
        ]
        self.global_link_map = None
        self.global_routes = "absolute"

    def getName(self):
        return "Dragonfly"

    def prepParams(self):
        #        if "xbar_arb" not in _params:
        #            _params["xbar_arb"] = "merlin.xbar_arb_lru"
        _params["topology"] = "merlin.dragonfly"
        _params["debug"] = debug
        #        _params["router_radix"] = int(_params["router_radix"])
        _params["dragonfly:hosts_per_router"] = int(
            _params["dragonfly:hosts_per_router"]
        )
        _params["dragonfly:routers_per_group"] = int(
            _params["dragonfly:routers_per_group"]
        )
        _params["dragonfly:intergroup_links"] = int(
            _params["dragonfly:intergroup_links"]
        )
        _params["dragonfly:num_groups"] = int(_params["dragonfly:num_groups"])
        _params["num_peers"] = (
            _params["dragonfly:hosts_per_router"]
            * _params["dragonfly:routers_per_group"]
            * _params["dragonfly:num_groups"]
        )
        _params["dragonfly:global_route_mode"] = self.global_routes

        self.total_intergroup_links = (_params["dragonfly:num_groups"] - 1) * _params[
            "dragonfly:intergroup_links"
        ]
        _params["dragonfly:intergroup_per_router"] = int(
            (self.total_intergroup_links + _params["dragonfly:routers_per_group"] - 1)
            // _params["dragonfly:routers_per_group"]
        )
        self.empty_ports = (
            _params["dragonfly:intergroup_per_router"]
            * _params["dragonfly:routers_per_group"]
            - self.total_intergroup_links
        )
        # print("Per router global -> " + str(_params["dragonfly:intergroup_per_router"]))

        _params["router_radix"] = (
            _params["dragonfly:routers_per_group"]
            - 1
            + _params["dragonfly:hosts_per_router"]
            + _params["dragonfly:intergroup_per_router"]
        )
        _params["num_ports"] = int(_params["router_radix"])

        if _params["dragonfly:num_groups"] > 2:
            foo = _params["dragonfly:algorithm"]
            self.topoKeys.append("dragonfly:algorithm")

    def setGlobalLinkMap(self, glm):
        self.global_link_map = glm

    def setRoutingModeAbsolute(self):
        self.global_routes = "absolute"

    def setRoutingModeRelative(self):
        self.global_routes = "relative"

    def getRouterNameForId(self, rtr_id):
        rpg = _params["dragonfly:routers_per_group"]
        ret = self.getRouterNameForLocation(rtr_id // rpg, rtr_id % rpg)
        return ret

    def getRouterNameForLocation(self, group, rtr):
        return "rtr:G%dR%d" % (group, rtr)

    def findRouterByLocation(self, group, rtr):
        return sst.findComponentByName(self.getRouterNameForLocation(group, rtr))

    def build(self):
        links = dict()

        #####################
        def getLink(name):
            if name not in links:
                links[name] = sst.Link(name)
            return links[name]

        #####################

        rpg = _params["dragonfly:routers_per_group"]
        ng = _params["dragonfly:num_groups"] - 1  # don't count my group
        igpr = _params["dragonfly:intergroup_per_router"]

        if self.global_link_map is None:
            # Need to define global link map

            self.global_link_map = [-1 for i in range(igpr * rpg)]

            # Links will be mapped in linear order, but we will
            # potentially skip one port per router, depending on the
            # parameters.  The variable self.empty_ports tells us how
            # many routers will have one global port empty.
            count = 0
            start_skip = rpg - self.empty_ports
            for i in range(0, rpg):
                # Determine if we skip last port for this router
                end = igpr
                if i >= start_skip:
                    end = end - 1
                for j in range(0, end):
                    self.global_link_map[i * igpr + j] = count
                    count = count + 1

        # print("Global link map array")
        # print(self.global_link_map)

        # End set global link map with default

        # g is group number
        # r is router number with group
        # p is port number relative to start of global ports

        def getGlobalLink(g, r, p):
            # Look into global link map to get the dest group and link
            # number to that group
            raw_dest = self.global_link_map[r * igpr + p]
            if raw_dest == -1:
                return None

            # Turn raw_dest into dest_grp and link_num
            link_num = raw_dest // ng
            dest_grp = raw_dest - link_num * ng

            if self.global_routes == "absolute":
                # Compute dest group ignoring my own group id, for a
                # dest_grp >= g, we need to add 1 to get the right group
                if dest_grp >= g:
                    dest_grp = dest_grp + 1
            elif self.global_routes == "relative":
                # For relative, add current group to dest_grp + 1 and
                # do modulo of num_groups to get actual group
                dest_grp = (dest_grp + g + 1) % (ng + 1)
            # else:
            # should never happen

            src = min(dest_grp, g)
            dest = max(dest_grp, g)

            # getLink("link:g%dg%dr%d"%(g, src, dst)), "port%d"%port, _params["link_lat"])
            return getLink("link:g%dg%dr%d" % (src, dest, link_num))

        #########################

        swap_keys = [
            ("dragonfly:hosts_per_router", "hosts_per_router"),
            ("dragonfly:routers_per_group", "routers_per_group"),
            ("dragonfly:intergroup_links", "intergroup_links"),
            ("dragonfly:num_groups", "num_groups"),
            ("dragonfly:intergroup_per_router", "intergroup_per_router"),
            ("dragonfly:algorithm", "algorithm"),
            ("dragonfly:global_route_mode", "global_route_mode"),
            ("dragonfly:adaptive_threshold", "adaptive_threshold"),
        ]

        _topo_params = _params.subsetWithRename(swap_keys)
        router_num = 0
        nic_num = 0
        # GROUPS
        for g in range(_params["dragonfly:num_groups"]):
            # GROUP ROUTERS
            for r in range(_params["dragonfly:routers_per_group"]):
                rtr = self._instanceRouter(router_num, "merlin.hr_router")
                # rtr = sst.Component("rtr:G%dR%d"%(g, r), "merlin.hr_router")
                rtr.addParams(_params.subset(self.topoKeys, self.topoOptKeys))
                rtr.addParam("id", router_num)
                topology = rtr.setSubComponent("topology", "merlin.dragonfly")
                topology.addParams(_topo_params)
                if router_num == 0:
                    # Need to send in the global_port_map
                    # map_str = str(self.global_link_map).strip('[]')
                    # rtr.addParam("dragonfly:global_link_map",map_str)
                    rtr.addParam("dragonfly:global_link_map", self.global_link_map)
                    topology.addParam("global_link_map", self.global_link_map)

                port = 0
                for p in range(_params["dragonfly:hosts_per_router"]):
                    ep = self._getEndPoint(nic_num).build(nic_num, {})
                    if ep:
                        link = sst.Link("link:g%dr%dh%d" % (g, r, p))
                        if self.bundleEndpoints:
                            link.setNoCut()
                        link.connect(ep, (rtr, "port%d" % port, _params["link_lat"]))
                    nic_num = nic_num + 1
                    port = port + 1

                for p in range(_params["dragonfly:routers_per_group"]):
                    if p != r:
                        src = min(p, r)
                        dst = max(p, r)
                        rtr.addLink(
                            getLink("link:g%dr%dr%d" % (g, src, dst)),
                            "port%d" % port,
                            _params["link_lat"],
                        )
                        port = port + 1

                for p in range(_params["dragonfly:intergroup_per_router"]):
                    link = getGlobalLink(g, r, p)
                    if link is not None:
                        rtr.addLink(link, "port%d" % port, _params["link_lat"])
                    port = port + 1

                router_num = router_num + 1


############################################################################


class EndPoint(object):
    def __init__(self):
        self.epKeys = []
        self.epOptKeys = []
        self.enableAllStats = False
        self.statInterval = "0"

    def getName(self):
        print("Not implemented")
        sys.exit(1)

    def prepParams(self):
        pass

    def build(self, nID, extraKeys):
        return None


class TestEndPoint(EndPoint):
    def __init__(self):
        EndPoint.__init__(self)
        # self.enableAllStats = False;
        # self.statInterval = "0"
        # self.nicKeys = ["topology", "num_peers", "num_messages", "link_bw", "checkerboard"]
        self.epKeys.extend(["num_peers", "link_bw"])
        self.epOptKeys.extend(["checkerboard", "num_messages"])
        self.split = 1
        self.group_array = None

    def divide(self, split):
        self.split = split

    def getName(self):
        return "Test End Point"

    def prepParams(self):
        # if "checkerboard" not in _params:
        #    _params["checkerboard"] = "1"
        # if "num_messages" not in _params:
        #    _params["num_messages"] = "10"
        pass

    def build(self, nID, extraKeys):
        # Copmute group size and offset
        if self.group_array is None:
            num_ep = sst.merlin._params["num_peers"]
            min_per_group = num_ep // self.split
            self.group_array = [min_per_group] * self.split
            num_ep = num_ep - (min_per_group * self.split)
            for i in range(num_ep):
                self.group_array[i] = self.group_array[i] + 1

        nic = sst.Component("testNic.%d" % nID, "merlin.test_nic")
        linkif = nic.setSubComponent("networkIF", "merlin.linkcontrol")
        if "link_bw" in _params:
            linkif.addParam("link_bw", _params["link_bw"])
        # if ( "input_buf_size" in _params):
        #    linkif.addParam("input_buf_size",_params["input_buf_size"])
        # if ( "output_buf_size" in _params):
        #    linkif.addParam("output_buf_size",_params["output_buf_size"])
        nic.addParams(_params.subset(self.epKeys, self.epOptKeys))
        nic.addParams(_params.subset(extraKeys))
        nic.addParam("id", nID)
        if self.split != 1:
            # Need to figure out what group I'm in
            limit = 0
            offset = 0
            for i in range(self.split):
                limit = limit + self.group_array[i]
                if nID < limit:
                    nic.addParam("group_peers", self.group_array[i])
                    nic.addParam("group_offset", offset)
                    break
                offset = offset + self.group_array[i]
        if self.enableAllStats:
            nic.enableAllStatistics(
                {"type": "sst.AccumulatorStatistic", "rate": self.statInterval}
            )
        return (linkif, "rtr_port", _params["link_lat"])
        # print("Created Endpoint with id: %d, and params: %s %s\n"%(nID, _params.subset(self.nicKeys), _params.subset(extraKeys)))

    def enableAllStatistics(self, interval):
        self.enableAllStats = True
        self.statInterval = interval


class BisectionEndPoint(EndPoint):
    def __init__(self):
        EndPoint.__init__(self)
        # self.enableAllStats = False;
        # self.statInterval = "0"
        self.epKeys.extend(
            ["num_peers", "link_bw", "packet_size", "packets_to_send", "buffer_size"]
        )
        self.epOptKeys.extend(["checkerboard", "rlc:networkIF"])

    def getName(self):
        return "Bisection Test End Point"

    def prepParams(self):
        # if "checkerboard" not in _params:
        #    _params["checkerboard"] = "1"
        pass

    def build(self, nID, extraKeys):
        nic = sst.Component("bisectionNic.%d" % nID, "merlin.bisection_test")
        linkif = nic.setSubComponent("networkIF", "merlin.linkcontrol")
        if "link_bw" in _params:
            linkif.addParam("link_bw", _params["link_bw"])
        if "buffer_size" in _params:
            linkif.addParam("input_buf_size", _params["buffer_size"])
            linkif.addParam("output_buf_size", _params["buffer_size"])
        nic.addParams(_params.subset(self.epKeys, self.epOptKeys))
        nic.addParams(_params.subset(extraKeys))
        nic.addParam("id", nID)
        if self.enableAllStats:
            nic.enableAllStatistics(
                {"type": "sst.AccumulatorStatistic", "rate": self.statInterval}
            )
        return (nic, "rtr", _params["link_lat"])
        # print("Created Endpoint with id: %d, and params: %s %s\n"%(nID, _params.subset(self.nicKeys), _params.subset(extraKeys)))

    def enableAllStatistics(self, interval):
        self.enableAllStats = True
        self.statInterval = interval


class Pt2ptEndPoint(EndPoint):
    def __init__(self):
        EndPoint.__init__(self)
        # self.enableAllStats = False;
        # self.statInterval = "0"
        self.epKeys.extend(
            ["link_bw", "packet_size", "packets_to_send", "buffer_size", "src", "dest"]
        )
        self.epOptKeys.extend(["linkcontrol", "stream_delays", "report_interval"])

    def getName(self):
        return "pt2pt Test End Point"

    def prepParams(self):
        # if "checkerboard" not in _params:
        #    _params["checkerboard"] = "1"
        pass

    def build(self, nID, extraKeys):
        nic = sst.Component("pt2ptNic.%d" % nID, "merlin.pt2pt_test")
        nic.addParams(_params.subset(self.epKeys, self.epOptKeys))
        nic.addParams(_params.subset(extraKeys))
        nic.addParam("id", nID)
        if self.enableAllStats:
            nic.enableAllStatistics(
                {"type": "sst.AccumulatorStatistic", "rate": self.statInterval}
            )
        return (nic, "rtr", _params["link_lat"])
        # print("Created Endpoint with id: %d, and params: %s %s\n"%(nID, _params.subset(self.nicKeys), _params.subset(extraKeys)))

    def enableAllStatistics(self, interval):
        self.enableAllStats = True
        self.statInterval = interval


class OfferedLoadEndPoint(EndPoint):
    def __init__(self):
        EndPoint.__init__(self)
        # self.enableAllStats = False;
        # self.statInterval = "0"
        self.epKeys.extend(
            [
                "offered_load",
                "num_peers",
                "link_bw",
                "message_size",
                "buffer_size",
                "pattern",
            ]
        )
        self.epOptKeys.extend(["linkcontrol"])

    def getName(self):
        return "Offered Load End Point"

    def prepParams(self):
        pass

    def build(self, nID, extraKeys):
        nic = sst.Component("offered_load.%d" % nID, "merlin.offered_load")
        nic.addParams(_params.subset(self.epKeys, self.epOptKeys))
        nic.addParams(_params.subset(extraKeys))
        nic.addParam("id", nID)
        if self.enableAllStats:
            nic.enableAllStatistics(
                {"type": "sst.AccumulatorStatistic", "rate": self.statInterval}
            )
        return (nic, "rtr", _params["link_lat"])
        # print("Created Endpoint with id: %d, and params: %s %s\n"%(nID, _params.subset(self.nicKeys), _params.subset(extraKeys)))

    def enableAllStatistics(self, interval):
        self.enableAllStats = True
        self.statInterval = interval


class ShiftEndPoint(EndPoint):
    def __init__(self):
        EndPoint.__init__(self)
        # self.enableAllStats = False;
        # self.statInterval = "0"
        # self.nicKeys = ["topology", "num_peers", "num_messages", "link_bw", "checkerboard"]
        self.epKeys.extend(["num_peers", "link_bw", "shift"])
        self.epOptKeys.extend(["checkerboard", "packets_to_send", "packet_size"])

    def getName(self):
        return "Test End Point"

    def prepParams(self):
        # if "checkerboard" not in _params:
        #    _params["checkerboard"] = "1"
        # if "num_messages" not in _params:
        #    _params["num_messages"] = "10"
        pass

    def build(self, nID, extraKeys):
        nic = sst.Component("shiftNic.%d" % nID, "merlin.shift_nic")
        nic.addParams(_params.subset(self.epKeys, self.epOptKeys))
        nic.addParams(_params.subset(extraKeys))
        nic.addParam("id", nID)
        if self.enableAllStats:
            nic.enableAllStatistics(
                {"type": "sst.AccumulatorStatistic", "rate": self.statInterval}
            )
        return (nic, "rtr", _params["link_lat"])
        # print("Created Endpoint with id: %d, and params: %s %s\n"%(nID, _params.subset(self.nicKeys), _params.subset(extraKeys)))

    def enableAllStatistics(self, interval):
        self.enableAllStats = True
        self.statInterval = interval


class TrafficGenEndPoint(EndPoint):
    def __init__(self):
        EndPoint.__init__(self)
        # self.enableAllStats = False;
        # self.statInterval = "0"
        self.optionalKeys = ["delay_between_packets"]
        for genType in ["PacketDest", "PacketSize", "PacketDelay"]:
            for tag in [
                "pattern",
                "RangeMin",
                "RangeMax",
                "HotSpot:target",
                "HotSpot:targetProbability",
                "Normal:Mean",
                "Normal:Sigma",
                "Binomial:Mean",
                "Binomial:Sigma",
            ]:
                self.optionalKeys.append("%s:%s" % (genType, tag))
        self.epKeys.extend(
            [
                "topology",
                "num_peers",
                "link_bw",
                "packets_to_send",
                "packet_size",
                "message_rate",
                "PacketDest:pattern",
                "PacketDest:RangeMin",
                "PacketDest:RangeMax",
            ]
        )
        self.epOptKeys.extend("checkerboard")
        self.epOptKeys.extend(self.optionalKeys)
        self.nicKeys = []

    def getName(self):
        return "Pattern-based traffic generator"

    def prepParams(self):
        # if "checkerboard" not in _params:
        #    _params["checkerboard"] = "1"
        _params["PacketDest:RangeMin"] = 0
        _params["PacketDest:RangeMax"] = int(_params["num_peers"])

        if _params["PacketDest:pattern"] == "NearestNeighbor":
            self.nicKeys.append("PacketDest:NearestNeighbor:3DSize")
            if not "PacketDest:NearestNeighbor:3DSize" in _params:
                _params["PacketDest:NearestNeighbor:3DSize"] = "%s %s %s" % (
                    _params["PacketDest:3D shape X"],
                    _params["PacketDest:3D shape Y"],
                    _params["PacketDest:3D shape Z"],
                )
        elif _params["PacketDest:pattern"] == "HotSpot":
            self.nicKeys.append("PacketDest:HotSpot:target")
            self.nicKeys.append("PacketDest:HotSpot:targetProbability")
        elif _params["PacketDest:pattern"] == "Normal":
            self.nicKeys.append("PacketDest:Normal:Mean")
            self.nicKeys.append("PacketDest:Normal:Sigma")
        elif _params["PacketDest:pattern"] == "Binomial":
            self.nicKeys.append("PacketDest:Binomial:Mean")
            self.nicKeys.append("PacketDest:Binomial:Sigma")
        elif _params["PacketDest:pattern"] == "Exponential":
            self.nicKeys.append("PacketDest:Exponential:Lambda")
        elif _params["PacketDest:pattern"] == "Uniform":
            pass
        else:
            print("Unknown pattern" + _params["PacketDest:pattern"])
            sys.exit(1)

    def build(self, nID, extraKeys):
        nic = sst.Component("TrafficGen.%d" % nID, "merlin.trafficgen")
        linkif = nic.setSubComponent("networkIF", "merlin.linkcontrol")
        if "link_bw" in _params:
            linkif.addParam("link_bw", _params["link_bw"])
        # if ( "input_buf_size" in _params):
        #    linkif.addParam("input_buf_size",_params["input_buf_size"])
        # if ( "output_buf_size" in _params):
        #    linkif.addParam("output_buf_size",_params["output_buf_size"])
        nic.addParams(_params.subset(self.epKeys, self.epOptKeys))
        nic.addParams(_params.subset(self.nicKeys))
        nic.addParams(_params.subset(extraKeys, {}))
        # for k in self.optionalKeys:
        #    if k in _params:
        #        nic.addParam(k, _params[k])
        nic.addParam("id", nID)
        if self.enableAllStats:
            nic.enableAllStatistics(
                {"type": "sst.AccumulatorStatistic", "rate": self.statInterval}
            )
        return (linkif, "rtr_port", _params["link_lat"])

    def enableAllStatistics(self, interval):
        self.enableAllStats = True
        self.statInterval = interval


############################################################################


if __name__ == "__main__":
    topos = dict(
        [(1, topoTorus()), (2, topoFatTree()), (3, topoDragonFly()), (4, topoSimple())]
    )
    endpoints = dict(
        [(1, TestEndPoint()), (2, TrafficGenEndPoint()), (3, BisectionEndPoint())]
    )

    print("Merlin SDL Generator\n")

    print("Please select network topology:")
    for x, y in topos.iteritems():
        print("[ %d ]  %s" % (x, y.getName()))
    topo = int(input())
    if topo not in topos:
        print("Bad answer.  try again.")
        sys.exit(1)

    topo = topos[topo]

    print("Please select endpoint:")
    for x, y in endpoints.iteritems():
        print("[ %d ]  %s" % (x, y.getName()))
    ep = int(input())
    if ep not in endpoints:
        print("Bad answer. try again.")
        sys.exit(1)

    endPoint = endpoints[ep]
    topo.prepParams()
    endPoint.prepParams()
    topo.setEndPoint(endPoint)
    topo.build()

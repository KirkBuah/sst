from .Topology import Topology
from .Jellyfish import Jellyfish
from .HammingMeshGenerator import BoardMesh

from math import ceil, sqrt

class ModHammingMesh(Topology):

    """
    N: total number of endnodes
    k: ratio between number of boards and nodes per board (assuming square boards and square board disposition)

    """
    def __init__(self, k = -1, N = -1):
        if k == -1 and N != -1:
            k = 1
        elif k == -1 and N == -1:
            k = 1
            N = 1000
        # Compute Hamming Mesh dimensions
        a = ceil((N/k) ** 0.25)
        b = ceil((N * k) ** 0.25)

        self.rows_per_board = a
        self.cols_per_board = a
        self.boards_horizontal = b
        self.boards_vertical = b

        self.total_edge_nodes = self.rows_per_board * self.cols_per_board * self.boards_horizontal * self.boards_vertical

        self.__topo = None
        self.name = "HM"

        self.N = self.total_edge_nodes
        self.R = self.get_number_of_routers(a, b)
        self.r = ceil((2*b)**(1/3))
        self.nr = self.get_number_of_edges(a, b) / (self.N + self.R)
        self.p = 1
        self.edge = self.total_edge_nodes

    def get_number_of_routers(self, a, b):
        """Get the total number of routers"""
        if a*b > 64:
            k = ceil((2*b)**(1/3))
            # fat tree non-edge routers + end nodes
            return 2 * (k + k ** 2) * a * b + a**2 * b ** 2
        else:
            return 2 * a * b

    def get_number_of_edges(self, a, b):
        # Sum of the edges within the boards
        k = ceil((2*b)**(1/3))
        intra_board_edges = 2 * a * (a - 1) * b ** 2

        if a * b <= 64:
            inter_board_edges = 4 * b * a * b
        else:
            inter_board_edges = (9 / 2) * a * b * k**2

        return intra_board_edges + inter_board_edges



    def get_topo(self):
        if self.__topo is None:
            self.__topo = BoardMesh(
                N=self.N,
                k = -1
                ).make()
        return self.__topo

    def get_jellyfish_eq(self):
        R = self._calculate_equivalent_routers()
        nr = self._calculate_network_radix()
        p = ceil(self.total_edge_nodes / R)

        jf = Jellyfish(nr,R,p)
        jf.name += "-" + self.name
        return jf

    def _calculate_equivalent_routers(self) -> int:
        """
        Calculate the equivalent number of routers based on BoardMesh structure.

        The number of routers depends on whether switches or fat trees are used:
        - Switch mode: Each row/column switch acts as a router
        - Fat tree mode: Each fat tree acts as a routing infrastructure
        """

        # Base routers: one per board for local connectivity
        base_routers = self.boards_horizontal * self.boards_vertical

        # Additional routers for inter-board connectivity
        if self.boards_horizontal * 2 < 64:  # Using row switches
            row_routers = self.boards_vertical * self.rows_per_board
        else:  # Using row fat trees
            # Each fat tree can be considered as multiple routers
            row_fat_trees = self.boards_vertical * self.rows_per_board
            # Approximate number of routers per fat tree based on structure
            routers_per_ft = max(1, self.row_k // 4)  # Conservative estimate
            row_routers = row_fat_trees * routers_per_ft

        if self.boards_vertical * 2 < 64:  # Using column switches
            col_routers = self.boards_horizontal * self.cols_per_board
        else:  # Using column fat trees
            col_fat_trees = self.boards_horizontal * self.cols_per_board
            routers_per_ft = max(1, self.col_k // 4)
            col_routers = col_fat_trees * routers_per_ft

        # Total equivalent routers
        total_routers = base_routers + row_routers + col_routers

        # Ensure minimum number of routers for meaningful comparison
        return max(total_routers, ceil(sqrt(self.total_edge_nodes)))

    def _calculate_network_radix(self, R: int) -> int:
        """
        Calculate network radix based on connectivity requirements.

        Args:
            R: Number of routers

        Returns:
            Network radix (ports per router for inter-router connections)
        """

        # In BoardMesh, connectivity varies by position and connection type
        # Estimate average connectivity requirements

        if self.boards_horizontal * 2 < 64 and self.boards_vertical * 2 < 64:
            # Both dimensions use switches - simpler connectivity
            avg_connections = 4  # Basic cross-connectivity
        elif self.boards_horizontal * 2 >= 64 and self.boards_vertical * 2 >= 64:
            # Both dimensions use fat trees - higher connectivity
            avg_connections = max(self.row_k, self.col_k) // 2
        else:
            # Mixed mode
            if self.boards_horizontal * 2 < 64:
                avg_connections = max(4, self.col_k // 2)
            else:
                avg_connections = max(4, self.row_k // 2)

        # Ensure reasonable bounds
        nr = max(2, min(avg_connections, R // 2))

        return nr
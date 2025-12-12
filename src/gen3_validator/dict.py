import json
from collections import defaultdict, deque
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Set, Tuple

logger = logging.getLogger(__name__)

class DataDictionary:
    def __init__(self, schema_path: str):
        """
        Initialize the DataDictionary class.

        Provides methods to extract gen3 jsonschema information.

        :param schema_path: The path to the JSON file which contains a list of gen3 jsonschema.
        :type schema_path: str
        """
        self.schema_path = schema_path
        logger.info(f"Initializing DataDictionary with schema path: {schema_path}")
        self.schema = None
        self.nodes = None
        self.node_pairs = None
        self.node_order = None
        self.schema_list = None
        self.schema_list_resolved = None
        self.schema_version = None

    def read_json(self, path: str) -> dict:
        """
        Read a JSON file and return its contents as a dictionary.

        :param path: The path to the JSON file.
        :type path: str

        :return: The contents of the JSON file.
        :rtype: dict
        """
        logger.info(f"Reading JSON file from path: {path}")
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"JSON file not found: {path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from file {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading JSON file {path}: {e}")
            raise

    def get_nodes(self) -> list:
        """
        Retrieve all node names from the schema.

        :return: A list of node names.
        :rtype: list
        """
        logger.info("Retrieving node names from schema.")
        try:
            nodes = list(self.schema.keys())
            return nodes
        except Exception as e:
            logger.error(f"Error retrieving nodes from schema: {e}")
            raise

    def get_node_link(self, node_name: str) -> tuple:
        """
        Retrieve the links and ID for a given node.

        :param node_name: The name of the node.
        :type node_name: str

        :return: A tuple containing the node ID and its links.
        :rtype: tuple
        """
        logger.info(f"Retrieving links and ID for node: {node_name}")
        try:
            links = self.schema[node_name]["links"]
            node_id = self.schema[node_name]["id"]
            if "subgroup" in links[0]:
                return node_id, links[0]["subgroup"]
            else:
                return node_id, links
        except KeyError as e:
            logger.error(f"Missing key {e} in node {node_name}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving node link for {node_name}: {e}")
            raise

    def get_node_category(self, node_name: str) -> tuple:
        """
        Retrieve the category and ID for a given node, excluding certain nodes.

        :param node_name: The name of the node.
        :type node_name: str

        :return: A tuple containing the node ID and its category, or None if the node is excluded.
        :rtype: tuple
        """
        logger.info(f"Retrieving category and ID for node: {node_name}")
        try:
            category = self.schema[node_name]["category"]
            node_id = self.schema[node_name]["id"]
            return node_id, category
        except KeyError as e:
            logger.error(f"Missing key {e} in node {node_name}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving node category for {node_name}: {e}")
            raise

    def get_node_properties(self, node_name: str) -> tuple:
        """
        Retrieve the properties for a given node.

        :param node_name: The name of the node.
        :type node_name: str

        :return: A tuple containing the node ID and its properties.
        :rtype: tuple
        """
        logger.info(f"Retrieving properties for node: {node_name}")
        try:
            properties = {
                k: v for k, v in self.schema[node_name]["properties"].items()
                if k != "$ref"
            }
            property_keys = list(properties.keys())
            node_id = self.schema[node_name]["id"]
            return node_id, property_keys
        except KeyError as e:
            logger.error(f"Missing key {e} in node {node_name}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving node properties for {node_name}: {e}")
            raise

    def generate_node_lookup(self) -> dict:
        """
        Generate a lookup dictionary for nodes, mapping node names to their categories and properties.

        :return: A dictionary mapping node names to their category and properties.
        :rtype: dict
        """
        logger.info("Generating node lookup dictionary.")
        node_lookup = {}
        excluded_nodes = [
            "_definitions.yaml",
            "_terms.yaml",
            "_settings.yaml",
            "program.yaml",
        ]

        for node in self.nodes:
            if node in excluded_nodes:
                continue

            try:
                category = self.get_node_category(node)
                if category:
                    category = category[1]

                props = self.get_node_properties(node)
                node_lookup[node] = {"category": category, "properties": props}
            except Exception as e:
                logger.error(f"Error generating node lookup for {node}: {e}")
                continue
        return node_lookup

    def _find_upstream_downstream(self, node_name: str) -> list:
        """
        Takes a node name and returns the upstream and downstream nodes.

        :param node_name: The name of the node.
        :type node_name: str

        :return: A list of tuples representing upstream and downstream nodes.
        :rtype: list
        """
        logger.info(f"Finding upstream and downstream nodes for: {node_name}")
        try:
            node_id, links = self.get_node_link(node_name)

            # Ensure links is a list
            if isinstance(links, dict):
                links = [links]

            results = []

            for link in links:
                target_type = link.get("target_type")

                if not node_id or not target_type:
                    logger.warning(f"Missing essential keys in link: {link}")
                    results.append((None, None))
                    continue

                results.append((target_type, node_id))

            return results
        except Exception as e:
            logger.error(f"Error finding upstream/downstream for {node_name}: {e}")
            raise

    def get_all_node_pairs(
        self,
        excluded_nodes=[
            "_definitions.yaml",
            "_terms.yaml",
            "_settings.yaml",
            "program.yaml",
        ],
    ) -> list:
        """
        Retrieve all node pairs, excluding specified nodes.

        :param excluded_nodes: A list of node names to exclude.
        :type excluded_nodes: list

        :return: A list of node pairs.
        :rtype: list
        """
        logger.info("Retrieving all node pairs, excluding specified nodes.")
        node_pairs = []
        for node in self.nodes:
            if node not in excluded_nodes:
                try:
                    node_pairs.extend(self._find_upstream_downstream(node))
                except Exception as e:
                    logger.error(f"Error retrieving node pairs for {node}: {e}")
                    continue
        return node_pairs

    def get_node_order(self, edges: list) -> list:
        """
        Determine the order of nodes based on their dependencies.

        :param edges: A list of tuples, where each tuple is a node pair (upstream, downstream).
        :type edges: list

        :return: A list of nodes in topological order.
        :rtype: list
        """
        logger.info("Determining node order based on dependencies.")
        try:
            # Build graph representation
            graph = defaultdict(list)
            in_degree = defaultdict(int)

            for upstream, downstream in edges:
                graph[upstream].append(downstream)
                in_degree[downstream] += 1
                if upstream not in in_degree:
                    in_degree[upstream] = 0

            # Perform Topological Sorting (Kahn's Algorithm)
            sorted_order = []
            zero_in_degree = deque([node for node in in_degree if in_degree[node] == 0])

            while zero_in_degree:
                node = zero_in_degree.popleft()
                sorted_order.append(node)

                for neighbor in graph[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        zero_in_degree.append(neighbor)

            # Ensure core_metadata_collection is last
            if "core_metadata_collection" in sorted_order:
                sorted_order.remove("core_metadata_collection")
                sorted_order.append("core_metadata_collection")

            return sorted_order
        except Exception as e:
            logger.error(f"Error determining node order: {e}")
            raise

    def split_json(self) -> list:
        """
        Split the schema into a list of individual node schemas.

        :return: A list of node schemas.
        :rtype: list
        """
        logger.info("Splitting schema into individual node schemas.")
        try:
            schema_list = []
            for node in self.nodes:
                schema_list.append(self.schema[node])
            return schema_list
        except Exception as e:
            logger.error(f"Error splitting JSON schema: {e}")
            raise

    def return_schema(self, schema_id: str) -> dict:
        """
        Retrieve the first dictionary from a list where the 'id' key matches the schema_id.

        :param schema_id: The value of the 'id' key to match.
        :type schema_id: str

        :return: The dictionary that matches the schema_id, or None if not found.
        :rtype: dict
        """
        logger.info(f"Retrieving schema for schema ID: {schema_id}")
        try:
            if schema_id.endswith(".yaml"):
                schema_id = schema_id[:-5]

            result = next(
                (item for item in self.schema_list if item.get("id") == schema_id), None
            )
            if result is None:
                logger.error(f"{schema_id} not found in schema list")
            return result
        except Exception as e:
            logger.error(f"Error retrieving schema for {schema_id}: {e}")
            raise

    def schema_list_to_json(self, schema_list: list) -> dict:
        """
        Convert a list of JSON schemas to a dictionary where each key is the schema id
        with '.yaml' appended, and the value is the schema content.

        :param schema_list: A list of gen3 JSON schemas.
        :type schema_list: list

        :return: A dictionary with schema ids as keys and schema contents as values.
        :rtype: dict
        """
        logger.info("Converting schema list to JSON format.")
        try:
            schema_dict = {}
            for schema in schema_list:
                schema_id = schema.get("id")
                if schema_id:
                    schema_dict[f"{schema_id}.yaml"] = schema
            return schema_dict
        except Exception as e:
            logger.error(f"Error converting schema list to JSON: {e}")
            raise

    def get_schema_version(self, schema: dict = None) -> str:
        """
        Extract the version of the schema from the provided schema dictionary.

        :param schema: The schema dictionary from which to extract the version.
        :type schema: dict

        :return: The version of the schema.
        :rtype: str
        """
        if not schema:
            schema = self.schema
        try:
            version = schema['_settings.yaml']['_dict_version']
            return version
        except Exception as e:
            logger.error(f"Could not pull schema version {e}")
            raise

    def parse_schema(self):
        """
        Read the list of gen3 jsonschema, then split it into individual node schemas.

        Data is stored in :attr:`self.schema` and :attr:`self.schema_list`.
        """
        self.schema = self.read_json(self.schema_path)
        logger.info("Successfully read JSON schema.")
        self.nodes = self.get_nodes()
        self.schema_list = self.split_json()
        logger.info("Split schema into individual node schemas.")

    def calculate_node_order(self):
        """
        Call the methods to get node information, node pairs, and node order.
        """
        self.nodes = self.get_nodes()
        logger.info(f"Retrieved {len(self.nodes)} nodes from schema.")

        self.node_pairs = self.get_all_node_pairs()
        logger.info(f"Retrieved {len(self.node_pairs)} node pairs.")
        self.node_order = self.get_node_order(edges=self.node_pairs)
        logger.info("Determined node order based on dependencies.")

@dataclass
class PathInfo:
    """
    Data structure representing a single path in a directed graph.

    Attributes
    ----------
    path : List[str]
        The sequence of node names (as strings) representing the path from the root to the destination node.
    steps : int
        The number of steps (edges) in the path. This is typically `len(path) - 1`.
    """

    path: List[str]
    steps: int

def build_graph(
    edges: List[Tuple[str, str]],
    ignore_nodes: Optional[List[str]] = None
) -> Tuple[Dict[str, List[str]], Set[str], Set[str]]:
    """
    Build an adjacency list representation of a directed graph from a list of edges.

    Parameters
    ----------
    edges : List[Tuple[str, str]]
        A list of (upstream, downstream) node pairs representing directed edges in the graph.
    ignore_nodes : Optional[List[str]], optional
        A list of node names to ignore when building the graph. Edges involving these nodes are skipped.
        Defaults to None.

    Returns
    -------
    graph : Dict[str, List[str]]
        The adjacency list representation of the graph, mapping each node to a list of its downstream neighbors.
    all_nodes : Set[str]
        The set of all node names present in the graph (including both upstream and downstream nodes).
    downstream_nodes : Set[str]
        The set of all nodes that appear as downstream nodes in any edge.

    Examples
    --------
    >>> edges = [('A', 'B'), ('B', 'C')]
    >>> build_graph(edges)
    ({'A': ['B'], 'B': ['C']}, {'A', 'B', 'C'}, {'B', 'C'})
    """
    if ignore_nodes is None:
        ignore_nodes = []
    graph = defaultdict(list)
    all_nodes = set()
    downstream_nodes = set()
    for upstream, downstream in edges:
        if upstream in ignore_nodes or downstream in ignore_nodes:
            continue
        graph[upstream].append(downstream)
        all_nodes.add(upstream)
        all_nodes.add(downstream)
        downstream_nodes.add(downstream)
    return graph, all_nodes, downstream_nodes

def find_root_node(
    all_nodes: Set[str],
    downstream_nodes: Set[str],
    ignore_nodes: Optional[List[str]] = None,
    root_node: Optional[str] = None
) -> List[str]:
    """
    Identify the root nodes of a directed graph.

    A root node is defined as a node that does not appear as a downstream node in any edge,
    and is not in the ignore_nodes list. If a specific root_node is provided, only that node is returned.

    Parameters
    ----------
    all_nodes : Set[str]
        The set of all node names in the graph.
    downstream_nodes : Set[str]
        The set of all nodes that appear as downstream nodes in any edge.
    ignore_nodes : Optional[List[str]], optional
        A list of node names to ignore as possible roots. Defaults to None.
    root_node : Optional[str], optional
        If provided, this node is returned as the only root node.

    Returns
    -------
    List[str]
        A list of root node names.

    Examples
    --------
    >>> all_nodes = {'A', 'B', 'C'}
    >>> downstream_nodes = {'B', 'C'}
    >>> find_root_node(all_nodes, downstream_nodes)
    ['A']
    """
    if ignore_nodes is None:
        ignore_nodes = []
    if root_node is not None:
        return [root_node]
    return [node for node in all_nodes if node not in downstream_nodes and node not in ignore_nodes]

def find_all_paths(
    graph: Dict[str, List[str]],
    start_node: str,
    ignore_nodes: Optional[List[str]] = None
) -> List[List[str]]:
    """
    Find all possible acyclic paths starting from a given node in a directed graph.

    Parameters
    ----------
    graph : Dict[str, List[str]]
        The adjacency list representation of the graph.
    start_node : str
        The node from which to start searching for paths.
    ignore_nodes : Optional[List[str]], optional
        A list of node names to ignore during traversal. Defaults to None.

    Returns
    -------
    List[List[str]]
        A list of paths, where each path is a list of node names (strings) from the start_node to a destination node.
        Each path has at least two nodes (start and destination).

    Notes
    -----
    - Cycles are avoided: a node is not revisited in the same path.
    - Nodes in ignore_nodes are not included in any path.

    Examples
    --------
    >>> graph = {'A': ['B', 'C'], 'B': ['C'], 'C': []}
    >>> find_all_paths(graph, 'A')
    [['A', 'B'], ['A', 'B', 'C'], ['A', 'C']]
    """
    if ignore_nodes is None:
        ignore_nodes = []
    paths = []

    def dfs(current_node, current_path):
        if current_node in ignore_nodes:
            return
        new_path = current_path + [current_node]
        if len(new_path) > 1:
            paths.append(new_path)
        for neighbor in graph.get(current_node, []):
            if neighbor not in new_path and neighbor not in ignore_nodes:
                dfs(neighbor, new_path)
    dfs(start_node, [])
    return paths

def group_paths_by_destination(
    edges: list,
    ignore_nodes: list = ["core_metadata_collection"],
    root_node: Optional[str] = None
) -> Dict[str, List[PathInfo]]:
    """
    Find and group all possible acyclic paths in a directed graph by their destination node.

    For each destination node, all unique paths from any root node (or a specified root_node) to that destination
    are collected, ignoring any nodes in ignore_nodes.

    Parameters
    ----------
    edges : list of tuple
        List of (upstream, downstream) node pairs representing the directed edges of the graph.
    ignore_nodes : list, optional
        List of node names to ignore in the graph and in path traversal. Defaults to ["core_metadata_collection"].
    root_node : Optional[str], optional
        If provided, only paths starting from this node are considered as root paths.

    Returns
    -------
    Dict[str, List[PathInfo]]
        A dictionary mapping each destination node name to a list of PathInfo objects,
        each representing a unique path from a root node to that destination.

    Examples
    --------
    >>> edges = [('A', 'B'), ('B', 'C')]
    >>> group_paths_by_destination(edges)
    {'B': [PathInfo(path=['A', 'B'], steps=1)], 'C': [PathInfo(path=['A', 'B', 'C'], steps=2)]}
    """
    graph, all_nodes, downstream_nodes = build_graph(edges, ignore_nodes)
    root_nodes = find_root_node(all_nodes, downstream_nodes, ignore_nodes, root_node)
    print("Graph root node(s):", root_nodes)

    structured_results = defaultdict(list)
    for node in root_nodes:
        if node not in ignore_nodes:
            all_paths = find_all_paths(graph, node, ignore_nodes)
            for path in all_paths:
                destination_node = path[-1]
                path_info = PathInfo(path=path, steps=len(path) - 1)
                structured_results[destination_node].append(path_info)
    return dict(structured_results)

def get_min_node_path(
    edges: list,
    target_node: str,
    ignore_nodes: list = ["core_metadata_collection"],
    root_node: Optional[str] = None
) -> PathInfo:
    """
    Find the shortest path from a root node (or specified root_node) to a target node in a directed graph.

    Parameters
    ----------
    edges : list of tuple
        List of (upstream, downstream) node pairs representing the directed edges of the graph.
    target_node : str
        The destination node for which the shortest path is sought.
    ignore_nodes : list, optional
        List of node names to ignore in the graph and in path traversal. Defaults to ["core_metadata_collection"].
    root_node : Optional[str], optional
        If provided, only paths starting from this node are considered as root paths.

    Returns
    -------
    PathInfo
        The PathInfo object representing the shortest path from a root node to the target_node.

    Raises
    ------
    ValueError
        If no path exists from any root node to the target_node.

    Examples
    --------
    >>> edges = [('A', 'B'), ('B', 'C')]
    >>> get_min_node_path(edges, 'C')
    PathInfo(path=['A', 'B', 'C'], steps=2)
    """
    graph, all_nodes, downstream_nodes = build_graph(edges, ignore_nodes)
    root_nodes = find_root_node(all_nodes, downstream_nodes, ignore_nodes, root_node)
    all_paths_by_dest = group_paths_by_destination(edges, ignore_nodes=ignore_nodes, root_node=root_node)
    all_paths = all_paths_by_dest.get(target_node, [])
    root_paths = [p for p in all_paths if p.path and p.path[0] in root_nodes]
    if not root_paths:
        raise ValueError(f"No path from any root node to {target_node}")
    return min(root_paths, key=lambda path: path.steps)